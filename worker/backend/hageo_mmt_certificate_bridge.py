"""Exact MMT certificate exchange for HAGeo auxiliary-construction search.

The bridge never accepts a benchmark answer.  It transports replayed Horn
certificates between the Newclid rule theory and the universal Euclidean
relation theory, then returns derived facts and still-open typed obligations to
the search controller.  Yuclid remains the only benchmark truth criterion.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Iterable, Sequence

from worker.backend.geometry_proof_hypergraph import (
    Atom,
    BackwardObligation,
    Theorem,
    atom_pattern_unifications,
    matched_theorem_support_facts,
    synthesize_backward_obligations,
)
from worker.backend.mmt_exact_coordination import (
    MMTAtom,
    MMTExactCoordinator,
    MMTSymbolAssignment,
    MMTTheoryView,
)
from worker.backend.mortra_geometry_content_dictionary import POINT_RELATION_URIS
from worker.backend.symbolic_sheaf_coordination import RuleClosureAdapter


SHARED_THEORY = "https://mortra.dev/mmt/geometry/euclidean-relation"


_SCALAR_TAIL_SIGNATURES: dict[str, tuple[str, ...]] = {
    # Newclid/JGEX relation syntax.  The final token is a semantic constant,
    # not a point name.  Keeping that distinction is required before these
    # certificates can safely cross into algebraic or spatial theories.
    "aconst": ("Point2", "Point2", "Point2", "Point2", "Angle"),
    "lconst": ("Point2", "Point2", "Real"),
    "rconst": ("Point2", "Point2", "Point2", "Point2", "Real"),
}


def shared_argument_sorts(predicate: str, arity: int) -> tuple[str, ...]:
    """Return the conservative shared signature for a native relation.

    HAGeo/Newclid atoms are predominantly point relations.  A small number of
    arithmetic relations carry a literal in their last argument.  Unknown
    signatures remain opaque rather than being asserted to be point-only.
    """

    normalized = predicate.lower()
    explicit = _SCALAR_TAIL_SIGNATURES.get(normalized)
    if explicit is not None:
        if len(explicit) != arity:
            raise ValueError(
                f"unexpected {predicate} arity: expected {len(explicit)}, got {arity}"
            )
        return explicit
    point_relations = {
        "coll",
        "cong",
        "contri",
        "cyclic",
        "diff",
        "eqangle",
        "eqangle3",
        "eqpoint",
        "eqratio",
        "eqratio6",
        "midp",
        "ncoll",
        "npara",
        "nperp",
        "nsameside",
        "obtuse_angle",
        "para",
        "perp",
        "sameclock",
        "sameside",
        "simtri",
    }
    if normalized in point_relations:
        return ("Point2",) * arity
    return ("Opaque",) * arity


# Backwards-compatible private name for existing research scripts.
_shared_argument_sorts = shared_argument_sorts


def _shared_symbol_uri(predicate: str, *, arity: int | None = None) -> str:
    normalized = predicate.lower()
    base = POINT_RELATION_URIS.get(
        normalized,
        f"{SHARED_THEORY}?{normalized}",
    )
    if arity is None:
        return base
    return f"{base}/arity-{arity}"


@dataclass(frozen=True)
class MMTGoalExchange:
    goal: Atom
    solved: bool
    replayed: bool
    rounds: int
    proposed: int
    accepted: int
    rejected: int


@dataclass(frozen=True)
class HageoMMTExchange:
    input_fact_count: int
    selected_fact_count: int
    accepted_facts: tuple[Atom, ...]
    derived_facts: tuple[Atom, ...]
    certificates: int
    certificate_sha256: str
    goals: tuple[MMTGoalExchange, ...]
    obligations: tuple[BackwardObligation, ...]
    initial_open_demands: tuple[Atom, ...]
    open_demands: tuple[Atom, ...]
    proof_state_facts: tuple[Atom, ...] = ()
    selection_strategy: str = "goal-conditioned-proof-basis"

    @property
    def solved(self) -> bool:
        return bool(self.goals) and all(item.solved for item in self.goals)

    @property
    def replayed(self) -> bool:
        return bool(self.goals) and all(item.replayed for item in self.goals)

    @property
    def closed_demands(self) -> tuple[Atom, ...]:
        proved = {
            item.canonical()
            for item in (self.proof_state_facts or self.accepted_facts)
        }
        return tuple(
            item
            for item in self.initial_open_demands
            if item.canonical() in proved
        )

    @property
    def introduced_demands(self) -> tuple[Atom, ...]:
        initial = {item.canonical() for item in self.initial_open_demands}
        return tuple(
            item for item in self.open_demands if item.canonical() not in initial
        )

    @property
    def made_goal_progress(self) -> bool:
        return self.solved or bool(self.closed_demands)

    def to_audit(self) -> dict[str, object]:
        return {
            "input_fact_count": self.input_fact_count,
            "selected_fact_count": self.selected_fact_count,
            "selection_strategy": self.selection_strategy,
            "accepted_fact_count": len(self.accepted_facts),
            "proof_state_fact_count": len(self.proof_state_facts),
            "derived_fact_count": len(self.derived_facts),
            "certificate_count": self.certificates,
            "certificate_sha256": self.certificate_sha256,
            "solved": self.solved,
            "replayed": self.replayed,
            "initial_open_demand_count": len(self.initial_open_demands),
            "open_demand_count": len(self.open_demands),
            "closed_demand_count": len(self.closed_demands),
            "introduced_demand_count": len(self.introduced_demands),
            "made_goal_progress": self.made_goal_progress,
            "goals": [
                {
                    "goal": _render(item.goal),
                    "solved": item.solved,
                    "replayed": item.replayed,
                    "rounds": item.rounds,
                    "proposed": item.proposed,
                    "accepted": item.accepted,
                    "rejected": item.rejected,
                }
                for item in self.goals
            ],
        }


def _render(atom: Atom) -> str:
    canonical = atom.canonical()
    return f"{canonical.predicate}({','.join(canonical.arguments)})"


def _backward_relevant_theorems(
    goals: Sequence[Atom],
    theorems: Sequence[Theorem],
) -> tuple[Theorem, ...]:
    """Keep the finite theorem cone that can feed a goal predicate."""

    needed = {item.canonical().predicate for item in goals}
    selected: set[int] = set()
    changed = True
    while changed:
        changed = False
        for index, theorem in enumerate(theorems):
            if theorem.conclusion.canonical().predicate not in needed:
                continue
            if index not in selected:
                selected.add(index)
                changed = True
            for premise in theorem.premises:
                predicate = premise.canonical().predicate
                if predicate not in needed:
                    needed.add(predicate)
                    changed = True
    return tuple(theorems[index] for index in sorted(selected))


def _open_obligations(
    facts: Sequence[Atom],
    goals: Sequence[Atom],
    theorems: Sequence[Theorem],
    *,
    max_results: int,
) -> tuple[tuple[BackwardObligation, ...], tuple[Atom, ...]]:
    obligations: list[BackwardObligation] = []
    for goal in goals:
        obligations.extend(
            synthesize_backward_obligations(
                facts,
                goal,
                theorems,
                max_open_premises=4,
                max_states_per_rule=192,
                max_results=max_results,
            )
        )
    ranked = tuple(obligations[:max_results])
    demands: list[Atom] = []
    seen: set[Atom] = set()
    for obligation in ranked:
        for premise in obligation.open_premises:
            canonical = premise.canonical()
            if canonical not in seen:
                seen.add(canonical)
                demands.append(canonical)
    return ranked, tuple(demands[:max_results])


def _build_agents_and_views(
    theorems: Sequence[Theorem],
    predicates: Sequence[str],
    *,
    certificate_budget: int,
    observed_atoms: Sequence[Atom] = (),
) -> tuple[tuple[RuleClosureAdapter, ...], tuple[MMTTheoryView, ...]]:
    partitions = (
        (
            "newclid_dd",
            "https://newclid.org/theory/dd",
            tuple(item for item in theorems if ":" in item.name),
        ),
        (
            "euclidean_ar",
            "https://mortra.dev/theory/euclidean-ar",
            tuple(item for item in theorems if ":" not in item.name),
        ),
    )
    observed_arities: dict[str, set[int]] = {predicate: set() for predicate in predicates}
    for theorem in theorems:
        for item in (*theorem.premises, theorem.conclusion):
            canonical = item.canonical()
            observed_arities.setdefault(canonical.predicate, set()).add(
                len(canonical.arguments)
            )
    for item in observed_atoms:
        canonical = item.canonical()
        observed_arities.setdefault(canonical.predicate, set()).add(
            len(canonical.arguments)
        )
    assignments = tuple(
        MMTSymbolAssignment(
            predicate,
            _shared_symbol_uri(
                predicate,
                arity=arity if len(observed_arities[predicate]) > 1 else None,
            ),
            argument_sorts=_shared_argument_sorts(predicate, arity),
        )
        for predicate in predicates
        for arity in sorted(observed_arities[predicate])
    )
    agents: list[RuleClosureAdapter] = []
    views: list[MMTTheoryView] = []
    for agent_id, theory_uri, local_theorems in partitions:
        if not local_theorems:
            continue
        exports = {
            item.conclusion.canonical().predicate for item in local_theorems
        }
        agents.append(
            RuleClosureAdapter(
                agent_id,
                local_theorems,
                imports=predicates,
                exports=exports,
                max_certificates_per_round=certificate_budget,
            )
        )
        views.append(
            MMTTheoryView(
                agent_id,
                theory_uri,
                SHARED_THEORY,
                assignments,
            )
        )
    return tuple(agents), tuple(views)


def _goal_connected_fact_slice(
    facts: Sequence[Atom],
    goals: Sequence[Atom],
    *,
    point_radius: int,
    max_facts: int,
) -> tuple[Atom, ...]:
    """Select a deterministic finite incidence neighbourhood of the goals."""

    relevant_points = {
        argument
        for goal in goals
        for argument in goal.canonical().arguments
        if not argument.startswith("?")
    }
    for _ in range(max(0, point_radius)):
        expanded = set(relevant_points)
        for fact in facts:
            arguments = set(fact.canonical().arguments)
            if arguments & relevant_points:
                expanded.update(arguments)
        if expanded == relevant_points:
            break
        relevant_points = expanded
    ordered = sorted(
        facts,
        key=lambda fact: (
            -len(set(fact.canonical().arguments) & relevant_points),
            len(fact.canonical().arguments),
            _render(fact),
        ),
    )
    connected = [
        fact
        for fact in ordered
        if set(fact.canonical().arguments) & relevant_points
    ]
    return tuple(connected[:max_facts])


def _proof_basis_fact_slice(
    facts: Sequence[Atom],
    goals: Sequence[Atom],
    theorems: Sequence[Theorem],
    *,
    point_radius: int,
    max_facts: int,
    max_obligations: int,
) -> tuple[Atom, ...]:
    """Compress a large native closure into a goal-conditioned proof basis.

    The old slice ranked thousands of facts mostly by point overlap and then
    truncated them.  In a dense incidence closure, almost every fact contains
    a goal-connected point, so the finite prefix became effectively lexical.
    Here backward theorem unification identifies premises that already match
    the native proof state.  Those exact matches and facts unifying with open
    typed demands are retained before the ordinary incidence neighbourhood.
    """

    canonical_facts = tuple(sorted({item.canonical() for item in facts}, key=_render))
    facts_by_predicate: dict[str, list[Atom]] = {}
    for fact in canonical_facts:
        facts_by_predicate.setdefault(fact.predicate, []).append(fact)

    # First project the theorem premises through the concrete goal
    # substitution.  This is linear in each matching predicate bucket and
    # avoids joining the entire native closure before we know which typed
    # premises can possibly feed the requested goal.
    projected: set[Atom] = set()
    for goal in goals:
        wanted = goal.canonical()
        for theorem in theorems:
            for initial_items in atom_pattern_unifications(
                theorem.conclusion.canonical(),
                wanted,
            ):
                initial = dict(initial_items)
                for premise in theorem.premises:
                    for fact in facts_by_predicate.get(
                        premise.canonical().predicate,
                        (),
                    ):
                        if atom_pattern_unifications(premise, fact, initial):
                            projected.add(fact)

    neighbourhood = _goal_connected_fact_slice(
        canonical_facts,
        goals,
        point_radius=point_radius,
        max_facts=max(max_facts * 2, 256),
    )
    analysis_facts = tuple(
        dict.fromkeys(
            (
                *sorted(projected, key=_render),
                *neighbourhood,
            )
        )
    )
    obligations, demands = _open_obligations(
        analysis_facts,
        goals,
        theorems,
        max_results=max_obligations,
    )
    exact_matches = {
        premise.canonical()
        for obligation in obligations
        for premise in obligation.matched_premises
    }
    exact_matches.update(
        matched_theorem_support_facts(
            analysis_facts,
            goals,
            theorems,
            max_matches=max(32, max_obligations * 8),
        )
    )
    demand_matches: set[Atom] = set()
    for demand in demands:
        for fact in facts_by_predicate.get(demand.predicate, ()):
            if atom_pattern_unifications(demand, fact):
                demand_matches.add(fact)

    fallback = _goal_connected_fact_slice(
        canonical_facts,
        (*goals, *demands),
        point_radius=point_radius,
        max_facts=max_facts,
    )
    ordered: list[Atom] = []
    seen: set[Atom] = set()
    for group in (
        sorted(exact_matches, key=_render),
        sorted(demand_matches, key=_render),
        fallback,
    ):
        for fact in group:
            canonical = fact.canonical()
            if canonical in seen:
                continue
            seen.add(canonical)
            ordered.append(canonical)
            if len(ordered) >= max_facts:
                return tuple(ordered)
    return tuple(ordered)


def goal_conditioned_proof_basis(
    facts: Sequence[Atom],
    goals: Sequence[Atom],
    theorems: Sequence[Theorem],
    *,
    point_radius: int = 1,
    max_facts: int = 192,
    max_obligations: int = 24,
) -> tuple[Atom, ...]:
    """Public, deterministic projection used before bounded proof-DAG search."""

    return _proof_basis_fact_slice(
        facts,
        goals,
        theorems,
        point_radius=point_radius,
        max_facts=max_facts,
        max_obligations=max_obligations,
    )


def coordinate_hageo_certificates(
    facts: Iterable[Atom],
    goals: Sequence[Atom],
    theorems: Sequence[Theorem],
    *,
    max_rounds: int = 8,
    max_obligations: int = 24,
    point_radius: int = 1,
    max_facts: int = 192,
    certificate_budget: int = 256,
    initial_open_demands: Sequence[Atom] | None = None,
) -> HageoMMTExchange:
    """Exchange exact certificates and expose the resulting search frontier."""

    canonical_facts = tuple(sorted({item.canonical() for item in facts}, key=_render))
    canonical_goals = tuple(item.canonical() for item in goals)
    relevant = _backward_relevant_theorems(canonical_goals, theorems)
    selected_facts = _proof_basis_fact_slice(
        canonical_facts,
        canonical_goals,
        relevant,
        point_radius=point_radius,
        max_facts=max_facts,
        max_obligations=max_obligations,
    )
    if initial_open_demands is None:
        _, initial_demands = _open_obligations(
            selected_facts,
            canonical_goals,
            relevant,
            max_results=max_obligations,
        )
    else:
        initial_demands = tuple(
            dict.fromkeys(item.canonical() for item in initial_open_demands)
        )[:max_obligations]
    predicates = tuple(
        sorted(
            {
                *(item.predicate for item in canonical_facts),
                *(item.predicate for item in canonical_goals),
                *(item.conclusion.canonical().predicate for item in relevant),
                *(
                    premise.canonical().predicate
                    for theorem in relevant
                    for premise in theorem.premises
                ),
            }
        )
    )
    agents, views = _build_agents_and_views(
        relevant,
        predicates,
        certificate_budget=certificate_budget,
        observed_atoms=(*selected_facts, *canonical_goals, *initial_demands),
    )
    accepted = set(selected_facts)
    goal_results: list[MMTGoalExchange] = []
    certificate_material: list[str] = []
    certificate_count = 0

    if agents:
        coordinator = MMTExactCoordinator(agents, views)
        anchor = views[0]
        for goal in canonical_goals:
            shared_goal = anchor.push(goal)
            if shared_goal is None:
                continue
            shared_facts = tuple(
                pushed
                for fact in sorted(accepted, key=_render)
                if (pushed := anchor.push(fact)) is not None
            )
            result = coordinator.solve(shared_facts, shared_goal, max_rounds=max_rounds)
            for shared_fact in result.accepted_facts:
                for view in views:
                    native = view.pull(shared_fact)
                    if native is not None:
                        accepted.add(native.canonical())
                        break
            for envelope in result.certificates:
                certificate_material.append(
                    "|".join(
                        (
                            envelope.source_agent_id,
                            envelope.native_certificate.rule_name,
                            envelope.conclusion.symbol_uri,
                            *envelope.conclusion.arguments,
                            *(
                                f"{premise.symbol_uri}({','.join(premise.arguments)})"
                                for premise in envelope.premises
                            ),
                        )
                    )
                )
            certificate_count += len(result.certificates)
            goal_results.append(
                MMTGoalExchange(
                    goal=goal,
                    solved=result.solved,
                    replayed=result.replayed,
                    rounds=len(result.rounds),
                    proposed=sum(item.proposed for item in result.rounds),
                    accepted=sum(item.accepted for item in result.rounds),
                    rejected=sum(item.rejected for item in result.rounds),
                )
            )
    else:
        goal_results.extend(
            MMTGoalExchange(
                goal=goal,
                solved=goal in accepted,
                replayed=goal in accepted,
                rounds=0,
                proposed=0,
                accepted=0,
                rejected=0,
            )
            for goal in canonical_goals
        )

    accepted_facts = tuple(sorted(accepted, key=_render))
    proof_state_facts = tuple(
        sorted({*canonical_facts, *accepted_facts}, key=_render)
    )
    obligations, demands = _open_obligations(
        proof_state_facts,
        canonical_goals,
        relevant,
        max_results=max_obligations,
    )
    if initial_open_demands is not None:
        proved = {item.canonical() for item in proof_state_facts}
        demands = tuple(
            item for item in initial_demands if item.canonical() not in proved
        )
    material = "\n".join(certificate_material).encode("utf-8")
    return HageoMMTExchange(
        input_fact_count=len(canonical_facts),
        selected_fact_count=len(selected_facts),
        accepted_facts=accepted_facts,
        derived_facts=tuple(
            item for item in accepted_facts if item not in canonical_facts
        ),
        certificates=certificate_count,
        certificate_sha256=hashlib.sha256(material).hexdigest(),
        goals=tuple(goal_results),
        obligations=obligations,
        initial_open_demands=initial_demands,
        open_demands=demands,
        proof_state_facts=proof_state_facts,
    )
