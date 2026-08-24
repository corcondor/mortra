"""Certified construction-block AND-DAG for exact geometry elimination.

The polynomial backend already emits replayable clique-separator identities.
This module restores the construction provenance that is otherwise lost when
all JGEX equations are flattened into one ideal.  A terminal proof is accepted
only when every local identity and the root ideal-membership certificate replay.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
from typing import Any, Callable, Iterable

import sympy as sp

from worker.backend.jgex_exact_constraint_bridge import (
    ConstructionEquationBlock,
    inspect_jgex_exact_system,
    inspect_jgex_relation_polynomials,
)
from worker.backend.chordal_buchberger_elimination import (
    eliminate_with_certified_chordal_buchberger,
)
from worker.backend.local_polynomial_elimination import (
    eliminate_local_linear_variables,
)
from worker.backend.polynomial_relation_reelaborator import (
    TypedRelationReelaborationCertificate,
    reelaborate_polynomial_lemmas,
)


def _polynomial_key(value: str) -> str:
    return sp.sstr(sp.expand(sp.sympify(value)))


@dataclass(frozen=True)
class ConstructionBlockNode:
    node_id: str
    clause_index: int
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    construction_vocabulary: tuple[str, ...]
    parent_node_ids: tuple[str, ...]
    equations: tuple[str, ...]
    nonzero_conditions: tuple[str, ...]


@dataclass(frozen=True)
class SeparatorLemmaNode:
    node_id: str
    variable: str
    parent_node_ids: tuple[str, ...]
    input_polynomials: tuple[str, ...]
    output_polynomials: tuple[str, ...]
    separator_variables: tuple[str, ...]
    coefficient_nonzero_obligations: tuple[str, ...]
    buchberger_complete: bool
    goal_proved: bool
    goal_certificate_sha256: str | None
    replayed: bool
    certificate_sha256: str
    typed_relation_certificates: tuple[
        TypedRelationReelaborationCertificate, ...
    ] = ()


@dataclass(frozen=True)
class LocalEliminationLemmaNode:
    node_id: str
    variable: str
    method: str
    parent_node_ids: tuple[str, ...]
    input_polynomials: tuple[str, ...]
    output_polynomials: tuple[str, ...]
    separator_variables: tuple[str, ...]
    nonzero_conditions: tuple[str, ...]
    replayed: bool
    certificate_sha256: str
    typed_relation_certificates: tuple[
        TypedRelationReelaborationCertificate, ...
    ] = ()


@dataclass(frozen=True)
class RootProofNode:
    node_id: str
    parent_node_ids: tuple[str, ...]
    goal_polynomial: str
    remaining_polynomials: tuple[str, ...]
    proved: bool
    replayed: bool
    certificate_sha256: str | None
    typed_relation_certificates: tuple[
        TypedRelationReelaborationCertificate, ...
    ] = ()


@dataclass(frozen=True)
class ConstructionBlockProofDAGCertificate:
    status: str
    target_relation: str
    target_points: tuple[str, ...]
    guidance_relations: tuple[str, ...]
    guidance_polynomials: tuple[str, ...]
    guidance_relation_branches: tuple[tuple[str, ...], ...]
    guidance_polynomial_branches: tuple[tuple[str, ...], ...]
    elimination_ordering_strategy: str
    obligation_cost_slack: int
    construction_nodes: tuple[ConstructionBlockNode, ...]
    local_elimination_nodes: tuple[LocalEliminationLemmaNode, ...]
    separator_nodes: tuple[SeparatorLemmaNode, ...]
    root: RootProofNode
    eliminated_variables: tuple[str, ...]
    remaining_variables: tuple[str, ...]
    prepass_stopped_reason: str | None
    stopped_reason: str | None
    all_local_certificates_replayed: bool
    exact_replay: bool
    certificate_sha256: str


def _construction_nodes(
    blocks: tuple[ConstructionEquationBlock, ...],
) -> tuple[ConstructionBlockNode, ...]:
    producers: dict[str, list[str]] = {}
    nodes: list[ConstructionBlockNode] = []
    for ordinal, block in enumerate(blocks):
        node_id = f"construction:{block.clause_index}:{ordinal}"
        parents = tuple(
            sorted(
                {
                    producer
                    for input_name in block.inputs
                    for producer in producers.get(input_name, ())
                }
            )
        )
        node = ConstructionBlockNode(
            node_id=node_id,
            clause_index=block.clause_index,
            inputs=block.inputs,
            outputs=block.outputs,
            construction_vocabulary=block.construction_vocabulary,
            parent_node_ids=parents,
            equations=tuple(map(_polynomial_key, block.surviving_equations)),
            nonzero_conditions=block.nonzero_conditions,
        )
        nodes.append(node)
        for output in block.outputs:
            producers.setdefault(output, []).append(node_id)
    return tuple(nodes)


def _certificate_hash(payload: dict[str, Any]) -> str:
    material = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _associate_key(value: str) -> str:
    expression = sp.factor(sp.sympify(value))
    if not expression.free_symbols:
        return "constant" if expression != 0 else "zero"
    variables = tuple(sorted(expression.free_symbols, key=str))
    return sp.sstr(sp.Poly(expression, *variables, domain=sp.QQ).monic().as_expr())


def _condition_expression(condition: str) -> str:
    return condition.rsplit("!=", 1)[0].strip()


def certify_construction_block_proof_dag(
    text: str,
    *,
    max_steps: int | None = None,
    max_separator_variables: int | None = 12,
    max_clique_polynomials: int = 32,
    max_pairs_per_clique: int = 4,
    max_basis_size_per_clique: int = 16,
    max_polynomial_terms: int = 1_000,
    max_witness_terms: int = 10_000,
    terminal_max_pairs: int = 64,
    terminal_max_basis_size: int = 32,
    local_prepass_max_steps: int = 16,
    local_prepass_max_output_terms: int = 256,
    local_prepass_max_resultant_degree: int = 2,
    local_prepass_max_separator_variables: int | None = None,
    enable_relation_reelaboration: bool = True,
    relation_reelaboration_max_lemmas: int = 32,
    relation_reelaboration_max_points: int = 5,
    relation_reelaboration_max_candidates: int = 1_024,
    relation_reelaboration_include_high_arity: bool = False,
    guidance_relations: Iterable[tuple[str, tuple[str, ...]]] = (),
    guidance_relation_branches: Iterable[
        Iterable[tuple[str, tuple[str, ...]]]
    ] = (),
    obligation_cost_slack: int = 1,
    progress_callback: Callable[[dict[str, object]], None] | None = None,
) -> ConstructionBlockProofDAGCertificate:
    """Build and replay a local-elimination AND-DAG for one typed JGEX goal."""

    system = inspect_jgex_exact_system(text, representation="relational")
    if progress_callback is not None:
        progress_callback(
            {
                "stage": "construction_chart_ready",
                "construction_block_count": len(system.construction_blocks),
                "equation_count": system.equation_count,
                "variable_count": system.variable_count,
                "maximum_expanded_terms": system.maximum_expanded_terms,
            }
        )
    symbols = {name: sp.Symbol(name) for name in system.variables}
    equations = tuple(
        sp.expand(sp.sympify(item, locals=symbols))
        for item in system.construction_equations
    )
    goal_polynomial = sp.expand(
        sp.sympify(system.goal_polynomial, locals=symbols)
    )
    raw_guidance_branches = tuple(
        tuple(
            (str(predicate), tuple(map(str, arguments)))
            for predicate, arguments in branch
        )
        for branch in guidance_relation_branches
    )
    raw_guidance = tuple(
        dict.fromkeys(
            (
                *(
                    (str(predicate), tuple(map(str, arguments)))
                    for predicate, arguments in guidance_relations
                ),
                *(relation for branch in raw_guidance_branches for relation in branch),
            )
        )
    )
    guidance_records: list[tuple[str, sp.Expr]] = []
    guidance_by_relation: dict[tuple[str, tuple[str, ...]], tuple[str, sp.Expr]] = {}
    for predicate, arguments in raw_guidance:
        try:
            relation = inspect_jgex_relation_polynomials(
                text,
                ((predicate, arguments),),
                representation="relational",
            )[0]
        except ValueError:
            continue
        expression = sp.expand(sp.sympify(relation.polynomial, locals=symbols))
        if expression.free_symbols:
            record = (f"{predicate}({','.join(arguments)})", expression)
            guidance_records.append(record)
            guidance_by_relation[(predicate, arguments)] = record
    guidance_polynomials = tuple(
        dict.fromkeys(expression for _, expression in guidance_records)
    )
    guidance_branches: list[tuple[tuple[str, sp.Expr], ...]] = []
    for branch in raw_guidance_branches:
        records = tuple(
            guidance_by_relation[item]
            for item in branch
            if item in guidance_by_relation
        )
        # Dropping one atom would turn an AND branch into an easier statement.
        if records and len(records) == len(branch):
            guidance_branches.append(records)
    guidance_polynomial_branches = tuple(
        dict.fromkeys(
            tuple(dict.fromkeys(expression for _, expression in branch))
            for branch in guidance_branches
        )
    )
    ordering_strategy = (
        "residual_conditioned"
        if guidance_polynomial_branches
        else "obligation_conditioned"
        if guidance_polynomials
        else "min_fill"
    )
    if progress_callback is not None:
        progress_callback(
            {
                "stage": "obligation_guidance_ready",
                "guidance_relation_count": len(guidance_records),
                "guidance_polynomial_count": len(guidance_polynomials),
                "guidance_branch_count": len(guidance_polynomial_branches),
                "elimination_ordering_strategy": ordering_strategy,
                "obligation_cost_slack": obligation_cost_slack,
            }
        )
    known_nonzero = {
        _associate_key(_condition_expression(condition))
        for condition in system.executable_regularity_conditions
    }

    def accepts_nondegeneracy(condition: str) -> bool:
        key = _associate_key(_condition_expression(condition))
        return key == "constant" or key in known_nonzero

    def prepass_progress(event: dict[str, object]) -> None:
        if progress_callback is not None:
            progress_callback(
                {
                    **event,
                    "stage": f"local_prepass_{event['stage']}",
                }
            )

    local_prepass = eliminate_local_linear_variables(
        equations,
        tuple(symbols.values()),
        protected_variables=goal_polynomial.free_symbols,
        max_steps=local_prepass_max_steps,
        max_output_terms=local_prepass_max_output_terms,
        max_resultant_degree=local_prepass_max_resultant_degree,
        max_separator_variables=(
            max_separator_variables
            if local_prepass_max_separator_variables is None
            else local_prepass_max_separator_variables
        ),
        ordering_strategy=ordering_strategy,
        guidance_polynomials=guidance_polynomials,
        guidance_branches=guidance_polynomial_branches,
        obligation_cost_slack=obligation_cost_slack,
        nonzero_condition_acceptor=accepts_nondegeneracy,
        progress_callback=prepass_progress,
    )
    if progress_callback is not None:
        progress_callback(
            {
                "stage": "local_prepass_completed",
                "step_count": len(local_prepass.steps),
                "eliminated_variable_count": len(
                    local_prepass.eliminated_variables
                ),
                "eliminated_variables": list(
                    local_prepass.eliminated_variables
                ),
                "remaining_variable_count": len(
                    local_prepass.remaining_variables
                ),
                "remaining_polynomial_count": len(
                    local_prepass.remaining_polynomials
                ),
                "stopped_reason": local_prepass.stopped_reason,
                "exact_replay": local_prepass.exact_replay,
            }
        )
    reduced_symbols = {
        name: symbols.get(name, sp.Symbol(name))
        for name in local_prepass.remaining_variables
    }
    reduced_equations = tuple(
        sp.expand(sp.sympify(item, locals=symbols))
        for item in local_prepass.remaining_polynomials
    )
    elimination = eliminate_with_certified_chordal_buchberger(
        reduced_equations,
        tuple(reduced_symbols.values()),
        protected_variables=goal_polynomial.free_symbols,
        goal_polynomial=goal_polynomial,
        guidance_polynomials=guidance_polynomials,
        guidance_branches=guidance_polynomial_branches,
        initial_residual_messages=tuple(
            sp.sympify(polynomial, locals=symbols)
            for step in local_prepass.steps
            for polynomial in step.output_polynomials
        ),
        ordering_strategy=ordering_strategy,
        obligation_cost_slack=obligation_cost_slack,
        max_steps=max_steps,
        max_separator_variables=max_separator_variables,
        max_clique_polynomials=max_clique_polynomials,
        max_pairs_per_clique=max_pairs_per_clique,
        max_basis_size_per_clique=max_basis_size_per_clique,
        max_polynomial_terms=max_polynomial_terms,
        max_witness_terms=max_witness_terms,
        terminal_max_pairs=terminal_max_pairs,
        terminal_max_basis_size=terminal_max_basis_size,
        progress_callback=progress_callback,
    )
    construction_nodes = _construction_nodes(system.construction_blocks)

    relation_by_polynomial: dict[
        str, tuple[TypedRelationReelaborationCertificate, ...]
    ] = {}
    if enable_relation_reelaboration and relation_reelaboration_max_lemmas > 0:
        candidate_lemmas = tuple(
            dict.fromkeys(
                polynomial
                for step in (*local_prepass.steps, *elimination.steps)
                for polynomial in step.output_polynomials
            )
        )[:relation_reelaboration_max_lemmas]
        candidate_lemmas = tuple(
            dict.fromkeys((*candidate_lemmas, *elimination.remaining_polynomials))
        )[:relation_reelaboration_max_lemmas]
        if candidate_lemmas:
            reelaborated = reelaborate_polynomial_lemmas(
                text,
                candidate_lemmas,
                max_points=relation_reelaboration_max_points,
                max_candidates_per_lemma=(
                    relation_reelaboration_max_candidates
                ),
                include_high_arity=(
                    relation_reelaboration_include_high_arity
                ),
            )
            relation_by_polynomial = {
                _polynomial_key(item.lemma_polynomial): item.certificates
                for item in reelaborated
            }
            if progress_callback is not None:
                progress_callback(
                    {
                        "stage": "typed_relation_reelaboration_completed",
                        "lemma_count": len(reelaborated),
                        "matched_lemma_count": sum(
                            bool(item.certificates) for item in reelaborated
                        ),
                        "certificate_count": sum(
                            len(item.certificates) for item in reelaborated
                        ),
                    }
                )

    provenance: dict[str, set[str]] = {}
    for node in construction_nodes:
        for equation in node.equations:
            provenance.setdefault(equation, set()).add(node.node_id)
    global_node_ids: dict[str, str] = {}
    for equation in system.construction_equations:
        key = _polynomial_key(equation)
        if key not in provenance:
            global_node_ids.setdefault(
                key,
                f"global:{hashlib.sha256(key.encode('utf-8')).hexdigest()[:12]}",
            )
            provenance[key] = {global_node_ids[key]}

    local_nodes: list[LocalEliminationLemmaNode] = []
    for index, step in enumerate(local_prepass.steps):
        node_id = f"local:{index}:{step.variable}"
        parent_ids = tuple(
            sorted(
                {
                    parent
                    for polynomial in step.input_polynomials
                    for parent in provenance.get(_polynomial_key(polynomial), ())
                }
            )
        )
        node = LocalEliminationLemmaNode(
            node_id=node_id,
            variable=step.variable,
            method=step.method,
            parent_node_ids=parent_ids,
            input_polynomials=step.input_polynomials,
            output_polynomials=step.output_polynomials,
            separator_variables=step.separator_variables,
            nonzero_conditions=step.nonzero_conditions,
            replayed=step.replayed,
            certificate_sha256=step.certificate_sha256,
            typed_relation_certificates=tuple(
                certificate
                for polynomial in step.output_polynomials
                for certificate in relation_by_polynomial.get(
                    _polynomial_key(polynomial), ()
                )
            ),
        )
        local_nodes.append(node)
        for polynomial in step.output_polynomials:
            provenance[_polynomial_key(polynomial)] = {node_id}

    separator_nodes: list[SeparatorLemmaNode] = []
    for index, step in enumerate(elimination.steps):
        node_id = f"separator:{index}:{step.variable}"
        parent_ids = tuple(
            sorted(
                {
                    parent
                    for polynomial in step.input_polynomials
                    for parent in provenance.get(_polynomial_key(polynomial), ())
                }
            )
        )
        node = SeparatorLemmaNode(
            node_id=node_id,
            variable=step.variable,
            parent_node_ids=parent_ids,
            input_polynomials=step.input_polynomials,
            output_polynomials=step.output_polynomials,
            separator_variables=step.separator_variables,
            coefficient_nonzero_obligations=(
                step.coefficient_nonzero_obligations
            ),
            buchberger_complete=step.buchberger_complete,
            goal_proved=bool(
                step.goal_membership is not None
                and step.goal_membership.proved
                and step.goal_membership.replayed
            ),
            goal_certificate_sha256=(
                step.goal_membership.certificate_sha256
                if step.goal_membership is not None
                else None
            ),
            replayed=step.replayed,
            certificate_sha256=step.certificate_sha256,
            typed_relation_certificates=tuple(
                certificate
                for polynomial in step.output_polynomials
                for certificate in relation_by_polynomial.get(
                    _polynomial_key(polynomial), ()
                )
            ),
        )
        separator_nodes.append(node)
        for polynomial in step.output_polynomials:
            provenance[_polynomial_key(polynomial)] = {node_id}

    local_goal_parents = tuple(
        node.node_id for node in separator_nodes if node.goal_proved
    )
    terminal_parents = tuple(
        sorted(
            set(local_goal_parents)
            | {
                parent
                for polynomial in elimination.remaining_polynomials
                for parent in provenance.get(_polynomial_key(polynomial), ())
            }
        )
    )
    membership = elimination.goal_membership
    root_replayed = bool(membership is not None and membership.replayed)
    root_proved = bool(membership is not None and membership.proved)
    root_certificate = (
        membership.certificate_sha256 if membership is not None else None
    )
    root = RootProofNode(
        node_id="root",
        parent_node_ids=terminal_parents,
        goal_polynomial=system.goal_polynomial,
        remaining_polynomials=elimination.remaining_polynomials,
        proved=root_proved,
        replayed=root_replayed,
        certificate_sha256=root_certificate,
        typed_relation_certificates=tuple(
            certificate
            for polynomial in elimination.remaining_polynomials
            for certificate in relation_by_polynomial.get(
                _polynomial_key(polynomial), ()
            )
        ),
    )
    structural_replay = all(
        item.replayed and item.composition_replayed
        for item in system.structural_lemma_certificates
    )
    local_replay = bool(
        local_prepass.exact_replay
        and elimination.exact_replay
        and structural_replay
        and all(node.replayed for node in local_nodes)
        and all(node.replayed for node in separator_nodes)
    )
    solved = bool(local_replay and root_proved and root_replayed)
    provisional = ConstructionBlockProofDAGCertificate(
        status="proved" if solved else "open",
        target_relation=system.channel,
        target_points=system.points,
        guidance_relations=tuple(item[0] for item in guidance_records),
        guidance_polynomials=tuple(map(sp.sstr, guidance_polynomials)),
        guidance_relation_branches=tuple(
            tuple(label for label, _ in branch) for branch in guidance_branches
        ),
        guidance_polynomial_branches=tuple(
            tuple(map(sp.sstr, branch)) for branch in guidance_polynomial_branches
        ),
        elimination_ordering_strategy=ordering_strategy,
        obligation_cost_slack=obligation_cost_slack,
        construction_nodes=construction_nodes,
        local_elimination_nodes=tuple(local_nodes),
        separator_nodes=tuple(separator_nodes),
        root=root,
        eliminated_variables=tuple(
            dict.fromkeys(
                (
                    *local_prepass.eliminated_variables,
                    *elimination.eliminated_variables,
                )
            )
        ),
        remaining_variables=elimination.remaining_variables,
        prepass_stopped_reason=local_prepass.stopped_reason,
        stopped_reason=elimination.stopped_reason,
        all_local_certificates_replayed=local_replay,
        exact_replay=solved,
        certificate_sha256="",
    )
    digest = _certificate_hash(asdict(provisional))
    return replace(provisional, certificate_sha256=digest)
