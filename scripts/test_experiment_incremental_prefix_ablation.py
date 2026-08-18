from scripts.experiment_incremental_prefix_ablation import exact_search_equivalent


def _run(**changes: object) -> dict[str, object]:
    result: dict[str, object] = {
        "returncode": 0,
        "solved": True,
        "solved_path": ["foot(...)->d", "reflect(...)->e"],
        "evaluated_paths": 142,
        "error_count": 0,
        "input_sha256": "abc123",
    }
    result.update(changes)
    return result


def test_exact_search_equivalence_requires_matching_exact_input() -> None:
    assert exact_search_equivalent(_run(), _run())
    assert not exact_search_equivalent(
        _run(), _run(input_sha256="different")
    )


def test_unsolved_none_hashes_are_not_treated_as_equivalent() -> None:
    assert not exact_search_equivalent(
        _run(solved=False, solved_path=None, input_sha256=None),
        _run(solved=False, solved_path=None, input_sha256=None),
    )
