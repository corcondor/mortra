"""Exchange typed Yuclid facts with exact polynomial specialists.

The separator keeps native geometric relations intact until the final exact
coordinate lowering.  It is deliberately problem-independent: candidate
premises are selected by predicate support, point incidence, and polynomial
scope, never by benchmark name or expected answer.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Iterable

import sympy as sp
from newclid.jgex.formulation import JGEXFormulation

from worker.backend.bounded_macaulay_membership import (
    BoundedMacaulayCertificate,
    certify_bounded_macaulay_membership,
)
from worker.backend.certified_buchberger import (
    CertifiedBuchbergerDAGResult,
    CertifiedDAGIdealMembership,
    certified_buchberger_dag,
    certify_dag_ideal_membership,
)
from worker.backend.geometry_proof_hypergraph import Atom
from worker.backend.jgex_exact_constraint_bridge import (
    JGEXExactSystemAnalysis,
    inspect_jgex_exact_system,
    inspect_jgex_relation_polynomials,
)
from worker.backend.local_polynomial_elimination import (
    LocalEliminationResult,
    eliminate_local_linear_variables,
)


SUPPORTED_RELATIONS: dict[str, int] = {
    "coll": 3,
    "para": 4,
    "perp": 4,
    "cong": 4,
    "cyclic": 4,
    "eqangle": 8,
    "eqratio": 8,
    "midp": 3,
}


@dataclass(frozen=True)
class TypedBoundaryPremise:
    atom: str
    source_atom: str
    derivation: str
    predicate: str
    arguments: tuple[str, ...]
    polynomial: str
    shared_target_points: int
    shared_target_variables: int
    polynomial_variable_count: int
    expanded_term_count: int


@dataclass(frozen=True)
class TypedSeparatorStage:
    name: str
    native_premise_count: int
    construction_equation_count: int
    generator_count: int
    variable_count: int
    processed_pair_count: int
    basis_size: int
    stopped_reason: str
    groebner_complete: bool
    all_identities_replayed: bool
    goal_proved: bool
    goal_replayed: bool
    goal_remainder: str


@dataclass(frozen=True)
class TypedMacaulayAttempt:
    generator_source: str
    saturation_multiplier: str
    saturation_assumptions_used: tuple[str, ...]
    certificate: BoundedMacaulayCertificate


@dataclass(frozen=True)
class TypedRelationSeparatorCertificate:
    status: str
    target_atom: str
    target_polynomial: str
    source_setup_sha256: str
    native_fact_basis_sha256: str
    selection_policy: str
    selected_native_premises: tuple[TypedBoundaryPremise, ...]
    selected_construction_equations: tuple[str, ...]
    variables: tuple[str, ...]
    local_elimination: LocalEliminationResult | None
    macaulay_attempts: tuple[TypedMacaulayAttempt, ...]
    stages: tuple[TypedSeparatorStage, ...]
    proof_dag: CertifiedBuchbergerDAGResult | None
    membership: CertifiedDAGIdealMembership | None
    exact_replay: bool
    certificate_sha256: str


def _render_atom(atom: Atom) -> str:
    return f"{atom.predicate} {' '.join(atom.arguments)}"


def relation_is_nondegenerate(atom: Atom) -> bool:
    """Reject relation syntax containing a zero segment or repeated locus."""

    atom = atom.canonical()
    if atom.predicate in {"para", "perp", "cong"} and len(atom.arguments) == 4:
        return (
            atom.arguments[0] != atom.arguments[1]
            and atom.arguments[2] != atom.arguments[3]
        )
    if atom.predicate in {"eqangle", "eqratio"} and len(atom.arguments) == 8:
        return all(
            atom.arguments[index] != atom.arguments[index + 1]
            for index in range(0, 8, 2)
        )
    if atom.predicate == "coll":
        return len(set(atom.arguments)) == 3
    if atom.predicate == "cyclic":
        return len(set(atom.arguments)) >= 4
    if atom.predicate == "midp" and len(atom.arguments) == 3:
        return atom.arguments[1] != atom.arguments[2]
    return True


def relation_is_informative(atom: Atom) -> bool:
    """Reject relation instances whose polynomial is identically zero by syntax."""

    atom = atom.canonical()
    if atom.predicate in {"cong", "para", "perp"} and len(atom.arguments) == 4:
        left = frozenset(atom.arguments[:2])
        right = frozenset(atom.arguments[2:])
        return left != right
    if atom.predicate in {"eqangle", "eqratio"} and len(atom.arguments) == 8:
        left = tuple(frozenset(atom.arguments[index : index + 2]) for index in (0, 2))
        right = tuple(frozenset(atom.arguments[index : index + 2]) for index in (4, 6))
        return left != right
    return True


def _relation_candidates_with_provenance(
    native_facts: Iterable[Atom],
) -> tuple[tuple[Atom, Atom, str], ...]:
    """Expose native relations plus sound low-degree consequences.

    Yuclid's ``circle o a b c`` statement has a distinguished center ``o``.
    Its radius equalities are logically immediate and usually much smaller
    than flattening the corresponding cyclic determinant after substitution.
    """

    records: dict[Atom, tuple[Atom, str]] = {}
    facts = tuple(native_facts)
    circle_components_by_center: dict[str, list[set[str]]] = {}
    for raw in facts:
        if raw.predicate.lower() != "circle" or len(raw.arguments) < 4:
            continue
        center, *points = raw.arguments
        components = circle_components_by_center.setdefault(center, [])
        merged = set(points)
        disjoint: list[set[str]] = []
        for component in components:
            if component & merged:
                merged.update(component)
            else:
                disjoint.append(component)
        components[:] = [*disjoint, merged]
    centered_circle_point_sets = tuple(
        frozenset(component)
        for components in circle_components_by_center.values()
        for component in components
    )
    for raw in facts:
        atom = raw.canonical()
        if atom.predicate == "cyclic" and any(
            set(atom.arguments) <= points
            for points in centered_circle_point_sets
        ):
            continue
        if atom.predicate in SUPPORTED_RELATIONS:
            records.setdefault(atom, (raw, "native"))
    for raw in facts:
        if raw.predicate.lower() != "circle" or len(raw.arguments) < 3:
            continue
        center, radius_point, *other_points = raw.arguments
        for point in other_points:
            derived = Atom(
                "cong",
                (center, radius_point, center, point),
            ).canonical()
            records.setdefault(
                derived,
                (raw, "circle_radius_congruence"),
            )
    return tuple(
        (atom, source, derivation)
        for atom, (source, derivation) in sorted(
            records.items(),
            key=lambda item: (item[0].predicate, item[0].arguments),
        )
    )


def _replace_goal(text: str, atom: Atom) -> str:
    formulation = JGEXFormulation.from_text(text.strip())
    setup = "; ".join(map(str, formulation.setup_clauses))
    if not setup:
        raise ValueError("typed separator requires a nonempty JGEX setup")
    return f"{setup} ? {_render_atom(atom)}"


def _safe_sympify(value: str, symbols: dict[str, sp.Symbol]) -> sp.Expr:
    return sp.expand(sp.sympify(value, locals=symbols))


def _term_count(expression: sp.Expr) -> int:
    return len(sp.Add.make_args(sp.expand(expression)))


def _normalized_polynomial_key(expression: sp.Expr) -> str:
    variables = tuple(sorted(expression.free_symbols, key=str))
    polynomial = sp.Poly(sp.expand(expression), *variables, domain=sp.QQ)
    return sp.sstr(polynomial.monic().as_expr())


def _fact_basis_sha256(facts: Iterable[Atom]) -> str:
    material = "\n".join(
        sorted(_render_atom(atom.canonical()) for atom in facts)
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _semantic_candidates(
    target: Atom,
    native_facts: Iterable[Atom],
    *,
    limit: int,
    relevant_points: frozenset[str] | None = None,
) -> tuple[Atom, ...]:
    target = target.canonical()
    target_points = set(target.arguments)
    candidates: dict[Atom, None] = {}
    for raw in native_facts:
        atom = raw.canonical()
        expected_arity = SUPPORTED_RELATIONS.get(atom.predicate)
        if expected_arity is None or len(atom.arguments) != expected_arity:
            continue
        if atom == target or any(argument.startswith("?") for argument in atom.arguments):
            continue
        if not relation_is_nondegenerate(atom):
            continue
        if not relation_is_informative(atom):
            continue
        atom_points = set(atom.arguments)
        target_overlap = len(atom_points & target_points)
        boundary_overlap = len(atom_points & (relevant_points or target_points))
        if target_overlap < 1 or boundary_overlap < 2:
            continue
        candidates.setdefault(atom, None)

    simple_relations = {"coll", "para", "perp", "cong", "cyclic", "midp"}

    def rank(
        atom: Atom,
    ) -> tuple[int, int, int, int, int, str, tuple[str, ...]]:
        overlap = len(set(atom.arguments) & target_points)
        boundary_overlap = len(
            set(atom.arguments) & (relevant_points or target_points)
        )
        return (
            -(atom.predicate == target.predicate),
            -overlap,
            -boundary_overlap,
            -(atom.predicate in simple_relations),
            len(set(atom.arguments) - target_points),
            atom.predicate,
            atom.arguments,
        )

    ordered = sorted(candidates, key=rank)
    predicate_order = tuple(
        dict.fromkeys(
            (
                target.predicate,
                "perp",
                "para",
                "coll",
                "cong",
                "cyclic",
                "midp",
                "eqangle",
                "eqratio",
            )
        )
    )
    buckets = {
        predicate: [atom for atom in ordered if atom.predicate == predicate]
        for predicate in predicate_order
    }
    selected: list[Atom] = []
    offset = 0
    while len(selected) < limit:
        added = False
        for predicate in predicate_order:
            bucket = buckets[predicate]
            if offset < len(bucket):
                selected.append(bucket[offset])
                added = True
                if len(selected) >= limit:
                    break
        if not added:
            break
        offset += 1
    return tuple(selected)


def _elaborate_boundary_premises(
    source: str,
    target: Atom,
    native_facts: Iterable[Atom],
    *,
    semantic_limit: int,
    max_native_facts: int,
    target_variables: frozenset[sp.Symbol],
    relevant_points: frozenset[str],
    max_premise_terms: int,
) -> tuple[TypedBoundaryPremise, ...]:
    target_points = set(target.arguments)
    provenance = {
        atom: (source_atom, derivation)
        for atom, source_atom, derivation in _relation_candidates_with_provenance(
            native_facts
        )
    }
    candidates = _semantic_candidates(
        target,
        provenance,
        limit=semantic_limit,
        relevant_points=relevant_points,
    )
    try:
        evaluated = inspect_jgex_relation_polynomials(
            _replace_goal(source, target),
            tuple((atom.predicate, atom.arguments) for atom in candidates),
            representation="relational",
        )
    except (KeyError, TypeError, ValueError, sp.SympifyError):
        return ()
    records: list[TypedBoundaryPremise] = []
    for atom, relation in zip(candidates, evaluated, strict=True):
        try:
            polynomial = sp.expand(sp.sympify(relation.polynomial))
        except (KeyError, TypeError, ValueError, sp.SympifyError):
            continue
        if polynomial == 0:
            continue
        if _term_count(polynomial) > max_premise_terms:
            continue
        source_atom, derivation = provenance[atom]
        records.append(
            TypedBoundaryPremise(
                atom=_render_atom(atom),
                source_atom=_render_atom(source_atom),
                derivation=derivation,
                predicate=atom.predicate,
                arguments=atom.arguments,
                polynomial=sp.sstr(polynomial),
                shared_target_points=len(set(atom.arguments) & target_points),
                shared_target_variables=len(
                    polynomial.free_symbols & target_variables
                ),
                polynomial_variable_count=len(polynomial.free_symbols),
                expanded_term_count=_term_count(polynomial),
            )
        )

    records.sort(
        key=lambda item: (
            -(item.predicate == target.predicate),
            item.expanded_term_count,
            item.polynomial_variable_count,
            -item.shared_target_variables,
            -item.shared_target_points,
            item.atom,
        )
    )
    target_active_records = [
        item for item in records if item.shared_target_variables > 0
    ]
    if target_active_records:
        records = target_active_records
    selected: list[TypedBoundaryPremise] = []
    seen_polynomials: set[str] = set()
    for item in records:
        key = _normalized_polynomial_key(sp.sympify(item.polynomial))
        if key in seen_polynomials:
            continue
        seen_polynomials.add(key)
        selected.append(item)
        if len(selected) >= max_native_facts:
            break
    return tuple(selected)


def _select_construction_equations(
    analysis: JGEXExactSystemAnalysis,
    boundary_polynomials: tuple[sp.Expr, ...],
    goal: sp.Expr,
    *,
    limit: int,
    max_terms: int,
) -> tuple[sp.Expr, ...]:
    equations = tuple(
        sp.expand(sp.sympify(item)) for item in analysis.construction_equations
    )
    boundary_symbols = set(goal.free_symbols)
    boundary_symbols.update(
        symbol for polynomial in boundary_polynomials for symbol in polynomial.free_symbols
    )
    selected: list[sp.Expr] = []
    remaining = [item for item in equations if item != 0 and _term_count(item) <= max_terms]
    while remaining and len(selected) < limit:
        ranked = sorted(
            remaining,
            key=lambda item: (
                -len(item.free_symbols & boundary_symbols),
                len(item.free_symbols - boundary_symbols),
                _term_count(item),
                sp.sstr(item),
            ),
        )
        candidate = ranked[0]
        if not (candidate.free_symbols & boundary_symbols):
            break
        selected.append(candidate)
        boundary_symbols.update(candidate.free_symbols)
        remaining.remove(candidate)
    return tuple(selected)


def _backward_point_boundary(
    analysis: JGEXExactSystemAnalysis,
    target: Atom,
    *,
    depth: int = 2,
) -> frozenset[str]:
    points = set(target.arguments)
    frontier = set(points)
    for _ in range(depth):
        discovered: set[str] = set()
        for block in analysis.construction_blocks:
            if set(block.outputs) & frontier:
                discovered.update(block.inputs)
                discovered.update(block.outputs)
        discovered -= points
        if not discovered:
            break
        points.update(discovered)
        frontier = discovered
    return frozenset(points)


def _saturation_specs(
    analysis: JGEXExactSystemAnalysis,
    symbols: dict[str, sp.Symbol],
    goal: sp.Expr,
    generators: tuple[sp.Expr, ...],
    *,
    allowed_symbols: frozenset[sp.Symbol],
    limit: int = 4,
) -> tuple[tuple[sp.Expr, tuple[str, ...]], ...]:
    generator_symbols = set().union(*(item.free_symbols for item in generators))
    factors: dict[str, tuple[sp.Expr, str]] = {}
    for condition in analysis.executable_regularity_conditions:
        if not condition.strip().endswith("!= 0"):
            continue
        expression = condition.rsplit("!=", 1)[0].strip()
        try:
            factor = _safe_sympify(expression, symbols)
        except (TypeError, ValueError, sp.SympifyError):
            continue
        if factor == 0 or not factor.free_symbols:
            continue
        if not factor.free_symbols <= allowed_symbols:
            continue
        if not (factor.free_symbols & generator_symbols):
            continue
        factors.setdefault(sp.sstr(factor), (factor, condition))
    ordered = sorted(
        factors.values(),
        key=lambda item: (
            _term_count(item[0]),
            -len(item[0].free_symbols & goal.free_symbols),
            len(item[0].free_symbols),
            sp.sstr(item[0]),
        ),
    )[:limit]
    specs: list[tuple[sp.Expr, tuple[str, ...]]] = [(sp.Integer(1), ())]
    specs.extend((factor, (condition,)) for factor, condition in ordered)
    if len(ordered) >= 2:
        specs.append(
            (
                sp.expand(ordered[0][0] * ordered[1][0]),
                (ordered[0][1], ordered[1][1]),
            )
        )
    return tuple(specs)


def _stage_record(
    name: str,
    *,
    native_count: int,
    construction_count: int,
    generator_count: int,
    variable_count: int,
    dag: CertifiedBuchbergerDAGResult,
    membership: CertifiedDAGIdealMembership,
) -> TypedSeparatorStage:
    return TypedSeparatorStage(
        name=name,
        native_premise_count=native_count,
        construction_equation_count=construction_count,
        generator_count=generator_count,
        variable_count=variable_count,
        processed_pair_count=dag.processed_pair_count,
        basis_size=len(dag.basis_polynomials),
        stopped_reason=dag.stopped_reason,
        groebner_complete=dag.groebner_complete,
        all_identities_replayed=dag.all_identities_replayed,
        goal_proved=membership.proved,
        goal_replayed=membership.replayed,
        goal_remainder=membership.remainder,
    )


def certify_typed_relation_separator(
    text: str,
    target: Atom,
    native_facts: Iterable[Atom],
    *,
    semantic_limit: int = 24,
    max_native_facts: int = 8,
    max_construction_equations: int = 4,
    max_pairs: int = 80,
    max_basis_size: int = 64,
    max_polynomial_terms: int = 400,
    max_premise_terms: int = 96,
    max_certificate_terms: int = 4_000,
    max_local_variables: int = 20,
    max_local_elimination_steps: int = 12,
    max_local_separator_variables: int = 8,
    enable_local_projection: bool = False,
) -> TypedRelationSeparatorCertificate:
    """Prove ``target`` from typed native facts and a bounded local separator.

    The procedure is sound but intentionally incomplete.  Failure is reported
    as ``open``; a proof is accepted only when the full Buchberger DAG and final
    ideal-membership edge replay exactly.
    """

    source = text.strip()
    target = target.canonical()
    target_source = _replace_goal(source, target)
    target_analysis = inspect_jgex_exact_system(
        target_source,
        representation="relational",
    )
    symbols = {name: sp.Symbol(name) for name in target_analysis.variables}
    goal = _safe_sympify(target_analysis.goal_polynomial, symbols)
    facts = tuple(atom.canonical() for atom in native_facts)
    premises = _elaborate_boundary_premises(
        source,
        target,
        facts,
        semantic_limit=semantic_limit,
        max_native_facts=max_native_facts,
        target_variables=frozenset(goal.free_symbols),
        relevant_points=_backward_point_boundary(target_analysis, target),
        max_premise_terms=max_premise_terms,
    )
    premise_polynomials = tuple(
        _safe_sympify(item.polynomial, symbols) for item in premises
    )
    construction_equations = _select_construction_equations(
        target_analysis,
        premise_polynomials,
        goal,
        limit=max_construction_equations,
        max_terms=max_polynomial_terms,
    )
    all_expressions = (*premise_polynomials, *construction_equations, goal)
    all_symbols = set().union(*(item.free_symbols for item in all_expressions))
    ordered_variables = tuple(
        symbol
        for name, symbol in symbols.items()
        if symbol in all_symbols
    )
    missing = sorted(all_symbols - set(ordered_variables), key=str)
    ordered_variables = (*ordered_variables, *missing)
    if not ordered_variables:
        raise ValueError("typed separator produced a constant polynomial system")

    combined_generators = tuple(
        item
        for item in (*premise_polynomials, *construction_equations)
        if item != 0
    )
    local_elimination = (
        eliminate_local_linear_variables(
            combined_generators,
            ordered_variables,
            protected_variables=goal.free_symbols,
            max_steps=max_local_elimination_steps,
            max_output_terms=max_premise_terms,
            max_resultant_degree=1,
            max_separator_variables=max_local_separator_variables,
            ordering_strategy="min_fill",
        )
        if enable_local_projection and combined_generators
        else None
    )
    projected_generators = (
        tuple(
            sp.expand(sp.sympify(item))
            for item in local_elimination.remaining_polynomials
        )
        if local_elimination is not None
        and local_elimination.exact_replay
        and local_elimination.steps
        else ()
    )

    stage_inputs: tuple[tuple[str, tuple[sp.Expr, ...], tuple[sp.Expr, ...]], ...] = ()
    fact_depths = tuple(
        dict.fromkeys(
            min(depth, len(premise_polynomials)) for depth in (4, 8, 12)
        )
    )
    for depth in fact_depths:
        if depth:
            stage_inputs += (
                (f"typed_facts_d{depth}", premise_polynomials[:depth], ()),
            )
    if construction_equations:
        for depth in fact_depths[:2]:
            if depth:
                stage_inputs += (
                    (
                        f"typed_facts_d{depth}_plus_local_construction",
                        premise_polynomials[:depth],
                        construction_equations,
                    ),
                )
    if projected_generators:
        stage_inputs = (
            (
                "typed_local_linear_projection",
                projected_generators,
                (),
            ),
            *stage_inputs,
        )

    stage_records: list[TypedSeparatorStage] = []
    macaulay_attempts: list[TypedMacaulayAttempt] = []
    macaulay_inputs = (
        *(
            (("typed_local_linear_projection", projected_generators),)
            if projected_generators
            else ()
        ),
        ("typed_facts", premise_polynomials),
        ("typed_facts_plus_local_construction", combined_generators),
    )
    for generator_source, generators in macaulay_inputs:
        active_symbols = set(goal.free_symbols).union(
            *(item.free_symbols for item in generators)
        )
        active_variables = tuple(
            item for item in ordered_variables if item in active_symbols
        )
        macaulay_degree = (
            1
            if len(active_variables) <= max_local_variables
            and sum(_term_count(item) for item in generators) <= 240
            else 0
        )
        if not generators:
            continue
        for multiplier, assumptions in _saturation_specs(
            target_analysis,
            symbols,
            goal,
            tuple(generators),
            allowed_symbols=frozenset(active_variables),
        ):
            certificate = certify_bounded_macaulay_membership(
                generators,
                active_variables,
                sp.expand(multiplier * goal),
                max_multiplier_degree=macaulay_degree,
                max_matrix_columns=512,
                max_matrix_rows=2_048,
            )
            macaulay_attempts.append(
                TypedMacaulayAttempt(
                    generator_source=generator_source,
                    saturation_multiplier=sp.sstr(multiplier),
                    saturation_assumptions_used=assumptions,
                    certificate=certificate,
                )
            )
            if certificate.proved and certificate.replayed:
                break
        if macaulay_attempts[-1].certificate.proved:
            break

    accepted_macaulay = next(
        (
            item
            for item in macaulay_attempts
            if item.certificate.proved and item.certificate.replayed
        ),
        None,
    )
    accepted_dag: CertifiedBuchbergerDAGResult | None = None
    accepted_membership: CertifiedDAGIdealMembership | None = None
    buchberger_inputs = stage_inputs
    for name, native_generators, construction_generators in (
        () if accepted_macaulay is not None else buchberger_inputs
    ):
        generators = tuple(
            item for item in (*native_generators, *construction_generators) if item != 0
        )
        if not generators:
            continue
        active_symbols = set(goal.free_symbols).union(
            *(item.free_symbols for item in generators)
        )
        active_variables = tuple(
            item for item in ordered_variables if item in active_symbols
        )
        if (
            len(active_variables) > max_local_variables
            or sum(_term_count(item) for item in generators) > 240
        ):
            continue
        dag = certified_buchberger_dag(
            generators,
            active_variables,
            max_pairs=max_pairs,
            max_basis_size=max_basis_size,
            max_polynomial_terms=max_polynomial_terms,
            max_certificate_terms=max_certificate_terms,
            membership_target=goal,
        )
        membership = certify_dag_ideal_membership(goal, dag)
        stage_records.append(
            _stage_record(
                name,
                native_count=len(native_generators),
                construction_count=len(construction_generators),
                generator_count=len(generators),
                variable_count=len(active_variables),
                dag=dag,
                membership=membership,
            )
        )
        if (
            membership.proved
            and membership.replayed
            and dag.all_identities_replayed
        ):
            accepted_dag = dag
            accepted_membership = membership
            break

    exact_replay = accepted_macaulay is not None or (
        accepted_dag is not None and accepted_membership is not None
    )
    source_setup = "; ".join(
        map(str, JGEXFormulation.from_text(source).setup_clauses)
    )
    digest_payload = {
        "target": _render_atom(target),
        "target_polynomial": sp.sstr(goal),
        "source_setup_sha256": hashlib.sha256(source_setup.encode()).hexdigest(),
        "native_fact_basis_sha256": _fact_basis_sha256(facts),
        "premises": [asdict(item) for item in premises],
        "construction_equations": [sp.sstr(item) for item in construction_equations],
        "local_elimination": (
            asdict(local_elimination) if local_elimination is not None else None
        ),
        "membership_sha256": (
            accepted_macaulay.certificate.certificate_sha256
            if accepted_macaulay is not None
            else
            accepted_membership.certificate_sha256
            if accepted_membership is not None
            else None
        ),
    }
    certificate_sha256 = hashlib.sha256(
        json.dumps(digest_payload, ensure_ascii=True, sort_keys=True).encode()
    ).hexdigest()
    return TypedRelationSeparatorCertificate(
        status="proved" if exact_replay else "open",
        target_atom=_render_atom(target),
        target_polynomial=sp.sstr(goal),
        source_setup_sha256=digest_payload["source_setup_sha256"],
        native_fact_basis_sha256=digest_payload["native_fact_basis_sha256"],
        selection_policy=(
            "typed relation arity + >=2 shared boundary points + polynomial scope; "
            "native circle-to-radius-congruence theorem + nontrivial relations + "
            "polynomial-equivalence quotient + goal-variable ranking + bounded "
            "algebraic complexity + opt-in certified local projection; no problem "
            "IDs, expected answers, or numeric templates"
        ),
        selected_native_premises=premises,
        selected_construction_equations=tuple(
            sp.sstr(item) for item in construction_equations
        ),
        variables=tuple(map(str, ordered_variables)),
        local_elimination=local_elimination,
        macaulay_attempts=tuple(macaulay_attempts),
        stages=tuple(stage_records),
        proof_dag=accepted_dag,
        membership=accepted_membership,
        exact_replay=exact_replay,
        certificate_sha256=certificate_sha256,
    )
