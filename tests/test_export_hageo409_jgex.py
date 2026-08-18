from scripts.export_hageo409_jgex import lower_known_dialect_constructions


def test_centroid_single_output_lowers_to_four_typed_outputs() -> None:
    lowered = lower_known_dialect_constructions(
        "a b c = triangle; g = centroid a b c ? coll a g b"
    )

    assert "g__median1 g__median2 g__median3 g = centroid" in lowered
    assert lowered.endswith("? coll a g b")


def test_centroid_four_outputs_repeats_typed_outputs_on_rhs() -> None:
    lowered = lower_known_dialect_constructions(
        "a b c = triangle; x y z g = centroid a b c ? coll a g b"
    )

    assert "x y z g = centroid x y z g a b c" in lowered


def test_ninepoints_lowers_to_midpoints_and_circumcenter() -> None:
    lowered = lower_known_dialect_constructions(
        "a b c = triangle; m1 m2 m3 n = ninepoints a b c ? cyclic x m1 m2 m3"
    )

    assert "m1 = midpoint b c" in lowered
    assert "m2 = midpoint c a" in lowered
    assert "m3 = midpoint a b" in lowered
    assert "n = circumcenter m1 m2 m3" in lowered


def test_equal_trapezoid_alias_is_lowered_by_vocabulary() -> None:
    lowered = lower_known_dialect_constructions(
        "a b c d = eq_trapezoid ? para a b c d"
    )

    assert "iso_trapezoid" in lowered
    assert "eq_trapezoid" not in lowered
