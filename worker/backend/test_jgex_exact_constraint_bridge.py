import sympy as sp
import pytest

from worker.backend.jgex_exact_constraint_bridge import (
    ConstructionEquationBlock,
    _RelationalJGEXElaborator,
    _expand_polynomial_in_generators,
    _canonical_nonconstant_factor_keys,
    _nonzero_condition_follows_from_factors,
    _prepare_exact_system,
    _reduce_with_nondegeneracy_saturation,
    _replay_groebner_certificate,
    inspect_jgex_local_elimination,
    inspect_jgex_exact_system,
    lower_jgex_to_exact_obligation,
)


SETUP = (
    "c a b = r_triangle c a b; "
    "d = foot d c a b; "
    "x = on_line x c d; "
    "k = on_line k a x, on_circle k b c; "
    "l = on_line l b x, on_circle l a c; "
    "m = on_line m a l, on_line m b k"
)


def test_generator_only_expansion_preserves_exact_coefficient_charts() -> None:
    x, parameter = sp.symbols("x parameter")
    coefficient = (parameter + 1) ** 12
    expression = coefficient * (x + 1) ** 2

    lowered = _expand_polynomial_in_generators(expression, (x,))

    assert sp.expand(lowered - expression) == 0
    assert lowered.coeff(x, 2) == coefficient
    assert len(sp.Add.make_args(lowered.coeff(x, 2))) == 1


def test_local_division_requires_source_semantic_nondegeneracy() -> None:
    x, y = sp.symbols("x y")
    known = _canonical_nonconstant_factor_keys(6 * x**2 * (y + 1))

    assert _nonzero_condition_follows_from_factors("-2*x != 0", known)
    assert _nonzero_condition_follows_from_factors("x*(y + 1) != 0", known)
    assert not _nonzero_condition_follows_from_factors("x - y != 0", known)


def test_complex_future_clause_is_kept_as_a_typed_boundary() -> None:
    x = sp.Symbol("x")
    elaborator = _RelationalJGEXElaborator(enable_affine_local_lemmas=True)
    elaborator.active_clause_outputs = {"future_point"}
    elaborator.relational_outputs = {"future_point"}
    elaborator.equations = [sum((x + index) ** 3 for index in range(40))]

    assert elaborator._preserve_affine_clause_variables(
        ("on_line", "on_circle"),
        equation_start=0,
    )


def test_circle_intersection_axis_goal_projects_to_boundary_discriminant() -> None:
    px, py, qx, qy, tx, ty, ax, ay, bx, by = sp.symbols(
        "px py qx qy tx ty ax ay bx by"
    )
    elaborator = _RelationalJGEXElaborator(enable_affine_local_lemmas=True)
    elaborator.coordinates = {
        "p": (px, py),
        "q": (qx, qy),
        "t": (tx, ty),
        "a": (ax, ay),
        "b": (bx, by),
    }
    elaborator.circle_circle_intersections["t"] = ("p", "a", "q", "b", 7)

    projected = elaborator.goal(
        "coll", ("p", "q", "t"), factor_result=False
    )

    axis_norm = (qx - px) ** 2 + (qy - py) ** 2
    first_radius = (ax - px) ** 2 + (ay - py) ** 2
    second_radius = (bx - qx) ** 2 + (by - qy) ** 2
    expected = sp.expand(
        4 * axis_norm * first_radius
        - (axis_norm + first_radius - second_radius) ** 2
    )
    assert sp.expand(projected - expected) == 0
    assert projected.free_symbols.isdisjoint({tx, ty})
    assert elaborator.goal_dependency_points == ("a", "b", "p", "q")
    assert elaborator.goal_hidden_points == {"t"}
    certificate = elaborator.structural_lemma_certificates[-1]
    assert certificate.theorem == "circle_circle_axis_incidence_elimination"
    assert certificate.replayed
    assert certificate.composition_replayed
    assert certificate.replay_residuals == ("0", "0")


def test_circle_axis_projection_clears_rational_coordinates_homogeneously() -> None:
    px, py, pd, qx, qy, qd, ax, ay, bx, by = sp.symbols(
        "px py pd qx qy qd ax ay bx by"
    )
    elaborator = _RelationalJGEXElaborator(enable_affine_local_lemmas=True)
    polynomial, denominator = elaborator._projective_circle_axis_discriminant(
        (px / pd, py / pd),
        (qx / qd, qy / qd),
        (ax, ay),
        (bx, by),
    )
    axis_norm = (qx / qd - px / pd) ** 2 + (qy / qd - py / pd) ** 2
    first_radius = (ax - px / pd) ** 2 + (ay - py / pd) ** 2
    second_radius = (bx - qx / qd) ** 2 + (by - qy / qd) ** 2
    rational_discriminant = (
        4 * axis_norm * first_radius
        - (axis_norm + first_radius - second_radius) ** 2
    )

    assert sp.cancel(polynomial / denominator - rational_discriminant) == 0
    assert polynomial.is_polynomial()
    assert pd in elaborator.denominators
    assert qd in elaborator.denominators


def test_affine_point_boundary_projection_replays_cramers_rule() -> None:
    x, y = sp.symbols("x y")
    elaborator = _RelationalJGEXElaborator(enable_affine_local_lemmas=True)
    elaborator.coordinates = {"p": (x, y)}
    elaborator.construction_blocks = [
        ConstructionEquationBlock(
            clause_index=3,
            outputs=("p",),
            inputs=("a", "b", "c"),
            construction_vocabulary=("circumcenter",),
            introduced_variables=("x", "y"),
            surviving_equations=("2*x + 3*y - 7", "5*x - y - 9"),
            local_lemma_count=0,
        )
    ]

    projection = elaborator._project_affine_point_boundary("p")

    assert projection is not None
    replacement, inputs = projection
    assert inputs == ("a", "b", "c")
    assert sp.cancel((2 * x + 3 * y - 7).subs(dict(zip((x, y), replacement)))) == 0
    assert sp.cancel((5 * x - y - 9).subs(dict(zip((x, y), replacement)))) == 0
    certificate = elaborator.structural_lemma_certificates[-1]
    assert certificate.theorem == "affine_point_boundary_projection"
    assert certificate.replayed
    assert certificate.composition_replayed
    assert certificate.replay_residuals == ("0", "0")


def test_nondegeneracy_saturation_retains_a_replayable_multiplier() -> None:
    x, y = sp.symbols("x y")
    basis = sp.groebner((x * y,), x, y, order="grevlex")

    quotients, remainder, multiplier, assumptions = (
        _reduce_with_nondegeneracy_saturation(
            basis,
            y,
            (("x", x),),
            max_rounds=1,
        )
    )
    basis_expressions = tuple(poly.as_expr() for poly in basis.polys)
    replay = sp.expand(
        y * multiplier
        - sum(
            (quotient * polynomial for quotient, polynomial in zip(
                quotients, basis_expressions, strict=True
            )),
            sp.Integer(0),
        )
    )

    assert remainder == 0
    assert replay == 0
    assert multiplier == x
    assert assumptions == ("x",)


def test_rational_coefficient_saturation_uses_a_compatible_ground_domain() -> None:
    x, y = sp.symbols("x y")
    basis = sp.groebner((x * y,), x, y, order="grevlex", domain=sp.QQ)

    quotients, remainder, multiplier, assumptions = (
        _reduce_with_nondegeneracy_saturation(
            basis,
            sp.Rational(1, 2) * y,
            (("x/3", sp.Rational(1, 3) * x),),
            max_rounds=1,
        )
    )

    assert remainder == 0
    assert multiplier == x / 3
    assert assumptions == ("x/3",)
    assert quotients


def test_parameter_field_groebner_certificate_replays_coefficientwise() -> None:
    x, parameter = sp.symbols("x parameter")
    basis = sp.groebner((x - parameter,), x, domain=sp.EX)
    quotients, remainder = basis.reduce((x - parameter) * (parameter + 1))
    basis_expressions = tuple(polynomial.as_expr() for polynomial in basis.polys)

    assert _replay_groebner_certificate(
        goal=(x - parameter) * (parameter + 1),
        multiplier=sp.Integer(1),
        quotients=quotients,
        basis=basis_expressions,
        remainder=remainder,
        variables=(x,),
    )
    assert not _replay_groebner_certificate(
        goal=(x - parameter) * (parameter + 1) + 1,
        multiplier=sp.Integer(1),
        quotients=quotients,
        basis=basis_expressions,
        remainder=remainder,
        variables=(x,),
    )


def test_right_triangle_locus_congruence_replays_exactly() -> None:
    obligation = lower_jgex_to_exact_obligation(SETUP + " ? cong m k m l")
    assert obligation.exact_replay
    assert obligation.remainder == "0"
    assert obligation.channel == "cong"
    assert obligation.construction_vocabulary == (
        "foot",
        "on_circle",
        "on_line",
        "r_triangle",
    )
    assert obligation.nondegeneracy_conditions


def test_altered_congruence_is_not_accepted() -> None:
    obligation = lower_jgex_to_exact_obligation(SETUP + " ? cong m k m a")
    assert not obligation.exact_replay
    assert obligation.remainder != "0"


def test_point_renaming_preserves_certificate_result() -> None:
    renamed = (
        "u v w = r_triangle u v w; "
        "p = foot p u v w; "
        "q = on_line q u p; "
        "r = on_line r v q, on_circle r w u; "
        "s = on_line s w q, on_circle s v u; "
        "t = on_line t v s, on_line t w r"
    )
    obligation = lower_jgex_to_exact_obligation(renamed + " ? cong t r t s")
    assert obligation.exact_replay


def test_general_triangle_uses_same_locus_and_metric_kernel() -> None:
    obligation = lower_jgex_to_exact_obligation(
        "a b c = triangle a b c; x = on_line x a b, on_circle x a b ? cong a x a b"
    )
    assert obligation.exact_replay
    assert obligation.construction_vocabulary == ("on_circle", "on_line", "triangle")


def test_quadrangle_fixes_only_euclidean_gauge_and_keeps_fourth_point_free() -> None:
    obligation = lower_jgex_to_exact_obligation(
        "a b c d = quadrangle; m = midpoint m a b ? coll a m b"
    )
    assert obligation.exact_replay
    assert obligation.construction_vocabulary == ("midpoint", "quadrangle")
    assert any("d=(" in item for item in obligation.normalization_assumptions)


def test_orthocenter_and_circumcenter_are_eliminated_as_constructions() -> None:
    orthocenter = lower_jgex_to_exact_obligation(
        "a b c = triangle a b c; h = orthocenter h a b c ? perp a b c h"
    )
    circumcenter = lower_jgex_to_exact_obligation(
        "a b c = triangle a b c; o = circle o a b c ? cong o a o b"
    )
    assert orthocenter.exact_replay
    assert circumcenter.exact_replay


def test_circumcenter_surface_name_normalizes_to_the_same_exact_morphism() -> None:
    obligation = lower_jgex_to_exact_obligation(
        "a b c = triangle a b c; o = circumcenter o a b c ? cong o a o c"
    )
    assert obligation.exact_replay
    assert obligation.construction_vocabulary == ("circumcenter", "triangle")


def test_centroid_macro_is_one_affine_average_morphism() -> None:
    obligation = lower_jgex_to_exact_obligation(
        "a b c = triangle a b c; d e f g = centroid d e f g a b c ? coll a d g"
    )
    assert obligation.exact_replay
    assert obligation.construction_vocabulary == ("centroid", "triangle")


def test_excenter_uses_signed_barycentric_weights_without_label_rules() -> None:
    obligation = lower_jgex_to_exact_obligation(
        "a b c = triangle a b c; i = excenter i a b c; "
        "p = foot p i a b; q = foot q i a c ? cong i p i q"
    )
    assert obligation.exact_replay
    assert obligation.construction_vocabulary == ("excenter", "foot", "triangle")


def test_parallel_and_perpendicular_loci_share_the_direction_kernel() -> None:
    perpendicular = lower_jgex_to_exact_obligation(
        "a b c = triangle a b c; x = on_tline x a b c ? perp x a b c"
    )
    parallel = lower_jgex_to_exact_obligation(
        "a b c = triangle a b c; y = on_pline y a b c ? para y a b c"
    )
    altered = lower_jgex_to_exact_obligation(
        "a b c = triangle a b c; x = on_tline x a b c ? para x a b c"
    )
    assert perpendicular.exact_replay
    assert parallel.exact_replay
    assert not altered.exact_replay


def test_diameter_circle_lowers_to_thales_inner_product() -> None:
    obligation = lower_jgex_to_exact_obligation(
        "a b c = triangle a b c; x = on_dia x a b ? perp x a x b"
    )
    assert obligation.exact_replay
    assert obligation.construction_vocabulary == ("on_dia", "triangle")


def test_angle_bisector_points_use_one_typed_bisector_line() -> None:
    obligation = lower_jgex_to_exact_obligation(
        "a b c = triangle a b c; "
        "x = angle_bisector x a b c; "
        "y = angle_bisector y a b c ? coll b x y"
    )
    assert obligation.exact_replay
    assert obligation.construction_vocabulary == ("angle_bisector", "triangle")
    assert any(
        assumption.startswith("principal_length")
        for assumption in obligation.normalization_assumptions
    )


def test_system_analysis_preserves_input_nondegeneracy_conditions() -> None:
    analysis = inspect_jgex_exact_system(
        "a b c = triangle a b c; x = on_tline x a b c ? perp x a b c",
        representation="relational",
    )
    assert analysis.normalization_assumptions
    assert analysis.nondegeneracy_conditions
    assert analysis.executable_regularity_conditions
    assert any(
        item.startswith("_base_0")
        for item in analysis.executable_regularity_conditions
    )
    assert all(item.endswith("!= 0") for item in analysis.nondegeneracy_conditions)


def test_incenter2_constructs_the_three_typed_perpendicular_feet() -> None:
    obligation = lower_jgex_to_exact_obligation(
        "a b c = triangle a b c; d e f i = incenter2 d e f i a b c ? perp i d b c"
    )
    assert obligation.exact_replay
    assert obligation.construction_vocabulary == ("incenter2", "triangle")
    assert (
        sum(
            assumption.startswith("principal_length")
            for assumption in obligation.normalization_assumptions
        )
        == 3
    )


def test_incenter_survives_point_renaming_without_problem_rules() -> None:
    obligation = lower_jgex_to_exact_obligation(
        "u v w = triangle u v w; j = incenter j u v w; d = foot d j v w ? perp j d v w"
    )
    assert obligation.exact_replay
    assert obligation.construction_vocabulary == ("foot", "incenter", "triangle")


def test_mirror_and_line_reflection_are_deterministic_affine_morphisms() -> None:
    mirror = lower_jgex_to_exact_obligation(
        "a b c = triangle a b c; x = mirror x a b ? cong b a b x"
    )
    altered_mirror = lower_jgex_to_exact_obligation(
        "a b c = triangle a b c; x = mirror x a b ? cong a x a b"
    )
    reflection = lower_jgex_to_exact_obligation(
        "a b c = triangle a b c; x = reflect x a b c ? perp b c a x"
    )
    assert mirror.exact_replay
    assert not altered_mirror.exact_replay
    assert reflection.exact_replay


def test_perpendicular_bisector_is_a_metric_locus() -> None:
    obligation = lower_jgex_to_exact_obligation(
        "a b c = triangle a b c; x = on_bline x a b ? cong x a x b"
    )
    assert obligation.exact_replay


def test_official_free_segment_semantics_replay_exactly() -> None:
    obligation = lower_jgex_to_exact_obligation(
        "p q = segment ? cong p q p q"
    )

    assert obligation.exact_replay
    assert obligation.construction_vocabulary == ("segment",)
    assert any("segment introduces two free points" in item for item in obligation.normalization_assumptions)


def test_segment_after_an_existing_figure_remains_independent() -> None:
    analysis = inspect_jgex_exact_system(
        "a b c = triangle; p q = segment ? cong p q p q",
        representation="relational",
    )
    coordinates = dict(analysis.point_coordinates)

    assert coordinates["p"] != coordinates["a"]
    assert coordinates["q"] != coordinates["b"]
    assert "diff p q" in analysis.normalization_assumptions


def test_isosceles_triangle_after_an_existing_figure_keeps_its_pose() -> None:
    analysis = inspect_jgex_exact_system(
        "a b c = triangle; u v w = iso_triangle ? cong u v u w",
        representation="relational",
    )
    coordinates = dict(analysis.point_coordinates)

    assert coordinates["u"] != coordinates["a"]
    assert any("isosceles_vertex_x" in item for item in coordinates["u"])
    assert sp.expand(
        sum(
            (sp.sympify(left) - sp.sympify(right)) ** 2
            for left, right in zip(coordinates["u"], coordinates["v"], strict=True)
        )
        - sum(
            (sp.sympify(left) - sp.sympify(right)) ** 2
            for left, right in zip(coordinates["u"], coordinates["w"], strict=True)
        )
    ) == 0


def test_remaining_hageo_locus_vocabulary_has_generic_polynomial_semantics() -> None:
    circum = lower_jgex_to_exact_obligation(
        "a b c = triangle a b c; x = on_circum x a b c ? cyclic a b c x"
    )
    distance = lower_jgex_to_exact_obligation(
        "a b c = triangle a b c; x = eqdistance x a b c ? cong x a b c"
    )
    free = lower_jgex_to_exact_obligation(
        "a = free a; b c d = triangle b c d; x = midpoint x a b ? coll a b x"
    )
    equilateral = lower_jgex_to_exact_obligation(
        "a b c = ieq_triangle a b c ? cong a b b c"
    )
    isosceles = lower_jgex_to_exact_obligation(
        "a b c = iso_triangle ? cong a b a c"
    )

    assert circum.exact_replay
    assert distance.exact_replay
    assert free.exact_replay
    assert equilateral.exact_replay
    assert isosceles.exact_replay
    assert isosceles.construction_vocabulary == ("iso_triangle",)


def test_four_point_cyclic_goal_uses_the_unsquared_determinant() -> None:
    analysis = inspect_jgex_exact_system(
        "a b c = triangle a b c; d = free d ? cyclic a b c d",
        representation="relational",
    )
    coordinates = {
        point: tuple(sp.sympify(value) for value in values)
        for point, values in analysis.point_coordinates
    }
    rows = []
    for point in ("a", "b", "c", "d"):
        x, y = coordinates[point]
        rows.append((x * x + y * y, x, y, sp.Integer(1)))
    determinant = sp.det(sp.Matrix(rows))

    assert sp.expand(sp.sympify(analysis.goal_polynomial) - determinant) == 0


def test_two_locus_intersection_excludes_a_shared_existing_root() -> None:
    analysis = inspect_jgex_exact_system(
        "a b c = triangle a b c; o = circumcenter o a b c; "
        "p = midpoint p a b; "
        "k = on_circle k o a, on_circle k p a ? cong k a k a",
        representation="relational",
    )
    coordinates = {
        point: tuple(sp.sympify(value) for value in values)
        for point, values in analysis.point_coordinates
    }
    kx, ky = coordinates["k"]
    ax, ay = coordinates["a"]
    distinctness = sp.factor((kx - ax) ** 2 + (ky - ay) ** 2)
    distinctness_numerator = sp.factor(sp.together(distinctness).as_numer_denom()[0])
    conditions = tuple(
        sp.factor(sp.sympify(item.removesuffix(" != 0")))
        for item in analysis.nondegeneracy_conditions
    )

    assert "diff k a" in analysis.normalization_assumptions
    assert any(
        sp.cancel(distinctness_numerator / condition).is_polynomial()
        for condition in conditions
    )


def test_2022_chn_circle_intersection_preserves_newclids_branch_choice() -> None:
    analysis = inspect_jgex_exact_system(
        "a b c = triangle a b c; o = circumcenter o a b c; "
        "p = on_bline p a o, on_pline p o b c; "
        "d = on_aline d b a b a c, on_aline d c a c a b; "
        "q = midpoint q a d; "
        "k = on_circle k p a, on_circle k q a ? cyclic k b c d",
        representation="relational",
    )

    assert "diff k a" in analysis.normalization_assumptions


def test_2022_chn_angle_loci_export_their_cramer_determinant() -> None:
    analysis = inspect_jgex_exact_system(
        "a b c = triangle a b c; "
        "d = on_aline d b a b a c, on_aline d c a c a b ? coll a b c",
        representation="relational",
    )
    coordinates = {
        point: tuple(sp.sympify(value) for value in values)
        for point, values in analysis.point_coordinates
    }
    base = coordinates["b"][0]
    apex_x, apex_y = coordinates["c"]
    required_factor = sp.factor(3 * apex_x**2 - apex_y**2)
    conditions = tuple(
        sp.factor(sp.sympify(item.removesuffix(" != 0")))
        for item in analysis.nondegeneracy_conditions
    )

    assert any(
        sp.cancel(condition / required_factor).is_polynomial(base, apex_x, apex_y)
        for condition in conditions
    )
    assert any(
        item.startswith("unique_linear_intersection d:")
        for item in analysis.normalization_assumptions
    )


def test_affine_compression_substitutes_nondegeneracy_conditions_too() -> None:
    analysis = inspect_jgex_exact_system(
        "a b c = triangle a b c; o = circumcenter o a b c; "
        "p = on_bline p a o, on_pline p o b c; "
        "d = on_aline d b a b a c, on_aline d c a c a b; "
        "q = midpoint q a d; "
        "k = on_circle k p a, on_circle k q a ? cyclic k b c d",
        representation="relational",
        enable_affine_local_lemmas=True,
    )
    remaining_variables = {sp.Symbol(name) for name in analysis.variables}
    coordinate_parameters = {
        symbol
        for _, coordinates in analysis.point_coordinates
        for coordinate in coordinates
        for symbol in sp.sympify(coordinate).free_symbols
    }
    allowed_symbols = remaining_variables | coordinate_parameters

    for condition in analysis.nondegeneracy_conditions:
        expression = sp.sympify(condition.removesuffix(" != 0"))
        assert expression.free_symbols <= allowed_symbols


def test_shared_circle_root_is_deflated_with_an_exact_local_certificate() -> None:
    analysis = inspect_jgex_exact_system(
        "a b c = triangle a b c; o = circumcenter o a b c; "
        "p = midpoint p a b; "
        "k = on_circle k o a, on_circle k p a ? cong k a k a",
        representation="relational",
    )
    certificates = tuple(
        item
        for item in analysis.structural_lemma_certificates
        if item.theorem == "circle_circle_known_root_deflation"
    )

    assert len(certificates) == 1
    assert certificates[0].replayed
    assert certificates[0].composition_replayed
    assert certificates[0].replay_residuals == ("0", "0")
    assert "diff k a" in analysis.normalization_assumptions


def test_nonterminal_shared_circle_root_stays_relational() -> None:
    analysis = inspect_jgex_exact_system(
        "a b c = triangle a b c; o = circumcenter o a b c; "
        "p = midpoint p a b; "
        "k = on_circle k o a, on_circle k p a; "
        "m = midpoint m k a ? coll a m k",
        representation="relational",
        enable_affine_local_lemmas=True,
    )

    output_coordinates = dict(analysis.point_coordinates)["k"]
    assert set(output_coordinates) <= set(analysis.variables)
    assert len(analysis.construction_equations) >= 2


def test_shared_circle_root_deflation_depends_on_structure_not_point_names() -> None:
    analysis = inspect_jgex_exact_system(
        "u v w = triangle u v w; z = circumcenter z u v w; "
        "n = midpoint n u v; "
        "x = on_circle x z u, on_circle x n u ? cong x u x u",
        representation="relational",
    )
    certificate = analysis.structural_lemma_certificates[0]

    assert certificate.theorem == "circle_circle_known_root_deflation"
    assert certificate.inputs == ("z", "n", "u")
    assert certificate.output == "x"
    assert certificate.replay_residuals == ("0", "0")


def test_second_request_for_the_same_circle_intersection_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="circle intersection reuses an already-existing point: k",
    ):
        inspect_jgex_exact_system(
            "a b c = triangle a b c; o = circumcenter o a b c; "
            "p = midpoint p a b; "
            "k = on_circle k o a, on_circle k p a; "
            "l = on_circle l o a, on_circle l p a ? cong l a l a",
            representation="relational",
        )


def test_remaining_hageo_goal_predicates_share_the_exact_kernel() -> None:
    setup = "a b c = triangle a b c; m = midpoint m a b"
    equal_angle = lower_jgex_to_exact_obligation(
        setup + " ? eqangle a b a c a b a c"
    )
    unequal_angle = lower_jgex_to_exact_obligation(
        setup + " ? eqangle a b a c a b b c"
    )
    equal_ratio = lower_jgex_to_exact_obligation(
        setup + " ? eqratio a b a c a b a c"
    )
    unequal_ratio = lower_jgex_to_exact_obligation(
        setup + " ? eqratio a b a c a b b c"
    )
    midpoint = lower_jgex_to_exact_obligation(setup + " ? midp m a b")
    wrong_midpoint = lower_jgex_to_exact_obligation(setup + " ? midp m a c")

    assert equal_angle.exact_replay
    assert not unequal_angle.exact_replay
    assert equal_ratio.exact_replay
    assert not unequal_ratio.exact_replay
    assert midpoint.exact_replay
    assert not wrong_midpoint.exact_replay


def test_midpoint_goal_replays_two_typed_components_and_their_composition() -> None:
    obligation = lower_jgex_to_exact_obligation(
        "a b c = triangle a b c; m = midpoint m a b ? midp m a b",
        representation="local_relational",
    )

    certificate = obligation.goal_decomposition_certificate
    assert obligation.exact_replay
    assert certificate is not None
    assert certificate.theorem == "midpoint_coordinate_conjunction"
    assert len(certificate.component_polynomials) == 2
    assert certificate.component_remainders == ("0", "0")
    assert certificate.composition_residual == "0"
    assert certificate.replayed


def test_angle_loci_emit_executable_polynomial_constraints() -> None:
    on_aline = lower_jgex_to_exact_obligation(
        "a b c = triangle a b c; x = on_line x a b, on_aline x a b b a c ? coll a b x",
        enable_affine_local_lemmas=True,
    )
    eqangle3 = lower_jgex_to_exact_obligation(
        "a b c = triangle a b c; x = on_line x a b, eqangle3 x a b a b c ? coll a b x",
        enable_affine_local_lemmas=True,
    )
    assert on_aline.exact_replay
    assert eqangle3.exact_replay
    assert on_aline.construction_equations or on_aline.local_lemma_certificates
    assert eqangle3.construction_equations or eqangle3.local_lemma_certificates
    assert all(item.replayed for item in on_aline.local_lemma_certificates)
    assert all(item.replayed for item in eqangle3.local_lemma_certificates)
    assert all(
        item.forward_residual == item.reverse_residual == "0"
        for item in (
            *on_aline.local_lemma_certificates,
            *eqangle3.local_lemma_certificates,
        )
    )


def test_circle_circle_tangent_is_a_typed_polynomial_relation() -> None:
    obligation = lower_jgex_to_exact_obligation(
        "o a u = triangle o a u; w b v = triangle w b v; "
        "x y z i = cc_tangent x y z i o a w b ? perp x o x y"
    )
    assert obligation.exact_replay
    assert obligation.construction_vocabulary == ("cc_tangent", "triangle")
    assert (
        len(obligation.construction_equations)
        + len(obligation.local_lemma_certificates)
        >= 8
    )
    assert all(item.replayed for item in obligation.local_lemma_certificates)


def test_tangent_intersection_is_compressed_to_a_replayable_boundary_lemma() -> None:
    problem = (
        "o a u = triangle o a u; w b v = triangle w b v; "
        "x y z i = cc_tangent x y z i o a w b; "
        "k = on_line k x y, on_line k z i ? coll o w k"
    )
    obligation = lower_jgex_to_exact_obligation(problem)
    compressed = inspect_jgex_exact_system(problem)
    monolithic = inspect_jgex_exact_system(
        problem,
        enable_affine_local_lemmas=False,
        enable_structural_lemmas=False,
    )
    assert obligation.exact_replay
    assert len(obligation.structural_lemma_certificates) == 1
    lemma = obligation.structural_lemma_certificates[0]
    assert lemma.replayed
    assert lemma.output == "k"
    assert lemma.hidden_points == ("x", "y", "z", "i")
    assert len(lemma.boundary_equations) == 2
    assert all(item == "0" for item in lemma.replay_residuals)
    assert not any(
        name in equation
        for name in ("_free_x_6", "_free_y_7")
        for equation in obligation.construction_equations
    )
    # Structural compression now keeps every existential symbol that still
    # occurs in its two boundary equations.  It therefore reduces the system
    # by equations, even when the number of live ring generators is equal.
    assert compressed.variable_count <= monolithic.variable_count
    assert compressed.equation_count < monolithic.equation_count


def test_relational_elaboration_proves_basic_construction_semantics() -> None:
    foot = lower_jgex_to_exact_obligation(
        "a b c = triangle a b c; f = foot f a b c ? perp a f b c",
        representation="relational",
    )
    center = lower_jgex_to_exact_obligation(
        "a b c = triangle a b c; o = circle o a b c ? cong o a o b",
        representation="relational",
    )
    assert foot.exact_replay and center.exact_replay


def test_relational_ring_keeps_every_uneliminated_existential_coordinate() -> None:
    (
        elaborator,
        _,
        _,
        _,
        _,
        equations,
        variables,
    ) = _prepare_exact_system(
        "a b c = triangle a b c; "
        "q = on_line q a b, on_circle q a c; "
        "o = circle o q b c ? cong o q o b",
        enable_affine_local_lemmas=True,
        representation="relational",
        expand_equations=False,
    )

    existential_symbols = (
        set().union(*(equation.free_symbols for equation in equations))
        & elaborator.existential_coordinate_variables
    )
    assert existential_symbols <= set(variables)


def test_relational_ring_keeps_constrained_principal_lengths() -> None:
    (
        elaborator,
        _,
        _,
        _,
        _,
        equations,
        variables,
    ) = _prepare_exact_system(
        "a b c = triangle; i = incenter a b c ? coll a i b",
        representation="relational",
        expand_equations=False,
    )

    live_lengths = {
        variable
        for variable in elaborator.variables
        if variable.name.startswith("_length_")
        and any(variable in equation.free_symbols for equation in equations)
    }
    assert live_lengths
    assert live_lengths <= set(variables)


def test_relational_ring_keeps_constrained_free_locus_coordinates() -> None:
    (
        elaborator,
        _,
        _,
        _,
        _,
        equations,
        variables,
    ) = _prepare_exact_system(
        "a b c = triangle; o = circumcenter a b c; "
        "d = on_circle o a ? cong o d o a",
        representation="relational",
        expand_equations=False,
    )

    live_free_coordinates = {
        variable
        for variable in elaborator.variables
        if variable.name.startswith(("_free_x_", "_free_y_"))
        and any(variable in equation.free_symbols for equation in equations)
    }
    assert live_free_coordinates
    assert live_free_coordinates <= set(variables)


def test_direct_and_reflected_triangle_similarity_have_distinct_semantics() -> None:
    direct = lower_jgex_to_exact_obligation(
        "a b c = triangle a b c; q = midpoint q a b; "
        "r = midpoint r a c ? simtri a b c a q r"
    )
    wrong_orientation = lower_jgex_to_exact_obligation(
        "a b c = triangle a b c; q = midpoint q a b; "
        "r = midpoint r a c ? simtrir a b c a q r"
    )
    reflected = lower_jgex_to_exact_obligation(
        "a b c = triangle a b c; x = reflect x c a b "
        "? simtrir a b c a b x"
    )

    assert direct.exact_replay
    assert not wrong_orientation.exact_replay
    assert reflected.exact_replay


def test_bounded_local_elimination_exports_replayed_separator_certificates() -> None:
    analysis = inspect_jgex_local_elimination(
        "a b c = triangle a b c; m = midpoint m a b; n = midpoint n m c ? coll a m n",
        max_output_terms=64,
    )
    assert analysis.all_local_certificates_replayed
    assert analysis.reduced_variable_count <= analysis.initial_variable_count
    assert analysis.local_elimination.exact_replay


def test_local_relational_pipeline_replays_local_and_terminal_certificates() -> None:
    obligation = lower_jgex_to_exact_obligation(
        "a b c = triangle a b c; m = midpoint m a b ? coll a m b",
        representation="local_relational",
    )
    assert obligation.exact_replay
    assert obligation.reduction_strategy == "typed_local_elimination_then_groebner"
    assert obligation.local_elimination is not None
    assert obligation.local_elimination.exact_replay
    assert len(obligation.reduced_construction_equations) <= len(
        obligation.construction_equations
    )


def test_goal_directed_slice_excludes_unrelated_construction_branch() -> None:
    obligation = lower_jgex_to_exact_obligation(
        "a b c = triangle a b c; m = midpoint m a b; "
        "u = midpoint u a c ? coll a m b",
        representation="goal_local_relational",
    )
    assert obligation.exact_replay
    assert obligation.goal_relevant_clause_indices == (0, 1)
    assert obligation.excluded_clause_indices == (2,)
    assert len(obligation.reduced_construction_equations) < len(
        obligation.construction_equations
    )


def test_exact_pipeline_reports_replayable_stage_progress() -> None:
    events: list[dict[str, object]] = []
    obligation = lower_jgex_to_exact_obligation(
        "a b c = triangle a b c; m = midpoint m a b ? coll a m b",
        representation="goal_local_relational",
        progress_callback=events.append,
    )

    stages = [str(event["stage"]) for event in events]
    assert obligation.exact_replay
    assert stages[0] == "preparation_started"
    assert "preparation_completed" in stages
    assert "goal_slice_completed" in stages
    assert "local_elimination_started" in stages
    assert "local_elimination_completed" in stages
    assert stages[-1] == "certificate_completed"
    assert all(float(event["elapsed_seconds"]) >= 0 for event in events)
