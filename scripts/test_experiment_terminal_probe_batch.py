from pathlib import Path

import pytest

from scripts.experiment_terminal_probe_batch import parse_case


def test_parse_case_preserves_problem_and_checkpoint() -> None:
    problem, checkpoint = parse_case("2017G4=data/checkpoint.json")

    assert problem == "2017G4"
    assert checkpoint == Path("data/checkpoint.json")


def test_parse_case_rejects_missing_path() -> None:
    with pytest.raises(Exception):
        parse_case("2017G4")
