"""Read Yuclid proof certificates without collapsing their mathematical terms.

The JSON proof is already a topologically ordered list of deductions.  This
module preserves every deduction, links assumptions to their producing
deductions, and distinguishes the two kinds of terms stored in Yuclid's
``SinOrDist`` system: sine-squared angle terms and squared-distance terms.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def statement_key(statement: Mapping[str, Any]) -> str:
    """Return the exact serialized identity used to connect proof nodes."""

    name = str(statement.get("name", ""))
    # Yuclid decorates an ordinary relation with lhs_terms when that relation
    # is consumed by AR.  The producing DD node contains only name/points, so
    # those display terms are not part of the relation's identity.  Explicit
    # equation_class statements are different: their terms are the statement.
    lhs_terms = (
        {
            str(key): str(value)
            for key, value in sorted(
                _mapping(statement.get("lhs_terms")).items(),
                key=lambda item: str(item[0]),
            )
        }
        if name.startswith("equation_class")
        else {}
    )
    payload = {
        "name": name,
        "points": [str(point) for point in statement.get("points", ()) or ()],
        "lhs_terms": lhs_terms,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def statement_weak_key(statement: Mapping[str, Any]) -> str:
    """Identity available in Yuclid rule nodes for type-erased equations.

    A rule-produced ``equation_class`` assertion currently omits lhs_terms,
    while the same statement used by an AR node includes them.  The ordered
    point list is the strongest common representation present in both JSON
    records.  It is used only as a fallback and is reported as such.
    """

    return json.dumps(
        {
            "name": str(statement.get("name", "")),
            "points": [str(point) for point in statement.get("points", ()) or ()],
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def render_statement(statement: Mapping[str, Any]) -> str:
    name = str(statement.get("name", "?"))
    points = ",".join(str(point) for point in statement.get("points", ()) or ())
    base = f"{name}({points})" if points else name
    lhs_terms = _mapping(statement.get("lhs_terms"))
    if not lhs_terms:
        return base
    terms = " + ".join(f"({coefficient})*{term}" for term, coefficient in lhs_terms.items())
    return f"{base}: {terms} = 0"


def classify_term(term: str) -> str:
    normalized = str(term).strip()
    if "\\sin" in normalized or "sin" in normalized.lower():
        return "sine_squared"
    if normalized.startswith("|") and "|^2" in normalized:
        return "squared_distance"
    if normalized.startswith("∠") or normalized.lower().startswith("angle"):
        return "directed_angle"
    return "other"


def equation_term_kinds(statements: Iterable[Mapping[str, Any]]) -> tuple[str, ...]:
    kinds = {
        classify_term(str(term))
        for statement in statements
        for term in _mapping(statement.get("lhs_terms"))
    }
    return tuple(sorted(kinds))


def producer_channel(deduction: Mapping[str, Any]) -> str:
    deduction_type = str(deduction.get("deduction_type", "unknown"))
    if deduction_type == "ar":
        kinds = equation_term_kinds(
            [
                *[item for item in deduction.get("assumptions", ()) or () if isinstance(item, Mapping)],
                *[item for item in deduction.get("assertions", ()) or () if isinstance(item, Mapping)],
            ]
        )
        reason = str(deduction.get("ar_reason", "unknown"))
        return f"ar:{reason}:{'+'.join(kinds) if kinds else 'relation'}"
    rule = str(deduction.get("newclid_rule", "unknown"))
    if rule == "By construction":
        return "construction"
    if rule == "Numerical check" or deduction_type == "num":
        return "numerical_guard"
    if rule == "ignore":
        return "internal_theorem"
    return f"dd:{rule}"


@dataclass(frozen=True)
class ProofNode:
    index: int
    channel: str
    assumption_producers: tuple[int | None, ...]
    assumption_link_modes: tuple[str, ...]
    assumptions: tuple[Mapping[str, Any], ...]
    assertions: tuple[Mapping[str, Any], ...]

    @property
    def is_cross_chart_bridge(self) -> bool:
        if not self.channel.startswith("ar:"):
            return False
        kinds = set(equation_term_kinds((*self.assumptions, *self.assertions)))
        return "sine_squared" in kinds and "squared_distance" in kinds

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "channel": self.channel,
            "assumption_producers": list(self.assumption_producers),
            "assumption_link_modes": list(self.assumption_link_modes),
            "assumptions": list(self.assumptions),
            "assertions": list(self.assertions),
            "term_kinds": list(equation_term_kinds((*self.assumptions, *self.assertions))),
            "cross_chart_bridge": self.is_cross_chart_bridge,
        }


def build_proof_trace(payload: Mapping[str, Any]) -> tuple[ProofNode, ...]:
    deductions = payload.get("deductions_for_goal", ()) or ()
    if not isinstance(deductions, list):
        raise TypeError("deductions_for_goal must be a list")

    latest_producer: dict[str, int] = {}
    weak_producers: dict[str, list[int]] = {}
    nodes: list[ProofNode] = []
    for index, raw in enumerate(deductions):
        if not isinstance(raw, Mapping):
            raise TypeError(f"deduction {index} must be an object")
        assumptions = tuple(
            item for item in raw.get("assumptions", ()) or () if isinstance(item, Mapping)
        )
        assertions = tuple(
            item for item in raw.get("assertions", ()) or () if isinstance(item, Mapping)
        )
        producers_list: list[int | None] = []
        link_modes: list[str] = []
        for item in assumptions:
            producer = latest_producer.get(statement_key(item))
            mode = "exact"
            if producer is None and str(item.get("name", "")).startswith("equation_class"):
                candidates = weak_producers.get(statement_weak_key(item), [])
                producer = candidates[-1] if candidates else None
                if len(candidates) == 1:
                    mode = "equation_points_fallback"
                elif len(candidates) > 1:
                    mode = "equation_points_fallback_ambiguous"
                else:
                    mode = "unlinked"
            elif producer is None:
                mode = "unlinked"
            producers_list.append(producer)
            link_modes.append(mode)
        node = ProofNode(
            index=index,
            channel=producer_channel(raw),
            assumption_producers=tuple(producers_list),
            assumption_link_modes=tuple(link_modes),
            assumptions=assumptions,
            assertions=assertions,
        )
        nodes.append(node)
        for assertion in assertions:
            latest_producer[statement_key(assertion)] = index
            weak_producers.setdefault(statement_weak_key(assertion), []).append(index)
    return tuple(nodes)


def load_proof_trace(path: Path) -> tuple[ProofNode, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise TypeError("proof payload must be an object")
    return build_proof_trace(payload)


def render_markdown(
    problem_name: str, proof_path: Path | str, nodes: Iterable[ProofNode]
) -> str:
    materialized = tuple(nodes)
    lines = [
        f"# {problem_name}: Yuclid proof trace",
        "",
        f"- Certificate: `{proof_path}`",
        f"- Deductions read: {len(materialized)}",
        "- Order: Yuclid certificate order; every deduction is retained.",
        "",
        "## Complete deduction trace",
        "",
    ]
    for node in materialized:
        refs = ", ".join(
            "given" if producer is None else f"D{producer:03d}"
            for producer in node.assumption_producers
        ) or "none"
        bridge = " [SINE-DISTANCE BRIDGE]" if node.is_cross_chart_bridge else ""
        lines.append(f"### D{node.index:03d} `{node.channel}`{bridge}")
        lines.append("")
        lines.append(f"Dependencies: {refs}")
        lines.append("")
        if node.assumptions:
            lines.append("Assumptions:")
            lines.extend(f"- {render_statement(item)}" for item in node.assumptions)
        else:
            lines.append("Assumptions: none")
        lines.append("")
        lines.append("Assertions:")
        lines.extend(f"- {render_statement(item)}" for item in node.assertions)
        lines.append("")
    return "\n".join(lines)
