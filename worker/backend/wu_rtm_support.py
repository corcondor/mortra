"""Wu RTMの支持集合射影を証明トレースから構成する。

完全なRTMは多項式係数ベクトルを保持する。本モジュールはその非零支持の
上界だけをBoolean集合として伝播し、局所証明義務へ分割可能かを監査する。
支持は過大近似なので、疎性を偽って報告しない。
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class WuRTMSupportRow:
    polynomial_sha256: str
    origin: str
    hypothesis_indices: tuple[int, ...]
    support_width: int


@dataclass(frozen=True)
class WuRTMLocalObligation:
    obligation_id: str
    phase: str
    direct_hypothesis_indices: tuple[int, ...]
    direct_support_width: int
    hypothesis_indices: tuple[int, ...]
    support_width: int
    certificate_count: int
    replayed: bool


@dataclass(frozen=True)
class CertifiedWuRTMSupportAudit:
    theorem: str
    hypothesis_count: int
    derived_polynomial_count: int
    support_rows: tuple[WuRTMSupportRow, ...]
    local_obligations: tuple[WuRTMLocalObligation, ...]
    hypothesis_components: tuple[tuple[int, ...], ...]
    goal_support_indices: tuple[int, ...]
    goal_support_width: int
    goal_support_fraction: float
    strict_local_obligation_count: int
    maximum_support_width: int
    mean_support_width: float
    support_matrix_density: float
    all_references_resolved: bool
    unresolved_reference_hashes: tuple[str, ...]
    all_certificates_replayed: bool


def _mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"expected mapping or dataclass, got {type(value).__name__}")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _components(count: int, supports: list[frozenset[int]]) -> tuple[tuple[int, ...], ...]:
    parent = list(range(count))

    def find(item: int) -> int:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for support in supports:
        ordered = sorted(support)
        for item in ordered[1:]:
            union(ordered[0], item)
    groups: dict[int, list[int]] = {}
    for item in range(count):
        groups.setdefault(find(item), []).append(item)
    return tuple(tuple(group) for group in sorted(groups.values(), key=lambda x: x[0]))


def audit_wu_rtm_support(proof: Any) -> CertifiedWuRTMSupportAudit:
    """厳密擬除算証明をBoolean RTMへ射影し、依存幅を測る。"""

    payload = _mapping(proof)
    characteristic = _mapping(payload["characteristic"])
    initial_polynomials = tuple(characteristic["initial_polynomials"])
    hypothesis_count = len(initial_polynomials)
    support_by_polynomial: dict[str, frozenset[int]] = {}
    origin_by_polynomial: dict[str, str] = {}
    unresolved: set[str] = set()
    obligations: list[WuRTMLocalObligation] = []
    all_replayed = True

    for index, polynomial in enumerate(initial_polynomials):
        support_by_polynomial[polynomial] = (
            support_by_polynomial.get(polynomial, frozenset()) | {index}
        )
        origin_by_polynomial.setdefault(polynomial, f"hypothesis:{index}")

    def resolve(polynomial: str) -> frozenset[int]:
        if polynomial in {"", "0"}:
            return frozenset()
        support = support_by_polynomial.get(polynomial)
        if support is None:
            unresolved.add(_sha256(polynomial))
            return frozenset()
        return support

    def record_reduction(reduction_value: Any, phase: str, ordinal: int) -> frozenset[int]:
        nonlocal all_replayed
        reduction = _mapping(reduction_value)
        support = resolve(str(reduction["dividend"]))
        direct_support: frozenset[int] = frozenset()
        steps = tuple(reduction.get("steps", ()))
        for step_value in steps:
            step = _mapping(step_value)
            divisor_support = resolve(str(step["divisor"]))
            direct_support = direct_support | divisor_support
            support = support | divisor_support
            remainder = str(step["remainder"])
            if remainder not in {"", "0"}:
                support_by_polynomial.setdefault(remainder, support)
                origin_by_polynomial.setdefault(remainder, phase)
            all_replayed = all_replayed and bool(step.get("replayed", False))
        remainder = str(reduction["remainder"])
        if remainder not in {"", "0"}:
            support_by_polynomial.setdefault(remainder, support)
            origin_by_polynomial.setdefault(remainder, phase)
        obligations.append(
            WuRTMLocalObligation(
                obligation_id=f"{phase}:{ordinal}:{_sha256(str(reduction['dividend']))[:12]}",
                phase=phase,
                direct_hypothesis_indices=tuple(sorted(direct_support)),
                direct_support_width=len(direct_support),
                hypothesis_indices=tuple(sorted(support)),
                support_width=len(support),
                certificate_count=len(steps),
                replayed=bool(reduction.get("all_identities_replayed", False)),
            )
        )
        all_replayed = all_replayed and bool(
            reduction.get("all_identities_replayed", False)
        )
        return support

    for round_value in characteristic.get("rounds", ()):
        round_payload = _mapping(round_value)
        round_index = int(round_payload["round_index"])
        for ordinal, reduction in enumerate(round_payload.get("reductions", ())):
            record_reduction(reduction, f"characteristic:{round_index}", ordinal)

    for ordinal, reduction in enumerate(characteristic.get("input_reductions", ())):
        record_reduction(reduction, "input_replay", ordinal)

    goal_support: frozenset[int] = frozenset()
    goal_reduction = payload.get("goal_reduction")
    if goal_reduction is not None:
        goal_payload = _mapping(goal_reduction)
        steps = tuple(goal_payload.get("steps", ()))
        for ordinal, step_value in enumerate(steps):
            step = _mapping(step_value)
            direct_support = resolve(str(step["divisor"]))
            goal_support = goal_support | direct_support
            all_replayed = all_replayed and bool(step.get("replayed", False))
            obligations.append(
                WuRTMLocalObligation(
                    obligation_id=f"goal:{ordinal}:{_sha256(str(step['divisor']))[:12]}",
                    phase="goal",
                    direct_hypothesis_indices=tuple(sorted(direct_support)),
                    direct_support_width=len(direct_support),
                    hypothesis_indices=tuple(sorted(goal_support)),
                    support_width=len(goal_support),
                    certificate_count=1,
                    replayed=bool(step.get("replayed", False)),
                )
            )

    rows = tuple(
        WuRTMSupportRow(
            polynomial_sha256=_sha256(polynomial),
            origin=origin_by_polynomial[polynomial],
            hypothesis_indices=tuple(sorted(support)),
            support_width=len(support),
        )
        for polynomial, support in support_by_polynomial.items()
    )
    derived_rows = tuple(row for row in rows if not row.origin.startswith("hypothesis:"))
    widths = [row.support_width for row in derived_rows]
    nonzero_entries = sum(widths)
    matrix_size = len(derived_rows) * hypothesis_count
    all_supports = [frozenset(item.hypothesis_indices) for item in obligations]
    return CertifiedWuRTMSupportAudit(
        theorem=(
            "If P and B belong to ideals generated by support sets S_P and S_B, "
            "then every exact pseudo-remainder in I(B)^k P = Q B + R belongs "
            "to the ideal generated by S_P union S_B."
        ),
        hypothesis_count=hypothesis_count,
        derived_polynomial_count=len(derived_rows),
        support_rows=rows,
        local_obligations=tuple(obligations),
        hypothesis_components=_components(hypothesis_count, all_supports),
        goal_support_indices=tuple(sorted(goal_support)),
        goal_support_width=len(goal_support),
        goal_support_fraction=(len(goal_support) / hypothesis_count if hypothesis_count else 0.0),
        strict_local_obligation_count=sum(
            item.support_width < hypothesis_count for item in obligations
        ),
        maximum_support_width=max(widths, default=0),
        mean_support_width=(sum(widths) / len(widths) if widths else 0.0),
        support_matrix_density=(nonzero_entries / matrix_size if matrix_size else 0.0),
        all_references_resolved=not unresolved,
        unresolved_reference_hashes=tuple(sorted(unresolved)),
        all_certificates_replayed=all_replayed,
    )
