"""Compile existential proof obligations into finite construction candidates.

The compiler is deliberately independent of problem identifiers, expected
answers, and published auxiliary points.  It only uses typed relation atoms
declared by construction schemas and the currently open proof obligations.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from itertools import product
from typing import Iterable, Sequence

from worker.backend.geometry_proof_hypergraph import (
    Atom,
    atom_pattern_unifications,
)
from worker.backend.geometry_representation_atlas import (
    certify_relation_equivalence,
    equivalent_atoms,
)
from worker.backend.typed_candidate_alignment import (
    candidate_directly_satisfies_obligation,
    obligation_signature,
)
from worker.backend.typed_geometry_stalk import (
    ConstructionFamily,
    equivalent_construction_inputs,
)


def _is_variable(value: str) -> bool:
    return value.startswith("?")


@dataclass(frozen=True)
class TypedConstructionContract:
    """A construction schema viewed as a relation-producing typed morphism."""

    family: ConstructionFamily
    output_variable: str
    input_variables: tuple[str, ...]
    relation_atoms: tuple[Atom, ...]
    requirement_atoms: tuple[Atom, ...] = ()


@dataclass(frozen=True)
class ContractCandidate:
    family: str
    inputs: tuple[str, ...]
    matched_obligation: Atom
    matched_relation: Atom
    fixed_input_count: int
    contract_atom_count: int
    branch_match_count: int
    branch_hole_binding_count: int
    requirement_atoms: tuple[Atom, ...] = ()
    open_requirements: tuple[Atom, ...] = ()
    residual_frontier: tuple[Atom, ...] = ()
    residual_reduction: int = 0
    fully_closes_branch: bool = False
    plan_certificate_sha256: str = ""
    matched_via_chart: bool = False
    chart_name: str | None = None
    chart_certificate_sha256: str | None = None

    @property
    def executable(self) -> bool:
        """Whether all construction side conditions are already certified."""

        return not self.open_requirements

    @property
    def key(self) -> str:
        return f"{self.family}({','.join(self.inputs)})"

    @property
    def rank(self) -> tuple[object, ...]:
        return (
            0 if self.executable else 1,
            0 if self.fully_closes_branch else 1,
            -self.residual_reduction,
            -self.branch_match_count,
            -self.branch_hole_binding_count,
            len(self.residual_frontier),
            len(self.open_requirements),
            0 if not self.matched_via_chart else 1,
            self.contract_atom_count,
            len(self.inputs),
            -self.fixed_input_count,
            self.family,
            self.inputs,
        )


@dataclass(frozen=True)
class ContractSynthesisAudit:
    witness_obligations: int
    matched_obligations: int
    matched_contracts: int
    raw_generated_candidates: int
    generated_candidates: int
    truncated_contracts: int
    requirement_atoms: int = 0
    open_requirement_atoms: int = 0
    residual_reducing_candidates: int = 0
    fully_closing_candidates: int = 0
    chart_matched_candidates: int = 0
    executable_candidates: int = 0
    held_open_candidates: int = 0
    statically_rejected_candidates: int = 0


@dataclass(frozen=True)
class RequirementAssessment:
    """Proof status of the side conditions for one construction term."""

    proved: tuple[Atom, ...]
    open: tuple[Atom, ...]
    contradictory: tuple[Atom, ...]

    @property
    def executable(self) -> bool:
        return not self.open and not self.contradictory


def _statically_false_requirement(atom: Atom) -> bool:
    """Refute degeneracies that are false in every Euclidean realization."""

    atom = atom.canonical()
    name = atom.predicate
    args = atom.arguments
    if name == "diff" and len(args) == 2:
        return args[0] == args[1]
    if name == "ncoll" and len(args) >= 3:
        return len(set(args)) < 3
    if name in {"npara", "nperp"} and len(args) == 4:
        return args[0] == args[1] or args[2] == args[3]
    return False


def _statically_true_requirement(atom: Atom) -> bool:
    """Close only representation-independent reflexive identities."""

    atom = atom.canonical()
    if atom.predicate == "cong" and len(atom.arguments) == 4:
        return atom.arguments[:2] == atom.arguments[2:]
    return False


def _known_fact_implies_requirement(requirement: Atom, fact: Atom) -> bool:
    requirement = requirement.canonical()
    fact = fact.canonical()
    if requirement == fact:
        return True
    if requirement.predicate != "diff" or len(requirement.arguments) != 2:
        return False
    endpoints = frozenset(requirement.arguments)
    if fact.predicate == "ncoll" and len(set(fact.arguments)) >= 3:
        return endpoints.issubset(fact.arguments)
    if fact.predicate in {"npara", "nperp"} and len(fact.arguments) == 4:
        return endpoints in {
            frozenset(fact.arguments[:2]),
            frozenset(fact.arguments[2:]),
        }
    return False


def assess_construction_requirements(
    requirements: Iterable[Atom],
    known_facts: Iterable[Atom],
) -> RequirementAssessment:
    """Classify side conditions without treating point names as inequalities."""

    known = tuple(dict.fromkeys(item.canonical() for item in known_facts))
    proved: list[Atom] = []
    open_requirements: list[Atom] = []
    contradictory: list[Atom] = []
    for requirement in dict.fromkeys(item.canonical() for item in requirements):
        if _statically_false_requirement(requirement):
            contradictory.append(requirement)
        elif _statically_true_requirement(requirement) or any(
            _known_fact_implies_requirement(requirement, fact) for fact in known
        ):
            proved.append(requirement)
        else:
            open_requirements.append(requirement)
    return RequirementAssessment(
        proved=tuple(proved),
        open=tuple(open_requirements),
        contradictory=tuple(contradictory),
    )


@dataclass(frozen=True)
class ObligationBranchReduction:
    branches: tuple[tuple[Atom, ...], ...]
    progressed_branches: tuple[tuple[Atom, ...], ...]
    matched_atom_count: int
    fully_closed_branch_count: int


def carry_construction_requirements(
    reduction: ObligationBranchReduction,
    requirement_atoms: Iterable[Atom],
    known_facts: Iterable[Atom],
) -> ObligationBranchReduction:
    """Keep construction existence conditions in every surviving branch."""

    known = {item.canonical() for item in known_facts}
    open_requirements = tuple(
        dict.fromkeys(
            item.canonical()
            for item in requirement_atoms
            if item.canonical() not in known
        )
    )

    def attach(branch: tuple[Atom, ...]) -> tuple[Atom, ...]:
        return tuple(dict.fromkeys((*branch, *open_requirements)))

    branches = tuple(dict.fromkeys(attach(branch) for branch in reduction.branches))
    progressed = tuple(
        dict.fromkeys(attach(branch) for branch in reduction.progressed_branches)
    )
    return ObligationBranchReduction(
        branches=branches,
        progressed_branches=progressed,
        matched_atom_count=reduction.matched_atom_count,
        fully_closed_branch_count=sum(not branch for branch in progressed),
    )


def _best_consistent_branch_match(
    candidate_atoms: Sequence[Atom],
    branch: Sequence[Atom],
    *,
    use_representation_atlas: bool = False,
) -> tuple[tuple[int, int], frozenset[int], dict[str, str]]:
    """Find the largest branch subset closed by one consistent substitution."""

    edges: dict[
        tuple[int, int], tuple[tuple[tuple[str, str], ...], ...]
    ] = {}
    for candidate_index, candidate in enumerate(candidate_atoms):
        for demand_index, demand in enumerate(branch):
            demand_variants = (
                (demand.canonical(), *equivalent_atoms(demand))
                if use_representation_atlas
                else (demand.canonical(),)
            )
            substitutions = tuple(
                dict.fromkeys(
                    substitution
                    for variant in demand_variants
                    for substitution in atom_pattern_unifications(
                        variant, candidate
                    )
                )
            )
            if substitutions:
                edges[(candidate_index, demand_index)] = substitutions

    best = (0, 0)
    best_used = frozenset()
    best_substitution: dict[str, str] = {}

    def visit(
        candidate_index: int,
        used_demands: frozenset[int],
        substitution: dict[str, str],
        matches: int,
    ) -> None:
        nonlocal best, best_used, best_substitution
        if candidate_index == len(candidate_atoms):
            score = (matches, len(substitution))
            if score > best:
                best = score
                best_used = used_demands
                best_substitution = dict(substitution)
            return
        visit(candidate_index + 1, used_demands, substitution, matches)
        for demand_index in range(len(branch)):
            if demand_index in used_demands:
                continue
            for raw in edges.get((candidate_index, demand_index), ()):
                bindings = dict(raw)
                if any(
                    variable in substitution
                    and substitution[variable] != value
                    for variable, value in bindings.items()
                ):
                    continue
                visit(
                    candidate_index + 1,
                    used_demands | {demand_index},
                    {**substitution, **bindings},
                    matches + 1,
                )

    visit(0, frozenset(), {}, 0)
    return best, best_used, best_substitution


def consistent_branch_closure_score(
    candidate_atoms: Sequence[Atom],
    branch: Sequence[Atom],
    *,
    use_representation_atlas: bool = False,
) -> tuple[int, int]:
    """Count jointly closed branch atoms under one consistent substitution."""

    score, _, _ = _best_consistent_branch_match(
        candidate_atoms,
        branch,
        use_representation_atlas=use_representation_atlas,
    )
    return score


def reduce_obligation_branches(
    candidate_atoms: Sequence[Atom],
    branches: Iterable[Sequence[Atom]],
    *,
    use_representation_atlas: bool = False,
) -> ObligationBranchReduction:
    """Apply true construction postconditions to coherent proof branches.

    The same substitution is applied to every remaining atom in an AND branch.
    This prevents one auxiliary point from closing one premise while a later
    round silently rebinds the same proof variable to a different point.
    """

    reduced: list[tuple[Atom, ...]] = []
    progressed: list[tuple[Atom, ...]] = []
    matched_atom_count = 0
    fully_closed = 0
    for raw_branch in branches:
        branch = tuple(item.canonical() for item in raw_branch)
        score, residual = _reduce_one_branch(
            candidate_atoms,
            branch,
            use_representation_atlas=use_representation_atlas,
        )
        reduced.append(residual)
        if score[0] > 0:
            progressed.append(residual)
            matched_atom_count += score[0]
            fully_closed += not residual
    return ObligationBranchReduction(
        branches=tuple(dict.fromkeys(reduced)),
        progressed_branches=tuple(dict.fromkeys(progressed)),
        matched_atom_count=matched_atom_count,
        fully_closed_branch_count=fully_closed,
    )


def _reduce_one_branch(
    candidate_atoms: Sequence[Atom],
    branch: Sequence[Atom],
    *,
    use_representation_atlas: bool = False,
) -> tuple[tuple[int, int], tuple[Atom, ...]]:
    score, used, substitution = _best_consistent_branch_match(
        candidate_atoms,
        branch,
        use_representation_atlas=use_representation_atlas,
    )
    residual = tuple(
        dict.fromkeys(
            Atom(
                atom.predicate,
                tuple(
                    substitution.get(argument, argument)
                    for argument in atom.arguments
                ),
            ).canonical()
            for index, atom in enumerate(branch)
            if index not in used
        )
    )
    return score, residual


def instantiate_contract_atoms(
    contract: TypedConstructionContract,
    *,
    output: str,
    inputs: Sequence[str],
) -> tuple[Atom, ...]:
    substitution = {
        contract.output_variable: output,
        **dict(zip(contract.input_variables, inputs)),
    }
    return tuple(
        Atom(
            atom.predicate,
            tuple(substitution.get(argument, argument) for argument in atom.arguments),
        ).canonical()
        for atom in contract.relation_atoms
    )


def instantiate_contract_requirements(
    contract: TypedConstructionContract,
    *,
    output: str,
    inputs: Sequence[str],
) -> tuple[Atom, ...]:
    substitution = {
        contract.output_variable: output,
        **dict(zip(contract.input_variables, inputs)),
    }
    return tuple(
        Atom(
            atom.predicate,
            tuple(substitution.get(argument, argument) for argument in atom.arguments),
        ).canonical()
        for atom in contract.requirement_atoms
    )


def synthesize_contract_candidates(
    obligations: Iterable[Atom],
    contracts: Iterable[TypedConstructionContract],
    *,
    visible_entities: Sequence[str],
    output_entity: str,
    used_keys: Iterable[str] = (),
    max_candidates_per_contract: int = 32,
    max_candidates_per_obligation: int = 16,
    obligation_branches: Iterable[Sequence[Atom]] = (),
    known_facts: Iterable[Atom] = (),
    use_representation_atlas: bool = True,
) -> tuple[tuple[ContractCandidate, ...], ContractSynthesisAudit]:
    """Reverse-unify witness obligations with construction postconditions.

    A ground proposition is never converted directly into a new point.  Only
    an explicit typed hole may be filled by a construction output.  Inputs
    fixed by the obligation stay fixed; any remaining finite input slots are
    enumerated over entities already visible in the proof state.
    """

    if max_candidates_per_contract < 1:
        raise ValueError("max_candidates_per_contract must be positive")
    if max_candidates_per_obligation < 1:
        raise ValueError("max_candidates_per_obligation must be positive")
    entities = tuple(dict.fromkeys(map(str, visible_entities)))
    used = set(map(str, used_keys))
    witness_demands = tuple(
        signature.atom
        for signature in map(obligation_signature, obligations)
        if signature.requires_witness
    )
    branches = tuple(tuple(branch) for branch in obligation_branches)
    if not branches:
        branches = tuple((demand,) for demand in witness_demands)
    candidates: dict[str, ContractCandidate] = {}
    known = {item.canonical() for item in known_facts}
    matched_demands: set[Atom] = set()
    matched_contracts: set[tuple[str, Atom]] = set()
    truncated_contracts = 0
    statically_rejected_candidates = 0

    for demand in witness_demands:
        holes = set(obligation_signature(demand).holes)
        demand_variants = (
            (demand.canonical(), *equivalent_atoms(demand))
            if use_representation_atlas
            else (demand.canonical(),)
        )
        for contract in contracts:
            family = contract.family
            if len(contract.input_variables) != family.input_arity:
                continue
            generated_for_contract = 0
            contract_matched = False
            for relation in contract.relation_atoms:
                matching_variants = tuple(
                    variant
                    for variant in demand_variants
                    if relation.predicate.lower() == variant.predicate.lower()
                )
                for demand_variant in matching_variants:
                    chart_certificate = (
                        None
                        if demand_variant == demand.canonical()
                        else certify_relation_equivalence(demand, demand_variant)
                    )
                    if demand_variant != demand.canonical() and (
                        chart_certificate is None or not chart_certificate.replayed
                    ):
                        continue
                    for raw_substitution in atom_pattern_unifications(
                        relation, demand_variant
                    ):
                        substitution = dict(raw_substitution)
                        if substitution.get(contract.output_variable) not in holes:
                            continue
                        contract_matched = True
                        fixed: dict[str, str] = {}
                        free: list[str] = []
                        valid = True
                        for variable in contract.input_variables:
                            value = substitution.get(variable)
                            if value is None or _is_variable(value):
                                free.append(variable)
                            elif value in entities:
                                fixed[variable] = value
                            else:
                                valid = False
                                break
                        if not valid:
                            continue
                        assignments = product(entities, repeat=len(free))
                        for values in assignments:
                            input_binding = {**fixed, **dict(zip(free, values))}
                            inputs = tuple(
                                input_binding[variable]
                                for variable in contract.input_variables
                            )
                            if (
                                not family.allow_repeated_inputs
                                and len(set(inputs)) != len(inputs)
                            ):
                                continue
                            key = f"{family.name}({','.join(inputs)})"
                            equivalent_key_exists = any(
                                item.family == family.name
                                and equivalent_construction_inputs(
                                    family, item.inputs, inputs
                                )
                                for item in candidates.values()
                            )
                            if key in used or key in candidates or equivalent_key_exists:
                                continue
                            actual_atoms = instantiate_contract_atoms(
                                contract,
                                output=output_entity,
                                inputs=inputs,
                            )
                            if not candidate_directly_satisfies_obligation(
                                actual_atoms, demand_variant
                            ):
                                continue
                            branch_reductions = tuple(
                                (
                                    *_reduce_one_branch(
                                        actual_atoms,
                                        branch,
                                        use_representation_atlas=(
                                            use_representation_atlas
                                        ),
                                    ),
                                    tuple(item.canonical() for item in branch),
                                )
                                for branch in branches
                            )
                            best_branch, best_residual, source_branch = min(
                                branch_reductions,
                                key=lambda item: (
                                    -item[0][0],
                                    len(item[1]),
                                    -item[0][1],
                                    item[1],
                                ),
                            )
                            requirements = instantiate_contract_requirements(
                                contract,
                                output=output_entity,
                                inputs=inputs,
                            )
                            requirement_assessment = assess_construction_requirements(
                                requirements,
                                known,
                            )
                            if requirement_assessment.contradictory:
                                statically_rejected_candidates += 1
                                continue
                            open_requirements = requirement_assessment.open
                            plan_material = "|".join(
                                (
                                    family.name,
                                    output_entity,
                                    *inputs,
                                    *(str(item) for item in actual_atoms),
                                    *(str(item) for item in requirements),
                                    *(str(item) for item in source_branch),
                                    *(str(item) for item in best_residual),
                                    demand_variant.predicate,
                                    *(demand_variant.arguments),
                                    (
                                        chart_certificate.certificate_sha256
                                        if chart_certificate is not None
                                        else "direct"
                                    ),
                                )
                            )
                            proposal = ContractCandidate(
                                family=family.name,
                                inputs=inputs,
                                matched_obligation=demand,
                                matched_relation=relation,
                                fixed_input_count=len(fixed),
                                contract_atom_count=len(contract.relation_atoms),
                                branch_match_count=best_branch[0],
                                branch_hole_binding_count=best_branch[1],
                                requirement_atoms=requirements,
                                open_requirements=open_requirements,
                                residual_frontier=best_residual,
                                residual_reduction=(
                                    len(source_branch) - len(best_residual)
                                ),
                                fully_closes_branch=(
                                    not best_residual and not open_requirements
                                ),
                                plan_certificate_sha256=hashlib.sha256(
                                    plan_material.encode("utf-8")
                                ).hexdigest(),
                                matched_via_chart=(chart_certificate is not None),
                                chart_name=(
                                    chart_certificate.chart
                                    if chart_certificate is not None
                                    else None
                                ),
                                chart_certificate_sha256=(
                                    chart_certificate.certificate_sha256
                                    if chart_certificate is not None
                                    else None
                                ),
                            )
                            previous = candidates.get(key)
                            if previous is None or proposal.rank < previous.rank:
                                candidates[key] = proposal
                            generated_for_contract += 1
                            matched_demands.add(demand)
                            matched_contracts.add((family.name, demand))
                            if generated_for_contract >= max_candidates_per_contract:
                                truncated_contracts += 1
                                break
                        if generated_for_contract >= max_candidates_per_contract:
                            break
                if generated_for_contract >= max_candidates_per_contract:
                    break
            if contract_matched and generated_for_contract == 0:
                matched_contracts.add((family.name, demand))

    raw_candidates = tuple(sorted(candidates.values(), key=lambda item: item.rank))
    retained: list[ContractCandidate] = []
    retained_per_obligation: dict[Atom, int] = {}
    for candidate in raw_candidates:
        count = retained_per_obligation.get(candidate.matched_obligation, 0)
        if count >= max_candidates_per_obligation:
            continue
        retained.append(candidate)
        retained_per_obligation[candidate.matched_obligation] = count + 1
    ordered = tuple(retained)
    return ordered, ContractSynthesisAudit(
        witness_obligations=len(witness_demands),
        matched_obligations=len(matched_demands),
        matched_contracts=len(matched_contracts),
        raw_generated_candidates=len(raw_candidates),
        generated_candidates=len(ordered),
        truncated_contracts=truncated_contracts,
        requirement_atoms=sum(len(item.requirement_atoms) for item in ordered),
        open_requirement_atoms=sum(len(item.open_requirements) for item in ordered),
        residual_reducing_candidates=sum(
            item.residual_reduction > 0 for item in ordered
        ),
        fully_closing_candidates=sum(item.fully_closes_branch for item in ordered),
        chart_matched_candidates=sum(item.matched_via_chart for item in ordered),
        executable_candidates=sum(item.executable for item in ordered),
        held_open_candidates=sum(not item.executable for item in ordered),
        statically_rejected_candidates=statically_rejected_candidates,
    )
