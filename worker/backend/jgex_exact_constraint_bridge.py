"""Lower a typed JGEX construction fragment to an exact polynomial certificate.

The implementation follows construction semantics rather than problem IDs.  It
eliminates deterministic geometric constructions, preserves locus parameters,
and asks Groebner reduction only about the remaining polynomial constraints.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import sympy as sp
from newclid.jgex.constructions import ALL_JGEX_CONSTRUCTIONS
from newclid.jgex.definition import JGEXDefinition
from newclid.jgex.formulation import JGEXFormulation

from worker.backend.jgex_legacy_normalizer import normalize_legacy_formulation


@dataclass(frozen=True)
class JGEXExactObligation:
    channel: str
    points: tuple[str, ...]
    construction_vocabulary: tuple[str, ...]
    normalization_assumptions: tuple[str, ...]
    construction_equations: tuple[str, ...]
    nondegeneracy_conditions: tuple[str, ...]
    goal_polynomial: str
    groebner_basis: tuple[str, ...]
    quotient_certificate: tuple[str, ...]
    remainder: str
    exact_replay: bool
    certificate_sha256: str


Point = tuple[sp.Expr, sp.Expr]

SUPPORTED_CONSTRUCTION_VOCABULARY = frozenset(
    {
        "triangle",
        "r_triangle",
        "midpoint",
        "foot",
        "orthocenter",
        "circle",
        "on_line",
        "on_circle",
        "on_tline",
        "on_pline",
        "on_dia",
        "angle_bisector",
        "incenter",
        "incenter2",
        "mirror",
        "reflect",
        "on_bline",
        "on_aline",
        "eqangle3",
    }
)


class _JGEXElaborator:
    SUPPORTED = SUPPORTED_CONSTRUCTION_VOCABULARY

    def __init__(self) -> None:
        self.coordinates: dict[str, Point] = {}
        self.variables: list[sp.Symbol] = []
        self.equations: list[sp.Expr] = []
        self.denominators: list[sp.Expr] = []
        self.normalization_assumptions: list[str] = []
        self.line_loci: dict[str, tuple[str, str]] = {}
        self.line_parameters: dict[str, sp.Symbol] = {}
        self.circle_loci: dict[
            tuple[tuple[str, str], str, str],
            list[tuple[str, sp.Symbol, sp.Expr]],
        ] = {}
        self.side_lengths: dict[tuple[str, str], sp.Symbol] = {}
        self._parameter_index = 0

    @staticmethod
    def _sub(left: Point, right: Point) -> Point:
        return left[0] - right[0], left[1] - right[1]

    @staticmethod
    def _add(left: Point, right: Point) -> Point:
        return left[0] + right[0], left[1] + right[1]

    @staticmethod
    def _scale(value: sp.Expr, point: Point) -> Point:
        return value * point[0], value * point[1]

    @staticmethod
    def _dot(left: Point, right: Point) -> sp.Expr:
        return sp.expand(left[0] * right[0] + left[1] * right[1])

    @staticmethod
    def _cross(left: Point, right: Point) -> sp.Expr:
        return sp.expand(left[0] * right[1] - left[1] * right[0])

    def _parameter(self, prefix: str) -> sp.Symbol:
        value = sp.Symbol(f"_{prefix}_{self._parameter_index}")
        self._parameter_index += 1
        self.variables.append(value)
        return value

    def _distance_squared(self, left: str, right: str) -> sp.Expr:
        delta = self._sub(self.coordinates[left], self.coordinates[right])
        return self._dot(delta, delta)

    def _free_point(self, name: str) -> Point:
        if name not in self.coordinates:
            self.coordinates[name] = (
                self._parameter("free_x"),
                self._parameter("free_y"),
            )
        return self.coordinates[name]

    def _append_equation(self, expression: sp.Expr) -> sp.Expr:
        numerator, denominator = sp.together(expression).as_numer_denom()
        denominator = sp.factor(denominator)
        if denominator != 1:
            self.denominators.append(denominator)
        polynomial = sp.factor(numerator)
        self.equations.append(polynomial)
        return polynomial

    def _side_length(self, left: str, right: str) -> sp.Symbol:
        key = tuple(sorted((left, right)))
        if key in self.side_lengths:
            return self.side_lengths[key]
        length = self._parameter("length")
        self.side_lengths[key] = length
        self._append_equation(
            length * length - self._distance_squared(left, right)
        )
        self.denominators.append(length)
        self.normalization_assumptions.append(
            f"principal_length {_safe(length)}=distance({key[0]},{key[1]})"
        )
        return length

    def _line_intersection(
        self,
        left_a: str,
        left_b: str,
        right_a: str,
        right_b: str,
    ) -> Point:
        origin = self.coordinates[left_a]
        left_direction = self._sub(self.coordinates[left_b], origin)
        right_origin = self.coordinates[right_a]
        right_direction = self._sub(self.coordinates[right_b], right_origin)
        denominator = sp.factor(self._cross(left_direction, right_direction))
        if denominator == 0:
            raise ValueError("parallel lines cannot define an intersection")
        self.denominators.append(denominator)
        parameter = sp.cancel(
            self._cross(self._sub(right_origin, origin), right_direction)
            / denominator
        )
        return tuple(
            sp.cancel(value)
            for value in self._add(origin, self._scale(parameter, left_direction))
        )  # type: ignore[return-value]

    def _directed_intersection(
        self,
        left_origin: Point,
        left_direction: Point,
        right_origin: Point,
        right_direction: Point,
    ) -> Point:
        denominator = sp.factor(self._cross(left_direction, right_direction))
        if denominator == 0:
            raise ValueError("parallel directed lines cannot define an intersection")
        self.denominators.append(denominator)
        parameter = sp.cancel(
            self._cross(self._sub(right_origin, left_origin), right_direction)
            / denominator
        )
        return tuple(
            sp.cancel(value)
            for value in self._add(left_origin, self._scale(parameter, left_direction))
        )  # type: ignore[return-value]

    def _right_triangle(self, points: tuple[str, ...]) -> None:
        if len(points) != 3:
            raise ValueError("r_triangle expects three output points")
        vertex, left, right = points
        leg_left = self._parameter("leg")
        leg_right = self._parameter("leg")
        self.coordinates[vertex] = (sp.Integer(0), sp.Integer(0))
        self.coordinates[left] = (leg_left, sp.Integer(0))
        self.coordinates[right] = (sp.Integer(0), leg_right)
        self.normalization_assumptions.extend(
            (
                f"euclidean_gauge {vertex}=(0,0) {left}=({_safe(leg_left)},0) "
                f"{right}=(0,{_safe(leg_right)})",
                f"{_safe(leg_left)} != 0",
                f"{_safe(leg_right)} != 0",
            )
        )

    def _triangle(self, points: tuple[str, ...]) -> None:
        if len(points) != 3:
            raise ValueError("triangle expects three output points")
        left, right, apex = points
        base = self._parameter("base")
        apex_x = self._parameter("apex_x")
        apex_y = self._parameter("apex_y")
        self.coordinates[left] = (sp.Integer(0), sp.Integer(0))
        self.coordinates[right] = (base, sp.Integer(0))
        self.coordinates[apex] = (apex_x, apex_y)
        self.normalization_assumptions.extend(
            (
                f"euclidean_gauge {left}=(0,0) {right}=({_safe(base)},0) "
                f"{apex}=({_safe(apex_x)},{_safe(apex_y)})",
                f"{_safe(base)} != 0",
                f"{_safe(apex_y)} != 0",
            )
        )

    def _foot(self, args: tuple[str, ...]) -> None:
        foot, point, left, right = args
        left_point = self.coordinates[left]
        direction = self._sub(self.coordinates[right], left_point)
        denominator = sp.factor(self._dot(direction, direction))
        self.denominators.append(denominator)
        parameter = sp.cancel(
            self._dot(self._sub(self.coordinates[point], left_point), direction)
            / denominator
        )
        self.coordinates[foot] = tuple(
            sp.cancel(value)
            for value in self._add(left_point, self._scale(parameter, direction))
        )  # type: ignore[assignment]

    def _midpoint(self, args: tuple[str, ...]) -> None:
        midpoint, left, right = args
        self.coordinates[midpoint] = tuple(
            sp.cancel((left_value + right_value) / 2)
            for left_value, right_value in zip(
                self.coordinates[left], self.coordinates[right], strict=True
            )
        )  # type: ignore[assignment]

    def _orthocenter(self, args: tuple[str, ...]) -> None:
        orthocenter, a, b, c = args
        bc = self._sub(self.coordinates[c], self.coordinates[b])
        ac = self._sub(self.coordinates[c], self.coordinates[a])
        altitude_a = (-bc[1], bc[0])
        altitude_b = (-ac[1], ac[0])
        self.coordinates[orthocenter] = self._directed_intersection(
            self.coordinates[a],
            altitude_a,
            self.coordinates[b],
            altitude_b,
        )

    def _circumcenter(self, args: tuple[str, ...]) -> None:
        center, a, b, c = args
        midpoint_ab = tuple(
            sp.cancel((left + right) / 2)
            for left, right in zip(
                self.coordinates[a], self.coordinates[b], strict=True
            )
        )
        midpoint_ac = tuple(
            sp.cancel((left + right) / 2)
            for left, right in zip(
                self.coordinates[a], self.coordinates[c], strict=True
            )
        )
        ab = self._sub(self.coordinates[b], self.coordinates[a])
        ac = self._sub(self.coordinates[c], self.coordinates[a])
        self.coordinates[center] = self._directed_intersection(
            midpoint_ab,  # type: ignore[arg-type]
            (-ab[1], ab[0]),
            midpoint_ac,  # type: ignore[arg-type]
            (-ac[1], ac[0]),
        )

    def _on_line(self, args: tuple[str, ...]) -> None:
        point, left, right = args
        if point not in self.coordinates:
            parameter = self._parameter("line")
            origin = self.coordinates[left]
            direction = self._sub(self.coordinates[right], origin)
            self.coordinates[point] = tuple(
                sp.expand(value)
                for value in self._add(origin, self._scale(parameter, direction))
            )  # type: ignore[assignment]
            self.line_loci[point] = tuple(sorted((left, right)))
            self.line_parameters[point] = parameter
            return
        displacement = self._sub(self.coordinates[point], self.coordinates[left])
        direction = self._sub(self.coordinates[right], self.coordinates[left])
        self._append_equation(self._cross(displacement, direction))

    def _on_parallel_line(self, args: tuple[str, ...]) -> None:
        point, origin_name, left, right = args
        origin = self.coordinates[origin_name]
        direction = self._sub(self.coordinates[right], self.coordinates[left])
        direction_norm = sp.factor(self._dot(direction, direction))
        self.denominators.append(direction_norm)
        if point not in self.coordinates:
            parameter = self._parameter("pline")
            self.coordinates[point] = tuple(
                sp.expand(value)
                for value in self._add(origin, self._scale(parameter, direction))
            )  # type: ignore[assignment]
            return
        displacement = self._sub(self.coordinates[point], origin)
        self._append_equation(self._cross(displacement, direction))

    def _on_perpendicular_line(self, args: tuple[str, ...]) -> None:
        point, origin_name, left, right = args
        origin = self.coordinates[origin_name]
        direction = self._sub(self.coordinates[right], self.coordinates[left])
        direction_norm = sp.factor(self._dot(direction, direction))
        self.denominators.append(direction_norm)
        if point not in self.coordinates:
            parameter = self._parameter("tline")
            perpendicular = (-direction[1], direction[0])
            self.coordinates[point] = tuple(
                sp.expand(value)
                for value in self._add(origin, self._scale(parameter, perpendicular))
            )  # type: ignore[assignment]
            return
        displacement = self._sub(self.coordinates[point], origin)
        self._append_equation(self._dot(displacement, direction))

    def _on_perpendicular_bisector(self, args: tuple[str, ...]) -> None:
        point, left, right = args
        direction = self._sub(self.coordinates[right], self.coordinates[left])
        direction_norm = sp.factor(self._dot(direction, direction))
        self.denominators.append(direction_norm)
        if point not in self.coordinates:
            parameter = self._parameter("bline")
            midpoint = self._scale(
                sp.Rational(1, 2),
                self._add(self.coordinates[left], self.coordinates[right]),
            )
            perpendicular = (-direction[1], direction[0])
            self.coordinates[point] = tuple(
                sp.expand(value)
                for value in self._add(
                    midpoint, self._scale(parameter, perpendicular)
                )
            )  # type: ignore[assignment]
            return
        self._append_equation(
            self._distance_squared(point, left)
            - self._distance_squared(point, right)
        )

    def _equal_angle_equation(
        self,
        ray_a: tuple[str, str],
        ray_b: tuple[str, str],
        ray_c: tuple[str, str],
        ray_d: tuple[str, str],
    ) -> sp.Expr:
        vectors = tuple(
            self._sub(self.coordinates[end], self.coordinates[start])
            for start, end in (ray_a, ray_b, ray_c, ray_d)
        )
        for vector in vectors:
            self.denominators.append(sp.factor(self._dot(vector, vector)))
        left_cross = self._cross(vectors[0], vectors[1])
        left_dot = self._dot(vectors[0], vectors[1])
        right_cross = self._cross(vectors[2], vectors[3])
        right_dot = self._dot(vectors[2], vectors[3])
        return self._append_equation(
            sp.expand(left_cross * right_dot - left_dot * right_cross)
        )

    def _on_angle_line(self, args: tuple[str, ...]) -> None:
        point, a, b, c, d, e = args
        self._free_point(point)
        self._equal_angle_equation(
            (a, point),
            (a, b),
            (d, c),
            (d, e),
        )

    def _equal_angle_locus(self, args: tuple[str, ...]) -> None:
        point, a, b, d, e, f = args
        self._free_point(point)
        self._equal_angle_equation(
            (point, a),
            (point, b),
            (d, e),
            (d, f),
        )

    def _mirror(self, args: tuple[str, ...]) -> None:
        point, source, center = args
        self.coordinates[point] = tuple(
            sp.expand(2 * center_value - source_value)
            for source_value, center_value in zip(
                self.coordinates[source], self.coordinates[center], strict=True
            )
        )  # type: ignore[assignment]

    def _reflect(self, args: tuple[str, ...]) -> None:
        point, source, left, right = args
        origin = self.coordinates[left]
        direction = self._sub(self.coordinates[right], origin)
        denominator = sp.factor(self._dot(direction, direction))
        self.denominators.append(denominator)
        parameter = sp.cancel(
            self._dot(self._sub(self.coordinates[source], origin), direction)
            / denominator
        )
        projection = self._add(origin, self._scale(parameter, direction))
        self.coordinates[point] = tuple(
            sp.cancel(2 * projected - source_value)
            for projected, source_value in zip(
                projection, self.coordinates[source], strict=True
            )
        )  # type: ignore[assignment]

    def _on_diameter_circle(self, args: tuple[str, ...]) -> None:
        point, left, right = args
        if point not in self.coordinates:
            parameter = self._parameter("diameter")
            direction = self._sub(
                self.coordinates[right], self.coordinates[left]
            )
            perpendicular = (-direction[1], direction[0])
            denominator = sp.factor(1 + parameter * parameter)
            offset = self._scale(
                1 / denominator,
                self._add(direction, self._scale(parameter, perpendicular)),
            )
            self.coordinates[point] = tuple(
                sp.cancel(value)
                for value in self._add(self.coordinates[left], offset)
            )  # type: ignore[assignment]
            self.denominators.extend(
                (denominator, self._distance_squared(left, right))
            )
            self.normalization_assumptions.append(f"diff {point} {left}")
            return
        left_ray = self._sub(self.coordinates[point], self.coordinates[left])
        right_ray = self._sub(self.coordinates[point], self.coordinates[right])
        self._append_equation(self._dot(left_ray, right_ray))
        self.denominators.append(self._distance_squared(left, right))

    def _angle_bisector(self, args: tuple[str, ...]) -> None:
        point, left, vertex, right = args
        left_length = self._side_length(vertex, left)
        right_length = self._side_length(vertex, right)
        left_ray = self._sub(self.coordinates[left], self.coordinates[vertex])
        right_ray = self._sub(self.coordinates[right], self.coordinates[vertex])
        direction = self._add(
            self._scale(right_length, left_ray),
            self._scale(left_length, right_ray),
        )
        direction_norm = sp.factor(self._dot(direction, direction))
        self.denominators.append(direction_norm)
        if point not in self.coordinates:
            parameter = self._parameter("bisector")
            self.coordinates[point] = tuple(
                sp.expand(value)
                for value in self._add(
                    self.coordinates[vertex], self._scale(parameter, direction)
                )
            )  # type: ignore[assignment]
            return
        displacement = self._sub(
            self.coordinates[point], self.coordinates[vertex]
        )
        self._append_equation(self._cross(displacement, direction))

    def _incenter(self, args: tuple[str, ...]) -> None:
        center, a, b, c = args
        side_a = self._side_length(b, c)
        side_b = self._side_length(c, a)
        side_c = self._side_length(a, b)
        denominator = sp.factor(side_a + side_b + side_c)
        self.denominators.append(denominator)
        weighted = self._add(
            self._add(
                self._scale(side_a, self.coordinates[a]),
                self._scale(side_b, self.coordinates[b]),
            ),
            self._scale(side_c, self.coordinates[c]),
        )
        self.coordinates[center] = tuple(
            sp.cancel(value / denominator) for value in weighted
        )  # type: ignore[assignment]

    def _incenter_with_feet(self, args: tuple[str, ...]) -> None:
        foot_a, foot_b, foot_c, center, a, b, c = args
        self._incenter((center, a, b, c))
        self._foot((foot_a, center, b, c))
        self._foot((foot_b, center, c, a))
        self._foot((foot_c, center, a, b))

    def _on_circle(self, args: tuple[str, ...]) -> None:
        point, center, radius_point = args
        if point not in self.coordinates:
            self.coordinates[point] = (
                self._parameter("free_x"),
                self._parameter("free_y"),
            )
        equation = self._distance_squared(center, point) - self._distance_squared(
            center, radius_point
        )
        numerator = self._append_equation(equation)
        if point in self.line_loci and point in self.line_parameters:
            signature = (self.line_loci[point], center, radius_point)
            self.circle_loci.setdefault(signature, []).append(
                (point, self.line_parameters[point], sp.factor(numerator))
            )

    def close_distinct_locus_roots(self) -> None:
        for roots in self.circle_loci.values():
            for index, (left_name, left_parameter, left_equation) in enumerate(roots):
                for right_name, right_parameter, right_equation in roots[index + 1 :]:
                    difference = sp.expand(left_equation - right_equation)
                    divisor = left_parameter - right_parameter
                    quotient, remainder = sp.div(difference, divisor)
                    if sp.expand(remainder) != 0:
                        continue
                    self._append_equation(quotient)
                    self.denominators.append(divisor)
                    self.normalization_assumptions.append(
                        f"diff {left_name} {right_name}"
                    )

    def elaborate_clause(self, clause) -> tuple[str, ...]:
        constructions = tuple(clause.constructions)
        names = tuple(construction.name for construction in constructions)
        unsupported = set(names) - self.SUPPORTED
        if unsupported:
            raise ValueError(
                "unsupported JGEX constructions: " + ", ".join(sorted(unsupported))
            )

        if len(constructions) == 1 and constructions[0].name in {
            "triangle",
            "r_triangle",
        }:
            points = tuple(str(arg) for arg in constructions[0].args)
            if constructions[0].name == "triangle":
                self._triangle(points)
            else:
                self._right_triangle(points)
            return names

        if len(constructions) == 1 and constructions[0].name == "foot":
            self._foot(tuple(str(arg) for arg in constructions[0].args))
            return names

        if len(constructions) == 1 and constructions[0].name in {
            "midpoint",
            "orthocenter",
            "circle",
            "incenter",
            "incenter2",
        }:
            arguments = tuple(str(arg) for arg in constructions[0].args)
            if constructions[0].name == "midpoint":
                self._midpoint(arguments)
            elif constructions[0].name == "orthocenter":
                self._orthocenter(arguments)
            elif constructions[0].name == "circle":
                self._circumcenter(arguments)
            elif constructions[0].name == "incenter":
                self._incenter(arguments)
            else:
                self._incenter_with_feet(arguments)
            return names

        line_constructions = [
            construction for construction in constructions if construction.name == "on_line"
        ]
        if len(line_constructions) == 2:
            left_args = tuple(str(arg) for arg in line_constructions[0].args)
            right_args = tuple(str(arg) for arg in line_constructions[1].args)
            if left_args[0] != right_args[0]:
                raise ValueError("line intersection clause has two output points")
            self.coordinates[left_args[0]] = self._line_intersection(
                left_args[1], left_args[2], right_args[1], right_args[2]
            )
            for construction in constructions:
                if construction.name != "on_line":
                    self._dispatch(construction.name, tuple(str(arg) for arg in construction.args))
            return names

        ordered_constructions = tuple(line_constructions) + tuple(
            construction
            for construction in constructions
            if construction.name != "on_line"
        )
        for construction in ordered_constructions:
            self._dispatch(
                construction.name,
                tuple(str(arg) for arg in construction.args),
            )
        return names

    def _dispatch(self, name: str, args: tuple[str, ...]) -> None:
        if name == "on_line":
            self._on_line(args)
        elif name == "on_circle":
            self._on_circle(args)
        elif name == "on_pline":
            self._on_parallel_line(args)
        elif name == "on_tline":
            self._on_perpendicular_line(args)
        elif name == "on_dia":
            self._on_diameter_circle(args)
        elif name == "angle_bisector":
            self._angle_bisector(args)
        elif name == "on_bline":
            self._on_perpendicular_bisector(args)
        elif name == "on_aline":
            self._on_angle_line(args)
        elif name == "eqangle3":
            self._equal_angle_locus(args)
        elif name == "mirror":
            self._mirror(args)
        elif name == "reflect":
            self._reflect(args)
        else:
            raise ValueError(f"unsupported clause dispatch: {name}")

    def goal(self, channel: str, points: tuple[str, ...]) -> sp.Expr:
        if channel == "cong" and len(points) == 4:
            left_a, left_b, right_a, right_b = points
            expression = self._distance_squared(
                left_a, left_b
            ) - self._distance_squared(right_a, right_b)
        elif channel in {"coll", "para", "perp"}:
            if channel == "coll" and len(points) == 3:
                a, b, c = points
                expression = self._cross(
                    self._sub(self.coordinates[b], self.coordinates[a]),
                    self._sub(self.coordinates[c], self.coordinates[a]),
                )
            elif channel in {"para", "perp"} and len(points) == 4:
                a, b, c, d = points
                left = self._sub(self.coordinates[b], self.coordinates[a])
                right = self._sub(self.coordinates[d], self.coordinates[c])
                expression = (
                    self._cross(left, right)
                    if channel == "para"
                    else self._dot(left, right)
                )
            else:
                raise ValueError(f"unsupported JGEX goal: {channel} {points}")
        elif channel == "cyclic" and len(points) >= 4:
            determinants = []
            for point in points[3:]:
                rows = []
                for selected in (*points[:3], point):
                    x, y = self.coordinates[selected]
                    rows.append((x * x + y * y, x, y, sp.Integer(1)))
                determinants.append(sp.det(sp.Matrix(rows)))
            expression = sum(
                (determinant * determinant for determinant in determinants),
                sp.Integer(0),
            )
        else:
            raise ValueError(f"unsupported JGEX goal: {channel} {points}")
        numerator, denominator = sp.together(expression).as_numer_denom()
        if denominator != 1:
            self.denominators.append(sp.factor(denominator))
        return sp.factor(numerator)


def _safe(value: sp.Expr) -> str:
    return sp.sstr(value)


def lower_jgex_to_exact_obligation(text: str) -> JGEXExactObligation:
    definitions = JGEXDefinition.to_dict(list(ALL_JGEX_CONSTRUCTIONS))
    formulation = JGEXFormulation.from_text(text)
    formulation, report = normalize_legacy_formulation(formulation, definitions)
    if report.unresolved_constructions:
        raise ValueError("JGEX normalization left unresolved constructions")
    if len(formulation.goals) != 1:
        raise ValueError("exact bridge currently requires one goal")

    elaborator = _JGEXElaborator()
    vocabulary: list[str] = []
    for clause in formulation.setup_clauses:
        vocabulary.extend(elaborator.elaborate_clause(clause))

    elaborator.close_distinct_locus_roots()

    goal = formulation.goals[0]
    channel = goal.predicate_type.value
    points = tuple(str(arg) for arg in goal.args)
    goal_polynomial = elaborator.goal(channel, points)
    equations = tuple(sp.expand(equation) for equation in elaborator.equations)
    variables = tuple(reversed(elaborator.variables))
    if sp.expand(goal_polynomial) == 0:
        quotients: list[sp.Expr] = []
        remainder = sp.Integer(0)
        basis_expressions: tuple[sp.Expr, ...] = tuple()
    elif not equations:
        quotients = []
        remainder = sp.expand(goal_polynomial)
        basis_expressions = tuple()
    else:
        if not variables:
            raise ValueError("exact bridge requires elimination variables")
        basis = sp.groebner(equations, *variables, order="grevlex")
        quotients, remainder = basis.reduce(goal_polynomial)
        basis_expressions = tuple(sp.expand(poly.as_expr()) for poly in basis.polys)
    replayed = sp.expand(
        goal_polynomial
        - sum((quotient * item for quotient, item in zip(quotients, basis_expressions)), sp.Integer(0))
    )
    if sp.expand(replayed - remainder) != 0:
        raise AssertionError("JGEX Groebner certificate did not replay")

    denominators = {
        _safe(item): item
        for item in elaborator.denominators
        if item != 0 and item.free_symbols
    }
    certificate_material = "|".join(
        (
            channel,
            *points,
            *vocabulary,
            *elaborator.normalization_assumptions,
            *(_safe(item) for item in equations),
            *denominators,
            _safe(goal_polynomial),
            *(_safe(item) for item in basis_expressions),
            *(_safe(item) for item in quotients),
            _safe(remainder),
        )
    )
    return JGEXExactObligation(
        channel=channel,
        points=points,
        construction_vocabulary=tuple(sorted(set(vocabulary))),
        normalization_assumptions=tuple(elaborator.normalization_assumptions),
        construction_equations=tuple(_safe(item) for item in equations),
        nondegeneracy_conditions=tuple(f"{key} != 0" for key in sorted(denominators)),
        goal_polynomial=_safe(goal_polynomial),
        groebner_basis=tuple(_safe(item) for item in basis_expressions),
        quotient_certificate=tuple(_safe(item) for item in quotients),
        remainder=_safe(remainder),
        exact_replay=sp.expand(remainder) == 0,
        certificate_sha256=hashlib.sha256(certificate_material.encode()).hexdigest(),
    )
