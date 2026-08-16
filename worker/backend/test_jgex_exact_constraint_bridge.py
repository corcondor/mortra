from worker.backend.jgex_exact_constraint_bridge import (
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


def test_orthocenter_and_circumcenter_are_eliminated_as_constructions() -> None:
    orthocenter = lower_jgex_to_exact_obligation(
        "a b c = triangle a b c; h = orthocenter h a b c ? perp a b c h"
    )
    circumcenter = lower_jgex_to_exact_obligation(
        "a b c = triangle a b c; o = circle o a b c ? cong o a o b"
    )
    assert orthocenter.exact_replay
    assert circumcenter.exact_replay


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
