"""Replayable symbolic normal forms for typed geometry construction paths.

The quotient implemented here is deliberately narrower than geometric
equivalence.  It identifies only alpha-renaming of generated points,
family-declared input symmetries, and permutations of independent actions in
the same dependency DAG.  Numeric branch choices, search completeness, and
native proof outcomes are not equated by this certificate.  A scheduler may
use the symbolic key as an experimental quotient, but every accepted result
still requires native proof replay.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any, Mapping, Sequence

from worker.backend.typed_geometry_stalk import (
    EXTENDED_POINT_FAMILIES,
    ConstructionFamily,
)


@dataclass(frozen=True)
class ConstructionAction:
    family: str
    output: str
    inputs: tuple[str, ...]


@dataclass(frozen=True)
class CanonicalConstructionAction:
    family: str
    output: str
    inputs: tuple[str, ...]
    semantic_term: str
    source_index: int
    dependency_indices: tuple[int, ...]


@dataclass(frozen=True)
class ConstructionActionCertificate:
    quotient: str
    original_actions: tuple[ConstructionAction, ...]
    canonical_actions: tuple[CanonicalConstructionAction, ...]
    base_symbols: tuple[str, ...]
    semantic_state: tuple[str, ...]
    semantic_state_key: str
    dependency_edges: tuple[tuple[int, int], ...]
    preserved: tuple[str, ...]
    not_claimed: tuple[str, ...]
    certificate_sha256: str


@dataclass(frozen=True)
class ConstructionNormalizationResult:
    certificate: ConstructionActionCertificate | None
    errors: tuple[str, ...]


FAMILY_BY_NAME = {family.name: family for family in EXTENDED_POINT_FAMILIES}


def _action(value: ConstructionAction | Mapping[str, Any] | Any) -> ConstructionAction:
    if isinstance(value, ConstructionAction):
        return value
    if isinstance(value, Mapping):
        return ConstructionAction(
            family=str(value["family"]),
            output=str(value["output"]),
            inputs=tuple(str(item) for item in value.get("inputs", ())),
        )
    return ConstructionAction(
        family=str(value.family),
        output=str(value.output),
        inputs=tuple(str(item) for item in value.inputs),
    )


def _canonical_inputs(family: ConstructionFamily, inputs: Sequence[str]) -> tuple[str, ...]:
    values = tuple(inputs)
    if family.symmetry == "ordered":
        return values
    if family.symmetry == "all":
        return tuple(sorted(values))
    if family.symmetry == "head_pair":
        return (values[0], *sorted(values[1:]))
    if family.symmetry == "line_pair":
        lines = sorted((tuple(sorted(values[:2])), tuple(sorted(values[2:]))))
        return (*lines[0], *lines[1])
    if family.symmetry == "line_relation":
        return (*sorted(values[:2]), values[2], *sorted(values[3:]))
    if family.symmetry == "relation_pair":
        relations = sorted(
            (
                (values[0], *sorted(values[1:3])),
                (values[3], *sorted(values[4:6])),
            )
        )
        return (*relations[0], *relations[1])
    raise ValueError(f"unknown construction symmetry: {family.symmetry}")


def _digest_payload(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def normalize_construction_actions(
    values: Sequence[ConstructionAction | Mapping[str, Any] | Any],
) -> ConstructionNormalizationResult:
    actions = tuple(_action(value) for value in values)
    errors: list[str] = []
    output_to_index: dict[str, int] = {}
    for index, action in enumerate(actions):
        if action.output in output_to_index:
            errors.append(f"duplicate generated output: {action.output}")
        else:
            output_to_index[action.output] = index

    semantic_terms: list[str] = []
    dependencies: list[tuple[int, ...]] = []
    base_symbols: set[str] = set()
    seen_semantic_terms: set[str] = set()
    for index, action in enumerate(actions):
        family = FAMILY_BY_NAME.get(action.family)
        if family is None:
            errors.append(f"unknown construction family: {action.family}")
            semantic_terms.append(f"invalid:{index}")
            dependencies.append(())
            continue
        if len(action.inputs) != family.input_arity:
            errors.append(
                f"{action.family} expects {family.input_arity} inputs, got {len(action.inputs)}"
            )
            semantic_terms.append(f"invalid:{index}")
            dependencies.append(())
            continue
        input_terms: list[str] = []
        input_dependencies: list[int] = []
        for item in action.inputs:
            producer = output_to_index.get(item)
            if producer is None:
                base_symbols.add(item)
                input_terms.append(f"point({item})")
            elif producer >= index:
                errors.append(f"forward reference {item} at action {index}")
                input_terms.append(f"forward({item})")
            else:
                input_dependencies.append(producer)
                input_terms.append(semantic_terms[producer])
        canonical_terms = _canonical_inputs(family, input_terms)
        semantic_term = f"{action.family}({','.join(canonical_terms)})"
        if semantic_term in seen_semantic_terms:
            errors.append(
                "duplicate semantic construction is branch-ambiguous: " + semantic_term
            )
        seen_semantic_terms.add(semantic_term)
        semantic_terms.append(semantic_term)
        dependencies.append(tuple(sorted(set(input_dependencies))))

    if errors:
        return ConstructionNormalizationResult(None, tuple(errors))

    children: dict[int, list[int]] = {index: [] for index in range(len(actions))}
    indegree = [0] * len(actions)
    for child, parents in enumerate(dependencies):
        indegree[child] = len(parents)
        for parent in parents:
            children[parent].append(child)
    ready = sorted(
        (index for index, degree in enumerate(indegree) if degree == 0),
        key=lambda index: (semantic_terms[index], index),
    )
    canonical_order: list[int] = []
    while ready:
        current = ready.pop(0)
        canonical_order.append(current)
        for child in children[current]:
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
        ready.sort(key=lambda index: (semantic_terms[index], index))
    if len(canonical_order) != len(actions):
        return ConstructionNormalizationResult(None, ("construction dependency cycle",))

    canonical_name = {
        original_index: f"g{canonical_index}"
        for canonical_index, original_index in enumerate(canonical_order)
    }
    canonical_actions: list[CanonicalConstructionAction] = []
    for original_index in canonical_order:
        action = actions[original_index]
        family = FAMILY_BY_NAME[action.family]
        rewritten_inputs = tuple(
            canonical_name[output_to_index[item]] if item in output_to_index else item
            for item in action.inputs
        )
        canonical_actions.append(
            CanonicalConstructionAction(
                family=action.family,
                output=canonical_name[original_index],
                inputs=_canonical_inputs(family, rewritten_inputs),
                semantic_term=semantic_terms[original_index],
                source_index=original_index,
                dependency_indices=tuple(
                    canonical_order.index(parent) for parent in dependencies[original_index]
                ),
            )
        )

    semantic_state = tuple(sorted(semantic_terms))
    semantic_state_key = "|".join(semantic_state)
    dependency_edges = tuple(
        sorted((parent, child) for child, parents in enumerate(dependencies) for parent in parents)
    )
    quotient = "alpha-renaming+declared-input-symmetry+independent-action-order"
    preserved = (
        "construction-family",
        "typed-input-dependency-DAG",
        "family-declared-input-symmetry",
        "multiset-of-semantic-construction-terms",
    )
    not_claimed = (
        "numeric-branch-equivalence",
        "generated-point-coordinate-equality",
        "numeric-branch-search-completeness",
        "native-proof-outcome-equivalence",
    )
    unsigned = {
        "quotient": quotient,
        "original_actions": [asdict(action) for action in actions],
        "canonical_actions": [asdict(action) for action in canonical_actions],
        "base_symbols": sorted(base_symbols),
        "semantic_state": semantic_state,
        "semantic_state_key": semantic_state_key,
        "dependency_edges": dependency_edges,
        "preserved": preserved,
        "not_claimed": not_claimed,
    }
    certificate = ConstructionActionCertificate(
        quotient=quotient,
        original_actions=actions,
        canonical_actions=tuple(canonical_actions),
        base_symbols=tuple(sorted(base_symbols)),
        semantic_state=semantic_state,
        semantic_state_key=semantic_state_key,
        dependency_edges=dependency_edges,
        preserved=preserved,
        not_claimed=not_claimed,
        certificate_sha256=_digest_payload(unsigned),
    )
    return ConstructionNormalizationResult(certificate, ())


def verify_construction_action_certificate(
    certificate: ConstructionActionCertificate,
) -> tuple[str, ...]:
    replayed = normalize_construction_actions(certificate.original_actions)
    if replayed.certificate is None:
        return replayed.errors
    errors: list[str] = []
    if replayed.certificate != certificate:
        errors.append("construction-action certificate replay mismatch")
    canonical_replay = normalize_construction_actions(certificate.canonical_actions)
    if canonical_replay.certificate is None:
        errors.extend(canonical_replay.errors)
    elif canonical_replay.certificate.semantic_state != certificate.semantic_state:
        errors.append("canonical path changed the semantic construction state")
    return tuple(dict.fromkeys(errors))


def certificate_to_dict(certificate: ConstructionActionCertificate) -> dict[str, Any]:
    return asdict(certificate)
