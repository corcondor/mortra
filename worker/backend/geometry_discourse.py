"""Typed discourse elaboration for named circles and tangent references.

The surface grammar only identifies declarations and references.  Mathematical
meaning is carried by CircleObject and is lowered to the same primitive
predicates used by the geometry backend.  This keeps anaphora resolution out of
the theorem prover and avoids treating each sentence form as a solution rule.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Callable


@dataclass
class CircleObject:
    name: str
    center: str | None
    through: tuple[str, ...]
    source: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class PrimitiveRelation:
    name: str
    points: tuple[str, ...]
    source: str


@dataclass
class DiscourseElaboration:
    premise_text: str
    goal_text: str
    premise_relations: list[PrimitiveRelation]
    goal_relations: list[PrimitiveRelation]
    circles: list[CircleObject]
    unresolved: list[str]


_CIRCLE_NAME = r"(?:[ΓΩγω]|[A-Za-z][A-Za-z0-9_]*)"


def elaborate_circle_discourse(premise_text: str, goal_text: str) -> DiscourseElaboration:
    circles: dict[str, CircleObject] = {}
    order: list[str] = []
    premise_relations: list[PrimitiveRelation] = []
    unresolved: list[str] = []

    premise_text, declarations = _extract_declarations(premise_text)
    for circle, relations in declarations:
        key = _circle_key(circle.name)
        circles[key] = circle
        if key in order:
            order.remove(key)
        order.append(key)
        premise_relations.extend(relations)

    premise_text, premise_refs, premise_errors = _elaborate_references(
        premise_text, circles, order, goal=False,
    )
    goal_text, goal_refs, goal_errors = _elaborate_references(
        goal_text, circles, order, goal=True,
    )
    premise_relations.extend(premise_refs)
    unresolved.extend(premise_errors)
    unresolved.extend(goal_errors)
    return DiscourseElaboration(
        premise_text=_clean_consumed_text(premise_text),
        goal_text=_clean_consumed_text(goal_text),
        premise_relations=premise_relations,
        goal_relations=goal_refs,
        circles=[circles[key] for key in order],
        unresolved=unresolved,
    )


def _extract_declarations(text: str) -> tuple[str, list[tuple[CircleObject, list[PrimitiveRelation]]]]:
    declarations: list[tuple[CircleObject, list[PrimitiveRelation]]] = []
    spans: list[tuple[int, int]] = []

    def collect(pattern: str, builder: Callable[[re.Match[str]], CircleObject]) -> None:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            if _overlaps(match.span(), spans):
                continue
            circle = builder(match)
            declarations.append((circle, _circle_definition_relations(circle)))
            spans.append(match.span())

    collect(
        rf"(?:円\s*)?({_CIRCLE_NAME})\s*(?:は|を)\s*([A-Z])\s*[,、]\s*([A-Z])\s*[,、]\s*([A-Z])\s*(?:を通る|through)",
        lambda m: CircleObject(m.group(1), None, _points(m, 2, 3, 4), m.group(0)),
    )
    collect(
        rf"([A-Z])\s*[,、]\s*([A-Z])\s*[,、]\s*([A-Z])\s*を通る円\s*({_CIRCLE_NAME})\s*(?:とする|を考える|である)?",
        lambda m: CircleObject(m.group(4), None, _points(m, 1, 2, 3), m.group(0)),
    )
    collect(
        rf"([A-Z])\s*を中心とし\s*([A-Z])\s*を通る円\s*({_CIRCLE_NAME})",
        lambda m: CircleObject(m.group(3), m.group(1).lower(), _points(m, 2), m.group(0)),
    )
    collect(
        rf"中心\s*([A-Z])\s*[,、]\s*半径\s*\1([A-Z])\s*の円\s*({_CIRCLE_NAME})",
        lambda m: CircleObject(m.group(3), m.group(1).lower(), _points(m, 2), m.group(0)),
    )
    collect(
        rf"三角形\s*([A-Z])([A-Z])([A-Z])\s*の外接円(?:を|は)\s*({_CIRCLE_NAME})\s*(?:とする|である)?",
        lambda m: CircleObject(m.group(4), None, _points(m, 1, 2, 3), m.group(0)),
    )
    collect(
        rf"Let\s+({_CIRCLE_NAME})\s+be\s+the\s+circle\s+through\s+([A-Z])\s*[, ]\s*([A-Z])\s*(?:and|[, ])\s*([A-Z])",
        lambda m: CircleObject(m.group(1), None, _points(m, 2, 3, 4), m.group(0)),
    )
    collect(
        rf"Let\s+({_CIRCLE_NAME})\s+be\s+the\s+circle\s+centered\s+at\s+([A-Z])\s+(?:and\s+)?through\s+([A-Z])",
        lambda m: CircleObject(m.group(1), m.group(2).lower(), _points(m, 3), m.group(0)),
    )
    collect(
        rf"Let\s+({_CIRCLE_NAME})\s+be\s+the\s+circumcircle\s+of\s+(?:triangle\s+)?([A-Z])([A-Z])([A-Z])",
        lambda m: CircleObject(m.group(1), None, _points(m, 2, 3, 4), m.group(0)),
    )
    return _blank_spans(text, spans), declarations


def _elaborate_references(
    text: str,
    circles: dict[str, CircleObject],
    order: list[str],
    *,
    goal: bool,
) -> tuple[str, list[PrimitiveRelation], list[str]]:
    if not circles:
        return text, [], []
    relations: list[PrimitiveRelation] = []
    errors: list[str] = []
    spans: list[tuple[int, int]] = []
    registered = "|".join(
        re.escape(circle.name)
        for circle in sorted(circles.values(), key=lambda item: len(item.name), reverse=True)
    )
    reference = rf"(?:{registered}|その円|this\s+circle|the\s+circle)"

    def circle_for(token: str) -> CircleObject | None:
        if re.fullmatch(r"その円|this\s+circle|the\s+circle", token, re.IGNORECASE):
            return circles[order[-1]] if order else None
        return circles.get(_circle_key(token))

    def consume(pattern: str, handler: Callable[[re.Match[str], CircleObject], list[PrimitiveRelation]]) -> None:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            if _overlaps(match.span(), spans):
                continue
            circle = circle_for(match.group("circle"))
            if circle is None:
                errors.append(f"unresolved circle reference: {match.group('circle')}")
                spans.append(match.span())
                continue
            produced = handler(match, circle)
            if goal and len(produced) != 1:
                errors.append("a circle query elaborated to a conjunction; name the requested primitive relation")
            else:
                relations.extend(produced)
            spans.append(match.span())

    consume(
        rf"(?P<point>[A-Z])\s*は\s*(?P<circle>{reference})\s*(?:の?円周上|上にある|上)",
        lambda m, c: _membership_relations(c, m.group("point").lower(), m.group(0)),
    )
    consume(
        rf"(?P<point>[A-Z])\s+(?:is|lies)\s+on\s+(?P<circle>{reference})",
        lambda m, c: _membership_relations(c, m.group("point").lower(), m.group(0)),
    )
    consume(
        rf"(?:直線\s*)?(?P<a>[A-Z])(?P<b>[A-Z])\s*(?:は|is)?\s*(?P<circle>{reference})\s*(?:に|へ|is\s+)?(?:点\s*)?(?P<contact>[A-Z])\s*(?:で|at)\s*(?:接する|tangent)",
        lambda m, c: _tangent_relations(c, m.group("a"), m.group("b"), m.group("contact"), m.group(0)),
    )
    consume(
        rf"(?:line\s+)?(?P<a>[A-Z])(?P<b>[A-Z])\s+is\s+tangent\s+to\s+(?P<circle>{reference})\s+at\s+(?P<contact>[A-Z])",
        lambda m, c: _tangent_relations(c, m.group("a"), m.group("b"), m.group("contact"), m.group(0)),
    )
    consume(
        rf"(?:直線\s*)?(?P<a>[A-Z])(?P<b>[A-Z])\s*(?:は|is)?\s*(?P<circle>{reference})\s*(?:に|の)?(?:接する|接線である|tangent)",
        lambda m, c: _tangent_relations(c, m.group("a"), m.group("b"), None, m.group(0)),
    )
    return _blank_spans(text, spans), relations, errors


def _circle_definition_relations(circle: CircleObject) -> list[PrimitiveRelation]:
    if circle.center and circle.through:
        return []
    if len(circle.through) >= 3:
        center = _ensure_center(circle)
        a, b, c = circle.through[:3]
        return [
            PrimitiveRelation("cong", (center, a, center, b), circle.source),
            PrimitiveRelation("cong", (center, b, center, c), circle.source),
        ]
    return []


def _membership_relations(circle: CircleObject, point: str, source: str) -> list[PrimitiveRelation]:
    if len(circle.through) >= 3:
        a, b, c = circle.through[:3]
        if point in (a, b, c):
            return []
        return [PrimitiveRelation("cyclic", (a, b, c, point), source)]
    if circle.center and circle.through:
        anchor = circle.through[0]
        return [PrimitiveRelation("cong", (circle.center, point, circle.center, anchor), source)]
    return []


def _tangent_relations(
    circle: CircleObject,
    a: str,
    b: str,
    contact: str | None,
    source: str,
) -> list[PrimitiveRelation]:
    a, b = a.lower(), b.lower()
    center = _ensure_center(circle)
    contact_name = contact.lower() if contact else _safe_name(f"{circle.name}_contact_{a}{b}")
    result = []
    if contact is None:
        result.append(PrimitiveRelation("coll", (a, contact_name, b), source))
    result.extend(_membership_relations(circle, contact_name, source))
    result.append(PrimitiveRelation("perp", (a, b, center, contact_name), source))
    return result


def _ensure_center(circle: CircleObject) -> str:
    if circle.center is None:
        circle.center = _safe_name(f"{circle.name}_center")
    return circle.center


def _circle_key(name: str) -> str:
    return name.strip().lower()


def _safe_name(name: str) -> str:
    transliteration = {"Γ": "gamma", "γ": "gamma", "Ω": "omega", "ω": "omega"}
    for source, target in transliteration.items():
        name = name.replace(source, target)
    return re.sub(r"[^a-zA-Z0-9_]+", "_", name).strip("_").lower()


def _points(match: re.Match[str], *indices: int) -> tuple[str, ...]:
    return tuple(match.group(index).lower() for index in indices)


def _overlaps(span: tuple[int, int], spans: list[tuple[int, int]]) -> bool:
    return any(span[0] < end and start < span[1] for start, end in spans)


def _blank_spans(text: str, spans: list[tuple[int, int]]) -> str:
    result = list(text)
    for start, end in spans:
        result[start:end] = " " * (end - start)
    return "".join(result)


def _clean_consumed_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip(" ,;。. ")
