from scripts.run_mortra_codex_fused_session import _stop_obligation


def test_solved_problem_has_no_stop_obligation() -> None:
    assert _stop_obligation(solved=True, source="a b c = triangle ? coll a b c") is None


def test_unproved_problem_keeps_typed_stop_obligation() -> None:
    obligation = _stop_obligation(
        solved=False,
        source="a b c = triangle ? coll a b c",
    )

    assert obligation is not None
    assert obligation["kind"] == "no_replayed_exact_certificate"
    assert obligation["nearest_chart_contracts"]
