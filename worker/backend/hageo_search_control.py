"""Pure control-plane helpers for typed HAGeo construction search."""

from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Any, Sequence, TypeVar

from worker.backend.geometry_proof_hypergraph import Atom, atom_pattern_unifications


T = TypeVar("T")


@dataclass(frozen=True)
class CandidatePolicySpec:
    """Control-plane properties for one auxiliary-construction policy."""

    structured: bool
    alignment_mode: str
    hard_incidence_gate: bool
    preserve_family_frontier: bool
    residual_feedback: bool = False
    terminal_credit: bool = False
    terminal_credit_mix: int = 0
    obligation_conditioned_credit: bool = False
    typed_contract_synthesis: bool = False
    ground_residual_synthesis: bool = False


_CANDIDATE_POLICY_SPECS = {
    "random": CandidatePolicySpec(False, "off", True, False),
    "typed-sheaf": CandidatePolicySpec(
        True, "native-formal-sheaf", False, True
    ),
    "mmt-sheaf": CandidatePolicySpec(True, "mmt-theory-view", False, True),
    "mmt-hageo": CandidatePolicySpec(True, "mmt-theory-view", True, True),
    "mmt-hageo-lite": CandidatePolicySpec(
        True, "mmt-theory-view", True, True
    ),
    # These two policies form a controlled ablation.  Both use the same
    # typed-atom ranking, numerical incidence gate, and native verifier
    # feedback.  Only residual-feedback replaces the next round's open goals
    # with the verifier's newly observed proof residual.
    "residual-static": CandidatePolicySpec(True, "typed-atom", True, True),
    "residual-feedback": CandidatePolicySpec(
        True, "typed-atom", True, True, residual_feedback=True
    ),
    "residual-portfolio": CandidatePolicySpec(
        True, "typed-atom", False, True, residual_feedback=True
    ),
    "terminal-credit": CandidatePolicySpec(
        True,
        "typed-atom",
        True,
        True,
        residual_feedback=True,
        terminal_credit=True,
    ),
    "terminal-credit-mixed": CandidatePolicySpec(
        True,
        "typed-atom",
        False,
        True,
        residual_feedback=True,
        terminal_credit=True,
        terminal_credit_mix=1,
    ),
    "obligation-credit-mixed": CandidatePolicySpec(
        True,
        "typed-atom",
        False,
        True,
        residual_feedback=True,
        terminal_credit=True,
        terminal_credit_mix=1,
        obligation_conditioned_credit=True,
    ),
    "contract-portfolio": CandidatePolicySpec(
        True,
        "typed-atom",
        False,
        True,
        residual_feedback=True,
        typed_contract_synthesis=True,
    ),
    "residual-construction": CandidatePolicySpec(
        True,
        "proof-dag-priority",
        False,
        True,
        residual_feedback=True,
        typed_contract_synthesis=True,
        ground_residual_synthesis=True,
    ),
}


def candidate_policy_spec(name: str) -> CandidatePolicySpec:
    try:
        return _CANDIDATE_POLICY_SPECS[name]
    except KeyError as exc:
        raise ValueError(f"unknown candidate policy: {name}") from exc


def proof_dag_search_roots(
    final_goals: Sequence[T],
    residual_demands: Sequence[T],
    *,
    ground_residual_synthesis: bool,
) -> tuple[T, ...]:
    """Keep alternative residual branches inside one backward proof DAG."""

    if ground_residual_synthesis:
        return tuple(final_goals)
    return tuple(residual_demands or final_goals)


def candidate_made_causal_progress(
    *,
    solved: bool,
    ground_residual_synthesis: bool,
    matched_obligation_atoms: int,
    closed_parent_demands: int,
    circular_goal_transport: bool,
    typed_plan_supported: bool = False,
) -> bool:
    """Accept verified progress or a typed plan that still requires replay."""

    if solved:
        return True
    if circular_goal_transport:
        return False
    if ground_residual_synthesis:
        return closed_parent_demands > 0 or typed_plan_supported
    return matched_obligation_atoms > 0


def next_relation_demands(
    current: Sequence[T],
    observed: Sequence[T],
    *,
    feedback_enabled: bool,
) -> tuple[T, ...]:
    """Advance the proof frontier only for the closed-loop ablation."""

    return tuple(observed if feedback_enabled else current)


def candidate_pool(
    extensions: Sequence[T],
    audit: dict[str, Any],
    *,
    hard_incidence_gate: bool,
    preserve_family_frontier: bool = False,
    family_order: Sequence[str] = (),
) -> list[T]:
    """Keep numerical incidence advisory unless a control ablation requests a gate."""

    profiles = {
        item["step_key"]: item
        for item in audit["numerical_incidence"].get("selected_candidates", [])
    }
    executable = [step for step in extensions if getattr(step, "key") in profiles]
    heuristic = [
        step
        for step in executable
        if profiles[getattr(step, "key")].get("is_heuristic_candidate")
    ]
    if hard_incidence_gate:
        return heuristic or executable
    if not preserve_family_frontier:
        return executable

    representative_by_family: dict[str, T] = {}
    for step in executable:
        family = str(getattr(step, "family"))
        if family not in representative_by_family:
            representative_by_family[family] = step
    ordered_families = list(dict.fromkeys(family_order))
    ordered_families.extend(
        family for family in representative_by_family if family not in ordered_families
    )
    representatives = [
        representative_by_family[family]
        for family in ordered_families
        if family in representative_by_family
    ]
    ordered: list[T] = []
    seen: set[str] = set()
    width = max(len(executable), len(representatives))
    for index in range(width):
        for values in (executable, representatives):
            if index >= len(values):
                continue
            step = values[index]
            key = str(getattr(step, "key"))
            if key in seen:
                continue
            seen.add(key)
            ordered.append(step)
    return ordered


def proof_residual_order_key(value: dict[str, Any]) -> tuple[float, ...]:
    """Order proof states without consulting an answer or problem identifier."""

    return (
        float(-value["ar_closed_goals"]),
        float(-value.get("closed_parent_demands", 0)),
        float(value.get("introduced_relation_demands", 0)),
        float(value["ar_residual_support"]),
        float(value["ar_residual_l1"]),
        float(-value["ar_known_rank"]),
        float(value["backward_obligations"]),
        float(value["open_relation_demands"]),
    )


def relation_demand_transition(
    parent: Sequence[Any],
    child: Sequence[Any],
    *,
    proved: Sequence[Any],
    parent_proved: Sequence[Any] = (),
) -> dict[str, int | list[str]]:
    """Measure progress only from facts newly proved after the intervention."""

    def identity(value: Any) -> str:
        if isinstance(value, Atom):
            canonical = value.canonical()
            return f"{canonical.predicate}({','.join(canonical.arguments)})"
        canonical = getattr(value, "canonical", None)
        if callable(canonical):
            return str(canonical())
        return str(value)

    parent_items = tuple(dict.fromkeys(parent))
    child_items = tuple(dict.fromkeys(child))
    proved_items = tuple(dict.fromkeys(proved))
    parent_proved_identities = {identity(item) for item in parent_proved}
    new_proved_items = tuple(
        item for item in proved_items if identity(item) not in parent_proved_identities
    )

    def matches(pattern: Any, value: Any) -> bool:
        if isinstance(pattern, Atom) and isinstance(value, Atom):
            return bool(atom_pattern_unifications(pattern, value))
        return identity(pattern) == identity(value)

    closed_items = tuple(
        item
        for item in parent_items
        if any(matches(item, proved_item) for proved_item in new_proved_items)
    )
    retained_items = tuple(
        item
        for item in parent_items
        if item not in closed_items
        and any(matches(item, child_item) for child_item in child_items)
    )
    introduced_items = tuple(
        item
        for item in child_items
        if not any(matches(parent_item, item) for parent_item in parent_items)
    )
    return {
        "parent_relation_demands": len(parent_items),
        "retained_parent_demands": len(retained_items),
        "closed_parent_demands": len(closed_items),
        "closed_parent_obligations": [identity(item) for item in closed_items],
        "new_native_facts": len(new_proved_items),
        "introduced_relation_demands": len(introduced_items),
    }


def obligation_conditioned_credit_ranking(
    credit_ranking: Sequence[dict[str, Any]],
    direct_matches: dict[str, Sequence[str]],
) -> list[dict[str, Any]]:
    """Retain positive credit only when a candidate can fill an open typed goal."""

    conditioned: list[dict[str, Any]] = []
    for item in credit_ranking:
        key = str(item["candidate"])
        matched = tuple(direct_matches.get(key, ()))
        if float(item.get("credit_score", 0.0)) <= 0.0 or not matched:
            continue
        conditioned.append(
            {
                **item,
                "matched_obligations": list(matched),
                "direct_match_count": len(matched),
            }
        )
    return conditioned


def obligation_conditioned_selection_key(
    *,
    solved: bool,
    residual: dict[str, Any],
    verified_credit: bool,
    static_rank: int,
) -> tuple[float | int | bool, ...]:
    """Use credit only after native replay closes a directly matched obligation."""

    residual_key = proof_residual_order_key(residual)
    return (
        not solved,
        residual_key[0],
        residual_key[1],
        not verified_credit,
        *residual_key[2:],
        static_rank,
    )


def verified_obligation_credit(
    *,
    selection_channel: str,
    matched_obligations: Sequence[str],
    residual: dict[str, Any],
) -> bool:
    """Require native closure of the same obligation matched by the candidate."""

    if selection_channel != "obligation_credit_probe":
        return False
    closed = {
        str(value) for value in residual.get("closed_parent_obligations", ())
    }
    return bool(closed.intersection(map(str, matched_obligations)))


def rank_biased_shortlist(
    pool: Sequence[T],
    *,
    count: int,
    rng: random.Random,
    temperature: float,
    trajectory_index: int = 0,
    protected_prefix: int = 0,
) -> list[tuple[int, T]]:
    """Draw a ranked subset while retaining certificate-backed candidates."""

    if count <= 0:
        return []
    if protected_prefix < 0:
        raise ValueError("protected_prefix must be nonnegative")
    available = list(enumerate(pool))
    protected = available[: min(protected_prefix, count)]
    tail = available[len(protected) :]
    if trajectory_index > 0 and protected_prefix == 0 and len(tail) > 1:
        # Preserve the original independent-trajectory ablation: uncredited
        # trajectories skip the greedy head and visit disjoint rank strata.
        tail = tail[1:]
    if trajectory_index > 0 and len(tail) > 1:
        start = ((trajectory_index - 1) * count) % len(tail)
        tail = tail[start:] + tail[:start]
    available = tail
    if temperature <= 0 or trajectory_index > 0:
        return [*protected, *available[: max(0, count - len(protected))]]
    selected: list[tuple[int, T]] = list(protected)
    continuation = math.exp(-1.0 / temperature)
    while available and len(selected) < count:
        weights = [continuation**rank for rank, _ in available]
        position = rng.choices(range(len(available)), weights=weights, k=1)[0]
        selected.append(available.pop(position))
    return selected


def mixed_credit_residual_shortlist(
    base_pool: Sequence[T],
    credit_ranking: Sequence[dict[str, Any]],
    *,
    count: int,
    rng: random.Random,
    temperature: float,
    trajectory_index: int = 0,
    credit_slots: int = 1,
) -> tuple[list[tuple[int, T]], list[dict[str, str]]]:
    """Reserve bounded credit slots and keep the rest on the base frontier."""

    if count <= 0:
        return [], []
    if credit_slots < 0:
        raise ValueError("credit_slots must be nonnegative")
    by_key = {
        str(getattr(candidate, "key")): (index, candidate)
        for index, candidate in enumerate(base_pool)
    }
    selected: list[tuple[int, T]] = []
    channels: list[dict[str, str]] = []
    selected_keys: set[str] = set()
    for item in credit_ranking:
        if len(selected) >= min(credit_slots, count):
            break
        if float(item.get("credit_score", 0.0)) <= 0.0:
            continue
        key = str(item["candidate"])
        pair = by_key.get(key)
        if pair is None or key in selected_keys:
            continue
        selected.append(pair)
        selected_keys.add(key)
        channels.append({"candidate": key, "channel": "terminal_credit"})

    residual_pool = [
        candidate
        for candidate in base_pool
        if str(getattr(candidate, "key")) not in selected_keys
    ]
    residual_indices = {
        str(getattr(candidate, "key")): index
        for index, candidate in enumerate(base_pool)
    }
    residual = rank_biased_shortlist(
        residual_pool,
        count=max(0, count - len(selected)),
        rng=rng,
        temperature=temperature,
        trajectory_index=trajectory_index,
    )
    for _, candidate in residual:
        key = str(getattr(candidate, "key"))
        selected.append((residual_indices[key], candidate))
        channels.append({"candidate": key, "channel": "residual_frontier"})
    return selected, channels
