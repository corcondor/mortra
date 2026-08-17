from worker.backend.geometry_ar_residual import relation_equation, yuclid_ar_residual


def _deduction(name: str, *points: str) -> dict[str, object]:
    return {
        "deduction_type": "rule",
        "assertions": [{"name": name, "points": list(points)}],
    }


def test_length_residual_closes_by_transitive_congruence() -> None:
    payload = {
        "all_deductions": [
            _deduction("cong", "a", "b", "c", "d"),
            _deduction("cong", "c", "d", "e", "f"),
        ]
    }

    result = yuclid_ar_residual(payload, (("cong", ("a", "b", "e", "f")),))

    assert result.supported_goal_count == 1
    assert result.closed_goal_count == 1
    assert result.residual_support_size == 0


def test_angle_residual_distinguishes_parallel_from_perpendicular() -> None:
    payload = {"all_deductions": [_deduction("para", "a", "b", "c", "d")]}

    result = yuclid_ar_residual(payload, (("perp", ("a", "b", "c", "d")),))

    assert result.closed_goal_count == 0
    assert result.goals[0].residual_terms == (("angle:#quarter_turn", "-1"),)


def test_cyclic_and_eqangle_have_additive_angle_coordinates() -> None:
    cyclic = relation_equation("cyclic", ("a", "b", "c", "d"))
    eqangle = relation_equation(
        "eqangle", ("b", "a", "d", "a", "b", "c", "d", "c")
    )

    assert cyclic is not None
    assert eqangle is not None
    assert cyclic[0] == eqangle[0] == "angle"
    assert cyclic[1] == {term: -value for term, value in eqangle[1].items()}
