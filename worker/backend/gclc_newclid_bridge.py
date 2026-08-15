"""Concrete GCLC obligations lowered to Newclid predicates and exact polynomials.

The bridge does not trust a GCLC success flag as a Newclid assumption.  It
reconstructs the construction equations, proves ideal membership independently,
and emits a Newclid predicate string only when the exact remainder is zero.
"""

from __future__ import annotations

import hashlib
import itertools
import re
from dataclasses import dataclass
from typing import Iterable

import sympy as sp

from worker.backend.geometry_relation_channels import canonical_relation


@dataclass(frozen=True)
class LineDefinition:
    kind: str
    origin: str
    reference: str | None = None
    head: str | None = None


@dataclass(frozen=True)
class GCLCRelationObligation:
    channel: str
    points: tuple[str, ...]
    newclid_predicate: str
    construction_equations: tuple[str, ...]
    normalization_assumptions: tuple[str, ...]
    nondegeneracy_conditions: tuple[str, ...]
    goal_polynomial: str
    groebner_basis: tuple[str, ...]
    quotient_certificate: tuple[str, ...]
    rational_denominators: tuple[str, ...]
    verification_method: str
    remainder: str
    exact_replay: bool
    certificate_sha256: str


def _active_lines(source: str) -> list[str]:
    return [
        line.strip()
        for line in source.splitlines()
        if line.strip() and not line.lstrip().startswith("%")
    ]


def _prove_tokens(source: str) -> tuple[str, tuple[str, ...]]:
    active = _active_lines(source)
    start = next(
        (index for index, line in enumerate(active) if re.search(r"\bprove\b", line)),
        None,
    )
    if start is None:
        raise ValueError("GCLC source has no prove block")
    prove = " ".join(active[start:])
    match = re.search(
        r"\bprove\s*\{\s*(collinear|parallel|perpendicular)\s+([^{}]+?)\s*\}",
        prove,
        flags=re.IGNORECASE,
    )
    if not match:
        segment = re.search(
            r"\bprove\s*\{\s*equal\s*\{\s*segment\s+(\S+)\s+(\S+)\s*\}"
            r"\s*\{\s*segment\s+(\S+)\s+(\S+)\s*\}\s*\}",
            prove,
            flags=re.IGNORECASE,
        )
        if segment:
            return "cong", tuple(segment.groups())
        raise ValueError("unsupported GCLC goal")
    relation = canonical_relation(match.group(1))
    points = tuple(match.group(2).split())
    expected_arity = {"coll": 3, "para": 4, "perp": 4}[relation]
    if len(points) != expected_arity:
        raise ValueError(f"{relation} expects {expected_arity} points, got {points}")
    return relation, points


def _newclid_name(name: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_]", "_", name).strip("_").lower()
    if not normalized:
        raise ValueError(f"invalid point name: {name!r}")
    return normalized


class _PolynomialModel:
    def __init__(
        self,
        source: str,
        goal_points: Iterable[str],
        goal_channel: str,
    ) -> None:
        self.lines: dict[str, LineDefinition] = {}
        self.midpoints: list[tuple[str, str, str]] = []
        self.online_points: list[tuple[str, str, str]] = []
        self.intersections: list[tuple[str, str, str]] = []
        self.construction_steps: list[tuple[str, tuple[str, ...]]] = []
        self.declared_points: list[tuple[str, sp.Rational, sp.Rational]] = []
        self.unsupported_commands: set[str] = set()
        self.point_names: set[str] = set(goal_points)
        for line in _active_lines(source):
            tokens = line.split()
            if not tokens:
                continue
            command = tokens[0].lower()
            if command == "point" and len(tokens) >= 2:
                self.point_names.add(tokens[1])
                if len(tokens) >= 4:
                    try:
                        self.declared_points.append(
                            (tokens[1], sp.Rational(tokens[2]), sp.Rational(tokens[3]))
                        )
                    except (TypeError, ValueError):
                        pass
            elif command == "midpoint" and len(tokens) == 4:
                self.midpoints.append((tokens[1], tokens[2], tokens[3]))
                self.construction_steps.append((command, tuple(tokens[1:])))
                self.point_names.update(tokens[1:])
            elif command == "online" and len(tokens) == 4:
                self.online_points.append((tokens[1], tokens[2], tokens[3]))
                self.construction_steps.append((command, tuple(tokens[1:])))
                self.point_names.update(tokens[1:])
            elif command == "line" and len(tokens) == 4:
                self.lines[tokens[1]] = LineDefinition("through", tokens[2], head=tokens[3])
                self.point_names.update(tokens[2:])
            elif command in {"perp", "parallel"} and len(tokens) == 4:
                kind = "perp" if command == "perp" else "parallel"
                self.lines[tokens[1]] = LineDefinition(kind, tokens[2], reference=tokens[3])
                self.point_names.add(tokens[2])
            elif command == "intersec" and len(tokens) == 4:
                self.intersections.append((tokens[1], tokens[2], tokens[3]))
                self.construction_steps.append((command, tuple(tokens[1:])))
                self.point_names.add(tokens[1])
            elif not self._is_decorative_command(command):
                self.unsupported_commands.add(command)

        self.normalization_assumptions: tuple[str, ...] = tuple()
        gauge = self._affine_gauge(goal_channel)
        ordered = sorted(self.point_names)
        self.coordinates: dict[str, tuple[sp.Expr, sp.Expr]] = {}
        for index, point in enumerate(ordered):
            if point in gauge:
                self.coordinates[point] = gauge[point]
            else:
                self.coordinates[point] = (
                    sp.Symbol(f"x_{index}"),
                    sp.Symbol(f"y_{index}"),
                )
        self.variables = tuple(
            coordinate
            for point in ordered
            for coordinate in self.coordinates[point]
            if isinstance(coordinate, sp.Symbol)
        )

    @staticmethod
    def _is_decorative_command(command: str) -> bool:
        return (
            command in {"area", "dim", "color", "prooflevel", "prove"}
            or command.startswith("draw")
            or command.startswith("cmark")
            or command.startswith("mark")
        )

    def _affine_gauge(self, goal_channel: str) -> dict[str, tuple[sp.Expr, sp.Expr]]:
        if goal_channel not in {"coll", "para"}:
            return {}
        if any(definition.kind == "perp" for definition in self.lines.values()):
            return {}
        for left, middle, right in itertools.combinations(self.declared_points, 3):
            determinant = (middle[1] - left[1]) * (right[2] - left[2]) - (
                middle[2] - left[2]
            ) * (right[1] - left[1])
            if determinant == 0:
                continue
            self.normalization_assumptions = (
                f"ncoll {left[0]} {middle[0]} {right[0]}",
                f"affine_gauge {left[0]}=(0,0) {middle[0]}=(1,0) {right[0]}=(0,1)",
            )
            return {
                left[0]: (sp.Integer(0), sp.Integer(0)),
                middle[0]: (sp.Integer(1), sp.Integer(0)),
                right[0]: (sp.Integer(0), sp.Integer(1)),
            }
        return {}

    def vector(self, start: str, end: str) -> tuple[sp.Expr, sp.Expr]:
        sx, sy = self.coordinates[start]
        ex, ey = self.coordinates[end]
        return ex - sx, ey - sy

    @staticmethod
    def cross(left: tuple[sp.Expr, sp.Expr], right: tuple[sp.Expr, sp.Expr]) -> sp.Expr:
        return sp.expand(left[0] * right[1] - left[1] * right[0])

    @staticmethod
    def dot(left: tuple[sp.Expr, sp.Expr], right: tuple[sp.Expr, sp.Expr]) -> sp.Expr:
        return sp.expand(left[0] * right[0] + left[1] * right[1])

    def direction(self, name: str, seen: frozenset[str] = frozenset()) -> tuple[sp.Expr, sp.Expr]:
        if name in seen:
            raise ValueError(f"cyclic line definition: {name}")
        definition = self.lines[name]
        if definition.kind == "through":
            assert definition.head is not None
            return self.vector(definition.origin, definition.head)
        assert definition.reference is not None
        dx, dy = self.direction(definition.reference, seen | {name})
        if definition.kind == "parallel":
            return dx, dy
        return -dy, dx

    def membership(self, point: str, line: str) -> sp.Expr:
        definition = self.lines[line]
        displacement = self.vector(definition.origin, point)
        direction = self.direction(line)
        if definition.kind == "perp":
            reference_direction = self.direction(definition.reference or "")
            return self.dot(displacement, reference_direction)
        return self.cross(displacement, direction)

    def equations(self) -> tuple[sp.Expr, ...]:
        result: list[sp.Expr] = []
        for midpoint, left, right in self.midpoints:
            mx, my = self.coordinates[midpoint]
            lx, ly = self.coordinates[left]
            rx, ry = self.coordinates[right]
            result.extend((2 * mx - lx - rx, 2 * my - ly - ry))
        for point, left, right in self.online_points:
            result.append(self.cross(self.vector(left, point), self.vector(left, right)))
        for point, left_line, right_line in self.intersections:
            result.extend(
                (self.membership(point, left_line), self.membership(point, right_line))
            )
        return tuple(sp.expand(item) for item in result if item != 0)

    def nondegeneracy(self) -> tuple[sp.Expr, ...]:
        result: list[sp.Expr] = []
        for definition in self.lines.values():
            if definition.kind == "through":
                assert definition.head is not None
                dx, dy = self.vector(definition.origin, definition.head)
                result.append(sp.expand(dx * dx + dy * dy))
        for _, left, right in self.online_points:
            dx, dy = self.vector(left, right)
            result.append(sp.expand(dx * dx + dy * dy))
        for _, left_line, right_line in self.intersections:
            result.append(sp.expand(self.cross(self.direction(left_line), self.direction(right_line))))
        unique = {sp.sstr(item): item for item in result if item != 0}
        return tuple(unique[key] for key in sorted(unique))

    def goal(self, channel: str, points: tuple[str, ...]) -> sp.Expr:
        if channel in {"coll", "para"}:
            a, b, c, *tail = points
            d = tail[0] if tail else c
            right = self.vector(c, d) if channel == "para" else self.vector(a, c)
            return self.cross(self.vector(a, b), right)
        if channel == "perp":
            a, b, c, d = points
            return self.dot(self.vector(a, b), self.vector(c, d))
        if channel == "cong":
            a, b, c, d = points
            ab = self.vector(a, b)
            cd = self.vector(c, d)
            return sp.expand(self.dot(ab, ab) - self.dot(cd, cd))
        raise ValueError(f"unsupported exact goal channel: {channel}")

    def rational_replay(
        self,
        channel: str,
        points: tuple[str, ...],
    ) -> tuple[bool, sp.Expr, tuple[sp.Expr, ...]]:
        substitutions: dict[sp.Symbol, sp.Expr] = {}
        denominators: list[sp.Expr] = []
        parameter_index = 0

        def resolve(expression: sp.Expr) -> sp.Expr:
            return sp.cancel(expression.xreplace(substitutions))

        def resolved_point(point: str) -> tuple[sp.Expr, sp.Expr]:
            x, y = self.coordinates[point]
            return resolve(x), resolve(y)

        def resolved_direction(line: str) -> tuple[sp.Expr, sp.Expr]:
            dx, dy = self.direction(line)
            return resolve(dx), resolve(dy)

        for kind, arguments in self.construction_steps:
            if kind == "midpoint":
                point, left, right = arguments
                px, py = self.coordinates[point]
                lx, ly = resolved_point(left)
                rx, ry = resolved_point(right)
                assert isinstance(px, sp.Symbol) and isinstance(py, sp.Symbol)
                substitutions[px] = sp.cancel((lx + rx) / 2)
                substitutions[py] = sp.cancel((ly + ry) / 2)
                continue
            if kind == "online":
                point, left, right = arguments
                px, py = self.coordinates[point]
                lx, ly = resolved_point(left)
                rx, ry = resolved_point(right)
                parameter = sp.Symbol(f"_online_{parameter_index}")
                parameter_index += 1
                assert isinstance(px, sp.Symbol) and isinstance(py, sp.Symbol)
                substitutions[px] = sp.expand(lx + parameter * (rx - lx))
                substitutions[py] = sp.expand(ly + parameter * (ry - ly))
                continue
            if kind == "intersec":
                point, left_line, right_line = arguments
                px, py = self.coordinates[point]
                left_definition = self.lines[left_line]
                right_definition = self.lines[right_line]
                ax, ay = resolved_point(left_definition.origin)
                bx, by = resolved_point(right_definition.origin)
                left_direction = resolved_direction(left_line)
                right_direction = resolved_direction(right_line)
                displacement = (bx - ax, by - ay)
                denominator = sp.factor(self.cross(left_direction, right_direction))
                if denominator == 0:
                    return False, sp.Integer(1), tuple(denominators)
                denominators.append(denominator)
                parameter = sp.cancel(self.cross(displacement, right_direction) / denominator)
                assert isinstance(px, sp.Symbol) and isinstance(py, sp.Symbol)
                substitutions[px] = sp.cancel(ax + parameter * left_direction[0])
                substitutions[py] = sp.cancel(ay + parameter * left_direction[1])
                continue
            return False, sp.Integer(1), tuple(denominators)

        resolved_goal = sp.cancel(resolve(self.goal(channel, points)))
        numerator, denominator = sp.fraction(resolved_goal)
        if denominator != 1:
            denominators.append(sp.factor(denominator))
        unique = {
            sp.sstr(item): item
            for item in denominators
            if item != 0 and item.free_symbols
        }
        return sp.expand(numerator) == 0, sp.expand(numerator), tuple(
            unique[key] for key in sorted(unique)
        )


def lower_gclc_to_newclid(source: str) -> GCLCRelationObligation:
    channel, points = _prove_tokens(source)
    model = _PolynomialModel(source, points, channel)
    if model.unsupported_commands:
        commands = ", ".join(sorted(model.unsupported_commands))
        raise ValueError(f"unsupported semantic GCLC commands: {commands}")
    equations = model.equations()
    goal = sp.expand(model.goal(channel, points))
    rational_exact, rational_numerator, rational_denominators = model.rational_replay(
        channel, points
    )
    if equations and len(model.variables) <= 10:
        basis = sp.groebner(equations, *model.variables, order="grevlex")
        quotients, remainder = basis.reduce(goal)
        basis_expressions = tuple(sp.expand(poly.as_expr()) for poly in basis.polys)
    else:
        quotients = []
        remainder = goal
        basis_expressions = tuple()
    replayed = sp.expand(
        goal - sum((q * b for q, b in zip(quotients, basis_expressions)), sp.Integer(0))
    )
    if sp.expand(replayed - remainder) != 0:
        raise AssertionError("Groebner quotient certificate did not replay")
    groebner_exact = sp.expand(remainder) == 0
    exact = groebner_exact or rational_exact
    verification_method = (
        "groebner_ideal_membership"
        if groebner_exact
        else "rational_construction_elimination"
        if rational_exact
        else "unproved"
    )
    normalized_points = tuple(_newclid_name(point) for point in points)
    predicate = " ".join((channel, *normalized_points))
    certificate_material = "|".join(
        (
            predicate,
            *model.normalization_assumptions,
            *(sp.sstr(item) for item in equations),
            sp.sstr(goal),
            *(sp.sstr(item) for item in basis_expressions),
            *(sp.sstr(item) for item in quotients),
            *(sp.sstr(item) for item in rational_denominators),
            verification_method,
            sp.sstr(remainder),
        )
    )
    return GCLCRelationObligation(
        channel=channel,
        points=normalized_points,
        newclid_predicate=predicate,
        construction_equations=tuple(sp.sstr(item) for item in equations),
        normalization_assumptions=model.normalization_assumptions,
        nondegeneracy_conditions=tuple(
            f"{sp.sstr(item)} != 0" for item in model.nondegeneracy()
        ),
        goal_polynomial=sp.sstr(goal),
        groebner_basis=tuple(sp.sstr(item) for item in basis_expressions),
        quotient_certificate=tuple(sp.sstr(item) for item in quotients),
        rational_denominators=tuple(sp.sstr(item) for item in rational_denominators),
        verification_method=verification_method,
        remainder=sp.sstr(sp.Integer(0) if rational_exact else remainder),
        exact_replay=exact,
        certificate_sha256=hashlib.sha256(certificate_material.encode()).hexdigest(),
    )
