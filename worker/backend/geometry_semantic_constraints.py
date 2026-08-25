"""Typed semialgebraic constraints recovered from geometry prose.

The JGEX construction language records incidence and metric equalities, but
some source problems also use strict order information such as "on the other
side of line BC".  This module keeps that information separate from the
polynomial ideal and produces replayable branch certificates when a strict
sign condition selects one component of an algebraic construction.

No parser or certificate in this module can inspect a problem identifier or a
goal.  The only inputs are source prose, typed points, and construction data.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import re
from typing import Literal

import sympy as sp


Point = tuple[sp.Expr, sp.Expr]
HalfPlanePredicate = Literal["same_side", "opposite_side"]


@dataclass(frozen=True)
class OrientedHalfPlaneRelation:
    predicate: HalfPlanePredicate
    left: str
    right: str
    line_start: str
    line_end: str
    source_text: str

    @property
    def canonical_line(self) -> tuple[str, str]:
        return tuple(sorted((self.line_start, self.line_end)))


@dataclass(frozen=True)
class HalfPlaneDerivation:
    predicate: HalfPlanePredicate
    left: str
    right: str
    line_start: str
    line_end: str
    premises: tuple[OrientedHalfPlaneRelation, ...]
    rule: str


@dataclass(frozen=True)
class GeometrySemanticContext:
    source_sha256: str
    half_plane_relations: tuple[OrientedHalfPlaneRelation, ...]

    def derive_same_side(
        self,
        left: str,
        right: str,
        line_start: str,
        line_end: str,
    ) -> HalfPlaneDerivation | None:
        """Prove a same-side relation using only finite signed-side logic."""

        target_line = tuple(sorted((line_start, line_end)))
        left = left.lower()
        right = right.lower()
        direct = [
            relation
            for relation in self.half_plane_relations
            if relation.canonical_line == target_line
            and relation.predicate == "same_side"
            and {relation.left, relation.right} == {left, right}
        ]
        if direct:
            return HalfPlaneDerivation(
                predicate="same_side",
                left=left,
                right=right,
                line_start=line_start,
                line_end=line_end,
                premises=(direct[0],),
                rule="source_same_side",
            )

        # If X and Y are both strictly opposite to the same anchor with
        # respect to one oriented line, X and Y are strictly on the same side.
        opposite = [
            relation
            for relation in self.half_plane_relations
            if relation.canonical_line == target_line
            and relation.predicate == "opposite_side"
        ]
        for first in opposite:
            first_pair = {first.left, first.right}
            for second in opposite:
                if first is second:
                    continue
                second_pair = {second.left, second.right}
                shared = first_pair & second_pair
                if len(shared) != 1:
                    continue
                outer = (first_pair | second_pair) - shared
                if outer == {left, right}:
                    return HalfPlaneDerivation(
                        predicate="same_side",
                        left=left,
                        right=right,
                        line_start=line_start,
                        line_end=line_end,
                        premises=(first, second),
                        rule="opposite_to_common_anchor_implies_same_side",
                    )
        return None


@dataclass(frozen=True)
class SemialgebraicBranchCertificate:
    theorem: str
    source_clause_indices: tuple[int, ...]
    points: tuple[str, ...]
    semantic_relations: tuple[str, ...]
    semantic_derivation_rule: str
    source_equations: tuple[str, ...]
    selected_branch_equations: tuple[str, ...]
    rejected_branch_equations: tuple[str, ...]
    coordinate_substitutions: tuple[tuple[str, str], ...]
    saturation_multiplier: str
    branch_product: str
    algebraic_replay_residuals: tuple[str, ...]
    sign_replay: str
    goal_independent: bool
    replayed: bool
    certificate_sha256: str


_POINT = r"[A-Z](?:_[A-Za-z0-9]+)?"
_POINT_LIST = rf"{_POINT}(?:\s*(?:,|and)\s*{_POINT})*"


def _normalize_geometry_prose(text: str) -> str:
    normalized = text.replace("\\(", " ").replace("\\)", " ")
    normalized = normalized.replace("$", " ")
    normalized = re.sub(r"_\{([^{}]+)\}", r"_\1", normalized)
    normalized = normalized.replace("{", " ").replace("}", " ")
    normalized = re.sub(r"\\(?:text|mathrm|operatorname)\s*", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _points(fragment: str) -> tuple[str, ...]:
    return tuple(item.lower() for item in re.findall(_POINT, fragment))


def parse_geometry_semantic_context(text: str | None) -> GeometrySemanticContext:
    """Extract explicit strict half-plane relations from English prose."""

    source = text or ""
    normalized = _normalize_geometry_prose(source)
    relations: list[OrientedHalfPlaneRelation] = []

    one_other = re.compile(
        rf"(?P<first>{_POINT_LIST})\s+(?:is|are|lies?|lie)\s+on\s+one\s+side\s+of\s+"
        rf"(?:the\s+)?line\s+(?P<line>{_POINT}{_POINT})\s+and\s+"
        rf"(?P<second>{_POINT_LIST})\s+(?:is|are|lies?|lie)\s+on\s+the\s+other\s+side",
        re.IGNORECASE,
    )
    same_side = re.compile(
        rf"(?P<points>{_POINT_LIST})\s+(?:is|are|lies?|lie)\s+on\s+the\s+same\s+side\s+of\s+"
        rf"(?:the\s+)?line\s+(?P<line>{_POINT}{_POINT})",
        re.IGNORECASE,
    )
    opposite_sides = re.compile(
        rf"(?P<points>{_POINT_LIST})\s+(?:is|are|lies?|lie)\s+on\s+(?:the\s+)?opposite\s+sides\s+of\s+"
        rf"(?:the\s+)?line\s+(?P<line>{_POINT}{_POINT})",
        re.IGNORECASE,
    )

    for match in one_other.finditer(normalized):
        line_points = _points(match.group("line"))
        first = _points(match.group("first"))
        second = _points(match.group("second"))
        if len(line_points) != 2:
            continue
        for left in first:
            for right in second:
                relations.append(
                    OrientedHalfPlaneRelation(
                        predicate="opposite_side",
                        left=left,
                        right=right,
                        line_start=line_points[0],
                        line_end=line_points[1],
                        source_text=match.group(0),
                    )
                )

    for pattern, predicate in (
        (same_side, "same_side"),
        (opposite_sides, "opposite_side"),
    ):
        for match in pattern.finditer(normalized):
            line_points = _points(match.group("line"))
            points = _points(match.group("points"))
            if len(line_points) != 2 or len(points) != 2:
                continue
            relations.append(
                OrientedHalfPlaneRelation(
                    predicate=predicate,
                    left=points[0],
                    right=points[1],
                    line_start=line_points[0],
                    line_end=line_points[1],
                    source_text=match.group(0),
                )
            )

    unique: dict[
        tuple[str, str, str, str, str], OrientedHalfPlaneRelation
    ] = {}
    for relation in relations:
        key = (
            relation.predicate,
            *sorted((relation.left, relation.right)),
            *relation.canonical_line,
        )
        unique.setdefault(key, relation)
    return GeometrySemanticContext(
        source_sha256=hashlib.sha256(source.encode("utf-8")).hexdigest(),
        half_plane_relations=tuple(unique.values()),
    )


def _sub(left: Point, right: Point) -> Point:
    return left[0] - right[0], left[1] - right[1]


def _scale(value: sp.Expr, point: Point) -> Point:
    return value * point[0], value * point[1]


def _dot(left: Point, right: Point) -> sp.Expr:
    return sp.expand(left[0] * right[0] + left[1] * right[1])


def _cross(left: Point, right: Point) -> sp.Expr:
    return sp.expand(left[0] * right[1] - left[1] * right[0])


def _safe(expression: sp.Expr) -> str:
    return sp.sstr(expression)


@lru_cache(maxsize=1)
def _paired_tangent_identity_replay_residuals() -> tuple[str, ...]:
    """Replay the universal polynomial identities once, before instantiation."""

    rx, ry, qx, qy, ux, uy, vx, vy = sp.symbols(
        "rx ry qx qy ux uy vx vy"
    )
    r = (rx, ry)
    q = (qx, qy)
    u = (ux, uy)
    v = (vx, vy)
    t = _sub(q, r)
    r2 = _dot(r, r)
    ur = _dot(u, r)
    s = (
        r2 * u[0] - 2 * ur * r[0],
        r2 * u[1] - 2 * ur * r[1],
    )
    p = _scale(r2, v)
    e0 = 2 * _dot(q, r) - r2
    e1 = _dot(u, q)
    e2 = _dot(u, u) - r2
    e3 = _dot(v, t)
    e4 = _dot(v, v) - r2
    p2 = _dot(p, p)
    s2 = _dot(s, s)
    dot_pt = _dot(p, t)
    dot_st = _dot(s, t)

    # Replay the two universal two-dimensional identities independently of
    # the geometry substitution.  Substituting all eight geometry variables
    # before expansion creates a large polynomial while proving no stronger
    # fact.
    px, py, sx, sy, tx, ty = sp.symbols("px py sx sy tx ty")
    abstract_p = (px, py)
    abstract_s = (sx, sy)
    abstract_t = (tx, ty)
    selected = _sub(abstract_p, abstract_s)
    rejected = (
        abstract_p[0] + abstract_s[0],
        abstract_p[1] + abstract_s[1],
    )
    residuals = (
        sp.expand(dot_pt - r2 * e3),
        sp.expand(dot_st - (r2 * e1 - ur * e0)),
        sp.expand(
            _dot(abstract_t, abstract_t) * _cross(abstract_p, abstract_s)
            - _dot(abstract_p, abstract_t) * _cross(abstract_t, abstract_s)
            - _cross(abstract_p, abstract_t) * _dot(abstract_t, abstract_s)
        ),
        sp.expand(p2 - r2**3 - r2**2 * e4),
        sp.expand(s2 - r2**3 - r2**2 * e2),
        sp.expand(
            _dot(selected, selected) * _dot(rejected, rejected)
            - (_dot(abstract_p, abstract_p) - _dot(abstract_s, abstract_s))
            ** 2
            - 4 * _cross(abstract_p, abstract_s) ** 2
        ),
    )
    if any(residual != 0 for residual in residuals):
        raise AssertionError("universal paired tangent identity did not replay")
    return tuple(sp.sstr(residual) for residual in residuals)


def certify_paired_circumcircle_tangent_branch(
    *,
    center: Point,
    first_center: Point,
    second_center: Point,
    first_output: Point,
    second_output: Point,
    point_names: tuple[str, str, str, str, str],
    source_clause_indices: tuple[int, int, int],
    same_side_derivation: HalfPlaneDerivation,
) -> tuple[
    SemialgebraicBranchCertificate,
    tuple[sp.Expr, sp.Expr],
    sp.Expr,
    Point,
]:
    """Select the reflection branch of two paired tangent-circle loci.

    Let O be equidistant from B and C.  D lies on the tangent at B and
    |BD|=|BC|; E satisfies the symmetric conditions at C.  Algebraically E
    has two possible branches.  If D and E are strictly on the same side of
    BC, the branch reversing signed height is impossible, so E is the mirror
    image of D in the perpendicular bisector of BC.
    """

    center_name, b_name, c_name, d_name, e_name = point_names
    r = _sub(second_center, first_center)
    q = _sub(center, first_center)
    u = _sub(first_output, first_center)
    v = _sub(second_output, second_center)
    t = _sub(q, r)
    r2 = _dot(r, r)
    ur = _dot(u, r)
    reflected_numerator = (
        sp.expand(r2 * u[0] - 2 * ur * r[0]),
        sp.expand(r2 * u[1] - 2 * ur * r[1]),
    )
    second_numerator = _scale(r2, v)
    selected_numerator = (
        sp.expand(second_numerator[0] - reflected_numerator[0]),
        sp.expand(second_numerator[1] - reflected_numerator[1]),
    )
    rejected_numerator = (
        sp.expand(second_numerator[0] + reflected_numerator[0]),
        sp.expand(second_numerator[1] + reflected_numerator[1]),
    )
    # These two equations are equivalent to v=S(u) on |BC|^2 != 0, but
    # remain bilinear instead of introducing the cubic numerator directly.
    selected = (
        sp.expand(_cross(r, _sub(v, u))),
        sp.expand(_dot(r, (v[0] + u[0], v[1] + u[1]))),
    )
    rejected = (
        sp.expand(_cross(r, (v[0] + u[0], v[1] + u[1]))),
        sp.expand(_dot(r, _sub(v, u))),
    )
    reflected_output = (
        sp.cancel(second_center[0] + reflected_numerator[0] / r2),
        sp.cancel(second_center[1] + reflected_numerator[1] / r2),
    )

    circumcenter_bc = sp.expand(2 * _dot(q, r) - r2)
    tangent_d = _dot(u, q)
    radius_d = sp.expand(_dot(u, u) - r2)
    tangent_e = _dot(v, t)
    radius_e = sp.expand(_dot(v, v) - r2)
    source_equations = (
        circumcenter_bc,
        tangent_d,
        radius_d,
        tangent_e,
        radius_e,
    )

    p = second_numerator
    s = reflected_numerator
    t2 = _dot(t, t)
    residuals = _paired_tangent_identity_replay_residuals()
    replayed = all(residual == "0" for residual in residuals)

    branch_product = sp.Mul(
        _dot(selected_numerator, selected_numerator),
        _dot(rejected_numerator, rejected_numerator),
        evaluate=False,
    )
    semantic_relations = tuple(
        f"{item.predicate}({item.left},{item.right};{item.line_start},{item.line_end})"
        for item in same_side_derivation.premises
    )
    sign_replay = (
        f"same_side({d_name},{e_name};{b_name},{c_name}) gives "
        "cross(C-B,D-B)*cross(C-B,E-C)>0; the rejected branch gives "
        "cross(C-B,E-C)=-cross(C-B,D-B), a contradiction"
    )
    material = "|".join(
        (
            "paired_circumcircle_tangent_equal_radius_same_side_reflection",
            *point_names,
            *(str(item) for item in source_clause_indices),
            *semantic_relations,
            *(_safe(item) for item in source_equations),
            *(_safe(item) for item in selected),
            *(_safe(item) for item in rejected),
            *(
                f"{_safe(variable)}={_safe(replacement)}"
                for variable, replacement in zip(
                    second_output,
                    reflected_output,
                    strict=True,
                )
            ),
            _safe(t2**2),
            _safe(branch_product),
            sign_replay,
        )
    )
    certificate = SemialgebraicBranchCertificate(
        theorem="paired_circumcircle_tangent_equal_radius_same_side_reflection",
        source_clause_indices=source_clause_indices,
        points=(center_name, b_name, c_name, d_name, e_name),
        semantic_relations=semantic_relations,
        semantic_derivation_rule=same_side_derivation.rule,
        source_equations=tuple(_safe(item) for item in source_equations),
        selected_branch_equations=tuple(_safe(item) for item in selected),
        rejected_branch_equations=tuple(_safe(item) for item in rejected),
        coordinate_substitutions=tuple(
            (_safe(variable), _safe(replacement))
            for variable, replacement in zip(
                second_output,
                reflected_output,
                strict=True,
            )
        ),
        saturation_multiplier=_safe(t2**2),
        branch_product=_safe(branch_product),
        algebraic_replay_residuals=residuals,
        sign_replay=sign_replay,
        goal_independent=True,
        replayed=replayed,
        certificate_sha256=hashlib.sha256(material.encode("utf-8")).hexdigest(),
    )
    return certificate, selected, t2, reflected_output
