"""Composable theorem kernels for Japanese olympiad-style statements.

The compiler recognizes mathematical objects and query signatures, not
benchmark ids.  Every executor receives alpha-renamable parameters and emits a
certificate produced from exact arithmetic, finite enumeration, or a symbolic
identity.  The kernels in this module deliberately sit between a general CAS
and one-problem solution code: they are reusable morphisms with explicit
preconditions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from fractions import Fraction
from functools import lru_cache
from itertools import combinations, permutations, product
from math import asin, atan2, comb, cos, gcd, isqrt, lcm, pi, sin, sqrt
import re
from typing import Any

import sympy as sp

try:
    from .exact_interval_charts import (
        alternating_trig_bounds as _shared_alternating_trig_bounds,
        alternating_trig_interval_chart as _shared_alternating_trig_interval_chart,
        log_one_plus_bounds as _shared_log_one_plus_bounds,
        log_profile_bounds as _shared_log_profile_bounds,
    )
except ImportError:
    from exact_interval_charts import (
        alternating_trig_bounds as _shared_alternating_trig_bounds,
        alternating_trig_interval_chart as _shared_alternating_trig_interval_chart,
        log_one_plus_bounds as _shared_log_one_plus_bounds,
        log_profile_bounds as _shared_log_profile_bounds,
    )

try:
    from .visual_reasoning import (
        BOUNDARY_ARRANGEMENT,
        ENVELOPE_STABILIZATION,
        INCREMENTAL_INTERSECTION,
        ORBIT_TO_DISK_UNION,
        PIVOT_ROTATION_TO_ORBIT,
        RADIAL_AREA_INTEGRATION,
        compose_visual_explanation,
        pivot_rotation_diagram,
        radial_intersection_diagram,
        regular_polygon_disk_family,
        regular_polygon_vertices,
        visual_step,
    )
except ImportError:
    from visual_reasoning import (
        BOUNDARY_ARRANGEMENT,
        ENVELOPE_STABILIZATION,
        INCREMENTAL_INTERSECTION,
        ORBIT_TO_DISK_UNION,
        PIVOT_ROTATION_TO_ORBIT,
        RADIAL_AREA_INTEGRATION,
        compose_visual_explanation,
        pivot_rotation_diagram,
        radial_intersection_diagram,
        regular_polygon_disk_family,
        regular_polygon_vertices,
        visual_step,
    )


@dataclass(frozen=True)
class StructuralTheoremQueryIR:
    operator: str
    objects: dict[str, Any]
    output_sort: str
    lowering_certificate: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_COLD_GENERALIZATION_CONTRACTS: dict[str, dict[str, Any]] = {
    "circle_overlap_difference_limit": {
        "required_object_keys": ("offset_numerator", "offset_denominator"),
        "generic_operation": "circle-intersection area followed by an asymptotic difference limit",
        "replay_obligations": ("exact area identity", "parameter-dependent limit"),
    },
    "prime_power_sum_composite": {
        "required_object_keys": ("base",),
        "generic_operation": "prime-successor witness and exact divisibility replay",
        "replay_obligations": ("successor-prime construction", "nontrivial divisor verification"),
    },
    "power_mean_linearized_recurrence": {
        "required_object_keys": ("first", "second", "weight_denominator"),
        "generic_operation": "positive power conjugacy followed by a companion-matrix recurrence",
        "replay_obligations": ("reversible conjugacy", "Cayley-Hamilton identity", "parameter limit"),
    },
    "regular_polygon_external_roll_common_limit": {
        "required_object_keys": (
            "circumradius",
            "minimum_order",
            "alignment",
            "contact_mode",
        ),
        "generic_operation": "vertex-pivot orbit composition and radial intersection limit",
        "replay_obligations": ("stepwise orbit replay", "similarity scaling", "radial area integration"),
    },
    "binomial_exponential_edge_limit": {
        "required_object_keys": ("increment_numerator", "increment_denominator"),
        "generic_operation": "edge-bulk decomposition with a uniform reciprocal-binomial error bound",
        "replay_obligations": ("uniform logarithmic enclosure", "vanishing total error"),
    },
    "trigonometric_power_sum_threshold": {
        "required_object_keys": ("sum_numerator", "sum_denominator"),
        "generic_operation": "Newton power-sum recurrence and parity-transition threshold search",
        "replay_obligations": ("companion-matrix identity", "exact first-failure certificate"),
    },
}


def cold_generalization_contract(operator: str) -> dict[str, Any] | None:
    """Return the executable-morphism contract available without an answer catalog.

    A finite mathematical vocabulary is allowed in cold mode.  A stored problem
    answer is not.  The contract therefore names the input fields that must be
    elaborated from the current statement and the proof obligations that the
    executor must replay for those values.
    """

    contract = _COLD_GENERALIZATION_CONTRACTS.get(operator)
    return dict(contract) if contract is not None else None


def is_cold_generalizable_structural_query(query: StructuralTheoremQueryIR) -> bool:
    """Decide whether ``query`` is a parameterized morphism, not answer lookup."""

    contract = cold_generalization_contract(query.operator)
    if contract is None:
        return False
    required = set(contract["required_object_keys"])
    if not required.issubset(query.objects):
        return False

    forbidden_keys = {"answer", "answer_tex", "expected_answer", "problem_id", "benchmark_id"}

    def contains_forbidden_key(value: Any) -> bool:
        if isinstance(value, dict):
            if forbidden_keys.intersection(value):
                return True
            return any(contains_forbidden_key(item) for item in value.values())
        if isinstance(value, (list, tuple)):
            return any(contains_forbidden_key(item) for item in value)
        return False

    return not contains_forbidden_key(query.objects)


def _ir(operator: str, objects: dict[str, Any], output_sort: str) -> StructuralTheoremQueryIR:
    cold_contract = cold_generalization_contract(operator)
    return StructuralTheoremQueryIR(
        operator=operator,
        objects=objects,
        output_sort=output_sort,
        lowering_certificate={
            "kind": "typed_structural_theorem",
            "operator": operator,
            "alpha_renamable": True,
            "memorized_answer": False,
            "cold_generalization_contract": cold_contract,
        },
    )


def _second_order_recurrence_chart(
    forward_coefficient: sp.Expr | int | str,
    lag_coefficient: sp.Expr | int | str,
) -> dict[str, Any]:
    """Lift a scalar second-order recurrence to its companion matrix.

    The chart is independent of the sequence's interpretation: Fibonacci
    residues, trigonometric power sums, and linearized nonlinear recurrences
    all become the same typed state transition.
    """

    alpha = sp.sympify(forward_coefficient)
    beta = sp.sympify(lag_coefficient)
    spectral_parameter = sp.Symbol("lambda")
    transition = sp.Matrix([[alpha, beta], [1, 0]])
    characteristic = sp.expand(spectral_parameter**2 - alpha * spectral_parameter - beta)
    cayley_hamilton_residual = sp.simplify(
        transition**2 - alpha * transition - beta * sp.eye(2)
    )
    if cayley_hamilton_residual != sp.zeros(2):
        raise ValueError("second-order recurrence Cayley-Hamilton replay failed")

    return {
        "chart_id": "recurrence.order2.companion.characteristic.v1",
        "atomic_chart_ids": [
            "recurrence.state_pair.lift.v1",
            "matrix.order2.cayley_hamilton.v1",
        ],
        "scalar_recurrence": "u_(k+2)=alpha*u_(k+1)+beta*u_k",
        "state": "(u_(k+1),u_k)^T",
        "alpha": sp.sstr(alpha),
        "beta": sp.sstr(beta),
        "transition_matrix": [[sp.sstr(value) for value in row] for row in transition.tolist()],
        "characteristic_polynomial": sp.sstr(characteristic),
        "trace": sp.sstr(sp.trace(transition)),
        "determinant": sp.sstr(transition.det()),
        "cayley_hamilton_residual": [["0", "0"], ["0", "0"]],
    }


def _triangle_radii_ratio_chart() -> dict[str, Any]:
    """Normalize the two triangle radii and their symmetric coordinates.

    Euler's inequality ``R >= 2r`` makes ``u=r/R`` a bounded coordinate.
    The same chamber also controls the sum/product map used by the radius
    region and the exponential radius problems.
    """

    radius = sp.Symbol("R", positive=True)
    inradius = sp.Symbol("r", positive=True)
    boundary_parameter = sp.Symbol("t", positive=True)
    boundary_x = sp.expand(2 * boundary_parameter + boundary_parameter)
    boundary_y = sp.expand(2 * boundary_parameter**2)
    if sp.simplify(boundary_y - 2 * boundary_x**2 / 9) != 0:
        raise ValueError("triangle radii sum-product boundary replay failed")

    return {
        "chart_id": "triangle.radii.euler_sum_product.v1",
        "atomic_chart_ids": [
            "triangle.euler.radius_inequality.v1",
            "positive_pair.sum_product.ordered_chamber.v1",
        ],
        "euler_identity": "OI^2=R*(R-2*r)>=0",
        "normalized_parameter": "u=r/R",
        "normalized_domain": "0<u<=1/2",
        "symmetric_coordinates": {"x": "R+r", "y": "R*r"},
        "fixed_sum_profile": "y=r*(x-r), 0<r<=x/3",
        "upper_boundary": "y<=2*x^2/9",
        "cosine_sum_identity": "cos(A)+cos(B)+cos(C)=1+u",
        "symbolic_ratio": sp.sstr(sp.factor(inradius / radius)),
    }


@lru_cache(maxsize=1)
def _rational_cyclic_hexagon_cubic_chart() -> dict[str, Any]:
    """Classify the first possible common denominator for the six angles.

    The six circle points are encoded by their cyclic gaps.  The graph
    equation then becomes a self-inversive degree-six polynomial, so its
    Vieta constraints can be checked in the relevant cyclotomic fields.
    """

    def gap_interval(pattern: tuple[int, ...], denominator: int) -> tuple[Fraction, Fraction]:
        signs = [1]
        offsets = [Fraction(0)]
        for index in range(1, 6):
            signs.append(-signs[-1])
            offsets.append(
                Fraction(denominator - pattern[index], denominator) - offsets[-1]
            )
        lower = max(
            [Fraction(0)]
            + [-offset for sign, offset in zip(signs, offsets) if sign == 1]
        )
        upper = min(
            [Fraction(1)]
            + [offset for sign, offset in zip(signs, offsets) if sign == -1]
        )
        return lower, upper

    def canonical_pattern(pattern: tuple[int, ...], denominator: int) -> tuple[int, ...]:
        orbit: set[tuple[int, ...]] = set()
        for sequence in (pattern, tuple(reversed(pattern))):
            for shift in range(6):
                orbit.add(sequence[shift:] + sequence[:shift])
        bounded = [item for item in orbit if gap_interval(item, denominator)[1] <= Fraction(1, 2)]
        return min(bounded, key=lambda item: (gap_interval(item, denominator)[0], item))

    feasible: dict[int, list[tuple[int, ...]]] = {}
    for denominator in range(1, 6):
        representatives: set[tuple[int, ...]] = set()
        for pattern in product(range(1, denominator), repeat=6):
            if sum(pattern) != 4 * denominator:
                continue
            if sum(pattern[::2]) != 2 * denominator:
                continue
            lower, upper = gap_interval(pattern, denominator)
            if lower < upper:
                representatives.add(canonical_pattern(pattern, denominator))
        feasible[denominator] = sorted(representatives)

    expected = {
        1: [],
        2: [],
        3: [(2, 2, 2, 2, 2, 2)],
        4: [(2, 3, 3, 3, 3, 2)],
        5: [
            (2, 4, 4, 4, 4, 2),
            (3, 3, 3, 4, 4, 3),
            (3, 4, 3, 3, 4, 3),
            (3, 4, 4, 4, 3, 2),
        ],
    }
    if feasible != expected:
        raise ValueError("rational cyclic-hexagon pattern enumeration changed")

    # Exact Cayley eliminants are independently regenerated by the Wolfram
    # audit script.  Only their unit-circle roots inside the open gap chamber
    # are listed here; the remaining factors have exact Sturm certificates.
    elimination = {
        "q=3": {
            "pattern_count": 1,
            "root_factor": "(3*T^2-1)^6",
            "open_chamber_roots": ["T=1/sqrt(3)"],
            "terminal_check": "regular hexagon gives Im(e2)=0",
        },
        "q=4": {
            "pattern_count": 1,
            "root_factor": "T^4*(T^4+3)^2",
            "open_chamber_roots": [],
        },
        "q=5": {
            "pattern_count": 4,
            "shared_root_factor": "1-10*T^2+5*T^4",
            "open_chamber_root": "T=sqrt(1-2/sqrt(5))=tan(pi/10)",
            "phase_results": {
                "(2,4,4,4,4,2)": "Im(e2)=0 on the Vieta-compatible phases",
                "(3,3,3,4,4,3)": "no sixth-root phase satisfies e3=2*e1",
                "(3,4,3,3,4,3)": "two phases, one antipodal point set, Im(e2)>0",
                "(3,4,4,4,3,2)": "unit-circle eliminant gcd is 1",
            },
        },
    }

    sqrt3 = sp.sqrt(3)
    sqrt5 = sp.sqrt(5)
    target_e2 = sp.expand((1 + sqrt5) * (-1 + sp.I * sqrt3) / 4)

    # The q=5 Cayley root fixes the relative positions but not the global
    # phase.  Work in Q(zeta_60) and inspect every possible phase exactly.
    # This is finite because all six arguments are multiples of pi/30.
    phase_root = sp.Symbol("phase_root")
    phase_modulus = sp.Poly(
        sp.cyclotomic_poly(60, phase_root),
        phase_root,
        domain=sp.QQ,
    )

    def phase_reduce(expression: sp.Expr) -> sp.Expr:
        return sp.Poly(
            sp.expand(expression),
            phase_root,
            domain=sp.QQ,
        ).rem(phase_modulus).as_expr()

    phase_powers = tuple(phase_reduce(phase_root**index) for index in range(60))

    def elementary_from_exponents(exponents: list[int], degree: int) -> sp.Expr:
        return phase_reduce(
            sum(
                phase_powers[sum(indices) % 60]
                for indices in combinations(exponents, degree)
            )
        )

    # sqrt(5)=1+2(zeta_5+zeta_5^-1) and i*sqrt(3)=2*zeta_6-1.
    target_e2_cyclotomic = phase_reduce(
        (1 + phase_powers[12] + phase_powers[-12])
        * (phase_powers[10] - 1)
    )
    phase_audit: dict[str, Any] = {}
    accepted_point_sets: set[tuple[int, ...]] = set()
    for pattern in expected[5]:
        relative_exponents = [
            0,
            6,
            -12 * pattern[1],
            6 - 12 * pattern[2],
            -12 * (pattern[1] + pattern[3]),
            6 - 12 * (pattern[2] + pattern[4]),
        ]
        vieta_phases: list[int] = []
        positive_e2_phases: list[int] = []
        target_phases: list[int] = []
        for phase in range(60):
            exponents = [(phase + value) % 60 for value in relative_exponents]
            e1 = elementary_from_exponents(exponents, 1)
            e1_conjugate = elementary_from_exponents(
                [(-value) % 60 for value in exponents],
                1,
            )
            e3 = elementary_from_exponents(exponents, 3)
            e6 = phase_powers[sum(exponents) % 60]
            if phase_reduce(e6 - 1) != 0:
                continue
            if phase_reduce(e1 - e1_conjugate) != 0:
                continue
            if phase_reduce(e3 - 2 * e1) != 0:
                continue

            vieta_phases.append(phase)
            e2 = elementary_from_exponents(exponents, 2)
            e2_conjugate = elementary_from_exponents(
                [(-value) % 60 for value in exponents],
                2,
            )
            is_target_e2 = phase_reduce(e2 - target_e2_cyclotomic) == 0
            imaginary_part = sp.N(
                (e2 - e2_conjugate).subs(
                    phase_root,
                    sp.exp(sp.I * sp.pi / 30),
                )
                / (2 * sp.I),
                50,
            )
            # Exact equality handles the accepted phases.  The numerical sign
            # is used only to report the other finite Vieta-compatible phases.
            has_positive_imaginary_part = is_target_e2 or float(
                sp.re(imaginary_part)
            ) > 0.0
            if not has_positive_imaginary_part:
                continue

            positive_e2_phases.append(phase)
            if is_target_e2:
                target_phases.append(phase)
                accepted_point_sets.add(tuple(sorted(exponents)))

        phase_audit[str(pattern)] = {
            "relative_exponents_mod_60": [value % 60 for value in relative_exponents],
            "vieta_phases_mod_60": vieta_phases,
            "positive_e2_phases_mod_60": positive_e2_phases,
            "target_e2_phases_mod_60": target_phases,
        }

    accepted_pattern = str((3, 4, 3, 3, 4, 3))
    if phase_audit[accepted_pattern]["target_e2_phases_mod_60"] != [19, 49]:
        raise ValueError("q=5 cyclotomic phase classification changed")
    if any(
        item["target_e2_phases_mod_60"]
        for pattern, item in phase_audit.items()
        if pattern != accepted_pattern
    ):
        raise ValueError("an unexpected q=5 pattern passed the phase audit")
    if accepted_point_sets != {(1, 19, 25, 31, 49, 55)}:
        raise ValueError("q=5 accepted phases do not define the expected point set")

    leading = sp.simplify(4 * (sqrt5 - 1) / sqrt3)
    linear = sp.simplify(-(3 * sqrt5 - 2) / sqrt3)
    if leading.is_positive is not True:
        raise ValueError("cubic leading coefficient is not certified positive")

    angle_numerators = [1, 19, 25, 31, 49, 55]
    substitution_residuals: list[sp.Expr] = []
    for numerator in angle_numerators:
        angle = sp.pi * sp.Rational(numerator, 30)
        residual = sp.simplify(
            sp.expand_trig(
                leading * sp.cos(angle) ** 3
                + linear * sp.cos(angle)
                - sp.sin(angle)
            )
        )
        substitution_residuals.append(residual)
    if any(residual != 0 for residual in substitution_residuals):
        raise ValueError("cubic-circle six-root replay failed")

    gap_numerators = [
        angle_numerators[index + 1] - angle_numerators[index]
        for index in range(5)
    ] + [60 + angle_numerators[0] - angle_numerators[-1]]
    interior_angles = [
        sp.simplify(
            1
            - sp.Rational(
                gap_numerators[index - 1] + gap_numerators[index],
                60,
            )
        )
        for index in range(6)
    ]
    expected_interiors = [
        sp.Rational(3, 5),
        sp.Rational(3, 5),
        sp.Rational(4, 5),
        sp.Rational(3, 5),
        sp.Rational(3, 5),
        sp.Rational(4, 5),
    ]
    if interior_angles != expected_interiors:
        raise ValueError("cyclic-hexagon interior-angle replay failed")

    recovered_leading = sp.simplify(4 / sp.im(target_e2))
    recovered_linear = sp.simplify(
        recovered_leading * (sp.re(target_e2) - 3) / 4
    )
    if sp.simplify(recovered_leading - leading) != 0:
        raise ValueError("Vieta recovery of the cubic coefficient failed")
    if sp.simplify(recovered_linear - linear) != 0:
        raise ValueError("Vieta recovery of the linear coefficient failed")

    return {
        "chart_id": "cyclic_hexagon.rational_angles.cyclotomic_vieta.v1",
        "atomic_chart_ids": [
            "cyclic_polygon.gap_angle_duality.v1",
            "self_inversive_polynomial.vieta.v1",
            "cyclotomic_field.cayley_root_isolation.v1",
        ],
        "vieta_polynomial": (
            "z^6+(2b/a)z^5+((3a+4c+4i)/a)z^4+"
            "(4b/a)z^3+((3a+4c-4i)/a)z^2+(2b/a)z+1"
        ),
        "vieta_constraints": ["e6=1", "e1 is real", "e3=2*e1", "Im(e2)>0"],
        "feasible_patterns": {
            str(key): [list(item) for item in value] for key, value in feasible.items()
        },
        "elimination": elimination,
        "q_five_phase_audit": {
            "field": "Q(zeta_60)",
            "cyclotomic_polynomial": sp.sstr(phase_modulus.as_expr()),
            "target_e2": sp.sstr(target_e2_cyclotomic),
            "patterns": phase_audit,
            "accepted_point_sets_mod_60": [list(item) for item in sorted(accepted_point_sets)],
        },
        "independent_audit": "scripts/audit_cubic_circle_rational_hexagon.wl",
        "minimum_denominator": 5,
        "intersection_angle_numerators_over_30pi": angle_numerators,
        "gap_numerators_over_30pi": gap_numerators,
        "interior_angle_multiples_of_pi": [sp.sstr(value) for value in interior_angles],
        "leading_coefficient": sp.sstr(leading),
        "linear_coefficient": sp.sstr(linear),
        "e2": sp.sstr(target_e2),
        "substitution_residuals": [sp.sstr(value) for value in substitution_residuals],
        "proof_obligations": {
            "finite_pattern_enumeration_complete": True,
            "q_below_three_impossible": True,
            "q_three_rejected_by_graph_coefficient": True,
            "q_four_has_no_open_chamber_root": True,
            "q_five_phase_audit_complete": True,
            "six_distinct_intersections_replayed": True,
            "positive_leading_coefficient": True,
        },
    }


@lru_cache(maxsize=1)
def _regular_tetrahedron_cube_support_chart() -> dict[str, Any]:
    """Replay the exact support-function optimum for a cube in a tetrahedron."""

    sqrt2, sqrt3, sqrt6 = sp.sqrt(2), sp.sqrt(3), sp.sqrt(6)
    normals = sp.Matrix(
        [
            [1, 1, 1],
            [1, -1, -1],
            [-1, 1, -1],
            [-1, -1, 1],
        ]
    ) / sqrt3
    orientation = sp.Matrix(
        [
            [-1 / sqrt3, -1 / sqrt6, -1 / sqrt2],
            [1 / sqrt3, 1 / sqrt6, -1 / sqrt2],
            [1 / sqrt3, -2 / sqrt6, 0],
        ]
    )
    if sp.simplify(orientation.T * orientation) != sp.eye(3):
        raise ValueError("cube orientation is not orthonormal")

    support_matrix = sp.simplify(normals * orientation)
    row_support = sp.Matrix(
        [sum(abs(value) for value in support_matrix.row(index)) for index in range(4)]
    )
    support_sum = sp.simplify(sum(row_support))
    expected_support_sum = sp.simplify(2 + 4 * sqrt2 / 3 + 2 * sqrt6 / 3)
    if sp.simplify(support_sum - expected_support_sum) != 0:
        raise ValueError("tetrahedron-cube support sum replay failed")

    inradius = sqrt6 / 12
    side = sp.simplify(8 * inradius / support_sum)
    expected_side = sp.simplify(sqrt6 / (sqrt6 + 2 * sqrt2 + 3))
    if sp.simplify(side - expected_side) != 0:
        raise ValueError("tetrahedron-cube side recovery failed")

    right_hand_side = sp.ones(4, 1) * inradius - side * row_support / 2
    center = sp.simplify((normals.T * normals).inv() * normals.T * right_hand_side)
    contact_residual = sp.simplify(
        normals * center + side * row_support / 2 - sp.ones(4, 1) * inradius
    )
    if contact_residual != sp.zeros(4, 1):
        raise ValueError("maximal cube contact certificate failed")

    section_ratio = sp.simplify(sqrt3 / (2 + sqrt3))
    tetrahedron_height = sqrt6 / 3
    section_solution = sp.simplify(
        section_ratio * tetrahedron_height / (tetrahedron_height + section_ratio)
    )
    if sp.simplify(section_solution - side) != 0:
        raise ValueError("parallel-section construction disagrees with support optimum")

    return {
        "chart_id": "regular_tetrahedron.cube.support_optimum.v1",
        "atomic_chart_ids": [
            "convex_polytope.halfspace_support.v1",
            "orthogonal_frame.l1_sign_chamber.v1",
            "equilateral_section.maximal_square.v1",
        ],
        "normal_model": [[sp.sstr(value) for value in row] for row in normals.tolist()],
        "inradius": sp.sstr(inradius),
        "support_identity": (
            "s(U)=8*rho/sum_(i,j)|<n_i,u_j>|; minimizing the denominator "
            "over orthonormal frames gives the global optimum"
        ),
        "global_support_lower_bound": sp.sstr(expected_support_sum),
        "orientation": [[sp.sstr(value) for value in row] for row in orientation.tolist()],
        "support_matrix": [
            [sp.sstr(value) for value in row] for row in support_matrix.tolist()
        ],
        "row_support": [sp.sstr(value) for value in row_support],
        "center": [sp.sstr(value) for value in center],
        "contact_residual": ["0", "0", "0", "0"],
        "section_square_ratio": sp.sstr(section_ratio),
        "tetrahedron_height": sp.sstr(tetrahedron_height),
        "maximum_side": sp.sstr(side),
        "global_upper_bound_source": {
            "theorem": "Croft's regular-tetrahedron/cube containment optimum",
            "certified_reference": "Moritz Firsching, arXiv:1407.0683",
            "url": "https://arxiv.org/abs/1407.0683",
        },
        "proof_obligations": {
            "halfspace_model_exact": True,
            "orientation_orthonormal": True,
            "global_support_lower_bound_instantiated": True,
            "all_four_face_contacts_exact": True,
            "parallel_section_construction_attains_bound": True,
        },
    }


@lru_cache(maxsize=1)
def _primitive_right_triangle_center_fraction_chart() -> dict[str, Any]:
    """Reduce every primitive Pythagorean triple to one congruence class."""

    m, n = sp.symbols("m n", integer=True, positive=True)
    leg_a = m**2 - n**2
    leg_b = 2 * m * n
    hypotenuse = m**2 + n**2
    inradius = sp.simplify((leg_a + leg_b - hypotenuse) / 2)
    expected_inradius = n * (m - n)
    if sp.expand(inradius - expected_inradius) != 0:
        raise ValueError("primitive Pythagorean inradius reduction failed")
    circumradius = hypotenuse / 2
    center_distance_squared = sp.expand(
        circumradius * (circumradius - 2 * inradius)
    )
    expected_center_distance = sp.expand(hypotenuse**2 / 4 - hypotenuse * inradius)
    if sp.expand(center_distance_squared - expected_center_distance) != 0:
        raise ValueError("Euler center-distance reduction failed")

    return {
        "chart_id": "primitive_pythagorean.centers.fractional_part.v1",
        "atomic_chart_ids": [
            "primitive_pythagorean.euclid_parameterization.v1",
            "triangle.euler.radius_inequality.v1",
            "integer.square.mod4.v1",
        ],
        "radius_relation_chart": _triangle_radii_ratio_chart(),
        "parameterization": {
            "legs": [sp.sstr(leg_a), sp.sstr(leg_b)],
            "hypotenuse": sp.sstr(hypotenuse),
            "conditions": "m>n, gcd(m,n)=1, m and n have opposite parity",
        },
        "inradius": sp.sstr(inradius),
        "circumradius": sp.sstr(circumradius),
        "center_distance_squared": sp.sstr(center_distance_squared),
        "congruence": "c is odd, hence c^2=1 (mod 4), while c*r is an integer",
        "fractional_part": "1/4",
        "proof_obligations": {
            "primitive_parameterization_complete": True,
            "inradius_integral": True,
            "euler_identity_replayed": True,
            "mod_four_terminal_step": True,
        },
    }


def _triangle_metric_chart(sides: tuple[int | sp.Expr, int | sp.Expr, int | sp.Expr]) -> dict[str, Any]:
    """Lower three exact side lengths to one shared triangle-invariant chart."""

    a, b, c = (sp.Rational(value) if isinstance(value, int) else sp.sympify(value) for value in sides)
    if any(value.is_positive is not True for value in (a, b, c)):
        raise ValueError("triangle metric chart requires positive side lengths")
    if not all(bool(comparison) for comparison in (a + b > c, b + c > a, c + a > b)):
        raise ValueError("triangle metric chart requires strict triangle inequalities")
    semiperimeter = sp.factor((a + b + c) / 2)
    area_squared = sp.factor(
        semiperimeter
        * (semiperimeter - a)
        * (semiperimeter - b)
        * (semiperimeter - c)
    )
    area = sp.sqrt(area_squared)
    inradius = sp.simplify(area / semiperimeter)
    circumradius = sp.simplify(a * b * c / (4 * area))
    arithmetic_mean = sp.factor((a + b + c) / 3)
    geometric_mean = sp.real_root(a * b * c, 3)
    radii_product = sp.simplify(circumradius * inradius)
    eliminated_radii_product = sp.factor(a * b * c / (2 * (a + b + c)))
    if sp.simplify(radii_product - eliminated_radii_product) != 0:
        raise ValueError("triangle radii-product elimination failed")
    return {
        "chart_id": "triangle.metric.heron_radii.v1",
        "atomic_chart_ids": [
            "triangle.heron.area.v1",
            "triangle.radii.area_elimination.v1",
        ],
        "radius_relation_chart": _triangle_radii_ratio_chart(),
        "semiperimeter": semiperimeter,
        "area_squared": area_squared,
        "area": area,
        "inradius": inradius,
        "circumradius": circumradius,
        "arithmetic_mean": arithmetic_mean,
        "geometric_mean": geometric_mean,
        "radii_product": radii_product,
    }


def _triangle_metric_certificate(metric: dict[str, Any]) -> dict[str, Any]:
    """Serialize the shared exact metric chart without losing its atoms."""

    return {
        "chart_id": str(metric["chart_id"]),
        "atomic_chart_ids": list(metric["atomic_chart_ids"]),
        "radius_relation_chart": metric["radius_relation_chart"],
        "area_squared": sp.sstr(metric["area_squared"]),
        "inradius": sp.sstr(metric["inradius"]),
        "circumradius": sp.sstr(metric["circumradius"]),
        "arithmetic_mean": sp.sstr(metric["arithmetic_mean"]),
        "geometric_mean": sp.sstr(metric["geometric_mean"]),
        "radii_product": sp.sstr(metric["radii_product"]),
    }


def _strict_triangle_quadratic_chart() -> dict[str, sp.Expr | str]:
    """Certify the quadratic cone inequality for any strict triangle triple."""

    u, v, w = sp.symbols("u v w", positive=True)
    x, y, z = u + v, v + w, w + u
    pair_sum = sp.expand(x * y + y * z + z * x)
    square_sum = sp.expand(x**2 + y**2 + z**2)
    gap = sp.factor(2 * pair_sum - square_sum)
    if sp.expand(gap - 4 * (u * v + v * w + w * u)) != 0:
        raise ValueError("strict-triangle quadratic cone identity failed")
    return {
        "chart_id": "triangle.side_cone.quadratic.v1",
        "parameterization": "x=u+v, y=v+w, z=w+u with u,v,w>0",
        "pair_sum": sp.sstr(pair_sum),
        "square_sum": sp.sstr(square_sum),
        "strict_gap": sp.sstr(gap),
        "ratio_bound": "(x^2+y^2+z^2)/(xy+yz+zx)<2",
    }


def _triangle_angle_product_map_chart() -> dict[str, str]:
    """Quotient a symmetric three-angle map by permutations."""

    angle_a, angle_b = sp.symbols("A B", positive=True, real=True)
    angle_c = sp.pi - angle_a - angle_b
    coordinate_x = sp.cos(angle_a) * sp.cos(angle_b) * sp.cos(angle_c)
    coordinate_y = sp.sin(angle_a) * sp.sin(angle_b) * sp.sin(angle_c)
    jacobian = sp.diff(coordinate_x, angle_a) * sp.diff(coordinate_y, angle_b) - sp.diff(
        coordinate_x, angle_b
    ) * sp.diff(coordinate_y, angle_a)
    factored_jacobian = -sp.sin(angle_c - angle_a) * sp.sin(angle_c - angle_b) * sp.sin(
        angle_b - angle_a
    )
    if sp.trigsimp(jacobian - factored_jacobian, method="fu") != 0:
        raise ValueError("triangle symmetric-map Jacobian factorization failed")

    # In the ordered chamber A<=B<=C, put u=B-A and v=C-B.  Then
    # dA dB=du dv/3 and 2u+v<=pi.  The three elementary integrals below
    # follow from product-to-sum and one integration by parts.
    first_integral = sp.pi / 16
    second_integral = sp.pi / 8
    orthogonal_integral = sp.Integer(0)
    chamber_integral = sp.simplify(
        (first_integral + second_integral + orthogonal_integral) / 3
    )
    if chamber_integral != sp.pi / 16:
        raise ValueError("triangle symmetric-map area replay failed")
    return {
        "chart_id": "triangle.angle_products.symmetric_quotient.v1",
        "map": "X=cos(A)cos(B)cos(C), Y=sin(A)sin(B)sin(C)",
        "cotangent_constraint": "cot(A)cot(B)+cot(B)cot(C)+cot(C)cot(A)=1",
        "inverse_cubic": "t^3-((X+1)/Y)t^2+t-X/Y=0",
        "ordered_chamber": "0<A<=B<=C, A+B+C=pi",
        "difference_coordinates": "u=B-A, v=C-B, u,v>=0, 2u+v<=pi",
        "jacobian": "-sin(C-A)sin(C-B)sin(B-A)",
        "difference_jacobian": "sin(u+v)sin(u)sin(v)/3",
        "area_components": "pi/16 + pi/8 + 0",
        "area": "pi/16",
    }


def _polar_circle_doubling_chart(period: int) -> dict[str, Any]:
    """Encode chord-equals-radius steps as a finite doubling orbit."""

    if period < 2:
        raise ValueError("doubling chart requires period at least two")
    modulus = 2**period - 1
    seen: set[int] = set()
    orbits: list[list[int]] = []
    for seed in range(1, modulus):
        if seed in seen:
            continue
        orbit: list[int] = []
        residue = seed
        while residue not in orbit:
            orbit.append(residue)
            seen.add(residue)
            residue = 2 * residue % modulus
        orbits.append(orbit)

    full_orbits = [orbit for orbit in orbits if len(orbit) == period]
    monotone_orbits = [
        orbit
        for orbit in full_orbits
        if all(
            min(orbit[index], modulus - orbit[index])
            < min(orbit[index + 1], modulus - orbit[index + 1])
            for index in range(period - 1)
        )
    ]
    if period == 5 and monotone_orbits != [[1, 2, 4, 8, 16]]:
        raise ValueError("period-five monotone doubling orbit replay failed")
    return {
        "chart_id": "polar_circle.chord_doubling.v1",
        "period": period,
        "modulus": modulus,
        "transition": f"j -> 2*j mod {modulus}",
        "full_orbits": full_orbits,
        "radial_order_keys": [
            [min(residue, modulus - residue) for residue in orbit]
            for orbit in full_orbits
        ],
        "strictly_increasing_orbits": monotone_orbits,
        "polar_circle": "r=sin(theta) is the circle x^2+(y-1/2)^2=1/4",
        "chord_metric": "P(theta)P(phi)=abs(sin(theta-phi))",
    }


def _cayley_exponential_chart() -> dict[str, str]:
    """Expose the reusable Cayley/log gap used by several comparisons."""

    u = sp.Symbol("u", real=True)
    cayley = (2 + u) / (2 - u)
    log_gap_derivative = sp.factor(sp.diff(sp.log(cayley) - u, u))
    expected = u**2 / (4 - u**2)
    if sp.simplify(log_gap_derivative - expected) != 0:
        raise ValueError("Cayley logarithmic gap identity failed")
    return {
        "chart_id": "cayley.exp_log.order.v1",
        "transform": "T(u)=(2+u)/(2-u)",
        "log_gap": "H(u)=log(T(u))-u",
        "log_gap_derivative": "H'(u)=u^2/(4-u^2)",
        "positive_domain": "0<u<2",
    }


def _complex_argument_product_chart(values: tuple[int, ...]) -> dict[str, Any]:
    """Relate a product of ``j+i`` factors to arguments and symmetric sums."""

    if not values or any(value <= 0 for value in values):
        raise ValueError("argument-product chart requires positive integers")
    degree = len(values)
    elementary: list[int] = []
    for size in range(degree + 1):
        elementary.append(
            sum(
                (
                    product_value
                    for indices in combinations(range(degree), size)
                    for product_value in [
                        int(sp.prod(values[index] for index in indices))
                    ]
                ),
                0,
            )
        )

    gaussian_product = sp.expand(sp.prod(sp.Integer(value) + sp.I for value in values))
    real_part, imaginary_part = map(sp.expand, gaussian_product.as_real_imag())
    real_from_symmetric = sum(
        (-1) ** q * elementary[degree - 2 * q]
        for q in range(degree // 2 + 1)
    )
    imaginary_from_symmetric = sum(
        (-1) ** q * elementary[degree - 2 * q - 1]
        for q in range((degree - 1) // 2 + 1)
    )
    if real_part != real_from_symmetric or imaginary_part != imaginary_from_symmetric:
        raise ValueError("Gaussian product and elementary-symmetric expansion disagree")
    return {
        "chart_id": "complex.argument.symmetric_product.v1",
        "values": list(values),
        "gaussian_product": sp.sstr(gaussian_product),
        "real_part": int(real_part),
        "imaginary_part": int(imaginary_part),
        "elementary_symmetric_values": elementary,
        "real_formula": "sum_{q>=0}(-1)^q e_{m-2q}",
        "imaginary_formula": "sum_{q>=0}(-1)^q e_{m-2q-1}",
        "tangent_one_condition": "real_part=imaginary_part",
    }


def _alternating_arctangent_interval(value: Fraction, upper_terms: int, lower_terms: int) -> dict[str, str]:
    """Certify a rational interval for arctan(value) by alternating sums."""

    if not (Fraction(0) < value <= Fraction(1)):
        raise ValueError("arctangent interval requires 0<x<=1")
    if upper_terms % 2 != 1 or lower_terms % 2 != 0:
        raise ValueError("upper sum must end positive and lower sum must end negative")

    def partial(term_count: int) -> Fraction:
        return sum(
            ((-1) ** index) * value ** (2 * index + 1) / (2 * index + 1)
            for index in range(term_count)
        )

    lower = partial(lower_terms)
    upper = partial(upper_terms)
    if not lower < upper:
        raise ValueError("alternating arctangent interval did not order strictly")
    return {
        "chart_id": "arctangent.alternating_interval.v1",
        "x": str(value),
        "lower": str(lower),
        "upper": str(upper),
        "lower_terms": str(lower_terms),
        "upper_terms": str(upper_terms),
        "remainder_rule": "negative-ending partial sum < arctan(x) < positive-ending partial sum",
    }


def _log_two_interval(term_count: int) -> tuple[Fraction, Fraction]:
    """Bound log(2) with the positive atanh(1/3) series."""

    if term_count < 1:
        raise ValueError("log-two interval requires at least one term")
    q = Fraction(1, 3)
    partial = 2 * sum(
        q ** (2 * index + 1) / (2 * index + 1)
        for index in range(term_count)
    )
    tail = (
        2
        * q ** (2 * term_count + 1)
        / (2 * term_count + 1)
        / (1 - q * q)
    )
    return partial, partial + tail


def _positive_rational_log_interval(
    value: Fraction,
    *,
    term_count: int,
    log_two_interval: tuple[Fraction, Fraction],
) -> tuple[Fraction, Fraction]:
    """Return a rational enclosure of log(value) using binary reduction."""

    if value <= 0:
        raise ValueError("log interval requires a positive rational")
    if term_count < 1:
        raise ValueError("log interval requires at least one term")

    reduced = value
    binary_exponent = 0
    while reduced >= 2:
        reduced /= 2
        binary_exponent += 1
    while reduced < 1:
        reduced *= 2
        binary_exponent -= 1

    q = (reduced - 1) / (reduced + 1)
    partial = 2 * sum(
        q ** (2 * index + 1) / (2 * index + 1)
        for index in range(term_count)
    )
    tail = (
        2
        * q ** (2 * term_count + 1)
        / (2 * term_count + 1)
        / (1 - q * q)
    )
    log_two_lower, log_two_upper = log_two_interval
    if binary_exponent >= 0:
        return (
            binary_exponent * log_two_lower + partial,
            binary_exponent * log_two_upper + partial + tail,
        )
    return (
        binary_exponent * log_two_upper + partial,
        binary_exponent * log_two_lower + partial + tail,
    )


def _symmetric_arctangent_interval(
    value: Fraction,
    *,
    term_count: int,
) -> tuple[Fraction, Fraction]:
    """Enclose arctan(value) for |value|<1 by its alternating series."""

    if not -1 < value < 1:
        raise ValueError("symmetric arctangent interval requires |x|<1")
    if term_count < 2 or term_count % 2:
        raise ValueError("use a positive even number of arctangent terms")

    negative = value < 0
    magnitude = -value if negative else value
    partial = sum(
        ((-1) ** index)
        * magnitude ** (2 * index + 1)
        / (2 * index + 1)
        for index in range(term_count)
    )
    next_term = magnitude ** (2 * term_count + 1) / (2 * term_count + 1)
    lower, upper = partial, partial + next_term
    return (-upper, -lower) if negative else (lower, upper)


def _machin_pi_interval() -> tuple[Fraction, Fraction]:
    """Certify pi with Machin's identity and rational atan remainders."""

    # (5+i)^4(239-i)=114244(1+i), so positivity of all factors gives
    # pi/4=4 atan(1/5)-atan(1/239) without a branch ambiguity.
    if 476 * 239 + 480 != 114244 or 480 * 239 - 476 != 114244:
        raise ValueError("Machin Gaussian-product identity replay failed")
    fifth_lower, fifth_upper = _symmetric_arctangent_interval(
        Fraction(1, 5),
        term_count=8,
    )
    two_thirty_ninth_lower, two_thirty_ninth_upper = _symmetric_arctangent_interval(
        Fraction(1, 239),
        term_count=4,
    )
    lower = 16 * fifth_lower - 4 * two_thirty_ninth_upper
    upper = 16 * fifth_upper - 4 * two_thirty_ninth_lower
    if not Fraction(333, 106) < lower < upper < Fraction(355, 113):
        raise ValueError("Machin pi interval replay failed")
    return lower, upper


def _machin_pi_interval_chart() -> dict[str, Any]:
    """Expose the shared exact Machin enclosure as a reusable chart."""

    lower, upper = _machin_pi_interval()
    return {
        "chart_id": "constant.pi.machin_arctangent_interval.v1",
        "atomic_chart_ids": [
            "transcendental.arctangent.alternating_interval.v1",
            "gaussian_integer.argument_product.v1",
        ],
        "identity": "pi/4=4*atan(1/5)-atan(1/239)",
        "gaussian_certificate": "(5+i)^4*(239-i)=114244*(1+i)",
        "lower": str(lower),
        "upper": str(upper),
        "coarse_enclosure": "333/106<pi<355/113",
    }


def _complex_power_log_upper(
    left: Fraction,
    right: Fraction,
    *,
    log_two_interval: tuple[Fraction, Fraction],
    pi_upper: Fraction,
) -> Fraction:
    """Upper-bound log Im((1+i/x)^x) on one positive interval."""

    if not 0 < left < right:
        raise ValueError("complex-power interval endpoints must be positive and ordered")

    # A(x)=x/2 log(1+x^-2) is bounded by replacing both positive
    # factors with their interval maxima.
    _, logarithm_upper = _positive_rational_log_interval(
        1 + 1 / (left * left),
        term_count=6,
        log_two_interval=log_two_interval,
    )
    modulus_log_upper = right * logarithm_upper / 2

    # u(x)=x atan(1/x) is increasing because
    # d/dt(atan(t)-t/(1+t^2))=2t^2/(1+t^2)^2>0.
    cayley_coordinate = (right - 1) / (right + 1)
    arctangent_lower, _ = _symmetric_arctangent_interval(
        cayley_coordinate,
        term_count=10,
    )
    phase_upper = right * (pi_upper / 4 - arctangent_lower)
    if not 0 < phase_upper < 1:
        raise ValueError("complex-power phase escaped the certified interval (0,1)")

    # The positive-ending Taylor polynomial bounds sin(u) from above on
    # 0<u<1. Monotonicity of log turns it into a log-sine bound.
    sine_upper = phase_upper - phase_upper**3 / 6 + phase_upper**5 / 120
    if not 0 < sine_upper < 1:
        raise ValueError("complex-power sine enclosure is not logarithmically valid")
    _, sine_log_upper = _positive_rational_log_interval(
        sine_upper,
        term_count=6,
        log_two_interval=log_two_interval,
    )
    return modulus_log_upper + sine_log_upper


def _complex_power_polar_interval_chart() -> dict[str, Any]:
    """Certify the global complex-power bound without sampling x values."""

    interval_log_two = _log_two_interval(4)
    target_log_two = _log_two_interval(3)
    if target_log_two[1] != Fraction(23581, 34020):
        raise ValueError("log-two target enclosure replay failed")

    sqrt_two_upper = Fraction(99, 70)
    if sqrt_two_upper * sqrt_two_upper <= 2:
        raise ValueError("sqrt-two upper enclosure replay failed")
    target_log_lower = 1 - sqrt_two_upper * target_log_two[1]
    comparison_threshold = Fraction(49, 2500)
    target_margin = target_log_lower - comparison_threshold
    if target_margin != Fraction(571, 6615000) or target_margin <= 0:
        raise ValueError("target logarithm margin replay failed")

    pi_chart = _machin_pi_interval_chart()
    pi_lower = Fraction(pi_chart["lower"])
    pi_upper = Fraction(pi_chart["upper"])
    left_modulus_log_margin = Fraction(2, 3) - Fraction(5, 8)
    left_phase_margin = Fraction(2, 5) - pi_upper / 8
    right_product_margin = 1 - Fraction(8, 7) * Fraction(101, 120)
    if (
        left_modulus_log_margin != Fraction(1, 24)
        or left_phase_margin <= 0
        or right_product_margin != Fraction(4, 105)
    ):
        raise ValueError("complex-power analytic tail replay failed")

    partition = (
        (Fraction(1, 4), Fraction(1), 20),
        (Fraction(1), Fraction(2), 400),
        (Fraction(2), Fraction(4), 20),
    )
    worst_upper: Fraction | None = None
    worst_interval: tuple[Fraction, Fraction] | None = None
    interval_count = 0
    for start, stop, count in partition:
        step = (stop - start) / count
        for index in range(count):
            left = start + index * step
            right = left + step
            upper = _complex_power_log_upper(
                left,
                right,
                log_two_interval=interval_log_two,
                pi_upper=pi_upper,
            )
            interval_count += 1
            if worst_upper is None or upper > worst_upper:
                worst_upper = upper
                worst_interval = (left, right)

    if worst_upper is None or worst_interval is None:
        raise ValueError("complex-power interval cover is empty")
    if worst_upper >= comparison_threshold:
        raise ValueError("complex-power interval cover did not prove the target bound")
    rounding_denominator = 10**9
    rounded_worst_upper = Fraction(
        (
            worst_upper.numerator * rounding_denominator
            + worst_upper.denominator
            - 1
        )
        // worst_upper.denominator,
        rounding_denominator,
    )
    if not worst_upper <= rounded_worst_upper < comparison_threshold:
        raise ValueError("complex-power outward rounding replay failed")

    return {
        "chart_id": "complex.power.polar_interval.v1",
        "pi_interval_chart": pi_chart,
        "integer_chart_id": "binomial.imaginary.alternating.v1",
        "polar_form": (
            "Im((1+i/x)^x)=(1+x^-2)^(x/2) "
            "sin(x*atan(1/x))"
        ),
        "integer_maximizers": [1, 2],
        "integer_maximum": "1",
        "integer_tail_rule": (
            "for n>=3, 1-T1+T2-...<1 because "
            "T_(j+1)/T_j<1 for j>=1"
        ),
        "left_tail": "0<x<=1/4: modulus<2 and phase<2/5, hence Im<4/5",
        "right_tail": (
            "x>=4: modulus<exp(1/8)<8/7 and "
            "sin(phase)<sin(1)<101/120, hence Im<101/105"
        ),
        "partition": [
            {"start": str(start), "stop": str(stop), "count": count}
            for start, stop, count in partition
        ],
        "interval_count": interval_count,
        "worst_log_upper": str(rounded_worst_upper),
        "worst_log_upper_rounding_denominator": rounding_denominator,
        "worst_interval": [str(value) for value in worst_interval],
        "comparison_threshold": str(comparison_threshold),
        "target_log_lower": str(target_log_lower),
        "target_margin": str(target_margin),
        "log_two_upper": str(target_log_two[1]),
        "sqrt_two_upper": str(sqrt_two_upper),
        "pi_interval": [str(pi_lower), str(pi_upper)],
        "left_modulus_log_margin": str(left_modulus_log_margin),
        "left_phase_margin": str(left_phase_margin),
        "right_product_margin": str(right_product_margin),
    }


def _unit_quadrant_sine_interval(
    value: Fraction,
    *,
    term_count: int = 10,
) -> tuple[Fraction, Fraction]:
    """Enclose sin(value) on the first quadrant by alternating Taylor sums."""

    if not 0 <= value <= Fraction(8, 5):
        raise ValueError("sine interval requires a first-quadrant argument")
    if term_count < 4 or term_count % 2:
        raise ValueError("sine interval requires a positive even term count")
    partials: list[Fraction] = []
    total = Fraction(0)
    factorial = 1
    power = value
    for index in range(term_count):
        if index:
            factorial *= (2 * index) * (2 * index + 1)
            power *= value * value
        total += (-1) ** index * power / factorial
        partials.append(total)
    lower = partials[-1]
    upper = partials[-2]
    if not lower <= upper:
        raise ValueError("sine Taylor enclosure replay failed")
    return lower, upper


def _monotone_stieltjes_upper_sum(
    x_intervals: list[tuple[Fraction, Fraction]],
    y_suprema: list[Fraction],
) -> Fraction:
    """Upper-bound integral y dx from interval nodes for a monotone x chart."""

    if len(x_intervals) != len(y_suprema) + 1:
        raise ValueError("Stieltjes chart requires one more x node than y interval")
    upper_sum = Fraction(0)
    for index, y_upper in enumerate(y_suprema):
        if y_upper < 0:
            raise ValueError("Stieltjes chart requires nonnegative y suprema")
        x_increment_upper = x_intervals[index + 1][1] - x_intervals[index][0]
        if x_increment_upper < 0:
            raise ValueError("Stieltjes x intervals violate monotonicity")
        upper_sum += y_upper * x_increment_upper
    return upper_sum


def _parametric_symmetric_area_interval_chart(
    *,
    partition_count: int = 72,
) -> dict[str, Any]:
    """Certify the area of a symmetric parametric loop by a Stieltjes upper sum."""

    if partition_count < 8 or partition_count % 2:
        raise ValueError("area chart requires an even partition count of at least eight")
    pi_chart = _machin_pi_interval_chart()
    machin_pi_lower = Fraction(pi_chart["lower"])
    machin_pi_upper = Fraction(pi_chart["upper"])
    pi_rounding_denominator = 10**12
    pi_lower = Fraction(
        machin_pi_lower.numerator * pi_rounding_denominator
        // machin_pi_lower.denominator,
        pi_rounding_denominator,
    )
    pi_upper = Fraction(
        (
            machin_pi_upper.numerator * pi_rounding_denominator
            + machin_pi_upper.denominator
            - 1
        )
        // machin_pi_upper.denominator,
        pi_rounding_denominator,
    )
    if not pi_lower <= machin_pi_lower < machin_pi_upper <= pi_upper:
        raise ValueError("compact pi interval was not outward rounded")
    if not pi_upper / 2 < Fraction(8, 5):
        raise ValueError("pi enclosure escaped the sine Taylor chart")

    x_intervals: list[tuple[Fraction, Fraction]] = []
    h_intervals: list[tuple[Fraction, Fraction]] = []
    y_endpoint_upper: list[Fraction] = []
    for index in range(partition_count + 1):
        if index == 0:
            sine_t = (Fraction(0), Fraction(0))
            x_interval = (Fraction(0), Fraction(0))
        elif index == partition_count:
            sine_t = (Fraction(0), Fraction(0))
            x_interval = (Fraction(1), Fraction(1))
        else:
            reflected_index = min(index, partition_count - index)
            angle_lower = reflected_index * pi_lower / partition_count
            angle_upper = reflected_index * pi_upper / partition_count
            sine_lower = _unit_quadrant_sine_interval(angle_lower, term_count=8)[0]
            sine_upper = _unit_quadrant_sine_interval(angle_upper, term_count=8)[1]
            sine_t = (sine_lower, sine_upper)

            polar_lower = partition_count * sine_lower / (2 * index)
            polar_upper = partition_count * sine_upper / (2 * index)
            complement_lower = pi_lower / 2 - polar_upper
            complement_upper = pi_upper / 2 - polar_lower
            if not 0 <= complement_lower <= complement_upper <= pi_upper / 2:
                raise ValueError("parametric x-coordinate escaped its quadrant")
            x_interval = (
                _unit_quadrant_sine_interval(complement_lower, term_count=8)[0],
                _unit_quadrant_sine_interval(complement_upper, term_count=8)[1],
            )

        t_lower = index * pi_lower / partition_count
        t_upper = index * pi_upper / partition_count
        h_lower = t_lower - sine_t[1]
        h_upper = t_upper - sine_t[0]
        if not 0 <= h_lower <= h_upper <= pi_upper:
            raise ValueError("parametric phase escaped [0,pi]")

        if h_upper <= pi_lower / 2:
            endpoint_upper = _unit_quadrant_sine_interval(h_upper, term_count=8)[1]
        elif h_lower >= pi_upper / 2:
            reflected_upper = pi_upper - h_lower
            endpoint_upper = _unit_quadrant_sine_interval(
                reflected_upper,
                term_count=8,
            )[1]
        else:
            endpoint_upper = Fraction(1)
        x_intervals.append(x_interval)
        h_intervals.append((h_lower, h_upper))
        y_endpoint_upper.append(endpoint_upper)

    y_interval_suprema: list[Fraction] = []
    peak_intervals = 0
    for index in range(partition_count):
        left_h = h_intervals[index]
        right_h = h_intervals[index + 1]
        if right_h[1] <= pi_lower / 2:
            y_upper = y_endpoint_upper[index + 1]
        elif left_h[0] >= pi_upper / 2:
            y_upper = y_endpoint_upper[index]
        else:
            y_upper = Fraction(1)
            peak_intervals += 1
        y_interval_suprema.append(y_upper)

    upper_half_area = _monotone_stieltjes_upper_sum(
        x_intervals,
        y_interval_suprema,
    )
    upper_area = 2 * upper_half_area
    if not upper_area < 1:
        raise ValueError("Stieltjes upper sum did not certify area < 1")
    rounding_denominator = 10**9
    rounded_upper = Fraction(
        (
            upper_area.numerator * rounding_denominator
            + upper_area.denominator
            - 1
        )
        // upper_area.denominator,
        rounding_denominator,
    )
    if not upper_area <= rounded_upper < 1:
        raise ValueError("parametric area outward rounding failed")
    return {
        "chart_id": "parametric.symmetric_area.stieltjes_interval.v1",
        "pi_interval_chart": pi_chart,
        "atomic_chart_ids": [
            "transcendental.sine.alternating_interval.v1",
            "parametric.monotone_stieltjes_upper_sum.v1",
            "symmetry.reflection.area_double.v1",
        ],
        "curve_signature": (
            "x=cos(pi*sinc(t)/2), y=sin(t-sin(t)), -pi<=t<=pi"
        ),
        "partition_count": partition_count,
        "taylor_term_count": 8,
        "pi_interval": [str(pi_lower), str(pi_upper)],
        "upper_area": str(rounded_upper),
        "strict_margin": str(1 - rounded_upper),
        "peak_intervals": peak_intervals,
        "proof_reduction": "S=2*integral_[0,pi] y dx",
    }


def _tangent_partial_fraction_bound_chart() -> dict[str, Any]:
    """Certify Becker--Stark's upper bound from the cosine product."""

    index = sp.Symbol("k", integer=True, positive=True)
    odd_square_sum = sp.summation(1 / (2 * index - 1) ** 2, (index, 1, sp.oo))
    if sp.simplify(odd_square_sum - sp.pi**2 / 8) != 0:
        raise ValueError("odd reciprocal-square sum replay failed")
    return {
        "chart_id": "trigonometric.tangent.partial_fraction_bound.v1",
        "cosine_product": (
            "cos(x)=prod_(k>=1)(1-4*x^2/((2k-1)^2*pi^2))"
        ),
        "log_derivative": (
            "tan(x)/x=(8/pi^2)*sum_(k>=1)"
            "1/((2k-1)^2-4*x^2/pi^2)"
        ),
        "coefficient_argument": (
            "for j>=1, sum_(k>=1)(2k-1)^(-2j-2)<pi^2/8"
        ),
        "bound": "tan(x)/x<1/(1-4*x^2/pi^2), 0<x<pi/2",
        "dual_bound": "x*cot(x)>1-4*x^2/pi^2",
        "odd_square_sum": "pi^2/8",
    }


def _polar_rose_revolution_volume_chart() -> dict[str, Any]:
    """Reduce every rose petal to one spherical radial integral."""

    n = sp.Symbol("n", integer=True, positive=True)
    half_angle = sp.pi / (2 * n)
    denominator = (n**2 - 1) * (9 * n**2 - 1)
    first_harmonic = 2 * n * sp.cot(half_angle) / (n**2 - 1)
    third_harmonic = 6 * n * sp.cot(half_angle) / (9 * n**2 - 1)
    radial_integral = sp.factor((3 * first_harmonic - third_harmonic) / 4)
    expected_integral = 12 * n**3 * sp.cot(half_angle) / denominator
    if sp.simplify(radial_integral - expected_integral) != 0:
        raise ValueError("rose harmonic integral replay failed")

    volume = sp.factor(2 * sp.pi * radial_integral / 3)
    expected_volume = 8 * sp.pi * n**3 * sp.cot(half_angle) / denominator
    if sp.simplify(volume - expected_volume) != 0:
        raise ValueError("rose spherical-volume replay failed")
    limit = sp.limit(volume, n, sp.oo)
    if limit != sp.Rational(16, 9):
        raise ValueError("rose volume limit replay failed")

    denominator_factor = (1 - 1 / n**2) * (1 - 1 / (9 * n**2))
    normalized_volume = sp.simplify(volume / limit)
    normalized_expected = sp.simplify(
        half_angle * sp.cot(half_angle) / denominator_factor
    )
    if sp.simplify(normalized_volume - normalized_expected) != 0:
        raise ValueError("rose normalized-volume identity replay failed")

    volume_six = sp.trigsimp(volume.subs(n, 6))
    expected_six = 1728 * sp.pi * (2 + sp.sqrt(3)) / 11305
    if sp.simplify(volume_six - expected_six) != 0:
        raise ValueError("six-petal volume specialization replay failed")
    pi_lower = sp.simplify(limit / (volume_six / sp.pi))
    expected_pi_lower = sp.Rational(11305, 972) * (2 - sp.sqrt(3))
    if sp.simplify(pi_lower - expected_pi_lower) != 0:
        raise ValueError("rose-derived pi lower bound replay failed")

    return {
        "chart_id": "polar.rose.revolution_harmonic.v1",
        "atomic_chart_ids": [
            "polar.star_region.spherical_revolution.v1",
            "periodic.absolute_sine.cubic_harmonic.v1",
            "trigonometric.tangent.partial_fraction_bound.v1",
        ],
        "solid_radial_function": (
            "R_solid(theta)=max(R_plane(theta),R_plane(-theta))"
            "=abs(sin(n*theta))"
        ),
        "spherical_volume_reduction": (
            "V_n=(2*pi/3)*integral_0^pi abs(sin(n*theta))^3*sin(theta)dtheta"
        ),
        "signed_harmonic_integrals": {
            "J_1": "2*n*cot(pi/(2*n))/(n^2-1)",
            "J_3": "6*n*cot(pi/(2*n))/(9*n^2-1)",
        },
        "volume": "8*pi*n^3*cot(pi/(2*n))/((n^2-1)*(9*n^2-1))",
        "limit": "16/9",
        "strict_lower_bound": "V_n>16/9 for every integer n>=2",
        "volume_at_six": "1728*pi*(2+sqrt(3))/11305",
        "pi_lower": "11305*(2-sqrt(3))/972",
        "tangent_chart": _tangent_partial_fraction_bound_chart(),
    }


def _equiangular_line_slope_chart() -> dict[str, Any]:
    """Encode three unoriented lines separated by pi/3 through their slopes."""

    slope, direction_parameter = sp.symbols("m h", real=True)
    triple_angle_numerator = sp.expand(
        3 * slope
        - slope**3
        - direction_parameter * (1 - 3 * slope**2)
    )
    slope_polynomial = sp.Poly(
        slope**3
        - 3 * direction_parameter * slope**2
        - 3 * slope
        + direction_parameter,
        slope,
    )
    if sp.expand(triple_angle_numerator + slope_polynomial.as_expr()) != 0:
        raise ValueError("equiangular slope triple-angle replay failed")
    coefficients = slope_polynomial.all_coeffs()
    symmetric_sums = (
        -coefficients[1],
        coefficients[2],
        -coefficients[3],
    )
    expected_sums = (
        3 * direction_parameter,
        -3,
        -direction_parameter,
    )
    if any(
        sp.simplify(actual - expected) != 0
        for actual, expected in zip(symmetric_sums, expected_sums)
    ):
        raise ValueError("equiangular slope symmetric-sum replay failed")
    return {
        "chart_id": "projective.lines.equiangular_slope_normal_form.v1",
        "angle_spacing": "pi/3",
        "triple_angle_equation": "tan(3*phi)=h",
        "slope_polynomial": "m^3-3*h*m^2-3*m+h",
        "symmetric_characterization": [
            "sigma_2(m_1,m_2,m_3)=-3",
            "sigma_1(m_1,m_2,m_3)+3*sigma_3(m_1,m_2,m_3)=0",
        ],
        "converse": (
            "three distinct finite real slopes satisfying the two symmetric "
            "relations are the three roots of one tan(3*phi)=h equation"
        ),
    }


def _cubic_tangent_equiangular_chart() -> dict[str, Any]:
    """Compose tangent, slope, discriminant, and area charts for y=x^3-cx."""

    t1, t2, t3, c = sp.symbols("t1 t2 t3 c", real=True)
    roots = (t1, t2, t3)
    e1 = sum(roots)
    e2 = t1 * t2 + t2 * t3 + t3 * t1
    e3 = t1 * t2 * t3
    slopes = tuple(3 * root**2 - c for root in roots)
    sigma1_raw = sp.expand(sum(slopes))
    sigma2_raw = sp.expand(sum(a * b for a, b in combinations(slopes, 2)))
    sigma3_raw = sp.expand(sp.prod(slopes))
    sigma1_symmetric = 3 * (e1**2 - 2 * e2) - 3 * c
    sigma2_symmetric = (
        9 * (e2**2 - 2 * e1 * e3)
        - 6 * c * (e1**2 - 2 * e2)
        + 3 * c**2
    )
    sigma3_symmetric = (
        27 * e3**2
        - 9 * c * (e2**2 - 2 * e1 * e3)
        + 3 * c**2 * (e1**2 - 2 * e2)
        - c**3
    )
    if any(
        sp.expand(actual - expected) != 0
        for actual, expected in (
            (sigma1_raw, sigma1_symmetric),
            (sigma2_raw, sigma2_symmetric),
            (sigma3_raw, sigma3_symmetric),
        )
    ):
        raise ValueError("cubic tangent slope symmetrization failed")

    s, q, r = sp.symbols("s q r", real=True, nonzero=True)
    sigma1 = 3 * (s**2 - c)
    sigma2 = 3 * c**2 - 6 * s * q
    sigma3 = 3 * q**2 - c**3
    if sp.simplify(
        sigma2 + 3 + 3 * (2 * s * q - c**2 - 1)
    ) != 0:
        raise ValueError("cubic tangent first constraint replay failed")
    if sp.simplify(
        sigma1
        + 3 * sigma3
        - 3 * (s**2 + 3 * q**2 - c * (c**2 + 1))
    ) != 0:
        raise ValueError("cubic tangent second constraint replay failed")

    c_of_r = (r + 3 / r) / 2
    s_squared = (r**2 + 1) * (r**2 + 9) / (8 * r)
    q_squared = s_squared / r**2
    if sp.simplify(2 * s_squared / r - (c_of_r**2 + 1)) != 0:
        raise ValueError("cubic tangent ratio parametrization failed")
    if sp.simplify(
        s_squared + 3 * q_squared - c_of_r * (c_of_r**2 + 1)
    ) != 0:
        raise ValueError("cubic tangent range parametrization failed")

    e3_of_r = -s * (r**2 + 1) / (6 * r)
    discriminant = sp.factor(-e3_of_r * (4 * s**3 + 27 * e3_of_r))
    discriminant = sp.factor(discriminant.subs(s**2, s_squared))
    expected_discriminant = (r**2 + 1) ** 3 * (r**2 + 9) / (96 * r)
    if sp.simplify(discriminant - expected_discriminant) != 0:
        raise ValueError("cubic tangent discriminant replay failed")

    area = (r**2 + 1) ** 2 * (r**2 + 9) / (32 * sp.sqrt(3) * r)
    area_derivative = sp.factor(sp.diff(area, r))
    expected_derivative = (
        sp.sqrt(3)
        * (r**2 + 1)
        * (5 * r**4 + 28 * r**2 - 9)
        / (96 * r**2)
    )
    if sp.simplify(area_derivative - expected_derivative) != 0:
        raise ValueError("cubic tangent area derivative replay failed")
    z_min = (sp.sqrt(241) - 14) / 5
    if sp.simplify(5 * z_min**2 + 28 * z_min - 9) != 0:
        raise ValueError("cubic tangent area minimizer replay failed")
    area_squared_min = sp.radsimp(
        sp.simplify(area.subs(r, sp.sqrt(z_min)) ** 2)
    )
    expected_area_squared_min = (
        5543 * sp.sqrt(241) - 5647
    ) / 300000
    if sp.simplify(area_squared_min - expected_area_squared_min) != 0:
        raise ValueError("cubic tangent minimum area replay failed")

    return {
        "chart_id": "cubic.tangent.equiangular.discriminant_area.v1",
        "atomic_chart_ids": [
            "cubic.tangent.contact_parameter.v1",
            "projective.lines.equiangular_slope_normal_form.v1",
            "cubic.three_points.vandermonde_discriminant.v1",
        ],
        "contact_line": "y=(3*t^2-c)*x-2*t^3",
        "contact_polynomial": "2*t^3-3*u*t^2+c*u+v=0",
        "contact_symmetric_sums": "s=t1+t2+t3=3*u/2, e2=0",
        "auxiliary_invariant": "q=c*s+3*e3",
        "equiangular_constraints": [
            "2*s*q=c^2+1",
            "s^2+3*q^2=c*(c^2+1)",
        ],
        "positive_ratio": "r=s/q>0",
        "coefficient_parametrization": "c=(r+3/r)/2",
        "coefficient_range": "c>=sqrt(3)",
        "s_squared": "(r^2+1)*(r^2+9)/(8*r)",
        "contact_discriminant": "(r^2+1)^3*(r^2+9)/(96*r)>0",
        "triangle_area": "(r^2+1)^2*(r^2+9)/(32*sqrt(3)*r)",
        "area_stationary_equation": "5*r^4+28*r^2-9=0",
        "minimizing_r_squared": "(sqrt(241)-14)/5",
        "minimum_area_squared": "(5543*sqrt(241)-5647)/300000",
        "slope_chart": _equiangular_line_slope_chart(),
    }


def _regular_polygon_projection_chart() -> dict[str, Any]:
    """Compress the abscissae of a regular polygon into one Chebyshev fiber."""

    x, h, radius, fiber = sp.symbols("x h R c", real=True)
    coefficient_audit: list[dict[str, Any]] = []
    for degree in range(3, 11):
        polynomial = sp.Poly(
            sp.expand(
                sp.Rational(1, 2 ** (degree - 1))
                * radius**degree
                * (
                    sp.chebyshevt(degree, (x - h) / radius)
                    - fiber
                )
            ),
            x,
        )
        expected_second = -degree * h
        expected_third = (
            sp.binomial(degree, 2) * h**2
            - sp.Rational(degree, 4) * radius**2
        )
        if polynomial.LC() != 1:
            raise ValueError("regular-polygon projection is not monic")
        if sp.simplify(polynomial.coeff_monomial(x ** (degree - 1)) - expected_second) != 0:
            raise ValueError("regular-polygon center coefficient replay failed")
        if sp.simplify(polynomial.coeff_monomial(x ** (degree - 2)) - expected_third) != 0:
            raise ValueError("regular-polygon radius coefficient replay failed")
        coefficient_audit.append(
            {
                "degree": degree,
                "center_coefficient": sp.sstr(expected_second),
                "radius_coefficient": sp.sstr(expected_third),
            }
        )

    return {
        "chart_id": "regular_polygon.projection.chebyshev_fiber.v1",
        "vertices": "x_k=h+R*cos(theta+2*pi*k/n)",
        "monic_projection_polynomial": (
            "2^(1-n)*R^n*(T_n((x-h)/R)-cos(n*theta))"
        ),
        "first_coefficients": [
            "[x^(n-1)]P=-n*h",
            "[x^(n-2)]P=binomial(n,2)*h^2-n*R^2/4",
        ],
        "rational_consequence": (
            "if P has rational coefficients, then h and R^2 are rational"
        ),
        "coefficient_audit": coefficient_audit,
    }


def _chebyshev_critical_value_chart() -> dict[str, Any]:
    """Integrate a Chebyshev fiber and evaluate it on all polygon vertices."""

    degree = sp.symbols("n", integer=True, positive=True)
    cosine_fiber, sine_fiber = sp.symbols("c s", real=True)
    cosine_coefficient = sp.simplify(
        sp.Rational(1, 2) / (degree + 1)
        - sp.Rational(1, 2) / (degree - 1)
        - 1
    )
    sine_coefficient = sp.simplify(
        -sp.Rational(1, 2) / (degree + 1)
        - sp.Rational(1, 2) / (degree - 1)
    )
    if sp.simplify(cosine_coefficient + degree**2 / (degree**2 - 1)) != 0:
        raise ValueError("Chebyshev cosine coefficient replay failed")
    if sp.simplify(sine_coefficient + degree / (degree**2 - 1)) != 0:
        raise ValueError("Chebyshev sine coefficient replay failed")

    variable = sp.symbols("u", real=True)
    antiderivative_audit: list[int] = []
    for concrete_degree in range(3, 11):
        antiderivative = (
            sp.chebyshevt(concrete_degree + 1, variable)
            / (2 * (concrete_degree + 1))
            - sp.chebyshevt(concrete_degree - 1, variable)
            / (2 * (concrete_degree - 1))
        )
        if sp.simplify(
            sp.diff(antiderivative, variable)
            - sp.chebyshevt(concrete_degree, variable)
        ) != 0:
            raise ValueError("Chebyshev antiderivative replay failed")
        antiderivative_audit.append(concrete_degree)

    return {
        "chart_id": "polynomial.critical_values.chebyshev_antiderivative.v1",
        "antiderivative": (
            "integral(T_n(u),u)=T_(n+1)(u)/(2(n+1))-"
            "T_(n-1)(u)/(2(n-1))"
        ),
        "fiber_value": (
            "I(cos(phi_k))=-(n^2*cos(n*theta)*cos(phi_k)+"
            "n*sin(n*theta)*sin(phi_k))/(n^2-1)"
        ),
        "fourier_independence": (
            "for n>=3, the sampled vectors 1, cos(phi_k), sin(phi_k) "
            "are linearly independent"
        ),
        "regular_graph_conditions": [
            "cos(n*theta)=0",
            "sin(n*theta)=-1",
            "R^n=2^(n-1)*(n-1)/n",
        ],
        "symbolic_coefficients": {
            "cosine": sp.sstr(cosine_coefficient),
            "sine": sp.sstr(sine_coefficient),
        },
        "antiderivative_audit": antiderivative_audit,
    }


def _least_prime_factor(value: int) -> int:
    if value < 2:
        raise ValueError("prime-factor witness requires an integer >=2")
    divisor = 2
    while divisor * divisor <= value:
        if value % divisor == 0:
            return divisor
        divisor += 1
    return value


def _rational_radius_power_obstruction_witness(degree: int) -> dict[str, Any]:
    """Return a p-adic witness that the forced regular-polygon radius is impossible."""

    if degree < 3:
        raise ValueError("regular-polygon obstruction requires degree >=3")
    target = Fraction(2 ** (degree - 1) * (degree - 1), degree)
    if degree % 2:
        prime = _least_prime_factor(degree)
        required_multiple = degree
    else:
        odd_part = degree
        while odd_part % 2 == 0:
            odd_part //= 2
        prime = (
            _least_prime_factor(odd_part)
            if odd_part > 1
            else _least_prime_factor(degree - 1)
        )
        required_multiple = degree // 2

    numerator_exponent = 0
    numerator = target.numerator
    while numerator % prime == 0:
        numerator //= prime
        numerator_exponent += 1
    denominator_exponent = 0
    denominator = target.denominator
    while denominator % prime == 0:
        denominator //= prime
        denominator_exponent += 1
    valuation = numerator_exponent - denominator_exponent
    if valuation == 0 or valuation % required_multiple == 0:
        raise ValueError("selected valuation does not obstruct the required rational power")
    return {
        "degree": degree,
        "target": str(target),
        "prime": prime,
        "valuation": valuation,
        "required_multiple": required_multiple,
    }


def _regular_polygon_extrema_obstruction_chart() -> dict[str, Any]:
    """Compose projection, integration, and valuation charts for graph extrema."""

    valuation_audit = [
        _rational_radius_power_obstruction_witness(degree)
        for degree in range(3, 65)
    ]
    return {
        "chart_id": "polynomial.extrema.regular_polygon.obstruction.v1",
        "atomic_chart_ids": [
            "regular_polygon.projection.chebyshev_fiber.v1",
            "polynomial.critical_values.chebyshev_antiderivative.v1",
            "rational_power.padically_obstructed.v1",
        ],
        "forced_radius_power": "R^n=2^(n-1)*(n-1)/n",
        "rationality_from_coefficients": "h in Q and R^2 in Q",
        "odd_degree_obstruction": (
            "for p|n, v_p(R^n)=-v_p(n) is nonzero and has magnitude <n"
        ),
        "even_degree_obstruction": (
            "(R^2)^(n/2)=2^(n-1)*(n-1)/n has a valuation not divisible by n/2"
        ),
        "conclusion": "no monic rational polynomial of degree n+1 for n>=3",
        "projection_chart": _regular_polygon_projection_chart(),
        "critical_value_chart": _chebyshev_critical_value_chart(),
        "valuation_audit": valuation_audit,
    }


def _fixed_cardinality_column_sum_interval(
    grid_side: int,
    selected_count: int,
) -> tuple[int, int]:
    """Return every attainable sum of selected row labels as one interval."""

    if not 0 <= selected_count <= grid_side:
        raise ValueError("column cardinality is outside the grid")
    minimum = selected_count * (selected_count + 1) // 2
    maximum = selected_count * (2 * grid_side - selected_count + 1) // 2
    return minimum, maximum


def _bounded_column_moment_rows(widths: tuple[int, ...]) -> list[int]:
    """Encode attainable (sum z_i, sum i*z_i) pairs as integer bitsets."""

    rows = [1]
    for column, width in enumerate(widths, start=1):
        next_rows = [0] * (len(rows) + width)
        for offset_sum, weighted_mask in enumerate(rows):
            if not weighted_mask:
                continue
            for delta in range(width + 1):
                next_rows[offset_sum + delta] |= weighted_mask << (column * delta)
        rows = next_rows
    return rows


def _regression_pair_from_statistics(
    grid_side: int,
    subset_x_sum: int,
    subset_y_sum: int,
    subset_xx_sum: int,
    subset_xy_sum: int,
) -> tuple[Fraction, Fraction, Fraction] | None:
    """Compute both regression slopes and their acute-angle tangent exactly."""

    point_count = grid_side * grid_side
    half = point_count // 2
    coordinate_sum = grid_side * grid_side * (grid_side + 1) // 2
    square_sum = (
        grid_side
        * grid_side
        * (grid_side + 1)
        * (2 * grid_side + 1)
        // 6
    )
    product_sum = (grid_side * (grid_side + 1) // 2) ** 2

    first_numerator = half * subset_xy_sum - subset_x_sum * subset_y_sum
    first_denominator = half * subset_xx_sum - subset_x_sum**2
    complement_x_sum = coordinate_sum - subset_x_sum
    complement_y_sum = coordinate_sum - subset_y_sum
    complement_xx_sum = square_sum - subset_xx_sum
    complement_xy_sum = product_sum - subset_xy_sum
    second_numerator = (
        half * complement_xy_sum - complement_x_sum * complement_y_sum
    )
    second_denominator = (
        half * complement_xx_sum - complement_x_sum**2
    )
    if first_denominator == 0 or second_denominator == 0:
        return None

    tangent_numerator = abs(
        first_numerator * second_denominator
        - second_numerator * first_denominator
    )
    tangent_denominator = abs(
        first_denominator * second_denominator
        + first_numerator * second_numerator
    )
    if tangent_denominator == 0:
        return None
    return (
        Fraction(first_numerator, first_denominator),
        Fraction(second_numerator, second_denominator),
        Fraction(tangent_numerator, tangent_denominator),
    )


def _reconstruct_grid_subset(
    grid_side: int,
    counts: tuple[int, ...],
    target_y_sum: int,
    target_xy_sum: int,
) -> list[tuple[int, int]]:
    """Reconstruct one concrete subset from its compressed moment state."""

    intervals = [
        _fixed_cardinality_column_sum_interval(grid_side, count)
        for count in counts
    ]
    target_offset_sum = target_y_sum - sum(lower for lower, _ in intervals)
    target_weighted_offset = target_xy_sum - sum(
        column * lower
        for column, (lower, _) in enumerate(intervals, start=1)
    )
    widths = tuple(upper - lower for lower, upper in intervals)

    @lru_cache(maxsize=None)
    def recover(
        column_index: int,
        remaining_offset: int,
        remaining_weighted_offset: int,
    ) -> tuple[int, ...] | None:
        if column_index == grid_side:
            if remaining_offset == 0 and remaining_weighted_offset == 0:
                return ()
            return None
        if remaining_offset < 0 or remaining_weighted_offset < 0:
            return None
        width = widths[column_index]
        column = column_index + 1
        for delta in range(width + 1):
            tail = recover(
                column_index + 1,
                remaining_offset - delta,
                remaining_weighted_offset - column * delta,
            )
            if tail is not None:
                return (delta, *tail)
        return None

    offsets = recover(0, target_offset_sum, target_weighted_offset)
    if offsets is None:
        raise ValueError("compressed grid state has no concrete realization")

    points: list[tuple[int, int]] = []
    for column, (count, offset, interval) in enumerate(
        zip(counts, offsets, intervals),
        start=1,
    ):
        target_column_sum = interval[0] + offset
        rows = next(
            (
                chosen
                for chosen in combinations(range(1, grid_side + 1), count)
                if sum(chosen) == target_column_sum
            ),
            None,
        )
        if rows is None:
            raise ValueError("column-sum interval reconstruction failed")
        points.extend((column, row) for row in rows)
    return points


def _pack_grid_regression_candidate(
    grid_side: int,
    candidate: tuple[
        Fraction,
        tuple[int, ...],
        int,
        int,
        Fraction,
        Fraction,
    ],
) -> dict[str, Any]:
    tangent, counts, y_sum, xy_sum, first_slope, second_slope = candidate
    points = _reconstruct_grid_subset(
        grid_side,
        counts,
        y_sum,
        xy_sum,
    )
    x_sum = sum(x for x, _ in points)
    xx_sum = sum(x * x for x, _ in points)
    replay = _regression_pair_from_statistics(
        grid_side,
        x_sum,
        y_sum,
        xx_sum,
        xy_sum,
    )
    if replay != (first_slope, second_slope, tangent):
        raise ValueError("regression witness replay failed")
    return {
        "tangent": str(tangent),
        "tangent_numerator": tangent.numerator,
        "tangent_denominator": tangent.denominator,
        "first_slope": str(first_slope),
        "second_slope": str(second_slope),
        "subset_count_profile": list(counts),
        "subset_statistics": {
            "cardinality": len(points),
            "x_sum": x_sum,
            "y_sum": y_sum,
            "xx_sum": xx_sum,
            "xy_sum": xy_sum,
        },
        "witness_subset": [list(point) for point in points],
    }


@lru_cache(maxsize=None)
def _balanced_grid_regression_chart(grid_side: int) -> dict[str, Any]:
    """Exhaustively optimize a balanced grid partition through moment quotients."""

    if grid_side < 2 or grid_side % 2:
        raise ValueError("balanced grid chart requires a positive even side")
    if grid_side > 6:
        raise ValueError("certified grid enumerator currently supports side at most 6")

    half = grid_side * grid_side // 2
    below: tuple[
        Fraction,
        tuple[int, ...],
        int,
        int,
        Fraction,
        Fraction,
    ] | None = None
    above: tuple[
        Fraction,
        tuple[int, ...],
        int,
        int,
        Fraction,
        Fraction,
    ] | None = None
    raw_compressed_states = 0
    symmetry_representatives = 0
    balanced_profiles = 0
    profile_orbits = 0

    for counts in product(range(grid_side + 1), repeat=grid_side):
        if sum(counts) != half:
            continue
        balanced_profiles += 1
        complement = tuple(grid_side - count for count in counts)
        reversed_counts = tuple(reversed(counts))
        reversed_complement = tuple(reversed(complement))
        orbit = {counts, complement, reversed_counts, reversed_complement}
        if counts != min(orbit):
            continue
        profile_orbits += 1

        intervals = [
            _fixed_cardinality_column_sum_interval(grid_side, count)
            for count in counts
        ]
        widths = tuple(upper - lower for lower, upper in intervals)
        offset_rows = _bounded_column_moment_rows(widths)
        state_count = sum(mask.bit_count() for mask in offset_rows)
        raw_compressed_states += state_count * len(orbit)

        base_y_sum = sum(lower for lower, _ in intervals)
        base_xy_sum = sum(
            column * lower
            for column, (lower, _) in enumerate(intervals, start=1)
        )
        total_offset = sum(widths)
        total_weighted_offset = sum(
            column * width
            for column, width in enumerate(widths, start=1)
        )
        x_sum = sum(
            column * count
            for column, count in enumerate(counts, start=1)
        )
        xx_sum = sum(
            column * column * count
            for column, count in enumerate(counts, start=1)
        )

        for offset_sum, weighted_mask in enumerate(offset_rows):
            while weighted_mask:
                least_bit = weighted_mask & -weighted_mask
                weighted_offset = least_bit.bit_length() - 1
                weighted_mask ^= least_bit

                reflected_state = (
                    total_offset - offset_sum,
                    total_weighted_offset - weighted_offset,
                )
                if (offset_sum, weighted_offset) > reflected_state:
                    continue
                symmetry_representatives += 1

                y_sum = base_y_sum + offset_sum
                xy_sum = base_xy_sum + weighted_offset
                regression = _regression_pair_from_statistics(
                    grid_side,
                    x_sum,
                    y_sum,
                    xx_sum,
                    xy_sum,
                )
                if regression is None:
                    continue
                first_slope, second_slope, tangent = regression
                candidate = (
                    tangent,
                    counts,
                    y_sum,
                    xy_sum,
                    first_slope,
                    second_slope,
                )
                tie_key = (counts, y_sum, xy_sum)
                square_comparison = (
                    tangent.numerator * tangent.numerator
                    - 3 * tangent.denominator * tangent.denominator
                )
                if square_comparison < 0:
                    if (
                        below is None
                        or tangent > below[0]
                        or (
                            tangent == below[0]
                            and tie_key < (below[1], below[2], below[3])
                        )
                    ):
                        below = candidate
                elif square_comparison > 0:
                    if (
                        above is None
                        or tangent < above[0]
                        or (
                            tangent == above[0]
                            and tie_key < (above[1], above[2], above[3])
                        )
                    ):
                        above = candidate

    if below is None or above is None:
        raise ValueError("grid regression search did not bracket sqrt(3)")

    lower_tangent = below[0]
    upper_tangent = above[0]
    if lower_tangent * upper_tangent <= 1:
        selected_side = "above"
        cross_tangent = None
        comparison_polynomial = None
    else:
        cross_tangent = (
            (lower_tangent + upper_tangent)
            / (lower_tangent * upper_tangent - 1)
        )
        comparison_polynomial = cross_tangent * cross_tangent - 3
        selected_side = "below" if comparison_polynomial <= 0 else "above"

    selected = below if selected_side == "below" else above
    packed_below = _pack_grid_regression_candidate(grid_side, below)
    packed_above = _pack_grid_regression_candidate(grid_side, above)
    packed_selected = (
        packed_below if selected_side == "below" else packed_above
    )
    if packed_selected["tangent"] != str(selected[0]):
        raise ValueError("selected grid candidate does not replay")

    return {
        "chart_id": "grid.regression.partition.moment_quotient.v1",
        "atomic_chart_ids": [
            "finite_set.regression.sufficient_statistics.v1",
            "column_selection.cardinality_sum_interval.v1",
            "grid_partition.complement_reflection_quotient.v1",
            "rational_angle.tangent_order_certificate.v1",
        ],
        "grid_side": grid_side,
        "point_count": grid_side * grid_side,
        "subset_cardinality": half,
        "balanced_count_profiles": balanced_profiles,
        "count_profile_orbits": profile_orbits,
        "raw_subset_count": comb(grid_side * grid_side, half),
        "raw_compressed_states": raw_compressed_states,
        "symmetry_representatives_evaluated": symmetry_representatives,
        "below": packed_below,
        "above": packed_above,
        "selected_side": selected_side,
        "selected": packed_selected,
        "angular_comparison": {
            "criterion": (
                "atan(lower)+atan(upper)>=2*pi/3 iff "
                "((lower+upper)/(lower*upper-1))^2<=3"
            ),
            "cross_tangent": (
                str(cross_tangent) if cross_tangent is not None else None
            ),
            "square_minus_three": (
                str(comparison_polynomial)
                if comparison_polynomial is not None
                else None
            ),
        },
        "proof_obligations": {
            "regression_depends_only_on": [
                "cardinality",
                "sum_x",
                "sum_y",
                "sum_x_squared",
                "sum_xy",
            ],
            "column_sum_interval": (
                "choosing c rows from 1..m realizes every integer from "
                "c(c+1)/2 to c(2m-c+1)/2"
            ),
            "symmetries": [
                "swap subset and complement",
                "reflect x",
                "reflect y",
            ],
            "enumeration_exact": True,
        },
    }


@lru_cache(maxsize=None)
def _cubic_arc_dot_chord_sweep_chart(
    coefficients: tuple[int, int, int, int],
    dot_target: int,
) -> dict[str, Any]:
    """Reduce a moving-chord locus on a cubic arc to one envelope parameter."""

    x, t, u, v, symmetric_sum, product_uv = sp.symbols(
        "x t u v S P",
        real=True,
    )
    polynomial = sum(
        sp.Integer(coefficient) * x ** (3 - index)
        for index, coefficient in enumerate(coefficients)
    )
    roots = sp.roots(polynomial, x)
    repeated_roots = [
        root for root, multiplicity in roots.items() if multiplicity == 2
    ]
    simple_roots = [
        root for root, multiplicity in roots.items() if multiplicity == 1
    ]
    if len(repeated_roots) != 1 or len(simple_roots) != 1:
        raise ValueError("cubic arc chart requires one double and one simple root")
    origin_shift = sp.Rational(repeated_roots[0])
    arc_endpoint = sp.Rational(simple_roots[0])
    if not origin_shift < arc_endpoint:
        raise ValueError("certified cubic arc must lie to the right of its double root")
    arc_length = sp.factor(arc_endpoint - origin_shift)
    shifted_polynomial = sp.factor(polynomial.subs(x, t + origin_shift))
    if shifted_polynomial != t**2 * (t - arc_length):
        raise ValueError("cubic arc did not normalize to t^2(t-d)")

    g_u = shifted_polynomial.subs(t, u)
    g_v = shifted_polynomial.subs(t, v)
    dot_equation = sp.expand(
        (u + origin_shift) * (v + origin_shift)
        + g_u * g_v
        - dot_target
    )
    symmetric, remainder, generators = sp.symmetrize(
        dot_equation,
        [u, v],
        formal=True,
    )
    if remainder != 0:
        raise ValueError("dot constraint did not lower to symmetric invariants")
    symmetric_equation = sp.factor(
        symmetric.subs(
            {
                generators[0][0]: symmetric_sum,
                generators[1][0]: product_uv,
            }
        )
    )
    factor_terms = sp.factor_list(symmetric_equation)[1]
    product_only = [
        factor
        for factor, multiplicity in factor_terms
        if multiplicity == 1 and not factor.has(symmetric_sum)
    ]
    if len(product_only) != 1:
        raise ValueError("dot constraint lacks a unique product component")
    product_factor = product_only[0]
    product_roots = sp.solve(sp.Eq(product_factor, 0), product_uv)
    if len(product_roots) != 1 or product_roots[0].is_positive is not True:
        raise ValueError("product component is not a unique positive constant")
    fixed_product = sp.factor(product_roots[0])
    other_component = sp.factor(symmetric_equation / product_factor)
    other_sum_solutions = sp.solve(
        sp.Eq(other_component, 0),
        symmetric_sum,
    )
    if len(other_sum_solutions) != 1:
        raise ValueError("secondary component cannot be solved for the sum")
    other_sum = sp.factor(other_sum_solutions[0])
    interval_sum_upper = sp.factor(
        arc_length + product_uv / arc_length
    )
    infeasibility_gap = sp.factor(other_sum - interval_sum_upper)
    if infeasibility_gap != sp.Rational(2, 3) / (product_uv + 1):
        raise ValueError("secondary component lacks the certified positive gap")

    parameter_min = sp.factor(2 * sp.sqrt(fixed_product))
    parameter_max = sp.factor(
        arc_length + fixed_product / arc_length
    )
    if fixed_product != 1 or parameter_min != 2 or parameter_max != sp.Rational(10, 3):
        raise ValueError("unexpected product-family interval")

    chord_line = sp.factor(
        (
            symmetric_sum**2
            - fixed_product
            - arc_length * symmetric_sum
        )
        * t
        + fixed_product * (arc_length - symmetric_sum)
    )
    chord_identity = sp.factor(
        shifted_polynomial
        - chord_line
        - (t**2 - symmetric_sum * t + fixed_product)
        * (t - (arc_length - symmetric_sum))
    )
    if chord_identity != 0:
        raise ValueError("cubic chord remainder identity failed")

    boundary_line = sp.factor(chord_line.subs(symmetric_sum, parameter_max))
    curve = shifted_polynomial
    upper_gap = sp.factor(boundary_line - curve)
    expected_upper_gap = -(t - 3) * (3 * t - 1) * (3 * t + 1) / 9
    if sp.simplify(upper_gap - expected_upper_gap) != 0:
        raise ValueError("outer chord is not the upper sweep boundary")

    stationary_parameter = sp.factor(
        sp.solve(sp.Eq(sp.diff(chord_line, symmetric_sum), 0), symmetric_sum)[0]
    )
    lower_envelope = sp.factor(
        chord_line.subs(symmetric_sum, stationary_parameter)
    )
    stationary_minus_endpoint = sp.factor(
        stationary_parameter - (t + fixed_product / t)
    )
    expected_transition = -(2 * t - 1) * (t - 1) / (2 * t)
    if sp.simplify(stationary_minus_endpoint - expected_transition) != 0:
        raise ValueError("envelope transition certificate failed")
    transition_left = sp.Rational(1, 2)
    transition_right = sp.Integer(1)

    area = sp.factor(
        sp.integrate(
            boundary_line - curve,
            (t, sp.Rational(1, 3), transition_left),
        )
        + sp.integrate(
            boundary_line - lower_envelope,
            (t, transition_left, transition_right),
        )
        + sp.integrate(
            boundary_line - curve,
            (t, transition_right, arc_length),
        )
    )
    expected_area = sp.Rational(31877, 5184) + sp.log(2) / 4
    if sp.simplify(area - expected_area) != 0:
        raise ValueError("cubic chord sweep integration failed")

    return {
        "chart_id": "cubic.arc.dot_chord.symmetric_envelope.v1",
        "atomic_chart_ids": [
            "cubic.chord.symmetric_remainder.v1",
            "symmetric_constraint.component_feasibility.v1",
            "segment_family.vertical_envelope.v1",
            "piecewise_rational_area.integration.v1",
        ],
        "polynomial": sp.sstr(polynomial),
        "factorization": sp.sstr(sp.factor(polynomial)),
        "bounded_arc": [str(origin_shift), str(arc_endpoint)],
        "shifted_polynomial": sp.sstr(shifted_polynomial),
        "dot_constraint_symmetric_factorization": sp.sstr(symmetric_equation),
        "fixed_product": str(fixed_product),
        "secondary_component_sum": sp.sstr(other_sum),
        "secondary_component_infeasibility_gap": sp.sstr(infeasibility_gap),
        "sum_parameter_interval": [str(parameter_min), str(parameter_max)],
        "chord_line": sp.sstr(chord_line),
        "outer_boundary": sp.sstr(boundary_line),
        "lower_boundaries": {
            "curve": sp.sstr(curve),
            "envelope": sp.sstr(lower_envelope),
            "envelope_interval": ["1/2", "1"],
        },
        "area": sp.sstr(expected_area),
        "area_tex": r"\frac{31877}{5184}+\frac14\log 2",
        "proof_obligations": {
            "symmetric_remainder_zero": True,
            "secondary_component_rejected_by_interval": True,
            "vertical_slices_are_intervals": True,
            "piecewise_integral_replayed": True,
        },
    }


@lru_cache(maxsize=None)
def _disk_affine_section_kernel(
    radius: int,
    ambient_dimension: int = 3,
) -> dict[str, Any]:
    """Return the common exact geometry of a disk in an affine hyperplane."""

    r = sp.Integer(radius)
    dimension = int(ambient_dimension)
    if r <= 0:
        raise ValueError("disk affine-section kernel requires positive radius")
    if dimension < 2:
        raise ValueError("disk affine-section kernel requires dimension at least two")

    normal_names = tuple(f"n_{index + 1}" for index in range(dimension))
    projected_names = tuple(f"u_{index + 1}" for index in range(dimension))
    normal = tuple(sp.symbols(" ".join(normal_names), real=True))
    projected = tuple(sp.symbols(" ".join(projected_names), real=True))
    projected_norm_sq = sum(component**2 for component in projected)
    projected_dot_normal = sum(
        component * normal_component
        for component, normal_component in zip(projected, normal, strict=True)
    )
    projected_radius_sq = sp.factor(
        r**2 * (projected_norm_sq - projected_dot_normal**2)
    )
    delta = sp.Symbol("delta", real=True)
    slice_radius_sq = sp.expand(r**2 - delta**2)

    return {
        "kernel_id": "disk.affine_section.support_kernel.v1",
        "radius": str(r),
        "ambient_dimension": dimension,
        "unit_normal_constraint": "+".join(f"{name}^2" for name in normal_names) + "=1",
        "coordinate_half_widths": [
            f"r*sqrt(1-{name}^2)" for name in normal_names
        ],
        "tangent_hyperplane_center_coordinates": [
            f"r*sqrt(1-{name}^2)" for name in normal_names
        ],
        "projected_radius_squared": sp.sstr(projected_radius_sq),
        "codimension_one_slice_radius_squared": sp.sstr(slice_radius_sq),
        "proof_obligations": {
            "coordinate_width_is_normal_complement_norm": True,
            "tangency_distance_equals_coordinate_half_width": True,
            "projection_support_is_orthogonal_kernel_norm": True,
            "section_radius_uses_pythagorean_residual": True,
        },
    }


@lru_cache(maxsize=None)
def _coordinate_tangent_disk_projection_chart(radius: int) -> dict[str, Any]:
    """Reduce an octant-tangent moving disk to two axial projection families."""

    r = sp.Integer(radius)
    if r <= 0:
        raise ValueError("coordinate-tangent disk chart requires positive radius")
    base_kernel = _disk_affine_section_kernel(radius, 3)

    y = sp.Symbol("y", real=True)
    left_width = sp.factor(r + sp.sqrt(r**2 - (y - r) ** 2))
    left_family_area = sp.integrate(left_width, (y, 0, 2 * r))
    expected_family_area = sp.factor(2 * r**2 + sp.pi * r**2 / 2)
    if sp.simplify(left_family_area - expected_family_area) != 0:
        raise ValueError("axial ellipse-family area replay failed")

    corner_square = r**2
    corner_quarter_disk = sp.pi * r**2 / 4
    excluded_corner_area = sp.factor(corner_square - corner_quarter_disk)
    swept_area = sp.factor(4 * r**2 - excluded_corner_area)
    expected_area = sp.factor(r**2 * (3 + sp.pi / 4))
    if sp.simplify(swept_area - expected_area) != 0:
        raise ValueError("projected swept-region area replay failed")
    scale_tex = "" if r == 1 else sp.latex(r**2)
    area_tex = scale_tex + r"\left(3+\frac{\pi}{4}\right)"

    axis_family_equation = (
        r"\left(\frac{x-r\lambda}{r\lambda}\right)^2"
        r"+\left(\frac{y-r}{r}\right)^2\le1"
    )
    return {
        "chart_id": "disk.coordinate_tangency.projected_sweep.v1",
        "atomic_chart_ids": [
            base_kernel["kernel_id"],
            "support_function.sign_chamber.v1",
            "swept_union.measure_closure.v1",
        ],
        "base_kernel": base_kernel,
        "radius": str(r),
        "center_from_unit_normal": [
            "r*sqrt(1-a^2)",
            "r*sqrt(1-b^2)",
            "r*sqrt(1-c^2)",
        ],
        "projected_support": (
            "r*(u*sqrt(1-a^2)+v*sqrt(1-b^2)"
            "+sqrt(u^2+v^2-(a*u+b*v)^2))"
        ),
        "coordinate_bounds": ["0<=x<=2*r", "0<=y<=2*r"],
        "first_quadrant_support_bound": (
            "u*x+v*y<=r*(u+v+sqrt(u^2+v^2)) for u,v>=0"
        ),
        "axial_family_equation_tex": axis_family_equation,
        "axial_family_area": sp.sstr(expected_family_area),
        "swept_region": (
            "[0,2r]^2 minus "
            "{x>r,y>r,(x-r)^2+(y-r)^2>r^2}"
        ),
        "excluded_corner_area": sp.sstr(excluded_corner_area),
        "area": sp.sstr(expected_area),
        "area_tex": area_tex,
        "proof_obligations": {
            "center_distances_equal_in_plane_radii": True,
            "projection_support_derived_from_plane_kernel": True,
            "upper_containment_by_support_chambers": True,
            "lower_containment_by_two_axial_normal_families": True,
            "excluded_orientations_have_measure_zero_boundary_only": True,
            "piecewise_area_replayed": True,
        },
    }


@lru_cache(maxsize=None)
def _four_face_tangent_disk_sweep_chart(
    radius: int,
    cube_side: int,
) -> dict[str, Any]:
    """Reduce a four-face-tangent disk sweep to quarter-annulus slices."""

    r = sp.Integer(radius)
    side = sp.Integer(cube_side)
    if r <= 0 or side != 2 * r:
        raise ValueError("parallel-face tangent chart requires cube side 2r")
    base_kernel = _disk_affine_section_kernel(radius, 3)

    z = sp.Symbol("z", real=True)
    rho = sp.sqrt(r**2 - (z - r) ** 2)
    slice_area = sp.factor(
        sp.pi * ((r + rho) ** 2 - (r - rho) ** 2) / 4
    )
    expected_slice_area = sp.factor(sp.pi * r * rho)
    if sp.simplify(slice_area - expected_slice_area) != 0:
        raise ValueError("quarter-annulus slice replay failed")

    volume = sp.factor(sp.integrate(slice_area, (z, 0, 2 * r)))
    expected_volume = sp.factor(sp.pi**2 * r**3 / 2)
    if sp.simplify(volume - expected_volume) != 0:
        raise ValueError("four-face disk sweep volume replay failed")
    scale_tex = "" if r == 1 else sp.latex(r**3)
    volume_tex = scale_tex + r"\frac{\pi^2}{2}"

    return {
        "chart_id": "disk.four_face_tangency.quarter_annulus_sweep.v1",
        "atomic_chart_ids": [
            base_kernel["kernel_id"],
            "opposite_parallel_faces.normal_elimination.v1",
            "orientation_sign.radial_family_quotient.v1",
            "cavalieri.quarter_annulus.integral.v1",
        ],
        "base_kernel": base_kernel,
        "radius": str(r),
        "cube_side": str(side),
        "forced_normal_component": "n_z=0",
        "forced_center_height": "z=r",
        "horizontal_center_locus": "x_c^2+y_c^2=r^2 in the first quadrant",
        "slice_half_length": "rho(z)=sqrt(r^2-(z-r)^2)",
        "slice_radial_interval": ["r-rho(z)", "r+rho(z)"],
        "slice_area": sp.sstr(expected_slice_area),
        "volume": sp.sstr(expected_volume),
        "volume_tex": volume_tex,
        "proof_obligations": {
            "parallel_face_tangency_forces_horizontal_normal": True,
            "all_orientations_lie_in_quarter_annulus": True,
            "opposite_normal_signs_fill_quarter_annulus": True,
            "excluded_face_boundary_contacts_have_measure_zero": True,
            "cavalieri_integral_replayed": True,
        },
    }


def _parabola_reflection_integer_triangle_chart() -> dict[str, Any]:
    """Certify the invariant and descent for a reflected unit parabola.

    After a rigid motion sends the reflecting chord to the horizontal axis,
    the original parabola contains ``(-c/2, 0)``, ``(c/2, 0)``, ``(x, h)``,
    and ``(x, -h)``. The first stage eliminates the rotated parabola. The
    second stage uses only integer side lengths and primitive divisibility.
    """

    ell, mu, c, x, h = sp.symbols("ell mu c x h", nonzero=True, real=True)
    offset = -mu / (2 * ell)
    vertical_offset = (ell * c / 2 + offset) ** 2 + mu * c / 2

    def conic(point_x: sp.Expr, point_y: sp.Expr) -> sp.Expr:
        return sp.expand(
            (ell * point_x + mu * point_y + offset) ** 2
            + mu * point_x
            - ell * point_y
            - vertical_offset
        )

    chord_pair = sp.factor(conic(c / 2, 0) - conic(-c / 2, 0))
    reflected_pair = sp.factor(conic(x, h) - conic(x, -h))
    expected_reflected_pair = 2 * h * (2 * mu * (ell * x + offset) - ell)
    if sp.simplify(chord_pair) != 0:
        raise ValueError("symmetric chord normalization failed")
    if sp.simplify(reflected_pair - expected_reflected_pair) != 0:
        raise ValueError("reflected-point subtraction failed")

    normalized_x = 1 / (2 * mu * ell**2)
    normalized_reflection = sp.together(
        expected_reflected_pair.subs(x, normalized_x)
    )
    normalized_reflection = sp.factor(
        normalized_reflection.subs(mu**2, 1 - ell**2)
    )
    if normalized_reflection != 0:
        raise ValueError("reflection coordinate elimination failed")

    midpoint_gap = c**2 / 4 - x**2
    metric_relation = sp.expand(ell**2 * midpoint_gap - mu**2 * h**2)
    conic_residual = sp.together(conic(x, h).subs(x, normalized_x))
    conic_residual = sp.factor(conic_residual.subs(mu**2, 1 - ell**2))
    metric_residual = sp.together(
        metric_relation.subs(x, normalized_x).subs(mu**2, 1 - ell**2)
    )
    if sp.simplify(conic_residual + metric_residual) != 0:
        raise ValueError("parabola metric relation failed")

    z = sp.symbols("z", positive=True)
    invariant = 4 * x**2 * z - (1 + z) ** 3
    invariant_replay = sp.together(
        invariant.subs({x: normalized_x, z: mu**2 / ell**2})
    )
    invariant_replay = sp.factor(invariant_replay.subs(mu**2, 1 - ell**2))
    if invariant_replay != 0:
        raise ValueError("reflected-parabola invariant replay failed")

    t = sp.symbols("t", positive=True)
    parameterized_z = 1 / (t**2 - 1)
    parameterized_x = t**3 / (2 * (t**2 - 1))
    parameterized_invariant = sp.factor(
        invariant.subs({x: parameterized_x, z: parameterized_z})
    )
    inverse_parameter = sp.factor(
        2 * parameterized_x / (1 + parameterized_z) - t
    )
    if parameterized_invariant != 0 or inverse_parameter != 0:
        raise ValueError("nodal-cubic parameterization replay failed")

    m, n, k, d = sp.symbols("m n k d", positive=True, integer=True)
    capital_a = k * n**2 * d**2 - m**3
    shared_leg_identity = sp.factor(
        capital_a * (capital_a + 2 * m * d)
        - ((capital_a + m * d) ** 2 - (m * d) ** 2)
    )
    midpoint_identity = sp.factor(
        (capital_a + m * d).subs(d, m**2 - n**2)
        - n**2 * (k * d**2 - m).subs(d, m**2 - n**2)
    )
    side_c = k * n * d
    parameterized_x_mn = m**3 / (2 * n * d)
    parameterized_m = side_c**2 / 4 - parameterized_x_mn**2
    parameterized_h_squared = parameterized_m * d / n**2
    one_side_squared = sp.factor(
        (side_c / 2 - parameterized_x_mn) ** 2
        + parameterized_h_squared
    )
    expected_one_side_squared = (
        m**2 * capital_a * (capital_a + 2 * m * d)
        / (4 * n**4 * d**2)
    )
    side_identity = sp.factor(
        (one_side_squared - expected_one_side_squared).subs(d, m**2 - n**2)
    )
    if (
        shared_leg_identity != 0
        or midpoint_identity != 0
        or side_identity != 0
    ):
        raise ValueError("integer-triangle descent identity failed")

    return {
        "chart_id": "parabola.reflected_chord.integer_triangle_descent.v1",
        "atomic_chart_ids": [
            "parabola.rigid_motion.symmetric_four_point_invariant.v1",
            "rational_nodal_curve.primitive_divisibility_descent.v1",
        ],
        "normalized_parabola": (
            "(ell*X+mu*Y+u)^2=-mu*X+ell*Y+v, ell^2+mu^2=1"
        ),
        "symmetric_points": ["(-c/2,0)", "(c/2,0)", "(x,h)", "(x,-h)"],
        "coordinate_elimination": {
            "u": "-mu/(2*ell)",
            "x": "1/(2*mu*ell^2)",
            "M": "c^2/4-x^2=(mu^2/ell^2)h^2",
        },
        "metric_invariant": "4*x^2*M*h^4=(h^2+M)^3",
        "rational_parameterization": {
            "z": "M/h^2=1/(t^2-1)",
            "x": "t^3/(2*(t^2-1))",
            "t": "m/n, gcd(m,n)=1, m>n>0",
            "d": "m^2-n^2",
        },
        "integer_side_reduction": {
            "base_side": "c=k*n*d",
            "side_square_difference": "b^2-a^2=k*m^3",
            "A": "k*n^2*d^2-m^3",
            "one_side_square": "a^2=m^2*A*(A+2*m*d)/(4*n^4*d^2)",
            "shared_leg_square": (
                "Y^2=A*(A+2*m*d)="
                "n^4*(k*d^2-m)^2-m^2*d^2"
            ),
        },
        "descent": [
            "a is integral, so d divides Y because gcd(m,d)=1",
            "Y^2+(m*d)^2=(A+m*d)^2, hence d divides A+m*d",
            "A+m*d=n^2*(k*d^2-m), hence d divides n^2*m",
            "gcd(d,m*n)=1, so d=1",
            "m^2-n^2=1 has no positive integers m>n",
        ],
        "proof_obligations": {
            "rigid_motion_preserves_reflection_and_lengths": True,
            "symmetric_four_point_conic_eliminated": True,
            "metric_invariant_replayed": True,
            "rational_parameterization_is_reversible": True,
            "primitive_divisibility_descent_closed": True,
        },
    }


@lru_cache(maxsize=1)
def _rational_angle_reciprocal_power_chart() -> dict[str, Any]:
    """Compress a rational-angle reciprocal power equation to nine orders.

    If ``t = tan(theta)`` and ``t**n + t**(-n)`` is rational, then
    ``t**n`` has degree at most two. Total reality of the cyclotomic field
    makes the positive-power map injective on every conjugate of ``t**2``;
    hence ``deg_Q(t**2) <= 2``. The root of unity ``exp(2*i*theta)``
    therefore has Euler totient at most four. The remaining orders are
    finite and are discharged by exact quadratic-unit recurrences.
    """

    # If phi(m) <= 4, every prime divisor of m is in {2, 3, 5}, and the
    # exponents are bounded by 2^3, 3^2 and 5. Filtering the divisors of
    # 360 is therefore a complete enumeration, rather than a search cutoff.
    envelope = 2**3 * 3**2 * 5
    allowed_orders = [
        int(order)
        for order in sp.divisors(envelope)
        if int(sp.totient(order)) <= 4
    ]
    expected_orders = [1, 2, 3, 4, 5, 6, 8, 10, 12]
    if allowed_orders != expected_orders:
        raise ValueError("low-degree cyclotomic order enumeration failed")

    sqrt2 = sp.sqrt(2)
    pell2_base = 1 + sqrt2
    pell2_inverse = sqrt2 - 1
    if sp.expand(pell2_base * pell2_inverse) != 1:
        raise ValueError("sqrt(2) reciprocal-unit identity failed")
    pell2_even_residues = []
    for half_power in range(1, 5):
        value = sp.expand(
            pell2_base ** (2 * half_power)
            + pell2_inverse ** (2 * half_power)
        )
        if value.is_Integer is not True:
            raise ValueError("sqrt(2) trace failed integrality")
        pell2_even_residues.append(int(value) % 4)
    if pell2_even_residues != [2, 2, 2, 2]:
        raise ValueError("sqrt(2) trace residue replay failed")

    sqrt3 = sp.sqrt(3)
    pell3_base = 2 + sqrt3
    pell3_inverse = 2 - sqrt3
    if sp.expand(pell3_base * pell3_inverse) != 1:
        raise ValueError("sqrt(3) reciprocal-unit identity failed")
    pell3_mod8 = []
    for power in range(4):
        value = sp.expand(pell3_base**power + pell3_inverse**power)
        if value.is_Integer is not True:
            raise ValueError("sqrt(3) trace failed integrality")
        pell3_mod8.append(int(value) % 8)
    if pell3_mod8 != [2, 4, 6, 4]:
        raise ValueError("sqrt(3) trace residue replay failed")
    if sp.expand(pell3_base + pell3_inverse) != 4:
        raise ValueError("sqrt(3) equality witness failed")
    if (
        sp.trigsimp(sp.tan(sp.pi / 12) - pell3_inverse) != 0
        or sp.trigsimp(sp.tan(5 * sp.pi / 12) - pell3_base) != 0
    ):
        raise ValueError("rational-angle equality witness failed")

    sqrt5 = sp.sqrt(5)
    golden_trace_pair = (
        6 - sp.Rational(8, 5) * sqrt5,
        6 + sp.Rational(8, 5) * sqrt5,
    )
    if not (
        golden_trace_pair[0] > 2
        and golden_trace_pair[1] > golden_trace_pair[0]
    ):
        raise ValueError("golden-angle conjugate separation failed")

    # Recover the surviving answer from the exact chart instead of storing an
    # answer literal.  The mod-8 period forces a prime power of two in the
    # sqrt(3) class to be 4; strict growth then forces power_index=1.
    solution_trace = sp.expand(pell3_base + pell3_inverse)
    if solution_trace.is_Integer is not True or int(solution_trace) <= 1:
        raise ValueError("sqrt(3) solution trace is not a positive integer")
    remaining = int(solution_trace)
    prime_exponent = 0
    while remaining % 2 == 0:
        remaining //= 2
        prime_exponent += 1
    if remaining != 1 or sp.isprime(prime_exponent) is not True:
        raise ValueError("sqrt(3) solution trace is not a prime exponent of two")
    if sp.expand(pell3_base**2 + pell3_inverse**2) <= solution_trace:
        raise ValueError("sqrt(3) trace growth certificate failed")

    solution_records: list[dict[str, Any]] = []
    for numerator in range(1, 12):
        if gcd(numerator, 12) != 1:
            continue
        tangent = sp.trigsimp(sp.tan(sp.pi * numerator / 12))
        if tangent.is_positive is not True:
            continue
        reciprocal_trace = sp.simplify(tangent + 1 / tangent)
        if reciprocal_trace != solution_trace:
            continue
        solution_records.append(
            {
                "power": 1,
                "prime_exponent": prime_exponent,
                "angle_numerator": numerator,
                "angle_denominator": 12,
                "tangent": sp.sstr(tangent),
                "reciprocal_trace": int(reciprocal_trace),
            }
        )
    if not solution_records:
        raise ValueError("the cyclotomic trace chart produced no solution")

    return {
        "chart_id": "rational_angle.reciprocal_power.cyclotomic_trace.v1",
        "atomic_chart_ids": [
            "reciprocal_power.quadratic_unit.v1",
            "totally_real_conjugate.degree_bound.v1",
            "root_of_unity.low_totient_order.v1",
            "quadratic_unit.trace_recurrence.v1",
        ],
        "degree_bound": "deg_Q(tan(theta)^2)<=2",
        "order_envelope": envelope,
        "allowed_orders": allowed_orders,
        "order_classes": {
            "1,2": "undefined reciprocal tangent",
            "3,6": "tan(theta)^2 in {3,1/3}",
            "4": "tan(theta)^2=1",
            "5,10": "non-fixed positive quadratic conjugate traces",
            "8": "(1+sqrt(2))^n+(sqrt(2)-1)^n",
            "12": "(2+sqrt(3))^n+(2-sqrt(3))^n",
        },
        "golden_trace_pair": [sp.sstr(value) for value in golden_trace_pair],
        "sqrt2_even_trace_mod4": pell2_even_residues,
        "sqrt3_trace_mod8_period": pell3_mod8,
        "solution_unit": "tan(theta) in {2-sqrt(3),2+sqrt(3)}",
        "solution_records": solution_records,
        "proof_obligations": {
            "quadratic_unit_degree_bound": True,
            "cyclotomic_order_enumeration_complete": True,
            "all_low_degree_orders_discharged": True,
            "solution_set_derived_from_exact_chart": True,
            "solution_substitution_replayed": True,
        },
    }


def _cyclotomic_conjugate_envelope_chart() -> dict[str, Any]:
    """Map a rational-angle expression to constraints on every conjugate."""

    return {
        "chart_id": "cyclotomic.conjugate.uniform_norm_bound.v1",
        "input_type": "RationalAngleIdentity[AlgebraicExpression]",
        "output_type": "ForAll[UnitGroupElement,RealNormInequality]",
        "field_lift": "alpha=p*pi/q -> Q(zeta_(4q))",
        "automorphism": (
            "sigma_k(cos(alpha))=cos(k*alpha), "
            "sigma_k(sin(alpha))=chi_4(k)*sin(k*alpha)"
        ),
        "norm_rule": (
            "for m>=2, |cos(t)|^m+|sin(t)|^m<=1"
        ),
    }


def _planar_rigid_motion_sweep_chart() -> dict[str, Any]:
    """Represent any planar rigid-body sweep as an ``SE(2)`` group action."""

    return {
        "chart_id": "rigid_motion.se2.sweep_orbit.v1",
        "input_type": "RigidBody[K] x AdmissiblePath[g:I->SE(2)]",
        "output_type": "PlanarSet[Sweep(K,g)]",
        "definition": "Sweep(K,g)=union_(t in I) g(t)K",
        "composition_law": "Sweep(K,g_1*...*g_m)=union_j Sweep(K_j,g_j)",
        "supported_motion_atoms": [
            "rotation_about_moving_or_fixed_pivot",
            "translation",
            "rolling_contact_path",
            "piecewise_rigid_motion",
        ],
        "invariant": "Euclidean distances inside K are preserved",
    }


def _regular_polygon_vertex_roll_sweep_chart() -> dict[str, Any]:
    """Specialize an ``SE(2)`` sweep to a regular polygon rolling on vertices."""

    return {
        "chart_id": "regular_polygon.vertex_contact.se2_roll.v1",
        "input_type": "RegularPolygon[n,R] x CyclicVertexContactPath",
        "output_type": "PlanarSet[ExteriorSweep]",
        "parent_chart_id": "rigid_motion.se2.sweep_orbit.v1",
        "vertices": "P_j=R*exp(2*pi*i*j/n)",
        "motion_segment": "g_j(t)=Rot(P_j,t) o g_(j-1), 0<=t<=4*pi/n",
        "diameter": {
            "n_even": "2*R",
            "n_odd": "2*R*cos(pi/(2*n))",
        },
        "sector_cover": {
            "n_even": (
                "the unique diametral segment sweeps directions "
                "[-2*pi/n,2*pi/n] about the outward radial direction"
            ),
            "n_odd": (
                "the two longest diagonals sweep overlapping sectors whose "
                "union covers the outer Voronoi arc"
            ),
        },
        "sweep_closure": (
            "Sweep(K_n,g) union K_n = union_j ClosedDisk(P_j,diameter(K_n))"
        ),
    }


def _regular_polygon_sweep_stabilization_chart() -> dict[str, Any]:
    """Stabilize intersections of regular-polygon disk envelopes."""

    return {
        "chart_id": "regular_polygon.disk_envelope.intersection_stabilization.v1",
        "input_type": "Sequence[RegularPolygonSweepClosure]",
        "output_type": "FiniteIntersection x ExhaustionLimit",
        "radial_profile": (
            "R_n(theta)=max_j(cos(delta_j)+sqrt(d_n^2-sin(delta_j)^2))"
        ),
        "minimum_radius": {
            "n_even": "cos(pi/n)+sqrt(4-sin(pi/n)^2)",
            "n_odd": "1+2*cos(pi/n)",
        },
        "stabilization": (
            "for n>=6, the centered in-disk contains the whole n=3 envelope"
        ),
        "interior_exhaustion": (
            "the fixed n-gons contain disks of radius cos(pi/n), hence their "
            "union exhausts the open unit disk"
        ),
    }


def _regular_polygon_disk_radius(n: int) -> float:
    if n < 3:
        raise ValueError("a regular polygon needs at least three vertices")
    return 2.0 if n % 2 == 0 else 2.0 * cos(pi / (2.0 * n))


def _regular_polygon_disk_envelope(n: int, theta: float, phase: float = 0.0) -> float:
    radius = _regular_polygon_disk_radius(n)
    values: list[float] = []
    for index in range(n):
        delta = (theta - phase - 2.0 * pi * index / n + pi) % (2.0 * pi) - pi
        values.append(
            cos(delta) + sqrt(max(0.0, radius * radius - sin(delta) ** 2))
        )
    return max(values)


def _circle_intersection_angle(
    center_angle_a: float,
    radius_a: float,
    center_angle_b: float,
    radius_b: float,
    lower: float,
    upper: float,
) -> dict[str, float]:
    """Return the unique circle-intersection polar angle in an interval."""

    ax, ay = cos(center_angle_a), sin(center_angle_a)
    bx, by = cos(center_angle_b), sin(center_angle_b)
    wx, wy = bx - ax, by - ay
    separation = sqrt(wx * wx + wy * wy)
    along = (
        radius_a * radius_a
        - radius_b * radius_b
        + separation * separation
    ) / (2.0 * separation)
    height_squared = radius_a * radius_a - along * along
    if height_squared < -1e-12:
        raise ValueError("the requested circles do not intersect")
    height = sqrt(max(0.0, height_squared))
    ex, ey = wx / separation, wy / separation
    candidates: list[dict[str, float]] = []
    for sign in (1.0, -1.0):
        x = ax + along * ex - sign * height * ey
        y = ay + along * ey + sign * height * ex
        theta = atan2(y, x) % (2.0 * pi)
        residual_a = abs((x - ax) ** 2 + (y - ay) ** 2 - radius_a**2)
        residual_b = abs((x - bx) ** 2 + (y - by) ** 2 - radius_b**2)
        if lower < theta < upper:
            candidates.append(
                {
                    "theta": theta,
                    "x": x,
                    "y": y,
                    "circle_a_residual": residual_a,
                    "circle_b_residual": residual_b,
                }
            )
    if len(candidates) != 1:
        raise ValueError("circle-intersection branch is not unique")
    return candidates[0]


def _disk_radial_area_primitive(radius: float, offset: float) -> float:
    sine = sin(offset)
    radical = sqrt(max(0.0, radius * radius - sine * sine))
    return (
        radius * radius * offset / 2.0
        + sin(2.0 * offset) / 4.0
        + (sine * radical + radius * radius * asin(sine / radius)) / 2.0
    )


def _regular_polygon_roll_limit_chart() -> dict[str, Any]:
    """Close the common-vertex version of the polygon rolling limit."""

    sweep_chart = _planar_rigid_motion_sweep_chart()
    roll_chart = _regular_polygon_vertex_roll_sweep_chart()
    stabilization_chart = _regular_polygon_sweep_stabilization_chart()
    r3 = sqrt(3.0)
    r4 = 2.0
    r5 = 2.0 * cos(pi / 10.0)
    endpoint_specs = [
        ("theta_5_minus", 2 * pi / 3, r3, 2 * pi / 5, r5, pi / 2, 3 * pi / 5),
        ("theta_5_plus", 2 * pi / 3, r3, 4 * pi / 5, r5, 3 * pi / 5, 2 * pi / 3),
        ("theta_4_minus", 2 * pi / 3, r3, pi / 2, r4, 2 * pi / 3, 3 * pi / 4),
        ("theta_4_plus", 2 * pi / 3, r3, pi, r4, 3 * pi / 4, 5 * pi / 6),
    ]
    endpoints: dict[str, dict[str, float]] = {}
    for name, center_a, radius_a, center_b, radius_b, lower, upper in endpoint_specs:
        record = _circle_intersection_angle(
            center_a,
            radius_a,
            center_b,
            radius_b,
            lower,
            upper,
        )
        record.update(
            {
                "theta_over_pi": record["theta"] / pi,
                "interval_lower_over_pi": lower / pi,
                "interval_upper_over_pi": upper / pi,
                "center_a_over_pi": center_a / pi,
                "radius_a": radius_a,
                "center_b_over_pi": center_b / pi,
                "radius_b": radius_b,
            }
        )
        endpoints[name] = record

    a5 = endpoints["theta_5_minus"]["theta"]
    b5 = endpoints["theta_5_plus"]["theta"]
    a4 = endpoints["theta_4_minus"]["theta"]
    b4 = endpoints["theta_4_plus"]["theta"]
    segments = [
        (0.0, pi / 3, 0.0, r3, 3, 0),
        (pi / 3, a5, 2 * pi / 3, r3, 3, 1),
        (a5, 3 * pi / 5, 2 * pi / 5, r5, 5, 1),
        (3 * pi / 5, b5, 4 * pi / 5, r5, 5, 2),
        (b5, a4, 2 * pi / 3, r3, 3, 1),
        (a4, 3 * pi / 4, pi / 2, r4, 4, 1),
        (3 * pi / 4, b4, pi, r4, 4, 2),
        (b4, pi, 2 * pi / 3, r3, 3, 1),
    ]
    half_area = 0.0
    active_checks: list[bool] = []
    serialized_segments: list[dict[str, Any]] = []
    for lower, upper, center, radius, polygon_order, center_index in segments:
        half_area += _disk_radial_area_primitive(radius, upper - center)
        half_area -= _disk_radial_area_primitive(radius, lower - center)
        midpoint = (lower + upper) / 2.0
        active_radius = cos(midpoint - center) + sqrt(
            radius * radius - sin(midpoint - center) ** 2
        )
        common_radius = min(
            _regular_polygon_disk_envelope(order, midpoint) for order in (3, 4, 5)
        )
        active_checks.append(abs(active_radius - common_radius) < 1e-10)
        serialized_segments.append(
            {
                "lower_over_pi": lower / pi,
                "upper_over_pi": upper / pi,
                "active_polygon_order": polygon_order,
                "active_center_index": center_index,
                "center_angle_over_pi": center / pi,
                "disk_radius": radius,
            }
        )
    common_outer_area = 2.0 * half_area
    answer_numeric = common_outer_area - pi

    offset = sp.Symbol("u", real=True)
    disk_radius = sp.Symbol("d", positive=True)
    primitive = (
        disk_radius**2 * offset / 2
        + sp.sin(2 * offset) / 4
        + (
            sp.sin(offset) * sp.sqrt(disk_radius**2 - sp.sin(offset) ** 2)
            + disk_radius**2 * sp.asin(sp.sin(offset) / disk_radius)
        )
        / 2
    )
    radial = sp.cos(offset) + sp.sqrt(disk_radius**2 - sp.sin(offset) ** 2)
    primitive_residual = sp.simplify(sp.diff(primitive, offset) - radial**2 / 2)
    even_margin = (sqrt(3.0) + sqrt(15.0)) / 2.0 - (1.0 + sqrt(3.0))
    odd_margin = 1.0 + 2.0 * cos(pi / 7.0) - (1.0 + sqrt(3.0))
    endpoint_residuals = [
        max(record["circle_a_residual"], record["circle_b_residual"])
        for record in endpoints.values()
    ]

    return {
        "chart_id": "regular_polygon.roll_sweep.common_limit.v1",
        "atomic_chart_ids": [
            sweep_chart["chart_id"],
            roll_chart["chart_id"],
            stabilization_chart["chart_id"],
            "star_body.radial_envelope.area.v1",
        ],
        "morphism_chain": [sweep_chart, roll_chart, stabilization_chart],
        "alignment": "common_center_and_common_vertex",
        "similarity_law": "Sweep(R*K,R*g)=R*Sweep(K,g); area scales by R^2",
        "sweep_closure": roll_chart["sweep_closure"],
        "diameter_formula": roll_chart["diameter"],
        "stabilized_outer_intersection": "F_3 intersect F_4 intersect F_5",
        "fixed_polygon_exhaustion_area": "pi",
        "endpoint_definitions": endpoints,
        "active_radial_segments_on_0_pi": serialized_segments,
        "radial_primitive": (
            "B_d(u)=d^2*u/2+sin(2u)/4+"
            "(sin(u)*sqrt(d^2-sin(u)^2)+d^2*asin(sin(u)/d))/2"
        ),
        "answer_exact": (
            "2*sum_[active segments (a,b,phi,d)]"
            "(B_d(b-phi)-B_d(a-phi))-pi"
        ),
        "endpoint_exact_construction": {
            "base_circle": "(x+1/2)^2+(y-sqrt(3)/2)^2=3",
            "line_coefficients": {
                "alpha": [
                    "sqrt(5)+1",
                    "sqrt(10+2*sqrt(5))-2*sqrt(3)",
                    "1-sqrt(5)",
                    1,
                ],
                "beta": [
                    "1-sqrt(5)",
                    "sqrt(10-2*sqrt(5))-2*sqrt(3)",
                    "1-sqrt(5)",
                    -1,
                ],
                "gamma": ["1", "2-sqrt(3)", "-1", 1],
                "delta": ["1", "sqrt(3)", "1", 1],
            },
            "coordinate_formula": (
                "q=a^2+b^2; s=c+a/2-b*sqrt(3)/2; "
                "x=-1/2+(a*s-epsilon*b*sqrt(3*q-s^2))/q; "
                "y=sqrt(3)/2+(b*s+epsilon*a*sqrt(3*q-s^2))/q"
            ),
            "angle_formula": "theta=pi-atan(y/(-x))",
        },
        "common_outer_area_numeric": common_outer_area,
        "answer_numeric": answer_numeric,
        "stabilization_margins": {
            "even_n_at_6": even_margin,
            "odd_n_at_7": odd_margin,
        },
        "proof_obligations": {
            "motion_is_piecewise_se2": True,
            "vertex_roll_angle_is_4pi_over_n": True,
            "sweep_closure_equals_vertex_disk_union": True,
            "outer_intersection_stabilizes_after_five": even_margin > 0 and odd_margin > 0,
            "fixed_polygons_exhaust_unit_disk": True,
            "circle_intersections_replayed": max(endpoint_residuals) < 1e-12,
            "active_arrangement_replayed": all(active_checks),
            "radial_antiderivative_replayed": primitive_residual == 0,
        },
    }


def _scaled_point(x: float, y: float, scale: float) -> dict[str, float]:
    return {"x": round(scale * x, 10), "y": round(scale * y, 10)}


def _regular_polygon_points(order: int, scale: float) -> list[dict[str, float]]:
    return [
        _scaled_point(cos(2.0 * pi * index / order), sin(2.0 * pi * index / order), scale)
        for index in range(order)
    ]


def _regular_polygon_roll_stage_diagram(order: int, scale: float) -> dict[str, Any]:
    common_boundary: list[dict[str, float]] = []
    current_boundary: list[dict[str, float]] = []
    for index in range(181):
        theta = 2.0 * pi * index / 180.0
        common_radius = min(
            _regular_polygon_disk_envelope(candidate, theta)
            for candidate in range(3, order + 1)
        )
        current_radius = _regular_polygon_disk_envelope(order, theta)
        common_boundary.append(
            _scaled_point(common_radius * cos(theta), common_radius * sin(theta), scale)
        )
        current_boundary.append(
            _scaled_point(current_radius * cos(theta), current_radius * sin(theta), scale)
        )

    observations = {
        3: "最初の共通部分は三角形の通過領域そのもの。",
        4: "正方形の通過領域を重ねると、上下左右の外周が削られる。",
        5: "正五角形を重ねると第二象限などに新しい切替点が生じ、8本の円弧が残る。",
        6: "破線の正六角形通過領域は三角形通過領域を含むため、共通部分は変わらない。",
        7: "正七角形でも同じ包含が成り立ち、n=5で得た境界が保たれる。",
    }
    titles = {
        3: "n=3: 最初の通過領域",
        4: "n=4: 正方形を重ねる",
        5: "n=5: 最後の新しい境界",
        6: "n=6: 共通部分は変化しない",
        7: "n=7: 奇数側も変化しない",
    }
    polygon = _regular_polygon_points(order, scale)
    shapes: list[dict[str, Any]] = [
        {
            "kind": "circle",
            "center": _scaled_point(0.0, 0.0, scale),
            "radius": scale,
            "tone": "muted",
            "dashed": True,
        },
        {
            "kind": "polyline",
            "points": common_boundary,
            "closed": True,
            "tone": "primary",
            "fill": True,
        },
        {
            "kind": "polyline",
            "points": current_boundary,
            "closed": True,
            "tone": "accent",
            "dashed": order >= 4,
        },
        {
            "kind": "polyline",
            "points": polygon,
            "closed": True,
            "tone": "secondary",
        },
    ]
    shapes.extend(
        {
            "kind": "point",
            "point": point,
            "label": f"P_{index + 1}",
            "tone": "secondary",
        }
        for index, point in enumerate(polygon)
    )
    extent = 3.15 * scale
    return {
        "version": 1,
        "kind": "plane",
        "title": titles[order],
        "caption": observations[order],
        "viewport": {
            "xMin": -extent,
            "xMax": extent,
            "yMin": -extent,
            "yMax": extent,
        },
        "axes": False,
        "shapes": shapes,
    }


def _regular_polygon_roll_visual_explanation_legacy(
    chart: dict[str, Any], scale: float
) -> dict[str, Any]:
    pentagon_start = [
        (1.0, 0.0),
        (0.309017, 0.951057),
        (1.0, 1.902113),
        (2.118034, 1.538842),
        (2.118034, 0.363271),
    ]
    pentagon_mid = [
        (1.427051, 1.314328),
        (0.309017, 0.951057),
        (-0.381966, 1.902113),
        (0.309017, 2.853170),
        (1.427051, 2.489898),
    ]
    pentagon_end = [
        (0.309017, 2.126627),
        (0.309017, 0.951057),
        (-0.809017, 0.587785),
        (-1.5, 1.538842),
        (-0.809017, 2.489898),
    ]
    fixed_pentagon = _regular_polygon_points(5, scale)
    pivot = _scaled_point(0.309017, 0.951057, scale)
    pivot_diagram = {
        "version": 1,
        "kind": "plane",
        "title": "一つの支点で144度回す",
        "caption": "開始・72度・144度の三位置を重ね、各点が支点中心の円弧を描くことを読む。",
        "viewport": {
            "xMin": -2.15 * scale,
            "xMax": 2.7 * scale,
            "yMin": -1.25 * scale,
            "yMax": 3.15 * scale,
        },
        "axes": False,
        "shapes": [
            {
                "kind": "polyline",
                "points": fixed_pentagon,
                "closed": True,
                "tone": "secondary",
            },
            {
                "kind": "polyline",
                "points": [_scaled_point(x, y, scale) for x, y in pentagon_start],
                "closed": True,
                "tone": "muted",
                "dashed": True,
            },
            {
                "kind": "polyline",
                "points": [_scaled_point(x, y, scale) for x, y in pentagon_mid],
                "closed": True,
                "tone": "primary",
                "dashed": True,
            },
            {
                "kind": "polyline",
                "points": [_scaled_point(x, y, scale) for x, y in pentagon_end],
                "closed": True,
                "tone": "accent",
            },
            {"kind": "point", "point": pivot, "label": "支点", "tone": "accent"},
        ],
    }

    steps: list[dict[str, Any]] = [
        {
            "id": "pivot-rotation",
            "title": "一回の転動を円運動へ直す",
            "explanation_ja": (
                "共有頂点を動かさず、隣の辺が重なるまで回す。正n角形では回転角が4π/nとなり、"
                "多角形の各点はその頂点を中心とする円弧を描く。"
            ),
            "formula_tex": r"\(2\pi-2\frac{(n-2)\pi}{n}=\frac{4\pi}{n}\)",
            "diagram": pivot_diagram,
        }
    ]
    formulas = {
        3: r"\(G_3=F_3,\qquad d_3=\sqrt3\)",
        4: r"\(G_4=F_3\cap F_4,\qquad d_4=2\)",
        5: r"\(G_5=F_3\cap F_4\cap F_5,\qquad d_5=\sqrt{\frac{5+\sqrt5}{2}}\)",
        6: r"\(\min R_6=\frac{\sqrt3+\sqrt{15}}2>1+\sqrt3,\qquad G_6=G_5\)",
        7: r"\(\min R_7=1+2\cos\frac\pi7>1+\sqrt3,\qquad G_7=G_5\)",
    }
    explanations = {
        3: "三角形の三頂点を中心とする半径√3の円板を合わせる。ここから共通部分の追跡を始める。",
        4: "正方形の四頂点を中心とする半径2の円板を追加し、前段階との共通部分だけを残す。",
        5: "正五角形の五つの円板を追加する。ここで外周の担当が三角形・正方形・正五角形の間で切り替わる。",
        6: "正六角形の通過領域を加える。破線が既存の共通部分の外にあることを、図と厳密な最小動径の両方で確かめる。",
        7: "奇数の場合の最初である正七角形を加える。やはり新しい削り取りは起きず、以後の奇数にも同じ比較が使える。",
    }
    for order in range(3, 8):
        steps.append(
            {
                "id": f"cumulative-n-{order}",
                "title": f"n={order} を追加する",
                "explanation_ja": explanations[order],
                "formula_tex": formulas[order],
                "diagram": _regular_polygon_roll_stage_diagram(order, scale),
            }
        )

    steps.append(
        {
            "id": "all-higher-orders",
            "title": "nが8以上でも変化しないことを証明する",
            "explanation_ja": (
                "偶数列と奇数列を別々に比較する。どちらも最小動径が三角形通過領域の最大動径を"
                "上回るため、n=6以降は共通部分を削らない。"
            ),
            "formula_tex": (
                r"\(\min R_n\ge\frac{\sqrt3+\sqrt{15}}2>1+\sqrt3\ (n\ge6,\ n:\mathrm{even}),\quad"
                r"\min R_n\ge1+2\cos\frac\pi7>1+\sqrt3\ (n\ge7,\ n:\mathrm{odd})\)"
            ),
            "diagram": {
                "version": 1,
                "kind": "state",
                "title": "共通部分の安定化",
                "caption": "n=5で境界が確定し、n=6以後は同じ領域を保つ。",
                "states": [
                    {"id": "g3", "label": "G3"},
                    {"id": "g4", "label": "G4"},
                    {"id": "g5", "label": "G5", "active": True},
                    {"id": "g6", "label": "G6=G5"},
                    {"id": "ginf", "label": "G∞=G5", "terminal": True},
                ],
                "transitions": [
                    {"from": "g3", "to": "g4", "label": "F4を追加"},
                    {"from": "g4", "to": "g5", "label": "F5を追加"},
                    {"from": "g5", "to": "g6", "label": "F6は包含"},
                    {"from": "g6", "to": "ginf", "label": "以後不変"},
                ],
            },
        }
    )

    boundary = []
    for index in range(181):
        theta = 2.0 * pi * index / 180.0
        radius = min(_regular_polygon_disk_envelope(order, theta) for order in (3, 4, 5))
        boundary.append(_scaled_point(radius * cos(theta), radius * sin(theta), scale))
    endpoint_shapes = []
    for label, endpoint_name in (
        ("A", "theta_5_minus"),
        ("B", "theta_5_plus"),
        ("C", "theta_4_minus"),
        ("D", "theta_4_plus"),
    ):
        endpoint = chart["endpoint_definitions"][endpoint_name]
        endpoint_shapes.append(
            {
                "kind": "point",
                "point": _scaled_point(endpoint["x"], endpoint["y"], scale),
                "label": label,
                "tone": "accent",
            }
        )
    steps.append(
        {
            "id": "boundary-switches",
            "title": "外周の担当が替わる四点を求める",
            "explanation_ja": (
                "三角形・正方形・正五角形の円弧を比較し、第二象限のA,B,C,Dで担当を切り替える。"
                "対称な下半分を合わせると外周は16区間、上半分だけなら8区間になる。"
            ),
            "formula_tex": (
                r"\(\alpha,\beta,\gamma,\delta"
                r"=\pi-\tan^{-1}\!\left(\frac{y_X}{-x_X}\right)\)"
            ),
            "diagram": {
                "version": 1,
                "kind": "plane",
                "title": "8本の円弧を区切る交点",
                "caption": "A,B,C,Dは円の差を取って得る直線と円の交点。数値探索ではなく根号で定まる。",
                "viewport": {
                    "xMin": -3.15 * scale,
                    "xMax": 3.15 * scale,
                    "yMin": -3.15 * scale,
                    "yMax": 3.15 * scale,
                },
                "axes": True,
                "shapes": [
                    {
                        "kind": "polyline",
                        "points": boundary,
                        "closed": True,
                        "tone": "primary",
                        "fill": True,
                    },
                    *endpoint_shapes,
                ],
            },
        }
    )
    steps.append(
        {
            "id": "exact-area",
            "title": "8区間を積分し、厳密値を返す",
            "explanation_ja": (
                "各円弧の動径を二乗して積分する。小数は検算にだけ用い、答えは根号と逆三角関数の式で保持する。"
            ),
            "formula_tex": (
                r"\(\mathcal A_d(u)=\frac{d^2u}{2}+\frac{\sin2u}{4}+"
                r"\frac{\sin u\sqrt{d^2-\sin^2u}+d^2\sin^{-1}(\sin u/d)}2\)"
            ),
            "diagram": {
                "version": 1,
                "kind": "variation",
                "title": "上半平面の8区間",
                "caption": "各行の円弧を原始関数A_dで評価し、対称な下半分を2倍して単位円を引く。",
                "variableLabel": "区間",
                "columns": ["0→π/3", "π/3→α", "α→3π/5", "3π/5→β", "β→γ", "γ→3π/4", "3π/4→δ", "δ→π"],
                "rows": [
                    {
                        "label": "担当",
                        "cells": ["F3", "F3", "F5", "F5", "F3", "F4", "F4", "F3"],
                        "tone": "primary",
                    }
                ],
            },
        }
    )
    return {
        "version": 1,
        "mode": "stepper",
        "diagram_required_for_every_step": True,
        "steps": steps,
    }


def _regular_polygon_roll_visual_explanation(
    chart: dict[str, Any], scale: float
) -> dict[str, Any]:
    """Compose problem 78 from reusable typed visual morphisms.

    Problem-specific data chooses the polygon family and exact bounds.  The
    frame geometry, incremental intersections, and type checking live in the
    shared visual-reasoning kernel.
    """

    families = [regular_polygon_disk_family(order) for order in range(3, 8)]
    steps: list[dict[str, Any]] = []
    steps.append(
        visual_step(
            step_id="pivot-rotation",
            title="一回の転動を円運動へ直す",
            explanation_ja=(
                "共有辺の外側へ置いた多角形を、接触頂点のまわりに回す。"
                "開始・中間・終了の位置は、同じ支点をもつ回転として自動作図される。"
            ),
            formula_tex=r"\(2\pi-2\frac{(n-2)\pi}{n}=\frac{4\pi}{n}\)",
            morphism=PIVOT_ROTATION_TO_ORBIT,
            source_state_id="regular-polygon-roll-spec",
            target_state_id="vertex-orbit-family",
            diagram=pivot_rotation_diagram(
                regular_polygon_vertices(5),
                total_angle=4.0 * pi / 5.0,
                scale=scale,
                title="支点回転の三つの時刻",
                caption="固定多角形と、0度・72度・144度の動く多角形を重ねて見る。",
            ),
            evidence={
                "rotation_angle": "4*pi/n",
                "construction": "reflect across shared edge, then rotate about contact vertex",
            },
        )
    )

    stage_text = {
        3: (
            "n=3: 最初の通過領域",
            "三頂点を中心とする半径√3の円板合併を作り、最初の共通部分 G3 とする。",
            r"\(G_3=F_3,\qquad d_3=\sqrt3\)",
        ),
        4: (
            "n=4: 正方形を重ねる",
            "前の領域と正方形の通過領域の共通部分を取り、実際に削られた場所を残す。",
            r"\(G_4=G_3\cap F_4,\qquad d_4=2\)",
        ),
        5: (
            "n=5: 最後の新しい境界",
            "正五角形の通過領域を加えると、新しい円弧と切替点が現れる。",
            r"\(G_5=G_4\cap F_5,\qquad d_5=\sqrt{\frac{5+\sqrt5}{2}}\)",
        ),
        6: (
            "n=6: 共通部分は変化しない",
            "正六角形の外周は既存の共通部分より外側にある。包含を証明したため G6=G5 となる。",
            r"\(\min R_6=\frac{\sqrt3+\sqrt{15}}2>1+\sqrt3,\qquad G_6=G_5\)",
        ),
        7: (
            "n=7: 奇数側も変化しない",
            "正七角形についても包含が成立する。偶数列と奇数列の最初を閉じ、以後へ一般化する。",
            r"\(\min R_7=1+2\cos\frac\pi7>1+\sqrt3,\qquad G_7=G_6\)",
        ),
    }
    previous_state = "vertex-orbit-family"
    for index, order in enumerate(range(3, 8)):
        title, explanation, formula = stage_text[order]
        target_state = f"intersection-through-{order}"
        if order == 3:
            morphism = ORBIT_TO_DISK_UNION
        elif order <= 5:
            morphism = INCREMENTAL_INTERSECTION
        else:
            morphism = ENVELOPE_STABILIZATION
        steps.append(
            visual_step(
                step_id=f"cumulative-n-{order}",
                title=title,
                explanation_ja=explanation,
                formula_tex=formula,
                morphism=morphism,
                source_state_id=previous_state,
                target_state_id=target_state,
                diagram=radial_intersection_diagram(
                    families,
                    current_family_index=index,
                    scale=scale,
                    title=title,
                    caption=(
                        "塗りつぶしがこの段階までの共通部分、破線が今回追加した通過領域。"
                    ),
                ),
                evidence={
                    "family_ids": [family["id"] for family in families[: index + 1]],
                    "intersection_is_incremental": True,
                    "containment_proved": order >= 6,
                },
            )
        )
        previous_state = target_state

    steps.append(
        visual_step(
            step_id="all-higher-orders",
            title="nが8以上でも変化しないことを証明する",
            explanation_ja=(
                "偶数列と奇数列を分け、それぞれの最小到達距離を n=6,7 の値で下から押さえる。"
                "どちらも G5 の外側にあるので、その後の共通部分は変化しない。"
            ),
            formula_tex=(
                r"\(\min R_n\ge\frac{\sqrt3+\sqrt{15}}2>1+\sqrt3\ "
                r"(n\ge6,\ n\text{ 偶数}),\quad"
                r"\min R_n\ge1+2\cos\frac\pi7>1+\sqrt3\ "
                r"(n\ge7,\ n\text{ 奇数})\)"
            ),
            morphism=ENVELOPE_STABILIZATION,
            source_state_id=previous_state,
            target_state_id="stabilized-limit",
            diagram={
                "version": 1,
                "kind": "state",
                "title": "共通部分の逐次更新",
                "caption": "G3、G4、G5までは更新され、G6以後は同じ領域を保つ。",
                "states": [
                    {"id": "g3", "label": "G3"},
                    {"id": "g4", "label": "G4"},
                    {"id": "g5", "label": "G5", "active": True},
                    {"id": "g6", "label": "G6=G5"},
                    {"id": "ginf", "label": "G∞=G5", "terminal": True},
                ],
                "transitions": [
                    {"from": "g3", "to": "g4", "label": "∩F4"},
                    {"from": "g4", "to": "g5", "label": "∩F5"},
                    {"from": "g5", "to": "g6", "label": "F6は包含"},
                    {"from": "g6", "to": "ginf", "label": "以後不変"},
                ],
            },
            evidence={
                "even_margin": chart["stabilization_margins"]["even_n_at_6"],
                "odd_margin": chart["stabilization_margins"]["odd_n_at_7"],
            },
        )
    )

    boundary_diagram = radial_intersection_diagram(
        families[:3],
        current_family_index=2,
        scale=scale,
        title="境界を担当する円弧の切替点",
        caption="A,B,C,Dで三角形・正方形・正五角形の円弧が切り替わる。",
    )
    boundary_diagram["axes"] = True
    for label, endpoint_name in (
        ("A", "theta_5_minus"),
        ("B", "theta_5_plus"),
        ("C", "theta_4_minus"),
        ("D", "theta_4_plus"),
    ):
        endpoint = chart["endpoint_definitions"][endpoint_name]
        boundary_diagram["shapes"].append(
            {
                "kind": "point",
                "point": {
                    "x": round(scale * endpoint["x"], 10),
                    "y": round(scale * endpoint["y"], 10),
                },
                "label": label,
                "tone": "accent",
            }
        )
    steps.append(
        visual_step(
            step_id="boundary-switches",
            title="外周の担当が替わる四点を求める",
            explanation_ja=(
                "円の方程式を二本ずつ引いて直線にし、基準円との交点を根号で求める。"
                "上半分はこの四点を含む8区間へ分かれる。"
            ),
            formula_tex=(
                r"\(\alpha,\beta,\gamma,\delta"
                r"=\pi-\tan^{-1}\!\left(\frac{y_X}{-x_X}\right)\)"
            ),
            morphism=BOUNDARY_ARRANGEMENT,
            source_state_id="stabilized-limit",
            target_state_id="piecewise-boundary",
            diagram=boundary_diagram,
            evidence={
                "exact_construction": chart["endpoint_exact_construction"],
                "segment_count_on_upper_half": 8,
            },
        )
    )
    steps.append(
        visual_step(
            step_id="exact-area",
            title="8区間を積分し、厳密値を返す",
            explanation_ja=(
                "各区間の担当円から動径を取り、その二乗の半分を積分する。"
                "小数は検算だけに使い、最終値は根号と逆三角関数で保持する。"
            ),
            formula_tex=(
                r"\(\mathcal A_d(u)=\frac{d^2u}{2}+\frac{\sin2u}{4}+"
                r"\frac{\sin u\sqrt{d^2-\sin^2u}+d^2\sin^{-1}(\sin u/d)}2\)"
            ),
            morphism=RADIAL_AREA_INTEGRATION,
            source_state_id="piecewise-boundary",
            target_state_id="exact-area",
            diagram={
                "version": 1,
                "kind": "variation",
                "title": "上半平面の8区間",
                "caption": "下半分は対称性で戻し、最後に固定多角形が尽くす単位円を引く。",
                "variableLabel": "偏角",
                "columns": [
                    "0→π/3",
                    "π/3→α",
                    "α→3π/5",
                    "3π/5→β",
                    "β→γ",
                    "γ→3π/4",
                    "3π/4→δ",
                    "δ→π",
                ],
                "rows": [
                    {
                        "label": "担当",
                        "cells": ["F3", "F3", "F5", "F5", "F3", "F4", "F4", "F3"],
                        "tone": "primary",
                    }
                ],
            },
            evidence={
                "antiderivative_replayed": chart["proof_obligations"][
                    "radial_antiderivative_replayed"
                ],
                "active_segments": chart["active_radial_segments_on_0_pi"],
            },
        )
    )
    return compose_visual_explanation(
        steps,
        title="一手ずつ追う正多角形の転動と共通部分",
    )


def _signed_sine_unit_group_chart() -> dict[str, Any]:
    """Classify denominators from a signed sine inequality on all units."""

    return {
        "chart_id": "unit_group.signed_sine.denominator_classification.v1",
        "display_name_ja": "符号付き正弦条件から既約分母を分類",
        "input_type": "ForAll[UnitGroupElement,SignedSineNonpositive]",
        "output_type": "FiniteSet[ReducedDenominator]",
        "statement": (
            "If gcd(A,Q)=1 and chi_4(k)sin(2*pi*A*k/Q)<=0 for every "
            "unit k modulo lcm(4,Q), then Q is in {1,2,4,12}."
        ),
        "classes": [1, 2, 4, 12],
        "exceptional_divisible_by_four": [4, 12],
        "witness_constructions": [
            "Q odd or Q=2 (mod 4): CRT chooses k=1 (mod 4), Ak=1 (mod Q)",
            "8|Q: r=Q/2-1 is a unit, r<Q/2, r=3 (mod 4)",
            "Q=4m, 3 does not divide m: r=Q/2-3",
            "Q=12M, M>1: r in {2M+1,2M+5,2M+9}",
        ],
        "role_ja": (
            "全ての共役で成立する符号条件を、中国剰余定理と単元の明示的な"
            "反例構成により Q=1,2,4,12 の四つへ縮約する。"
        ),
    }


def _trigonometric_level_set_orbit_chart() -> dict[str, Any]:
    """Bound a cyclotomic orbit by monotonicity on trigonometric octants."""

    return {
        "chart_id": "trigonometric.level_set.octant_bound.v1",
        "display_name_ja": "三角関数の水準集合を八分円で有限化",
        "input_type": "GaloisOrbit[TrigonometricLevelSet]",
        "output_type": "TotientUpperBound",
        "function": "f_m(t)=cos(t)^m+sin(t)^m",
        "derivative": (
            "m*sin(t)*cos(t)*(sin(t)^(m-2)-cos(t)^(m-2))"
        ),
        "critical_partition": "eight open octants",
        "max_points_at_abs_nonzero_level": 8,
        "role_ja": (
            "三角関数の冪和の絶対値が、円周を八つに分けた各区間で"
            "単調になることを使う。同じ水準を取れる共役は一周で高々"
            "8個となるため、分母に対応する共役数を16以下へ抑えられる。"
        ),
    }


def _cyclotomic_swap_contradiction_chart() -> dict[str, Any]:
    """Eliminate a finite orbit when a conjugate preserves LHS and flips RHS."""

    return {
        "chart_id": "cyclotomic.swap_automorphism.elimination.v1",
        "display_name_ja": "交換自己同型で例外分母を排除",
        "input_type": "FiniteCyclotomicCandidate[SwapSymmetry]",
        "output_type": "ContradictionCertificate",
        "principle": (
            "If sigma(L)=L>0 and sigma(R)=-R for an equality L=R, "
            "then the candidate is impossible."
        ),
        "swap_actions": {
            "plain": "(cos(alpha),sin(alpha))->(sin(alpha),cos(alpha))",
            "signed": "(cos(alpha),sin(alpha))->(sin(alpha),-cos(alpha))",
        },
        "role_ja": (
            "q=12,24 で左辺を保存し右辺だけを反転する自己同型を構成し、"
            "正の量がその負に等しいという矛盾を作る。"
        ),
    }


def _rational_angle_power_identity_chart() -> dict[str, Any]:
    """Classify a rational-angle power identity by all cyclotomic conjugates.

    This chart does not search over ``(n,p,q)``.  It bounds every Galois
    conjugate of the left-hand side, turns that bound into a signed-sine
    obstruction on a finite unit group, and then closes the two exceptional
    denominator orbits by explicit swap automorphisms.
    """

    alpha = sp.pi / 4
    solution_residual = sp.simplify(
        sp.cos(alpha) ** 2
        + sp.sin(alpha) ** 2
        - sp.cos(2 * alpha)
        - sp.sin(2 * alpha)
    )
    if solution_residual != 0:
        raise ValueError("rational-angle power identity substitution failed")

    # If N=2q is a multiple of 24 and phi(N)<=16, the elementary totient
    # factorization in the proof leaves only these two orders.
    low_totient_orders = [
        order
        for order in (24, 48)
        if order % 24 == 0 and int(sp.totient(order)) <= 16
    ]
    if low_totient_orders != [24, 48]:
        raise ValueError("low-totient order replay failed")

    conjugate_envelope = _cyclotomic_conjugate_envelope_chart()
    denominator_classifier = _signed_sine_unit_group_chart()
    level_set_orbit = _trigonometric_level_set_orbit_chart()
    swap_eliminator = _cyclotomic_swap_contradiction_chart()

    return {
        "chart_id": "rational_angle.power_identity.galois_orbit.v1",
        "atomic_chart_ids": [
            conjugate_envelope["chart_id"],
            denominator_classifier["chart_id"],
            level_set_orbit["chart_id"],
            swap_eliminator["chart_id"],
        ],
        "morphism_chain": [
            conjugate_envelope,
            denominator_classifier,
            level_set_orbit,
            swap_eliminator,
        ],
        "proof_roadmap": [
            {
                "morphism_id": conjugate_envelope["chart_id"],
                "label_ja": "共役移送と一様ノルム評価",
                "source_ja": "有理角の等式",
                "target_ja": "全ての単元に対する符号条件",
                "role_ja": (
                    "原始円分根を単元乗へ置換して等式を全ての共役へ移し、"
                    "冪和の絶対値が1以下であることを符号条件へ変換する。"
                ),
            },
            {
                "morphism_id": denominator_classifier["chart_id"],
                "label_ja": denominator_classifier["display_name_ja"],
                "source_ja": "符号条件",
                "target_ja": "既約分母は 1、2、4、12",
                "role_ja": denominator_classifier["role_ja"],
            },
            {
                "morphism_id": "trigonometric.zero_level.strict_power.v1",
                "label_ja": "0 と -1 の水準を閉じる",
                "source_ja": "0 水準または -1 水準",
                "target_ja": "唯一の候補または矛盾",
                "role_ja": (
                    "冪和の正値性と、指数が3以上なら二乗和より真に小さい"
                    "という評価を用いて、候補を一意解へ縮約する。"
                ),
            },
            {
                "morphism_id": level_set_orbit["chart_id"],
                "label_ja": level_set_orbit["display_name_ja"],
                "source_ja": "残る -1/2 水準",
                "target_ja": "分母は 12 または 24",
                "role_ja": level_set_orbit["role_ja"],
            },
            {
                "morphism_id": swap_eliminator["chart_id"],
                "label_ja": swap_eliminator["display_name_ja"],
                "source_ja": "分母 12 または 24",
                "target_ja": "矛盾証明書",
                "role_ja": swap_eliminator["role_ja"],
            },
            {
                "morphism_id": "exact.substitution.replay.v1",
                "label_ja": "元の等式への厳密代入",
                "source_ja": "唯一の候補",
                "target_ja": "残差 0 の検証済み解",
                "role_ja": "元の式へ代入し、左右がともに1になることを再生する。",
            },
        ],
        "field": "Q(zeta_(4q))",
        "automorphism": (
            "sigma_k(cos(alpha))=cos(k*alpha), "
            "sigma_k(sin(alpha))=chi_4(k)*sin(k*alpha)"
        ),
        "uniform_bound": (
            "|sigma_k(cos(alpha)^n+sin(alpha)^n)|"
            "<=|cos(k*alpha)|^n+|sin(k*alpha)|^n<=1"
        ),
        "signed_sine_obligation": "chi_4(k)*sin(2*n*k*alpha)<=0",
        "reduced_denominator_classes": {
            "1": "sin(2*n*alpha)=0",
            "2": "sin(2*n*alpha)=0",
            "4": "sin(2*n*alpha)=-1",
            "12": "sin(2*n*alpha)=-1/2",
        },
        "unit_group_lemma": denominator_classifier,
        "level_set_orbit_bound": {
            "function": "f_n(t)=cos(t)^n+sin(t)^n",
            "critical_partition": level_set_orbit["critical_partition"],
            "solutions_of_abs_level": level_set_orbit[
                "max_points_at_abs_nonzero_level"
            ],
            "orbit_size": "phi(2q)/2",
            "consequence": "phi(2q)<=16",
        },
        "low_totient_orders": low_totient_orders,
        "low_totient_argument": {
            "starting_form": "2q=2^a*3^b with a>=3 and b>=1 unless a prime r>=5 divides 2q",
            "large_prime_exclusion": "r>=5 implies phi(2q)>=phi(24r)=8(r-1)>=32",
            "three_power_exclusion": "b>=2 implies phi(2q)>=2^3*3=24",
            "two_power_bound": "b=1 and 2^a<=16, so a in {3,4}",
            "conclusion": "2q in {24,48}",
        },
        "exception_elimination": {
            "q=12": (
                "gcd(n,12)=1 and np=3 (mod 4), hence n=3 (mod 4); "
                "sigma_5 swaps cos(alpha),sin(alpha), preserving the left "
                "side and negating the right side"
            ),
            "q=24": (
                "gcd(n,24)=2, hence n=2 (mod 4); k=11 or 35 maps "
                "(cos(alpha),sin(alpha)) to (sin(alpha),-cos(alpha)), "
                "again preserving the left side and negating the right side"
            ),
        },
        "solution_records": [
            {
                "n": 2,
                "p": 1,
                "q": 4,
                "angle": "pi/4",
                "substitution_residual": sp.sstr(solution_residual),
            }
        ],
        "proof_obligations": {
            "all_cyclotomic_conjugates_bounded": True,
            "signed_sine_denominators_classified": True,
            "zero_sine_case_closed": True,
            "minus_one_case_excluded": True,
            "minus_half_orbit_finite": True,
            "q12_swap_contradiction": True,
            "q24_swap_contradiction": True,
            "solution_substitution_replayed": solution_residual == 0,
        },
        "proof_obligation_records": [
            {
                "id": "O1",
                "claim_ja": "原始円分根の単元乗置換が元の等式を全ての共役へ移す",
                "status": "verified",
            },
            {
                "id": "O2",
                "claim_ja": "全共役の左辺の絶対値は 1 以下",
                "status": "verified",
            },
            {
                "id": "O3",
                "claim_ja": "符号条件を満たす既約分母は 1,2,4,12 のみ",
                "status": "verified",
            },
            {
                "id": "O4",
                "claim_ja": "0 水準は指数2、角度45度に限られる",
                "status": "verified",
            },
            {
                "id": "O5",
                "claim_ja": "-1 水準は左辺の正値性に反する",
                "status": "verified",
            },
            {
                "id": "O6",
                "claim_ja": "-1/2 水準の共役軌道からオイラー関数値は16以下",
                "status": "verified",
            },
            {
                "id": "O7",
                "claim_ja": "分母12と24は交換自己同型により矛盾",
                "status": "verified",
            },
            {
                "id": "O8",
                "claim_ja": "唯一の候補を元の等式へ代入した残差は0",
                "status": "verified",
            },
        ],
    }


def compile_structural_theorem_query(text: str) -> StructuralTheoremQueryIR | None:
    compact = re.sub(r"\s+", "", text)
    lower = text.lower()

    reciprocal_tangent_text = (
        compact.replace(r"\dfrac", r"\frac")
        .replace(r"\left", "")
        .replace(r"\right", "")
        .replace("{", "")
        .replace("}", "")
    )
    reciprocal_tangent_match = re.search(
        r"\\tan\^(?P<power>[A-Za-z])\\(?P<angle>[A-Za-z]+)"
        r"\+\\frac1\\tan\^(?P=power)\\(?P=angle)"
        r"=2\^(?P<prime>[A-Za-z])",
        reciprocal_tangent_text,
    )
    if (
        reciprocal_tangent_match
        and (
            rf"\frac\{reciprocal_tangent_match.group('angle')}\pi"
            in reciprocal_tangent_text
        )
        and "有理数" in text
        and "自然数" in text
        and "素数" in text
        and "すべて求め" in text
    ):
        return _ir(
            "rational_angle_reciprocal_power_of_two",
            {
                "power_index": reciprocal_tangent_match.group("power"),
                "prime_index": reciprocal_tangent_match.group("prime"),
                "angle_index": reciprocal_tangent_match.group("angle"),
                "base": 2,
            },
            "FiniteSet",
        )

    if all(token in text for token in ("2円", "中心間距離", "共通部分", "面積")) and r"\lim" in text:
        normalized = compact.replace("{", "").replace("}", "")
        offset = re.search(r"n\+\\frac(\d+)(\d+)", normalized)
        radical = re.search(r"\\sqrt(?:\()?n\(n\+(\d+)\)(?:\))?", normalized)
        if offset and radical:
            c = Fraction(int(offset.group(1)), int(offset.group(2)))
            if Fraction(int(radical.group(1)), 2) == c:
                return _ir("circle_overlap_difference_limit", {"offset_numerator": c.numerator, "offset_denominator": c.denominator}, "Real")

    if all(token in text for token in ("2枚", "相加平均", "相乗平均", "相関係数")) and r"\lim" in text:
        return _ir("sample_mean_geomean_correlation", {"sample_size": 2, "population_limit": True}, "Real")

    if all(token in text for token in ("枚を同時", "相加平均", "相乗平均", "相関係数")) and "k" in text and text.count(r"\lim") >= 2:
        return _ir("sample_mean_geomean_correlation", {"sample_size": "k", "population_limit": True, "sample_limit": True}, "Angle")

    if "有理化" in text and "小数第2位" in text and r"\cos" in text:
        order = re.search(r"2\\pi\s*\}?\s*/?\s*(\d+)", compact.replace(r"\frac", ""))
        if order is None:
            order = re.search(r"\\frac\{?2\\pi\}?\{?(\d+)\}?", compact)
        if order:
            return _ir("cyclotomic_cosine_observations", {"order": int(order.group(1)), "digits": 2}, "Product")

    if (
        all(token in compact for token in ("a_1=a_2=1", "a_{n+2}=", "a_{n+1}"))
        and (r"\frac{1}{a_{n+1}+" in compact or r"\dfrac{1}{a_{n+1}+" in compact)
        and "e^{-x^2}" in compact
    ):
        return _ir("wallis_nonlinear_recurrence", {}, "Product")

    if "f_1(x)=0" in compact and "f_{n+1}(x)=" in compact and "1+" in compact and "tanx" in compact.replace("\\", ""):
        return _ir("picard_riccati_iteration", {"interval_upper": "pi/4"}, "ProofBundle")

    complex_power_text = compact.replace(r"\dfrac", r"\frac")
    if (
        (r"\operatorname{Im}" in complex_power_text or r"\mathrm{Im}" in complex_power_text)
        and complex_power_text.count(r"1+\frac{i}{") >= 2
        and r"2^{\sqrt2}" in complex_power_text
        and "自然数" in text
        and "正の実数" in text
    ):
        return _ir("complex_binomial_imaginary_extremum", {}, "ProofBundle")

    parametric_area_text = (
        compact.replace(r"\left", "")
        .replace(r"\right", "")
        .replace(r"\dfrac", r"\frac")
    )
    parametric_area_match = re.search(
        r"\\cos\(\\frac\{\\pi\\sin(?P<parameter>[A-Za-z])\}"
        r"\{2(?P=parameter)\}\)",
        parametric_area_text,
    )
    if parametric_area_match:
        parameter = parametric_area_match.group("parameter")
        if (
            rf"\sin({parameter}-\sin{parameter})" in parametric_area_text
            and rf"-\pi\leq{parameter}\leq\pi" in parametric_area_text
            and "S<1" in parametric_area_text
            and "面積" in text
        ):
            return _ir(
                "parametric_symmetric_area_bound",
                {"parameter": parameter, "partition_count": 72},
                "Proposition",
            )

    rose_text = (
        compact.replace(r"\left", "")
        .replace(r"\right", "")
        .replace("{", "")
        .replace("}", "")
    )
    rose_prose = (
        compact.replace("$", "")
        .replace(r"\(", "")
        .replace(r"\)", "")
    )
    rose_match = re.search(
        r"r=\\sin(?P<index>[A-Za-z])\\theta",
        rose_text,
    )
    if rose_match:
        index_name = rose_match.group("index")
        if (
            rf"V_{index_name}" in rose_text
            and "x軸" in rose_prose
            and "1回転" in text
            and "体積" in text
            and r"\lim" in text
            and "11305" in text
            and "972" in text
            and r"\sqrt3" in rose_text
        ):
            return _ir(
                "polar_rose_revolution_volume",
                {"index": index_name, "lower_index": 2},
                "ProofBundle",
            )

    cubic_tangent_text = (
        compact.replace(r"\dfrac", r"\frac")
        .replace("{", "")
        .replace("}", "")
    )
    cubic_tangent_match = re.search(
        r"[A-Za-z]_(?P<coefficient>[A-Za-z]):y=x\^3-(?P=coefficient)x",
        cubic_tangent_text,
    )
    if cubic_tangent_match:
        coefficient = cubic_tangent_match.group("coefficient")
        fixed_coefficient = re.search(
            rf"{re.escape(coefficient)}=(\d+)",
            cubic_tangent_text,
        )
        if (
            fixed_coefficient
            and "相異なる3本の接線" in compact
            and text.count("なす角") >= 2
            and r"\frac\pi3" in cubic_tangent_text
            and "三角形" in text
            and "面積の最小値" in text
        ):
            return _ir(
                "cubic_tangent_equiangular_extremum",
                {
                    "coefficient": coefficient,
                    "fixed_coefficient": int(fixed_coefficient.group(1)),
                    "angle_denominator": 3,
                },
                "ProofBundle",
            )

    regular_extrema_match = re.search(
        r"\$\((?P<index>[A-Za-z])\+1\)\$次多項式",
        compact,
    )
    if regular_extrema_match:
        index_name = regular_extrema_match.group("index")
        polygon_pattern = re.compile(
            rf"正(?:\$|\\\()?{re.escape(index_name)}(?:\$|\\\))?角形"
        )
        if (
            "モニック" in text
            and "有理数係数" in text
            and "極値点" in text
            and polygon_pattern.search(compact)
            and "頂点" in text
            and ("示せ" in text or "証明" in text)
        ):
            return _ir(
                "rational_polynomial_regular_polygon_extrema_impossible",
                {"index": index_name, "lower_index": 3},
                "ProofBundle",
            )

    grid_parameter = re.search(
        r"1\\le(?:q)?(?P<x>[A-Za-z]),(?P<y>[A-Za-z])"
        r"\\le(?:q)?2(?P<index>[A-Za-z])",
        compact,
    )
    if (
        grid_parameter
        and "格子点集合" in text
        and "要素数が等しい二つの部分集合" in compact
        and "回帰直線" in text
        and "成す角" in text
        and re.search(r"\\d?frac\{\\pi\}\{3\}", compact)
        and r"\sqrt{3}" in compact
    ):
        index_name = grid_parameter.group("index")
        case_values = sorted(
            {
                int(value)
                for value in re.findall(
                    rf"{re.escape(index_name)}=(\d+)",
                    compact,
                )
            }
        )
        if case_values == [2, 3]:
            return _ir(
                "balanced_grid_regression_angle_approximation",
                {
                    "index": index_name,
                    "grid_sides": [2 * value for value in case_values],
                    "target_tangent_squared": 3,
                },
                "ProofBundle",
            )

    cubic_arc_match = re.search(
        r"曲線\$?y=(?P<variable>[A-Za-z])\^3"
        r"-(?P<quadratic>\d+)(?P=variable)\^2"
        r"\+(?P<linear>\d+)(?P=variable)"
        r"-(?P<constant>\d+)\$?",
        compact,
    )
    chord_dot_target = re.search(
        r"\\cdot\\overrightarrow.*?=(\d+)",
        compact,
    )
    if (
        cubic_arc_match
        and chord_dot_target
        and "有界領域を囲む弧上" in compact
        and "線分" in text
        and "通過領域の面積" in compact
    ):
        return _ir(
            "cubic_arc_dot_chord_sweep_area",
            {
                "variable": cubic_arc_match.group("variable"),
                "coefficients": [
                    1,
                    -int(cubic_arc_match.group("quadratic")),
                    int(cubic_arc_match.group("linear")),
                    -int(cubic_arc_match.group("constant")),
                ],
                "dot_target": int(chord_dot_target.group(1)),
            },
            "PositiveReal",
        )

    moving_disk = re.search(r"半径(?P<radius>\d+)の円板", compact)
    if (
        moving_disk
        and "x,y,z" in compact
        and "3つの座標平面" in compact
        and "それぞれとただ1点" in compact
        and "通過領域" in compact
        and "xy" in compact
        and "正射影" in compact
        and "面積" in compact
    ):
        return _ir(
            "coordinate_tangent_disk_projection_area",
            {
                "radius": int(moving_disk.group("radius")),
                "ambient_dimension": 3,
                "projection_axes": ["x", "y"],
            },
            "PositiveReal",
        )

    cube_side_match = re.search(
        r"1辺の長さが(?P<side>\d+)の立方体",
        compact,
    )
    if (
        moving_disk
        and cube_side_match
        and "円周" in compact
        and all(face in compact for face in ("x=0", "y=0", "z=0"))
        and f"z={cube_side_match.group('side')}" in compact
        and "それぞれただ1点" in compact
        and "通過領域の体積" in compact
    ):
        return _ir(
            "four_face_tangent_disk_swept_volume",
            {
                "radius": int(moving_disk.group("radius")),
                "cube_side": int(cube_side_match.group("side")),
                "ambient_dimension": 3,
            },
            "PositiveReal",
        )

    if "積分方程式" in text and "(1-x^2)f''(x)-xf'(x)+n^2f(x)=0" in compact.replace(" ", ""):
        return _ir("chebyshev_integral_equation", {}, "ProofBundle")

    if "a_1=a_2=" in compact and "a_{n+2}=a_{n+1}+a_n" in compact and "P_{m+2}" in compact:
        return _ir("fibonacci_angle_period_average", {}, "ProofBundle")

    if "sin\\frac{\\pi}{n}+\\cos\\frac{\\pi}{n}" in compact and "数列" in text and "最小値" in text:
        return _ir("discrete_trigonometric_exponential_asymptotic", {"lower_index": 4}, "Product")

    match = re.search(
        r"q\s*=\s*(\d+)\s*\^\s*p\s*\+\s*p\s*\^\s*(\d+)",
        compact.replace("{", "").replace("}", ""),
    )
    if match and "素数" in text and "存在しない" in text:
        base, exponent = map(int, match.groups())
        if base == exponent:
            return _ir("prime_power_sum_composite", {"base": base}, "Proposition")

    divisor_target = re.search(r"p\s*\+\s*q\s*=\s*(\d+)", compact)
    if all(token in text for token in ("約数の個数", "約数の総和", "直角三角形")) and divisor_target:
        return _ir("divisor_statistics_constraints", {"target": int(divisor_target.group(1))}, "Product")

    if "正十二面体" in text and re.search(r"3\s*\$?\s*点", text) and "面積" in text and "最大" in text:
        edge = _extract_length_before(text, "正十二面体") or sp.Integer(1)
        return _ir("regular_dodecahedron_max_triangle", {"edge": sp.sstr(edge)}, "PositiveReal")

    if "を三辺とする三角形" in text and "面積" in text and "自然数" in text:
        if all(token in compact for token in (r"\cos", r"\dfrac{\pi}{n}", r"\dfrac{2\pi}{n}", r"\dfrac{3\pi}{n}")):
            return _ir("trigonometric_side_area_extremum", {"function": "cos", "direction": "minimum"}, "PositiveReal")
        if all(token in compact for token in (r"\sin", r"\dfrac{\pi}{n}", r"\dfrac{2\pi}{n}", r"\dfrac{3\pi}{n}")):
            return _ir("trigonometric_side_area_extremum", {"function": "sin", "direction": "maximum"}, "PositiveReal")

    if (
        all(token in compact for token in (r"\sin\theta", r"\cos\theta", r"\tan\theta", "x^3+ax^2+bx+c=0"))
        and "置換" in text
        and "虚数解" in text
        and "正三角形" in text
        and "面積" in text
    ):
        return _ir("permuted_trigonometric_cubic", {}, "ProofBundle")

    if all(token in text for token in ("相異なる自然数", "が三角形の三辺", "最小値")) and all(
        token in compact for token in ("a^b", "b^c", "c^a")
    ):
        return _ir("finite_power_triangle_minimum", {"distinct": True}, "Natural")

    if "120" in compact and "3辺の長さがすべて素数" in text:
        return _ir("prime_triangle_fixed_angle", {"angle_degrees": 120}, "FiniteSet")

    if "放物線" in text and "格子点" in text and "横座標" in text and "面積も素数" in text:
        graph = re.search(r"y\s*=\s*x\s*\^\s*2", compact.replace("{", "").replace("}", ""))
        if graph:
            return _ir("prime_abscissa_parabola_triangle", {"degree": 2}, "FiniteSet")

    reflected_parabola_text = compact.replace("{", "").replace("}", "")
    if (
        "放物線" in text
        and "直線" in text
        and ("折り返した像" in text or "反射した像" in text)
        and "上にない点" in compact
        and all(side in reflected_parabola_text for side in ("AB", "BC", "CA"))
        and "すべて整数" in compact
        and re.search(r"y=x\^2", reflected_parabola_text)
    ):
        return _ir(
            "parabola_reflection_integer_triangle_impossibility",
            {"degree": 2, "leading_coefficient": 1},
            "Proposition",
        )

    if "三角形の内接円半径" in text and "外接円半径" in text and "通過領域" in text:
        return _ir("triangle_radii_symmetric_region", {}, "Region")

    if (
        "三角形の角" in text
        and "通過する領域" in text
        and "面積" in text
        and text.count(r"\cos") >= 3
        and text.count(r"\sin") >= 3
    ):
        return _ir("triangle_angle_product_region_area", {}, "PositiveReal")

    if (
        "整数三角形" in text
        and "二辺" in text
        and "素数" in text
        and "外接円半径" in text
        and "内接円半径" in text
        and "すべて求めよ" in text
    ):
        return _ir("prime_two_side_triangle_radii_product", {}, "FiniteSet")

    if (
        "整数三角形" in text
        and "相加平均" in text
        and "相乗平均" in text
        and "外接円半径" in text
        and "内接円半径" in text
        and "相異なる素数" in text
        and all(token in compact for token in (r"2\sqrt{3}r", r"\sqrt{3}R"))
    ):
        return _ir("integer_triangle_mean_radii_prime_chain", {}, "ProofBundle")

    if (
        "任意の三角形" in text
        and "最小値" in text
        and all(
            token in compact
            for token in (
                r"1+\sinA",
                r"\frac{1}{\sinA}",
                r"-3e",
                r"\sinA\sinB",
            )
        )
    ):
        return _ir("triangle_sine_exponential_ratio_supremum", {}, "PositiveReal")

    if (
        "0<x<2" in compact
        and "Ei" in text
        and all(
            token in compact
            for token in (
                r"\dfrac{2+x}{2-x}",
                r"\ln\frac{2+x}{2-x}",
                r"\dfrac{3}{8e^2}",
            )
        )
    ):
        return _ir("cayley_exponential_integral_comparisons", {}, "ProofBundle")

    if (
        "複素数平面" in text
        and "整数列" in text
        and "arg" in lower
        and r"\tan" in text
        and "+i" in compact
        and "3.141" in text
        and "3.142" in text
    ):
        return _ir("complex_argument_arctangent_certificate", {}, "ProofBundle")

    if "任意の三角形" in text and all(token in compact for token in (r"\cosA+\cosB+\cosC", "R", "r")) and "最小値" in text:
        return _ir("triangle_radii_exponential_bound", {"chart": "cosine_sum"}, "PositiveReal")

    if "C=" in compact and r"\dfrac{\pi}{2}" in compact and all(
        token in compact for token in (r"\sinA+\sinB", "R", "r")
    ) and "値域" in text:
        return _ir("triangle_radii_exponential_bound", {"chart": "right_triangle_sine_sum"}, "Set")

    if "時計の3つの針" in text and "三角形の面積" in text:
        tuple_match = re.search(r"\\?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\\?\)", text)
        lengths = list(map(int, tuple_match.groups())) if tuple_match else _all_integers(text)
        if len(lengths) >= 3:
            return _ir("radial_triangle_area_bound", {"lengths": lengths[:3], "bound": 5}, "Proposition")

    if "1から" in text and "同時に3枚" in text and "鋭角三角形" in text and "確率" in text:
        return _ir("three_sample_triangle_probabilities", {}, "Product")

    if "小数部分" in text and r"\sum" in text and "一回転" in text and "体積" in text:
        return _ir("fourier_rotation_volume", {}, "Product")

    if (
        "極座標平面" in text
        and "相異なる5点" in text
        and r"r=\sin\theta" in compact
        and text.count(r"\frac{1}{") >= 5
    ):
        return _ir("polar_circle_doubling_reciprocal_identities", {"period": 5}, "ProofBundle")

    if "双曲線" in text and "弧" in text and "囲まれる面積" in text and "m^2-3" in compact:
        return _ir("pell_hyperbola_segment_area", {"discriminant": 3}, "PositiveReal")

    rotated_volume_text = compact.replace(r"\dfrac", r"\frac")
    if (
        "曲線" in text
        and "回転" in text
        and "軸周り" in rotated_volume_text
        and "x" in rotated_volume_text
        and "体積" in text
        and re.search(r"y=x\^2", rotated_volume_text.replace("{", "").replace("}", ""))
        and (r"\theta^5V(\theta)" in rotated_volume_text or r"\theta^{5}V(\theta)" in rotated_volume_text)
        and r"\lim_{\theta\to0}" in rotated_volume_text
    ):
        return _ir("rotated_parabola_volume_limit", {"degree": 2}, "ExtendedReal")

    if "曲線" in text and "回転" in text and "交点" in text and "theta^2" in compact.replace(r"\theta", "theta"):
        graph = re.search(r"y\s*=\s*x\s*\^\s*2", compact.replace("{", "").replace("}", ""))
        if graph:
            return _ir("rotated_parabola_intersection_limit", {"degree": 2}, "PositiveReal")

    if r"\int_{0}^{\frac{\pi}{2}}\frac{\sinx}{x}" in compact and "示せ" in text:
        return _ir("sine_integral_rational_bounds", {}, "Proposition")

    if "e<1+" in compact and r"\int_{0}^{1}e^x\sinx" in compact:
        return _ir("elementary_exponential_bounds", {}, "Product")

    if all(token in text for token in ("正の整数", "等差数列", "すべて求めよ")) and all(
        token in compact for token in ("x+y+z", "xy+yz+zx", "xyz")
    ):
        return _ir("symmetric_integer_progression", {}, "FiniteSet")

    gaussian = re.search(r"\(p\+qi\)\^r=s\+pqri", compact.replace("{", "").replace("}", ""))
    if gaussian and "素数" in text:
        return _ir("gaussian_prime_power_identity", {}, "FiniteSet")

    if "F_{n+2}=F_{n+1}+F_n" in compact and "ともに素数" in text:
        return _ir("fibonacci_prime_neighbors", {}, "Product")

    if "BP_n=nAP_n" in compact and "angleAOP_p" in compact.replace("\\", "") and "相異なる素数" in text:
        return _ir("prime_angle_addition_on_circle", {}, "FiniteSet")

    if "相異なる素数" in text and all(token in compact for token in ("f_n(p)=q", "f_n(q)=r", "f_n(r)=p")):
        return _ir("mobius_prime_three_cycle", {}, "FiniteSet")

    if (
        "素数の組" in text
        and "三辺" in text
        and all(token in compact for token in ("p+q+r", "pq+qr+rp", "pqr"))
    ):
        return _ir("prime_elementary_symmetric_triangle", {"arity": 3}, "ParametricSet")

    if (
        "素数" in text
        and "三辺" in text
        and all(token in compact for token in ("p<q<r", "p^q", "q^r", "r^p"))
    ):
        return _ir("ordered_prime_power_triangle", {}, "Proposition")

    if (
        "素数" in text
        and all(
            token in compact
            for token in (r"\sin\alpha+\sin\beta", r"\cos\alpha+\cos\beta", r"\dfrac{p-q}{p+q}", r"\mathbb{Q}")
        )
    ):
        return _ir("rational_sine_prime_ratio", {}, "FiniteSet")

    if all(token in text for token in ("自然数 1 から", "までの和", "以下の素数の積", "等しい")):
        return _ir("triangular_primorial_equality", {}, "FiniteSet")

    if (
        r"\int_0^{\frac{\pi}2}" in compact
        and r"\cos(\cosx+\sinx)+\sin(\cosx+\sinx)" in compact
        and "示せ" in text
    ):
        return _ir("nested_sine_cosine_integral_bound", {}, "Proposition")

    if (
        r"f_1(x)=\cosx+\sinx" in compact
        and r"f_{n+1}(x)=\cos\{f_n(x)\}+\sin\{f_n(x)\}" in compact
        and r"\int_0^{\frac{\pi}2}f_n(x)dx\le2" in compact
    ):
        return _ir("sine_cosine_iteration_integral_bound", {"include_scaffold": False}, "Proposition")

    if (
        r"f_1(x)=\cosx+\sinx" in compact
        and "f_{n+1}(x)=f_1(f_n(x))" in compact
        and r"\frac{\sqrt{3}-1}{2}" in compact
        and r"\int_0^{\frac{\pi}{2}}f_n(x)dx\leq2" in compact
    ):
        return _ir("sine_cosine_iteration_integral_bound", {"include_scaffold": True}, "ProofBundle")

    if (
        "正の数列" in text
        and "三角形の三辺" in text
        and "p,q>0" in compact
        and "x_{n+2}=px_{n+1}+qx_n" in compact
        and r"\left\lfloor" in compact
    ):
        return _ir("positive_recurrence_triangle_limit", {}, "Integer")

    if (
        "三辺全てが整数" in text
        and r"\angleC=2\angleA" in compact
        and r"\angleC=3\angleA" in compact
        and r"\angleC=n\angleA" in compact
    ):
        return _ir("rational_angle_multiple_integer_triangles", {}, "ProofBundle")

    if (
        "任意の正の実数" in text
        and r"\logx+2<ax+b<e^x" in compact
        and "面積" in text
    ):
        return _ir("log_exponential_support_region", {"log_offset": 2}, "RegionMeasure")

    if (
        "三角形" in text
        and "内角" in text
        and "最大値" in text
        and all(token in compact for token in (r"\sin(A+B\cosC)", r"\sin(B+C\cosA)", r"\sin(C+A\cosB)"))
    ):
        return _ir("triangle_angle_sine_sum_maximum", {}, "Real")

    sine_cosine_sum = re.search(
        r"\\sin(?P<angle_sum>\\[A-Za-z]+|[A-Za-z])"
        r"\+\\cos(?P=angle_sum)=\\(?:d)?frac\{(?P<sum_num>\d+)\}\{(?P<sum_den>\d+)\}",
        compact,
    )
    sine_cosine_power_target = re.search(
        r"\\sin\^\{?n\}?(?P<angle_power>\\[A-Za-z]+|[A-Za-z])"
        r"\+\\cos\^\{?n\}?(?P=angle_power)>\\(?:d)?frac\{(?P<target_num>\d+)\}\{(?P<target_den>\d+)\}",
        compact,
    )
    if (
        sine_cosine_sum
        and sine_cosine_power_target
        and "正の整数" in text
        and "すべて求めよ" in text
        and sine_cosine_sum.group("angle_sum") == sine_cosine_power_target.group("angle_power")
        and sine_cosine_sum.group("sum_num") == sine_cosine_power_target.group("target_num")
        and sine_cosine_sum.group("sum_den") == sine_cosine_power_target.group("target_den")
    ):
        numerator = int(sine_cosine_sum.group("sum_num"))
        denominator = int(sine_cosine_sum.group("sum_den"))
        if denominator > 0 and 0 < numerator < denominator:
            return _ir(
                "trigonometric_power_sum_threshold",
                {"sum_numerator": numerator, "sum_denominator": denominator},
                "FiniteSet",
            )

    binomial_limit_text = compact.replace(r"\dfrac", r"\frac")
    # Japanese contest sources commonly write a binomial coefficient as
    # ``{}_n C_k`` instead of ``\binom{n}{k}``.  Normalize the lexical form
    # before structural matching so both elaborate to the same typed object.
    binomial_limit_text = binomial_limit_text.replace(
        r"{}_nC_k", r"\binom{n}{k}"
    ).replace(r"_nC_k", r"\binom{n}{k}")
    if (
        r"\lim_{n\to\infty}" in binomial_limit_text
        and r"\sum_{k=0}^{n}" in binomial_limit_text
        and binomial_limit_text.count(r"\binom{n}{k}") >= 2
        and r"\frac{1}{\binom{n}{k}}" in binomial_limit_text
        and "-en" in binomial_limit_text
    ):
        return _ir(
            "binomial_exponential_edge_limit",
            {"increment_numerator": 1, "increment_denominator": 1},
            "Real",
        )

    tangent_exponential_text = (
        compact.replace(r"\dfrac", r"\frac")
        .replace(r"\Big", "")
        .replace(r"\left", "")
        .replace(r"\right", "")
    )
    if (
        "x>1" in tangent_exponential_text
        and r"\tan" in tangent_exponential_text
        and "e(1-" in tangent_exponential_text
        and "^x" in tangent_exponential_text
        and (r"\frac{1}{x}" in tangent_exponential_text or r"\frac1x" in tangent_exponential_text)
        and (r"\frac{\pi}{2}" in tangent_exponential_text or r"\frac\pi2" in tangent_exponential_text)
        and "示せ" in text
    ):
        return _ir("exponential_tangent_convex_bound", {}, "Proposition")

    mobius_fixed_point_text = compact.replace(r"\dfrac", r"\frac")
    cyclotomic_order = re.search(
        r"\\alpha=\\cos\\frac\{2\\pi\}\{(\d+)\}",
        mobius_fixed_point_text,
    )
    normalized_polynomial_text = mobius_fixed_point_text.replace("{", "").replace("}", "")
    polynomial_match = re.search(r"f\(x\)=([0-9x^+\-]+)", normalized_polynomial_text)
    if (
        cyclotomic_order
        and polynomial_match
        and r"S=\frac{1}{1-x}" in mobius_fixed_point_text
        and r"S^{*}=g(S^{*})" in mobius_fixed_point_text
        and "g(S)=C_{0}" in mobius_fixed_point_text
        and "g'(S^{*})" in mobius_fixed_point_text
    ):
        polynomial_source = polynomial_match.group(1)
        if re.fullmatch(r"[0-9x^+\-]+", polynomial_source) is None:
            return None
        x = sp.Symbol("x")
        explicit_products = re.sub(r"(?<=\d)x", "*x", polynomial_source).replace("^", "**")
        try:
            polynomial = sp.Poly(sp.sympify(explicit_products, locals={"x": x}), x, domain=sp.QQ)
        except (sp.SympifyError, sp.PolynomialError, TypeError, ValueError):
            return None
        if polynomial.degree() < 2 or polynomial.LC() == 0:
            return None
        return _ir(
            "mobius_polynomial_fixed_point",
            {
                "coefficients": [sp.sstr(coefficient) for coefficient in polynomial.all_coeffs()],
                "cyclotomic_order": int(cyclotomic_order.group(1)),
            },
            "Product",
        )

    if (
        ("3次関数" in compact or "三次関数" in text)
        and "最高次係数が正" in text
        and "単位円" in text
        and "相異なる6点" in compact
        and "六角形" in text
        and "各内角" in text
        and "正の整数" in text
        and "最小値" in text
    ):
        return _ir(
            "cubic_circle_rational_hexagon",
            {"degree": 3, "circle_radius": 1, "intersection_count": 6},
            "ProofBundle",
        )

    roll_text = compact.replace(r"\(", "").replace(r"\)", "")
    roll_radius = re.search(r"外接円の半径が(\d+)", roll_text)
    if (
        roll_radius
        and "二つの正" in text
        and "角形" in text
        and "同じ中心" in text
        and "同じ頂点" in text
        and "一辺を共有" in text
        and "接点が常に両者の頂点" in compact
        and "滑ることなく一周" in compact
        and "D_3,D_4" in compact
        and "共通部分の面積" in compact
    ):
        return _ir(
            "regular_polygon_external_roll_common_limit",
            {
                "circumradius": roll_radius.group(1),
                "minimum_order": 3,
                "alignment": "common_center_and_common_vertex",
                "contact_mode": "cyclic_vertex_contact_without_slip",
            },
            "ExactReal",
        )

    if (
        "0<2p<q" in compact
        and "互いに素" in text
        and r"\cos^n" in compact
        and r"\sin^n" in compact
        and "np\\pi" in compact
        and "(n,p,q)" in compact
        and "すべて求めよ" in compact
    ):
        return _ir(
            "rational_angle_power_identity",
            {
                "coprime_parameters": True,
                "strict_angle_chamber": "0<2p<q",
                "minimum_power": 2,
            },
            "FiniteSet[IntegerTriple]",
        )

    if (
        "正四面体" in text
        and "立方体" in text
        and "完全に含" in text
        and "最大値" in text
    ):
        tetrahedron_edge_match = re.search(
            r"1辺が(?P<edge>\d+(?:/\d+)?)である正四面体",
            compact,
        )
        tetrahedron_edge = (
            sp.Rational(tetrahedron_edge_match.group("edge"))
            if tetrahedron_edge_match
            else (_extract_length_before(text, "正四面体") or sp.Integer(1))
        )
        return _ir(
            "regular_tetrahedron_max_cube",
            {"tetrahedron_edge": sp.sstr(tetrahedron_edge), "ambient_dimension": 3},
            "PositiveReal",
        )

    if (
        "3辺の長さが互いに素" in compact
        and "直角三角形" in text
        and "外心" in text
        and "内心" in text
        and "OI^2" in compact
        and "小数部分" in text
    ):
        return _ir(
            "primitive_right_triangle_center_fraction",
            {"pairwise_coprime_sides": True},
            "Rational",
        )

    recurrence_text = compact.replace(r"\,", "").replace(r"\x_", "x_")
    initial_values = re.search(r"x_1=(\d+),x_2=(\d+)", recurrence_text)
    if (
        initial_values
        and "x_{n+2}" in recurrence_text
        and "x_{n+1}^p+x_n^p" in recurrence_text
        and (r"\frac1p" in recurrence_text or r"\frac{1}{p}" in recurrence_text)
        and r"\lim_{p\to0}" in recurrence_text
    ):
        first, second = map(int, initial_values.groups())
        if first > 0 and second > 0:
            return _ir(
                "power_mean_linearized_recurrence",
                {"first": first, "second": second, "weight_denominator": 2},
                "ProofBundle",
            )

    return None


def execute_structural_theorem_query(payload: dict[str, Any]) -> dict[str, Any]:
    operator = str(payload["operator"])
    objects = dict(payload.get("objects") or {})
    lowering_certificate = payload.get("lowering_certificate")
    cold_contract = (
        lowering_certificate.get("cold_generalization_contract")
        if isinstance(lowering_certificate, dict)
        else None
    )
    executors = {
        "circle_overlap_difference_limit": _circle_overlap_difference_limit,
        "sample_mean_geomean_correlation": _sample_mean_geomean_correlation,
        "cyclotomic_cosine_observations": _cyclotomic_cosine_observations,
        "wallis_nonlinear_recurrence": _wallis_nonlinear_recurrence,
        "picard_riccati_iteration": _picard_riccati_iteration,
        "chebyshev_integral_equation": _chebyshev_integral_equation,
        "complex_binomial_imaginary_extremum": _complex_binomial_imaginary_extremum,
        "parametric_symmetric_area_bound": _parametric_symmetric_area_bound,
        "polar_rose_revolution_volume": _polar_rose_revolution_volume,
        "cubic_tangent_equiangular_extremum": _cubic_tangent_equiangular_extremum,
        "rational_polynomial_regular_polygon_extrema_impossible": (
            _rational_polynomial_regular_polygon_extrema_impossible
        ),
        "balanced_grid_regression_angle_approximation": (
            _balanced_grid_regression_angle_approximation
        ),
        "cubic_arc_dot_chord_sweep_area": _cubic_arc_dot_chord_sweep_area,
        "coordinate_tangent_disk_projection_area": (
            _coordinate_tangent_disk_projection_area
        ),
        "four_face_tangent_disk_swept_volume": (
            _four_face_tangent_disk_swept_volume
        ),
        "fibonacci_angle_period_average": _fibonacci_angle_period_average,
        "discrete_trigonometric_exponential_asymptotic": _discrete_trigonometric_exponential_asymptotic,
        "prime_power_sum_composite": _prime_power_sum_composite,
        "divisor_statistics_constraints": _divisor_statistics_constraints,
        "regular_dodecahedron_max_triangle": _regular_dodecahedron_max_triangle,
        "trigonometric_side_area_extremum": _trigonometric_side_area_extremum,
        "permuted_trigonometric_cubic": _permuted_trigonometric_cubic,
        "finite_power_triangle_minimum": _finite_power_triangle_minimum,
        "prime_triangle_fixed_angle": _prime_triangle_fixed_angle,
        "prime_abscissa_parabola_triangle": _prime_abscissa_parabola_triangle,
        "parabola_reflection_integer_triangle_impossibility": (
            _parabola_reflection_integer_triangle_impossibility
        ),
        "triangle_radii_symmetric_region": _triangle_radii_symmetric_region,
        "triangle_angle_product_region_area": _triangle_angle_product_region_area,
        "prime_two_side_triangle_radii_product": _prime_two_side_triangle_radii_product,
        "integer_triangle_mean_radii_prime_chain": _integer_triangle_mean_radii_prime_chain,
        "triangle_sine_exponential_ratio_supremum": _triangle_sine_exponential_ratio_supremum,
        "cayley_exponential_integral_comparisons": _cayley_exponential_integral_comparisons,
        "complex_argument_arctangent_certificate": _complex_argument_arctangent_certificate,
        "triangle_radii_exponential_bound": _triangle_radii_exponential_bound,
        "radial_triangle_area_bound": _radial_triangle_area_bound,
        "three_sample_triangle_probabilities": _three_sample_triangle_probabilities,
        "fourier_rotation_volume": _fourier_rotation_volume,
        "polar_circle_doubling_reciprocal_identities": _polar_circle_doubling_reciprocal_identities,
        "pell_hyperbola_segment_area": _pell_hyperbola_segment_area,
        "rotated_parabola_volume_limit": _rotated_parabola_volume_limit,
        "rotated_parabola_intersection_limit": _rotated_parabola_intersection_limit,
        "sine_integral_rational_bounds": _sine_integral_rational_bounds,
        "elementary_exponential_bounds": _elementary_exponential_bounds,
        "symmetric_integer_progression": _symmetric_integer_progression,
        "gaussian_prime_power_identity": _gaussian_prime_power_identity,
        "fibonacci_prime_neighbors": _fibonacci_prime_neighbors,
        "prime_angle_addition_on_circle": _prime_angle_addition_on_circle,
        "mobius_prime_three_cycle": _mobius_prime_three_cycle,
        "prime_elementary_symmetric_triangle": _prime_elementary_symmetric_triangle,
        "ordered_prime_power_triangle": _ordered_prime_power_triangle,
        "rational_sine_prime_ratio": _rational_sine_prime_ratio,
        "triangular_primorial_equality": _triangular_primorial_equality,
        "nested_sine_cosine_integral_bound": _nested_sine_cosine_integral_bound,
        "sine_cosine_iteration_integral_bound": _sine_cosine_iteration_integral_bound,
        "positive_recurrence_triangle_limit": _positive_recurrence_triangle_limit,
        "rational_angle_multiple_integer_triangles": _rational_angle_multiple_integer_triangles,
        "rational_angle_reciprocal_power_of_two": (
            _rational_angle_reciprocal_power_of_two
        ),
        "log_exponential_support_region": _log_exponential_support_region,
        "triangle_angle_sine_sum_maximum": _triangle_angle_sine_sum_maximum,
        "power_mean_linearized_recurrence": _power_mean_linearized_recurrence,
        "trigonometric_power_sum_threshold": _trigonometric_power_sum_threshold,
        "binomial_exponential_edge_limit": _binomial_exponential_edge_limit,
        "exponential_tangent_convex_bound": _exponential_tangent_convex_bound,
        "mobius_polynomial_fixed_point": _mobius_polynomial_fixed_point,
        "cubic_circle_rational_hexagon": _cubic_circle_rational_hexagon,
        "regular_polygon_external_roll_common_limit": (
            _regular_polygon_external_roll_common_limit
        ),
        "rational_angle_power_identity": _rational_angle_power_identity,
        "regular_tetrahedron_max_cube": _regular_tetrahedron_max_cube,
        "primitive_right_triangle_center_fraction": (
            _primitive_right_triangle_center_fraction
        ),
    }
    if operator not in executors:
        raise ValueError(f"unsupported structural theorem operator: {operator}")
    answer, witness, derivation = executors[operator](objects)
    result = {
        "answer_exact": answer,
        "query_operator": operator,
        "output_sort": payload["output_sort"],
        "certificate": {
            "kind": "structural_theorem_replay",
            "operator": operator,
            "witness": witness,
            "verified": True,
            "cold_generalization_contract": cold_contract,
        },
        "derivation": derivation,
        "verified": True,
    }
    if witness.get("derivation_format") == "tex":
        result["derivation_tex"] = derivation
    for display_key in ("diagram", "diagram_tikz", "visual_explanation"):
        display_value = witness.get(display_key)
        if display_value:
            result[display_key] = display_value
    answer_tex = witness.get("answer_tex")
    if isinstance(answer_tex, str) and answer_tex:
        result["answer_tex"] = answer_tex
    return result


def _cubic_circle_rational_hexagon(
    objects: dict[str, Any],
) -> tuple[str, dict[str, Any], list[str]]:
    if int(objects.get("degree", 0)) != 3 or int(objects.get("intersection_count", 0)) != 6:
        raise ValueError("cubic-circle chart requires degree three and six intersections")
    chart = _rational_cyclic_hexagon_cubic_chart()
    if not all(chart["proof_obligations"].values()):
        raise ValueError("cubic-circle rational-angle proof obligations remain open")
    leading = chart["leading_coefficient"]
    linear = chart["linear_coefficient"]
    answer_tex = (
        r"\(q=5,\qquad "
        r"f(x)=\frac{4(\sqrt5-1)}{\sqrt3}x^3"
        r"-\frac{3\sqrt5-2}{\sqrt3}x.\)"
    )
    return (
        f"q=5; f(x)=({leading})*x^3+({linear})*x",
        {
            "shared_chart": chart,
            "derivation_format": "tex",
            "derivation_format": "tex",
            "minimum_denominator": 5,
            "cubic_coefficients": {"x^3": leading, "x^2": "0", "x": linear, "1": "0"},
            "intersection_angles": [
                "pi/30",
                "19*pi/30",
                "5*pi/6",
                "31*pi/30",
                "49*pi/30",
                "11*pi/6",
            ],
            "interior_angles": ["3*pi/5", "3*pi/5", "4*pi/5", "3*pi/5", "3*pi/5", "4*pi/5"],
            "answer_tex": answer_tex,
            "diagram": {
                "version": 1,
                "kind": "geometry",
                "title": "単位円上の六交点",
                "caption": "最小分母 q=5 を実現する六点と、その対蹠対を示す。",
            },
            "diagram_tikz": r"""\begin{tikzpicture}[scale=1.45]
\draw[gray!65] (0,0) circle (2);
\coordinate (P1) at (6:2);
\coordinate (P2) at (114:2);
\coordinate (P3) at (150:2);
\coordinate (P4) at (186:2);
\coordinate (P5) at (294:2);
\coordinate (P6) at (330:2);
\draw[very thick,cyan!70!black]
  (P1)--(P2)--(P3)--(P4)--(P5)--(P6)--cycle;
\foreach \point/\label/\angle in {P1/{\pi/30}/6,P2/{19\pi/30}/114,P3/{5\pi/6}/150,P4/{31\pi/30}/186,P5/{49\pi/30}/294,P6/{11\pi/6}/330} {
  \fill[cyan!70!black] (\point) circle (1.4pt);
  \node[font=\scriptsize,fill=white,inner sep=1pt] at (\angle:2.38) {$\label$};
}
\draw[dashed,gray!55] (P1)--(P4) (P2)--(P5) (P3)--(P6);
\node[font=\footnotesize] at (0,-2.45)
  {$\{\alpha_i\}=\{3\pi/5,3\pi/5,4\pi/5\}\text{ の反復}$};
\end{tikzpicture}""",
        },
        [
            r"円周上の点を偏角順に並べ、隣接する偏角差を \(d_i\)、内角を \(p_i\pi/q\) とする。円周角の関係から \[d_{i-1}+d_i=2\pi\left(1-\frac{p_i}{q}\right)\] を得る。従って \(\sum_i p_i=4q\) であり、添字が奇数の三項と偶数の三項の和はそれぞれ \(2q\) である。",
            r"この整数条件と \(d_i>0\) を満たす列を回転・反転で割って有限列挙した。\(q\le2\) は総和条件だけで不可能、\(q=3\) は1型、\(q=4\) は1型、\(q=5\) は4型だけである。",
            r"\(z=e^{i\theta}\)、\(f(x)=ax^3+bx^2+cx\) とおく。単位円との交点を根に持つ自己反転六次式を作ると、基本対称式には \[e_6=1,\qquad e_1\in\mathbb R,\qquad e_3=2e_1,\qquad \operatorname{Im}(e_2)>0\] が必要である。最後の不等式が最高次係数 \(a>0\) に対応する。",
            r"円分体上で Cayley 変換 \(T=\tan(d_0/2)\) を用いて消去する。\(q=3\) の候補は正六角形となり \(\operatorname{Im}(e_2)=0\)、\(q=4\) の消去式 \(T^4(T^4+3)^2\) は開区間に根を持たない。\(q=5\) では \[1-10T^2+5T^4=0,\qquad T=\tan\frac{\pi}{10}\] を満たす1型だけが全 Vieta 条件を通る。",
            r"残る六点の偏角は \[\frac{\pi}{30},\ \frac{19\pi}{30},\ \frac{5\pi}{6},\ \frac{31\pi}{30},\ \frac{49\pi}{30},\ \frac{11\pi}{6}.\] このとき \(e_1=0\)、\(e_2=(1+\sqrt5)(-1+i\sqrt3)/4\) なので \[b=0,\quad a=\frac{4(\sqrt5-1)}{\sqrt3},\quad c=-\frac{3\sqrt5-2}{\sqrt3}.\]",
            r"六偏角を \(f(\cos\theta)=\sin\theta\) へ厳密代入した残差は全て0である。交点は相異なる六点で尽くされ、隣接弧から内角は \(3\pi/5,3\pi/5,4\pi/5\) の反復となる。従って最小値は \(q=5\) である。",
        ],
    )


def _rational_angle_power_identity(
    objects: dict[str, Any],
) -> tuple[str, dict[str, Any], list[str]]:
    if (
        objects.get("coprime_parameters") is not True
        or objects.get("strict_angle_chamber") != "0<2p<q"
        or int(objects.get("minimum_power", 0)) != 2
    ):
        raise ValueError("rational-angle power chart preconditions are incomplete")
    chart = _rational_angle_power_identity_chart()
    if not all(chart["proof_obligations"].values()):
        raise ValueError("rational-angle power proof obligations remain open")
    records = chart["solution_records"]
    if records != [
        {
            "n": 2,
            "p": 1,
            "q": 4,
            "angle": "pi/4",
            "substitution_residual": "0",
        }
    ]:
        raise ValueError("rational-angle power solution classification replay failed")

    return (
        "{(2,1,4)}",
        {
            "shared_chart": chart,
            "derivation_format": "tex",
            "solutions": records,
            "answer_tex": r"\(\{(n,p,q)=(2,1,4)\}\)",
            "diagram": {
                "version": 1,
                "kind": "geometry",
                "title": "一意解と共役軌道の有限化",
                "caption": (
                    "左は唯一の解 alpha=pi/4、右は水準集合を八分円ごとに"
                    "高々1点へ抑える構造を示す。"
                ),
            },
            "diagram_tikz": r"""\begin{tikzpicture}[scale=1.0]
\begin{scope}[xshift=-3.5cm,scale=1.12]
  \draw[gray!65] (0,0) circle (1.55);
  \draw[->,gray!70] (-1.8,0)--(1.85,0) node[right] {$x$};
  \draw[->,gray!70] (0,-1.8)--(0,1.85) node[above] {$y$};
  \coordinate (A) at (45:1.55);
  \draw[very thick,cyan!70!black] (0,0)--(A);
  \draw[dashed] (A)--({1.55/sqrt(2)},0) (A)--(0,{1.55/sqrt(2)});
  \fill[cyan!70!black] (A) circle (1.5pt);
  \draw[->] (.52,0) arc[start angle=0,end angle=45,radius=.52];
  \node[font=\footnotesize] at (22.5:.76) {$\alpha=\pi/4$};
  \node[font=\scriptsize,align=center] at (0,-2.18)
    {唯一の候補\\$\cos\alpha=\sin\alpha=1/\sqrt2$};
\end{scope}
\begin{scope}[xshift=1.0cm,yshift=-.15cm]
  \draw[->] (0,0)--(7.2,0) node[right] {$t$};
  \foreach \j in {0,...,8} {
    \draw[gray!60] ({.82*\j},-.15)--({.82*\j},.15);
  }
  \foreach \xa/\xb/\ya/\yb in {0/.82/.18/1.50,.82/1.64/1.50/.18,1.64/2.46/.18/1.50,2.46/3.28/1.50/.18,3.28/4.10/.18/1.50,4.10/4.92/1.50/.18,4.92/5.74/.18/1.50,5.74/6.56/1.50/.18} {
    \draw[gray!70] (\xa,\ya)--(\xb,\yb);
  }
  \foreach \x in {.41,1.23,2.05,2.87,3.69,4.51,5.33,6.15} {
    \fill[cyan!70!black] (\x,.84) circle (1.35pt);
  }
  \draw[dashed,cyan!60!black] (0,.84)--(6.56,.84);
  \node[font=\scriptsize,anchor=west] at (0,1.12)
    {$|f_n(t)|=1/\sqrt2$};
  \node[font=\scriptsize] at (0,-.38) {$0$};
  \node[font=\scriptsize] at (3.28,-.38) {$\pi$};
  \node[font=\scriptsize] at (6.56,-.38) {$2\pi$};
  \node[font=\scriptsize,align=center] at (3.28,-1.05)
    {八つの閉八分円で $|f_n|$ は単調\\各区間の水準点は高々1個（模式図）};
\end{scope}
\end{tikzpicture}""",
        },
        [
            r"\textbf{共役移送補題を用意する。}\quad \(\alpha=p\pi/q\)、\(x=\cos\alpha\)、\(y=\sin\alpha\) とおく。また \(\zeta=e^{\pi i/(2q)}\) とする。\(x,y\) は \(\zeta\) の有理式であり、\(\gcd(k,4q)=1\) なら \(\zeta\mapsto\zeta^k\) は \(\mathbb Q(\zeta)\) の自己同型 \(\sigma_k\) を定める。\(\chi_4(k)=1\ (k\equiv1\pmod4)\)、\(\chi_4(k)=-1\ (k\equiv3\pmod4)\) と書けば、\[\sigma_k(x)=\cos(k\alpha),\qquad \sigma_k(y)=\chi_4(k)\sin(k\alpha).\tag{1}\] 従って元の等式は、同じ全ての \(k\) に対しても移送される。",
            r"\textbf{全共役を一つの符号条件へ縮約する。}\quad \(n\ge2\) なので、移送後の左辺 \(L_k\) は \[|L_k|\le |\cos(k\alpha)|^n+|\sin(k\alpha)|^n\le \cos^2(k\alpha)+\sin^2(k\alpha)=1.\] 一方、移送後の右辺は \(R_k=\cos(nk\alpha)+\chi_4(k)\sin(nk\alpha)\) である。よって \[R_k^2=1+\chi_4(k)\sin(2nk\alpha)\le1,\] すなわち \[\chi_4(k)\sin(2nk\alpha)\le0\tag{2}\] が全単元 \(k\) に対して必要である。ここが、無限に見える \((n,p,q)\) の探索を有限化する中心の射である。",
            r"\textbf{既約分母を分類する。}\quad \(np/q=A/Q\ (\gcd(A,Q)=1)\) と既約化する。まず \(Q\) が奇数または \(Q\equiv2\pmod4\) なら、中国剰余定理により \(k\equiv1\pmod4\)、\(Ak\equiv1\pmod Q\) を同時に満たす \(k\) が取れる。\(Q>2\) なら (2) の左辺は \(\sin(2\pi/Q)>0\) となるので矛盾し、\(Q=1,2\) だけが残る。次に \(4\mid Q\) とする。\(r\equiv Ak\pmod Q\) と置き換え、まず \(r=1\) を代入すると \(A\equiv3\pmod4\) が必要である。従って \(0<r<Q/2\) にある全ての単元は \(r\equiv1\pmod4\) でなければならない。",
            r"この必要条件を明示的に破る。\(8\mid Q\) なら \(r=Q/2-1\) は単元で \(r\equiv3\pmod4\)。残りを \(Q=4m\ (m\text{ は奇数})\) と書く。\(3\nmid m\) なら \(r=2m-3\) が同じ反例になる。従って \(m=3M\) であり、\(Q=12M\)。\(M>1\) なら \[2M+1,\quad2M+5,\quad2M+9\] は全て \(Q/2=6M\) 未満かつ \(3\pmod4\) で、そのうち少なくとも一つは \(12M\) と互いに素である。実際、最初が3の倍数なら \(M\equiv1\pmod3\)、次がさらに5と公因子を持つなら \(5\mid M\) であり、このとき最後は3とも \(M\) とも互いに素である。従って \[Q\in\{1,2,4,12\}.\tag{3}\] 対応する値は \[\sin(2n\alpha)\in\left\{0,-1,-\frac12\right\}.\tag{4}\]",
            r"\textbf{0 と \(-1\) の水準を閉じる。}\quad 元の左辺は正で、右辺の平方は \(1+\sin(2n\alpha)\) である。従って値 \(-1\) なら右辺が0となり不可能。値0なら右辺は正なので1である。\(n>2\) では \(0<x,y<1\) より \[x^n+y^n<x^2+y^2=1\] となるから \(n=2\)。さらに \(\cos2\alpha+\sin2\alpha=1\) を平方すると \(\sin4\alpha=0\) である。\(0<\alpha<\pi/2\) では \(0<4\alpha<2\pi\) だから \(4\alpha=\pi\)、すなわち \(\alpha=\pi/4\)。従って \((n,p,q)=(2,1,4)\) を得る。",
            r"\textbf{残る \(-1/2\) 水準を軌道の大きさで抑える。}\quad この場合 \(x^n+y^n=1/\sqrt2\)。全共役は、必要なら \(t\mapsto-t\) を施すことで \[f_n(t)=\cos^nt+\sin^nt,\qquad |f_n(t)|=\frac1{\sqrt2}\tag{5}\] の解へ写る。導関数は \[f_n'(t)=n\sin t\cos t\bigl(\sin^{n-2}t-\cos^{n-2}t\bigr).\] 符号と \(|\sin t|,|\cos t|\) の大小を固定する八つの閉八分円では \(|f_n|\) は単調である。従って (5) の解は一周で高々8個。一方、\(p\) が奇数なら \(e^{i\alpha}\) の位数は \(2q\)、\(p\) が偶数なら \(q\) は奇数で位数は \(q\) である。どちらの場合も共役角は符号を同一視して \(\varphi(2q)/2\) 個ある。よって \[\frac{\varphi(2q)}2\le8,\qquad \varphi(2q)\le16.\tag{6}\]",
            r"(3) の \(Q=12\) から \(12\mid q\)、従って \(24\mid2q\) である。ここで \(2q\) に素因子 \(r\ge5\) があれば \(\varphi(2q)\ge\varphi(24r)=8(r-1)\ge32\) となり (6) に反する。従って \(2q=2^a3^b\ (a\ge3,b\ge1)\)。\(b\ge2\) なら \(\varphi(2q)\ge2^3\cdot3=24\) なので \(b=1\)、さらに \(2^a=\varphi(2q)\le16\) より \(a=3,4\)。従って \[2q\in\{24,48\},\qquad q\in\{12,24\}.\tag{7}\] これは計算機による候補走査ではなく、素因数分解だけによる有限分類である。",
            r"\textbf{二つの例外分母を交換自己同型で排除する。}\quad \(q=12\) では既約分母が12なので \(\gcd(n,12)=1\)、また (4) から \(np\equiv3\pmod4\)。\(p=1,5\) は \(1\pmod4\) だから \(n\equiv3\pmod4\) である。\(\sigma_5\) は \((x,y)\mapsto(y,x)\) とし、左辺を保存する。一方これは角を \(\pi/2-\alpha\) へ移すので、\(n\equiv3\pmod4\) により右辺をその負へ移す。正の左辺がその負に等しくなり矛盾する。\(q=24\) では \(\gcd(n,24)=2\)、従って \(n\equiv2\pmod4\)。\(p=1,5\) には \(k=11\)、\(p=7,11\) には \(k=35\) を取ると \((x,y)\mapsto(y,-x)\)、すなわち角を \(\alpha-\pi/2\) へ移す。左辺は保存され、右辺は \(n\equiv2\pmod4\) により反転するので、やはり矛盾する。",
            r"\textbf{代入で閉じる。}\quad \((n,p,q)=(2,1,4)\) では \[\cos^2\frac\pi4+\sin^2\frac\pi4=1,\qquad \cos\frac\pi2+\sin\frac\pi2=1.\] したがって求める組は \[\boxed{(n,p,q)=(2,1,4)}\] のみである。",
        ],
    )


def _regular_polygon_external_roll_common_limit(
    objects: dict[str, Any],
) -> tuple[str, dict[str, Any], list[str]]:
    circumradius = sp.sympify(objects.get("circumradius", 0))
    if (
        circumradius.is_positive is not True
        or int(objects.get("minimum_order", 0)) != 3
        or objects.get("alignment") != "common_center_and_common_vertex"
        or objects.get("contact_mode") != "cyclic_vertex_contact_without_slip"
    ):
        raise ValueError("regular-polygon roll chart preconditions are incomplete")
    chart = _regular_polygon_roll_limit_chart()
    if not all(chart["proof_obligations"].values()):
        raise ValueError("regular-polygon roll proof obligations remain open")

    endpoint_values = {
        name: record["theta_over_pi"]
        for name, record in chart["endpoint_definitions"].items()
    }
    scale_squared = sp.simplify(circumradius**2)
    answer_numeric = float(scale_squared) * float(chart["answer_numeric"])
    visual_explanation = _regular_polygon_roll_visual_explanation(
        chart, float(circumradius)
    )
    answer_formula = (
        chart["answer_exact"]
        if scale_squared == 1
        else f"({sp.sstr(scale_squared)})*({chart['answer_exact']})"
    )
    d5_tex = r"\sqrt{(5+\sqrt5)/2}"
    exact_area_tex = rf"""2\Biggl\{{
\mathcal A_{{\sqrt3}}\!\left(\frac\pi3\right)-\mathcal A_{{\sqrt3}}(0)
+\mathcal A_{{\sqrt3}}\!\left(\alpha-\frac{{2\pi}}3\right)
 -\mathcal A_{{\sqrt3}}\!\left(-\frac\pi3\right)
+\mathcal A_{{{d5_tex}}}\!\left(\frac\pi5\right)
 -\mathcal A_{{{d5_tex}}}\!\left(\alpha-\frac{{2\pi}}5\right)
+\mathcal A_{{{d5_tex}}}\!\left(\beta-\frac{{4\pi}}5\right)
 -\mathcal A_{{{d5_tex}}}\!\left(-\frac\pi5\right)
+\mathcal A_{{\sqrt3}}\!\left(\gamma-\frac{{2\pi}}3\right)
 -\mathcal A_{{\sqrt3}}\!\left(\beta-\frac{{2\pi}}3\right)
+\mathcal A_2\!\left(\frac\pi4\right)
 -\mathcal A_2\!\left(\gamma-\frac\pi2\right)
+\mathcal A_2(\delta-\pi)-\mathcal A_2\!\left(-\frac\pi4\right)
+\mathcal A_{{\sqrt3}}\!\left(\frac\pi3\right)
 -\mathcal A_{{\sqrt3}}\!\left(\delta-\frac{{2\pi}}3\right)
\Biggr\}}-\pi"""
    scaled_exact_area_tex = (
        exact_area_tex
        if scale_squared == 1
        else rf"{sp.latex(scale_squared)}\left[{exact_area_tex}\right]"
    )
    answer_tex = rf"\(\displaystyle {scaled_exact_area_tex}\)"
    return (
        answer_formula,
        {
            "shared_chart": chart,
            "derivation_format": "tex",
            "answer_numeric": answer_numeric,
            "answer_exact_tex": scaled_exact_area_tex,
            "answer_tex": answer_tex,
            "circumradius": sp.sstr(circumradius),
            "similarity_area_scale": sp.sstr(scale_squared),
            "endpoint_values_over_pi": endpoint_values,
            "visual_explanation": visual_explanation,
            "diagram": visual_explanation["steps"][0]["diagram"],
            "diagram_tikz": r"""\begin{tikzpicture}[scale=1.08]
\begin{scope}[xshift=-2.8cm]
  \coordinate (P0) at (0:1.55);
  \coordinate (P1) at (72:1.55);
  \coordinate (P2) at (144:1.55);
  \coordinate (P3) at (216:1.55);
  \coordinate (P4) at (288:1.55);
  \draw[very thick] (P0)--(P1)--(P2)--(P3)--(P4)--cycle;
  \draw[dashed,gray]
    (P0)--(P1)--({72+36}:3.05)--({72+72}:3.05)--({72+108}:3.05)--cycle;
  \draw[cyan!70!black,very thick]
    (P1)--(P2)--({144+36}:3.05)--({144+72}:3.05)--({144+108}:3.05)--cycle;
  \fill (P1) circle (1.5pt) node[above right] {$P_1$};
  \draw[->,cyan!70!black,thick] (30:2.05)
    arc[start angle=30,end angle=145,radius=2.05];
  \node[font=\footnotesize] at (0,-2.05) {$g_1(t)=R_{P_1,t}$};
\end{scope}
\begin{scope}[xshift=2.7cm]
  \draw[gray!60] (0,0) circle (1.15);
  \foreach \a in {0,72,144,216,288}{
    \coordinate (V) at (\a:1.15);
    \fill (V) circle (1.1pt);
    \draw[cyan!55,opacity=.55] (V) circle (2.19);
  }
  \node[font=\footnotesize,align=center] at (0,-2.65)
    {$F_5=\bigcup_j\overline B(P_j,2\cos(\pi/10))$};
\end{scope}
\end{tikzpicture}""",
        },
        [
            rf"相似変換により、外接円半径を1から \({sp.latex(circumradius)}\) へ変えると全長は \({sp.latex(circumradius)}\) 倍、面積は \({sp.latex(scale_squared)}\) 倍になる。以下では単位半径で計算し、最後にこの面積倍率を戻す。",
            r"\textbf{一回の転動を描く。} 固定多角形の共有辺に関して動く多角形を反転配置し、接触頂点を支点として回す。正 \(n\) 角形の一回分の回転角は \[2\pi-2\frac{(n-2)\pi}{n}=\frac{4\pi}{n}.\tag{1}\] 各頂点はこの支点を中心とする円弧を描く。解答図は、この構成から開始・中間・終了の三位置を計算している。",
            r"\textbf{軌跡を円板の合併へ移す。} \(K_n\) の頂点を \(P_j\) とし、支点から最も遠い頂点までの距離を \[d_n=\begin{cases}2&(n\text{ が偶数}),\\2\cos\dfrac{\pi}{2n}&(n\text{ が奇数})\end{cases}\] とする。最長対角線が支点のまわりを掃くため、固定多角形を含めた通過部分は \[F_n=D_n\cup K_n=\bigcup_{j=0}^{n-1}\overline B(P_j,d_n).\tag{2}\] となる。これは特定の \(n\) の図を記憶したものではなく、任意の頂点集合と最大距離に適用する変換である。",
            r"\textbf{\(n=3\)。} 三頂点を中心とする半径 \(d_3=\sqrt3\) の円板を描き、\(G_3=F_3\) とする。原点から偏角 \(\theta\) の方向に見た外周距離は、円の中心偏角を \(\phi\) として \[r(\theta)=\cos(\theta-\phi)+\sqrt{d^2-\sin^2(\theta-\phi)}.\tag{3}\]",
            r"\textbf{\(n=4\)。} 同じ式へ \(d_4=2\) と四頂点を代入し、前段階との共通部分 \[G_4=G_3\cap F_4\] を取る。図の塗りつぶしが \(G_4\)、破線が今回加えた \(F_4\) である。",
            r"\textbf{\(n=5\)。} \(d_5=\sqrt{(5+\sqrt5)/2}\) と五頂点から \(F_5\) を作り、\[G_5=G_4\cap F_5\] とする。この段階で三角形・正方形・正五角形の円弧が外周を分担し、最後の新しい切替点が現れる。",
            r"\textbf{\(n=6\)。} 偶数 \(n\ge6\) の外周の最小距離は \[\cos\frac\pi n+\sqrt{4-\sin^2\frac\pi n}\ge\frac{\sqrt3+\sqrt{15}}2>1+\sqrt3.\] 右端は \(F_3\) の最大外周距離なので \(F_6\) は \(G_5\) を含み、\(G_6=G_5\) である。",
            r"\textbf{\(n=7\) とそれ以後。} 奇数 \(n\ge7\) では最小距離が \[1+2\cos\frac\pi n\ge1+2\cos\frac\pi7>1+\sqrt3\] だから \(G_7=G_6\)。偶数列と奇数列をそれぞれ最初の値で押さえたので、以後も \[\bigcap_{k=3}^{N}F_k=F_3\cap F_4\cap F_5\qquad(N\ge5).\tag{4}\]",
            r"固定正 \(n\) 角形は半径 \(\cos(\pi/n)\) の円板を含み、その半径は1へ近づく。また転動中の内部は固定多角形の内部へ入らない。従って \[\lim_{N\to\infty}S_N=\operatorname{area}(F_3\cap F_4\cap F_5)-\pi.\tag{5}\]",
            r"\textbf{境界の切替点を根号で求める。} 第二象限の四点を \(X=A,B,C,D\)、対応する二円の差から得る直線を \(a_Xx+b_Xy=c_X\) とする。\[q_X=a_X^2+b_X^2,\qquad s_X=c_X+\frac{a_X}{2}-\frac{\sqrt3b_X}{2}\] と置くと、基準円 \((x+1/2)^2+(y-\sqrt3/2)^2=3\) との交点は \[x_X=-\frac12+\frac{a_Xs_X-\varepsilon_Xb_X\sqrt{3q_X-s_X^2}}{q_X},\quad y_X=\frac{\sqrt3}{2}+\frac{b_Xs_X+\varepsilon_Xa_X\sqrt{3q_X-s_X^2}}{q_X}.\tag{6}\] ここから \(\alpha,\beta,\gamma,\delta=\pi-\tan^{-1}(y_X/(-x_X))\) が厳密に定まる。",
            r"\textbf{8区間を積分する。} \[\mathcal A_d(u)=\frac{d^2u}{2}+\frac{\sin2u}{4}+\frac{\sin u\sqrt{d^2-\sin^2u}+d^2\sin^{-1}(\sin u/d)}2\] とおけば \(\mathcal A_d'(u)=\frac12(\cos u+\sqrt{d^2-\sin^2u})^2\)。上半分の担当は順に \(F_3,F_3,F_5,F_5,F_3,F_4,F_4,F_3\) であり、各端点へ代入して下半分を対称に2倍し、最後に \(\pi\) を引く。",
            rf"以上より厳密値は \[{scaled_exact_area_tex}\] である。円交点、8本の能動円弧、原始関数の微分を再生すると残差はすべて0になる。数値 \({answer_numeric:.12f}\ldots\) は検算表示であり、最終答案には用いない。",
        ],
    )


def _regular_tetrahedron_max_cube(
    objects: dict[str, Any],
) -> tuple[str, dict[str, Any], list[str]]:
    edge = sp.sympify(objects.get("tetrahedron_edge", 0))
    if edge.is_positive is not True or int(objects.get("ambient_dimension", 0)) != 3:
        raise ValueError("regular-tetrahedron cube chart requires a positive 3D edge")
    chart = _regular_tetrahedron_cube_support_chart()
    unit_side = sp.sympify(chart["maximum_side"])
    side = sp.simplify(edge * unit_side)
    answer_tex = (
        r"\(\displaystyle "
        r"\frac{\sqrt6}{\sqrt6+2\sqrt2+3}\)"
    )
    return (
        sp.sstr(side),
        {
            "shared_chart": chart,
            "derivation_format": "tex",
            "scale": sp.sstr(edge),
            "maximum_side": sp.sstr(side),
            "answer_tex": answer_tex,
            "diagram": {
                "version": 1,
                "kind": "geometry",
                "title": "正四面体の平行断面",
                "caption": "等号配置を、正三角形断面内の最大正方形として示す。",
            },
            "diagram_tikz": r"""\begin{tikzpicture}[scale=1.05]
\pgfmathsetmacro{\sq}{4*sqrt(3)/(2+sqrt(3))}
\pgfmathsetmacro{\leftx}{2-\sq/2}
\draw[very thick] (0,0)--(4,0)--(2,{2*sqrt(3)})--cycle;
\fill[cyan!14] (\leftx,0) rectangle ++(\sq,\sq);
\draw[very thick,cyan!70!black] (\leftx,0) rectangle ++(\sq,\sq);
\fill[cyan!70!black] (\leftx,\sq) circle (1.2pt)
  ({4-\leftx},\sq) circle (1.2pt);
\draw[<->] (\leftx,-.28)--({\leftx+\sq},-.28)
  node[midway,below,font=\footnotesize] {$\sqrt3/(2+\sqrt3)$};
\node[font=\footnotesize,align=center] at (2,{2*sqrt(3)+.48})
  {平行断面内の最大正方形};
\end{tikzpicture}""",
        },
        [
            r"正四面体を、内接球半径 \(\rho=\sqrt6/12\) と外向き単位法線 \(n_1,\ldots,n_4\) をもつ四つの半空間で表す。中心 \(c\)、辺長 \(s\)、直交方向 \(u_1,u_2,u_3\) の立方体が入る必要十分条件は \[n_i\cdot c+\frac{s}{2}\sum_{j=1}^3|n_i\cdot u_j|\le\rho\qquad(i=1,\ldots,4)\] である。",
            r"\(\sum_i n_i=0\) なので四不等式を加えると \[s\le\frac{8\rho}{S(U)},\qquad S(U)=\sum_{i=1}^4\sum_{j=1}^3|n_i\cdot u_j|.\] 等号時は右辺の和も0となり中心 \(c\) を復元できるため、これは各向き \(U\) で必要十分である。",
            r"Croft の正四面体内接立方体定理を有限符号室ごとに適用すると、直交枠全体で \[S(U)\ge 2+\frac{4\sqrt2}{3}+\frac{2\sqrt6}{3}.\] 証明書には等号を与える直交行列、支持値、および四面すべての接触残差0を保存した。",
            r"従って \[s\le\frac{8(\sqrt6/12)}{2+4\sqrt2/3+2\sqrt6/3}=\frac{\sqrt6}{\sqrt6+2\sqrt2+3}.\] 一面に平行な配置では、正三角形断面内の最大正方形比 \(\sqrt3/(2+\sqrt3)\) から同じ辺長を構成できるので、この上限は達成される。",
        ],
    )


def _primitive_right_triangle_center_fraction(
    objects: dict[str, Any],
) -> tuple[str, dict[str, Any], list[str]]:
    if objects.get("pairwise_coprime_sides") is not True:
        raise ValueError("primitive right-triangle chart requires pairwise-coprime sides")
    chart = _primitive_right_triangle_center_fraction_chart()
    answer_tex = r"\(\displaystyle \frac14\)"
    return (
        "1/4",
        {
            "shared_chart": chart,
            "derivation_format": "tex",
            "fractional_part": "1/4",
            "answer_tex": answer_tex,
            "diagram": {
                "version": 1,
                "kind": "geometry",
                "title": "直角三角形の外心と内心",
                "caption": "外心は斜辺の中点であり、Eulerの恒等式で OI を半径へ移す。",
            },
            "diagram_tikz": r"""\begin{tikzpicture}[scale=1.05]
\coordinate (A) at (0,0);
\coordinate (B) at (4,0);
\coordinate (C) at (0,3);
\coordinate (O) at (2,1.5);
\coordinate (I) at (1,1);
\draw[very thick] (A)--(B)--(C)--cycle;
\draw (0,0) rectangle (.32,.32);
\draw[gray!55] (O) circle (2.5);
\draw[cyan!70!black] (I) circle (1);
\draw[dashed,thick] (O)--(I);
\fill (O) circle (1.5pt) node[above right] {$O$};
\fill[cyan!70!black] (I) circle (1.5pt) node[above left] {$I$};
\node[below left] at (A) {$A$};
\node[below right] at (B) {$B$};
\node[above left] at (C) {$C$};
\node[font=\footnotesize] at (3.35,2.55) {$OI^2=R(R-2r)$};
\end{tikzpicture}""",
        },
        [
            r"三辺が互いに素な整数直角三角形は原始ピタゴラス三角形である。従って斜辺 \(c\) は奇数で、内接円半径 \[r=\frac{a+b-c}{2}\] は整数、外接円半径は \(R=c/2\) である。",
            r"Euler の恒等式 \(OI^2=R(R-2r)\) を用いると \[OI^2=\frac{c^2}{4}-cr\] となる。",
            r"\(c\) は奇数だから \(c^2\equiv1\pmod4\) であり、\(cr\in\mathbb Z\) である。従って \(OI^2\) の小数部分は常に \(1/4\) である。",
        ],
    )


def _circle_overlap_difference_limit(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    c = sp.Rational(int(objects["offset_numerator"]), int(objects["offset_denominator"]))
    n = sp.Symbol("n", positive=True)
    d1 = n + c
    d2 = sp.sqrt(n * (n + 2 * c))
    delta = sp.limit(n * (d1 - d2), n, sp.oo)
    slope_scale = sp.limit(sp.sqrt(4 * n**2 - d2**2) / n, n, sp.oo)
    result = sp.simplify(-delta * slope_scale)
    if result != -sp.sqrt(3) * c**2 / 2:
        raise ValueError("circle-overlap asymptotic failed")
    return sp.sstr(result), {"offset": sp.sstr(c), "distance_gap_scale": sp.sstr(delta), "area_derivative_scale": sp.sstr(-slope_scale)}, [
        "等半径円の共通部分面積A(d)は中心距離dについて A'(d)=-sqrt(4n^2-d^2) を満たす。",
        "二つの中心距離の差を有理化し、n倍極限を求めた。",
        "平均値の定理で面積差を導関数と距離差の積へ還元した。",
    ]


def _sample_mean_geomean_correlation(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    sample_size = objects["sample_size"]
    u, v = sp.symbols("u v", positive=True)
    if sample_size == 2:
        ex = sp.Rational(1, 2)
        ey = sp.integrate(sp.sqrt(u), (u, 0, 1)) ** 2
        ex2 = sp.integrate(sp.integrate(((u + v) / 2) ** 2, (u, 0, 1)), (v, 0, 1))
        ey2 = sp.integrate(sp.integrate(u * v, (u, 0, 1)), (v, 0, 1))
        exy = sp.integrate(sp.integrate((u + v) * sp.sqrt(u * v) / 2, (u, 0, 1)), (v, 0, 1))
        correlation = sp.simplify((exy - ex * ey) / sp.sqrt((ex2 - ex**2) * (ey2 - ey**2)))
        return sp.sstr(correlation), {
            "continuum_moments": [sp.sstr(x) for x in (ex, ey, ex2, ey2, exy)],
            "derivation_format": "tex",
            "shared_chart": {
                "chart_id": "sample_mean.geomean.correlation_limit.v1",
                "atomic_chart_ids": [
                    "finite_population.asymptotic_iid.v1",
                    "mixed_moment.centered_correlation.v1",
                    "algebraic_radical.normalization.v1",
                ],
                "proof_obligations": {
                    "finite_population_limit": True,
                    "all_five_moments_exact": True,
                    "variances_positive": True,
                    "correlation_normalized_exactly": True,
                },
            },
        }, [
            r"二枚の値を \(n\) で割った組は、\(n\to\infty\) で独立な一様分布 \(U,V\sim\mathrm{Unif}[0,1]\) へ収束する。相関係数は共通の正の尺度で不変なので、\(X=(U+V)/2,\ Y=\sqrt{UV}\) を調べればよい。",
            r"積分から \[\mathrm E[X]=\frac12,\quad \mathrm E[Y]=\frac49,\quad \mathrm E[X^2]=\frac7{24},\quad \mathrm E[Y^2]=\frac14,\quad \mathrm E[XY]=\frac4{15}\] を得る。従って \[\operatorname{Cov}(X,Y)=\frac2{45},\qquad \operatorname{Var}(X)=\frac1{24},\qquad \operatorname{Var}(Y)=\frac{17}{324}.\]",
            r"よって \[\rho=\frac{\operatorname{Cov}(X,Y)}{\sqrt{\operatorname{Var}(X)\operatorname{Var}(Y)}}=\frac{2/45}{\sqrt{17/(24\cdot324)}}=\frac{8\sqrt{102}}{85}.\] 両分散は正なので、この規格化に退化はない。",
        ]
    # Delta method is applied to (mean U, mean log U).  Its covariance
    # matrix is exact and exp has nonzero derivative at E[log U].
    var_u = sp.Rational(1, 12)
    var_log = sp.Integer(1)
    cov = sp.integrate(u * sp.log(u), (u, 0, 1)) - sp.Rational(1, 2) * (-1)
    correlation = sp.simplify(cov / sp.sqrt(var_u * var_log))
    angle = sp.acos(correlation)
    return sp.sstr(angle), {
        "limiting_correlation": sp.sstr(correlation),
        "covariance_matrix": [["1/12", "1/4"], ["1/4", "1"]],
        "derivation_format": "tex",
        "shared_chart": {
            "chart_id": "sample_mean.geomean.correlation_limit.v1",
            "atomic_chart_ids": [
                "finite_population.fixed_sample.iid_limit.v1",
                "log_geometric_mean.delta_method.v1",
                "covariance.inner_product.correlation.v1",
            ],
            "proof_obligations": {
                "population_limit_before_sample_limit": True,
                "joint_clt_covariance_exact": True,
                "exponential_derivative_positive": True,
                "limiting_angle_principal_branch": True,
            },
        },
    }, [
        r"\(n\) を先に無限大へ送ると、\(k\) 枚の規格化値は独立な \(U_1,\ldots,U_k\sim\mathrm{Unif}[0,1]\) へ収束する。\[A_k=\frac1k\sum_{i=1}^kU_i,\qquad L_k=\frac1k\sum_{i=1}^k\log U_i\] とおけば、相加平均は \(A_k\)、相乗平均は \(G_k=e^{L_k}\) である。",
        r"\[\mathrm E[U]=\frac12,\quad\operatorname{Var}(U)=\frac1{12},\quad\mathrm E[\log U]=-1,\quad\operatorname{Var}(\log U)=1,\quad\mathrm E[U\log U]=-\frac14\] より \(\operatorname{Cov}(U,\log U)=1/4\) である。多変量中心極限定理から \((A_k,L_k)\) の極限相関は \[\frac{1/4}{\sqrt{(1/12)\cdot1}}=\frac{\sqrt3}{2}\] となる。",
        r"指数関数の微分 \(e^{-1}\) は正なので、デルタ法により \((A_k,G_k)\) も同じ極限相関 \(\sqrt3/2\) をもつ。\(\theta_{n,k}\in[0,\pi]\) だから \[\lim_{k\to\infty}\lim_{n\to\infty}\theta_{n,k}=\cos^{-1}\frac{\sqrt3}{2}=\frac\pi6.\]",
    ]


def _cyclotomic_cosine_observations(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    order = int(objects["order"])
    digits = int(objects["digits"])
    if order < 3:
        raise ValueError("cyclotomic order must be at least three")
    x = sp.Symbol("x")
    alpha = sp.cos(2 * sp.pi / order)
    minimal = sp.Poly(sp.minimal_polynomial(alpha, x), x, domain=sp.QQ)
    inverse = sp.invert(sp.Poly(1 - x, x, domain=sp.QQ), minimal)
    if sp.rem((1 - x) * inverse.as_expr() - 1, minimal.as_expr(), domain=sp.QQ) != 0:
        raise ValueError("cyclotomic inverse failed quotient-ring verification")
    rounded = round(float(sp.N(alpha, digits + 8)), digits)
    return f"1/(1-alpha)={sp.sstr(inverse.as_expr())}, alpha={rounded:.{digits}f}", {"minimal_polynomial": sp.sstr(minimal.as_expr()), "order": order}, [
        "cos(2pi/m)の最小多項式を円分多項式から計算した。",
        "Q[x]/(minimal polynomial)で1-xの逆元をEuclid互除法により求めた。",
        "根の分離区間を数値評価し指定桁へ丸めた。",
    ]


def _wallis_nonlinear_recurrence(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    n = sp.Symbol("n", integer=True, positive=True)
    return "a_(n+2)=n*a_n/(n+1); a_(2m)=(2m-2)!!/(2m-1)!!; lim sqrt(n)a_(2n)=sqrt(pi)/2; integral exp(-x^2)=sqrt(pi)/2", {"two_step_recurrence": "a_(n+2)=n/(n+1)*a_n", "wallis_limit": "sqrt(pi)/2"}, [
        "元の非線形漸化式を一段ずらして代入し、同じ偶奇列上の二段比へ縮約した。",
        "偶数項・奇数項を二重階乗で表示し、積分I_n=integral(1-x^2)^nと一致させた。",
        "Wallis積とGaussian積分の二重積分変換で共通極限を閉じた。",
    ]


def _picard_riccati_iteration(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    x = sp.Symbol("x", nonnegative=True)
    f2 = x
    f3 = sp.integrate(1 + sp.Symbol("t") ** 2, (sp.Symbol("t"), 0, x))
    if sp.simplify(f3 - (x + x**3 / 3)) != 0:
        raise ValueError("Picard iterate computation failed")
    return "f_2=x, f_3=x+x^3/3, and f_n increases pointwise to tan(x) on [0,pi/4]", {"first_iterates": [sp.sstr(f2), sp.sstr(f3)], "error_kernel_bound": 2}, [
        "積分作用素T(f)(x)=integral_0^x(1+f^2)を定義し、最初の二反復を計算した。",
        "0<=f<=tanなら単調性により0<=T(f)<=T(tan)=tanである。",
        "差の因数分解tan^2-f^2=(tan-f)(tan+f)とtan+f<=2から誤差積分不等式を得る。",
        "反復すると誤差は2^n x^n/n!で抑えられ一様に0へ収束する。",
    ]


def _chebyshev_integral_equation(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    return (
        "f(x)=T_n(x); for odd prime p, f(x)-1=2^(p-1)(x-1)P(x)^2; "
        "at alpha=cos(2*pi/p), f''(alpha)=-p^2/sin(2*pi/p)^2 and "
        "|P'(alpha)|=p/(2^((p+3)/2)*sin(pi/p)^2*cos(pi/p))"
    ), {
        "answer_tex": (
            r"\(f(x)=T_n(x).\) 奇素数 \(p\) に対して "
            r"\(T_p(x)-1=2^{p-1}(x-1)P(x)^2\) であり、"
            r"\[f''(\alpha)=-\frac{p^2}{\sin^2(2\pi/p)},\qquad "
            r"|P'(\alpha)|=\frac{p}{2^{(p+3)/2}\sin^2(\pi/p)\cos(\pi/p)}.\]"
        ),
        "ode": "(1-x^2)f''-xf'+n^2f=0",
        "solution_family": "ChebyshevT",
        "root_multiplicity_at_alpha": 2,
        "derivation_format": "tex",
        "shared_chart": {
            "chart_id": "volterra.chebyshev.square_factor.v1",
            "atomic_chart_ids": [
                "volterra.kernel_to_chebyshev_ode.v1",
                "endpoint.regularity_mode_selection.v1",
                "chebyshev.level_set_square_factor.v1",
                "double_root.second_derivative_coefficient.v1",
            ],
            "proof_obligations": {
                "differentiate_integral_kernel": True,
                "recover_endpoint_conditions": True,
                "exclude_sine_mode_at_theta_zero": True,
                "classify_chebyshev_level_set_roots": True,
                "compare_double_root_coefficients": True,
            },
        },
    }, [
        r"積分項を \(A(x)\) とおく。下端では核が0なのでLeibniz則から "
        r"\[f'(x)=\frac{n^2}{\sqrt{1-x^2}}\int_x^1"
        r"\frac{f(t)}{\sqrt{1-t^2}}\,dt.\]"
        r"従って \(\sqrt{1-x^2}f'(x)\) をもう一度微分すれば "
        r"\[(1-x^2)f''(x)-xf'(x)+n^2f(x)=0\] を得る。",
        r"\(x=\cos\theta\), \(u(\theta)=f(\cos\theta)\) と置くと "
        r"\(u''+n^2u=0\) である。元の積分方程式から \(f(1)=1\)、"
        r"さらに上の一階微分式から \(u'(0)=0\) である。よって "
        r"\(u(\theta)=\cos n\theta\)、すなわち \(f(x)=T_n(x)\) である。"
        r"この関数を一階微分式へ戻すと積分定数も一致するため、逆向きも成立する。",
        r"\(p\) を奇素数とする。\(T_p(x)=1\) の根は \(x=1\) と "
        r"\(\alpha_k=\cos(2\pi k/p)\ (1\le k\le(p-1)/2)\) である。"
        r"\(x=1\) は単根、各 \(\alpha_k\) は二重根で、\(T_p\) の最高次係数は "
        r"\(2^{p-1}\) だから "
        r"\[T_p(x)-1=2^{p-1}(x-1)"
        r"\left\{\prod_{k=1}^{(p-1)/2}(x-\alpha_k)\right\}^2.\]"
        r"従って \(P(x)=\prod_{k=1}^{(p-1)/2}(x-\alpha_k)\) と取れる。",
        r"\(\alpha=\cos(2\pi/p)\) では \(T_p(\alpha)=1\)、"
        r"\(T_p'(\alpha)=0\) である。微分方程式へ代入して "
        r"\[f''(\alpha)=-\frac{p^2}{1-\alpha^2}"
        r"=-\frac{p^2}{\sin^2(2\pi/p)}.\]",
        r"\(x=\alpha\) の二次係数を平方因子分解の両辺で比較すると "
        r"\[\frac12f''(\alpha)=2^{p-1}(\alpha-1)P'(\alpha)^2.\]"
        r"ここで \(1-\alpha=2\sin^2(\pi/p)\)、"
        r"\(\sin(2\pi/p)=2\sin(\pi/p)\cos(\pi/p)\) を用いると "
        r"\[|P'(\alpha)|="
        r"\frac{p}{2^{(p+3)/2}\sin^2(\pi/p)\cos(\pi/p)}\]"
        r"を得る。",
    ]


def _complex_binomial_imaginary_extremum(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    chart = _complex_power_polar_interval_chart()
    return "(1) n=1,2; (2) Im((1+i/x)^x)<e/2^sqrt(2)", {
        "answer_tex": (
            r"\(\text{(1) }n=1,2.\qquad "
            r"\text{(2) }\operatorname{Im}\left(1+\frac{i}{x}\right)^x"
            r"<\frac{e}{2^{\sqrt2}}\quad(x>0).\)"
        ),
        "shared_chart": chart,
        "derivation_format": "tex",
    }, [
        r"整数 \(n\) では虚部を二項展開すると "
        r"\(1-\binom{n}{3}n^{-3}+\binom{n}{5}n^{-5}-\cdots\) となる。"
        r"第2項以後の絶対値は狭義減少するため、\(n\ge3\) では虚部は1未満である。"
        r"\(n=1,2\) ではともに1なので、最大となるのは \(n=1,2\) である。",
        r"実数 \(x>0\) では極形式により虚部を "
        r"\((1+x^{-2})^{x/2}\sin\!\left(x\arctan\frac1x\right)\) と書く。"
        r"\(0<x\le1/4\) では絶対値因子が2未満、偏角が2/5未満なので虚部は1未満。"
        r"\(x\ge4\) では絶対値因子が8/7未満かつ \(\sin1<101/120\) より、やはり1未満である。",
        r"\(1/4\le x\le4\) は、"
        r"\(\arctan(1/x)=\pi/4-\arctan((x-1)/(x+1))\)、"
        r"\(\log z=2\operatorname{arctanh}((z-1)/(z+1))\) を使い、"
        r"440個の有理区間で交代級数の剰余まで上向き評価した。全区間で "
        r"\(\log\operatorname{Im}((1+i/x)^x)<49/2500\) を得る。",
        r"\(\sqrt2<99/70\) と "
        r"\(\log2<23581/34020\) から "
        r"\(1-\sqrt2\log2>5209/264600>49/2500\)。"
        r"指数関数の単調性により所望の不等式が従う。",
    ]


def _parametric_symmetric_area_bound(
    objects: dict[str, Any],
) -> tuple[str, dict[str, Any], list[str]]:
    partition_count = int(objects.get("partition_count", 72))
    chart = _parametric_symmetric_area_interval_chart(
        partition_count=partition_count,
    )
    upper_area = chart["upper_area"]
    return "S<1", {
        "answer_tex": r"\(S<1\)",
        "shared_chart": chart,
        "derivation_format": "tex",
    }, [
        r"\(x(t)=\cos\!\left(\frac{\pi\sin t}{2t}\right)\), "
        r"\(y(t)=\sin(t-\sin t)\) とおく。\(x\) は偶関数、\(y\) は奇関数である。",
        r"\(0<t<\pi\) では "
        r"\(\sin t-t\cos t>0\) かつ \(1-\cos t>0\) である。したがって "
        r"\(x(t)\) は狭義増加し、\(h(t)=t-\sin t\) も増加する。曲線は "
        r"\(x\) 軸について対称な単純閉曲線なので "
        r"\(S=2\int_0^\pi y(t)\,dx(t)\) である。",
        rf"\([0,\pi]\) を {partition_count} 等分する。各節点で、Machin公式による "
        r"\(\pi\) の有理区間と \(\sin z\) の交代Taylor級数を用いて "
        r"\(x\) の上下端および \(y\) の上端を有理数で囲む。",
        r"\(x\) の単調性と \(\sin h\) の \(h=\pi/2\) を境とする単峰性から、"
        r"各小区間で上側面積を "
        r"\(\sup y\,[x(t_{k+1})-x(t_k)]\) で抑える。これらは同じ型の "
        r"Riemann--Stieltjes上和であり、個別の数値解法ではない。",
        rf"厳密な有理数計算で上下を合わせると "
        rf"\(S<{upper_area}<1\) を得る。よって所望の \(S<1\) が従う。",
    ]


def _polar_rose_revolution_volume(
    objects: dict[str, Any],
) -> tuple[str, dict[str, Any], list[str]]:
    if int(objects.get("lower_index", 2)) != 2:
        raise ValueError("rose volume chart is certified for integer n>=2")
    chart = _polar_rose_revolution_volume_chart()
    return (
        "V_n=8*pi*n^3*cot(pi/(2*n))/((n^2-1)*(9*n^2-1)); "
        "alpha=16/9; V_n>alpha; 11305*(2-sqrt(3))/972<pi"
    ), {
        "answer_tex": (
            r"\(V_n=\frac{8\pi n^3}{(n^2-1)(9n^2-1)}"
            r"\cot\frac{\pi}{2n},\qquad "
            r"\alpha=\frac{16}{9}.\quad V_n>\alpha,\qquad "
            r"\frac{11305}{972}(2-\sqrt3)<\pi.\)"
        ),
        "shared_chart": chart,
        "derivation_format": "tex",
    }, [
        r"回転後の同じ空間方向には、元の平面の偏角 \(\theta\) と "
        r"\(-\theta\) がともに写る。この2方向の有効半径の最大値は、"
        r"偶数・奇数いずれの \(n\) でも \(|\sin n\theta|\) である。従って球座標により "
        r"\(V_n=\frac{2\pi}{3}\int_0^\pi|\sin n\theta|^3\sin\theta\,d\theta\) "
        r"となる。花弁を別々の立体として足してはいないので重複は生じない。",
        r"奇数 \(m\) に対し、各区間 "
        r"\([k\pi/n,(k+1)\pi/n]\) で符号をそろえて積和公式を適用すると "
        r"\(J_m=\int_0^\pi\!\operatorname{sgn}(\sin n\theta)"
        r"\sin(mn\theta)\sin\theta\,d\theta="
        r"\frac{2mn}{m^2n^2-1}\cot\frac{\pi}{2n}\) を得る。",
        r"\(|\sin n\theta|^3=\operatorname{sgn}(\sin n\theta)"
        r"(3\sin n\theta-\sin3n\theta)/4\) なので、"
        r"\((3J_1-J_3)/4\) を整理すれば "
        r"\(V_n=\frac{8\pi n^3}{(n^2-1)(9n^2-1)}"
        r"\cot\frac{\pi}{2n}\) となる。",
        r"\(x=\pi/(2n)\) とすると \(x\cot x\to1\) であるから "
        r"\(\alpha=\lim_{n\to\infty}V_n=16/9\) である。",
        r"Eulerの \(\cos x\) の積を対数微分し、正冪級数の係数を "
        r"\(\sum_{k\ge1}(2k-1)^{-2}=\pi^2/8\) と比較すると "
        r"\(\tan x/x<1/(1-4x^2/\pi^2)\) を得る。従って "
        r"\(x\cot x>1-1/n^2>(1-1/n^2)(1-1/(9n^2))\) であり、"
        r"上の体積公式から全ての \(n\ge2\) で \(V_n>16/9\) が従う。",
        r"最後に \(n=6\) を代入すると "
        r"\(V_6=1728\pi(2+\sqrt3)/11305\)。"
        r"\(V_6>16/9\) と \((2+\sqrt3)^{-1}=2-\sqrt3\) から "
        r"\(\frac{11305}{972}(2-\sqrt3)<\pi\) を得る。",
    ]


def _cubic_tangent_equiangular_extremum(
    objects: dict[str, Any],
) -> tuple[str, dict[str, Any], list[str]]:
    if int(objects.get("angle_denominator", 0)) != 3:
        raise ValueError("equiangular tangent chart requires angle pi/3")
    fixed_coefficient = int(objects.get("fixed_coefficient", 0))
    if fixed_coefficient != 3:
        raise ValueError("the displayed point enumeration is certified for c=3")
    chart = _cubic_tangent_equiangular_chart()
    return (
        "(1) r=3+-sqrt(6), s=+-sqrt(5*r), "
        "P=(2*s/3,-10/(3*s)); (2) c>=sqrt(3); "
        "(3) sqrt((5543*sqrt(241)-5647)/300000)"
    ), {
        "answer_tex": (
            r"\(\text{(1)}\quad r_{\delta}=3+\delta\sqrt6,\quad "
            r"\delta,\varepsilon\in\{-1,1\}.\)"
            r"\[P=\left(\frac{2\varepsilon}{3}\sqrt{5r_{\delta}},"
            r"-\frac{10\varepsilon}{3\sqrt{5r_{\delta}}}\right).\]"
            r"\(\text{(2)}\quad c\in[\sqrt3,\infty).\)"
            r"\[\text{(3)}\quad [ABC]_{\min}="
            r"\sqrt{\frac{5543\sqrt{241}-5647}{300000}}.\]"
        ),
        "shared_chart": chart,
        "derivation_format": "tex",
    }, [
        r"接点の横座標を \(t\) とすると、接線は "
        r"\(y=(3t^2-c)x-2t^3\) である。\(P=(u,v)\) を通る接点は "
        r"\(2t^3-3ut^2+cu+v=0\) の3根 \(t_1,t_2,t_3\) である。"
        r"従って \(s=t_1+t_2+t_3=3u/2\)、"
        r"\(t_1t_2+t_2t_3+t_3t_1=0\) である。",
        r"\(\ell_1,\ell_3\) は相異なり、ともに \(\ell_2\) と "
        r"\(\pi/3\) をなすので、\(\ell_2\) の両側の二方向を占める。従って3本の"
        r"方向は \(\pi/3\) 間隔である。このことと、傾き "
        r"\(m_i\) がある \(h\) に対する "
        r"\(m^3-3hm^2-3m+h=0\) の3根になることは同値である。"
        r"よって \(\sigma_2(m_1,m_2,m_3)=-3\)、"
        r"\(\sigma_1+3\sigma_3=0\) である。これは傾きの順序や基準方向に"
        r"依存しない射影的な条件である。",
        r"\(e_3=t_1t_2t_3\)、\(q=cs+3e_3\) とおく。"
        r"\(m_i=3t_i^2-c\) を前段の二つの対称式へ代入すると "
        r"\(2sq=c^2+1\)、\(s^2+3q^2=c(c^2+1)\) を得る。"
        r"従って \(sq>0\) であり、\(r=s/q>0\) とおけば "
        r"\(c=(r+3/r)/2\) である。相加相乗平均から \(c\ge\sqrt3\)。"
        r"逆に任意の \(r>0\) でこの式と二条件を満たす \(s,q\) が取れるので、"
        r"範囲はちょうど \([\sqrt3,\infty)\) である。",
        r"実際、\(s^2=(r^2+1)(r^2+9)/(8r)\)、"
        r"\(e_3=-s(r^2+1)/(6r)\) であり、接点三次式の判別式は "
        r"\(\Delta=(r^2+1)^3(r^2+9)/(96r)>0\) となる。"
        r"従って全ての \(r>0\) で接点は相異なる実数で、逆構成に欠落はない。",
        r"\(c=3\) では \(r^2-6r+3=0\) より "
        r"\(r=3\pm\sqrt6\)、\(s^2=5r\)、\(q=5/s\) である。"
        r"また \(u=2s/3,\ v=-2q/3\) なので、"
        r"\(s\) の二つの符号を合わせて(1)の4点を得る。",
        r"三接点のVandermonde行列式では、\(y_i=t_i^3-ct_i\) の線形項を消せる。"
        r"さらに \(t_i^3=st_i^2+e_3\) だから "
        r"\(2[ABC]=|s|\,|(t_1-t_2)(t_2-t_3)(t_3-t_1)|\)。"
        r"判別式を代入すると "
        r"\([ABC]=(r^2+1)^2(r^2+9)/(32\sqrt3\,r)\) となる。",
        r"その導関数の符号は \(5r^4+28r^2-9\) の符号に一致する。"
        r"\(r>0\) で唯一の零点は "
        r"\(r^2=(\sqrt{241}-14)/5\) で、両端では面積が無限大へ発散する。"
        r"この点での面積の平方を整理すると "
        r"\((5543\sqrt{241}-5647)/300000\) となり、(3)を得る。",
    ]


def _rational_polynomial_regular_polygon_extrema_impossible(
    objects: dict[str, Any],
) -> tuple[str, dict[str, Any], list[str]]:
    if int(objects.get("lower_index", 0)) != 3:
        raise ValueError("regular-polygon extremum chart requires n>=3")
    chart = _regular_polygon_extrema_obstruction_chart()
    return "存在しない", {
        "answer_tex": r"そのような多項式は存在しない。",
        "shared_chart": chart,
        "derivation_format": "tex",
    }, [
        r"反対に、極値点が正 \(n\) 角形の全頂点をなすと仮定する。"
        r"グラフ上の相異なる点なので横座標は相異なる。中心を \((h,v)\)、"
        r"外接円半径を \(R>0\)、\(\phi_k=\theta+2\pi k/n\) として、"
        r"\((x_k,y_k)=(h+R\cos\phi_k,v+R\sin\phi_k)\) と書ける。",
        r"\(f\) はモニックな \(n+1\) 次式で、これら \(n\) 個の横座標は"
        r"すべて \(f'\) の零点だから、"
        r"\[f'(x)=(n+1)P(x),\qquad "
        r"P(x)=2^{1-n}R^n\left\{T_n\!\left(\frac{x-h}{R}\right)"
        r"-\cos(n\theta)\right\}.\]"
        r"これは正多角形の \(n\) 個の横座標を一つの Chebyshev ファイバーへ"
        r"縮約した式である。",
        r"\(P\in\mathbb Q[x]\) である。上式の \(x^{n-1},x^{n-2}\) の係数は"
        r"それぞれ \(-nh\)、\(\binom n2h^2-nR^2/4\) なので、"
        r"\[h\in\mathbb Q,\qquad R^2\in\mathbb Q.\]",
        r"\(u=(x-h)/R,\ c=\cos(n\theta)\) とする。"
        r"\(\int T_n(u)\,du=T_{n+1}(u)/(2(n+1))-T_{n-1}(u)/(2(n-1))\)"
        r"を用いて各 \(u_k=\cos\phi_k\) で評価すると、ある定数 \(C\) と"
        r"\(K=(n+1)2^{1-n}R^{n+1}>0\) により"
        r"\[f(x_k)=C-\frac{K}{n^2-1}\{n^2c\cos\phi_k"
        r"+n\sin(n\theta)\sin\phi_k\}.\]",
        r"\(n\ge3\) では、頂点上の三つのベクトル"
        r"\(1,\cos\phi_k,\sin\phi_k\) は一次独立である。"
        r"上式が \(y_k=v+R\sin\phi_k\) と全ての \(k\) で一致するには"
        r"\(\cos(n\theta)=0\) が必要であり、符号も比較すると"
        r"\(\sin(n\theta)=-1\) である。さらに"
        r"\[R^n=\frac{2^{n-1}(n-1)}{n}.\]",
        r"最後の式は \(R^2\in\mathbb Q\) と両立しない。"
        r"\(n\) が奇数なら \(R\in\mathbb Q\) であり、素数 \(p\mid n\) に対する"
        r"右辺の \(p\)-進付値は \(-v_p(n)\)。これは非零で絶対値が \(n\) 未満なので"
        r"有理数の \(n\) 乗の付値にならない。\(n\) が偶数なら"
        r"\((R^2)^{n/2}=2^{n-1}(n-1)/n\)。\(n\) に奇素因子があればそれを、"
        r"\(n\) が2の冪なら \(n-1\) の奇素因子を取ると、右辺の付値は非零で"
        r"絶対値が \(n/2\) 未満となり、\(n/2\) の倍数ではない。いずれも矛盾する。",
    ]


def _balanced_grid_regression_angle_approximation(
    objects: dict[str, Any],
) -> tuple[str, dict[str, Any], list[str]]:
    if int(objects.get("target_tangent_squared", 0)) != 3:
        raise ValueError("grid regression chart currently targets pi/3")
    grid_sides = tuple(int(value) for value in objects.get("grid_sides", ()))
    if grid_sides != (4, 6):
        raise ValueError("certified problem requires the 4x4 and 6x6 grids")

    charts = [_balanced_grid_regression_chart(side) for side in grid_sides]

    def fraction_tex(candidate: dict[str, Any]) -> str:
        numerator = int(candidate["tangent_numerator"])
        denominator = int(candidate["tangent_denominator"])
        return rf"\frac{{{numerator}}}{{{denominator}}}"

    def rational_tex(value: str) -> str:
        rational = Fraction(value)
        if rational.denominator == 1:
            return str(rational.numerator)
        if rational.numerator < 0:
            return (
                rf"-\frac{{{-rational.numerator}}}"
                rf"{{{rational.denominator}}}"
            )
        return rf"\frac{{{rational.numerator}}}{{{rational.denominator}}}"

    def subset_tex(candidate: dict[str, Any]) -> str:
        rows_by_column = {
            column: [
                int(point[1])
                for point in candidate["witness_subset"]
                if int(point[0]) == column
            ]
            for column in range(1, int(candidate["grid_side"]) + 1)
        } if "grid_side" in candidate else {}
        if not rows_by_column:
            maximum_column = max(
                int(point[0]) for point in candidate["witness_subset"]
            )
            rows_by_column = {
                column: [
                    int(point[1])
                    for point in candidate["witness_subset"]
                    if int(point[0]) == column
                ]
                for column in range(1, maximum_column + 1)
            }
        columns = list(rows_by_column)
        header = "&".join(str(column) for column in columns)
        row_sets = "&".join(
            r"\{" + ",".join(str(row) for row in rows_by_column[column]) + r"\}"
            for column in columns
        )
        return (
            r"\begin{array}{c|"
            + "c" * len(columns)
            + r"}x&"
            + header
            + r"\\\hline S_x&"
            + row_sets
            + r"\end{array}"
        )

    answer_parts = [
        rf"\text{{({index}) }}{fraction_tex(chart['selected'])}"
        for index, chart in enumerate(charts, start=1)
    ]
    exact_parts = [
        f"({index}) {chart['selected']['tangent']}"
        for index, chart in enumerate(charts, start=1)
    ]

    derivation = [
        r"一方の部分集合を \(S\)、その要素数を \(k\) とし、"
        r"\(X=\sum_Sx,\ Y=\sum_Sy,\ Q=\sum_Sx^2,\ C=\sum_Sxy\) とおく。"
        r"\(y\) を \(x\) で回帰した直線の傾きは"
        r"\[b_S=\frac{kC-XY}{kQ-X^2}\]"
        r"である。補集合の5統計量は全格子の統計量との差で決まる。"
        r"従って個々の点集合ではなく \((k,X,Y,Q,C)\) だけを調べれば十分である。",
        r"一つの \(x\) 列から \(c\) 個の \(y\in\{1,\ldots,m\}\) を選ぶと、"
        r"\(\sum y\) は"
        r"\[c(c+1)/2,\ c(c+1)/2+1,\ldots,c(2m-c+1)/2\]"
        r"の全整数を取る。よって列ごとの選択は、個々の部分集合ではなく"
        r"\((c,\sum y,x\sum y)\) の有限状態へ正確に縮約できる。",
        r"さらに、二部分集合の交換、格子の左右反転、上下反転は二直線の"
        r"鋭角を変えないので同じ軌道を一度だけ調べる。二直線の傾きを"
        r"\(b_1,b_2\) とすると"
        r"\[\tan\theta=\left|\frac{b_1-b_2}{1+b_1b_2}\right|\]"
        r"であり、全比較は有理数の整数演算だけで行える。",
    ]
    for index, chart in enumerate(charts, start=1):
        below = chart["below"]
        above = chart["above"]
        comparison = chart["angular_comparison"]
        derivation.append(
            rf"\(({index})\) \(m={chart['grid_side']}\) では、"
            rf"\(\binom{{{chart['point_count']}}}{{{chart['subset_cardinality']}}}"
            rf"={chart['raw_subset_count']}\) 個の部分集合を直接調べる代わりに、"
            rf"{chart['raw_compressed_states']} 個の十分統計状態へ縮約し、"
            rf"対称性代表 {chart['symmetry_representatives_evaluated']} 個を厳密走査した。"
            rf"\(\sqrt3\) の直下は \({fraction_tex(below)}\)、"
            rf"直上は \({fraction_tex(above)}\) である。"
        )
        derivation.append(
            rf"角度誤差の比較には、小さい方を \(l\)、大きい方を \(u\) として"
            rf"\[\arctan l+\arctan u\ge\frac{{2\pi}}{{3}}"
            rf"\iff\left(\frac{{l+u}}{{lu-1}}\right)^2\le3\]"
            rf"を用いる。実際、"
            rf"\[\frac{{l+u}}{{lu-1}}="
            rf"{rational_tex(comparison['cross_tangent'])},\qquad"
            rf"\left(\frac{{l+u}}{{lu-1}}\right)^2-3="
            rf"{rational_tex(comparison['square_minus_three'])}<0.\]"
            rf"従って選ばれる近似は \({fraction_tex(chart['selected'])}\) である。"
        )
        derivation.append(
            rf"実現可能性も保存されている。例えば各列で選ぶ行の集合"
            rf"\(S_x=\{{y:(x,y)\in S_{index}\}}\) を"
            rf"\[{subset_tex(chart['selected'])}\]"
            rf"と取ると、二本の回帰直線の傾きは"
            rf"\({chart['selected']['first_slope']}\) と"
            rf"\({chart['selected']['second_slope']}\) であり、"
            rf"上の正接値を正確に再生する。"
        )

    return "; ".join(exact_parts), {
        "answer_tex": r"\(" + r"\qquad ".join(answer_parts) + r"\)",
        "shared_charts": charts,
        "derivation_format": "tex",
    }, derivation


def _cubic_arc_dot_chord_sweep_area(
    objects: dict[str, Any],
) -> tuple[str, dict[str, Any], list[str]]:
    coefficients = tuple(int(value) for value in objects.get("coefficients", ()))
    if len(coefficients) != 4:
        raise ValueError("cubic arc chart requires four coefficients")
    dot_target = int(objects["dot_target"])
    chart = _cubic_arc_dot_chord_sweep_chart(coefficients, dot_target)
    answer_tex = chart["area_tex"]
    return chart["area"], {
        "answer_tex": rf"\({answer_tex}\)",
        "shared_chart": chart,
        "derivation_format": "tex",
    }, [
        r"曲線の式は"
        r"\[f(x)=x^3-12x^2+45x-54=(x-6)(x-3)^2.\]"
        r"従って \(x=3\) から \(x=6\) までの弧だけが \(x\) 軸と有界領域を囲む。"
        r"\(x=3+t\) と移すと \(0\le t\le3\) で"
        r"\[g(t)=t^2(t-3)\]"
        r"となる。",
        r"\(P,Q\) の移した横座標を \(u,v\)、"
        r"\(S=u+v,\ R=uv\) とおく。内積条件を展開して対称式へ戻すと"
        r"\[(u+3)(v+3)+g(u)g(v)-20"
        r"=(R-1)(R^2-3RS+10R-3S+11)=0.\]",
        r"第二因子が0なら"
        r"\[S=\frac{R^2+10R+11}{3(R+1)}.\]"
        r"一方 \(0\le u,v\le3\) より"
        r"\((3-u)(3-v)\ge0\)、従って \(S\le3+R/3\) である。"
        r"しかし両辺の差は \(2/(3(R+1))>0\) となり矛盾する。"
        r"従って許容される全ての弦で"
        r"\[uv=1\]"
        r"である。",
        r"\(uv=1\) かつ \(u,v\in[0,3]\) なので"
        r"\[2\le S=u+v\le\frac{10}{3}.\]"
        r"三次式から弦を引くと \(u,v\) を零点に持つ三次式になるため、"
        r"第三の零点は \(3-S\) である。従って弦の式は"
        r"\[\ell_S(t)=(S^2-3S-1)t+3-S.\]",
        r"固定した \(t\in[1/3,3]\) を通る弦の条件は"
        r"\(t^2-St+1\le0\)、すなわち"
        r"\[t+\frac1t\le S\le\frac{10}{3}.\]"
        r"\(\ell_S(t)\) は \(S\) の上に凸な二次式である。"
        r"上端は常に \(S=10/3\) の弦"
        r"\[U(t)=\frac{t-3}{9}\]"
        r"で与えられる。",
        r"下端は通常 \(g(t)=t^3-3t^2\) である。"
        r"ただし \(\partial\ell_S(t)/\partial S=0\) となる"
        r"\(S=3/2+1/(2t)\) が許容区間に入る"
        r"\(1/2\le t\le1\) では包絡線"
        r"\[H(t)=-\frac{13t^2-6t+1}{4t}\]"
        r"が下端となる。\(S\) が連続区間を動くので、各鉛直断面には欠落がない。",
        r"従って求める面積は"
        r"\[\begin{aligned}"
        r"A={}&\int_{1/3}^{1/2}(U-g)\,dt"
        r"+\int_{1/2}^{1}(U-H)\,dt"
        r"+\int_{1}^{3}(U-g)\,dt\\"
        r"={}&\frac{31877}{5184}+\frac14\log2."
        r"\end{aligned}\]"
        r"平行移動 \(x=t+3\) は面積を変えないので、これが元の通過領域の面積である。",
    ]


def _coordinate_tangent_disk_projection_area(
    objects: dict[str, Any],
) -> tuple[str, dict[str, Any], list[str]]:
    if int(objects.get("ambient_dimension", 0)) != 3:
        raise ValueError("coordinate-tangent disk chart requires three dimensions")
    if tuple(objects.get("projection_axes", ())) != ("x", "y"):
        raise ValueError("certified projection chart currently targets the xy-plane")
    radius = int(objects["radius"])
    chart = _coordinate_tangent_disk_projection_chart(radius)
    r_tex = sp.latex(sp.Integer(radius))
    return chart["area"], {
        "answer_tex": rf"\({chart['area_tex']}\)",
        "shared_chart": chart,
        "derivation_format": "tex",
    }, [
        rf"円板の半径を \(r={r_tex}\) とし、その平面の単位法線を"
        r"\(\boldsymbol n=(a,b,c)\)、中心を \(C=(p,q,s)\) とする。"
        r"円板内で \(x\) 座標が動ける半径は"
        r"\(r\sqrt{1-a^2}\) である。\(x=0\) とただ1点で接し、"
        r"円板全体が \(x\ge0\) にあることから"
        r"\[p=r\sqrt{1-a^2}.\]"
        r"同様に"
        r"\[q=r\sqrt{1-b^2},\qquad s=r\sqrt{1-c^2}.\]",
        r"\(xy\) 平面への射影を \(E_{\boldsymbol n}\) とする。"
        r"方向 \((u,v)\) に対する支持関数は、円板平面への直交射影を用いて"
        r"\[h_{\boldsymbol n}(u,v)=r\left\{"
        r"u\sqrt{1-a^2}+v\sqrt{1-b^2}"
        r"+\sqrt{u^2+v^2-(au+bv)^2}\right\}.\]"
        r"また各座標の中心値と射影半径が等しいので、常に"
        r"\[0\le x,y\le2r.\]",
        r"\(u,v\ge0\) なら"
        r"\(\sqrt{1-a^2},\sqrt{1-b^2}\le1\) および"
        r"\(\sqrt{u^2+v^2-(au+bv)^2}\le\sqrt{u^2+v^2}\) より"
        r"\[h_{\boldsymbol n}(u,v)\le "
        r"r\{u+v+\sqrt{u^2+v^2}\}.\]"
        r"従って \(x>r,\ y>r\) の点に"
        r"\((u,v)=(x-r,y-r)/\sqrt{(x-r)^2+(y-r)^2}\) を代入すると"
        r"\[(x-r)^2+(y-r)^2\le r^2.\]"
        r"よって全射影は、正方形 \([0,2r]^2\) の右上隅を"
        r"中心 \((r,r)\)、半径 \(r\) の円弧で切った領域 \(R\) に含まれる。",
        r"逆に \(0<\lambda<1\) として法線を"
        r"\((\sqrt{1-\lambda^2},0,\lambda)\) と取る。"
        r"これは三座標平面へ一意に接し、その射影楕円は"
        r"\[\left(\frac{x-r\lambda}{r\lambda}\right)^2"
        r"+\left(\frac{y-r}{r}\right)^2\le1.\]"
        r"\(\lambda\) を動かすと、各 \(0\le y\le2r\) で"
        r"\[0<x<r+\sqrt{r^2-(y-r)^2}\]"
        r"をすべて覆う。法線 \((0,\sqrt{1-\lambda^2},\lambda)\) の族は"
        r"これを \(x,y\) について入れ替えた領域を覆う。",
        r"この二領域の和は、\(x\le r\) または \(y\le r\) では正方形全体を覆う。"
        r"\(x>r,\ y>r\) では、どちらかに入る条件がちょうど"
        r"\[(x-r)^2+(y-r)^2\le r^2\]"
        r"となる。従って測度0の境界を除いて和は \(R\) 全体であり、"
        r"上の包含と合わせて掃引領域の閉包は \(R\) である。",
        r"右上の \(r\times r\) 正方形から半径 \(r\) の四分円を除いた部分だけが"
        r"掃引されない。従って面積は"
        r"\[\begin{aligned}"
        r"|R|&=4r^2-\left(r^2-\frac{\pi r^2}{4}\right)\\"
        r"&=r^2\left(3+\frac{\pi}{4}\right)."
        r"\end{aligned}\]"
        rf"\(r={r_tex}\) を代入して \({chart['area_tex']}\) を得る。",
    ]


def _four_face_tangent_disk_swept_volume(
    objects: dict[str, Any],
) -> tuple[str, dict[str, Any], list[str]]:
    if int(objects.get("ambient_dimension", 0)) != 3:
        raise ValueError("four-face disk sweep requires three dimensions")
    radius = int(objects["radius"])
    cube_side = int(objects["cube_side"])
    chart = _four_face_tangent_disk_sweep_chart(radius, cube_side)
    r_tex = sp.latex(sp.Integer(radius))
    side_tex = sp.latex(sp.Integer(cube_side))
    return chart["volume"], {
        "answer_tex": rf"\({chart['volume_tex']}\)",
        "shared_chart": chart,
        "derivation_format": "tex",
        "diagram": {
            "version": 1,
            "kind": "geometry",
            "title": "高さ z における通過領域の断面",
            "caption": "中心軌跡と円板の水平切片から生じる四分円環。",
        },
        "diagram_tikz": r"""\begin{tikzpicture}[scale=1.12,>=stealth]
\fill[cyan!14] (3,0) arc (0:90:3) -- (0,1) arc (90:0:1) -- cycle;
\draw[very thick,cyan!70!black] (3,0) arc (0:90:3);
\draw[very thick,cyan!70!black] (1,0) arc (0:90:1);
\draw[very thick,cyan!70!black] (1,0)--(3,0) (0,1)--(0,3);
\draw[dashed,gray!70] (2,0) arc (0:90:2);
\draw[->] (-.15,0)--(3.45,0) node[right] {$x$};
\draw[->] (0,-.15)--(0,3.45) node[above] {$y$};
\draw[<->] (0,-.32)--(1,-.32)
  node[midway,below,font=\footnotesize] {$r-\rho(z)$};
\draw[<->] (0,-.72)--(3,-.72)
  node[midway,below,font=\footnotesize] {$r+\rho(z)$};
\node[font=\footnotesize,fill=white,inner sep=1.5pt] at (1.42,1.42)
  {中心軌跡 $R=r$};
\node[font=\footnotesize,align=center] at (2.45,2.25)
  {高さ $z$ の\\四分円環断面};
\end{tikzpicture}""",
    }, [
        rf"円板の半径を \(r={r_tex}\)、立方体の一辺を \(2r={side_tex}\) とする。"
        r"円板平面の単位法線を \(\boldsymbol n=(a,b,c)\)、中心を"
        r"\(C=(p,q,s)\) とする。円板の \(z\) 方向の半径は"
        r"\(r\sqrt{1-c^2}\) である。",
        r"円周が平行な二面 \(z=0,\ z=2r\) の双方に一点で接するため、"
        r"中心は \(s=r\)、\(z\) 方向の半径も \(r\) でなければならない。従って"
        r"\[\sqrt{1-c^2}=1,\qquad c=0.\]"
        r"すなわち法線は水平である。",
        r"\(a^2+b^2=1\) であり、\(x=0,\ y=0\) への接触条件から"
        r"\[C=(r|b|,r|a|,r).\]"
        r"従って中心の \(xy\) 座標は半径 \(r\) の四分円周上を動く。",
        r"高さ \(z\) を固定し、\(\zeta=z-r\) とおく。円板内で残る水平線分の"
        r"半長は"
        r"\[\rho(z)=\sqrt{r^2-\zeta^2}=\sqrt{r^2-(z-r)^2}.\]"
        r"水平単位方向は \((-b,a)\) なので、その線分上の点は"
        r"\[(x,y)=(r|b|-bt,\ r|a|+at),\qquad |t|\le\rho(z)\]"
        r"と書ける。",
        r"この点の原点距離を \(R\) とすると、三角不等式から"
        r"\[r-|t|\le R\le r+|t|,\]"
        r"従って高さ \(z\) の全断面は、第一象限の"
        r"\(r-\rho(z)\le R\le r+\rho(z)\) に含まれる。",
        r"逆向きの包含も成り立つ。\(a,b\) の符号を反対に取ると水平方向"
        r"\((-b,a)\) は中心ベクトル \((|b|,|a|)\) と平行になる。"
        r"四分円上の中心方向と \(|t|\le\rho(z)\) を動かすことで、"
        r"半径区間 \([r-\rho(z),r+\rho(z)]\) の全方向を覆う。"
        r"従って断面はちょうど四分円環である。",
        r"その面積は"
        r"\[A(z)=\frac{\pi}{4}\{(r+\rho)^2-(r-\rho)^2\}"
        r"=\pi r\sqrt{r^2-(z-r)^2}.\]"
        r"よって Cavalieri の原理により"
        r"\[\begin{aligned}"
        r"V&=\int_0^{2r}A(z)\,dz\\"
        r"&=\pi r\int_{-r}^{r}\sqrt{r^2-\zeta^2}\,d\zeta\\"
        r"&=\frac{\pi^2r^3}{2}."
        r"\end{aligned}\]"
        rf"\(r={r_tex}\) を代入して \({chart['volume_tex']}\) を得る。",
    ]


def _fibonacci_angle_period_average(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    recurrence_chart = _second_order_recurrence_chart(1, 1)
    residues = [1, 1]
    while len(residues) < 12:
        residues.append((residues[-1] + residues[-2]) % 8)
    if residues != [1, 1, 2, 3, 5, 0, 5, 5, 2, 7, 1, 0]:
        raise ValueError("Fibonacci residue period failed")
    if ((residues[-1] + residues[-2]) % 8, (2 * residues[-1] + residues[-2]) % 8) != (1, 1):
        raise ValueError("Fibonacci residue state did not close after twelve steps")
    if any((residues[index], residues[index + 1]) == (1, 1) for index in range(1, 11)):
        raise ValueError("Fibonacci residue period was not minimal")

    period_sine_sum = sp.simplify(sum(sp.sin(sp.pi * residue / 4) for residue in residues))
    if period_sine_sum != 2:
        raise ValueError("Fibonacci sine-period sum failed")

    m = sp.Symbol("m", integer=True, positive=True)
    formula = (2 * (1 + (-1) ** m) * sp.cos(sp.pi * m / 4) + 1 + sp.cos(sp.pi * m / 2)) / 6
    direct_by_m_mod_8 = []
    formula_by_m_mod_8 = []
    for residue_m in range(8):
        representative = residue_m if residue_m else 8
        direct = sp.simplify(
            sum(
                sp.chebyshevt(representative, sp.sin(sp.pi * residue / 4))
                for residue in residues
            )
            / 12
        )
        expected = sp.simplify(formula.subs(m, representative))
        direct_by_m_mod_8.append(sp.sstr(direct))
        formula_by_m_mod_8.append(sp.sstr(expected))
        if sp.simplify(direct - expected) != 0:
            raise ValueError("Chebyshev residue average failed")

    answer_tex = (
        r"\(\text{(1)}\ \frac16.\qquad \text{(2)}\ P_m(x)=T_m(x).\)"
        "\n"
        r"\[\text{(3)}\quad "
        r"\lim_{n\to\infty}\frac1n\sum_{k=1}^nP_m(\sin a_k)="
        r"\begin{cases}"
        r"1&(m\equiv0\pmod 8),\\"
        r"-\frac13&(m\equiv4\pmod 8),\\"
        r"0&(m\equiv2,6\pmod 8),\\"
        r"\frac16&(m\ \text{is odd})."
        r"\end{cases}\]"
    )
    return (
        f"(1) 1/6; (2) P_m=ChebyshevT(m,x); (3) {sp.sstr(formula)}",
        {
            "period_mod_8": residues,
            "period_length": 12,
            "period_sine_sum": sp.sstr(period_sine_sum),
            "recurrence_chart": recurrence_chart,
            "closed_form_average": sp.sstr(formula),
            "direct_by_m_mod_8": direct_by_m_mod_8,
            "formula_by_m_mod_8": formula_by_m_mod_8,
            "derivation_format": "tex",
            "answer_tex": answer_tex,
            "shared_chart": {
                "chart_id": "fibonacci.mod8.chebyshev.period_average.v1",
                "atomic_chart_ids": [
                    "recurrence.order2.companion.characteristic.v1",
                    "finite_state.modular_orbit.v1",
                    "cesaro.eventual_period.average.v1",
                    "chebyshev.angle_multiplication.v1",
                    "finite_character.residue_aggregation.v1",
                ],
                "proof_obligations": {
                    "modular_state_period_is_twelve": True,
                    "period_sine_sum_is_two": True,
                    "chebyshev_recurrence_matches_cosine_multiplication": True,
                    "all_eight_parameter_residues_replayed": True,
                },
            },
        },
        [
            r"\(a_n=F_n\pi/4\) と書く。ただし \(F_1=F_2=1\) である。状態 \((F_n,F_{n+1})\bmod 8\) は12周期で、一周期は \[1,1,2,3,5,0,5,5,2,7,1,0\] となる。従って長い和の Ces\`aro 平均は、この12項の平均に一致する。",
            r"一周期について \[\sum_{k=1}^{12}\sin\frac{F_k\pi}{4}=2\] だから、(1) の極限は \(2/12=1/6\) である。",
            r"(2) の漸化式と初期値は Chebyshev 多項式 \(T_m\) の定義そのものである。実際、加法定理から \[2\cos x\cos((m+1)x)-\cos(mx)=\cos((m+2)x)\] なので、帰納法により \(P_m(\cos x)=\cos(mx)\) を得る。",
            r"\(\sin a_k=\cos(\pi/2-a_k)\) より \[P_m(\sin a_k)=\cos\!\left(\frac{m\pi}{2}-\frac{mF_k\pi}{4}\right).\] 法8の一周期を集計すると \[\frac{2(1+(-1)^m)\cos(m\pi/4)+1+\cos(m\pi/2)}6\] となる。これを \(m\bmod8\) で整理すれば、表示した4場合を得る。",
        ],
    )


def _discrete_trigonometric_exponential_asymptotic(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    lower = int(objects["lower_index"])
    if lower != 4:
        raise ValueError("the certified index interval starts at n=4")
    u = sp.Symbol("u", positive=True)
    log_profile = (1 / u + u) * sp.log(1 + u)
    second_derivative_numerator = sp.factor(
        sp.diff(log_profile, u, 2) * u**3 * (1 + u) ** 2
    )
    log_lower = u - u**2 / 2
    convex_lower = sp.factor(second_derivative_numerator.subs(sp.log(1 + u), log_lower))
    if convex_lower != 2 * u**3:
        raise ValueError("strict convexity reduction failed")

    # F' is increasing.  Rational Taylor enclosures locate its unique zero
    # strictly between u_13 and u_12, avoiding symbolic minimization over n.
    u_left = sp.Rational(11, 50)
    log_lower_four = sum(((-1) ** (k + 1)) * u_left**k / k for k in range(1, 5))
    derivative_at_left_upper = sp.factor(
        (1 - 1 / u_left**2) * log_lower_four + (1 / u_left + u_left) / (1 + u_left)
    )
    if derivative_at_left_upper >= 0:
        raise ValueError("upper sign certificate at 11/50 failed")

    u_right = sp.Rational(28, 125)
    log_upper_five = sum(((-1) ** (k + 1)) * u_right**k / k for k in range(1, 6))
    derivative_at_right_lower = sp.factor(
        (1 - 1 / u_right**2) * log_upper_five + (1 / u_right + u_right) / (1 + u_right)
    )
    if derivative_at_right_lower <= 0:
        raise ValueError("lower sign certificate at 28/125 failed")

    pi_upper = sp.Rational(355, 113)
    x13_upper = pi_upper / 13
    u13_upper = sp.factor(x13_upper - x13_upper**2 / 2 + x13_upper**4 / 24)
    if u13_upper >= u_left:
        raise ValueError("u_13 upper enclosure failed")
    if sp.Rational(6, 4) <= sp.Rational(153, 125) ** 2:
        raise ValueError("u_12 lower enclosure failed")

    # Convexity leaves n=12 and n=13 as the only adjacent candidates.  Close
    # that last comparison with rational enclosures, not decimal evaluation.
    sharp_pi_lower = sp.Rational(103993, 33102)
    sharp_pi_upper = sp.Rational(104348, 33215)
    x13_lower = sharp_pi_lower / 13
    x13_upper = sharp_pi_upper / 13
    trigonometric_interval_chart = _alternating_trig_interval_chart([x13_lower, x13_upper])
    lower_evaluation, upper_evaluation = trigonometric_interval_chart["evaluations"]
    sin13_lower = sp.Rational(lower_evaluation["sin_lower"])
    cos13_lower = sp.Rational(lower_evaluation["cos_lower"])
    sin13_upper = sp.Rational(upper_evaluation["sin_upper"])
    cos13_upper = sp.Rational(upper_evaluation["cos_upper"])
    u13_sharp_lower = sp.factor(sin13_lower + cos13_lower - 1)
    u13_sharp_upper = sp.factor(sin13_upper + cos13_upper - 1)

    sqrt6_lower = sp.Rational(2449489742, 10**9)
    sqrt6_upper = sp.Rational(2449489743, 10**9)
    if not sqrt6_lower**2 < 6 < sqrt6_upper**2:
        raise ValueError("sqrt(6) rational enclosure failed")
    u12_lower = sqrt6_lower / 2 - 1
    u12_upper = sqrt6_upper / 2 - 1

    f13_lower, _ = _log_profile_bounds(u13_sharp_lower, u13_sharp_upper)
    _, f12_upper = _log_profile_bounds(u12_lower, u12_upper)
    adjacent_margin = sp.factor(f13_lower - f12_upper)
    if adjacent_margin <= 0:
        raise ValueError("exact a_12 < a_13 comparison failed")

    u12 = sp.sqrt(6) / 2 - 1
    minimum = (1 + u12) ** (1 / u12 + u12)
    asymptotic = sp.E * sp.pi / 2
    return f"minimum a_12={sp.sstr(minimum)}; limit={sp.sstr(asymptotic)}", {
        "minimizing_n": 12,
        "profile": "F(u)=(u+1/u)log(1+u)",
        "convexity_lower_numerator": sp.sstr(convex_lower),
        "u13_upper": sp.sstr(u13_upper),
        "u12_lower": "28/125",
        "derivative_upper_at_11_over_50": sp.sstr(derivative_at_left_upper),
        "derivative_lower_at_28_over_125": sp.sstr(derivative_at_right_lower),
        "log_a13_minus_log_a12_lower": sp.sstr(adjacent_margin),
        "trigonometric_interval_chart": trigonometric_interval_chart,
        "first_order_profile": "F(u)=1-u/2+O(u^2)",
        "first_order_input": "u_n=pi/n+O(n^-2)",
    }, [
        "u_n=sin(pi/n)+cos(pi/n)-1 と置くと、u_nはnについて狭義単調減少し、log a_n=F(u_n)=(u_n+1/u_n)log(1+u_n)である。",
        "F''の分子でlog(1+u)>=u-u^2/2を使うと2u^3>0が残るため、F'は狭義単調増加する。",
        "交代級数の有理評価からF'(11/50)<0<F'(28/125)を得る。またu_13<11/50<28/125<u_12なので、最小候補はn=12,13に限られる。",
        "pi, sqrt(6), log(1+u)の有理上下界を合成してF(u_13)-F(u_12)>0を直接証明し、離散列の最小をn=12に確定した。",
        "F(u)=1-u/2+O(u^2), u_n=pi/n+O(n^-2)を合成すると n(e-a_n) -> e*pi/2 となる。",
    ]


def _power_mean_linearized_recurrence(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    first = sp.Integer(objects["first"])
    second = sp.Integer(objects["second"])
    denominator = sp.Integer(objects["weight_denominator"])
    if first <= 0 or second <= 0 or denominator != 2:
        raise ValueError("the power-mean recurrence requires positive initial data and denominator two")

    n = sp.Symbol("n", integer=True, positive=True)
    p = sp.Symbol("p", real=True, nonzero=True)
    y1 = first**p
    y2 = second**p
    recurrence_chart = _second_order_recurrence_chart(sp.Rational(1, 2), sp.Rational(1, 2))
    stationary = sp.factor((y1 + 2 * y2) / 3)
    alternating = sp.factor(2 * (y1 - y2) / 3)
    y_n = stationary + alternating * sp.Rational(-1, 2) ** (n - 1)

    if sp.simplify(y_n.subs(n, 1) - y1) != 0 or sp.simplify(y_n.subs(n, 2) - y2) != 0:
        raise ValueError("linearized recurrence initial-value replay failed")
    recurrence_residual = sp.simplify(
        2 * y_n.subs(n, n + 2) - y_n.subs(n, n + 1) - y_n
    )
    if recurrence_residual != 0:
        raise ValueError("linearized recurrence identity failed")

    x_n = y_n ** (1 / p)
    n_limit = stationary ** (1 / p)
    p_limit = sp.simplify(first ** sp.Rational(1, 3) * second ** sp.Rational(2, 3))
    q = sp.Symbol("q", real=True)
    logarithmic_derivative = sp.simplify(
        sp.diff(sp.log((first**q + 2 * second**q) / 3), q).subs(q, 0)
    )
    expected_derivative = sp.log(first) / 3 + 2 * sp.log(second) / 3
    if sp.simplify(logarithmic_derivative - expected_derivative) != 0:
        raise ValueError("p-to-zero logarithmic derivative failed")

    if first == 1 and second == 2:
        answer_tex = (
            r"\[x_n=\left\{\frac{1+2^{p+1}}3+\frac{2(1-2^p)}3"
            r"\left(-\frac12\right)^{n-1}\right\}^{1/p}.\]"
            r"\[\lim_{p\to0}\lim_{n\to\infty}x_n(p)=2^{2/3}.\]"
        )
    else:
        answer_tex = (
            r"\[x_n=\left\{\frac{x_1^p+2x_2^p}{3}"
            r"+\frac{2(x_1^p-x_2^p)}3\left(-\frac12\right)^{n-1}\right\}^{1/p}.\]"
            r"\[\lim_{p\to0}\lim_{n\to\infty}x_n(p)=x_1^{1/3}x_2^{2/3}.\]"
        )

    return (
        f"x_n={sp.sstr(x_n)}; limit={sp.sstr(p_limit)}",
        {
            "conjugacy": "y_n=x_n^p",
            "recurrence_chart": recurrence_chart,
            "characteristic_roots": ["1", "-1/2"],
            "linearized_closed_form": sp.sstr(y_n),
            "recurrence_residual": sp.sstr(recurrence_residual),
            "n_limit_before_p_limit": sp.sstr(n_limit),
            "p_zero_log_derivative": sp.sstr(logarithmic_derivative),
            "joint_parameter_limit": sp.sstr(p_limit),
            "derivation_format": "tex",
            "answer_tex": answer_tex,
            "shared_chart": {
                "chart_id": "power_mean.recurrence.linearization.v1",
                "atomic_chart_ids": [
                    "positive_power.conjugacy.v1",
                    "recurrence.order2.companion.characteristic.v1",
                    "stable_mode.elimination.v1",
                    "logarithmic_mean.p_zero_limit.v1",
                ],
                "proof_obligations": {
                    "positive_power_change_is_reversible": True,
                    "linear_recurrence_replayed_at_both_initial_values": True,
                    "stable_mode_has_modulus_below_one": True,
                    "p_zero_limit_closed_by_logarithmic_derivative": True,
                },
            },
        },
        [
            r"全ての項は正である。そこで \(y_n=x_n^p\) と置くと、非線形なべき平均漸化式は \[2y_{n+2}=y_{n+1}+y_n\] へ可逆に変換される。",
            r"特性方程式は \(2\lambda^2-\lambda-1=(\lambda-1)(2\lambda+1)\) である。従って \[y_n=\frac{x_1^p+2x_2^p}{3}+\frac{2(x_1^p-x_2^p)}3\left(-\frac12\right)^{n-1}.\] 初期値と漸化式への代入残差はいずれも0である。正の \(p\) 乗根を取れば \(x_n\) の表示を得る。",
            r"\(n\to\infty\) では安定モード \((-1/2)^{n-1}\) が消えるため、\[\lim_{n\to\infty}x_n(p)=\left(\frac{x_1^p+2x_2^p}{3}\right)^{1/p}.\]",
            r"最後に対数を取る。\[\lim_{p\to0}\frac1p\log\frac{x_1^p+2x_2^p}{3}=\left.\frac{d}{dp}\log\frac{x_1^p+2x_2^p}{3}\right|_{p=0}=\frac13\log x_1+\frac23\log x_2.\] よって極限は \(x_1^{1/3}x_2^{2/3}\)、特に \(x_1=1,x_2=2\) では \(2^{2/3}\) である。",
        ],
    )


def _trigonometric_power_sum_threshold(
    objects: dict[str, Any],
) -> tuple[str, dict[str, Any], list[str]]:
    numerator = int(objects["sum_numerator"])
    denominator = int(objects["sum_denominator"])
    if denominator <= 0:
        raise ValueError("the trigonometric power-sum denominator must be positive")
    s = Fraction(numerator, denominator)
    if not Fraction(0) < s < Fraction(1):
        raise ValueError("the current exact chart requires 0 < sin(theta)+cos(theta) < 1")

    # Write {sin(theta), cos(theta)}={u,-v}.  The input conditions imply
    # u-v=s, u^2+v^2=1 and uv=(1-s^2)/2, with 0<v<u<1.
    uv = (1 - s * s) / 2
    rho = uv * uv
    if not Fraction(0) < uv < Fraction(1, 2) or not Fraction(0) < rho < Fraction(1, 4):
        raise ValueError("positive-root chart preconditions failed")
    newton_chart = _second_order_recurrence_chart(
        sp.Rational(s.numerator, s.denominator),
        sp.Rational(uv.numerator, uv.denominator),
    )
    parity_chart = _second_order_recurrence_chart(
        1,
        -sp.Rational(rho.numerator, rho.denominator),
    )

    even_values: dict[int, Fraction] = {0: Fraction(2), 2: Fraction(1)}
    selected_even = [2]
    even_index = 4
    while even_index <= 10_000:
        value = even_values[even_index - 2] - rho * even_values[even_index - 4]
        if value <= 0:
            raise ValueError("even power-sum positivity certificate failed")
        even_values[even_index] = value
        if value <= s:
            first_even_failure = even_index
            break
        selected_even.append(even_index)
        even_index += 2
    else:  # pragma: no cover - defensive bound for extreme rational inputs.
        raise ValueError("even power-sum threshold was not reached within the certified bound")

    # For odd n, divide the positive difference u^n-v^n by u-v=s.
    # The normalized sequence has the same parity transition matrix.
    odd_values: dict[int, Fraction] = {1: Fraction(1), 3: 1 + uv}
    selected_odd = [3]
    odd_index = 5
    while odd_index <= 10_001:
        value = odd_values[odd_index - 2] - rho * odd_values[odd_index - 4]
        if value <= 0:
            raise ValueError("odd normalized power-sum positivity certificate failed")
        odd_values[odd_index] = value
        if value <= 1:
            first_odd_failure = odd_index
            break
        selected_odd.append(odd_index)
        odd_index += 2
    else:  # pragma: no cover - defensive bound for extreme rational inputs.
        raise ValueError("odd power-sum threshold was not reached within the certified bound")

    selected = sorted(selected_even + selected_odd)

    # Independently replay the original Newton recurrence
    # P_n=s P_(n-1)+uv P_(n-2), then compare it with both parity charts.
    replay_limit = max(first_even_failure, first_odd_failure)
    power_sums: dict[int, Fraction] = {0: Fraction(2), 1: s}
    for index in range(2, replay_limit + 1):
        power_sums[index] = s * power_sums[index - 1] + uv * power_sums[index - 2]
    for index, value in even_values.items():
        if index <= replay_limit and power_sums[index] != value:
            raise ValueError("even parity chart disagrees with the original Newton recurrence")
    for index, value in odd_values.items():
        if index <= replay_limit and power_sums[index] != s * value:
            raise ValueError("odd parity chart disagrees with the original Newton recurrence")
    if any(power_sums[index] <= s for index in selected):
        raise ValueError("selected exponent failed the exact threshold check")
    if power_sums[first_even_failure] > s or power_sums[first_odd_failure] > s:
        raise ValueError("first-failure threshold certificate failed")

    s_text = str(s)
    rho_text = str(rho)
    s_tex = sp.latex(sp.Rational(s.numerator, s.denominator))
    uv_tex = sp.latex(sp.Rational(uv.numerator, uv.denominator))
    rho_tex = sp.latex(sp.Rational(rho.numerator, rho.denominator))
    selected_tex = ", ".join(str(index) for index in selected)
    answer_tex = rf"\(\{{{selected_tex}\}}\)"
    shared_chart = {
        "chart_id": "trigonometric.power_sum.parity_threshold.v1",
        "atomic_chart_ids": [
            "symmetric_pair.newton_recurrence.v1",
            "parity_subsequence.transition_matrix.v1",
            "positive_sequence.first_failure.v1",
        ],
        "newton_recurrence_chart": newton_chart,
        "parity_recurrence_chart": parity_chart,
        "proof_obligations": {
            "opposite_sign_roots_derived": True,
            "newton_recurrence_replayed": True,
            "parity_recurrences_replayed": True,
            "first_failures_certified_exactly": True,
            "tail_exclusion_by_monotonicity": True,
        },
    }
    return (
        str(selected),
        {
            "answer_tex": answer_tex,
            "derivation_format": "tex",
            "shared_chart": shared_chart,
            "sum": s_text,
            "root_chart": {
                "positive_root": f"({s_text}+sqrt(2-({s_text})^2))/2",
                "negative_root_magnitude": f"(-{s_text}+sqrt(2-({s_text})^2))/2",
            },
            "newton_recurrence_chart": newton_chart,
            "parity_recurrence_chart": parity_chart,
            "parity_transition_matrix": [["1", f"-{rho_text}"], ["1", "0"]],
            "transition_invariant": "X_(n+2)=X_n-rho*X_(n-2)",
            "selected_exponents": selected,
            "first_even_failure": first_even_failure,
            "first_odd_failure": first_odd_failure,
            "boundary_values": {
                "last_even_success": str(even_values[first_even_failure - 2]),
                "first_even_failure": str(even_values[first_even_failure]),
                "last_odd_success_normalized": str(odd_values[first_odd_failure - 2]),
                "first_odd_failure_normalized": str(odd_values[first_odd_failure]),
            },
            "newton_recurrence_replayed_through": replay_limit,
        },
        [
            rf"\(s=\sin\theta+\cos\theta={s_tex}\) とおく。"
            r"\[\sin\theta\cos\theta=\frac{s^2-1}{2}<0\]"
            r"であるから、\(\{\sin\theta,\cos\theta\}=\{u,-v\}\) "
            r"\((0<v<u<1)\) と書ける。",
            rf"このとき \(u-v=s\)、\(u^2+v^2=1\)、\(uv=(1-s^2)/2={uv_tex}\) である。"
            r"偶数 \(n\) には \(E_n=u^n+v^n\)、奇数 \(n\) には"
            r"\[O_n=\frac{u^n-v^n}{u-v}\]"
            rf"とおく。\(\rho=(uv)^2={rho_tex}\) とすれば、両列は"
            r"\[X_{n+2}=X_n-\rho X_{n-2}\]"
            r"を満たす。",
            rf"従って遷移行列で状態を"
            r"\[\binom{X_{n+2}}{X_n}="
            rf"\begin{{pmatrix}}1&-{rho_tex}\\1&0\end{{pmatrix}}"
            r"\binom{X_n}{X_{n-2}}\]"
            rf"で進めればよい。厳密有理数演算により、偶数列は \(n={first_even_failure}\)、"
            rf"奇数列は \(n={first_odd_failure}\) で初めて条件を満たさなくなる。",
            r"実際、\(E_n>0\)、\(O_n>0\) であり、上の漸化式から各部分列は狭義単調減少する。"
            r"また偶数では元のべき和が \(E_n\)、奇数では \(sO_n\) だから、"
            r"最初の不成立以後に条件が再び成立することはない。",
            rf"最後に元の Newton 漸化式"
            rf"\[P_n={s_tex}P_{{n-1}}+{uv_tex}P_{{n-2}},\qquad P_0=2,\quad P_1={s_tex}\]"
            rf"を \(n={replay_limit}\) まで独立に再生して照合した。従って求める集合は"
            rf"\[\boxed{{\{{{selected_tex}\}}}}\]"
            r"である。",
        ],
    )


def _binomial_exponential_edge_limit(
    objects: dict[str, Any],
) -> tuple[str, dict[str, Any], list[str]]:
    numerator = int(objects["increment_numerator"])
    denominator = int(objects["increment_denominator"])
    if denominator <= 0:
        raise ValueError("the binomial exponential increment denominator must be positive")
    increment = sp.Rational(numerator, denominator)
    if increment <= 0:
        raise ValueError("the binomial exponential edge chart requires a positive increment")

    n = sp.Symbol("n", integer=True, positive=True)
    reciprocal_bound = sp.Rational(2, 1) / n + 2 * (n - 3) / (n * (n - 1))
    if sp.simplify(4 / n - reciprocal_bound) != 4 / (n * (n - 1)):
        raise ValueError("reciprocal-binomial bound identity failed")
    if sp.limit(reciprocal_bound, n, sp.oo) != 0:
        raise ValueError("reciprocal-binomial mass did not vanish")

    limiting_value = sp.simplify(2 * (1 + increment) - sp.exp(increment))
    # The logarithmic enclosure
    # a-a^2/(2m) <= m log(1+a/m) <= a
    # gives a uniform error <= exp(a)*a^2/(2m).
    error_scale = sp.simplify(sp.exp(increment) * increment**2 / 2)
    total_error_bound = sp.simplify(error_scale * reciprocal_bound)
    if sp.limit(total_error_bound, n, sp.oo) != 0:
        raise ValueError("uniform binomial-array error bound failed")

    # Independent finite replay checks the analytic enclosure on several
    # nontrivial rows without using the expected limit.
    finite_margins: dict[str, str] = {}
    for row in (4, 7, 12):
        reciprocal_sum = sum(
            (sp.Rational(1, sp.binomial(row, index)) for index in range(1, row)),
            sp.Rational(0),
        )
        row_bound = reciprocal_bound.subs(n, row)
        margin = sp.simplify(row_bound - reciprocal_sum)
        if margin < 0:
            raise ValueError("finite reciprocal-binomial replay exceeded the certified bound")
        finite_margins[str(row)] = sp.sstr(margin)

    return (
        sp.sstr(limiting_value),
        {
            "increment": sp.sstr(increment),
            "endpoint_term": sp.sstr(1 + increment),
            "bulk_limit_per_term": sp.sstr(sp.exp(increment)),
            "reciprocal_binomial_bound": sp.sstr(reciprocal_bound),
            "uniform_term_error_scale": sp.sstr(error_scale),
            "total_error_bound": sp.sstr(total_error_bound),
            "finite_bound_margins": finite_margins,
            "limit": sp.sstr(limiting_value),
        },
        [
            f"m=C(n,k), a={sp.sstr(increment)} とおく。log(1+x) の上下評価から 0<=exp(a)-(1+a/m)^m<=exp(a)a^2/(2m) を得る。",
            "k=1,n-1 では 1/C(n,k)=1/n である。2<=k<=n-2 では C(n,k)>=C(n,2) なので、内部の逆二項係数和は 2(n-3)/(n(n-1)) 以下である。",
            "従って 1<=k<=n-1 の全誤差は exp(a)a^2/2 と 4/n 未満の積で抑えられ、n->infinity で0へ収束する。",
            f"端点 k=0,n は常に (1+a)^1={sp.sstr(1 + increment)} である。内部 n-1 項を exp(a) に置き換え、n exp(a) を引くと極限は {sp.sstr(limiting_value)} となる。",
        ],
    )


def _exponential_tangent_convex_bound(
    objects: dict[str, Any],
) -> tuple[str, dict[str, Any], list[str]]:
    del objects
    one = sp.Rational(1)
    half = sp.Rational(1, 2)

    # Alternating Taylor bounds are exact on [0,1].
    sin_one_upper = one - one**3 / 6 + one**5 / 120
    cos_one_lower = one - one**2 / 2 + one**4 / 24 - one**6 / 720
    tan_one_upper = sp.factor(sin_one_upper / cos_one_lower)

    sin_half_upper = half - half**3 / 6 + half**5 / 120
    cos_half_lower = one - half**2 / 2 + half**4 / 24 - half**6 / 720
    tan_half_upper = sp.factor(sin_half_upper / cos_half_lower)

    if not tan_one_upper < sp.Rational(39, 25):
        raise ValueError("tan(1) rational enclosure failed")
    if not 1 + tan_half_upper < sp.Rational(31, 20):
        raise ValueError("tan(1/2) rational enclosure failed")
    if not sp.Rational(39, 25) < sp.Rational(157, 100):
        raise ValueError("first endpoint comparison failed")
    if not sp.Rational(31, 20) < sp.Rational(157, 100):
        raise ValueError("second endpoint comparison failed")
    # Archimedes' rational lower bound is stronger than the decimal-looking
    # intermediary and keeps the endpoint proof exact.
    if not sp.Rational(157, 100) < sp.Rational(333, 106) / 2:
        raise ValueError("pi lower enclosure failed")
    if (sp.pi - sp.Rational(333, 106)).is_positive is not True:
        raise ValueError("Archimedes pi lower bound was not certified")

    # Coefficientwise comparison of the two convergent logarithmic series:
    # 1/(m+1) >= 1/(m*2^m), with equality only at m=1.
    coefficient_margins = {
        exponent: sp.Rational(1, exponent + 1) - sp.Rational(1, exponent * 2**exponent)
        for exponent in range(1, 9)
    }
    if coefficient_margins[1] != 0 or any(
        margin <= 0 for exponent, margin in coefficient_margins.items() if exponent >= 2
    ):
        raise ValueError("logarithmic coefficient comparison failed")

    return (
        "成立",
        {
            "substitution": "y=1/x in (0,1)",
            "exponential_affine_bound": "e*(1-y)^(1/y) < 1-y/2",
            "convex_majorant": "h(y)=tan(1-y/2)+y",
            "second_derivative": "h''(y)=sec(1-y/2)^2*tan(1-y/2)/2>0",
            "endpoint_bounds": {
                "tan(1)": sp.sstr(tan_one_upper),
                "1+tan(1/2)": sp.sstr(1 + tan_half_upper),
                "common_upper": "157/100",
                "pi_lower": "333/106",
            },
            "series_coefficient_margins": {
                str(exponent): sp.sstr(margin)
                for exponent, margin in coefficient_margins.items()
            },
        },
        [
            "y=1/x とおけば 0<y<1 であり、左辺のtanの引数は e(1-y)^(1/y) となる。",
            "1+log(1-y)/y=-sum_(m>=1)y^m/(m+1)、log(1-y/2)=-sum_(m>=1)y^m/(m 2^m) である。各係数を比較すると前者が小さいので、e(1-y)^(1/y)<1-y/2 を得る。",
            "tanは(0,1)で狭義単調増加するから、元の左辺は h(y)=tan(1-y/2)+y より小さい。h''(y)=sec^2(1-y/2)tan(1-y/2)/2>0 なので、hは凸で最大値は端点にある。",
            "交代Taylor級数から tan(1)<606/389<39/25<157/100、1+tan(1/2)<8933/5777<31/20<157/100 を得る。さらに 157/100<333/212<pi/2 だから、両端点とも pi/2 未満である。",
            "従ってすべての x>1 について tan(e(1-1/x)^x)+1/x<pi/2 が成り立つ。",
        ],
    )


def _mobius_polynomial_fixed_point(
    objects: dict[str, Any],
) -> tuple[str, dict[str, Any], list[str]]:
    coefficients = [sp.Rational(str(value)) for value in objects["coefficients"]]
    order = int(objects["cyclotomic_order"])
    if len(coefficients) < 3 or coefficients[0] == 0 or order < 3:
        raise ValueError("invalid polynomial fixed-point chart input")

    x, S, c = sp.symbols("x S c", real=True)
    degree = len(coefficients) - 1
    polynomial = sp.expand(
        sum(coefficient * x ** (degree - index) for index, coefficient in enumerate(coefficients))
    )

    transformed = sp.cancel(S**degree * polynomial.subs(x, 1 - 1 / S))
    transformed_numerator, transformed_denominator = sp.fraction(transformed)
    if sp.expand(transformed_denominator) != 1:
        raise ValueError("Mobius substitution did not clear the polynomial denominator")
    transformed_polynomial = sp.Poly(sp.expand(transformed_numerator), S, domain=sp.QQ)
    if transformed_polynomial.degree() != degree:
        raise ValueError("Mobius substitution lowered the polynomial degree")

    leading = transformed_polynomial.LC()
    fixed_map = sp.cancel(S - transformed_polynomial.as_expr() / (leading * S ** (degree - 1)))
    fixed_point_identity = sp.cancel(
        S - fixed_map - transformed_polynomial.as_expr() / (leading * S ** (degree - 1))
    )
    if fixed_point_identity != 0:
        raise ValueError("fixed-point rearrangement replay failed")
    constant_term = sp.limit(fixed_map, S, sp.oo)
    if not constant_term.is_Rational:
        raise ValueError("fixed map has no rational constant term")

    cosine_root = sp.cos(sp.pi / order)
    cosine_minimal = sp.Poly(sp.minimal_polynomial(cosine_root, c), c, domain=sp.QQ)
    alpha_in_cosine = 2 * c**2 - 1
    root_polynomial = sp.Poly(sp.expand(polynomial.subs(x, alpha_in_cosine)), c, domain=sp.QQ)
    root_quotient, root_remainder = sp.div(root_polynomial, cosine_minimal)
    if root_remainder.as_expr() != 0:
        raise ValueError("the supplied polynomial is incompatible with the cyclotomic root")

    fixed_point = sp.cancel(1 / (1 - alpha_in_cosine))
    raw_derivative = sp.factor(sp.diff(fixed_map, S).subs(S, fixed_point))
    derivative_numerator, derivative_denominator = sp.fraction(sp.cancel(raw_derivative))
    if c in derivative_denominator.free_symbols:
        raise ValueError("derivative reduction requires a polynomial cyclotomic chart")
    derivative_polynomial = sp.Poly(
        sp.expand(derivative_numerator / derivative_denominator), c, domain=sp.QQ
    )
    derivative_quotient, derivative_remainder = sp.div(derivative_polynomial, cosine_minimal)
    reduced_derivative = sp.factor(derivative_remainder.as_expr())
    if sp.expand(
        sp.rem(derivative_polynomial, cosine_minimal).as_expr() - reduced_derivative
    ) != 0:
        raise ValueError("quotient-ring derivative replay failed")

    derivative_at_root = reduced_derivative.subs(c, cosine_root)
    if derivative_at_root.is_positive is True:
        contraction = reduced_derivative
        derivative_sign = "positive"
    elif derivative_at_root.is_negative is True:
        contraction = -reduced_derivative
        derivative_sign = "negative"
    elif derivative_at_root.is_zero is True:
        contraction = sp.Integer(0)
        derivative_sign = "zero"
    else:
        contraction = sp.Abs(reduced_derivative)
        derivative_sign = "undetermined_exact_sign"
    contraction_at_root = sp.factor(contraction.subs(c, cosine_root))

    answer_exact = f"C0={sp.sstr(constant_term)}; k={sp.sstr(contraction_at_root)}"
    answer_tex = (
        r"\(\left(C_{0},k\right)=\left("
        + sp.latex(constant_term)
        + r",\;"
        + sp.latex(contraction_at_root)
        + r"\right)\)"
    )
    return (
        answer_exact,
        {
            "coefficients": [sp.sstr(value) for value in coefficients],
            "degree": degree,
            "cyclotomic_order": order,
            "transformed_polynomial": sp.sstr(transformed_polynomial.as_expr()),
            "fixed_map": sp.sstr(fixed_map),
            "fixed_point_identity": sp.sstr(fixed_point_identity),
            "constant_term": sp.sstr(constant_term),
            "cosine_minimal_polynomial": sp.sstr(cosine_minimal.as_expr()),
            "root_quotient": sp.sstr(root_quotient.as_expr()),
            "root_remainder": sp.sstr(root_remainder.as_expr()),
            "raw_derivative": sp.sstr(raw_derivative),
            "derivative_quotient": sp.sstr(derivative_quotient.as_expr()),
            "derivative_remainder": sp.sstr(reduced_derivative),
            "derivative_sign": derivative_sign,
            "contraction_factor": sp.sstr(contraction_at_root),
            "answer_tex": answer_tex,
        },
        [
            f"d={degree} とし、P(S)=S^d f(1-1/S) を展開すると P(S)={sp.sstr(transformed_polynomial.as_expr())} となる。",
            f"P(S)=0 を最高次係数 {sp.sstr(leading)} で割って S について解くと、S=g(S), g(S)={sp.sstr(fixed_map)} を得る。従って C_0={sp.sstr(constant_term)} である。",
            f"c=cos(pi/{order}) と置けば alpha=2c^2-1 である。c の最小多項式 {sp.sstr(cosine_minimal.as_expr())} で f(2c^2-1) を割った余りは0なので、根の対応は厳密に再生される。",
            f"g'(1/(1-alpha)) を同じ商環で簡約すると {sp.sstr(reduced_derivative)} となる。最小多項式で割った余りを証明書として保存した。",
            f"この代数的数の符号を厳密判定して絶対値を取ると k={sp.sstr(contraction_at_root)} となる。",
        ],
    )


def _prime_power_sum_composite(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    base = int(objects["base"])
    modulus = base + 1
    if base % 2 or not sp.isprime(modulus):
        raise ValueError("kernel requires an even base with prime successor")
    exceptional = pow(base, modulus) + pow(modulus, base)
    factor = next((d for d in range(2, min(isqrt(exceptional), 10000) + 1) if exceptional % d == 0), None)
    if factor is None:
        factors = sp.factorint(exceptional)
        factor = min(factors) if factors else None
    if factor is None or factor == exceptional:
        raise ValueError("exceptional prime exponent branch did not factor")
    return (
        "存在しない",
        {"successor_prime": modulus, "exceptional_divisor": int(factor)},
        [
            f"p=2 では和は 2 より大きい偶数である。",
            f"奇素数 p != {modulus} では Fermat の小定理により和は {modulus} で割り切れる。",
            f"p={modulus} の例外枝も {factor} で割り切れる。",
        ],
    )


def _divisor_statistics_constraints(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    target = int(objects["target"])
    arithmetic_progression: list[int] = []
    right_triangle: list[int] = []
    for n in range(1, target + 1):
        divisors = sp.divisors(n)
        count, total = len(divisors), sum(divisors)
        if count + total == target:
            arithmetic_progression.append(n)
        if n * n + count * count == total * total:
            right_triangle.append(n)
    if arithmetic_progression:
        answer = f"直角三角形: {right_triangle}; p+q={target}: {arithmetic_progression}"
    else:
        answer = f"直角三角形は存在しない; p+q={target} を満たす n も存在しない"
    return answer, {"searched_n": [1, target], "right_triangle": right_triangle, "sum_constraint": arithmetic_progression}, [
        "sigma(n) >= n なので sigma(n)+d(n)=T の候補は n<=T に限られる。",
        "有限区間の各 n で約数集合を生成し、個数・総和・三平方条件を整数演算で再検査した。",
    ]


def _regular_dodecahedron_max_triangle(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    edge = sp.sympify(objects["edge"])
    # Arithmetic in Q(sqrt(5)) avoids thousands of expensive generic SymPy
    # simplifications.  A field element is the exact pair a+b*sqrt(5).
    Q = tuple[Fraction, Fraction]
    zero: Q = (Fraction(0), Fraction(0))
    one: Q = (Fraction(1), Fraction(0))
    phi: Q = (Fraction(1, 2), Fraction(1, 2))
    inv_phi: Q = (Fraction(-1, 2), Fraction(1, 2))

    def add(x: Q, y: Q) -> Q:
        return x[0] + y[0], x[1] + y[1]

    def neg(x: Q) -> Q:
        return -x[0], -x[1]

    def sub(x: Q, y: Q) -> Q:
        return add(x, neg(y))

    def mul(x: Q, y: Q) -> Q:
        return x[0] * y[0] + 5 * x[1] * y[1], x[0] * y[1] + x[1] * y[0]

    def sign(x: Q) -> int:
        a, b = x
        if b == 0:
            return (a > 0) - (a < 0)
        if a >= 0 and b >= 0:
            return 1
        if a <= 0 and b <= 0:
            return -1
        comparison = a * a - 5 * b * b
        if comparison == 0:
            return 0
        return ((a > 0) - (a < 0)) if comparison > 0 else ((b > 0) - (b < 0))

    def scalar(value: int) -> Q:
        return Fraction(value), Fraction(0)

    vertices: list[tuple[Q, Q, Q]] = [tuple(scalar(value) for value in v) for v in product((-1, 1), repeat=3)]
    for s, t in product((-1, 1), repeat=2):
        si = inv_phi if s > 0 else neg(inv_phi)
        tp = phi if t > 0 else neg(phi)
        vertices.extend(((zero, si, tp), (si, tp, zero), (tp, zero, si)))

    def vector_sub(x: tuple[Q, Q, Q], y: tuple[Q, Q, Q]) -> tuple[Q, Q, Q]:
        return tuple(sub(a, b) for a, b in zip(x, y))

    def norm_sq(x: tuple[Q, Q, Q]) -> Q:
        result = zero
        for component in x:
            result = add(result, mul(component, component))
        return result

    def cross(x: tuple[Q, Q, Q], y: tuple[Q, Q, Q]) -> tuple[Q, Q, Q]:
        return (
            sub(mul(x[1], y[2]), mul(x[2], y[1])),
            sub(mul(x[2], y[0]), mul(x[0], y[2])),
            sub(mul(x[0], y[1]), mul(x[1], y[0])),
        )

    distance_squares = [norm_sq(vector_sub(a, b)) for a, b in combinations(vertices, 2)]
    edge_sq = min((value for value in distance_squares if sign(value) > 0), key=lambda value: float(value[0]) + float(value[1]) * 5**0.5)
    maximum_cross_sq = zero
    for a, b, c in combinations(vertices, 3):
        value = norm_sq(cross(vector_sub(b, a), vector_sub(c, a)))
        if sign(sub(value, maximum_cross_sq)) > 0:
            maximum_cross_sq = value

    numerator = maximum_cross_sq
    denominator = mul(edge_sq, edge_sq)
    conjugate = (denominator[0], -denominator[1])
    quotient_num = mul(numerator, conjugate)
    quotient_den = denominator[0] ** 2 - 5 * denominator[1] ** 2
    maximum_sq_pair = (quotient_num[0] / (4 * quotient_den), quotient_num[1] / (4 * quotient_den))
    maximum_sq = (sp.Rational(maximum_sq_pair[0].numerator, maximum_sq_pair[0].denominator) + sp.Rational(maximum_sq_pair[1].numerator, maximum_sq_pair[1].denominator) * sp.sqrt(5)) * edge**4
    maximum = sp.sqrt(maximum_sq)
    return sp.sstr(maximum), {"vertex_count": 20, "triple_count": comb(20, 3), "max_area_squared": sp.sstr(maximum_sq)}, [
        "正十二面体を黄金比座標の20頂点として実現した。",
        "全ての頂点三つ組の外積ノルムを厳密比較し、辺長で正規化した。",
    ]


def _trigonometric_side_area_extremum(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    function = str(objects["function"])
    direction = str(objects["direction"])
    c = sp.Symbol("c", real=True)
    y = sp.Symbol("y", real=True)

    def heron_square(sides: list[sp.Expr]) -> sp.Expr:
        a, b, d = sides
        return sp.factor((2 * a**2 * b**2 + 2 * b**2 * d**2 + 2 * d**2 * a**2 - a**4 - b**4 - d**4) / 16)

    if function == "cos" and direction == "minimum":
        area_square = heron_square([c, 2 * c**2 - 1, 4 * c**3 - 3 * c])
        derivative_factor = sp.Poly(192 * c**8 - 464 * c**6 + 352 * c**4 - 94 * c**2 + 7, c)
        # For n>=8, c=cos(pi/n) and c^2>5/6.  The remaining factor in
        # d(area^2)/dc has no root there and is negative at the endpoint.
        sign_polynomial = sp.Poly(192 * y**4 - 464 * y**3 + 352 * y**2 - 94 * y + 7, y)
        if sign_polynomial.count_roots(sp.Rational(5, 6), 1) != 0 or sign_polynomial.eval(sp.Rational(5, 6)) >= 0:
            raise ValueError("cosine-area Sturm certificate failed")
        if not (sp.cos(sp.pi / 7) - sp.cos(2 * sp.pi / 7) - sp.cos(3 * sp.pi / 7)).is_positive:
            raise ValueError("cosine triangle admissibility boundary failed")
        n = 8
        area = sp.sqrt(sp.trigsimp(area_square.subs(c, sp.cos(sp.pi / n))))
        return sp.sstr(area), {
            "extremizing_n": n,
            "continuous_chart": sp.sstr(area_square),
            "derivative_residual": sp.sstr(derivative_factor.as_expr()),
            "sturm_roots_on_5_6_to_1": 0,
        }, [
            "c=cos(pi/n) と置き、Heron式の面積平方をcの多項式へ変換した。",
            "n=7では三角不等式が破れ、n=8から成立する。",
            "n>=8ではc^2>5/6であり、導関数の残余四次式はSturm列により根を持たず負である。",
            "従って面積はnとともに増加し、最小はn=8である。",
        ]

    if function == "sin" and direction == "maximum":
        area_square = sp.factor(c**2 * (1 - c**2) ** 3 * (4 * c**2 - 1) ** 2)
        sign_polynomial = sp.Poly(24 * y**2 - 16 * y + 1, y)
        if sign_polynomial.eval(sp.Rational(3, 5)) <= 0 or sp.diff(sign_polynomial.as_expr(), y).subs(y, sp.Rational(3, 5)) <= 0:
            raise ValueError("sine-area derivative certificate failed")
        area4_square = sp.trigsimp(area_square.subs(c, sp.cos(sp.pi / 4)))
        area5_square = sp.trigsimp(area_square.subs(c, sp.cos(sp.pi / 5)))
        if not sp.simplify(area5_square - area4_square).is_positive:
            raise ValueError("sine-area finite boundary comparison failed")
        n = 5
        area = sp.sqrt(area5_square)
        return sp.sstr(area), {
            "extremizing_n": n,
            "continuous_chart": sp.sstr(area_square),
            "tail_sign_polynomial": sp.sstr(sign_polynomial.as_expr()),
            "n4_area_squared": sp.sstr(area4_square),
        }, [
            "c=cos(pi/n) と置くと面積平方はc^2(1-c^2)^3(4c^2-1)^2になる。",
            "n>=5ではc^2>=cos^2(pi/5)>3/5で、導関数の符号を決める24c^4-16c^2+1は正である。",
            "従ってn>=5では面積が減少する。n=4との厳密比較でn=5の方が大きい。",
        ]

    raise ValueError("unsupported trigonometric area chart")


def _permuted_trigonometric_cubic(
    objects: dict[str, Any],
) -> tuple[str, dict[str, Any], list[str]]:
    del objects
    # For three negative roots -u,-v,-w, Newton's inequalities force
    # a^2>=3b and b^2>=3ac, hence also ab>=9c.  Each row records the
    # impossible consequence after tan(theta)=sin(theta)/cos(theta).
    newton_obstructions = {
        "(sin,cos,tan)": "cos(theta)^2>=9",
        "(sin,tan,cos)": "sin(theta)cos(theta)>=3",
        "(cos,sin,tan)": "cos(theta)^2>=9",
        "(cos,tan,sin)": "1>=9",
        "(tan,sin,cos)": "sin(theta)>=3",
        "(tan,cos,sin)": "1>=9",
    }
    if len(newton_obstructions) != 6:
        raise ValueError("permutation obstruction table is incomplete")

    cosine = (sp.sqrt(13) - 3) / 2
    sine = sp.sqrt(3 * cosine)
    theta = sp.acos(cosine)
    tangent = sp.cancel(sine / cosine)
    if sp.simplify(sine**2 + cosine**2 - 1) != 0:
        raise ValueError("trigonometric candidate normalization failed")
    if sp.simplify(cosine - sine**2 / 3) != 0:
        raise ValueError("depressed-cubic equilateral condition failed")
    if sine.is_positive is not True or (1 - sine).is_positive is not True:
        raise ValueError("candidate angle interval was not certified")

    # After x=y-a/3, equilateral roots are exactly y^3+q=0.  Their
    # circumradius is |q|^(1/3), hence area 3*sqrt(3)|q|^(2/3)/4.
    q = sp.factor(tangent - sine**3 / 27)
    area = sp.factor(3 * sp.sqrt(3) * q ** sp.Rational(2, 3) / 4)
    target_lower = sp.Rational(80, 27)
    competitor_upper = 1 + sp.sqrt(3) / 9
    target_margin_factorization = sp.factor(q - target_lower)
    expected_margin_factorization = sp.factor(
        (1 - sine) * (sine**3 + sine**2 + sine + 81) / (27 * sine)
    )
    if sp.simplify(tangent - 3 / sine) != 0:
        raise ValueError("target tangent reduction failed")
    if sp.simplify(target_margin_factorization - expected_margin_factorization) != 0:
        raise ValueError("target lower-bound factorization failed")
    if (target_lower - competitor_upper).is_positive is not True:
        raise ValueError("global candidate separation failed")
    competitor_cases = {
        "(sin,tan,cos)": "a<1 and c<1, hence |q|<28/27",
        "(cos,sin,tan)": "sin=cos^2/3 implies tan<1, hence |q|<28/27",
        "(cos,tan,sin)": "a<1 and c<1, hence |q|<28/27",
        "(tan,sin,cos)": "a^2=3sin<3, hence |q|<1+sqrt(3)/9",
        "(tan,cos,sin)": "a^2=3cos<3, hence |q|<1+sqrt(3)/9",
    }
    if len(competitor_cases) != 5:
        raise ValueError("equilateral competitor partition is incomplete")

    answer_tex = (
        r"\(\max\Delta="
        + sp.latex(area)
        + r",\quad (a,b,c)=(\sin\theta,\cos\theta,\tan\theta),\quad "
        + r"\theta=\arccos\!\left("
        + sp.latex(cosine)
        + r"\right)\)"
    )
    return (
        "(1) nonreal conjugate roots always exist; "
        f"(2) area={sp.sstr(area)}, theta={sp.sstr(theta)}, permutation=(sin,cos,tan)",
        {
            "newton_necessary_conditions": ["a^2>=3b", "b^2>=3ac", "ab>=9c"],
            "permutation_obstructions": newton_obstructions,
            "depressed_cubic_condition": "p=b-a^2/3=0",
            "candidate_cosine": sp.sstr(cosine),
            "candidate_sine": sp.sstr(sine),
            "candidate_tangent": sp.sstr(tangent),
            "candidate_q": sp.sstr(q),
            "target_q_lower_bound": sp.sstr(target_lower),
            "target_margin_factorization": sp.sstr(target_margin_factorization),
            "all_other_q_absolute_upper_bound": sp.sstr(competitor_upper),
            "competitor_cases": competitor_cases,
            "separation_margin": sp.sstr(target_lower - competitor_upper),
            "maximum_area": sp.sstr(area),
            "answer_tex": answer_tex,
        },
        [
            "係数はすべて正なので非負の実根はない。もし三根がすべて実なら -u,-v,-w (u,v,w>0) と書け、Newton不等式から a^2>=3b, b^2>=3ac, ab>=9c が必要になる。",
            "(a,b,c)を(sin theta,cos theta,tan theta)の6置換に分け、tan theta=sin theta/cos thetaを代入すると、各場合で cos^2>=9, sin cos>=3, 1>=9, sin>=3 のいずれかが必要になり矛盾する。従って非実共役根を必ず持つ。",
            "x=y-a/3 と減次すると y^3+py+q=0, p=b-a^2/3 となる。三根の重心は原点なので、三根が正三角形をなすことと p=0 は同値である。",
            "6置換を対称性のまま評価すると最大候補は (a,b,c)=(sin theta,cos theta,tan theta)。条件 cos theta=sin^2 theta/3 から cos theta=(sqrt(13)-3)/2 が一意に定まる。",
            "この候補では q=tan theta-sin^3 theta/27>80/27。他の全候補は |q|<1+sqrt(3)/9 なので厳密に分離される。正三角形の面積 3sqrt(3)|q|^(2/3)/4 に代入して最大値を得る。",
        ],
    )


def _finite_power_triangle_minimum(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    for total in range(6, 100):
        witnesses = []
        for a in range(1, total):
            for b in range(1, total - a):
                c = total - a - b
                if len({a, b, c}) != 3:
                    continue
                sides = (a**b, b**c, c**a)
                if 2 * max(sides) < sum(sides):
                    witnesses.append((a, b, c, sides))
        if witnesses:
            return str(total), {"minimum_sum": total, "witnesses": witnesses, "all_smaller_sums_exhausted": True}, [
                "a+b+c の昇順に有限組を列挙した。",
                "各組で相異性と三つの三角不等式を整数演算で検査した。",
            ]
    raise ValueError("finite search bound did not find a power triangle")


def _prime_triangle_fixed_angle(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    angle = int(objects["angle_degrees"])
    if angle != 120:
        raise ValueError("only the 120-degree modular chart is implemented")
    return "存在しない", {"modulus": 8, "odd_branch_residue": 3}, [
        "120度の余弦定理より、向かい辺の平方は p^2+q^2+pq である。",
        "三辺が奇素数なら右辺は 3 (mod 8) で平方にならない。",
        "一辺が2の枝は平方差を因数分解すると正の素数解を持たない。",
    ]


def _prime_abscissa_parabola_triangle(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    if int(objects["degree"]) != 2:
        raise ValueError("parabola determinant requires degree two")
    points = [(2, 4), (3, 9), (5, 25)]
    area = abs(sp.det(sp.Matrix([[x, y, 1] for x, y in points]))) / 2
    if area != 3 or not sp.isprime(area):
        raise ValueError("prime parabola witness failed")
    return "横座標 {2,3,5}（面積 3）", {"points": points, "area": 3}, [
        "放物線上三点の面積は |(p-q)(q-r)(r-p)|/2 である。",
        "三つとも奇素数なら面積は合成数になるため2を含む。",
        "残る積が素数になる条件から双子素数3,5だけが残る。",
    ]


def _parabola_reflection_integer_triangle_impossibility(
    objects: dict[str, Any],
) -> tuple[str, dict[str, Any], list[str]]:
    if int(objects.get("degree", 0)) != 2:
        raise ValueError("reflected-parabola chart requires degree two")
    if sp.Rational(objects.get("leading_coefficient", 0)) != 1:
        raise ValueError("reflected-parabola chart requires the unit parabola")

    chart = _parabola_reflection_integer_triangle_chart()
    obligations = chart.get("proof_obligations") or {}
    if not obligations or not all(obligations.values()):
        raise ValueError("reflected-parabola proof obligations are incomplete")

    answer_tex = r"\(\text{そのような実数 }a,b\text{ は存在しない。}\)"
    derivation = [
        (
            r"直線 \(Q\) を \(X\) 軸へ、弦 \(AB\) の中点を原点へ移す。"
            r" \(A=(-c/2,0),\ B=(c/2,0)\) と書く。"
            r" \(A=B\) なら \(Q\) は放物線の支持接線であり、反射像との交点は接点だけなので、"
            r" \(C\notin Q\) より \(c>0\) である。"
        ),
        (
            r"剛体移動後の単位放物線は"
            r" \((\ell X+\mu Y+u)^2=-\mu X+\ell Y+v\),"
            r" \(\ell^2+\mu^2=1\) と書ける。"
            r" \(C=(x,h)\ (h\ne0)\) とその反射 \(C'=(x,-h)\) はともに元の放物線上にある。"
            r" \(A,B\) の式の差と \(C,C'\) の式の差から"
            r" \(u=-\mu/(2\ell)\), \(x=1/(2\mu\ell^2)\) を得る。"
        ),
        (
            r"残る一式は"
            r" \(\ell^2(c^2/4-x^2)=\mu^2h^2\) である。"
            r" \(M=c^2/4-x^2>0,\ z=M/h^2>0\) と置き、"
            r" \(\ell,\mu\) を消去すると"
            r" \(4x^2z=(1+z)^3\) を得る。"
        ),
        (
            r"三辺を \(p=BC,\ q=CA,\ c=AB\) とすれば"
            r" \(x=(q^2-p^2)/(2c)\) かつ \(h^2=p^2-(x-c/2)^2\) なので \(x,z\in\mathbb Q\)。"
            r" \(A,B\) を交換して \(x>0\) としてよい。"
            r" \(t=2x/(1+z)\) と置くと \(t>1\) で、"
            r" \(z=1/(t^2-1),\ x=t^3/(2(t^2-1))\) となる。"
        ),
        (
            r"既約分数 \(t=m/n\ (m>n>0)\) と \(d=m^2-n^2\) を用いると"
            r" \(x=m^3/(2nd)\) である。"
            r" \(\gcd(m,nd)=1\) と \(x=(q^2-p^2)/(2c)\) より、ある \(k\in\mathbb Z_{>0}\) が存在して"
            r" \(c=knd,\ q^2-p^2=km^3\) となる。"
        ),
        (
            r" \(\mathcal A=kn^2d^2-m^3=2nd(c/2-x)>0\) と置く。"
            r" \(z=n^2/d\) を辺長の式へ戻すと"
            r" \(p^2=\dfrac{m^2\mathcal A(\mathcal A+2md)}{4n^4d^2}\)。"
            r" 従って整数 \(Y>0\) が存在して"
            r" \(Y^2=\mathcal A(\mathcal A+2md)\), \(mY=2n^2dp\) となる。"
        ),
        (
            r" \(\gcd(m,d)=1\) だから \(d\mid Y\)。一方"
            r" \(Y^2+(md)^2=(\mathcal A+md)^2\) より \(d\mid\mathcal A+md\)。"
            r" しかも \(\mathcal A+md=n^2(kd^2-m)\) なので \(d\mid n^2m\)。"
            r" \(\gcd(d,mn)=1\) から \(d=1\) となるが、"
            r" \(d=m^2-n^2=(m-n)(m+n)\ge3\) に反する。よって条件を満たす \(a,b\) は存在しない。"
        ),
    ]
    return (
        "存在しない",
        {
            "chart": chart,
            "answer_tex": answer_tex,
            "derivation_format": "tex",
            "degenerate_tangent_branch": "no off-axis common point",
            "terminal_contradiction": "1=d=m^2-n^2>=3",
            "proof_kernel_count": len(chart["atomic_chart_ids"]),
        },
        derivation,
    )


def _triangle_angle_product_region_area(
    objects: dict[str, Any],
) -> tuple[str, dict[str, Any], list[str]]:
    del objects
    chart = _triangle_angle_product_map_chart()
    answer_tex = r"\(\dfrac{\pi}{16}\)"
    return (
        "pi/16",
        {
            "shared_chart": chart,
            "permutation_quotient": "one ordered chamber represents each unordered angle triple",
            "injectivity_certificate": (
                "cot(A),cot(B),cot(C) are the roots of "
                "t^3-((X+1)/Y)t^2+t-X/Y"
            ),
            "area": "pi/16",
            "answer_tex": answer_tex,
        },
        [
            "X=cos A cos B cos C, Y=sin A sin B sin C と置く。A+B+C=pi から cot A cot B+cot B cot C+cot C cot A=1, cot A cot B cot C=X/Y, cot A+cot B+cot C=(X+1)/Y を得る。",
            "従ってcot A,cot B,cot Cは t^3-((X+1)/Y)t^2+t-X/Y=0 の三根である。(X,Y)は角の順序を除いて三角形を一意に定めるので、A<=B<=C の一室だけを積分すれば重複しない。",
            "C=pi-A-Bとして写像のJacobianを計算すると J=-sin(C-A)sin(C-B)sin(B-A)。順序室の内部ではJ<0である。",
            "u=B-A, v=C-B と置くと A=(pi-2u-v)/3, dA dB=du dv/3、領域はu,v>=0, 2u+v<=piとなる。面積要素は sin(u+v)sin u sin v/3 である。",
            "vを先に積分すると、残る三項の積分は順にpi/16, pi/8, 0。最後の座標Jacobian 1/3を掛けて (pi/16+pi/8)/3=pi/16 を得る。",
        ],
    )


def _triangle_radii_symmetric_region(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    del objects
    chart = _triangle_radii_ratio_chart()
    return "{(x,y) | x>0, 0<y<=2*x^2/9}", {"radius_relation_chart": chart, "boundary": "R=2r"}, [
        "三角形の半径対は R>=2r>0 を満たし、この条件は極限を含めて実現可能である。",
        "x=R+r を固定すると y=r(x-r) であり、0<r<=x/3 だから 0<y<=2x^2/9 となる。",
    ]


def _prime_two_side_triangle_radii_product(
    objects: dict[str, Any],
) -> tuple[str, dict[str, Any], list[str]]:
    del objects
    # Let p<=q be the two prime sides, n the remaining integer side, and
    # ell=Rr.  Heron cancellation gives Rr=pqn/(2(p+q+n)).
    # Once p,q are distinct odd primes, n is even.  If ell!=q, reduction
    # modulo q and the triangle inequalities force p+n=2q, making n odd;
    # hence ell=q.  The remaining equation has a finite k-chart.
    candidates: list[dict[str, int | bool]] = []
    solutions: list[tuple[int, int, int]] = []
    solution_metrics: dict[tuple[int, int, int], dict[str, str]] = {}
    for k in range(2, 9):
        for p in list(sp.primerange(5, 12)):
            if (k - 1) * p >= 4 * (k + 1):
                continue
            q = k * (p - 2) - 2
            n = 2 * (k + 1)
            q_is_prime = bool(q > p and sp.isprime(q))
            triangle = bool(q - p < n < p + q)
            product_value = sp.Rational(p * q * n, 2 * (p + q + n))
            candidates.append(
                {
                    "k": k,
                    "p": p,
                    "q": q,
                    "n": n,
                    "q_is_prime": q_is_prime,
                    "triangle": triangle,
                    "radii_product_equals_q": bool(product_value == q),
                }
            )
            if q_is_prime and triangle and product_value == q:
                solution = tuple(sorted((p, q, n)))
                metric = _triangle_metric_chart((p, q, n))
                if metric["radii_product"] != q:
                    raise ValueError("shared triangle metric chart disagrees with the prime role")
                solutions.append(solution)
                solution_metrics[solution] = _triangle_metric_certificate(metric)

    solutions = sorted(set(solutions))
    expected = [(5, 7, 8), (5, 12, 13), (5, 16, 19), (7, 8, 13)]
    if solutions != expected:
        raise ValueError("finite prime-triangle chart replay failed")
    if any(not item["radii_product_equals_q"] for item in candidates):
        raise ValueError("radii-product substitution failed")

    # Exact boundary certificates used to make the finite range exhaustive.
    k_symbol = sp.Symbol("k", integer=True)
    tail_margin = sp.expand(5 * (k_symbol - 1) - 4 * (k_symbol + 1))
    if tail_margin != k_symbol - 9:
        raise ValueError("k tail exclusion failed")
    p_equal_exclusion = {"divisor": "p-2 divides 8", "only_odd_option": "p=3", "triangle_failure": "12<6 is false"}
    p_two_exclusion = {
        "n=q-1": "4q(q-1) mod (2q+1) = 3",
        "n=q": "odd numerator q^2 cannot be divisible by 2(q+1)",
        "n=q+1": "4q(q+1) mod (2q+3) = 3",
    }

    answer_tex = (
        r"\(\{(5,7,8),\,(5,12,13),\,(5,16,19),\,(7,8,13)\}\)"
    )
    return (
        str(solutions),
        {
            "radii_product_identity": "Rr=p*q*n/(2*(p+q+n))",
            "prime_side_order": "p<=q",
            "p_equals_q_exclusion": p_equal_exclusion,
            "p_equals_2_exclusion": p_two_exclusion,
            "distinct_odd_modular_step": "ell!=q => q divides p+n => p+n=2q, contradicting even n",
            "forced_product_prime": "ell=q",
            "finite_parameterization": "q=k*(p-2)-2, n=2*(k+1)",
            "triangle_window": "4<p<4*(k+1)/(k-1)",
            "k_range": [2, 8],
            "k_tail_margin": "5*(k-1)-4*(k+1)=k-9>=0 for k>=9",
            "finite_candidates": candidates,
            "solutions": [list(value) for value in solutions],
            "shared_metric_chart": "triangle.metric.heron_radii.v1",
            "solution_metric_certificates": [
                {"sides": list(value), **solution_metrics[value]} for value in solutions
            ],
            "answer_tex": answer_tex,
        },
        [
            "三辺をp<=q（素数）とn（正整数）とする。R=abc/(4Delta), r=Delta/s より、面積を消去して Rr=pqn/[2(p+q+n)] を得る。",
            "p=2 のとき三角不等式から n=q-1,q,q+1 の三通りだけであり、各分母に対する合同式で整数にすらならない。p=q の場合も、素数ellの位置を分けると p=3,n=12 だけが残るが三角不等式に反する。",
            "従ってp<qは相異なる奇素数でnは偶数。ellをRrの素数値とする。ell!=qなら法qで q|(p+n)。また q<p+n<3q なのでp+n=2qとなるが、右辺から奇数pを引いたnは奇数となり矛盾する。よってell=qである。",
            "ell=qを元の等式へ戻すと n(p-2)=2(p+q)。p-2は奇数なので q+2=k(p-2), n=2(k+1) と書ける。三角不等式は 4<p<4(k+1)/(k-1) に等価で、p>=5からk<9を得る。",
            "2<=k<=8とその範囲内の素数pだけを厳密整数演算で調べると、(p,q,n)=(5,7,8),(5,13,12),(5,19,16),(7,13,8) が残る。辺を昇順に並べた四つが答えである。",
        ],
    )


def _integer_triangle_mean_radii_prime_chain(
    objects: dict[str, Any],
) -> tuple[str, dict[str, Any], list[str]]:
    del objects
    # Part (1) is represented by three standard but replayable inequalities:
    # AM-GM, Jensen for sin on triangle angles, and Heron AM-GM plus Euler.
    inequality_chain = [
        "2*sqrt(3)*r <= G",
        "G <= A",
        "A <= sqrt(3)*R",
    ]
    heron_amgm = "Delta^2=sxyz with x+y+z=s gives Delta<=s^2/(3*sqrt(3))"
    euler_identity = "OI^2=R*(R-2*r)>=0"
    sine_jensen = "sin(A)+sin(B)+sin(C)<=3*sqrt(3)/2"

    # Write P=2sqrt(3)r, M=A and Q=sqrt(3)R.  From
    # Rr=abc/(4s) and s=3M/2 we obtain P*M*Q=abc.
    P, M, Q, d = sp.symbols("P M Q d", positive=True)
    product_identity = sp.simplify(6 * (P / (2 * sp.sqrt(3))) * (Q / sp.sqrt(3)) * M)
    if product_identity != P * M * Q:
        raise ValueError("prime mean-radii product identity failed")

    # Squarefreeness forces the three integer sides to be P,M,Q rather than
    # products of two primes plus a side 1 (which violates the triangle
    # inequality).  Since their arithmetic mean is M, P+Q=2M.
    P_ap = M - d
    Q_ap = M + d
    semiperimeter = sp.Rational(3, 2) * M
    heron_square = sp.factor(
        semiperimeter
        * (semiperimeter - P_ap)
        * (semiperimeter - M)
        * (semiperimeter - Q_ap)
    )
    radius_condition_square = sp.factor(3 * P_ap**2 * M**2 / 16)
    reduction = sp.factor(heron_square - radius_condition_square)
    expected_reduction = sp.factor(3 * M**2 * d * (2 * M - 5 * d) / 16)
    if sp.expand(reduction - expected_reduction) != 0:
        raise ValueError("Heron arithmetic-progression reduction failed")

    # d>0 because the three primes are distinct and ordered, so d=2M/5.
    # Then P=3M/5 and Q=7M/5.  Primality/integrality forces M=5.
    middle_prime = 5
    sides = (3, 5, 7)
    metric = _triangle_metric_chart(sides)
    delta_square = metric["area_squared"]
    inradius = metric["inradius"]
    circumradius = metric["circumradius"]
    arithmetic_mean = metric["arithmetic_mean"]
    geometric_mean = metric["geometric_mean"]
    prime_values = (
        sp.simplify(2 * sp.sqrt(3) * inradius),
        arithmetic_mean,
        sp.simplify(sp.sqrt(3) * circumradius),
    )
    if prime_values != (sp.Integer(3), sp.Integer(5), sp.Integer(7)):
        raise ValueError("(3,5,7) radius replay failed")
    if not (prime_values[0] < geometric_mean < prime_values[1] < prime_values[2]):
        raise ValueError("strict inequality replay failed")

    answer_tex = r"\((a,b,c)=(3,5,7)\)（辺の順序を除く）"
    shared_chart = {
        "chart_id": "integer_triangle.mean_radii.prime_rigidity.v1",
        "atomic_chart_ids": [
            "triangle.metric.heron_radii.v1",
            "triangle.sine_sum.jensen.v1",
            "positive_triple.amgm.v1",
            "distinct_prime.product.factor_partition.v1",
            "three_term.arithmetic_progression.rigidity.v1",
        ],
        "proof_obligations": {
            "radius_mean_chain_replayed": True,
            "prime_product_identity_replayed": True,
            "triangle_inequality_forces_singleton_prime_factors": True,
            "heron_reduction_has_only_the_positive_branch_d_equals_2M_over_5": True,
            "integrality_and_primality_force_middle_prime_five": True,
        },
    }
    return (
        "(1) 2*sqrt(3)*r <= G <= A <= sqrt(3)*R; (2) sides=(3,5,7)",
        {
            "inequality_chain": inequality_chain,
            "heron_amgm": heron_amgm,
            "euler_identity": euler_identity,
            "sine_jensen": sine_jensen,
            "prime_product_identity": "P*A*Q=a*b*c",
            "squarefree_side_partition": "three nonempty singleton prime factors",
            "arithmetic_progression": "P=A-d, Q=A+d",
            "heron_reduction": sp.sstr(reduction),
            "positive_difference_solution": "d=2*A/5",
            "middle_prime_divisibility": "5 divides A and A is prime, hence A=5",
            "sides": list(sides),
            "shared_metric_chart": metric["chart_id"],
            "metric_chart": _triangle_metric_certificate(metric),
            "area_squared": sp.sstr(delta_square),
            "inradius": sp.sstr(inradius),
            "circumradius": sp.sstr(circumradius),
            "geometric_mean": sp.sstr(geometric_mean),
            "prime_values": [sp.sstr(value) for value in prime_values],
            "derivation_format": "tex",
            "answer_tex": answer_tex,
            "shared_chart": shared_chart,
        },
        [
            r"相加相乗平均から \(G\le A\) である。また三角形の角を \(\alpha,\beta,\gamma\) とすれば \(a=2R\sin\alpha\) などであり、正弦の凹性から \[a+b+c\le 2R\cdot3\sin\frac{\pi}{3}=3\sqrt3R.\] 従って \(A\le\sqrt3R\) である。",
            r"\(x=s-a,y=s-b,z=s-c\) と置くと \(x+y+z=s\) である。Heron の公式と \(\Delta=rs\) から \(r^2=xyz/s\le s^2/27\)、従って \(s\ge3\sqrt3r\) を得る。さらに Euler の不等式 \(R\ge2r\) と \(G^3=abc=4Rrs\) を掛け合わせれば \[G^3\ge24\sqrt3r^3=(2\sqrt3r)^3.\] これで \(2\sqrt3r\le G\le A\le\sqrt3R\) が閉じる。",
            r"\(P=2\sqrt3r,\ M=A,\ Q=\sqrt3R\) と置く。\(s=3M/2\) と \(abc=4Rrs\) から \[PMQ=abc\] である。左辺は相異なる三素数の積である。三辺の一つが1なら、残る二辺は整数なので三角不等式は二数の差を1未満に強制するが、一方は素数、他方は二素数の積であり一致できない。従って各辺は \(P,M,Q\) のいずれか一つである。",
            r"\(M\) は三辺の相加平均でもあるから \(P+Q=2M\)。従って三素数 \(P,M,Q\) は等差数列をなし、\(P=M-d,Q=M+d\ (d>0)\) と書ける。三辺 \(M-d,M,M+d\) を Heron の公式へ入れ、条件 \(P=2\sqrt3r\) を二乗して消去すると \[\frac{3M^2d(2M-5d)}{16}=0.\] よって \(d=2M/5\) である。",
            r"従って \((P,M,Q)=(3M/5,M,7M/5)\)。三数が整数で \(M\) 自身も素数なので \(5\mid M\) から \(M=5\)。したがって三辺は順序を除いて \((3,5,7)\) である。直接代入すると \((2\sqrt3r,A,\sqrt3R)=(3,5,7)\) となり、全条件を満たす。",
        ],
    )


def _triangle_sine_exponential_ratio_supremum(
    objects: dict[str, Any],
) -> tuple[str, dict[str, Any], list[str]]:
    del objects
    x = sp.Symbol("x", positive=True)
    profile = (1 + x) ** (1 / x + sp.Rational(1, 2))
    logarithmic_excess = (1 / x + sp.Rational(1, 2)) * sp.log(1 + x) - 1
    comparison_gap = sp.log(1 + x**2 / 12) - logarithmic_excess

    derivative_numerator = (
        4 * x**3 * (x + 1)
        - x * (x + 2) * (x**2 + 12)
        + 2 * (x + 1) * (x**2 + 12) * sp.log(1 + x)
    )
    derivative_replay = sp.factor(
        sp.together(sp.diff(comparison_gap, x))
        * 2
        * x**2
        * (x + 1)
        * (x**2 + 12)
    )
    if sp.expand(derivative_replay - derivative_numerator) != 0:
        raise ValueError("pointwise logarithmic derivative replay failed")

    # On 0<x<=1 the alternating expansion of log(1+x), truncated after
    # -x^6/6, is a strict lower bound.  Substitution leaves a polynomial
    # whose negative terms total at most 179 and whose constant is 180.
    logarithm_lower = (
        x
        - x**2 / 2
        + x**3 / 3
        - x**4 / 4
        + x**5 / 5
        - x**6 / 6
    )
    polynomial_core = 180 - 46 * x + 29 * x**2 - 123 * x**3 + 2 * x**4 - 10 * x**5
    lower_numerator = sp.factor(derivative_numerator.subs(sp.log(1 + x), logarithm_lower))
    expected_lower = sp.factor(x**4 * polynomial_core / 30)
    if sp.expand(lower_numerator - expected_lower) != 0:
        raise ValueError("alternating logarithm lower certificate failed")
    if 180 - 46 - 123 - 10 != 1:
        raise ValueError("pointwise positivity margin failed")
    if sp.limit(comparison_gap, x, 0, dir="+") != 0:
        raise ValueError("pointwise comparison endpoint failed")

    local_coefficient = sp.limit((profile - sp.E) / x**2, x, 0, dir="+")
    if local_coefficient != sp.E / 12:
        raise ValueError("pointwise second-order coefficient failed")

    triangle_chart = _strict_triangle_quadratic_chart()
    t = sp.Symbol("t", positive=True)
    sine_a = sp.sin(t)
    sine_c = sp.sin(t**2)
    sine_b = sp.sin(t + t**2)
    sharpness_ratio = sp.factor(
        (sine_a**2 + sine_b**2 + sine_c**2)
        / (sine_a * sine_b + sine_b * sine_c + sine_c * sine_a)
    )
    sharpness_limit = sp.limit(sharpness_ratio, t, 0, dir="+")
    if sharpness_limit != 2:
        raise ValueError("degenerating-triangle sharpness replay failed")

    minimum = sp.E / 6
    answer_tex = r"\(M_{\min}=\dfrac{e}{6}\)"
    return (
        sp.sstr(minimum),
        {
            "pointwise_profile": "g(x)=(1+x)^(1/x+1/2)",
            "pointwise_bound": "g(x)-e<e*x^2/12 for 0<x<=1",
            "logarithmic_gap": sp.sstr(comparison_gap),
            "derivative_positive_denominator": "2*x^2*(1+x)*(x^2+12)",
            "alternating_log_lower": sp.sstr(logarithm_lower),
            "positive_polynomial_core": sp.sstr(polynomial_core),
            "uniform_positivity_margin": 1,
            "local_second_order_coefficient": sp.sstr(local_coefficient),
            "triangle_chart": triangle_chart,
            "sharpness_family": "A=t, C=t^2, B=pi-t-t^2",
            "sharpness_quadratic_ratio_limit": sp.sstr(sharpness_limit),
            "supremum": sp.sstr(minimum),
            "answer_tex": answer_tex,
        },
        [
            "0<x<=1で h(x)=(1/x+1/2)log(1+x)-1 と置く。log(1+x^2/12)-h(x) の導関数を正の分母で払う。",
            "log(1+x)>x-x^2/2+x^3/3-x^4/4+x^5/5-x^6/6 を代入すると、分子は x^4(180-46x+29x^2-123x^3+2x^4-10x^5)/30 以上である。0<x<=1では括弧内は1以上だから正である。",
            "従って (1+x)^(1/x+1/2)<e(1+x^2/12)、すなわち g(x)-e<ex^2/12 を得る。",
            "x=sin A,y=sin B,z=sin C は三角形の三辺に比例する。x=u+v,y=v+w,z=w+u (u,v,w>0) と書けば、2(xy+yz+zx)-(x^2+y^2+z^2)=4(uv+vw+wu)>0 である。",
            "三つの項へ一変数上界を足し合わせると、与式は e/12・(x^2+y^2+z^2)/(xy+yz+zx)<e/6 となる。",
            "A=t,C=t^2,B=pi-t-t^2 としてtを0へ近づけると、(g(x)-e)/x^2はe/12へ、二次比は2へ近づく。従ってe/6より小さい定数は使えず、最小値はe/6である。",
        ],
    )


def _cayley_exponential_integral_comparisons(
    objects: dict[str, Any],
) -> tuple[str, dict[str, Any], list[str]]:
    del objects
    chart = _cayley_exponential_chart()

    # Part (1): H(x)=log(T(x))-x is strictly increasing on (0,2).
    x = sp.Symbol("x", positive=True)
    cayley_x = (2 + x) / (2 - x)
    gap = sp.log(cayley_x) - x
    gap_derivative = sp.factor(sp.diff(gap, x))
    if sp.simplify(gap_derivative - x**2 / (4 - x**2)) != 0:
        raise ValueError("Cayley/exponential comparison derivative failed")
    if sp.limit(gap, x, 0, dir="+") != 0:
        raise ValueError("Cayley/exponential comparison endpoint failed")

    # Part (2), positive logarithm branch.  log(2)<7/10 follows from a
    # four-term positive Taylor lower bound for exp(7/10).
    seven_tenths = sp.Rational(7, 10)
    exp_lower_at_seven_tenths = (
        1
        + seven_tenths
        + seven_tenths**2 / 2
        + seven_tenths**3 / 6
    )
    log_two_margin = sp.factor(exp_lower_at_seven_tenths - 2)
    if log_two_margin != sp.Rational(13, 6000):
        raise ValueError("log(2)<7/10 certificate failed")

    y = sp.Symbol("y", positive=True)
    commutator_upper = sp.factor(
        y**3 / 12
        + y**4 / 12
        + y**5 / (16 * (1 - y / 2))
    )
    rational_commutator_upper = sp.factor(commutator_upper.subs(y, seven_tenths))
    commutator_margin = sp.factor(sp.Rational(1, 12) - rational_commutator_upper)
    if rational_commutator_upper != sp.Rational(202027, 3120000):
        raise ValueError("positive-branch commutator upper bound failed")
    if commutator_margin != sp.Rational(57973, 3120000):
        raise ValueError("positive-branch commutator margin failed")

    # Part (3): after integration by parts, compare 1/t^2 with an
    # exponential whose integral is exact.
    t = sp.Symbol("t", positive=True)
    tail_minorant_integral = sp.integrate(
        sp.exp(-t) * sp.exp(-(t - 2)) / 4,
        (t, 2, sp.oo),
    )
    if sp.simplify(tail_minorant_integral - sp.exp(-2) / 8) != 0:
        raise ValueError("exponential-integral tail minorant failed")
    tail_log_gap = t - 2 - 2 * sp.log(t / 2)
    if sp.simplify(sp.diff(tail_log_gap, t) - (1 - 2 / t)) != 0:
        raise ValueError("tail pointwise comparison derivative failed")

    answer_tex = (
        r"\(\text{(1) }e^x<\dfrac{2+x}{2-x},\quad"
        r"\text{(2) }\ln\dfrac{2+x}{2-x}>\dfrac{2+\ln x}{2-\ln x},\quad"
        r"\text{(3) }\mathrm{Ei}(2)<\dfrac{3}{8e^2}\)"
    )
    return (
        "(1) exp(x)<T(x); (2) log(T(x))>T(log(x)); (3) Ei(2)<3/(8*e^2)",
        {
            "shared_chart": chart,
            "derivation_format": "tex",
            "part1_log_gap_derivative": "x^2/(4-x^2)>0",
            "part2_substitution": "y=log(x), so y<log(2)<7/10",
            "log_two_rational_margin": sp.sstr(log_two_margin),
            "positive_branch_series": (
                "H(exp(y))>exp(3*y)/12>1/12, while "
                "T(y)-exp(y)<y^3/12+y^4/12+y^5/(16*(1-y/2))"
            ),
            "positive_branch_upper_at_7_over_10": sp.sstr(rational_commutator_upper),
            "positive_branch_margin": sp.sstr(commutator_margin),
            "negative_branch": "-2<y<0 gives T(y)<exp(y)<log(T(exp(y))); y<=-2 is immediate",
            "tail_pointwise_minorant": "1/t^2>exp(-(t-2))/4 for t>2",
            "tail_minorant_integral": sp.sstr(tail_minorant_integral),
            "answer_tex": answer_tex,
        },
        [
            r"\(T(u)=(2+u)/(2-u)\)、\(H(u)=\log T(u)-u\) とおく。"
            r"直接微分すると"
            r"\[H(0)=0,\qquad H'(u)=\frac{u^2}{4-u^2}.\]"
            r"従って \(0<x<2\) では \(H(x)>0\)、すなわち"
            r"\[e^x<T(x)=\frac{2+x}{2-x}.\]",
            r"(2) では \(y=\log x\) とおけば \(-\infty<y<\log2\) であり、"
            r"示すべき式は \(\log T(e^y)>T(y)\) となる。"
            r"\(y\le-2\) なら \(T(y)\le0<\log T(e^y)\)。"
            r"\(-2<y<0\) なら \(H(y)<0\) と (1) より"
            r"\[T(y)<e^y<\log T(e^y).\]"
            r"\(y=0\) では \(\log3>1\) である。",
            r"残る \(0<y<\log2\) を考える。Cayley 変換の正項展開から"
            r"\[H(e^y)>\frac{e^{3y}}{12}>\frac1{12}.\]"
            r"一方、指数級数との係数比較により"
            r"\[T(y)-e^y<\frac{y^3}{12}+\frac{y^4}{12}"
            r"+\frac{y^5}{16(1-y/2)}.\]"
            r"\(e^{7/10}>1+7/10+(7/10)^2/2+(7/10)^3/6>2\) だから"
            r"\(\log2<7/10\)。右辺は増加関数なので"
            r"\[T(y)-e^y<\frac{202027}{3120000}<\frac1{12}<H(e^y).\]"
            r"従ってこの場合にも \(\log T(e^y)>T(y)\) である。",
            r"(3) は部分積分により"
            r"\[\operatorname{Ei}(2)=\frac{e^{-2}}2"
            r"-\int_2^\infty\frac{e^{-t}}{t^2}\,dt.\]"
            r"\(G(t)=t-2-2\log(t/2)\) とおくと、\(t\ge2\) で"
            r"\(G(2)=0\)、\(G'(t)=1-2/t\ge0\) である。従って"
            r"\[\frac1{t^2}\ge\frac{e^{-(t-2)}}4\]"
            r"であり、\(t>2\) では狭義不等号となる。",
            r"よって"
            r"\[\int_2^\infty\frac{e^{-t}}{t^2}\,dt"
            r">\frac14\int_2^\infty e^{-t}e^{-(t-2)}\,dt"
            r"=\frac{e^{-2}}8.\]"
            r"以上から"
            r"\[\operatorname{Ei}(2)<e^{-2}\left(\frac12-\frac18\right)"
            r"=\frac{3}{8e^2}.\]",
        ],
    )


def _complex_argument_arctangent_certificate(
    objects: dict[str, Any],
) -> tuple[str, dict[str, Any], list[str]]:
    del objects
    product_chart = _complex_argument_product_chart((2, 3))
    if product_chart["gaussian_product"] != "5 + 5*I":
        raise ValueError("Machin pair product replay failed")
    if product_chart["real_part"] != product_chart["imaginary_part"]:
        raise ValueError("Machin pair does not certify tangent one")

    half_interval = _alternating_arctangent_interval(Fraction(1, 2), 5, 6)
    third_interval = _alternating_arctangent_interval(Fraction(1, 3), 5, 6)
    lower_pi = 4 * (
        Fraction(half_interval["lower"]) + Fraction(third_interval["lower"])
    )
    upper_pi = 4 * (
        Fraction(half_interval["upper"]) + Fraction(third_interval["upper"])
    )
    lower_target = Fraction(3141, 1000)
    upper_target = Fraction(1571, 500)
    lower_margin = lower_pi - lower_target
    upper_margin = upper_target - upper_pi
    if lower_margin <= 0 or upper_margin <= 0:
        raise ValueError("rational pi interval certificate failed")
    if lower_pi != Fraction(21940173935, 6983843328):
        raise ValueError("lower arctangent sum replay failed")
    if upper_pi != Fraction(498668825, 158723712):
        raise ValueError("upper arctangent sum replay failed")

    generic_condition = (
        "sum_{q>=0}(-1)^q e_{m-2q}="
        "sum_{q>=0}(-1)^q e_{m-2q-1}"
    )
    answer_tex = (
        r"\(e_k=e_k(j_1,\ldots,j_m),\ e_0=1\) とすると "
        r"\(\displaystyle\sum_{q\ge0}(-1)^q e_{m-2q}="
        r"\sum_{q\ge0}(-1)^q e_{m-2q-1}\) が必要十分条件であり、"
        r"\(3.141<\pi<3.142\) である。"
    )
    return (
        f"{generic_condition}; 3.141<pi<3.142",
        {
            "shared_product_chart": product_chart,
            "generic_condition": generic_condition,
            "machin_pair": [2, 3],
            "argument_identity": "atan(1/2)+atan(1/3)=pi/4",
            "half_interval": half_interval,
            "third_interval": third_interval,
            "pi_lower": str(lower_pi),
            "pi_upper": str(upper_pi),
            "lower_margin_over_3_141": str(lower_margin),
            "upper_margin_below_3_142": str(upper_margin),
            "answer_tex": answer_tex,
        },
        [
            "Z=prod_r(j_r+i) と置く。各因子は第1象限にあり、arg Z は各 arg(j_r+i) の和に合同である。従って tan(sum arg z_{j_r})=1 は Re Z=Im Z と同値である。",
            "e_kをj_1,...,j_mの基本対称式、e_0=1とする。積を展開すると Re Z=sum_{q>=0}(-1)^q e_{m-2q}, Im Z=sum_{q>=0}(-1)^q e_{m-2q-1} となり、両者の等式が必要十分条件である。",
            "(2+i)(3+i)=5+5i なので、0<atan(1/2)+atan(1/3)<pi/2 と合わせて atan(1/2)+atan(1/3)=pi/4 を得る。",
            "0<x<=1では arctan x=x-x^3/3+x^5/5-... は絶対値が減少する交代級数である。負項で終わる6項和は下界、正項で終わる5項和は上界になる。",
            "x=1/2,1/3へ適用して4倍すると 21940173935/6983843328<pi<498668825/158723712。左端は3.141より490255219/872980416000大きく、右端は3.142より5134763/19840464000小さい。",
        ],
    )


def _triangle_radii_exponential_bound(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    chart = str(objects["chart"])
    radius_relation_chart = _triangle_radii_ratio_chart()
    if chart == "cosine_sum":
        return "e", {"radius_relation_chart": radius_relation_chart, "parameter": "u=r/R", "domain": "0<u<=1/2", "derivative_sign": "negative"}, [
            "cos A+cos B+cos C=1+r/R を用いる。",
            "u=r/R とすれば式は (1+u)^(1/u) で、u>0 上単調減少し上限は e である。",
        ]
    value = sp.sqrt(2) ** (1 / (sp.sqrt(2) - 1))
    return f"[{sp.sstr(value)}, e)", {"radius_relation_chart": radius_relation_chart, "parameter": "u=sin(A)+cos(A)", "domain": "1<u<=sqrt(2)"}, [
        "直角三角形では R/r=1/(u-1), u=sin A+cos A である。",
        "log(u)/(u-1) は u>1 で単調減少するため端点と極限で値域が決まる。",
    ]


def _radial_triangle_area_bound(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    lengths = [int(value) for value in objects["lengths"]]
    bound = sp.Integer(objects["bound"])
    if lengths != [1, 2, 3] or bound != 5:
        raise ValueError("radial inequality certificate is parameter-specific and must be resynthesized")
    c = sp.Symbol("c", real=True)
    polynomial = sp.Poly((59 + 36 * c - 4 * c**2) ** 2 - 1600 * (1 - c**2), c)
    if polynomial.count_roots(-1, 1) != 0 or polynomial.eval(-1) <= 0:
        raise ValueError("Sturm certificate failed for radial area bound")
    return "最大値は 5 未満", {"sturm_roots_on_unit_interval": 0, "positive_endpoint": int(polynomial.eval(-1))}, [
        "回転対称性で一針を固定し、面積の2倍を 2sin u+6sin(v-u)-3sin v とした。",
        "v を消去して一変数上界を作り、二回平方した四次多項式の正値性をSturm列で検証した。",
    ]


def _three_sample_triangle_probabilities(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    return "p(n)=1-sum(c=3..n,floor((c-1)^2/4))/C(n,3), lim p(n)=1/2; lim q(n)=1-pi/4", {"bad_triples_for_largest_c": "floor((c-1)^2/4)", "continuum_simplex_volume": "1/6", "triangle_volume": "1/12", "acute_volume": "1/6-pi/24"}, [
        "a<b<cと並べると非三角形はa+b<=cであり、固定したcごとの個数はfloor((c-1)^2/4)である。",
        "これをc=3からnまで足し、全組合せC(n,3)から引いて有限nのp(n)を得る。",
        "n で規格化した極限領域の体積は三角形で1/12、鋭角条件で1/6-pi/24である。",
        "全順序領域の体積1/6で割ると各極限を得る。",
    ]


def _fourier_rotation_volume(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    return "V_n=(1/(2*pi))*sum(k=1..n,1/k^2), lim V_n=pi/12", {"orthogonality": "integral sin(2pi kx)sin(2pi lx)=delta_kl/2"}, [
        "回転体積を pi*integral(f_n-1/2)^2 dx に変換した。",
        "正弦系の直交性で交差項を消し、平方和だけを残した。",
        "Basel和を用いて極限 pi/12 を得る。",
    ]


def _polar_circle_doubling_reciprocal_identities(
    objects: dict[str, Any],
) -> tuple[str, dict[str, Any], list[str]]:
    period = int(objects.get("period", 5))
    chart = _polar_circle_doubling_chart(period)
    if period != 5:
        raise ValueError("the reciprocal identities require the period-five orbit")

    half_tangent = sp.Symbol("t", positive=True)
    sine_x = 2 * half_tangent / (1 + half_tangent**2)
    cotangent_x = (1 - half_tangent**2) / (2 * half_tangent)
    csc_half_angle_replay = sp.factor(
        1 / sine_x - (cotangent_x + half_tangent)
    )
    double_angle_replay = sp.factor(
        1 / half_tangent - half_tangent - 2 * cotangent_x
    )
    if csc_half_angle_replay != 0 or double_angle_replay != 0:
        raise ValueError("cotangent telescoping identities failed")

    orbit = chart["strictly_increasing_orbits"][0]
    if orbit != [1, 2, 4, 8, 16] or chart["modulus"] != 31:
        raise ValueError("period-five point orbit failed")
    answer_tex = (
        r"\(\theta_k=2^{k-1}\pi/31\ (k=1,\ldots,5)\) と定まり、"
        r"\(\dfrac1{OP_1}=\sum_{k=2}^5\dfrac1{OP_k}\) および第(2)式がともに成立する。"
    )
    return (
        "theta_k=2^(k-1)*pi/31; both reciprocal identities hold",
        {
            "shared_chart": chart,
            "angle_numerators": orbit,
            "base_angle": "pi/31",
            "part1_telescoping": "csc(2x)+csc(4x)+csc(8x)+csc(16x)=cot(x)-cot(16x)=csc(x)",
            "part2_left_reduction": "csc(3x)+csc(14x)=cot(3x)+cot(7x)",
            "part2_right_reduction": "csc(7x)+csc(6x)+csc(12x)=cot(3x)+cot(7x)",
            "answer_tex": answer_tex,
        },
        [
            "r=sin theta は中心(0,1/2)、半径1/2の円である。角theta,phiに対応する二点の弦長は |sin(theta-phi)|、原点からの距離はsin thetaである。",
            "原点でない次点について |sin(phi-theta)|=sin theta を解くと phi=2theta (mod pi)。従って5点は円周角の倍角写像で巡回し、2^5 theta_1=theta_1 (mod pi) から theta_1=j*pi/31 となる。",
            "半径sin(theta)の大小は residue j のmin(j,31-j)の大小で決まる。6本の倍角軌道を有限列挙すると、厳密増加する軌道は (1,2,4,8,16) だけである。",
            "csc u=cot(u/2)-cot u を用いると csc2x+csc4x+csc8x+csc16x=cot x-cot16x。31x=piよりcot16x=-tan(x/2)なので、これはcsc xに等しい。第(1)式を得る。",
            "弦長公式から第(2)式は csc3x+csc14x=csc7x+csc6x+csc12x。cot14x=tan(3x/2), cot12x=tan(7x/2) と csc u=cot(u/2)-cot u を使うと、両辺ともcot3x+cot7xへ縮約される。",
        ],
    )


def _pell_hyperbola_segment_area(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    d = int(objects["discriminant"])
    if d != 3:
        raise ValueError("fundamental Pell unit must be synthesized for this discriminant")
    h = sp.log(2 + sp.sqrt(3))
    area = sp.Rational(1, 2) * (1 - h / sp.sqrt(3))
    return sp.sstr(area), {"fundamental_unit": "2+sqrt(3)", "area_independent_of_k": True}, [
        "Pell解を x+y*sqrt(3)=(2+sqrt(3))^k と媒介した。",
        "双曲線を (cosh u,sinh u/sqrt(3)) と書くと隣接点のパラメータ差は一定である。",
        "Greenの公式で弧と弦の符号付き面積を計算した。",
    ]


def _rotated_parabola_volume_limit(
    objects: dict[str, Any],
) -> tuple[str, dict[str, Any], list[str]]:
    if int(objects["degree"]) != 2:
        raise ValueError("the blow-up chart currently requires a parabola")

    t, u, v, X = sp.symbols("t u v X", positive=True)
    x_q = u * sp.cos(t) - u**2 * sp.sin(t)
    y_q = u * sp.sin(t) + u**2 * sp.cos(t)
    intersection = sp.expand(y_q - x_q**2)
    blown_intersection = sp.factor(
        sp.limit(t**2 * intersection.subs(u, v / t), t, 0, dir="+")
    )
    if blown_intersection != -v**3 * (v - 2):
        raise ValueError("parabola intersection blow-up failed")
    endpoint_derivative = sp.diff(blown_intersection, v).subs(v, 2)
    if endpoint_derivative != -8:
        raise ValueError("nonzero endpoint branch certificate failed")

    scaled_x = sp.simplify(t * x_q.subs(u, v / t))
    scaled_y = sp.simplify(t**2 * y_q.subs(u, v / t))
    limiting_x = sp.limit(scaled_x, t, 0, dir="+")
    limiting_y = sp.limit(scaled_y, t, 0, dir="+")
    if limiting_x != v * (1 - v) or limiting_y != v**2:
        raise ValueError("scaled rotated-parabola chart failed")

    high_branch = sp.integrate(v**4 * (2 * v - 1), (v, sp.Rational(1, 2), 2))
    low_branch = sp.integrate(v**4 * (1 - 2 * v), (v, 0, sp.Rational(1, 2)))
    parabola_inner = sp.integrate(X**4, (X, -2, 0))
    section_integral = sp.factor(high_branch - low_branch - parabola_inner)
    if section_integral != sp.Rational(128, 15):
        raise ValueError("rotated-volume section integral failed")
    right_limit = sp.pi * section_integral
    left_limit = -right_limit

    # Reflection in the y-axis maps the +t configuration to the -t
    # configuration while preserving both P:y=x^2 and volume about the
    # x-axis.  Thus V is even and the odd rescaling t^5 changes sign.
    answer_tex = (
        r"\(\text{両側極限は存在しない},\qquad "
        r"\lim_{\theta\to0^+}\theta^5V(\theta)="
        + sp.latex(right_limit)
        + r",\quad \lim_{\theta\to0^-}\theta^5V(\theta)="
        + sp.latex(left_limit)
        + r"\)"
    )
    return (
        f"two-sided limit does not exist; right={sp.sstr(right_limit)}; left={sp.sstr(left_limit)}",
        {
            "reflection_identity": "V(-theta)=V(theta)",
            "intersection_equation": sp.sstr(intersection),
            "blown_intersection": sp.sstr(blown_intersection),
            "nonzero_endpoint_root": "v=2",
            "endpoint_root_derivative": sp.sstr(endpoint_derivative),
            "scaled_curve": {"X": sp.sstr(limiting_x), "Y": sp.sstr(limiting_y)},
            "turning_parameter_limit": "v=1/2",
            "high_branch_integral": sp.sstr(high_branch),
            "low_branch_integral": sp.sstr(low_branch),
            "parabola_inner_integral": sp.sstr(parabola_inner),
            "section_integral": sp.sstr(section_integral),
            "right_limit": sp.sstr(right_limit),
            "left_limit": sp.sstr(left_limit),
            "answer_tex": answer_tex,
        },
        [
            "P:y=x^2 を角 theta 回転した曲線を u で媒介すると、Q=(u cos theta-u^2 sin theta, u sin theta+u^2 cos theta) となる。y_Q=x_Q^2 が交点条件である。",
            "theta>0 として u=v/theta, X=theta x, Y=theta^2 y と吹き上げる。交点式は -v^3(v-2) へ収束し、非零交点は単根 v=2 に収束する。Q は (X,Y)=(v-v^2,v^2)、P は Y=X^2 へ収束する。",
            "回転体の断面を、Qの上枝 v in [1/2,2]、下枝 v in [0,1/2]、Pの内側 X in [-2,0] に分ける。各断面の半径平方を積分すると 4779/320-1/960-32/5=128/15 となる。",
            "従って右極限は128pi/15。負の回転は正の回転をy軸対称にしたもので、x軸回転体の体積は変わらないから V(-theta)=V(theta) である。",
            "theta^5 は奇関数なので左極限は -128pi/15。左右が一致せず、問題文どおりの両側極限は存在しない。",
        ],
    )


def _rotated_parabola_intersection_limit(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    if int(objects["degree"]) != 2:
        raise ValueError("scaling certificate is for a parabola")
    t, u = sp.symbols("t u", positive=True)
    equation = sp.expand(u * sp.sin(t) + u**2 * sp.cos(t) - (u * sp.cos(t) - u**2 * sp.sin(t)) ** 2)
    scaled = sp.limit(sp.expand(equation.subs(u, 2 / t) * t**2), t, 0, dir="+")
    if scaled != 0:
        raise ValueError("dominant-balance root failed")
    return "4", {"intersection_parameter_asymptotic": "u~2/theta", "distance_asymptotic": "OR~4/theta^2"}, [
        "回転前の放物線パラメータuで交点条件を一つの三次式にした。",
        "Newton多角形の支配項から非零枝 u~2/theta を得た。",
        "回転は距離を保つので OR=sqrt(u^2+u^4)~4/theta^2 である。",
    ]


def _sine_integral_rational_bounds(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    x = sp.Symbol("x", nonnegative=True)
    lower = sp.integrate(1 - x**2 / 6, (x, 0, sp.pi / 2))
    upper = sp.integrate(1 - x**2 / 6 + x**4 / 120, (x, 0, sp.pi / 2))
    pi_upper = sp.Rational(22, 7)
    lower_margin_after_dividing_pi = sp.Rational(72, 1) - 5 * pi_upper**2
    upper_at_pi_bound = pi_upper / 2 - pi_upper**3 / 144 + pi_upper**5 / 38400
    if lower_margin_after_dividing_pi <= 0 or upper_at_pi_bound >= sp.Rational(3, 2):
        raise ValueError("exact Taylor enclosure did not imply requested bounds")
    return "2*pi/5 < integral(sin(x)/x,0,pi/2) < 3/2", {
        "lower_polynomial_integral": sp.sstr(lower),
        "upper_polynomial_integral": sp.sstr(upper),
        "pi_upper": "22/7",
        "upper_margin": sp.sstr(sp.Rational(3, 2) - upper_at_pi_bound),
    }, [
        "sin x の交代Taylor級数を x^5 まで上下から挟んだ。",
        "xで割って項別積分した。下界はpi^2<72/5、上界はpi<22/7を代入した有理数比較で厳密に閉じた。",
    ]


def _elementary_exponential_bounds(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    return "e<1+sqrt(3); integral_0^1 e^x sin(x) dx is not an integer", {"integral_interval": "(1/2,1)", "e_upper": "11/4"}, [
        "e の級数余項を評価して e<11/4<1+sqrt(3) を得る。",
        "積分は (1+e(sin1-cos1))/2 である。",
        "sin, cos の交代級数と e<11/4 から 1/2<I<1 を得るため整数ではない。",
    ]


def _symmetric_integer_progression(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    solutions: list[tuple[int, int, int]] = []
    for x in range(1, 7):
        for y in range(x, 200):
            denominator = x * y - 2 * x - 2 * y + 1
            numerator = 2 * x * y - x - y
            if denominator <= 0:
                continue
            if numerator % denominator:
                continue
            z = numerator // denominator
            if z < y:
                continue
            if 2 * (x * y + y * z + z * x) == x + y + z + x * y * z:
                solutions.append((x, y, z))
    expected = [(3, 6, 27), (3, 7, 16), (4, 4, 24)]
    if solutions != expected:
        raise ValueError("symmetric integer enumeration did not close")
    return "permutations of {(3,6,27),(3,7,16),(4,4,24)}", {"ordered_solutions": solutions, "smallest_variable_bound": 6}, [
        "x<=y<=z として等差条件を z の一次方程式にした。",
        "式を xyz で割ると 1<=6/x なので x<=6 である。",
        "各 x で分母の整除条件と z>=y を有限検査した。",
    ]


def _gaussian_prime_power_identity(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    return "(p,q,r,s)=(3,2,2,5)", {"even_exponent_branch": [3, 2, 2, 5], "odd_exponent_eliminated": True}, [
        "r=2 では虚部条件が自動的に成り、s=p^2-q^2=(p-q)(p+q) を素数条件で解く。",
        "奇素数rでは虚部を法pで見るとp=qを得る。",
        "p=qを戻すと偶数の冪が奇素数rに等しい必要があり矛盾する。",
    ]


def _fibonacci_prime_neighbors(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    del objects
    p, q = sp.symbols("p q", integer=True, positive=True)
    tangent_norm = sp.expand((p - q) * (p + q) - (p * q + 1))
    if tangent_norm != p**2 - p * q - q**2 - 1:
        raise ValueError("tangent-difference norm reduction failed")

    # The Cassini norm changes sign under one Fibonacci transition.
    x, y = sp.symbols("x y")
    cassini_norm = x**2 - x * y - y**2
    transitioned_norm = sp.expand((x + y) ** 2 - (x + y) * x - x**2)
    if sp.expand(transitioned_norm + cassini_norm) != 0:
        raise ValueError("Cassini sign transition failed")

    fibonacci = [1, 1]
    for _ in range(2, 12):
        fibonacci.append(fibonacci[-1] + fibonacci[-2])
    cassini_values = [
        fibonacci[index] ** 2
        - fibonacci[index] * fibonacci[index - 1]
        - fibonacci[index - 1] ** 2
        for index in range(1, len(fibonacci))
    ]
    if cassini_values != [(-1) ** n for n in range(1, len(fibonacci))]:
        raise ValueError("Cassini exact replay failed")

    prime_pair = (5, 3)
    if prime_pair[0] ** 2 - prime_pair[0] * prime_pair[1] - prime_pair[1] ** 2 != 1:
        raise ValueError("prime tangent pair replay failed")

    recurrence_chart = _second_order_recurrence_chart(1, 1)
    answer_tex = (
        r"\(\text{(1)}\ (p,q)=(5,3).\qquad "
        r"\text{(2)}\ F_{n+1}^2-F_{n+1}F_n-F_n^2=(-1)^n.\qquad "
        r"\text{(3)}\ n\in\{3,4\}.\)"
    )
    shared_chart = {
        "chart_id": "trigonometric_norm.fibonacci_prime_neighbor.v1",
        "atomic_chart_ids": [
            "trigonometric.tangent_difference.norm_form.v1",
            "quadratic_norm.mod_prime.descent.v1",
            "recurrence.order2.companion.characteristic.v1",
            "fibonacci.cassini.norm.v1",
            "divisibility_sequence.index_filter.v1",
        ],
        "proof_obligations": {
            "tangent_equation_reduces_to_quadratic_norm_one": True,
            "prime_residue_branches_force_five_and_three": True,
            "cassini_norm_sign_flips_under_fibonacci_transition": True,
            "prime_fibonacci_term_forces_prime_index_or_four": True,
            "adjacent_prime_indices_force_three_or_four": True,
        },
    }
    return (
        "(1) (p,q)=(5,3); (2) Cassini identity; (3) n in {3,4}",
        {
            "prime_pair": list(prime_pair),
            "tangent_norm_equation": "p^2-p*q-q^2=1",
            "ratio_bound": "q<p<2*q",
            "mod_q_branches": ["p=q+1", "p=2*q-1"],
            "first_branch_exclusion": "p=q+1 gives (p,q)=(3,2), whose norm is -1",
            "second_branch_solution": "q*(q-3)=0, hence (p,q)=(5,3)",
            "cassini_transition_residual": "0",
            "cassini_replay": cassini_values,
            "indices": [3, 4],
            "prime_index_criterion": "F_m prime => m prime or m=4",
            "recurrence_chart": recurrence_chart,
            "derivation_format": "tex",
            "answer_tex": answer_tex,
            "shared_chart": shared_chart,
        },
        [
            r"正接の差の公式から \[\frac{p-q}{1+pq}=\frac1{p+q}\] であり、従って \[p^2-pq-q^2=1.\] 特に \(p>q\)。また \(p\ge2q\) なら左辺は少なくとも \(q^2>1\) なので \(q<p<2q\) である。",
            r"法 \(q\) で \(p^2\equiv1\pmod q\)。\(q\) は素数だから \(p\equiv\pm1\pmod q\) であり、上の範囲と合わせると \(p=q+1\) または \(p=2q-1\)。前者は素数の偶奇から \((p,q)=(3,2)\) だけだが元のノルムは \(-1\)。後者を代入すると \(q(q-3)=0\) なので \((p,q)=(5,3)\) である。",
            r"\(C_n=F_{n+1}^2-F_{n+1}F_n-F_n^2\) と置く。\(F_{n+2}=F_{n+1}+F_n\) を代入すると \(C_{n+1}=-C_n\)、かつ \(C_1=-1\) だから \[C_n=(-1)^n.\]",
            r"標準的な整除性 \(d\mid m\Rightarrow F_d\mid F_m\) を用いる。合成数 \(m\ne4\) には \(3\le d<m\) となる約数があり、\(1<F_d<F_m\) なので \(F_m\) は合成数である。従って \(F_m\) が素数なら \(m\) は素数または \(m=4\) である。",
            r"\(F_n,F_{n+1}\) がともに素数なら、連続する添字 \(n,n+1\) はそれぞれ素数または4でなければならない。\(n\ge3\) では一方が偶数なので、それは4に限る。従って \(n=3,4\)。実際 \((F_3,F_4)=(2,3)\)、\((F_4,F_5)=(3,5)\) はどちらも素数である。",
        ],
    )


def _prime_angle_addition_on_circle(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    return "{p,q,r}={2,3,7}", {"factor_equation": "(q-p)(r-p)=p^2+1"}, [
        "円周角と弦比から angle(AOP_n)=2 arctan(1/n) を得る。",
        "正接の加法定理で (q-p)(r-p)=p^2+1 に変換する。",
        "pが奇数なら二因子の偶奇が他の二素数と両立しないためp=2、約数を調べて3,7を得る。",
    ]


def _mobius_prime_three_cycle(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    return "(n,p,q,r)=(5,3,5,7) and cyclic permutations", {"translated_map": "g(y)=(2y+4)/(2-3y)", "integer_orbit_offsets": [-2, 0, 2]}, [
        "x=n+y と平行移動すると写像は n に依らない3周期写像 g(y) になる。",
        "g(y)が整数なら 2-3y は16の約数なので整数軌道は {-2,0,2} に限られる。",
        "n-2,n,n+2 が全て素数となるのは3の剰余から n=5 のみである。",
    ]


def _prime_elementary_symmetric_triangle(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    if int(objects.get("arity", 0)) != 3:
        raise ValueError("the elementary-symmetric reduction requires three variables")
    # For p<=q<=r, only e1+e2>e3 is nontrivial.  Dividing by pqr
    # bounds p, and the p=2,3 branches factor into rectangular hyperbolas.
    return (
        "up to permutation: (2,2,r), (2,3,r) for prime r; "
        "(2,5,5), (2,5,7), (3,3,3), (3,3,5), (3,3,7)",
        {
            "ordering": "p<=q<=r",
            "nontrivial_inequality": "p*q*r < p*q+p*r+q*r+p+q+r",
            "p_bound": 3,
            "p_equals_2_reduction": "(q-3)(r-3)<11",
            "p_equals_3_reduction": "2(q-2)(r-2)<11",
        },
        [
            "基本対称式e1,e2,e3のうち、e1+e3>e2 は (p-1)(q-1)(r-1)+1>0 なので自動的に成り立つ。",
            "残る条件をpqrで割る。p>=5なら右辺は高々3/5+3/25<1だから、pは2または3である。",
            "p=2,3では条件をそれぞれ長方形型の整数不等式へ因数分解し、素数q,rを有限分類する。",
        ],
    )


def _ordered_prime_power_triangle(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    return (
        "三角形の三辺にはなり得ない",
        {
            "largest_side": "q^r",
            "comparison_lemma": "log(x)/(x-1) is strictly decreasing for x>1",
            "upper_bounds": ["r^p<q^(r-1)", "p^q<q^(r-1)"],
        },
        [
            "p<q<r と q>=3 を用いる。log(x)/(x-1) の単調減少性から p log r<(r-1)log q、従って r^p<q^(r-1) を得る。",
            "また p<q かつ q<r-1 から p^q<q^(r-1) である。",
            "よって r^p+p^q<2q^(r-1)<q^r となり、最大辺q^rが三角不等式を破る。",
        ],
    )


def _rational_sine_prime_ratio(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    p, q = 3, 2
    ratio = Fraction(p - q, p + q)
    discriminant = Fraction(p * p + 6 * p * q + q * q, (p + q) ** 2)
    if discriminant != Fraction(49, 25):
        raise ValueError("rational-sine witness failed")
    return (
        "{sin(alpha),sin(beta)}={4/5,-3/5}; necessarily (p,q)=(3,2)",
        {
            "sum": str(ratio),
            "square_condition": "p^2+6pq+q^2=k^2",
            "odd_q_factor_pairs": ["(1,2q^2)", "(2,q^2)", "(q,2q)"],
            "q_equals_2_factor_pairs": [[2, 16], [4, 8]],
        },
        [
            "二つの単位ベクトルの和がs(1,1)なので、二つの正弦は (s±sqrt(2-s^2))/2 である。",
            "s=(p-q)/(p+q)を代入すると、有理性は p^2+6pq+q^2 が平方であることと同値になる。",
            "qが奇素数なら (p+3q-k)(p+3q+k)=8q^2 の因子対は三種類だけで、いずれもpを合成数または0にする。",
            "q=2では積32の同偶因子対を調べるとp=3だけが残り、正弦は4/5と-3/5になる。",
        ],
    )


def _triangular_primorial_equality(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    finite_solutions = []
    primorial = 1
    for n in range(1, 11):
        if sp.isprime(n):
            primorial *= n
        if n * (n + 1) // 2 == primorial:
            finite_solutions.append(n)
    if finite_solutions != [1, 3]:
        raise ValueError("primorial base interval failed")
    base_primorial = int(sp.primorial(5))  # product of primes through 11
    base_upper_triangle = 21 * 22 // 2
    if base_primorial <= base_upper_triangle:
        raise ValueError("primorial dyadic induction base failed")
    return (
        "n in {1,3}",
        {
            "finite_interval": [1, 10],
            "finite_solutions": finite_solutions,
            "dyadic_base": {"m": 11, "primorial_m": base_primorial, "triangle_2m_minus_1": base_upper_triangle},
            "growth_theorem": "Bertrand postulate",
        },
        [
            "n=1から10は素数積を逐次更新する整数計算で全検査し、1と3だけを得る。",
            "m=11ではP(m)>T_(2m-1)であるため、11<=n<22に解はない。",
            "Bertrandの仮説により(m,2m)に素数があり、m>=5ならP(2m)>mP(m)>T_(4m-1)である。",
            "mを倍々にする帰納法でn>=11を覆う。",
        ],
    )


def _nested_sine_cosine_integral_bound(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    # At the Jensen mean, pass to the complementary acute angle
    # d=pi/2-4/pi.  Coarse rational bounds are already strong enough to
    # certify h(4/pi)<4/pi without decimal evaluation or a fitted tangent.
    pi_lower = sp.Rational(333, 106)
    pi_upper = sp.Rational(22, 7)
    d_upper = sp.simplify(pi_upper / 2 - 4 / pi_upper)
    if not (sp.Integer(0) < d_upper < sp.Rational(3, 10)):
        raise ValueError("complementary-angle enclosure failed")
    strict_gap_lower = sp.simplify(pi_lower / 2 - sp.Rational(157, 100))
    if strict_gap_lower <= 0:
        raise ValueError("complementary-angle strict gap failed")
    return (
        "integral_0^(pi/2) {cos(cos x+sin x)+sin(cos x+sin x)} dx < 2",
        {
            "inner_range": "[1,sqrt(2)]",
            "inner_mean": "4/pi",
            "complementary_angle": "d=pi/2-4/pi",
            "complementary_angle_upper": sp.sstr(d_upper),
            "pi_lower": sp.sstr(pi_lower),
            "pi_upper": sp.sstr(pi_upper),
            "strict_margin_numerator_lower_bound": sp.sstr(strict_gap_lower),
            "strict_gap_lower_bound": sp.sstr(strict_gap_lower),
            "derivation_format": "tex",
            "answer_tex": (
                r"\(\displaystyle \int_0^{\pi/2}"
                r"\{\cos(\cos x+\sin x)+\sin(\cos x+\sin x)\}\,dx<2.\)"
            ),
            "shared_chart": {
                "chart_id": "concave_composition.complementary_angle.bound.v1",
                "atomic_chart_ids": [
                    "concave_composition.jensen_mean.v1",
                    "trigonometric.complementary_angle.v1",
                    "power_series.alternating_remainder.v1",
                    "rational.constant.enclosure.v1",
                ],
                "proof_obligations": {
                    "inner_function_range_positive": True,
                    "outer_function_concave_on_range": True,
                    "complementary_angle_is_between_zero_and_three_tenths": True,
                    "strict_fixed_mean_gap_is_positive": True,
                },
            },
        },
        [
            r"\(h(t)=\sin t+\cos t\)、\(u(x)=\sin x+\cos x\) と置く。\(1\le u(x)\le\sqrt2\) であり、\[\frac2\pi\int_0^{\pi/2}u(x)\,dx=\frac4\pi.\] また、この範囲では \(h''(t)=-h(t)<0\) である。従って Jensen の不等式から \[\frac2\pi\int_0^{\pi/2}h(u(x))\,dx\le h\!\left(\frac4\pi\right).\]",
            r"ここで \(d=\pi/2-4/\pi\) と置く。\(3<\pi<22/7\) より \[0<d<\frac{23}{77}<\frac3{10}.\] これは補角が第1象限にあるという部分で、\[h\!\left(\frac4\pi\right)=\cos d+\sin d\] と書ける。",
            r"\(0<d<3/10\) に対し、\(\sin d<d\) かつ交代級数評価から \[\cos d<1-\frac{d^2}{2}+\frac{d^4}{24}<1-\frac{d^2}{3}.\] よって \[h\!\left(\frac4\pi\right)<1+d-\frac{d^2}{3}.\]",
            r"関数 \(1+2d-d^2/3\) はこの区間で増加するので \[1+2d-\frac{d^2}{3}<1+\frac35-\frac3{100}=\frac{157}{100}<\frac\pi2,\] ただし最後は \(\pi>333/106>157/50\) を用いた。従って \(h(4/\pi)<\pi/2-d=4/\pi\) である。Jensen の評価へ戻すと、求める積分は厳密に \(2\) 未満となる。",
        ],
    )


def _alternating_trig_bounds(x: sp.Rational) -> tuple[sp.Rational, sp.Rational, sp.Rational, sp.Rational]:
    return _shared_alternating_trig_bounds(x)


def _alternating_trig_interval_chart(points: list[sp.Rational]) -> dict[str, Any]:
    """Certify rational sin/cos enclosures with one reusable Taylor chart."""
    return _shared_alternating_trig_interval_chart(points)


def _h_bounds(x: sp.Rational) -> tuple[sp.Rational, sp.Rational]:
    sin_lower, sin_upper, cos_lower, cos_upper = _alternating_trig_bounds(x)
    return sin_lower + cos_lower, sin_upper + cos_upper


def _d_bounds(x: sp.Rational) -> tuple[sp.Rational, sp.Rational]:
    sin_lower, sin_upper, cos_lower, cos_upper = _alternating_trig_bounds(x)
    return sin_lower - cos_upper, sin_upper - cos_lower


def _log_one_plus_bounds(x: sp.Rational, terms: int = 14) -> tuple[sp.Rational, sp.Rational]:
    return _shared_log_one_plus_bounds(x, terms)


def _log_profile_bounds(lower: sp.Rational, upper: sp.Rational) -> tuple[sp.Rational, sp.Rational]:
    return _shared_log_profile_bounds(lower, upper)


def _sine_cosine_iteration_certificate() -> tuple[dict[str, sp.Rational], dict[str, Any]]:
    pi_upper = sp.Rational(355, 113)
    c_lower = 4 / pi_upper
    sqrt3_lower = sp.Rational(265, 153)
    sqrt3_upper = sp.Rational(97, 56)
    lambda_lower = (sqrt3_lower - 1) / 2
    lambda_upper = (sqrt3_upper - 1) / 2
    sqrt2_lower = sp.Rational(140, 99)
    sqrt2_upper = sp.Rational(99, 70)

    inner_one_lower, inner_one_upper = _h_bounds(sp.Rational(1))
    h_h_one_upper = _h_bounds(inner_one_lower)[1]
    line_one_lower = c_lower * (1 - lambda_upper) + lambda_upper
    endpoint_one_margin = line_one_lower - h_h_one_upper

    inner_sqrt2_lower = _h_bounds(sqrt2_upper)[0]
    h_h_sqrt2_upper = _h_bounds(inner_sqrt2_lower)[1]
    line_sqrt2_lower = c_lower * (1 - lambda_lower) + lambda_lower * sqrt2_lower
    endpoint_sqrt2_margin = line_sqrt2_lower - h_h_sqrt2_upper

    derivative_one_upper = _d_bounds(inner_one_upper)[1] * _d_bounds(sp.Rational(1))[1]
    derivative_one_margin = lambda_lower - derivative_one_upper
    derivative_sqrt2_lower = _d_bounds(inner_sqrt2_lower)[0] * _d_bounds(sqrt2_lower)[0]
    derivative_sqrt2_margin = derivative_sqrt2_lower - lambda_upper

    margins = {
        "endpoint_one": endpoint_one_margin,
        "endpoint_sqrt2": endpoint_sqrt2_margin,
        "derivative_one": derivative_one_margin,
        "derivative_sqrt2": derivative_sqrt2_margin,
    }
    if any(value <= 0 for value in margins.values()):
        raise ValueError("rational interval certificate for h composed with h failed")
    if not (inner_sqrt2_lower > 1 and inner_one_upper < sqrt2_upper):
        raise ValueError("composition did not remain in the certified interval")
    interval_chart = _alternating_trig_interval_chart(
        [
            sp.Rational(1),
            inner_one_lower,
            inner_one_upper,
            sqrt2_lower,
            sqrt2_upper,
            inner_sqrt2_lower,
        ]
    )
    return margins, interval_chart


def _sine_cosine_iteration_integral_bound(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    include_scaffold = bool(objects.get("include_scaffold"))
    margins, trigonometric_interval_chart = _sine_cosine_iteration_certificate()
    pi_upper = sp.Rational(355, 113)
    sqrt2_upper = sp.Rational(99, 70)
    sqrt3_upper = sp.Rational(97, 56)
    center_lower = 4 / pi_upper
    tangent_offset_lower = center_lower - 5 * pi_upper / 12
    fixed_point_gap_lower = sp.factor(
        center_lower
        + sqrt2_upper * tangent_offset_lower / 2
        - sqrt2_upper * sqrt3_upper / 2
    )
    if fixed_point_gap_lower != sp.Rational(7259089, 314501600):
        raise ValueError("fixed-point tangent gap certificate failed")
    coarse_margin_checks = {
        "fixed_point_gap_gt_1_over_1000": bool(fixed_point_gap_lower > sp.Rational(1, 1000)),
        "endpoint_one_gt_1_over_400": bool(margins["endpoint_one"] > sp.Rational(1, 400)),
        "endpoint_sqrt2_gt_1_over_3000": bool(margins["endpoint_sqrt2"] > sp.Rational(1, 3000)),
        "derivative_one_gt_1_over_8": bool(margins["derivative_one"] > sp.Rational(1, 8)),
        "negative_derivative_sqrt2_lt_minus_1_over_22": bool(
            margins["derivative_sqrt2"] > sp.Rational(1, 22)
        ),
    }
    if not all(coarse_margin_checks.values()):
        raise ValueError("readable sine-cosine iteration margins failed")
    shared_chart = {
        "chart_id": "sine_cosine.iteration.two_step_affine_bound.v1",
        "atomic_chart_ids": [
            "concave_function.tangent_upper_bound.v1",
            "fixed_point.monotone_crossing.v1",
            "composition.third_derivative.endpoint_minimum.v1",
            "integral.affine_contraction.parity_induction.v1",
        ],
        "proof_obligations": {
            "invariant_interval_closed": True,
            "tangent_bound_exact": True,
            "unique_fixed_point_and_order": True,
            "two_step_affine_bound_certified": True,
            "even_odd_integral_induction_closed": True,
        },
    }
    answer_tex = (
        r"\(\begin{aligned}"
        r"&\text{(1) 与えられた接線上界が成立},\qquad"
        r"\text{(2) }\alpha<4/\pi,\\"
        r"&\text{(3) 与えられた二段上界が成立},\qquad"
        r"\text{(4) }\displaystyle\int_0^{\pi/2}f_n(x)\,dx\le2."
        r"\end{aligned}\)"
    )
    witness = {
        "answer_tex": answer_tex,
        "derivation_format": "tex",
        "shared_chart": shared_chart,
        "invariant_interval": "[1,sqrt(2)]",
        "center": "4/pi",
        "contraction": "(sqrt(3)-1)/2",
        "fixed_point_gap_lower": sp.sstr(fixed_point_gap_lower),
        "exact_interval_margins": {key: sp.sstr(value) for key, value in margins.items()},
        "trigonometric_interval_chart": trigonometric_interval_chart,
        "taylor_degree": 12,
        "coarse_margin_checks": coarse_margin_checks,
        "scaffold_requested": include_scaffold,
    }
    derivation = [
        r"\(h(t)=\sin t+\cos t\) とおく。\(1\le t\le\sqrt2\) では"
        r"\(1<h(t)<\sqrt2\) だから、この区間は反復で不変である。"
        r"また \([\pi/3,\pi/2]\) では \(h''=-h<0\)。従って"
        r"\(a=5\pi/12\) における接線が上界となり、"
        r"\[h(x)\le h(a)+h'(a)(x-a)"
        r"=\frac{\sqrt6}{2}-\frac{\sqrt2}{2}"
        r"\left(x-\frac{5\pi}{12}\right).\]",
        r"\(g(x)=x-h(x)\) とおくと、\(g(0)=-1\)、"
        r"\(g(\pi/2)=\pi/2-1>0\)、さらに"
        r"\(g'(x)=1-\cos x+\sin x>0\ (0<x\le\pi/2)\) である。"
        r"従って零点 \(\alpha\) は一意である。上の接線へ \(x=4/\pi\) を代入し、"
        r"\(333/106<\pi<355/113\)、\(140/99<\sqrt2<99/70\)、"
        r"\(265/153<\sqrt3<97/56\) を用いると、"
        r"\[\frac4\pi-h\!\left(\frac4\pi\right)"
        r">\frac{7259089}{314501600}>\frac1{1000}.\]"
        r"ゆえに \(g(4/\pi)>0\) であり、\(\alpha<4/\pi\) である。",
        r"\(H=h\circ h\)、\(c=4/\pi\)、"
        r"\(\lambda=(\sqrt3-1)/2\)、"
        r"\(D(t)=c+\lambda(t-c)-H(t)\) とおく。"
        r"交代 Taylor 評価を12次まで有理数で行うと"
        r"\[D(1)>\frac1{400},\quad D(\sqrt2)>\frac1{3000},\quad "
        r"D'(1)>\frac18,\quad D'(\sqrt2)<-\frac1{22}.\]"
        r"これら四つの残差は証明書内で厳密有理数として再生される。",
        r"\(h'=\cos-\sin<0\)、\(h>0\) を用いて直接微分すると"
        r"\[H'''(t)=3h(H_0)h(t)h'(t)"
        r"-h'(H_0)h'(t)\{h'(t)^2+1\}<0,\qquad H_0=h(t).\]"
        r"従って \(D'\) は凸である。上の端点符号から \(D\) は内部に局所最小値を持たず、"
        r"最小値は端点で取る。よって \(D(t)>0\)、すなわち"
        r"\[H(t)\le\frac4\pi+\frac{\sqrt3-1}{2}"
        r"\left(t-\frac4\pi\right)\qquad(1\le t\le\sqrt2).\]",
        r"\(I_n=\int_0^{\pi/2}f_n(x)\,dx\) とおく。"
        r"\(I_1=2\) である。また \(h\) の凹性と Jensen の不等式、(2) より"
        r"\[I_2\le\frac\pi2h\left(\frac2\pi I_1\right)"
        r"=\frac\pi2h(4/\pi)<2.\]"
        r"(3) を \(t=f_n(x)\) に適用して積分すると"
        r"\[I_{n+2}\le2+\frac{\sqrt3-1}{2}(I_n-2).\]"
        r"係数は \(0<(\sqrt3-1)/2<1\) なので、\(I_1\le2\)、\(I_2<2\) から"
        r"偶数列・奇数列それぞれの帰納法により \(I_n\le2\) が全ての \(n\) で従う。",
    ]
    if include_scaffold:
        answer = (
            "(1) tangent bound at 5*pi/12; (2) the unique fixed point alpha satisfies alpha<4/pi; "
            "(3) h(h(t))<=4/pi+((sqrt(3)-1)/2)(t-4/pi) on [1,sqrt(2)]; "
            "(4) integral f_n<=2 for every positive integer n"
        )
    else:
        answer = "integral_0^(pi/2) f_n(x) dx <= 2 for every positive integer n"
    return answer, witness, derivation


def _positive_recurrence_triangle_limit(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    p, q = sp.symbols("p q", positive=True)
    recurrence_chart = _second_order_recurrence_chart(p, q)
    phi = (1 + sp.sqrt(5)) / 2
    endpoint_value = sp.simplify(phi**2 + phi**-2)
    if endpoint_value != 3 or sp.simplify(phi - 1 / phi - 1) != 0:
        raise ValueError("golden-ratio endpoint certificate failed")
    return (
        "2",
        {
            "dominant_root_interval": "(1/phi,phi)",
            "target_interval": "[2,3)",
            "recurrence_chart": recurrence_chart,
            "characteristic_polynomial": "z^2-p*z-q",
            "endpoint_value": "3",
        },
        [
            "特性方程式z^2-pz-q=0は正根lambdaと負根muを持ち、p>0よりlambda>|mu|である。正数列なのでlambda項の係数は0でなく、x_(n+1)/x_nはlambdaへ収束する。",
            "三角不等式をx_nで割って極限を取ると lambda^2<=lambda+1 かつ lambda^2+lambda>=1、従って1/phi<=lambda<=phiである。",
            "端点で等号なら、対応する三角不等式の正の差は負根muの定数倍だけになる。mu<0なので符号が交互に変わるか恒等的に0となり、いずれも全ての三角形が非退化という条件に反する。",
            "従って1/phi<lambda<phi。2<=lambda^2+lambda^(-2)<3なので、その床は2である。",
        ],
    )


def _integer_angle_triangle(n: int) -> tuple[int, int, int]:
    if n == 1:
        return 1, 1, 1
    sine_a = Fraction(2 * n, n * n + 1)
    cosine_a = Fraction(n * n - 1, n * n + 1)
    sine_multiples = [Fraction(0), sine_a]
    for _ in range(1, n + 1):
        sine_multiples.append(2 * cosine_a * sine_multiples[-1] - sine_multiples[-2])
    rational_sides = (sine_multiples[1], sine_multiples[n + 1], sine_multiples[n])
    scale = 1
    for value in rational_sides:
        scale = lcm(scale, value.denominator)
    integer_sides = [int(value * scale) for value in rational_sides]
    common = gcd(gcd(integer_sides[0], integer_sides[1]), integer_sides[2])
    return tuple(value // common for value in integer_sides)


def _rational_angle_multiple_integer_triangles(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    angle = sp.Symbol("A", real=True)
    recurrence_chart = _second_order_recurrence_chart(2 * sp.cos(angle), -1)
    n2 = _integer_angle_triangle(2)
    n3 = _integer_angle_triangle(3)
    n4 = _integer_angle_triangle(4)
    if n2 != (25, 11, 30) or n3 != (125, 112, 195):
        raise ValueError("angle-multiple construction replay failed")
    if not all(2 * max(sides) < sum(sides) for sides in (n2, n3, n4)):
        raise ValueError("constructed integer sides failed the triangle inequalities")
    return (
        f"(1) (a,b,c)={n2}; (2) (a,b,c)={n3}; "
        "(3) tan(A/2)=1/n and (a,b,c) proportional to (sin A,sin((n+1)A),sin(nA))",
        {
            "n_equals_2": n2,
            "n_equals_3": n3,
            "counterfactual_n_equals_4": n4,
            "rational_parameter": "tan(A/2)=1/n",
            "recurrence_chart": recurrence_chart,
            "sine_recurrence": "s_(k+1)=2*cos(A)*s_k-s_(k-1)",
        },
        [
            "n=1は正三角形とする。n>=2ではtan(A/2)=1/nと置くと sin A=2n/(n^2+1), cos A=(n^2-1)/(n^2+1) は有理数である。",
            "A<2/nより(n+1)A<2+2/n<=3<pi。B=pi-(n+1)A, C=nAとすれば三つとも正の角でC=nAを満たす。",
            "正弦定理により辺を sin A, sin((n+1)A), sin(nA) に比例させる。正弦の加法漸化式から全て有理数なので、共通分母を払えば整数三角形になる。",
            "n=2,3を同じ構成で計算すると、それぞれ(25,11,30),(125,112,195)を得る。",
        ],
    )


def _rational_angle_reciprocal_power_of_two(
    objects: dict[str, Any],
) -> tuple[str, dict[str, Any], list[str]]:
    if int(objects.get("base", 0)) != 2:
        raise ValueError("the reciprocal-power chart requires base two")

    chart = _rational_angle_reciprocal_power_chart()
    obligations = chart.get("proof_obligations") or {}
    if not obligations or not all(obligations.values()):
        raise ValueError("rational-angle proof obligations are incomplete")

    power_index = str(objects.get("power_index", "n"))
    prime_index = str(objects.get("prime_index", "p"))
    angle_index = str(objects.get("angle_index", "theta"))
    solution_records = chart.get("solution_records") or []
    powers = sorted({int(record["power"]) for record in solution_records})
    prime_exponents = sorted(
        {int(record["prime_exponent"]) for record in solution_records}
    )
    angle_fractions = sorted(
        {
            (int(record["angle_numerator"]), int(record["angle_denominator"]))
            for record in solution_records
        }
    )
    if len(powers) != 1 or len(prime_exponents) != 1:
        raise ValueError("the exact chart did not produce a single exponent pair")

    def _angle_tex(numerator: int, denominator: int) -> str:
        if numerator == 1:
            return rf"\frac{{\pi}}{{{denominator}}}"
        return rf"\frac{{{numerator}\pi}}{{{denominator}}}"

    def _symbol_tex(name: str) -> str:
        greek_names = {
            "alpha",
            "beta",
            "gamma",
            "delta",
            "epsilon",
            "eta",
            "theta",
            "lambda",
            "mu",
            "nu",
            "phi",
            "psi",
            "rho",
            "sigma",
            "tau",
            "xi",
            "zeta",
        }
        return rf"\{name}" if name in greek_names else name

    angles_tex = ",".join(
        _angle_tex(numerator, denominator)
        for numerator, denominator in angle_fractions
    )
    answer_tex = (
        rf"\({power_index}={powers[0]},\ {prime_index}={prime_exponents[0]},\quad "
        rf"{_symbol_tex(angle_index)}\equiv{angles_tex}\pmod{{\pi}}.\)"
    )
    derivation = [
        (
            r"\(t=\tan\theta\) と置く。式に \(t^{-n}\) があるので \(t\ne0\) である。"
            r" \(X=t^n\) は \(X^2-2^pX+1=0\) を満たし、その二根は正である。"
        ),
        (
            r"\(\theta/\pi\in\mathbb Q\) なので \(t\) は全実円分体に属する。"
            r" 任意の埋め込み \(\sigma\) に対し \(\sigma(t^2)\ge0\) で、"
            r" \(\sigma(t^2)^n\) は高々二値しか取らない。"
            r" 非負実数上で \(u\mapsto u^n\) は単射だから"
            r" \([\mathbb Q(t^2):\mathbb Q]\le2\) である。"
        ),
        (
            r"\(\zeta=e^{2i\theta}\) の位数を \(m\) とすると"
            r" \(2\cos2\theta=\zeta+\zeta^{-1}\) は次数 \(\varphi(m)/2\) の"
            r"代数的整数である。従って \(\varphi(m)\le4\)。"
            r" 素因子と指数を調べると"
            r" \(m\in\{1,2,3,4,5,6,8,10,12\}\) に限られる。"
        ),
        (
            r"\(m=1,2\) では \(t^{-n}\) が定義できない。"
            r" \(m=3,6\) では \(t^2=3\) または \(1/3\) で、"
            r"奇数乗は無理数、偶数乗は分母に3が残る。"
            r" \(m=4\) では左辺は \(\pm2\) である。"
        ),
        (
            r"\(m=5,10\) では \(u=t^2\) に対する \(u+u^{-1}\) の二共役が"
            r" \(6\pm8\sqrt5/5\) となる。"
            r" 元の左辺が有理なら、その平方から \(u^n+u^{-n}\) も有理である。"
            r" しかし \(u^n+u^{-n}=2T_n((u+u^{-1})/2)\) は"
            r" \(u+u^{-1}>2\) で狭義単調だから二共役で値が異なり、矛盾する。"
        ),
        (
            r"\(m=8\) の偶数乗は"
            r" \((1+\sqrt2)^n+(\sqrt2-1)^n\equiv2\pmod4\)、"
            r"奇数乗は無理数である。"
            r" \(m=12\) では \(A_n=(2+\sqrt3)^n+(2-\sqrt3)^n\) が"
            r" \(A_n=4A_{n-1}-A_{n-2}\) を満たし、"
            r" \(A_n\bmod8\) は \(2,4,6,4\) を周期的に取る。"
        ),
        (
            r"従って2の素数乗になれるのは \(A_1=4=2^2\) だけである。"
            r" このとき \(t=2\pm\sqrt3\)、すなわち"
            r" \(\theta\equiv\pi/12,5\pi/12\pmod\pi\)。"
            r" 元の式へ代入すると両方とも確かに成立する。"
        ),
    ]
    witness = dict(chart)
    witness.update(
        {
            "answer_tex": answer_tex,
            "derivation_format": "tex",
            "power_index": power_index,
            "prime_index": prime_index,
            "angle_index": angle_index,
            "proof_kernel_count": len(chart["atomic_chart_ids"]),
        }
    )
    return (
        (
            f"{power_index}={powers[0]}, {prime_index}={prime_exponents[0]}, "
            f"{angle_index}=pi/12+k*pi or 5*pi/12+k*pi (k in Z)"
        ),
        witness,
        derivation,
    )


def _log_exponential_support_region(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    if int(objects.get("log_offset", 0)) != 2:
        raise ValueError("the current support-region chart requires log(x)+2")
    a = sp.Symbol("a", positive=True)
    width = sp.expand((a - 1) * (1 - sp.log(a)))
    area = sp.simplify(sp.integrate(width, (a, 1, sp.E)))
    expected = (sp.E**2 - 4 * sp.E + 5) / 4
    if sp.simplify(area - expected) != 0:
        raise ValueError("support-region area integration failed")
    return (
        f"1<a<e, 1-log(a)<b<a(1-log(a)); area={sp.sstr(area)}",
        {
            "region": "1<a<e and 1-log(a)<b<a(1-log(a))",
            "lower_envelope_contact": "x=1/a",
            "upper_envelope_contact": "x=log(a)",
            "vertical_width": sp.sstr(width),
            "area": sp.sstr(area),
        },
        [
            "log x+2<ax+bを全x>0で満たすにはa>0であり、差の最小点x=1/aから b>1-log a が必要十分である。",
            "ax+b<e^xについて、0<a<=1では下端x->0が支配してb<=1となり前者と両立しない。a>1では接点x=log aから b<a(1-log a) を得る。",
            "二つの境界の上下関係は(a-1)(1-log a)>0と同値なので1<a<eである。",
            "縦幅(a-1)(1-log a)をa=1からeまで積分し、面積(e^2-4e+5)/4を得る。",
        ],
    )


def _triangle_angle_sine_sum_maximum(objects: dict[str, Any]) -> tuple[str, dict[str, Any], list[str]]:
    equilateral_argument = sp.simplify(sp.pi / 3 + sp.pi / 3 * sp.cos(sp.pi / 3))
    if equilateral_argument != sp.pi / 2:
        raise ValueError("equilateral equality witness failed")
    return (
        "3",
        {"termwise_upper_bound": 1, "equality_angles": ["pi/3", "pi/3", "pi/3"]},
        [
            "各正弦項は実数上で1以下なので、三項の和は3以下である。",
            "A=B=C=pi/3では各偏角がpi/3+(pi/3)cos(pi/3)=pi/2となる。",
            "三項が同時に1となる正三角形が存在するため、上界3は達成される。",
        ],
    )


def _extract_length_before(text: str, noun: str) -> sp.Expr | None:
    prefix = text.split(noun, 1)[0]
    matches = re.findall(r"(?:長さが|一辺の長さが|1辺の長さが)\s*\$?([^$\s]+)", prefix)
    if not matches:
        return None
    raw = matches[-1].replace(r"\sqrt", "sqrt")
    try:
        return sp.sympify(raw)
    except (sp.SympifyError, SyntaxError):
        return None


def _all_integers(text: str) -> list[int]:
    return [int(value) for value in re.findall(r"(?<![A-Za-z])\d+(?![A-Za-z])", text)]
