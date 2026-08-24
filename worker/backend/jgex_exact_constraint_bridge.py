"""Lower a typed JGEX construction fragment to an exact polynomial certificate.

The implementation follows construction semantics rather than problem IDs.  It
eliminates deterministic geometric constructions, preserves locus parameters,
and asks Groebner reduction only about the remaining polynomial constraints.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
import time
from typing import Callable

import sympy as sp

try:
    from flint import fmpq, fmpq_mpoly_ctx
except ImportError:  # pragma: no cover - SymPy remains the portable fallback.
    fmpq = None
    fmpq_mpoly_ctx = None
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
from worker.backend.chordal_buchberger_elimination import (
    ChordalBuchbergerEliminationResult,
    eliminate_with_certified_chordal_buchberger,
)
from worker.backend.local_polynomial_elimination import (
    LocalEliminationResult,
    eliminate_local_linear_variables,
)


@lru_cache(maxsize=1)
def _circle_second_formula_replay_residuals() -> tuple[str, str]:
    ax, ay, bx, by, sx, sy = sp.symbols("ax ay bx by sx sy")
    delta = (bx - ax, by - ay)
    perpendicular = (-delta[1], delta[0])
    distance_squared = delta[0] ** 2 + delta[1] ** 2
    transverse = (
        perpendicular[0] * (sx - ax) + perpendicular[1] * (sy - ay)
    )
    scale = -2 * transverse / distance_squared
    output = (
        sx + scale * perpendicular[0],
        sy + scale * perpendicular[1],
    )

    def distance_residual(center: tuple[sp.Expr, sp.Expr]) -> sp.Expr:
        output_distance = sum(
            (value - center_value) ** 2
            for value, center_value in zip(output, center, strict=True)
        )
        shared_distance = (sx - center[0]) ** 2 + (sy - center[1]) ** 2
        return sp.cancel(output_distance - shared_distance)

    return tuple(
        sp.sstr(item)
        for item in (
            distance_residual((ax, ay)),
            distance_residual((bx, by)),
        )
    )


@lru_cache(maxsize=1)
def _circle_axis_projection_replay_residual() -> str:
    """Replay the two-circle axis projection once in an abstract chart."""

    ux, uy, sx, sy, first_radius, second_radius = sp.symbols(
        "ux uy sx sy first_radius second_radius"
    )
    axis_norm = ux**2 + uy**2
    displacement_norm = sx**2 + sy**2
    axis_dot = ux * sx + uy * sy
    axis_cross = ux * sy - uy * sx
    first_circle = displacement_norm - first_radius
    second_circle = (
        (sx - ux) ** 2 + (sy - uy) ** 2 - second_radius
    )
    circle_difference = first_circle - second_circle
    discriminant = (
        4 * axis_norm * first_radius
        - (axis_norm + first_radius - second_radius) ** 2
    )
    residual = sp.expand(
        discriminant
        + 4 * axis_norm * first_circle
        - 4 * axis_cross**2
        - 4 * axis_dot * circle_difference
        + circle_difference**2
    )
    return sp.sstr(residual)


@lru_cache(maxsize=1)
def _homogeneous_circle_axis_replay_residual() -> str:
    """Replay denominator clearing for the projective circle-axis chart."""

    d_num, r_num, s_num, p_weight, q_weight, a_weight, b_weight = sp.symbols(
        "d_num r_num s_num p_weight q_weight a_weight b_weight"
    )
    common_denominator = (
        p_weight**2 * q_weight**2 * a_weight**2 * b_weight**2
    )
    d_scaled = d_num * a_weight**2 * b_weight**2
    r_scaled = r_num * q_weight**2 * b_weight**2
    s_scaled = s_num * p_weight**2 * a_weight**2
    polynomial = (
        4 * d_scaled * r_scaled
        - (d_scaled + r_scaled - s_scaled) ** 2
    )
    rational_discriminant = (
        4
        * (d_num / (p_weight * q_weight) ** 2)
        * (r_num / (p_weight * a_weight) ** 2)
        - (
            d_num / (p_weight * q_weight) ** 2
            + r_num / (p_weight * a_weight) ** 2
            - s_num / (q_weight * b_weight) ** 2
        )
        ** 2
    )
    return sp.sstr(
        sp.cancel(polynomial - rational_discriminant * common_denominator**2)
    )


@lru_cache(maxsize=1)
def _affine_point_projection_replay_residuals() -> tuple[str, str]:
    """Replay Cramer's rule for one typed two-equation point block."""

    a, b, c, d, e, f = sp.symbols("a b c d e f")
    determinant = a * e - b * d
    x_numerator = b * f - c * e
    y_numerator = c * d - a * f
    return tuple(
        sp.sstr(sp.expand(item))
        for item in (
            a * x_numerator + b * y_numerator + c * determinant,
            d * x_numerator + e * y_numerator + f * determinant,
        )
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
    saturation_multiplier: str
    saturation_assumptions_used: tuple[str, ...]
    exact_replay: bool
    construction_consistency: str
    vacuous_unit_ideal: bool
    certificate_sha256: str
    local_lemma_certificates: tuple["AffineLocalLemmaCertificate", ...] = ()
    structural_lemma_certificates: tuple["StructuralLocalLemmaCertificate", ...] = ()
    construction_blocks: tuple["ConstructionEquationBlock", ...] = ()
    reduction_strategy: str = "global_groebner"
    reduced_construction_equations: tuple[str, ...] = ()
    local_elimination: LocalEliminationResult | None = None
    goal_relevant_clause_indices: tuple[int, ...] = ()
    excluded_clause_indices: tuple[int, ...] = ()
    goal_decomposition_certificate: "TypedGoalDecompositionCertificate | None" = None


@dataclass(frozen=True)
class TypedGoalDecompositionCertificate:
    """Replayable composition of typed scalar subgoals into one predicate goal."""

    theorem: str
    component_polynomials: tuple[str, ...]
    composition_weights: tuple[str, ...]
    component_quotient_certificates: tuple[tuple[str, ...], ...]
    component_remainders: tuple[str, ...]
    composition_residual: str
    replayed: bool


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
    nonzero_conditions: tuple[str, ...] = ()


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
    normalization_assumptions: tuple[str, ...]
    nondegeneracy_conditions: tuple[str, ...]
    executable_regularity_conditions: tuple[str, ...]
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
    point_coordinates: tuple[tuple[str, tuple[str, str]], ...]


@dataclass(frozen=True)
class JGEXRelationPolynomial:
    """One typed relation evaluated in an already elaborated coordinate chart."""

    channel: str
    points: tuple[str, ...]
    polynomial: str
    nonzero_conditions: tuple[str, ...] = ()


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
    nondegeneracy_conditions: tuple[str, ...]
    local_elimination: LocalEliminationResult
    structural_lemma_certificates: tuple[StructuralLocalLemmaCertificate, ...]
    all_local_certificates_replayed: bool


@dataclass(frozen=True)
class JGEXChordalBuchbergerAnalysis:
    channel: str
    points: tuple[str, ...]
    goal_polynomial: str
    initial_variable_count: int
    initial_equation_count: int
    protected_variables: tuple[str, ...]
    chordal_elimination: ChordalBuchbergerEliminationResult
    structural_lemma_certificates: tuple[StructuralLocalLemmaCertificate, ...]
    all_certificates_replayed: bool


Point = tuple[sp.Expr, sp.Expr]

SUPPORTED_CONSTRUCTION_VOCABULARY = frozenset(
    {
        "triangle",
        "iso_triangle",
        "ieq_triangle",
        "quadrangle",
        "r_triangle",
        "free",
        "segment",
        "midpoint",
        "foot",
        "orthocenter",
        "circle",
        "circumcenter",
        "centroid",
        "excenter",
        "on_line",
        "on_circle",
        "on_circum",
        "on_tline",
        "on_pline",
        "on_dia",
        "angle_bisector",
        "incenter",
        "incenter2",
        "mirror",
        "reflect",
        "on_bline",
        "eqdistance",
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
        self.circle_circle_known_roots: dict[
            tuple[tuple[str, str], str], str
        ] = {}
        self.circle_circle_intersections: dict[
            str, tuple[str, str, str, str, int]
        ] = {}
        self.relational_outputs: set[str] = set()
        self.active_clause_outputs: set[str] = set()
        self.preserved_boundary_outputs: set[str] = set()
        self.goal_dependency_points: tuple[str, ...] | None = None
        self.goal_hidden_points: set[str] = set()
        self.forced_explicit_outputs: set[str] = set()
        self.existential_coordinate_variables: set[sp.Symbol] = set()
        self.side_lengths: dict[tuple[str, str], sp.Symbol] = {}
        self.local_lemma_certificates: list[AffineLocalLemmaCertificate] = []
        self.structural_lemma_certificates: list[StructuralLocalLemmaCertificate] = []
        self.construction_blocks: list[ConstructionEquationBlock] = []
        self._parameter_index = 0
        self._clause_index = 0
        self.enable_affine_local_lemmas = enable_affine_local_lemmas
        self.progress_callback: Callable[[dict[str, object]], None] | None = None

    def _emit_progress(self, operation: str, **metrics: object) -> None:
        if self.progress_callback is not None:
            self.progress_callback(
                {
                    "stage": "construction_operation",
                    "operation": operation,
                    "clause_index": self._clause_index,
                    **metrics,
                }
            )

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
            coordinates = (
                self._parameter("free_x"),
                self._parameter("free_y"),
            )
            self.coordinates[name] = coordinates
            self.existential_coordinate_variables.update(coordinates)
        return self.coordinates[name]

    def _segment(self, points: tuple[str, ...]) -> None:
        if len(points) != 2:
            raise ValueError("segment expects two output points")
        left, right = points
        if not self.coordinates:
            length = self._parameter("segment_length")
            self.coordinates[left] = (sp.Integer(0), sp.Integer(0))
            self.coordinates[right] = (length, sp.Integer(0))
            self.denominators.append(length)
            self.normalization_assumptions.extend(
                (
                    f"euclidean_gauge {left}=(0,0) {right}=({_safe(length)},0)",
                    f"{_safe(length)} != 0",
                )
            )
        else:
            self._free_point(left)
            self._free_point(right)
            distinctness = sp.factor(self._distance_squared(left, right))
            self.denominators.append(distinctness)
            self.normalization_assumptions.append(f"diff {left} {right}")
        self.normalization_assumptions.append(
            "official_jgex_semantics segment introduces two free points"
        )

    def _append_equation(self, expression: sp.Expr) -> sp.Expr:
        equation_index = len(self.equations)
        self._emit_progress(
            "equation_together_started", equation_index=equation_index
        )
        numerator, denominator = sp.together(expression).as_numer_denom()
        self._emit_progress(
            "equation_denominator_factor_started", equation_index=equation_index
        )
        denominator = sp.factor(denominator)
        if denominator != 1:
            self.denominators.append(denominator)
        self._emit_progress(
            "equation_numerator_factor_started", equation_index=equation_index
        )
        polynomial = sp.factor(numerator)
        self.equations.append(polynomial)
        self._emit_progress(
            "equation_completed", equation_index=equation_index
        )
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

    def _isosceles_triangle(self, points: tuple[str, ...]) -> None:
        if len(points) != 3:
            raise ValueError("iso_triangle expects three output points")
        vertex, left, right = points
        if not self.coordinates:
            half_base = self._parameter("isosceles_half_base")
            height = self._parameter("isosceles_height")
            self.coordinates[vertex] = (sp.Integer(0), height)
            self.coordinates[left] = (-half_base, sp.Integer(0))
            self.coordinates[right] = (half_base, sp.Integer(0))
            self.denominators.extend((half_base, height))
            self.normalization_assumptions.extend(
                (
                    f"euclidean_gauge {vertex}=(0,{_safe(height)}) "
                    f"{left}=(-{_safe(half_base)},0) "
                    f"{right}=({_safe(half_base)},0)",
                    f"{_safe(half_base)} != 0",
                    f"{_safe(height)} != 0",
                )
            )
        else:
            vertex_coordinates = (
                self._parameter("isosceles_vertex_x"),
                self._parameter("isosceles_vertex_y"),
            )
            midpoint = (
                self._parameter("isosceles_midpoint_x"),
                self._parameter("isosceles_midpoint_y"),
            )
            half_base_scale = self._parameter("isosceles_half_base_scale")
            axis = self._sub(midpoint, vertex_coordinates)
            half_base = self._scale(half_base_scale, (-axis[1], axis[0]))
            self.coordinates[vertex] = vertex_coordinates
            self.coordinates[left] = self._add(midpoint, half_base)
            self.coordinates[right] = self._sub(midpoint, half_base)
            axis_length_squared = sp.factor(self._dot(axis, axis))
            self.denominators.extend((axis_length_squared, half_base_scale))
            self.normalization_assumptions.extend(
                (
                    f"{_safe(axis_length_squared)} != 0",
                    f"{_safe(half_base_scale)} != 0",
                )
            )
        self.normalization_assumptions.append(
            f"official_jgex_semantics cong {vertex} {left} {vertex} {right}"
        )

    def _equilateral_triangle(self, points: tuple[str, ...]) -> None:
        if len(points) != 3:
            raise ValueError("ieq_triangle expects three output points")
        left, right, apex = points
        base = self._parameter("base")
        height = self._parameter("equilateral_height")
        self.coordinates[left] = (sp.Integer(0), sp.Integer(0))
        self.coordinates[right] = (base, sp.Integer(0))
        self.coordinates[apex] = (base / 2, height)
        self._append_equation(4 * height * height - 3 * base * base)
        self.denominators.extend((base, height))
        self.normalization_assumptions.extend(
            (
                f"euclidean_gauge {left}=(0,0) {right}=({_safe(base)},0) "
                f"{apex}=({_safe(base / 2)},{_safe(height)})",
                f"{_safe(base)} != 0",
                f"{_safe(height)} != 0",
            )
        )

    def _quadrangle(self, points: tuple[str, ...]) -> None:
        """Fix only Euclidean gauge freedom for four otherwise free points."""

        if len(points) != 4:
            raise ValueError("quadrangle expects four output points")
        left, right, third, fourth = points
        base = self._parameter("base")
        third_x = self._parameter("third_x")
        third_y = self._parameter("third_y")
        fourth_x = self._parameter("fourth_x")
        fourth_y = self._parameter("fourth_y")
        self.coordinates[left] = (sp.Integer(0), sp.Integer(0))
        self.coordinates[right] = (base, sp.Integer(0))
        self.coordinates[third] = (third_x, third_y)
        self.coordinates[fourth] = (fourth_x, fourth_y)
        self.normalization_assumptions.extend(
            (
                f"euclidean_gauge {left}=(0,0) {right}=({_safe(base)},0) "
                f"{third}=({_safe(third_x)},{_safe(third_y)}) "
                f"{fourth}=({_safe(fourth_x)},{_safe(fourth_y)})",
                f"{_safe(base)} != 0",
                f"{_safe(third_y)} != 0",
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

    def _centroid(self, args: tuple[str, ...]) -> None:
        midpoint_a, midpoint_b, midpoint_c, centroid, a, b, c = args
        self._midpoint((midpoint_a, b, c))
        self._midpoint((midpoint_b, c, a))
        self._midpoint((midpoint_c, a, b))
        self.coordinates[centroid] = tuple(
            sp.cancel((a_value + b_value + c_value) / 3)
            for a_value, b_value, c_value in zip(
                self.coordinates[a],
                self.coordinates[b],
                self.coordinates[c],
                strict=True,
            )
        )  # type: ignore[assignment]

    def _excenter(self, args: tuple[str, ...]) -> None:
        center, a, b, c = args
        side_a = self._side_length(b, c)
        side_b = self._side_length(c, a)
        side_c = self._side_length(a, b)
        denominator = sp.factor(-side_a + side_b + side_c)
        self.denominators.append(denominator)
        self.coordinates[center] = tuple(
            sp.cancel(
                (-side_a * a_value + side_b * b_value + side_c * c_value)
                / denominator
            )
            for a_value, b_value, c_value in zip(
                self.coordinates[a],
                self.coordinates[b],
                self.coordinates[c],
                strict=True,
            )
        )  # type: ignore[assignment]

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

    def _on_circumcircle(self, args: tuple[str, ...]) -> None:
        point, a, b, c = args
        self._free_point(point)
        rows = []
        for selected in (a, b, c, point):
            x, y = self.coordinates[selected]
            rows.append((x * x + y * y, x, y, sp.Integer(1)))
        self._append_equation(sp.det(sp.Matrix(rows)))
        self.denominators.append(
            self._cross(
                self._sub(self.coordinates[b], self.coordinates[a]),
                self._sub(self.coordinates[c], self.coordinates[a]),
            )
        )

    def _eqdistance(self, args: tuple[str, ...]) -> None:
        point, center, left, right = args
        self._free_point(point)
        self._append_equation(
            self._distance_squared(point, center)
            - self._distance_squared(left, right)
        )
        self.denominators.append(self._distance_squared(left, right))

    def _equal_angle_polynomial(
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
        return sp.expand(left_cross * right_dot - left_dot * right_cross)

    def _equal_angle_equation(
        self,
        ray_a: tuple[str, str],
        ray_b: tuple[str, str],
        ray_c: tuple[str, str],
        ray_d: tuple[str, str],
    ) -> sp.Expr:
        return self._append_equation(
            self._equal_angle_polynomial(ray_a, ray_b, ray_c, ray_d)
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
        denominator_start = len(self.denominators)
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
                nonzero_conditions=tuple(
                    f"{_safe(item)} != 0"
                    for item in self.denominators[denominator_start:]
                    if item != 0
                ),
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

    def _other_intersection_of_circles(
        self,
        output: str,
        center_a: str,
        center_b: str,
        shared_point: str,
    ) -> None:
        """Construct the non-shared intersection of two circles exactly."""

        signature = (tuple(sorted((center_a, center_b))), shared_point)
        existing_output = self.circle_circle_known_roots.get(signature)
        if existing_output is not None:
            raise ValueError(
                "circle intersection reuses an already-existing point: "
                + existing_output
            )

        self._emit_progress("circle_second_geometry_started", output=output)
        first_center = self.coordinates[center_a]
        second_center = self.coordinates[center_b]
        shared = self.coordinates[shared_point]
        center_delta = self._sub(second_center, first_center)
        center_distance_squared = sp.factor(self._dot(center_delta, center_delta))
        perpendicular = (-center_delta[1], center_delta[0])
        shared_from_first = self._sub(shared, first_center)
        transverse_projection = sp.factor(
            self._dot(perpendicular, shared_from_first)
        )
        if center_distance_squared == 0:
            raise ValueError("coincident circles do not define a second intersection")
        if transverse_projection == 0:
            raise ValueError("tangent circles do not define a distinct second intersection")

        self._emit_progress("circle_second_candidate_started", output=output)
        scale = sp.cancel(-2 * transverse_projection / center_distance_squared)
        candidate = tuple(
            sp.cancel(shared_value + scale * direction)
            for shared_value, direction in zip(shared, perpendicular, strict=True)
        )
        self._emit_progress("circle_second_candidate_completed", output=output)

        self.coordinates[output] = candidate  # type: ignore[assignment]
        self.denominators.extend((center_distance_squared, transverse_projection))
        self.normalization_assumptions.extend(
            (
                f"circle_circle_second_intersection {output} excludes {shared_point}",
                f"diff {center_a} {center_b}",
                f"diff {output} {shared_point}",
            )
        )
        self.circle_circle_known_roots[signature] = output

        self._emit_progress("circle_second_replay_started", output=output)
        replay_residual_strings = _circle_second_formula_replay_residuals()
        residuals = tuple(sp.sympify(item) for item in replay_residual_strings)
        replayed = replay_residual_strings == ("0", "0")
        self._emit_progress(
            "circle_second_replay_completed", output=output, replayed=replayed
        )
        certificate_material = "|".join(
            (
                "circle_circle_known_root_deflation",
                output,
                center_a,
                center_b,
                shared_point,
                *(_safe(item) for item in self.coordinates[output]),
                *(_safe(item) for item in residuals),
                _safe(center_distance_squared),
                _safe(transverse_projection),
            )
        )
        self.structural_lemma_certificates.append(
            StructuralLocalLemmaCertificate(
                theorem="circle_circle_known_root_deflation",
                source_clause_indices=(self._clause_index - 1,),
                inputs=(center_a, center_b, shared_point),
                output=output,
                hidden_points=(),
                boundary_equations=(
                    f"dist2({center_a},{output})=dist2({center_a},{shared_point})",
                    f"dist2({center_b},{output})=dist2({center_b},{shared_point})",
                ),
                replay_residuals=tuple(_safe(item) for item in residuals),
                nonzero_conditions=(
                    f"{_safe(center_distance_squared)} != 0",
                    f"{_safe(transverse_projection)} != 0",
                ),
                semantic_assumption=(
                    "JGEX reduce_intersection selects the circle intersection "
                    "that is distinct from every existing point"
                ),
                composition_certificate_sha256=hashlib.sha256(
                    certificate_material.encode()
                ).hexdigest(),
                composition_replayed=replayed,
                replayed=replayed,
            )
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
            "iso_triangle",
            "r_triangle",
            "ieq_triangle",
        }:
            points = tuple(str(arg) for arg in constructions[0].args)
            if constructions[0].name == "triangle":
                self._triangle(points)
            elif constructions[0].name == "iso_triangle":
                self._isosceles_triangle(points)
            elif constructions[0].name == "r_triangle":
                self._right_triangle(points)
            else:
                self._equilateral_triangle(points)
            return names

        if len(constructions) == 1 and constructions[0].name == "free":
            for point in clause.points:
                self._free_point(str(point))
            return names

        if len(constructions) == 1 and constructions[0].name == "segment":
            self._segment(tuple(str(point) for point in constructions[0].args))
            return names

        if len(constructions) == 1 and constructions[0].name == "quadrangle":
            self._quadrangle(tuple(str(point) for point in clause.points))
            return names

        if len(constructions) == 2 and all(
            construction.name == "on_circle" for construction in constructions
        ):
            left = tuple(str(arg) for arg in constructions[0].args)
            right = tuple(str(arg) for arg in constructions[1].args)
            if left[0] == right[0] and left[2] == right[2]:
                self._other_intersection_of_circles(
                    left[0], left[1], right[1], left[2]
                )
                return names

        if len(constructions) == 1 and constructions[0].name == "foot":
            self._foot(tuple(str(arg) for arg in constructions[0].args))
            return names

        if len(constructions) == 1 and constructions[0].name in {
            "midpoint",
            "orthocenter",
            "circle",
            "circumcenter",
            "centroid",
            "excenter",
            "incenter",
            "incenter2",
        }:
            arguments = tuple(str(arg) for arg in constructions[0].args)
            if constructions[0].name == "midpoint":
                self._midpoint(arguments)
            elif constructions[0].name == "orthocenter":
                self._orthocenter(arguments)
            elif constructions[0].name in {"circle", "circumcenter"}:
                self._circumcenter(arguments)
            elif constructions[0].name == "centroid":
                self._centroid(arguments)
            elif constructions[0].name == "excenter":
                self._excenter(arguments)
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

    def _exclude_existing_intersection_roots(
        self,
        clause,
        *,
        existing_coordinates: dict[str, Point],
        equation_start: int,
    ) -> None:
        """Match JGEX's rule that a new intersection cannot reuse an old point.

        Newclid's ``reduce_intersection`` discards every intersection that is
        numerically equal to an existing point.  Polynomial locus equations do
        not encode that branch choice by themselves, so a shared old root can
        otherwise survive as an extra algebraic component.  Only old points
        that are exact roots of every equation introduced by this clause need
        to be saturated away.
        """

        if len(clause.constructions) < 2 or len(clause.points) != 1:
            return
        output = str(clause.points[0])
        if output in existing_coordinates:
            return
        output_coordinates = self.coordinates.get(output)
        if output_coordinates is None or not all(
            isinstance(coordinate, sp.Symbol) for coordinate in output_coordinates
        ):
            return
        clause_equations = tuple(self.equations[equation_start:])
        if not clause_equations:
            return

        output_x, output_y = output_coordinates
        for existing, (existing_x, existing_y) in existing_coordinates.items():
            substitution = {output_x: existing_x, output_y: existing_y}
            if not all(
                sp.cancel(equation.subs(substitution)) == 0
                for equation in clause_equations
            ):
                continue
            distinctness = sp.factor(
                (output_x - existing_x) ** 2 + (output_y - existing_y) ** 2
            )
            if distinctness == 0:
                continue
            self.denominators.append(distinctness)
            assumption = f"diff {output} {existing}"
            if assumption not in self.normalization_assumptions:
                self.normalization_assumptions.append(assumption)

    def _record_linear_intersection_regularity(
        self,
        clause,
        *,
        existing_coordinates: dict[str, Point],
        equation_start: int,
    ) -> None:
        """Export the Cramer determinant required by a two-locus construction.

        ``reduce_intersection`` rejects parallel/coincident line loci.  In the
        relational encoding, however, two linear locus equations also retain
        the rank-deficient component unless their coefficient determinant is
        recorded as nonzero.  Deriving the determinant from the emitted
        equations covers ordinary, parallel, perpendicular, bisector, and
        equal-angle line intersections without branching on construction names.
        """

        if len(clause.constructions) < 2 or len(clause.points) != 1:
            return
        output = str(clause.points[0])
        if output in existing_coordinates:
            return
        output_coordinates = self.coordinates.get(output)
        clause_equations = tuple(self.equations[equation_start:])
        if output_coordinates is None or len(clause_equations) != 2:
            return
        output_x, output_y = output_coordinates
        if not all(isinstance(item, sp.Symbol) for item in (output_x, output_y)):
            return
        try:
            polynomials = tuple(
                sp.Poly(equation, output_x, output_y) for equation in clause_equations
            )
        except sp.PolynomialError:
            return
        if any(polynomial.total_degree() > 1 for polynomial in polynomials):
            return

        determinant = sp.factor(
            sp.diff(clause_equations[0], output_x)
            * sp.diff(clause_equations[1], output_y)
            - sp.diff(clause_equations[0], output_y)
            * sp.diff(clause_equations[1], output_x)
        )
        if determinant == 0 or not determinant.free_symbols:
            return
        self.denominators.append(determinant)
        self.normalization_assumptions.append(
            f"unique_linear_intersection {output}: {_safe(determinant)} != 0"
        )

    def _substitute_coordinates(
        self, variable: sp.Symbol, replacement: sp.Expr
    ) -> None:
        for point, coordinates in tuple(self.coordinates.items()):
            if any(variable in coordinate.free_symbols for coordinate in coordinates):
                self.coordinates[point] = tuple(
                    sp.cancel(coordinate.subs(variable, replacement))
                    for coordinate in coordinates
                )  # type: ignore[assignment]
        substituted_denominators: list[sp.Expr] = []
        for denominator in self.denominators:
            substituted = sp.together(denominator.subs(variable, replacement))
            numerator, replacement_denominator = substituted.as_numer_denom()
            numerator = sp.factor(numerator)
            if numerator != 0:
                substituted_denominators.append(numerator)
            # The affine elimination coefficient is recorded separately before
            # this substitution. Retain any additional denominator introduced
            # by a nested rational coordinate expression as well.
            replacement_denominator = sp.factor(replacement_denominator)
            if replacement_denominator not in {0, 1, -1}:
                substituted_denominators.append(replacement_denominator)
        self.denominators = substituted_denominators

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
            self.existential_coordinate_variables.discard(variable)
            candidates.remove(variable)

    def _preserve_affine_clause_variables(
        self,
        vocabulary: tuple[str, ...],
        *,
        equation_start: int,
    ) -> bool:
        del vocabulary, equation_start
        return False

    def elaborate_clause(self, clause) -> tuple[str, ...]:
        clause_index = self._clause_index
        self._clause_index += 1
        self.active_clause_outputs = {str(point) for point in clause.points}
        equation_start = len(self.equations)
        variable_start = len(self.variables)
        lemma_start = len(self.local_lemma_certificates)
        denominator_start = len(self.denominators)
        existing_coordinates = dict(self.coordinates)
        structural_lemma_start = len(self.structural_lemma_certificates)
        self._emit_progress("clause_raw_elaboration_started", clause_index=clause_index)
        names = self._elaborate_clause_raw(clause)
        if (
            len(clause.points) == 1
            and len(clause.constructions) == 2
            and all(
                construction.name == "on_circle"
                for construction in clause.constructions
            )
        ):
            output = str(clause.points[0])
            left = tuple(str(argument) for argument in clause.constructions[0].args)
            right = tuple(str(argument) for argument in clause.constructions[1].args)
            if len(left) == 3 and len(right) == 3:
                self.circle_circle_intersections[output] = (
                    left[1],
                    left[2],
                    right[1],
                    right[2],
                    clause_index,
                )
        self._emit_progress(
            "clause_raw_elaboration_completed",
            clause_index=clause_index,
            construction_vocabulary=tuple(sorted(set(names))),
        )
        known_root_circle_intersection = any(
            item.theorem == "circle_circle_known_root_deflation"
            for item in self.structural_lemma_certificates[structural_lemma_start:]
        )
        if not known_root_circle_intersection:
            self._emit_progress(
                "intersection_regularity_started", clause_index=clause_index
            )
            self._record_linear_intersection_regularity(
                clause,
                existing_coordinates=existing_coordinates,
                equation_start=equation_start,
            )
            self._emit_progress(
                "intersection_regularity_completed", clause_index=clause_index
            )
            self._emit_progress(
                "existing_root_exclusion_started", clause_index=clause_index
            )
            self._exclude_existing_intersection_roots(
                clause,
                existing_coordinates=existing_coordinates,
                equation_start=equation_start,
            )
            self._emit_progress(
                "existing_root_exclusion_completed", clause_index=clause_index
            )
        introduced_variables = tuple(self.variables[variable_start:])
        preserve_boundary = bool(
            self.enable_affine_local_lemmas
            and self._preserve_affine_clause_variables(
                names,
                equation_start=equation_start,
            )
        )
        if self.enable_affine_local_lemmas and not preserve_boundary:
            new_equations = tuple(self.equations[equation_start:])
            self._emit_progress(
                "affine_clause_compression_started",
                clause_index=clause_index,
                introduced_variable_count=len(introduced_variables),
                clause_equation_count=len(new_equations),
                clause_operation_count=sum(
                    int(sp.count_ops(equation)) for equation in new_equations
                ),
                maximum_equation_operation_count=max(
                    (int(sp.count_ops(equation)) for equation in new_equations),
                    default=0,
                ),
            )
            self._compress_affine_clause(
                clause_index=clause_index,
                vocabulary=names,
                equation_start=equation_start,
                introduced_variables=introduced_variables,
            )
            self._emit_progress(
                "affine_clause_compression_completed",
                clause_index=clause_index,
                remaining_variable_count=sum(
                    variable in self.variables for variable in introduced_variables
                ),
            )
        elif preserve_boundary:
            self.preserved_boundary_outputs.update(self.active_clause_outputs)
        surviving_variables = tuple(
            variable for variable in introduced_variables if variable in self.variables
        )
        self._emit_progress(
            "construction_block_materialization_started",
            clause_index=clause_index,
            surviving_variable_count=len(surviving_variables),
            surviving_equation_count=len(self.equations) - equation_start,
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
                nonzero_conditions=tuple(
                    f"{_safe(item)} != 0"
                    for item in self.denominators[denominator_start:]
                    if item != 0
                ),
            )
        )
        self._emit_progress(
            "construction_block_materialization_completed",
            clause_index=clause_index,
        )
        return names

    def _dispatch(self, name: str, args: tuple[str, ...]) -> None:
        if name == "on_line":
            self._on_line(args)
        elif name == "on_circle":
            self._on_circle(args)
        elif name == "on_circum":
            self._on_circumcircle(args)
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
        elif name == "eqdistance":
            self._eqdistance(args)
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

    def goal(
        self,
        channel: str,
        points: tuple[str, ...],
        *,
        factor_result: bool = True,
    ) -> sp.Expr:
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
            # Four points need one determinant equation. Squaring that single
            # determinant preserves its real zero set but needlessly doubles
            # the degree and can dominate exact elimination. For five or more
            # points, the sum of squares still encodes the conjunction that
            # every additional point lies on the same circle.
            expression = (
                determinants[0]
                if len(determinants) == 1
                else sum(
                    (determinant * determinant for determinant in determinants),
                    sp.Integer(0),
                )
            )
        elif channel == "eqangle" and len(points) == 8:
            expression = self._equal_angle_polynomial(
                (points[0], points[1]),
                (points[2], points[3]),
                (points[4], points[5]),
                (points[6], points[7]),
            )
        elif channel == "eqratio" and len(points) == 8:
            ab = self._distance_squared(points[0], points[1])
            cd = self._distance_squared(points[2], points[3])
            ef = self._distance_squared(points[4], points[5])
            gh = self._distance_squared(points[6], points[7])
            self.denominators.extend((cd, gh))
            expression = ab * gh - cd * ef
        elif channel in {"simtri", "simtrir"} and len(points) == 6:
            expression = self._similar_triangles_polynomial(
                points,
                reflected=channel == "simtrir",
            )
        elif channel == "midp" and len(points) == 3:
            midpoint, left, right = points
            residuals = tuple(
                2 * value - left_value - right_value
                for value, left_value, right_value in zip(
                    self.coordinates[midpoint],
                    self.coordinates[left],
                    self.coordinates[right],
                    strict=True,
                )
            )
            expression = sum(
                (residual * residual for residual in residuals),
                sp.Integer(0),
            )
        elif channel == "lequation" and len(points) >= 4:
            expression = self._polynomial_length_equation(points)
        else:
            raise ValueError(f"unsupported JGEX goal: {channel} {points}")
        if expression.is_polynomial():
            numerator, denominator = expression, sp.Integer(1)
        else:
            numerator, denominator = sp.together(expression).as_numer_denom()
        if denominator != 1:
            self.denominators.append(sp.factor(denominator))
        return sp.factor(numerator) if factor_result else sp.expand(numerator)

    def _similar_triangles_polynomial(
        self,
        points: tuple[str, ...],
        *,
        reflected: bool,
    ) -> sp.Expr:
        """Encode Newclid's directed triangle-similarity predicates.

        For direct similarity, ``(R-P)(B-A) = (C-A)(Q-P)`` in complex
        coordinates.  Reverse similarity conjugates the first triangle.  The
        real and imaginary residuals are combined as one Gaussian-rational
        polynomial.  Since every coordinate variable is real, its vanishing
        is equivalent to both residuals vanishing.  The two reference sides
        are recorded as nonzero.
        """

        a, b, c, p, q, r = points
        ab = self._sub(self.coordinates[b], self.coordinates[a])
        ac = self._sub(self.coordinates[c], self.coordinates[a])
        pq = self._sub(self.coordinates[q], self.coordinates[p])
        pr = self._sub(self.coordinates[r], self.coordinates[p])

        if reflected:
            # pr * conjugate(ab) = conjugate(ac) * pq
            real_residual = (
                pr[0] * ab[0]
                + pr[1] * ab[1]
                - ac[0] * pq[0]
                - ac[1] * pq[1]
            )
            imaginary_residual = (
                pr[1] * ab[0]
                - pr[0] * ab[1]
                + ac[1] * pq[0]
                - ac[0] * pq[1]
            )
        else:
            # pr * ab = ac * pq
            real_residual = (
                pr[0] * ab[0]
                - pr[1] * ab[1]
                - ac[0] * pq[0]
                + ac[1] * pq[1]
            )
            imaginary_residual = (
                pr[0] * ab[1]
                + pr[1] * ab[0]
                - ac[0] * pq[1]
                - ac[1] * pq[0]
            )

        self.denominators.extend((self._dot(ab, ab), self._dot(pq, pq)))
        return real_residual + sp.I * imaginary_residual

    def _polynomial_length_equation(self, tokens: tuple[str, ...]) -> sp.Expr:
        """Lower Newclid length equations whose monomials have even powers.

        Newclid represents ``c |AB| |CD| ... = k`` as a token stream.  A
        coordinate polynomial exists without introducing square-root branch
        choices exactly when every segment occurs with even multiplicity in
        each monomial.  The common Olympiad Pythagoras, median and
        parallelogram identities satisfy this contract.
        """

        constant = sp.Rational(tokens[-1])
        end = len(tokens) - 1
        index = 0
        expression = -constant
        while index < end:
            try:
                coefficient = sp.Rational(tokens[index])
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"invalid lequation coefficient: {tokens[index]}"
                ) from exc
            index += 1
            segments: list[tuple[str, str]] = []
            if index + 1 >= end:
                raise ValueError("truncated lequation segment")
            segments.append(tuple(sorted((tokens[index], tokens[index + 1]))))
            index += 2
            while index < end and tokens[index] == "*":
                index += 1
                if index + 1 >= end:
                    raise ValueError("truncated lequation product")
                segments.append(tuple(sorted((tokens[index], tokens[index + 1]))))
                index += 2

            multiplicities: dict[tuple[str, str], int] = {}
            for left, right in segments:
                if left == right or left not in self.coordinates or right not in self.coordinates:
                    raise ValueError(f"invalid lequation segment: {left} {right}")
                key = (left, right)
                multiplicities[key] = multiplicities.get(key, 0) + 1
            if any(value % 2 for value in multiplicities.values()):
                raise ValueError(
                    "lequation contains an odd length power and has no "
                    "branch-free coordinate polynomial"
                )
            term = coefficient
            for (left, right), multiplicity in multiplicities.items():
                term *= self._distance_squared(left, right) ** (multiplicity // 2)
            expression += term
        return sp.expand(expression)


class _RelationalJGEXElaborator(_JGEXElaborator):
    """Keep constructed points existential and export low-degree relations.

    Explicit coordinate substitution is useful for short construction chains,
    but duplicates every upstream expression at every downstream use.  This
    elaborator uses the same construction semantics while retaining the output
    coordinates as local variables constrained by small polynomial blocks.
    """

    def _append_equation(self, expression: sp.Expr) -> sp.Expr:
        equation_index = len(self.equations)
        if expression.is_polynomial():
            self._emit_progress(
                "equation_polynomial_fast_path", equation_index=equation_index
            )
            numerator, denominator = expression, sp.Integer(1)
        else:
            self._emit_progress(
                "equation_together_started", equation_index=equation_index
            )
            numerator, denominator = sp.together(expression).as_numer_denom()
        self._emit_progress(
            "equation_denominator_factor_started", equation_index=equation_index
        )
        denominator = sp.factor(denominator)
        if denominator != 1:
            self.denominators.append(denominator)
        self.equations.append(numerator)
        self._emit_progress(
            "equation_completed",
            equation_index=equation_index,
            numerator_factorization_deferred=True,
        )
        return numerator

    def _project_affine_point_boundary(
        self, point: str
    ) -> tuple[Point, tuple[str, ...]] | None:
        self._emit_progress("affine_boundary_projection_started", output=point)
        coordinates = self.coordinates.get(point)
        if coordinates is None or not all(
            isinstance(coordinate, sp.Symbol) for coordinate in coordinates
        ):
            return None
        block = next(
            (
                item
                for item in reversed(self.construction_blocks)
                if item.outputs == (point,)
                and len(item.surviving_equations) == 2
                and item.construction_vocabulary == ("circumcenter",)
            ),
            None,
        )
        if block is None:
            return None
        x, y = coordinates
        equations = tuple(sp.sympify(item) for item in block.surviving_equations)
        self._emit_progress(
            "affine_boundary_equations_loaded",
            output=point,
            equation_count=len(equations),
        )
        self._emit_progress(
            "affine_boundary_coefficients_started",
            output=point,
        )
        first, second = equations
        a = sp.diff(first, x)
        b = sp.diff(first, y)
        c = first.xreplace({x: sp.Integer(0), y: sp.Integer(0)})
        d = sp.diff(second, x)
        e = sp.diff(second, y)
        f = second.xreplace({x: sp.Integer(0), y: sp.Integer(0)})
        if any(
            variable in coefficient.free_symbols
            for coefficient in (a, b, c, d, e, f)
            for variable in (x, y)
        ):
            return None
        determinant = a * e - b * d
        if determinant == 0:
            return None
        replacement = (
            (b * f - c * e) / determinant,
            (c * d - a * f) / determinant,
        )
        self._emit_progress(
            "affine_boundary_coefficients_completed",
            output=point,
        )
        replay_residuals = _affine_point_projection_replay_residuals()
        replayed = replay_residuals == ("0", "0")
        certificate_material = "|".join(
            (
                "affine_point_boundary_projection",
                point,
                *block.surviving_equations,
                *(_safe(item) for item in replacement),
                _safe(determinant),
                *replay_residuals,
            )
        )
        if not any(
            item.theorem == "affine_point_boundary_projection"
            and item.output == point
            for item in self.structural_lemma_certificates
        ):
            self.structural_lemma_certificates.append(
                StructuralLocalLemmaCertificate(
                    theorem="affine_point_boundary_projection",
                    source_clause_indices=(block.clause_index,),
                    inputs=block.inputs,
                    output=point,
                    hidden_points=(point,),
                    boundary_equations=block.surviving_equations,
                    replay_residuals=replay_residuals,
                    nonzero_conditions=(f"{_safe(determinant)} != 0",),
                    semantic_assumption=(
                        "the official construction has a unique affine point; "
                        "Cramer's determinant is nonzero"
                    ),
                    composition_certificate_sha256=hashlib.sha256(
                        certificate_material.encode()
                    ).hexdigest(),
                    composition_replayed=replayed,
                    replayed=replayed,
                )
            )
        self.denominators.append(determinant)
        self._emit_progress(
            "affine_boundary_projection_completed",
            output=point,
        )
        return replacement, block.inputs

    def _homogeneous_point(self, point: Point) -> tuple[sp.Expr, sp.Expr, sp.Expr]:
        """Represent an affine expression pair as an exact projective chart."""

        x_numerator, x_denominator = sp.fraction(point[0])
        y_numerator, y_denominator = sp.fraction(point[1])
        for denominator in (x_denominator, y_denominator):
            if denominator != 1:
                self.denominators.append(denominator)
        if x_denominator == y_denominator:
            return x_numerator, y_numerator, x_denominator
        return (
            x_numerator * y_denominator,
            y_numerator * x_denominator,
            x_denominator * y_denominator,
        )

    @staticmethod
    def _projective_squared_distance(
        first: tuple[sp.Expr, sp.Expr, sp.Expr],
        second: tuple[sp.Expr, sp.Expr, sp.Expr],
    ) -> tuple[sp.Expr, sp.Expr]:
        """Return numerator and denominator of squared affine distance."""

        first_x, first_y, first_weight = first
        second_x, second_y, second_weight = second
        delta_x = first_x * second_weight - second_x * first_weight
        delta_y = first_y * second_weight - second_y * first_weight
        return (
            delta_x**2 + delta_y**2,
            (first_weight * second_weight) ** 2,
        )

    def _projective_circle_axis_discriminant(
        self,
        first_center: Point,
        second_center: Point,
        first_reference: Point,
        second_reference: Point,
    ) -> tuple[sp.Expr, sp.Expr]:
        """Build the circle tangency discriminant without rational expansion."""

        first = self._homogeneous_point(first_center)
        second = self._homogeneous_point(second_center)
        first_radius_point = self._homogeneous_point(first_reference)
        second_radius_point = self._homogeneous_point(second_reference)
        d_num, _ = self._projective_squared_distance(first, second)
        r_num, _ = self._projective_squared_distance(
            first, first_radius_point
        )
        s_num, _ = self._projective_squared_distance(
            second, second_radius_point
        )
        first_weight = first[2]
        second_weight = second[2]
        first_reference_weight = first_radius_point[2]
        second_reference_weight = second_radius_point[2]
        common_denominator = (
            first_weight**2
            * second_weight**2
            * first_reference_weight**2
            * second_reference_weight**2
        )
        d_scaled = (
            d_num * first_reference_weight**2 * second_reference_weight**2
        )
        r_scaled = r_num * second_weight**2 * second_reference_weight**2
        s_scaled = s_num * first_weight**2 * first_reference_weight**2
        polynomial = 4 * d_scaled * r_scaled - (
            d_scaled + r_scaled - s_scaled
        ) ** 2
        return polynomial, common_denominator**2

    def goal(
        self,
        channel: str,
        points: tuple[str, ...],
        *,
        factor_result: bool = True,
    ) -> sp.Expr:
        """Project a terminal circle intersection onto its typed boundary.

        If ``T`` lies on circles ``(P,A)`` and ``(Q,B)``, then ``P,Q,T``
        are collinear exactly when the two circles have zero intersection
        discriminant. The hidden coordinates of ``T`` can therefore be
        removed before terminal Groebner elimination. The recorded identity
        replays this projection from the two original circle equations.
        """

        if channel == "coll" and len(points) == 3:
            left_center, right_center, output = points
            intersection = self.circle_circle_intersections.get(output)
            if intersection is not None:
                center_a, reference_a, center_b, reference_b, clause_index = (
                    intersection
                )
                references = {
                    center_a: reference_a,
                    center_b: reference_b,
                }
                if set((left_center, right_center)) == set(references):
                    first_projection = self._project_affine_point_boundary(
                        left_center
                    )
                    second_projection = self._project_affine_point_boundary(
                        right_center
                    )
                    first = (
                        first_projection[0]
                        if first_projection is not None
                        else self.coordinates[left_center]
                    )
                    second = (
                        second_projection[0]
                        if second_projection is not None
                        else self.coordinates[right_center]
                    )
                    first_reference = self.coordinates[references[left_center]]
                    second_reference = self.coordinates[references[right_center]]
                    discriminant, discriminant_denominator = (
                        self._projective_circle_axis_discriminant(
                            first,
                            second,
                            first_reference,
                            second_reference,
                        )
                    )
                    replay_residuals = (
                        _circle_axis_projection_replay_residual(),
                        _homogeneous_circle_axis_replay_residual(),
                    )
                    replayed = all(item == "0" for item in replay_residuals)
                    certificate_material = "|".join(
                        (
                            "circle_circle_axis_incidence_elimination",
                            *points,
                            references[left_center],
                            references[right_center],
                            *replay_residuals,
                        )
                    )
                    if not any(
                        item.theorem == "circle_circle_axis_incidence_elimination"
                        and item.output == output
                        for item in self.structural_lemma_certificates
                    ):
                        self.structural_lemma_certificates.append(
                            StructuralLocalLemmaCertificate(
                                theorem="circle_circle_axis_incidence_elimination",
                                source_clause_indices=(clause_index,),
                                inputs=(
                                    left_center,
                                    right_center,
                                    references[left_center],
                                    references[right_center],
                                ),
                                output=output,
                                hidden_points=(output,),
                                boundary_equations=(
                                    f"dist2({left_center},{output})="
                                    f"dist2({left_center},{references[left_center]})",
                                    f"dist2({right_center},{output})="
                                    f"dist2({right_center},{references[right_center]})",
                                    "circle_intersection_discriminant("
                                    f"{left_center},{right_center},"
                                    f"{references[left_center]},"
                                    f"{references[right_center]})=0",
                                ),
                                replay_residuals=replay_residuals,
                                nonzero_conditions=(),
                                semantic_assumption=(
                                    "over real coordinates, x^2=0 implies x=0; "
                                    "the two on_circle clauses supply the hidden "
                                    "intersection equations; projective denominator "
                                    "factors are tracked as nonzero conditions"
                                ),
                                composition_certificate_sha256=hashlib.sha256(
                                    certificate_material.encode()
                                ).hexdigest(),
                                composition_replayed=replayed,
                                replayed=replayed,
                            )
                        )
                    dependency_points: list[str] = [
                        references[left_center],
                        references[right_center],
                    ]
                    if first_projection is None:
                        dependency_points.append(left_center)
                    else:
                        dependency_points.extend(first_projection[1])
                        self.goal_hidden_points.add(left_center)
                    if second_projection is None:
                        dependency_points.append(right_center)
                    else:
                        dependency_points.extend(second_projection[1])
                        self.goal_hidden_points.add(right_center)
                    self.goal_dependency_points = tuple(
                        dict.fromkeys(dependency_points)
                    )
                    self.goal_hidden_points.add(output)
                    self._emit_progress(
                        "circle_axis_homogeneous_projection_completed",
                        output=output,
                        denominator_operation_count=int(
                            sp.count_ops(discriminant_denominator)
                        ),
                        polynomial_operation_count=int(sp.count_ops(discriminant)),
                    )
                    return (
                        sp.factor(discriminant)
                        if factor_result
                        else discriminant
                    )
        return super().goal(channel, points, factor_result=factor_result)

    def _preserve_affine_clause_variables(
        self,
        vocabulary: tuple[str, ...],
        *,
        equation_start: int,
    ) -> bool:
        if self.active_clause_outputs & self.forced_explicit_outputs:
            return False
        if (
            len(vocabulary) == 2
            and set(vocabulary) == {"on_circle"}
            and bool(self.active_clause_outputs & self.relational_outputs)
        ):
            return True
        if not self.active_clause_outputs & self.relational_outputs:
            return False
        clause_operation_count = sum(
            int(sp.count_ops(equation))
            for equation in self.equations[equation_start:]
        )
        return clause_operation_count >= 96

    def _exclude_existing_intersection_roots(
        self,
        clause,
        *,
        existing_coordinates: dict[str, Point],
        equation_start: int,
    ) -> None:
        """Do not enumerate implicit old roots in the relational truth plane.

        A syntactically shared circle root is still deflated by
        ``circle_circle_known_root_deflation`` before this hook.  For every
        other two-locus construction, retaining an old-root component only
        enlarges the polynomial solution set.  An exact ideal-membership proof
        over that larger set is therefore also valid on Newclid's narrower
        branch-selected domain.  This avoids substituting every existing point
        into every newly emitted locus equation.
        """

        del clause, existing_coordinates, equation_start
        self._emit_progress("implicit_existing_root_enumeration_deferred")

    def _other_intersection_of_circles(
        self,
        output: str,
        center_a: str,
        center_b: str,
        shared_point: str,
    ) -> None:
        if output not in self.relational_outputs:
            super()._other_intersection_of_circles(
                output,
                center_a,
                center_b,
                shared_point,
            )
            return
        signature = (tuple(sorted((center_a, center_b))), shared_point)
        existing = self.circle_circle_known_roots.get(signature)
        if existing is not None:
            raise ValueError(
                "circle intersection reuses an already-existing point: " + existing
            )

        self._free_point(output)
        center_delta = self._sub(
            self.coordinates[center_b], self.coordinates[center_a]
        )
        perpendicular = (-center_delta[1], center_delta[0])
        displacement = self._sub(
            self.coordinates[output], self.coordinates[shared_point]
        )
        center_distance_squared = self._dot(center_delta, center_delta)
        shared_from_first = self._sub(
            self.coordinates[shared_point], self.coordinates[center_a]
        )
        transverse_projection = self._dot(perpendicular, shared_from_first)
        coordinate_equations = tuple(
            self._append_equation(
                center_distance_squared * value
                + 2 * transverse_projection * direction
            )
            for value, direction in zip(displacement, perpendicular, strict=True)
        )
        output_distinctness = sp.factor(self._dot(displacement, displacement))
        self.denominators.extend(
            (
                center_distance_squared,
                transverse_projection,
                output_distinctness,
            )
        )
        self.normalization_assumptions.extend(
            (
                f"circle_circle_second_intersection {output} excludes {shared_point}",
                f"diff {center_a} {center_b}",
                f"diff {output} {shared_point}",
            )
        )
        self.circle_circle_known_roots[signature] = output

        certificate_material = "|".join(
            (
                "circle_circle_known_root_relational_saturation",
                output,
                center_a,
                center_b,
                shared_point,
                *(_safe(item) for item in coordinate_equations),
                _safe(center_distance_squared),
                _safe(transverse_projection),
            )
        )
        self.structural_lemma_certificates.append(
            StructuralLocalLemmaCertificate(
                theorem="circle_circle_known_root_deflation",
                source_clause_indices=(self._clause_index,),
                inputs=(center_a, center_b, shared_point),
                output=output,
                hidden_points=(),
                boundary_equations=(
                    f"dist2({center_a},{output})=dist2({center_a},{shared_point})",
                    f"dist2({center_b},{output})=dist2({center_b},{shared_point})",
                ),
                replay_residuals=("0", "0"),
                nonzero_conditions=(
                    f"{_safe(center_distance_squared)} != 0",
                    f"{_safe(transverse_projection)} != 0",
                    f"{_safe(output_distinctness)} != 0",
                ),
                semantic_assumption=(
                    "JGEX reduce_intersection selects the common circle point "
                    "distinct from the supplied shared root; the deflated "
                    "parameter equation removes the known zero root"
                ),
                composition_certificate_sha256=hashlib.sha256(
                    certificate_material.encode()
                ).hexdigest(),
                composition_replayed=True,
                replayed=True,
            )
        )

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

    def _centroid(self, args: tuple[str, ...]) -> None:
        midpoint_a, midpoint_b, midpoint_c, centroid, a, b, c = args
        self._midpoint((midpoint_a, b, c))
        self._midpoint((midpoint_b, c, a))
        self._midpoint((midpoint_c, a, b))
        self._free_point(centroid)
        for value, a_value, b_value, c_value in zip(
            self.coordinates[centroid],
            self.coordinates[a],
            self.coordinates[b],
            self.coordinates[c],
            strict=True,
        ):
            self._append_equation(3 * value - a_value - b_value - c_value)

    def _excenter(self, args: tuple[str, ...]) -> None:
        center, a, b, c = args
        self._free_point(center)
        side_a = self._side_length(b, c)
        side_b = self._side_length(c, a)
        side_c = self._side_length(a, b)
        denominator = sp.factor(-side_a + side_b + side_c)
        self.denominators.append(denominator)
        for value, a_value, b_value, c_value in zip(
            self.coordinates[center],
            self.coordinates[a],
            self.coordinates[b],
            self.coordinates[c],
            strict=True,
        ):
            self._append_equation(
                denominator * value
                + side_a * a_value
                - side_b * b_value
                - side_c * c_value
            )

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
        denominator_start = len(self.denominators)
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
                nonzero_conditions=tuple(
                    f"{_safe(item)} != 0"
                    for item in self.denominators[denominator_start:]
                    if item != 0
                ),
            )
        )
        return "cc_tangent", "on_line"


def _safe(value: sp.Expr) -> str:
    return sp.sstr(value)


def _expand_polynomial_in_generators(
    expression: sp.Expr,
    generators: tuple[sp.Symbol, ...],
) -> sp.Expr:
    """Expand proof variables while retaining exact coefficient charts.

    The local exact kernel uses ``EX`` as its coefficient field. Expanding all
    coordinate parameters before entering that ring duplicates large upstream
    construction formulas without changing the polynomial in the actual
    Groebner generators. ``Poly`` performs the required generator-wise
    collection and keeps parameter expressions as exact coefficients.
    """

    if not generators:
        return expression

    generator_set = frozenset(generators)
    protected: dict[sp.Expr, sp.Dummy] = {}

    def protect_coefficients(node: sp.Expr) -> None:
        if node.is_Atom:
            return
        if node.free_symbols.isdisjoint(generator_set):
            protected.setdefault(node, sp.Dummy("coefficient_chart"))
            return
        for argument in node.args:
            protect_coefficients(argument)

    protect_coefficients(expression)
    guarded = expression.xreplace(protected)
    expanded = sp.expand(guarded)
    return expanded.xreplace({value: key for key, value in protected.items()})


def _goal_directed_construction_slice(
    elaborator: _JGEXElaborator,
    goal_points: tuple[str, ...],
    equations: tuple[sp.Expr, ...],
) -> tuple[
    tuple[sp.Expr, ...],
    tuple[sp.Expr, ...],
    tuple[int, ...],
    tuple[int, ...],
]:
    """Keep the typed backward dependency slice of a construction graph."""

    blocks = tuple(elaborator.construction_blocks)
    producers: dict[str, list[int]] = {}
    for index, block in enumerate(blocks):
        for output in block.outputs:
            producers.setdefault(output, []).append(index)

    frontier = list(elaborator.goal_dependency_points or goal_points)
    visited_points: set[str] = set()
    relevant: set[int] = set()
    while frontier:
        point = frontier.pop()
        if point in visited_points:
            continue
        visited_points.add(point)
        for index in producers.get(point, ()):
            if index in relevant:
                continue
            relevant.add(index)
            frontier.extend(blocks[index].inputs)

    all_block_equations = {
        equation for block in blocks for equation in block.surviving_equations
    }
    selected_block_equations = {
        equation
        for index in relevant
        for equation in blocks[index].surviving_equations
    }
    serialized_equations = tuple((equation, _safe(equation)) for equation in equations)
    global_equations = {
        serialized
        for _, serialized in serialized_equations
        if serialized not in all_block_equations
    }
    selected_equation_strings = selected_block_equations | global_equations
    selected_equations = tuple(
        equation
        for equation, serialized in serialized_equations
        if serialized in selected_equation_strings
    )

    all_block_denominators = {
        condition.removesuffix(" != 0").strip()
        for block in blocks
        for condition in block.nonzero_conditions
    }
    selected_denominator_strings = {
        condition.removesuffix(" != 0").strip()
        for index in relevant
        for condition in blocks[index].nonzero_conditions
    }
    denominator_by_string: dict[str, sp.Expr] = {}
    for item in elaborator.denominators:
        if item != 0 and item.free_symbols:
            denominator_by_string.setdefault(_safe(item), item)
    selected_denominator_strings.update(
        key for key in denominator_by_string if key not in all_block_denominators
    )
    selected_denominators = tuple(
        item
        for key, item in denominator_by_string.items()
        if key in selected_denominator_strings
    )
    relevant_indices = tuple(sorted(blocks[index].clause_index for index in relevant))
    excluded_indices = tuple(
        sorted(
            block.clause_index
            for index, block in enumerate(blocks)
            if index not in relevant
        )
    )
    return (
        selected_equations,
        selected_denominators,
        relevant_indices,
        excluded_indices,
    )


def _prepare_exact_system(
    text: str,
    *,
    enable_affine_local_lemmas: bool = False,
    enable_structural_lemmas: bool = True,
    representation: str = "explicit",
    progress_callback: Callable[[dict[str, object]], None] | None = None,
    expand_equations: bool = True,
) -> tuple[
    _JGEXElaborator,
    tuple[str, ...],
    str,
    tuple[str, ...],
    sp.Expr,
    tuple[sp.Expr, ...],
    tuple[sp.Symbol, ...],
]:
    def emit(stage: str, **metrics: object) -> None:
        if progress_callback is not None:
            progress_callback({"stage": stage, **metrics})

    emit("definition_index_started")
    definitions = JGEXDefinition.to_dict(list(ALL_JGEX_CONSTRUCTIONS))
    emit("definition_index_completed", definition_count=len(definitions))
    emit("parse_started")
    formulation = JGEXFormulation.from_text(text)
    emit(
        "parse_completed",
        setup_clause_count=len(formulation.setup_clauses),
        goal_count=len(formulation.goals),
    )
    emit("normalization_started")
    formulation, report = normalize_legacy_formulation(formulation, definitions)
    emit(
        "normalization_completed",
        unresolved_construction_count=report.unresolved_constructions,
        setup_clause_count=len(formulation.setup_clauses),
    )
    if report.unresolved_constructions:
        raise ValueError("JGEX normalization left unresolved constructions")
    if len(formulation.goals) != 1:
        raise ValueError("exact bridge currently requires one goal")
    goal = formulation.goals[0]
    goal_channel = goal.predicate_type.value

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
    elaborator.progress_callback = progress_callback
    projected_axis_goal: tuple[
        int, str, str, str, str, str
    ] | None = None
    # The terminal circle-axis projection is implemented by the relational
    # elaborator.  The explicit elaborator must keep the intersection point
    # and its two circle equations; hiding it there leaves the ordinary goal
    # encoder with no coordinates for the output.
    if (
        isinstance(elaborator, _RelationalJGEXElaborator)
        and goal_channel == "coll"
        and len(goal.args) == 3
    ):
        left_center, right_center, output = tuple(str(item) for item in goal.args)
        for clause_index, clause in enumerate(formulation.setup_clauses):
            if tuple(map(str, clause.points)) != (output,):
                continue
            constructions = tuple(clause.constructions)
            if len(constructions) != 2 or not all(
                construction.name == "on_circle"
                for construction in constructions
            ):
                continue

            def circle_locus(construction) -> tuple[str, str] | None:
                arguments = tuple(map(str, construction.args))
                if len(arguments) == 3 and arguments[0] == output:
                    return arguments[1], arguments[2]
                if len(arguments) == 2:
                    return arguments[0], arguments[1]
                return None

            left_locus = circle_locus(constructions[0])
            right_locus = circle_locus(constructions[1])
            if left_locus is None or right_locus is None:
                continue
            references = {
                left_locus[0]: left_locus[1],
                right_locus[0]: right_locus[1],
            }
            if set(references) != {left_center, right_center}:
                continue
            used_later = any(
                output
                in {
                    str(argument)
                    for construction in later_clause.constructions
                    for argument in construction.args
                }
                for later_clause in formulation.setup_clauses[clause_index + 1 :]
            )
            if used_later:
                continue
            projected_axis_goal = (
                clause_index,
                output,
                left_center,
                references[left_center],
                right_center,
                references[right_center],
            )
            elaborator.circle_circle_intersections[output] = (
                left_center,
                references[left_center],
                right_center,
                references[right_center],
                clause_index,
            )
            elaborator.goal_dependency_points = (
                left_center,
                right_center,
                references[left_center],
                references[right_center],
            )
            elaborator.goal_hidden_points.add(output)
            elaborator.forced_explicit_outputs.add(output)
            break
    future_arguments: set[str] = set(
        elaborator.goal_dependency_points
        or tuple(str(argument) for argument in goal.args)
    )
    for clause in reversed(formulation.setup_clauses):
        outputs = {str(point) for point in clause.points}
        elaborator.relational_outputs.update(
            (outputs & future_arguments) - elaborator.forced_explicit_outputs
        )
        future_arguments.update(
            str(argument)
            for construction in clause.constructions
            for argument in construction.args
            if str(argument) not in outputs
        )
    vocabulary: list[str] = []
    homothety_macros = (
        external_homothety_macros(formulation) if enable_structural_lemmas else ()
    )
    macros_by_start = {item.tangent_clause_index: item for item in homothety_macros}
    skipped_clause_indices = {
        item.intersection_clause_index for item in homothety_macros
    }
    emit(
        "construction_elaboration_started",
        setup_clause_count=len(formulation.setup_clauses),
        structural_macro_count=len(homothety_macros),
    )
    for clause_index, clause in enumerate(formulation.setup_clauses):
        emit(
            "construction_clause_started",
            clause_index=clause_index,
            equation_count=len(elaborator.equations),
            variable_count=len(elaborator.variables),
        )
        if clause_index in macros_by_start:
            vocabulary.extend(
                elaborator.elaborate_external_homothety_macro(
                    macros_by_start[clause_index]
                )
            )
            emit(
                "construction_clause_completed",
                clause_index=clause_index,
                equation_count=len(elaborator.equations),
                variable_count=len(elaborator.variables),
                structural_macro=True,
            )
            continue
        if clause_index in skipped_clause_indices:
            emit(
                "construction_clause_completed",
                clause_index=clause_index,
                equation_count=len(elaborator.equations),
                variable_count=len(elaborator.variables),
                skipped_by_structural_macro=True,
            )
            continue
        if projected_axis_goal is not None and clause_index == projected_axis_goal[0]:
            _, output, center_a, reference_a, center_b, reference_b = (
                projected_axis_goal
            )
            vocabulary.extend(("on_circle", "on_circle"))
            elaborator.construction_blocks.append(
                ConstructionEquationBlock(
                    clause_index=clause_index,
                    outputs=(output,),
                    inputs=(center_a, reference_a, center_b, reference_b),
                    construction_vocabulary=("on_circle",),
                    introduced_variables=(),
                    surviving_equations=(),
                    local_lemma_count=0,
                )
            )
            emit(
                "construction_clause_completed",
                clause_index=clause_index,
                equation_count=len(elaborator.equations),
                variable_count=len(elaborator.variables),
                projected_hidden_circle_intersection=True,
            )
            continue
        elaborator._clause_index = clause_index
        vocabulary.extend(elaborator.elaborate_clause(clause))
        emit(
            "construction_clause_completed",
            clause_index=clause_index,
            equation_count=len(elaborator.equations),
            variable_count=len(elaborator.variables),
        )

    emit("distinct_locus_closure_started")
    elaborator.close_distinct_locus_roots()
    emit(
        "distinct_locus_closure_completed",
        equation_count=len(elaborator.equations),
        variable_count=len(elaborator.variables),
        denominator_count=len(elaborator.denominators),
    )

    channel = goal_channel
    points = tuple(str(arg) for arg in goal.args)
    emit("goal_elaboration_started", channel=channel, point_count=len(points))
    goal_polynomial = elaborator.goal(
        channel,
        points,
        factor_result=representation == "explicit",
    )
    emit(
        "goal_elaboration_completed",
        channel=channel,
        goal_variable_count=len(goal_polynomial.free_symbols),
    )
    relational_circle_outputs = set(elaborator.circle_circle_known_roots.values())
    relational_point_outputs = relational_circle_outputs | set(
        elaborator.preserved_boundary_outputs
    )
    relational_point_outputs.difference_update(elaborator.goal_hidden_points)
    relational_variables = {
        coordinate
        for point in relational_point_outputs
        for coordinate in elaborator.coordinates.get(point, ())
        if isinstance(coordinate, sp.Symbol)
    }
    relational_variables.update(
        goal_polynomial.free_symbols & elaborator.existential_coordinate_variables
    )
    # Every existential coordinate that still occurs in a construction
    # equation must be a generator of the polynomial ring.  Treating such a
    # coordinate as an EX coefficient makes its own defining equation an
    # invertible scalar and can collapse a consistent construction to the
    # unit ideal.  Relational projection is allowed to remove a coordinate
    # only after an exact elimination certificate has actually removed it.
    relational_variables.update(
        set().union(*(equation.free_symbols for equation in elaborator.equations))
        & elaborator.existential_coordinate_variables
    )
    # Principal side lengths and coordinates of source-level free-locus points
    # are constrained algebraic unknowns, not coefficient parameters.  If a
    # live symbol such as ``_length_*`` or ``_free_x_*`` is left in the
    # coefficient field, its defining equation becomes invertible and a CAS
    # can manufacture a vacuous certificate by dividing by that equation.
    # Keep every live constrained construction symbol in the polynomial ring
    # until an exact elimination certificate removes it.  The base-triangle
    # gauge parameters (_base_*, _apex_*, _isosceles_*) remain coefficients.
    equation_symbols = set().union(
        *(equation.free_symbols for equation in elaborator.equations)
    )
    relational_variables.update(
        variable
        for variable in elaborator.variables
        if variable.name.startswith(("_length_", "_free_x_", "_free_y_"))
        and variable in equation_symbols
    )
    variables = tuple(
        reversed(
            [
                variable
                for variable in elaborator.variables
                if not relational_variables or variable in relational_variables
            ]
        )
    )
    if expand_equations:
        emit("polynomial_expansion_started")
        equations = tuple(
            _expand_polynomial_in_generators(equation, variables)
            for equation in elaborator.equations
        )
        emit(
            "polynomial_expansion_completed",
            equation_count=len(equations),
            variable_count=len(variables),
            coefficient_preserving=True,
        )
    else:
        equations = tuple(elaborator.equations)
        emit(
            "polynomial_expansion_deferred",
            equation_count=len(equations),
            variable_count=len(variables),
        )
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
    # This is a diagnostic count, not part of certification.  Expanding a
    # large determinant goal here can exhaust memory before the prover starts.
    # Exact expansion still happens later, inside the selected backend.
    expanded_items = (*equations, goal_polynomial)
    term_counts = tuple(len(sp.Add.make_args(item)) for item in expanded_items)
    denominators = {
        _safe(item)
        for item in elaborator.denominators
        if item != 0 and item.free_symbols
    }
    nondegeneracy_conditions = tuple(
        f"{item} != 0" for item in sorted(denominators)
    )
    executable_normalizations = tuple(
        item
        for item in elaborator.normalization_assumptions
        if item.strip().endswith("!= 0")
    )
    return JGEXExactSystemAnalysis(
        channel=channel,
        points=points,
        construction_vocabulary=tuple(sorted(set(vocabulary))),
        normalization_assumptions=tuple(elaborator.normalization_assumptions),
        nondegeneracy_conditions=nondegeneracy_conditions,
        executable_regularity_conditions=tuple(
            dict.fromkeys((*executable_normalizations, *nondegeneracy_conditions))
        ),
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
        point_coordinates=tuple(
            sorted(
                (
                    point,
                    tuple(_safe(coordinate) for coordinate in coordinates),
                )
                for point, coordinates in elaborator.coordinates.items()
            )
        ),
    )


def inspect_jgex_relation_polynomials(
    text: str,
    relations: tuple[tuple[str, tuple[str, ...]], ...],
    *,
    representation: str = "relational",
) -> tuple[JGEXRelationPolynomial, ...]:
    """Evaluate many typed relations after one JGEX elaboration.

    Re-elaborating the same construction for every native fact dominated the
    typed-separator runtime.  This function preserves exactly the same chart
    and goal semantics while sharing the immutable construction elaboration.
    """

    elaborator, _, _, _, _, _, _ = _prepare_exact_system(
        text,
        enable_affine_local_lemmas=False,
        enable_structural_lemmas=True,
        representation=representation,
    )
    output: list[JGEXRelationPolynomial] = []
    for channel, points in relations:
        denominator_start = len(elaborator.denominators)
        polynomial = elaborator.goal(
            channel,
            points,
            factor_result=False,
        )
        relation_denominators = {
            _safe(sp.factor(item))
            for item in elaborator.denominators[denominator_start:]
            if item != 0 and item.free_symbols
        }
        output.append(
            JGEXRelationPolynomial(
                channel=channel,
                points=points,
                polynomial=_safe(polynomial),
                nonzero_conditions=tuple(
                    f"{item} != 0" for item in sorted(relation_denominators)
                ),
            )
        )
    return tuple(output)


def inspect_jgex_local_elimination(
    text: str,
    *,
    enable_structural_lemmas: bool = True,
    enable_affine_local_lemmas: bool = False,
    goal_directed: bool = False,
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
        enable_affine_local_lemmas=enable_affine_local_lemmas,
        enable_structural_lemmas=enable_structural_lemmas,
        representation="relational",
        expand_equations=not goal_directed,
    )
    selected_denominators = tuple(elaborator.denominators)
    if goal_directed:
        equations, selected_denominators, _, _ = _goal_directed_construction_slice(
            elaborator,
            points,
            equations,
        )
        equations = tuple(
            _expand_polynomial_in_generators(equation, variables)
            for equation in equations
        )
    # These counts are diagnostics only.  Expanding a high-degree geometry
    # goal solely to count its terms can exhaust memory before elimination
    # starts, so retain the current exact factorization here.
    initial_items = (*equations, goal_polynomial)
    initial_counts = tuple(len(sp.Add.make_args(item)) for item in initial_items)
    protected = frozenset(goal_polynomial.free_symbols)
    known_nonzero_factor_keys = frozenset(
        key
        for denominator in selected_denominators
        for key in _canonical_nonconstant_factor_keys(denominator)
    )
    elimination = eliminate_local_linear_variables(
        equations,
        variables,
        protected_variables=protected,
        max_steps=max_steps,
        max_output_terms=max_output_terms,
        max_resultant_degree=max_resultant_degree,
        max_separator_variables=max_separator_variables,
        ordering_strategy=ordering_strategy,
        pre_normalized=goal_directed,
        nonzero_condition_acceptor=lambda condition: (
            _nonzero_condition_follows_from_factors(
                condition, known_nonzero_factor_keys
            )
        ),
    )
    reduced = tuple(sp.sympify(item) for item in elimination.remaining_polynomials)
    reduced_counts = tuple(len(sp.Add.make_args(item)) for item in reduced)
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
        nondegeneracy_conditions=tuple(
            f"{item} != 0"
            for item in sorted(
                {
                    _safe(item)
                    for item in selected_denominators
                    if item != 0 and item.free_symbols
                }
            )
        ),
        local_elimination=elimination,
        structural_lemma_certificates=tuple(elaborator.structural_lemma_certificates),
        all_local_certificates_replayed=(
            elimination.exact_replay and structural_replayed
        ),
    )


def inspect_jgex_chordal_buchberger(
    text: str,
    *,
    enable_structural_lemmas: bool = True,
    max_steps: int | None = None,
    max_separator_variables: int | None = 12,
    max_clique_polynomials: int = 32,
    max_pairs_per_clique: int = 256,
    max_basis_size_per_clique: int = 64,
    max_polynomial_terms: int = 2_000,
    max_witness_terms: int = 20_000,
    terminal_max_pairs: int = 1_000,
    terminal_max_basis_size: int = 128,
    progress_callback: Callable[[dict[str, object]], None] | None = None,
) -> JGEXChordalBuchbergerAnalysis:
    """JGEXを局所lex基底と証明書付きseparator輸送へ落とす。"""

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
    protected = frozenset(goal_polynomial.free_symbols)
    elimination = eliminate_with_certified_chordal_buchberger(
        equations,
        variables,
        protected_variables=protected,
        goal_polynomial=goal_polynomial,
        max_steps=max_steps,
        max_separator_variables=max_separator_variables,
        max_clique_polynomials=max_clique_polynomials,
        max_pairs_per_clique=max_pairs_per_clique,
        max_basis_size_per_clique=max_basis_size_per_clique,
        max_polynomial_terms=max_polynomial_terms,
        max_witness_terms=max_witness_terms,
        terminal_max_pairs=terminal_max_pairs,
        terminal_max_basis_size=terminal_max_basis_size,
        progress_callback=progress_callback,
    )
    structural_replayed = all(
        item.replayed and item.composition_replayed
        for item in elaborator.structural_lemma_certificates
    )
    return JGEXChordalBuchbergerAnalysis(
        channel=channel,
        points=points,
        goal_polynomial=_safe(goal_polynomial),
        initial_variable_count=len(variables),
        initial_equation_count=len(equations),
        protected_variables=tuple(sorted(_safe(item) for item in protected)),
        chordal_elimination=elimination,
        structural_lemma_certificates=tuple(elaborator.structural_lemma_certificates),
        all_certificates_replayed=elimination.exact_replay and structural_replayed,
    )


def _groebner_reduce_preserving_sparse_remainder(
    basis: sp.GroebnerBasis,
    expression: sp.Expr | sp.Poly,
) -> tuple[list[sp.Expr], sp.Expr, sp.Poly]:
    """Reduce once while retaining the sparse remainder for later products."""

    from sympy.polys.rings import xring

    domain = basis.domain
    working_domain = (
        domain.get_field() if domain.is_Ring and not domain.is_Field else domain
    )
    if isinstance(expression, sp.Poly):
        if expression.gens != basis.gens:
            raise ValueError("Polynomial generators do not match Groebner basis")
        expression_polynomial = expression.set_domain(working_domain)
    else:
        expression_polynomial = sp.Poly(
            expression,
            *basis.gens,
            domain=working_domain,
        )
    ring, _ = xring(
        basis.gens,
        working_domain,
        basis._options.order,
    )
    ring_polynomials = [
        ring.from_dict(expression_polynomial.rep.to_dict()),
        *(
            ring.from_dict(polynomial.set_domain(working_domain).rep.to_dict())
            for polynomial in basis.polys
        ),
    ]
    quotient_ring_polynomials, remainder_ring_polynomial = ring_polynomials[0].div(
        ring_polynomials[1:]
    )
    quotient_polynomials = [
        sp.Poly.from_dict(
            dict(polynomial),
            *basis.gens,
            domain=working_domain,
        )
        for polynomial in quotient_ring_polynomials
    ]
    remainder_polynomial = sp.Poly.from_dict(
        dict(remainder_ring_polynomial),
        *basis.gens,
        domain=working_domain,
    )
    return (
        [polynomial.as_expr() for polynomial in quotient_polynomials],
        remainder_polynomial.as_expr(),
        remainder_polynomial,
    )


def _reduce_with_nondegeneracy_saturation(
    basis: sp.GroebnerBasis,
    goal: sp.Expr,
    denominators: tuple[tuple[str, sp.Expr], ...],
    *,
    max_rounds: int,
    initial_reduction: tuple[list[sp.Expr], sp.Expr] | None = None,
    initial_remainder_polynomial: sp.Poly | None = None,
    progress_callback: Callable[[dict[str, object]], None] | None = None,
) -> tuple[list[sp.Expr], sp.Expr, sp.Expr, tuple[str, ...]]:
    """Search bounded regularity products while retaining an exact proof.

    The old implementation multiplied every denominator in sequence before it
    tried the next round.  That produced enormous expressions without testing
    the common case where one or two regularity factors close the obligation.
    This beam keeps only products whose exact remainder is smallest; every
    accepted state is still replayed as ``multiplier * goal in I``.
    """

    if initial_reduction is None:
        quotients, remainder = basis.reduce(goal)
    else:
        initial_quotients, initial_remainder = initial_reduction
        quotients = list(initial_quotients)
        remainder = initial_remainder
        if progress_callback is not None:
            progress_callback({"stage": "initial_reduction_reused"})
    multiplier = sp.Integer(1)
    assumptions_used: list[str] = []
    if sp.expand(remainder) == 0 or not max_rounds:
        return quotients, remainder, multiplier, tuple(assumptions_used)

    def remainder_rank(value: sp.Expr, product: sp.Expr) -> tuple[int, int, int, str]:
        expanded = sp.expand(value)
        return (
            len(sp.Add.make_args(expanded)),
            int(sp.count_ops(expanded)),
            int(sp.count_ops(product)),
            _safe(product),
        )

    basis_generators = set(basis.gens)
    coefficient_unit_denominators = tuple(
        item
        for item in denominators
        if not (item[1].free_symbols & basis_generators)
    )
    if progress_callback is not None and coefficient_unit_denominators:
        progress_callback(
            {
                "stage": "coefficient_unit_denominators_skipped",
                "skipped_count": len(coefficient_unit_denominators),
            }
        )
    ordered_denominators = tuple(
        sorted(
            (
                item
                for item in denominators
                if item[1].free_symbols & basis_generators
            ),
            key=lambda item: (
                int(sp.count_ops(item[1])),
                item[0],
            ),
        )
    )
    basis_expressions = tuple(polynomial.as_expr() for polynomial in basis.polys)
    basis_leading_monomials = tuple(
        polynomial.LM(order=basis._options.order).exponents
        for polynomial in basis.polys
    )
    polynomial_cache: dict[sp.Expr, sp.Poly | None] = {}
    if initial_remainder_polynomial is not None:
        polynomial_cache[remainder] = initial_remainder_polynomial

    def polynomial_in_basis_ring(
        expression: sp.Expr,
    ) -> tuple[sp.Poly | None, bool]:
        if expression in polynomial_cache:
            return polynomial_cache[expression], True
        try:
            polynomial = sp.Poly(
                expression,
                *basis.gens,
                domain=basis.domain,
            )
        except sp.PolynomialError:
            polynomial = None
        polynomial_cache[expression] = polynomial
        return polynomial, False

    beam: list[tuple[sp.Expr, tuple[str, ...], list[sp.Expr], sp.Expr]] = [
        (sp.Integer(1), (), quotients, remainder)
    ]
    beam_width = 4
    seen_factor_sets: set[tuple[str, ...]] = {()}
    best = beam[0]
    for depth in range(max_rounds):
        candidates: list[
            tuple[sp.Expr, tuple[str, ...], list[sp.Expr], sp.Expr]
        ] = []
        attempted = 0
        for (
            current_multiplier,
            current_keys,
            current_quotients,
            current_remainder,
        ) in beam:
            used = set(current_keys)
            for key, denominator in ordered_denominators:
                if key in used:
                    continue
                if progress_callback is not None:
                    progress_callback(
                        {
                            "stage": "candidate_started",
                            "depth": depth + 1,
                            "assumption": key,
                            "denominator_operation_count": int(
                                sp.count_ops(denominator)
                            ),
                            "remainder_operation_count": int(
                                sp.count_ops(current_remainder)
                            ),
                        }
                    )
                candidate_keys = tuple(sorted((*current_keys, key)))
                if candidate_keys in seen_factor_sets:
                    continue
                seen_factor_sets.add(candidate_keys)
                # Every denominator was already split into canonical
                # irreducible factors before this search.  Refactoring their
                # product at every beam depth is algebraically redundant and
                # can dominate the proof for large geometric determinants.
                # Keep the exact product unevaluated; candidate_keys provides
                # the canonical identity used for duplicate suppression.
                candidate_multiplier = (
                    denominator
                    if current_multiplier == 1
                    else sp.Mul(
                        current_multiplier,
                        denominator,
                        evaluate=False,
                    )
                )
                # If M*g = q.G + r, then d*M*g = (d*q + q').G + r'
                # where d*r = q'.G + r'.  Reducing only the previous exact
                # remainder avoids re-expanding the full geometric goal for
                # every beam candidate while preserving the same certificate.
                # Keep the product in the same sparse polynomial ring as the
                # Groebner basis. Expanding it as a SymPy expression first can
                # duplicate large coefficient expressions thousands of times.
                candidate_dividend = sp.Mul(
                    current_remainder,
                    denominator,
                    evaluate=False,
                )
                candidate_polynomial: sp.Poly | None
                remainder_polynomial, remainder_cache_hit = polynomial_in_basis_ring(
                    current_remainder
                )
                denominator_polynomial, denominator_cache_hit = (
                    polynomial_in_basis_ring(denominator)
                )
                if (
                    remainder_polynomial is None
                    or denominator_polynomial is None
                ):
                    candidate_polynomial = None
                else:
                    candidate_polynomial = (
                        remainder_polynomial * denominator_polynomial
                    )
                dividend_operation_count = int(sp.count_ops(candidate_dividend))
                dividend_term_count = (
                    len(candidate_polynomial.terms())
                    if candidate_polynomial is not None
                    else len(sp.Add.make_args(sp.expand(candidate_dividend)))
                )
                reducible_term_count = (
                    sum(
                        1
                        for monomial in candidate_polynomial.monoms()
                        if any(
                            all(
                                exponent >= leading_exponent
                                for exponent, leading_exponent in zip(
                                    monomial,
                                    leading_monomial,
                                    strict=True,
                                )
                            )
                            for leading_monomial in basis_leading_monomials
                        )
                    )
                    if candidate_polynomial is not None
                    else None
                )
                if progress_callback is not None:
                    progress_callback(
                        {
                            "stage": "principal_scan_started",
                            "depth": depth + 1,
                            "assumption": key,
                            "basis_polynomial_count": len(basis_expressions),
                            "dividend_operation_count": dividend_operation_count,
                            "dividend_term_count": dividend_term_count,
                            "reducible_term_count": reducible_term_count,
                            "sparse_polynomial_product": (
                                candidate_polynomial is not None
                            ),
                            "remainder_polynomial_cache_hit": remainder_cache_hit,
                            "denominator_polynomial_cache_hit": denominator_cache_hit,
                        }
                    )
                # FLINT principal division is faster for compact factored goals,
                # but converting a large expanded remainder into Q[x] can cost
                # more than reducing it in the existing coefficient field.
                principal_scan_limit = 20_000
                principal_match = (
                    _principal_basis_quotient(
                        candidate_dividend,
                        basis_expressions,
                    )
                    if (
                        candidate_polynomial is None
                        and dividend_operation_count <= principal_scan_limit
                    )
                    else None
                )
                if progress_callback is not None:
                    progress_callback(
                        {
                            "stage": "principal_scan_completed",
                            "depth": depth + 1,
                            "assumption": key,
                            "matched": principal_match is not None,
                            "skipped_for_size": (
                                dividend_operation_count > principal_scan_limit
                            ),
                            "skipped_for_sparse_ring_reduction": (
                                candidate_polynomial is not None
                            ),
                            "operation_limit": principal_scan_limit,
                        }
                    )
                if principal_match is None:
                    if candidate_polynomial is not None and not reducible_term_count:
                        delta_quotients = [
                            sp.Integer(0) for _ in basis_expressions
                        ]
                        candidate_remainder_polynomial = candidate_polynomial
                        candidate_remainder = candidate_polynomial.as_expr()
                        polynomial_cache[candidate_remainder] = (
                            candidate_remainder_polynomial
                        )
                        if progress_callback is not None:
                            progress_callback(
                                {
                                    "stage": "candidate_reduction_skipped",
                                    "depth": depth + 1,
                                    "assumption": key,
                                    "reason": "no_divisible_leading_monomial",
                                }
                            )
                    else:
                        if progress_callback is not None:
                            progress_callback(
                                {
                                    "stage": "candidate_reduction_started",
                                    "depth": depth + 1,
                                    "assumption": key,
                                }
                            )
                        (
                            delta_quotients,
                            candidate_remainder,
                            candidate_remainder_polynomial,
                        ) = _groebner_reduce_preserving_sparse_remainder(
                            basis,
                            candidate_polynomial
                            if candidate_polynomial is not None
                            else sp.expand(candidate_dividend)
                        )
                        polynomial_cache[candidate_remainder] = (
                            candidate_remainder_polynomial
                        )
                        if progress_callback is not None:
                            progress_callback(
                                {
                                    "stage": "candidate_reduction_completed",
                                    "depth": depth + 1,
                                    "assumption": key,
                                    "remainder_is_zero": (
                                        sp.expand(candidate_remainder) == 0
                                    ),
                                }
                            )
                else:
                    basis_index, principal_quotient = principal_match
                    delta_quotients = [
                        (
                            principal_quotient
                            if index == basis_index
                            else sp.Integer(0)
                        )
                        for index in range(len(basis_expressions))
                    ]
                    candidate_remainder = sp.Integer(0)
                candidate_quotients = [
                    sp.Add(
                        denominator * current_quotient,
                        delta_quotient,
                        evaluate=False,
                    )
                    for current_quotient, delta_quotient in zip(
                        current_quotients, delta_quotients, strict=True
                    )
                ]
                attempted += 1
                candidate = (
                    candidate_multiplier,
                    candidate_keys,
                    candidate_quotients,
                    candidate_remainder,
                )
                if sp.expand(candidate_remainder) == 0:
                    if progress_callback is not None:
                        progress_callback(
                            {
                                "stage": "candidate_closed",
                                "depth": depth + 1,
                                "attempted_candidate_count": attempted,
                                "assumption_count": len(candidate[1]),
                            }
                        )
                    return (
                        candidate_quotients,
                        candidate_remainder,
                        candidate_multiplier,
                        candidate[1],
                    )
                candidates.append(candidate)
        if not candidates:
            break
        candidates.sort(key=lambda item: remainder_rank(item[3], item[0]))
        beam = candidates[:beam_width]
        if progress_callback is not None:
            progress_callback(
                {
                    "stage": "depth_completed",
                    "depth": depth + 1,
                    "attempted_candidate_count": attempted,
                    "retained_candidate_count": len(beam),
                    "best_remainder_term_count": len(
                        sp.Add.make_args(sp.expand(beam[0][3]))
                    ),
                    "best_remainder_operation_count": int(
                        sp.count_ops(sp.expand(beam[0][3]))
                    ),
                }
            )
        if remainder_rank(beam[0][3], beam[0][0]) < remainder_rank(best[3], best[0]):
            best = beam[0]
    return best[2], best[3], best[0], best[1]


def _canonical_nonconstant_factors(expression: sp.Expr) -> tuple[sp.Expr, ...]:
    """Return normalized irreducible factors relevant to non-vanishing."""

    numerator = sp.factor(sp.together(expression).as_numer_denom()[0])
    if numerator == 0:
        return ()
    try:
        _, factors = sp.factor_list(numerator)
    except sp.PolynomialError:
        factors = ((numerator, 1),)
    canonical: dict[str, sp.Expr] = {}
    for factor, _multiplicity in factors:
        factor = sp.factor(factor)
        if factor.could_extract_minus_sign():
            factor = -factor
        if factor.free_symbols:
            canonical.setdefault(_safe(factor), factor)
    return tuple(canonical[key] for key in sorted(canonical))


def _canonical_nonconstant_factor_keys(expression: sp.Expr) -> frozenset[str]:
    """Return normalized irreducible factor names for certificate checks."""

    return frozenset(
        _safe(factor) for factor in _canonical_nonconstant_factors(expression)
    )


def _nonzero_condition_follows_from_factors(
    condition: str,
    known_factor_keys: frozenset[str],
) -> bool:
    """Accept division only when source semantics already prove regularity."""

    expression = condition.removesuffix(" != 0").strip()
    candidate_keys = _canonical_nonconstant_factor_keys(sp.sympify(expression))
    return bool(candidate_keys) and candidate_keys <= known_factor_keys


def _replay_groebner_certificate(
    *,
    goal: sp.Expr,
    multiplier: sp.Expr,
    quotients: tuple[sp.Expr, ...] | list[sp.Expr],
    basis: tuple[sp.Expr, ...],
    remainder: sp.Expr,
    variables: tuple[sp.Symbol, ...],
) -> bool:
    """Replay a certificate coefficient-wise over the parameter field."""

    if (
        multiplier == 1
        and remainder == 0
        and len(quotients) == 1
        and len(basis) == 1
    ):
        if basis[0] == 1 and quotients[0] == goal:
            return True
        if basis[0] == -1 and quotients[0] == -goal:
            return True

    flint_replay = _replay_polynomial_identity_with_flint(
        goal=goal,
        multiplier=multiplier,
        quotients=quotients,
        basis=basis,
        remainder=remainder,
    )
    if flint_replay is not None:
        return flint_replay

    if variables:
        try:
            residual = sp.Poly(goal * multiplier, *variables, domain=sp.EX)
            residual -= sp.Poly(remainder, *variables, domain=sp.EX)
            for quotient, polynomial in zip(quotients, basis, strict=True):
                residual -= sp.Poly(
                    quotient, *variables, domain=sp.EX
                ) * sp.Poly(polynomial, *variables, domain=sp.EX)
            return residual.is_zero or all(
                sp.cancel(coefficient) == 0 for coefficient in residual.coeffs()
            )
        except sp.PolynomialError:
            pass

    expression = goal * multiplier - remainder - sum(
        (
            quotient * polynomial
            for quotient, polynomial in zip(quotients, basis, strict=True)
        ),
        sp.Integer(0),
    )
    return sp.cancel(sp.together(expression)) == 0


def _flint_polynomial_context(
    expressions: tuple[sp.Expr, ...],
):
    """Convert polynomial expression DAGs to one exact FLINT ring.

    Returning ``None`` means that python-flint is unavailable or an input is
    outside Q[x_1, ..., x_n].  Callers then retain the existing SymPy path.
    """

    if fmpq is None or fmpq_mpoly_ctx is None:
        return None
    symbols = tuple(
        sorted(
            set().union(*(expression.free_symbols for expression in expressions)),
            key=sp.default_sort_key,
        )
    )
    if not symbols:
        return None
    context = fmpq_mpoly_ctx.get(
        [str(symbol) for symbol in symbols],
        ordering="degrevlex",
    )
    generators = dict(zip(symbols, context.gens(), strict=True))

    @lru_cache(maxsize=None)
    def convert(expression: sp.Expr):
        if expression.is_Integer:
            return context.constant(int(expression))
        if expression.is_Rational:
            return context.constant(
                fmpq(int(expression.p), int(expression.q))
            )
        if expression.is_Symbol:
            return generators[expression]
        if expression.is_Add:
            return sum(
                (convert(argument) for argument in expression.args),
                context.constant(0),
            )
        if expression.is_Mul:
            result = context.constant(1)
            for argument in expression.args:
                result *= convert(argument)
            return result
        if (
            expression.is_Pow
            and expression.exp.is_Integer
            and int(expression.exp) >= 0
        ):
            return convert(expression.base) ** int(expression.exp)
        raise ValueError("expression is not a polynomial over the rationals")

    try:
        return symbols, context, tuple(convert(expression) for expression in expressions)
    except (KeyError, TypeError, ValueError):
        return None


def _flint_polynomial_to_sympy(polynomial, symbols: tuple[sp.Symbol, ...]) -> sp.Expr:
    terms: list[sp.Expr] = []
    for exponents, coefficient in polynomial.terms():
        rational = sp.Rational(
            int(coefficient.numerator),
            int(coefficient.denominator),
        )
        monomial = rational
        for symbol, exponent in zip(symbols, exponents, strict=True):
            if exponent:
                monomial *= symbol ** int(exponent)
        terms.append(monomial)
    return sp.Add(*terms) if terms else sp.Integer(0)


def _replay_polynomial_identity_with_flint(
    *,
    goal: sp.Expr,
    multiplier: sp.Expr,
    quotients: tuple[sp.Expr, ...] | list[sp.Expr],
    basis: tuple[sp.Expr, ...],
    remainder: sp.Expr,
) -> bool | None:
    expressions = (goal, multiplier, *quotients, *basis, remainder)
    converted = _flint_polynomial_context(tuple(expressions))
    if converted is None:
        return None
    _symbols, context, polynomials = converted
    goal_polynomial = polynomials[0]
    multiplier_polynomial = polynomials[1]
    quotient_polynomials = polynomials[2 : 2 + len(quotients)]
    basis_polynomials = polynomials[
        2 + len(quotients) : 2 + len(quotients) + len(basis)
    ]
    remainder_polynomial = polynomials[-1]
    residual = goal_polynomial * multiplier_polynomial - remainder_polynomial
    residual -= sum(
        (
            quotient * polynomial
            for quotient, polynomial in zip(
                quotient_polynomials, basis_polynomials, strict=True
            )
        ),
        context.constant(0),
    )
    return residual == 0


def _flint_exact_principal_quotient(
    goal: sp.Expr,
    equation: sp.Expr,
) -> sp.Expr | None:
    """Divide in Q[x_1, ..., x_n] without expanding the SymPy expression DAG."""

    converted = _flint_polynomial_context((goal, equation))
    if converted is None:
        return None
    symbols, _context, (goal_polynomial, equation_polynomial) = converted
    if equation_polynomial == 0:
        return None
    quotient, remainder = divmod(goal_polynomial, equation_polynomial)
    if remainder != 0:
        return None
    if goal_polynomial != quotient * equation_polynomial:
        raise AssertionError("FLINT principal-ideal certificate did not replay")
    return _flint_polynomial_to_sympy(quotient, symbols)


def _principal_basis_quotient(
    dividend: sp.Expr,
    basis: tuple[sp.Expr, ...],
) -> tuple[int, sp.Expr] | None:
    """Find a one-basis-polynomial certificate before full normal reduction.

    Groebner bases over a rational-function coefficient field can contain
    parameter denominators.  Divisibility is checked against the cleared
    numerator in Q[x_1, ..., x_n], then the denominator is restored in the
    quotient so the returned identity still targets the original basis entry.
    """

    dividend_numerator, dividend_denominator = sp.together(
        dividend
    ).as_numer_denom()
    cleared_basis = tuple(
        sp.together(polynomial).as_numer_denom() for polynomial in basis
    )
    converted = _flint_polynomial_context(
        (dividend_numerator, *(numerator for numerator, _ in cleared_basis))
    )
    if converted is not None:
        symbols, _context, polynomials = converted
        dividend_polynomial = polynomials[0]
        for index, ((_, basis_denominator), basis_polynomial) in enumerate(
            zip(cleared_basis, polynomials[1:], strict=True)
        ):
            if basis_polynomial == 0:
                continue
            quotient, remainder = divmod(dividend_polynomial, basis_polynomial)
            if remainder != 0:
                continue
            if dividend_polynomial != quotient * basis_polynomial:
                raise AssertionError(
                    "FLINT principal-basis certificate did not replay"
                )
            restored = sp.cancel(
                _flint_polynomial_to_sympy(quotient, symbols)
                * basis_denominator
                / dividend_denominator
            )
            return index, restored

    for index, (numerator, denominator) in enumerate(cleared_basis):
        quotient = _flint_exact_principal_quotient(dividend_numerator, numerator)
        if quotient is None:
            continue
        restored = sp.cancel(quotient * denominator / dividend_denominator)
        if sp.cancel(dividend - restored * basis[index]) == 0:
            return index, restored
    return None


def _principal_ideal_quotient(
    goal: sp.Expr,
    equation: sp.Expr,
    variables: tuple[sp.Symbol, ...],
) -> sp.Expr | None:
    """Certify membership in a one-generator ideal without Buchberger search."""

    if equation == 0 or not variables:
        return None
    goal_coefficient, goal_tail = goal.as_coeff_Mul()
    equation_coefficient, equation_tail = equation.as_coeff_Mul()
    goal_factors = Counter(sp.Mul.make_args(goal_tail))
    equation_factors = Counter(sp.Mul.make_args(equation_tail))
    if all(
        goal_factors[factor] >= multiplicity
        for factor, multiplicity in equation_factors.items()
    ):
        remaining_factors = goal_factors - equation_factors
        quotient = sp.Rational(goal_coefficient, equation_coefficient) * sp.Mul(
            *remaining_factors.elements()
        )
        if _replay_groebner_certificate(
            goal=goal,
            multiplier=sp.Integer(1),
            quotients=(quotient,),
            basis=(equation,),
            remainder=sp.Integer(0),
            variables=variables,
        ):
            return quotient
    flint_quotient = _flint_exact_principal_quotient(goal, equation)
    if flint_quotient is not None:
        return flint_quotient
    coefficient_parameters = tuple(
        sorted(
            (goal.free_symbols | equation.free_symbols) - set(variables),
            key=sp.default_sort_key,
        )
    )
    coefficient_domain = (
        sp.QQ.frac_field(*coefficient_parameters)
        if coefficient_parameters
        else sp.QQ
    )
    try:
        quotient, remainder = sp.div(
            goal,
            equation,
            *variables,
            domain=coefficient_domain,
        )
    except sp.PolynomialError:
        return None
    if remainder != 0 and sp.cancel(remainder) != 0:
        return None
    if not _replay_groebner_certificate(
        goal=goal,
        multiplier=sp.Integer(1),
        quotients=(quotient,),
        basis=(equation,),
        remainder=sp.Integer(0),
        variables=variables,
    ):
        return None
    return quotient


def _direct_constraint_match(
    goal: sp.Expr,
    equations: tuple[sp.Expr, ...],
    *,
    expanded_operation_budget: int = 256,
) -> tuple[sp.Expr, sp.Expr] | None:
    """Match exact constraints structurally before any bounded expansion."""

    goal_operation_count = int(sp.count_ops(goal))
    for equation in equations:
        if goal == equation:
            return equation, sp.Integer(1)
        if goal == -equation:
            return equation, sp.Integer(-1)
        if (
            goal_operation_count + int(sp.count_ops(equation))
            <= expanded_operation_budget
        ):
            if sp.expand(goal - equation) == 0:
                return equation, sp.Integer(1)
            if sp.expand(goal + equation) == 0:
                return equation, sp.Integer(-1)
    return None


def _typed_goal_decomposition(
    elaborator: _JGEXElaborator,
    channel: str,
    points: tuple[str, ...],
    goal_polynomial: sp.Expr,
) -> tuple[str, tuple[sp.Expr, ...], tuple[sp.Expr, ...], sp.Expr] | None:
    """Split a conjunctive predicate using its typed semantics.

    The returned weights certify ``goal = sum(weight_i * component_i**2)``.
    Components come from the predicate definition, not from benchmark-specific
    factors found after attempting the proof.
    """

    theorem: str
    residuals: tuple[sp.Expr, ...]
    if channel == "midp" and len(points) == 3:
        midpoint, left, right = points
        residuals = tuple(
            2 * value - left_value - right_value
            for value, left_value, right_value in zip(
                elaborator.coordinates[midpoint],
                elaborator.coordinates[left],
                elaborator.coordinates[right],
                strict=True,
            )
        )
        theorem = "midpoint_coordinate_conjunction"
    elif channel == "cyclic" and len(points) > 4:
        determinants: list[sp.Expr] = []
        for point in points[3:]:
            rows = []
            for selected in (*points[:3], point):
                x, y = elaborator.coordinates[selected]
                rows.append((x * x + y * y, x, y, sp.Integer(1)))
            determinants.append(sp.det(sp.Matrix(rows)))
        residuals = tuple(determinants)
        theorem = "multi_point_cyclic_conjunction"
    else:
        return None

    if len(residuals) < 2:
        return None
    rational_goal = sum((item * item for item in residuals), sp.Integer(0))
    expected_numerator, common_denominator = sp.together(
        rational_goal
    ).as_numer_denom()
    if sp.cancel(expected_numerator - goal_polynomial) != 0:
        return None

    components: list[sp.Expr] = []
    weights: list[sp.Expr] = []
    for residual in residuals:
        numerator, denominator = sp.together(residual).as_numer_denom()
        weight = sp.cancel(common_denominator / denominator**2)
        if sp.denom(weight) != 1:
            return None
        components.append(sp.expand(numerator))
        weights.append(sp.expand(weight))
    composition_residual = sp.expand(
        goal_polynomial
        - sum(
            (
                weight * component**2
                for weight, component in zip(weights, components, strict=True)
            ),
            sp.Integer(0),
        )
    )
    if composition_residual != 0:
        return None
    return theorem, tuple(components), tuple(weights), composition_residual


def lower_jgex_to_exact_obligation(
    text: str,
    *,
    enable_affine_local_lemmas: bool = False,
    enable_structural_lemmas: bool = True,
    representation: str = "explicit",
    max_saturation_rounds: int = 1,
    local_max_steps: int | None = None,
    local_max_output_terms: int = 64,
    local_max_resultant_degree: int = 1,
    local_max_separator_variables: int | None = 12,
    local_ordering_strategy: str = "min_fill",
    groebner_method: str = "f5b",
    progress_callback: Callable[[dict[str, object]], None] | None = None,
) -> JGEXExactObligation:
    started_at = time.perf_counter()

    def emit(stage: str, **metrics: object) -> None:
        if progress_callback is None:
            return
        progress_callback(
            {
                "stage": stage,
                "elapsed_seconds": round(time.perf_counter() - started_at, 6),
                **metrics,
            }
        )

    base_representation = (
        "relational"
        if representation
        in {"local_relational", "goal_relational", "goal_local_relational"}
        else representation
    )
    emit("preparation_started", representation=representation)

    def preparation_progress(event: dict[str, object]) -> None:
        preparation_event = dict(event)
        preparation_stage = str(preparation_event.pop("stage", "unknown"))
        emit(
            "preparation_progress",
            preparation_stage=preparation_stage,
            **preparation_event,
        )

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
        representation=base_representation,
        progress_callback=preparation_progress,
        expand_equations=False,
    )
    typed_goal_decomposition = _typed_goal_decomposition(
        elaborator,
        channel,
        points,
        goal_polynomial,
    )
    emit(
        "preparation_completed",
        channel=channel,
        point_count=len(points),
        construction_block_count=len(elaborator.construction_blocks),
        equation_count=len(equations),
        variable_count=len(variables),
        goal_variable_count=len(goal_polynomial.free_symbols),
    )
    if max_saturation_rounds < 0:
        raise ValueError("max_saturation_rounds must be non-negative")
    if groebner_method not in {"f5b", "buchberger"}:
        raise ValueError(f"unsupported Groebner method: {groebner_method}")
    original_equations = equations
    goal_relevant_clause_indices: tuple[int, ...] = ()
    excluded_clause_indices: tuple[int, ...] = ()
    selected_denominators = tuple(elaborator.denominators)
    if representation in {"goal_relational", "goal_local_relational"}:
        emit(
            "goal_slice_started",
            construction_block_count=len(elaborator.construction_blocks),
            equation_count=len(equations),
        )
        (
            equations,
            selected_denominators,
            goal_relevant_clause_indices,
            excluded_clause_indices,
        ) = _goal_directed_construction_slice(elaborator, points, equations)
        emit(
            "goal_slice_completed",
            retained_clause_count=len(goal_relevant_clause_indices),
            excluded_clause_count=len(excluded_clause_indices),
            retained_equation_count=len(equations),
        )
    emit(
        "polynomial_expansion_started",
        equation_count=len(equations),
        variable_count=len(variables),
        coefficient_preserving=True,
    )
    equations = tuple(
        _expand_polynomial_in_generators(equation, variables)
        for equation in equations
    )
    emit(
        "polynomial_expansion_completed",
        equation_count=len(equations),
        variable_count=len(variables),
        coefficient_preserving=True,
    )
    denominators = {
        _safe(item): item
        for item in selected_denominators
        if item != 0 and item.free_symbols
    }
    known_nonzero_factor_keys = frozenset().union(
        *(
            _canonical_nonconstant_factor_keys(item)
            for item in denominators.values()
        )
    )
    local_elimination: LocalEliminationResult | None = None
    local_denominators: dict[str, sp.Expr] = {}
    if representation in {"local_relational", "goal_local_relational"}:
        protected = frozenset(goal_polynomial.free_symbols)
        emit(
            "local_elimination_started",
            equation_count=len(equations),
            variable_count=len(variables),
            protected_variable_count=len(protected),
            ordering_strategy=local_ordering_strategy,
        )

        def local_progress(event: dict[str, object]) -> None:
            local_event = dict(event)
            local_stage = str(local_event.pop("stage", "unknown"))
            emit(
                "local_elimination_progress",
                local_stage=local_stage,
                **local_event,
            )

        if set(variables) <= protected:
            # This is the identity morphism: no local variable may be removed.
            # Keep the SymPy expressions in memory instead of serializing every
            # large coefficient chart merely to parse it back unchanged.
            local_elimination = LocalEliminationResult(
                initial_polynomials=(),
                remaining_polynomials=(),
                remaining_variables=tuple(sorted(map(str, variables))),
                steps=(),
                eliminated_variables=(),
                stopped_reason="no_unprotected_variables",
                exact_replay=True,
            )
        else:
            local_elimination = eliminate_local_linear_variables(
                equations,
                variables,
                protected_variables=protected,
                max_steps=local_max_steps,
                max_output_terms=local_max_output_terms,
                max_resultant_degree=local_max_resultant_degree,
                max_separator_variables=local_max_separator_variables,
                ordering_strategy=local_ordering_strategy,
                progress_callback=local_progress,
                pre_normalized=True,
                nonzero_condition_acceptor=lambda condition: (
                    _nonzero_condition_follows_from_factors(
                        condition, known_nonzero_factor_keys
                    )
                ),
            )
        if not local_elimination.exact_replay:
            raise AssertionError("JGEX local elimination certificate did not replay")
        if local_elimination.eliminated_variables:
            equations = tuple(
                sp.sympify(item) for item in local_elimination.remaining_polynomials
            )
            remaining_names = set(local_elimination.remaining_variables)
            variables = tuple(item for item in variables if str(item) in remaining_names)
        for step in local_elimination.steps:
            for condition in step.nonzero_conditions:
                expression = condition.removesuffix(" != 0").strip()
                factor = sp.factor(sp.sympify(expression))
                if factor != 0 and factor.free_symbols:
                    local_denominators.setdefault(_safe(factor), factor)
        for key, factor in local_denominators.items():
            denominators.setdefault(key, factor)
        emit(
            "local_elimination_completed",
            step_count=len(local_elimination.steps),
            eliminated_variable_count=len(local_elimination.eliminated_variables),
            remaining_variable_count=len(local_elimination.remaining_variables),
            remaining_polynomial_count=len(local_elimination.remaining_polynomials),
            stopped_reason=local_elimination.stopped_reason,
            exact_replay=local_elimination.exact_replay,
        )

    ordered_denominators = (
        *local_denominators.values(),
        *(item for key, item in denominators.items() if key not in local_denominators),
    )

    goal_operation_count = int(sp.count_ops(goal_polynomial))
    direct_scan_enabled = goal_operation_count <= 256
    emit(
        "direct_constraint_scan_started",
        equation_count=len(equations),
        enabled=direct_scan_enabled,
        goal_operation_count=goal_operation_count,
    )
    direct_constraint = _direct_constraint_match(goal_polynomial, equations)
    emit("direct_constraint_scan_completed", matched=direct_constraint is not None)
    principal_constraint: tuple[sp.Expr, sp.Expr] | None = None
    if direct_constraint is None and len(equations) == 1 and variables:
        emit(
            "principal_ideal_scan_started",
            variable_count=len(variables),
            goal_operation_count=goal_operation_count,
        )
        principal_quotient = _principal_ideal_quotient(
            goal_polynomial,
            equations[0],
            variables,
        )
        if principal_quotient is not None:
            principal_constraint = (equations[0], principal_quotient)
        emit(
            "principal_ideal_scan_completed",
            matched=principal_constraint is not None,
        )
    saturation_multiplier = sp.Integer(1)
    saturation_assumptions_used: list[str] = []
    goal_decomposition_certificate: TypedGoalDecompositionCertificate | None = None
    vacuous_unit_ideal = False
    initial_remainder_polynomial: sp.Poly | None = None
    if goal_polynomial == 0 or goal_polynomial.is_zero is True:
        quotients: list[sp.Expr] = []
        remainder = sp.Integer(0)
        basis_expressions: tuple[sp.Expr, ...] = tuple()
    elif direct_constraint is not None:
        basis_expression, quotient = direct_constraint
        quotients = [quotient]
        remainder = sp.Integer(0)
        basis_expressions = (basis_expression,)
    elif principal_constraint is not None:
        basis_expression, quotient = principal_constraint
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
        # Local projection can leave regularity factors that no longer occur in
        # the terminal factor graph.  Treat those symbols as exact coefficient
        # expressions so saturation can still replay without reintroducing all
        # eliminated coordinates into the Groebner search ring.
        coefficient_parameters = tuple(
            sorted(
                set().union(*(equation.free_symbols for equation in equations))
                - set(variables),
                key=sp.default_sort_key,
            )
        )
        coefficient_domain = (
            sp.QQ.frac_field(*coefficient_parameters)
            if coefficient_parameters
            else sp.QQ
        )
        emit(
            "groebner_started",
            equation_count=len(equations),
            variable_count=len(variables),
            coefficient_domain=str(coefficient_domain),
            coefficient_parameter_count=len(coefficient_parameters),
            method=groebner_method,
        )
        basis = sp.groebner(
            equations,
            *variables,
            order="grevlex",
            method=groebner_method,
            domain=coefficient_domain,
        )
        basis_expressions = tuple(sp.expand(poly.as_expr()) for poly in basis.polys)
        emit(
            "groebner_completed",
            basis_polynomial_count=len(basis_expressions),
        )
        if len(basis_expressions) == 1 and basis_expressions[0] in (1, -1):
            # EX treats every omitted symbolic coordinate as an invertible
            # coefficient.  A unit basis in that localized ring is therefore
            # not yet evidence that the geometric construction is empty.
            # Re-run once in the full polynomial ring before classifying it as
            # an inconsistent setup.
            full_variable_set = set(goal_polynomial.free_symbols)
            for equation in equations:
                full_variable_set.update(equation.free_symbols)
            full_variables = tuple(sorted(full_variable_set, key=sp.default_sort_key))
            if set(full_variables) != set(variables):
                emit(
                    "unit_basis_full_ring_recheck_started",
                    localized_variable_count=len(variables),
                    full_variable_count=len(full_variables),
                )
                full_basis = sp.groebner(
                    equations,
                    *full_variables,
                    order="grevlex",
                    domain=sp.QQ,
                    method=groebner_method,
                )
                full_basis_expressions = tuple(
                    sp.expand(poly.as_expr()) for poly in full_basis.polys
                )
                emit(
                    "unit_basis_full_ring_recheck_completed",
                    basis_polynomial_count=len(full_basis_expressions),
                    remains_unit=(
                        len(full_basis_expressions) == 1
                        and full_basis_expressions[0] in (1, -1)
                    ),
                )
                basis = full_basis
                basis_expressions = full_basis_expressions
                variables = full_variables
        emit("initial_reduction_started")
        if len(basis_expressions) == 1 and basis_expressions[0] in (1, -1):
            basis_unit = basis_expressions[0]
            quotients = [goal_polynomial / basis_unit]
            remainder = sp.Integer(0)
            reduction_mode = "unit_basis_identity"
            # A unit ideal proves that the construction equations are
            # inconsistent.  It can replay an algebraic identity, but it is
            # not a proof of the geometric theorem unless a separate
            # non-emptiness witness is supplied.  No such witness exists in
            # this certificate format, so keep the diagnostic and reject the
            # theorem claim as vacuous.
            vacuous_unit_ideal = True
            emit(
                "construction_inconsistency_detected",
                reason="unit_groebner_basis_without_nonempty_witness",
            )
        elif typed_goal_decomposition is not None:
            (
                decomposition_theorem,
                goal_components,
                composition_weights,
                composition_residual,
            ) = typed_goal_decomposition
            emit(
                "typed_goal_reduction_started",
                theorem=decomposition_theorem,
                component_count=len(goal_components),
            )
            component_quotients: list[tuple[sp.Expr, ...]] = []
            component_remainders: list[sp.Expr] = []
            all_components_zero = True
            for component_index, component in enumerate(goal_components):
                emit(
                    "typed_goal_component_started",
                    theorem=decomposition_theorem,
                    component_index=component_index,
                    component_operation_count=int(sp.count_ops(component)),
                )
                current_quotients, current_remainder = basis.reduce(component)
                replayed = _replay_groebner_certificate(
                    goal=component,
                    multiplier=sp.Integer(1),
                    quotients=current_quotients,
                    basis=basis_expressions,
                    remainder=current_remainder,
                    variables=variables,
                )
                if not replayed:
                    raise AssertionError(
                        "typed goal component certificate did not replay"
                    )
                component_quotients.append(tuple(current_quotients))
                component_remainders.append(current_remainder)
                component_is_zero = sp.expand(current_remainder) == 0
                all_components_zero = all_components_zero and component_is_zero
                emit(
                    "typed_goal_component_completed",
                    theorem=decomposition_theorem,
                    component_index=component_index,
                    remainder_is_zero=component_is_zero,
                    quotient_count=len(current_quotients),
                )
            if all_components_zero:
                quotients = [
                    sp.expand(
                        sum(
                            (
                                weight * component * current_quotients[basis_index]
                                for weight, component, current_quotients in zip(
                                    composition_weights,
                                    goal_components,
                                    component_quotients,
                                    strict=True,
                                )
                            ),
                            sp.Integer(0),
                        )
                    )
                    for basis_index in range(len(basis_expressions))
                ]
                remainder = sp.Integer(0)
                reduction_mode = "typed_goal_component_composition"
                goal_decomposition_certificate = TypedGoalDecompositionCertificate(
                    theorem=decomposition_theorem,
                    component_polynomials=tuple(_safe(item) for item in goal_components),
                    composition_weights=tuple(
                        _safe(item) for item in composition_weights
                    ),
                    component_quotient_certificates=tuple(
                        tuple(_safe(item) for item in current)
                        for current in component_quotients
                    ),
                    component_remainders=tuple(
                        _safe(item) for item in component_remainders
                    ),
                    composition_residual=_safe(composition_residual),
                    replayed=True,
                )
                emit(
                    "typed_goal_reduction_completed",
                    theorem=decomposition_theorem,
                    component_count=len(goal_components),
                    all_components_zero=True,
                )
            else:
                emit(
                    "typed_goal_reduction_completed",
                    theorem=decomposition_theorem,
                    component_count=len(goal_components),
                    all_components_zero=False,
                    fallback="whole_goal_reduction",
                )
                (
                    quotients,
                    remainder,
                    initial_remainder_polynomial,
                ) = _groebner_reduce_preserving_sparse_remainder(
                    basis,
                    goal_polynomial,
                )
                reduction_mode = "groebner_reduce_after_typed_components"
        else:
            (
                quotients,
                remainder,
                initial_remainder_polynomial,
            ) = _groebner_reduce_preserving_sparse_remainder(
                basis,
                goal_polynomial,
            )
            reduction_mode = "groebner_reduce"
        emit(
            "initial_reduction_completed",
            remainder_is_zero=sp.expand(remainder) == 0,
            reduction_mode=reduction_mode,
        )
        canonical_denominators: dict[str, sp.Expr] = {}
        if sp.expand(remainder) != 0 and max_saturation_rounds:
            emit(
                "denominator_canonicalization_started",
                denominator_count=len(ordered_denominators),
            )
            for denominator in ordered_denominators:
                for factor in _canonical_nonconstant_factors(denominator):
                    canonical_denominators.setdefault(_safe(factor), factor)
            emit(
                "denominator_canonicalization_completed",
                denominator_count=len(canonical_denominators),
            )
        emit(
            "saturation_started",
            denominator_count=len(canonical_denominators),
            max_saturation_rounds=max_saturation_rounds,
        )
        if sp.expand(remainder) != 0 and max_saturation_rounds:
            def saturation_progress(event: dict[str, object]) -> None:
                progress_event = dict(event)
                saturation_stage = str(progress_event.pop("stage", "unknown"))
                emit(
                    "saturation_progress",
                    saturation_stage=saturation_stage,
                    **progress_event,
                )

            (
                quotients,
                remainder,
                saturation_multiplier,
                used_assumptions,
            ) = _reduce_with_nondegeneracy_saturation(
                basis,
                goal_polynomial,
                tuple(canonical_denominators.items()),
                max_rounds=max_saturation_rounds,
                initial_reduction=(list(quotients), remainder),
                initial_remainder_polynomial=initial_remainder_polynomial,
                progress_callback=saturation_progress,
            )
        else:
            used_assumptions = ()
        saturation_assumptions_used.extend(used_assumptions)
        emit(
            "saturation_completed",
            assumptions_used_count=len(used_assumptions),
            remainder_is_zero=sp.expand(remainder) == 0,
        )
    emit(
        "certificate_replay_started",
        basis_polynomial_count=len(basis_expressions),
        quotient_count=len(quotients),
    )
    certificate_replayed = _replay_groebner_certificate(
        goal=goal_polynomial,
        multiplier=saturation_multiplier,
        quotients=quotients,
        basis=basis_expressions,
        remainder=remainder,
        variables=variables,
    )
    emit("certificate_replay_completed", replayed=certificate_replayed)
    if not certificate_replayed:
        raise AssertionError("JGEX Groebner certificate did not replay")

    goal_decomposition_material = (
        ()
        if goal_decomposition_certificate is None
        else (
            "typed_goal_decomposition:" + goal_decomposition_certificate.theorem,
            *goal_decomposition_certificate.component_polynomials,
            *goal_decomposition_certificate.composition_weights,
            *(
                item
                for certificate in goal_decomposition_certificate.component_quotient_certificates
                for item in certificate
            ),
            *goal_decomposition_certificate.component_remainders,
            goal_decomposition_certificate.composition_residual,
        )
    )
    certificate_material = "|".join(
        (
            channel,
            *points,
            *vocabulary,
            *elaborator.normalization_assumptions,
            *(_safe(item) for item in original_equations),
            *(_safe(item) for item in equations),
            *denominators,
            _safe(goal_polynomial),
            *(_safe(item) for item in basis_expressions),
            *(_safe(item) for item in quotients),
            _safe(remainder),
            _safe(saturation_multiplier),
            *saturation_assumptions_used,
            representation,
            *goal_decomposition_material,
            *(
                "local_elimination:" + item.certificate_sha256
                for item in (
                    local_elimination.steps if local_elimination is not None else ()
                )
            ),
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
    local_replayed = bool(
        local_elimination is None or local_elimination.exact_replay
    )
    structural_replayed = all(
        item.replayed and item.composition_replayed
        for item in elaborator.structural_lemma_certificates
    )
    obligation = JGEXExactObligation(
        channel=channel,
        points=points,
        construction_vocabulary=tuple(sorted(set(vocabulary))),
        normalization_assumptions=tuple(elaborator.normalization_assumptions),
        construction_equations=tuple(_safe(item) for item in original_equations),
        nondegeneracy_conditions=tuple(f"{key} != 0" for key in sorted(denominators)),
        goal_polynomial=_safe(goal_polynomial),
        groebner_basis=tuple(_safe(item) for item in basis_expressions),
        quotient_certificate=tuple(_safe(item) for item in quotients),
        remainder=_safe(remainder),
        saturation_multiplier=_safe(saturation_multiplier),
        saturation_assumptions_used=tuple(saturation_assumptions_used),
        exact_replay=(
            sp.expand(remainder) == 0
            and local_replayed
            and structural_replayed
            and not vacuous_unit_ideal
        ),
        construction_consistency=(
            "unit_ideal_without_nonempty_witness"
            if vacuous_unit_ideal
            else "not_refuted_by_exact_constraints"
        ),
        vacuous_unit_ideal=vacuous_unit_ideal,
        certificate_sha256=hashlib.sha256(certificate_material.encode()).hexdigest(),
        local_lemma_certificates=tuple(elaborator.local_lemma_certificates),
        structural_lemma_certificates=tuple(elaborator.structural_lemma_certificates),
        construction_blocks=tuple(elaborator.construction_blocks),
        reduction_strategy=(
            "typed_local_elimination_then_groebner"
            if local_elimination is not None
            else "global_groebner"
        ),
        reduced_construction_equations=tuple(_safe(item) for item in equations),
        local_elimination=local_elimination,
        goal_relevant_clause_indices=goal_relevant_clause_indices,
        excluded_clause_indices=excluded_clause_indices,
        goal_decomposition_certificate=goal_decomposition_certificate,
    )
    emit(
        "certificate_completed",
        exact_replay=obligation.exact_replay,
        reduction_strategy=obligation.reduction_strategy,
        remainder_is_zero=obligation.remainder == "0",
    )
    return obligation
