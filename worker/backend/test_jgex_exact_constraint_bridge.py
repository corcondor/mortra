import sympy as sp

from worker.backend.jgex_exact_constraint_bridge import (
    _reduce_with_nondegeneracy_saturation,
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

    assert circum.exact_replay
    assert distance.exact_replay
    assert free.exact_replay
    assert equilateral.exact_replay


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
    assert compressed.variable_count < monolithic.variable_count
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
