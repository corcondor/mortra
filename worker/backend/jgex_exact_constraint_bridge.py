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
from worker.backend.jgex_gclc_translator import (
    ExternalHomothetyMacro,
    external_homothety_macros,
)
from worker.backend.geometry_local_lemma_certificate import (
    external_homothety_tangent_certificate,
)
from worker.backend.local_polynomial_elimination import (
    LocalEliminationResult,
    eliminate_local_linear_variables,
)


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
    local_lemma_certificates: tuple["AffineLocalLemmaCertificate", ...] = ()
    structural_lemma_certificates: tuple["StructuralLocalLemmaCertificate", ...] = ()
    construction_blocks: tuple["ConstructionEquationBlock", ...] = ()


@dataclass(frozen=True)
class AffineLocalLemmaCertificate:
    """A replayable localization step produced inside one construction clause."""

    clause_index: int
    construction_vocabulary: tuple[str, ...]
    variable: str
    defining_equation: str
    coefficient: str
    constant_term: str
    replacement: str
    nonzero_condition: str
    forward_residual: str
    reverse_residual: str
    replayed: bool


@dataclass(frozen=True)
class ConstructionEquationBlock:
    """The typed boundary of one elaborated JGEX construction clause."""

    clause_index: int
    outputs: tuple[str, ...]
    inputs: tuple[str, ...]
    construction_vocabulary: tuple[str, ...]
    introduced_variables: tuple[str, ...]
    surviving_equations: tuple[str, ...]
    local_lemma_count: int


@dataclass(frozen=True)
class StructuralLocalLemmaCertificate:
    """A typed construction-composition lemma with an exact coordinate replay."""

    theorem: str
    source_clause_indices: tuple[int, ...]
    inputs: tuple[str, ...]
    output: str
    hidden_points: tuple[str, ...]
    boundary_equations: tuple[str, ...]
    replay_residuals: tuple[str, ...]
    nonzero_conditions: tuple[str, ...]
    semantic_assumption: str
    composition_certificate_sha256: str
    composition_replayed: bool
    replayed: bool


@dataclass(frozen=True)
class JGEXExactSystemAnalysis:
    """Pre-Groebner structural metrics for a typed polynomial obligation."""

    channel: str
    points: tuple[str, ...]
    construction_vocabulary: tuple[str, ...]
    variables: tuple[str, ...]
    construction_equations: tuple[str, ...]
    goal_polynomial: str
    equation_count: int
    variable_count: int
    total_expanded_terms: int
    maximum_expanded_terms: int
    local_lemma_certificates: tuple[AffineLocalLemmaCertificate, ...]
    structural_lemma_certificates: tuple[StructuralLocalLemmaCertificate, ...]
    construction_blocks: tuple[ConstructionEquationBlock, ...]


@dataclass(frozen=True)
class JGEXLocalEliminationAnalysis:
    channel: str
    points: tuple[str, ...]
    goal_polynomial: str
    initial_variable_count: int
    initial_equation_count: int
    initial_total_expanded_terms: int
    initial_maximum_expanded_terms: int
    protected_variables: tuple[str, ...]
    reduced_variable_count: int
    reduced_equation_count: int
    reduced_total_expanded_terms: int
    reduced_maximum_expanded_terms: int
    local_elimination: LocalEliminationResult
    structural_lemma_certificates: tuple[StructuralLocalLemmaCertificate, ...]
    all_local_certificates_replayed: bool


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
        "cc_tangent",
    }
)


class _JGEXElaborator:
    SUPPORTED = SUPPORTED_CONSTRUCTION_VOCABULARY

    def __init__(self, *, enable_affine_local_lemmas: bool = False) -> None:
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
        self.local_lemma_certificates: list[AffineLocalLemmaCertificate] = []
        self.structural_lemma_certificates: list[StructuralLocalLemmaCertificate] = []
        self.construction_blocks: list[ConstructionEquationBlock] = []
        self._parameter_index = 0
        self._clause_index = 0
        self.enable_affine_local_lemmas = enable_affine_local_lemmas

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
        self._append_equation(length * length - self._distance_squared(left, right))
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
            self._cross(self._sub(right_origin, origin), right_direction) / denominator
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
                for value in self._add(midpoint, self._scale(parameter, perpendicular))
            )  # type: ignore[assignment]
            return
        self._append_equation(
            self._distance_squared(point, left) - self._distance_squared(point, right)
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

    def _circle_circle_tangent(self, args: tuple[str, ...]) -> None:
        first, second, third, fourth, center_a, radius_a, center_b, radius_b = args
        for point in (first, second, third, fourth):
            self._free_point(point)
        for point_a, point_b in ((first, second), (third, fourth)):
            self._append_equation(
                self._distance_squared(center_a, point_a)
                - self._distance_squared(center_a, radius_a)
            )
            self._append_equation(
                self._distance_squared(center_b, point_b)
                - self._distance_squared(center_b, radius_b)
            )
            tangent = self._sub(self.coordinates[point_b], self.coordinates[point_a])
            self._append_equation(
                self._dot(
                    self._sub(self.coordinates[center_a], self.coordinates[point_a]),
                    tangent,
                )
            )
            self._append_equation(
                self._dot(
                    self._sub(self.coordinates[center_b], self.coordinates[point_b]),
                    tangent,
                )
            )

    def elaborate_external_homothety_macro(
        self,
        macro: ExternalHomothetyMacro,
    ) -> tuple[str, ...]:
        """Replace external tangent contact points by their boundary center."""

        equation_start = len(self.equations)
        variable_start = len(self.variables)
        radius_a = self._side_length(macro.center_a, macro.radius_a)
        radius_b = self._side_length(macro.center_b, macro.radius_b)
        denominator = sp.factor(radius_a - radius_b)
        self.denominators.append(denominator)
        center_a = self.coordinates[macro.center_a]
        center_b = self.coordinates[macro.center_b]
        numerator = self._sub(
            self._scale(radius_a, center_b),
            self._scale(radius_b, center_a),
        )
        self.coordinates[macro.output] = tuple(
            sp.cancel(value / denominator) for value in numerator
        )  # type: ignore[assignment]
        boundary_equations = tuple(
            sp.factor(denominator * coordinate - radius_a * target + radius_b * source)
            for coordinate, target, source in zip(
                self.coordinates[macro.output], center_b, center_a, strict=True
            )
        )
        replayed = all(sp.cancel(item) == 0 for item in boundary_equations)
        composition_certificate = external_homothety_tangent_certificate()
        self.normalization_assumptions.append(
            "external_homothety_semantics "
            f"{macro.center_a} {macro.radius_a} "
            f"{macro.center_b} {macro.radius_b} -> {macro.output}"
        )
        self.structural_lemma_certificates.append(
            StructuralLocalLemmaCertificate(
                theorem="external_common_tangents_intersect_at_external_homothety_center",
                source_clause_indices=(
                    macro.tangent_clause_index,
                    macro.intersection_clause_index,
                ),
                inputs=(
                    macro.center_a,
                    macro.radius_a,
                    macro.center_b,
                    macro.radius_b,
                ),
                output=macro.output,
                hidden_points=macro.hidden_tangent_points,
                boundary_equations=(
                    f"(rA-rB)*{macro.output}.x-rA*{macro.center_b}.x+"
                    f"rB*{macro.center_a}.x=0",
                    f"(rA-rB)*{macro.output}.y-rA*{macro.center_b}.y+"
                    f"rB*{macro.center_a}.y=0",
                ),
                replay_residuals=tuple(_safe(item) for item in boundary_equations),
                nonzero_conditions=(f"{_safe(denominator)} != 0",),
                semantic_assumption=(
                    "JGEX cc_tangent denotes the two external common tangents, "
                    "as specified by sketch_cc_tangent"
                ),
                composition_certificate_sha256=(
                    composition_certificate.certificate_sha256
                ),
                composition_replayed=composition_certificate.replayed,
                replayed=replayed,
            )
        )
        introduced_variables = tuple(self.variables[variable_start:])
        self.construction_blocks.append(
            ConstructionEquationBlock(
                clause_index=macro.tangent_clause_index,
                outputs=(macro.output,),
                inputs=(
                    macro.center_a,
                    macro.radius_a,
                    macro.center_b,
                    macro.radius_b,
                ),
                construction_vocabulary=("cc_tangent", "on_line"),
                introduced_variables=tuple(
                    _safe(item) for item in introduced_variables
                ),
                surviving_equations=tuple(
                    _safe(item) for item in self.equations[equation_start:]
                ),
                local_lemma_count=1,
            )
        )
        return "cc_tangent", "on_line"

    def _on_diameter_circle(self, args: tuple[str, ...]) -> None:
        point, left, right = args
        if point not in self.coordinates:
            parameter = self._parameter("diameter")
            direction = self._sub(self.coordinates[right], self.coordinates[left])
            perpendicular = (-direction[1], direction[0])
            denominator = sp.factor(1 + parameter * parameter)
            offset = self._scale(
                1 / denominator,
                self._add(direction, self._scale(parameter, perpendicular)),
            )
            self.coordinates[point] = tuple(
                sp.cancel(value) for value in self._add(self.coordinates[left], offset)
            )  # type: ignore[assignment]
            self.denominators.extend((denominator, self._distance_squared(left, right)))
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
        displacement = self._sub(self.coordinates[point], self.coordinates[vertex])
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

    def _elaborate_clause_raw(self, clause) -> tuple[str, ...]:
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
            construction
            for construction in constructions
            if construction.name == "on_line"
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
                    self._dispatch(
                        construction.name, tuple(str(arg) for arg in construction.args)
                    )
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

    @staticmethod
    def _point_arguments(clause) -> tuple[str, ...]:
        outputs = {str(point) for point in clause.points}
        arguments = {
            str(argument)
            for construction in clause.constructions
            for argument in construction.args
            if str(argument) and str(argument)[0].isalpha()
        }
        return tuple(sorted(arguments - outputs))

    def _substitute_coordinates(
        self, variable: sp.Symbol, replacement: sp.Expr
    ) -> None:
        for point, coordinates in tuple(self.coordinates.items()):
            if any(variable in coordinate.free_symbols for coordinate in coordinates):
                self.coordinates[point] = tuple(
                    sp.cancel(coordinate.subs(variable, replacement))
                    for coordinate in coordinates
                )  # type: ignore[assignment]

    def _compress_affine_clause(
        self,
        *,
        clause_index: int,
        vocabulary: tuple[str, ...],
        equation_start: int,
        introduced_variables: tuple[sp.Symbol, ...],
    ) -> None:
        """Eliminate clause-local affine variables and retain replayable lemmas.

        The transformation is valid in the localization where the affine
        coefficient is nonzero.  That coefficient is therefore exported as a
        nondegeneracy condition rather than silently divided away.
        """

        candidates = [
            variable
            for variable in introduced_variables
            if not variable.name.startswith("_length_")
        ]
        while candidates:
            best: tuple[int, int, sp.Symbol, int, sp.Expr, sp.Expr] | None = None
            for equation_index in range(equation_start, len(self.equations)):
                equation = sp.expand(self.equations[equation_index])
                for variable in candidates:
                    try:
                        polynomial = sp.Poly(equation, variable)
                    except sp.PolynomialError:
                        continue
                    if polynomial.degree() != 1:
                        continue
                    coefficient = sp.factor(polynomial.coeff_monomial(variable))
                    constant = sp.factor(polynomial.coeff_monomial(1))
                    if variable in coefficient.free_symbols or coefficient == 0:
                        continue
                    replacement = sp.cancel(-constant / coefficient)
                    complexity = int(sp.count_ops(replacement))
                    if complexity > 2_000:
                        continue
                    rank = (complexity, int(sp.count_ops(equation)))
                    candidate = (*rank, variable, equation_index, coefficient, constant)
                    if best is None or candidate[:2] < best[:2]:
                        best = candidate
            if best is None:
                break

            _, _, variable, equation_index, coefficient, constant = best
            defining_equation = sp.expand(self.equations[equation_index])
            replacement = sp.cancel(-constant / coefficient)
            forward_residual = sp.cancel(defining_equation.subs(variable, replacement))
            reverse_residual = sp.cancel(
                coefficient * (variable - replacement) - defining_equation
            )
            replayed = forward_residual == 0 and reverse_residual == 0
            if not replayed:
                candidates.remove(variable)
                continue

            self.denominators.append(coefficient)
            self.normalization_assumptions.append(
                f"local_affine {_safe(coefficient)} != 0"
            )
            self.local_lemma_certificates.append(
                AffineLocalLemmaCertificate(
                    clause_index=clause_index,
                    construction_vocabulary=tuple(sorted(set(vocabulary))),
                    variable=_safe(variable),
                    defining_equation=_safe(defining_equation),
                    coefficient=_safe(coefficient),
                    constant_term=_safe(constant),
                    replacement=_safe(replacement),
                    nonzero_condition=f"{_safe(coefficient)} != 0",
                    forward_residual=_safe(forward_residual),
                    reverse_residual=_safe(reverse_residual),
                    replayed=True,
                )
            )
            self._substitute_coordinates(variable, replacement)
            del self.equations[equation_index]
            for index in range(equation_start, len(self.equations)):
                self.equations[index] = sp.factor(
                    sp.together(
                        self.equations[index].subs(variable, replacement)
                    ).as_numer_denom()[0]
                )
            if variable in self.variables:
                self.variables.remove(variable)
            candidates.remove(variable)

    def elaborate_clause(self, clause) -> tuple[str, ...]:
        clause_index = self._clause_index
        self._clause_index += 1
        equation_start = len(self.equations)
        variable_start = len(self.variables)
        lemma_start = len(self.local_lemma_certificates)
        names = self._elaborate_clause_raw(clause)
        introduced_variables = tuple(self.variables[variable_start:])
        if self.enable_affine_local_lemmas:
            self._compress_affine_clause(
                clause_index=clause_index,
                vocabulary=names,
                equation_start=equation_start,
                introduced_variables=introduced_variables,
            )
        surviving_variables = tuple(
            variable for variable in introduced_variables if variable in self.variables
        )
        self.construction_blocks.append(
            ConstructionEquationBlock(
                clause_index=clause_index,
                outputs=tuple(str(point) for point in clause.points),
                inputs=self._point_arguments(clause),
                construction_vocabulary=tuple(sorted(set(names))),
                introduced_variables=tuple(_safe(item) for item in surviving_variables),
                surviving_equations=tuple(
                    _safe(item) for item in self.equations[equation_start:]
                ),
                local_lemma_count=(len(self.local_lemma_certificates) - lemma_start),
            )
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
        elif name == "cc_tangent":
            self._circle_circle_tangent(args)
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


class _RelationalJGEXElaborator(_JGEXElaborator):
    """Keep constructed points existential and export low-degree relations.

    Explicit coordinate substitution is useful for short construction chains,
    but duplicates every upstream expression at every downstream use.  This
    elaborator uses the same construction semantics while retaining the output
    coordinates as local variables constrained by small polynomial blocks.
    """

    def _foot(self, args: tuple[str, ...]) -> None:
        foot, point, left, right = args
        self._free_point(foot)
        direction = self._sub(self.coordinates[right], self.coordinates[left])
        self._append_equation(
            self._cross(
                self._sub(self.coordinates[foot], self.coordinates[left]),
                direction,
            )
        )
        self._append_equation(
            self._dot(
                self._sub(self.coordinates[foot], self.coordinates[point]),
                direction,
            )
        )
        self.denominators.append(sp.factor(self._dot(direction, direction)))

    def _midpoint(self, args: tuple[str, ...]) -> None:
        midpoint, left, right = args
        self._free_point(midpoint)
        for coordinate, left_value, right_value in zip(
            self.coordinates[midpoint],
            self.coordinates[left],
            self.coordinates[right],
            strict=True,
        ):
            self._append_equation(2 * coordinate - left_value - right_value)

    def _orthocenter(self, args: tuple[str, ...]) -> None:
        orthocenter, a, b, c = args
        self._free_point(orthocenter)
        self._append_equation(
            self._dot(
                self._sub(self.coordinates[orthocenter], self.coordinates[a]),
                self._sub(self.coordinates[c], self.coordinates[b]),
            )
        )
        self._append_equation(
            self._dot(
                self._sub(self.coordinates[orthocenter], self.coordinates[b]),
                self._sub(self.coordinates[c], self.coordinates[a]),
            )
        )

    def _circumcenter(self, args: tuple[str, ...]) -> None:
        center, a, b, c = args
        self._free_point(center)
        self._append_equation(
            self._distance_squared(center, a) - self._distance_squared(center, b)
        )
        self._append_equation(
            self._distance_squared(center, a) - self._distance_squared(center, c)
        )

    def _on_line(self, args: tuple[str, ...]) -> None:
        point, left, right = args
        self._free_point(point)
        self._append_equation(
            self._cross(
                self._sub(self.coordinates[point], self.coordinates[left]),
                self._sub(self.coordinates[right], self.coordinates[left]),
            )
        )

    def _on_parallel_line(self, args: tuple[str, ...]) -> None:
        point, origin, left, right = args
        self._free_point(point)
        direction = self._sub(self.coordinates[right], self.coordinates[left])
        self._append_equation(
            self._cross(
                self._sub(self.coordinates[point], self.coordinates[origin]),
                direction,
            )
        )
        self.denominators.append(sp.factor(self._dot(direction, direction)))

    def _on_perpendicular_line(self, args: tuple[str, ...]) -> None:
        point, origin, left, right = args
        self._free_point(point)
        direction = self._sub(self.coordinates[right], self.coordinates[left])
        self._append_equation(
            self._dot(
                self._sub(self.coordinates[point], self.coordinates[origin]),
                direction,
            )
        )
        self.denominators.append(sp.factor(self._dot(direction, direction)))

    def _on_perpendicular_bisector(self, args: tuple[str, ...]) -> None:
        point, left, right = args
        self._free_point(point)
        self._append_equation(
            self._distance_squared(point, left) - self._distance_squared(point, right)
        )
        self.denominators.append(self._distance_squared(left, right))

    def _mirror(self, args: tuple[str, ...]) -> None:
        point, source, center = args
        self._free_point(point)
        for point_value, source_value, center_value in zip(
            self.coordinates[point],
            self.coordinates[source],
            self.coordinates[center],
            strict=True,
        ):
            self._append_equation(point_value + source_value - 2 * center_value)

    def _reflect(self, args: tuple[str, ...]) -> None:
        point, source, left, right = args
        self._free_point(point)
        direction = self._sub(self.coordinates[right], self.coordinates[left])
        midpoint_twice = self._sub(
            self._add(self.coordinates[point], self.coordinates[source]),
            self._scale(2, self.coordinates[left]),
        )
        self._append_equation(self._cross(midpoint_twice, direction))
        self._append_equation(
            self._dot(
                self._sub(self.coordinates[point], self.coordinates[source]),
                direction,
            )
        )
        self.denominators.append(sp.factor(self._dot(direction, direction)))

    def _on_diameter_circle(self, args: tuple[str, ...]) -> None:
        point, left, right = args
        self._free_point(point)
        self._append_equation(
            self._dot(
                self._sub(self.coordinates[point], self.coordinates[left]),
                self._sub(self.coordinates[point], self.coordinates[right]),
            )
        )
        self.denominators.append(self._distance_squared(left, right))

    def _angle_bisector(self, args: tuple[str, ...]) -> None:
        point, left, vertex, right = args
        self._free_point(point)
        left_length = self._side_length(vertex, left)
        right_length = self._side_length(vertex, right)
        direction = self._add(
            self._scale(
                right_length,
                self._sub(self.coordinates[left], self.coordinates[vertex]),
            ),
            self._scale(
                left_length,
                self._sub(self.coordinates[right], self.coordinates[vertex]),
            ),
        )
        self._append_equation(
            self._cross(
                self._sub(self.coordinates[point], self.coordinates[vertex]),
                direction,
            )
        )
        self.denominators.append(sp.factor(self._dot(direction, direction)))

    def _incenter(self, args: tuple[str, ...]) -> None:
        center, a, b, c = args
        self._free_point(center)
        side_a = self._side_length(b, c)
        side_b = self._side_length(c, a)
        side_c = self._side_length(a, b)
        denominator = sp.factor(side_a + side_b + side_c)
        self.denominators.append(denominator)
        for center_value, a_value, b_value, c_value in zip(
            self.coordinates[center],
            self.coordinates[a],
            self.coordinates[b],
            self.coordinates[c],
            strict=True,
        ):
            self._append_equation(
                denominator * center_value
                - side_a * a_value
                - side_b * b_value
                - side_c * c_value
            )

    def _elaborate_clause_raw(self, clause) -> tuple[str, ...]:
        constructions = tuple(clause.constructions)
        line_constructions = tuple(
            item for item in constructions if item.name == "on_line"
        )
        if len(line_constructions) != 2:
            return super()._elaborate_clause_raw(clause)
        names = tuple(item.name for item in constructions)
        unsupported = set(names) - self.SUPPORTED
        if unsupported:
            raise ValueError(
                "unsupported JGEX constructions: " + ", ".join(sorted(unsupported))
            )
        ordered = line_constructions + tuple(
            item for item in constructions if item.name != "on_line"
        )
        for construction in ordered:
            self._dispatch(
                construction.name,
                tuple(str(argument) for argument in construction.args),
            )
        return names

    def elaborate_external_homothety_macro(
        self,
        macro: ExternalHomothetyMacro,
    ) -> tuple[str, ...]:
        equation_start = len(self.equations)
        variable_start = len(self.variables)
        radius_a = self._side_length(macro.center_a, macro.radius_a)
        radius_b = self._side_length(macro.center_b, macro.radius_b)
        denominator = sp.factor(radius_a - radius_b)
        self.denominators.append(denominator)
        self._free_point(macro.output)
        boundary_equations = tuple(
            self._append_equation(
                denominator * coordinate - radius_a * target + radius_b * source
            )
            for coordinate, target, source in zip(
                self.coordinates[macro.output],
                self.coordinates[macro.center_b],
                self.coordinates[macro.center_a],
                strict=True,
            )
        )
        composition_certificate = external_homothety_tangent_certificate()
        self.normalization_assumptions.append(
            "external_homothety_semantics "
            f"{macro.center_a} {macro.radius_a} "
            f"{macro.center_b} {macro.radius_b} -> {macro.output}"
        )
        self.structural_lemma_certificates.append(
            StructuralLocalLemmaCertificate(
                theorem="external_common_tangents_intersect_at_external_homothety_center",
                source_clause_indices=(
                    macro.tangent_clause_index,
                    macro.intersection_clause_index,
                ),
                inputs=(
                    macro.center_a,
                    macro.radius_a,
                    macro.center_b,
                    macro.radius_b,
                ),
                output=macro.output,
                hidden_points=macro.hidden_tangent_points,
                boundary_equations=tuple(_safe(item) for item in boundary_equations),
                replay_residuals=("0", "0"),
                nonzero_conditions=(f"{_safe(denominator)} != 0",),
                semantic_assumption=(
                    "JGEX cc_tangent denotes the two external common tangents, "
                    "as specified by sketch_cc_tangent"
                ),
                composition_certificate_sha256=(
                    composition_certificate.certificate_sha256
                ),
                composition_replayed=composition_certificate.replayed,
                replayed=composition_certificate.replayed,
            )
        )
        introduced_variables = tuple(self.variables[variable_start:])
        self.construction_blocks.append(
            ConstructionEquationBlock(
                clause_index=macro.tangent_clause_index,
                outputs=(macro.output,),
                inputs=(
                    macro.center_a,
                    macro.radius_a,
                    macro.center_b,
                    macro.radius_b,
                ),
                construction_vocabulary=("cc_tangent", "on_line"),
                introduced_variables=tuple(
                    _safe(item) for item in introduced_variables
                ),
                surviving_equations=tuple(
                    _safe(item) for item in self.equations[equation_start:]
                ),
                local_lemma_count=1,
            )
        )
        return "cc_tangent", "on_line"


def _safe(value: sp.Expr) -> str:
    return sp.sstr(value)


def _prepare_exact_system(
    text: str,
    *,
    enable_affine_local_lemmas: bool = False,
    enable_structural_lemmas: bool = True,
    representation: str = "explicit",
) -> tuple[
    _JGEXElaborator,
    tuple[str, ...],
    str,
    tuple[str, ...],
    sp.Expr,
    tuple[sp.Expr, ...],
    tuple[sp.Symbol, ...],
]:
    definitions = JGEXDefinition.to_dict(list(ALL_JGEX_CONSTRUCTIONS))
    formulation = JGEXFormulation.from_text(text)
    formulation, report = normalize_legacy_formulation(formulation, definitions)
    if report.unresolved_constructions:
        raise ValueError("JGEX normalization left unresolved constructions")
    if len(formulation.goals) != 1:
        raise ValueError("exact bridge currently requires one goal")

    if representation == "explicit":
        elaborator = _JGEXElaborator(
            enable_affine_local_lemmas=enable_affine_local_lemmas
        )
    elif representation == "relational":
        elaborator = _RelationalJGEXElaborator(
            enable_affine_local_lemmas=enable_affine_local_lemmas
        )
    else:
        raise ValueError(f"unknown exact representation: {representation}")
    vocabulary: list[str] = []
    homothety_macros = (
        external_homothety_macros(formulation) if enable_structural_lemmas else ()
    )
    macros_by_start = {item.tangent_clause_index: item for item in homothety_macros}
    skipped_clause_indices = {
        item.intersection_clause_index for item in homothety_macros
    }
    for clause_index, clause in enumerate(formulation.setup_clauses):
        if clause_index in macros_by_start:
            vocabulary.extend(
                elaborator.elaborate_external_homothety_macro(
                    macros_by_start[clause_index]
                )
            )
            continue
        if clause_index in skipped_clause_indices:
            continue
        elaborator._clause_index = clause_index
        vocabulary.extend(elaborator.elaborate_clause(clause))

    elaborator.close_distinct_locus_roots()

    goal = formulation.goals[0]
    channel = goal.predicate_type.value
    points = tuple(str(arg) for arg in goal.args)
    goal_polynomial = elaborator.goal(channel, points)
    equations = tuple(sp.expand(equation) for equation in elaborator.equations)
    variables = tuple(reversed(elaborator.variables))
    return (
        elaborator,
        tuple(vocabulary),
        channel,
        points,
        goal_polynomial,
        equations,
        variables,
    )


def inspect_jgex_exact_system(
    text: str,
    *,
    enable_affine_local_lemmas: bool = False,
    enable_structural_lemmas: bool = True,
    representation: str = "explicit",
) -> JGEXExactSystemAnalysis:
    (
        elaborator,
        vocabulary,
        channel,
        points,
        goal_polynomial,
        equations,
        variables,
    ) = _prepare_exact_system(
        text,
        enable_affine_local_lemmas=enable_affine_local_lemmas,
        enable_structural_lemmas=enable_structural_lemmas,
        representation=representation,
    )
    expanded_items = (*equations, sp.expand(goal_polynomial))
    term_counts = tuple(len(sp.Add.make_args(item)) for item in expanded_items)
    return JGEXExactSystemAnalysis(
        channel=channel,
        points=points,
        construction_vocabulary=tuple(sorted(set(vocabulary))),
        variables=tuple(_safe(item) for item in variables),
        construction_equations=tuple(_safe(item) for item in equations),
        goal_polynomial=_safe(goal_polynomial),
        equation_count=len(equations),
        variable_count=len(variables),
        total_expanded_terms=sum(term_counts),
        maximum_expanded_terms=max(term_counts, default=0),
        local_lemma_certificates=tuple(elaborator.local_lemma_certificates),
        structural_lemma_certificates=tuple(elaborator.structural_lemma_certificates),
        construction_blocks=tuple(elaborator.construction_blocks),
    )


def inspect_jgex_local_elimination(
    text: str,
    *,
    enable_structural_lemmas: bool = True,
    max_steps: int | None = None,
    max_output_terms: int = 64,
    max_resultant_degree: int = 2,
    max_separator_variables: int | None = None,
    ordering_strategy: str = "local_degree",
) -> JGEXLocalEliminationAnalysis:
    """Project a relational construction system through bounded local stalks."""

    (
        elaborator,
        _,
        channel,
        points,
        goal_polynomial,
        equations,
        variables,
    ) = _prepare_exact_system(
        text,
        enable_affine_local_lemmas=False,
        enable_structural_lemmas=enable_structural_lemmas,
        representation="relational",
    )
    initial_items = (*equations, sp.expand(goal_polynomial))
    initial_counts = tuple(
        len(sp.Add.make_args(sp.expand(item))) for item in initial_items
    )
    protected = frozenset(goal_polynomial.free_symbols)
    elimination = eliminate_local_linear_variables(
        equations,
        variables,
        protected_variables=protected,
        max_steps=max_steps,
        max_output_terms=max_output_terms,
        max_resultant_degree=max_resultant_degree,
        max_separator_variables=max_separator_variables,
        ordering_strategy=ordering_strategy,
    )
    reduced = tuple(sp.sympify(item) for item in elimination.remaining_polynomials)
    reduced_counts = tuple(len(sp.Add.make_args(sp.expand(item))) for item in reduced)
    structural_replayed = all(
        item.replayed and item.composition_replayed
        for item in elaborator.structural_lemma_certificates
    )
    return JGEXLocalEliminationAnalysis(
        channel=channel,
        points=points,
        goal_polynomial=_safe(goal_polynomial),
        initial_variable_count=len(variables),
        initial_equation_count=len(equations),
        initial_total_expanded_terms=sum(initial_counts),
        initial_maximum_expanded_terms=max(initial_counts, default=0),
        protected_variables=tuple(sorted(_safe(item) for item in protected)),
        reduced_variable_count=len(elimination.remaining_variables),
        reduced_equation_count=len(reduced),
        reduced_total_expanded_terms=sum(reduced_counts),
        reduced_maximum_expanded_terms=max(reduced_counts, default=0),
        local_elimination=elimination,
        structural_lemma_certificates=tuple(elaborator.structural_lemma_certificates),
        all_local_certificates_replayed=(
            elimination.exact_replay and structural_replayed
        ),
    )


def lower_jgex_to_exact_obligation(
    text: str,
    *,
    enable_affine_local_lemmas: bool = False,
    enable_structural_lemmas: bool = True,
    representation: str = "explicit",
) -> JGEXExactObligation:
    (
        elaborator,
        vocabulary,
        channel,
        points,
        goal_polynomial,
        equations,
        variables,
    ) = _prepare_exact_system(
        text,
        enable_affine_local_lemmas=enable_affine_local_lemmas,
        enable_structural_lemmas=enable_structural_lemmas,
        representation=representation,
    )
    direct_constraint: tuple[sp.Expr, sp.Expr] | None = None
    for equation in equations:
        if sp.expand(goal_polynomial - equation) == 0:
            direct_constraint = (equation, sp.Integer(1))
            break
        if sp.expand(goal_polynomial + equation) == 0:
            direct_constraint = (equation, sp.Integer(-1))
            break
    if sp.expand(goal_polynomial) == 0:
        quotients: list[sp.Expr] = []
        remainder = sp.Integer(0)
        basis_expressions: tuple[sp.Expr, ...] = tuple()
    elif direct_constraint is not None:
        basis_expression, quotient = direct_constraint
        quotients = [quotient]
        remainder = sp.Integer(0)
        basis_expressions = (basis_expression,)
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
        - sum(
            (quotient * item for quotient, item in zip(quotients, basis_expressions)),
            sp.Integer(0),
        )
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
            *(
                "local_affine:"
                + ":".join(
                    (
                        str(item.clause_index),
                        item.variable,
                        item.defining_equation,
                        item.coefficient,
                        item.replacement,
                    )
                )
                for item in elaborator.local_lemma_certificates
            ),
            *(
                "structural_lemma:"
                + ":".join(
                    (
                        item.theorem,
                        *item.inputs,
                        item.output,
                        *item.boundary_equations,
                    )
                )
                for item in elaborator.structural_lemma_certificates
            ),
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
        local_lemma_certificates=tuple(elaborator.local_lemma_certificates),
        structural_lemma_certificates=tuple(elaborator.structural_lemma_certificates),
        construction_blocks=tuple(elaborator.construction_blocks),
    )
