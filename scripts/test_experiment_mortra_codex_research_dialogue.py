import json
from pathlib import Path

from scripts.experiment_mortra_codex_research_dialogue import (
    CHART_ID,
    _attempt_summary,
    run_research_dialogue,
)
from worker.backend.exact_geometry_chart_portfolio import (
    certify_jgex_with_exact_chart_portfolio,
)
from worker.backend.mortra_research_dialogue import ResearchDialogueLedger


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "data/fixtures/major-arc-homothety-tangent.jgex.txt").read_text(
    encoding="utf-8"
).strip()
NATURAL = (
    ROOT / "data/fixtures/major-arc-homothety-tangent.natural.txt"
).read_text(encoding="utf-8").strip()


def test_control_treatment_cycle_is_persistent_and_resumable(tmp_path) -> None:
    union_path = tmp_path / "union.json"
    dataset_path = tmp_path / "dataset.txt"
    natural_path = tmp_path / "natural.json"
    output_path = tmp_path / "dialogue.json"
    union_path.write_text(
        json.dumps(
            {"sets": {"unresolved_frozen_problems": ["heldout-structural-probe"]}}
        ),
        encoding="utf-8",
    )
    dataset_path.write_text(
        f"heldout-structural-probe\n{SOURCE}\n",
        encoding="utf-8",
    )
    natural_path.write_text(
        json.dumps({"heldout-structural-probe": NATURAL}),
        encoding="utf-8",
    )

    first = run_research_dialogue(
        union_path=union_path,
        dataset_path=dataset_path,
        natural_dataset_path=natural_path,
        output_path=output_path,
    )
    second = run_research_dialogue(
        union_path=union_path,
        dataset_path=dataset_path,
        natural_dataset_path=natural_path,
        output_path=output_path,
    )

    assert first["decision"]["accepted"]
    assert first["decision"]["capability_union_delta"] == 1
    assert first["decision"]["frozen_unseen_score_delta"] == 0
    assert second["resumed"]
    ledger = ResearchDialogueLedger.load(output_path)
    cycle = ledger.cycle_entries(first["cycle_fingerprint"])
    assert [entry.kind for entry in cycle] == [
        "cohort_observation",
        "typed_hypothesis",
        "controlled_experiment",
        "decision",
    ]
    hypothesis = cycle[1].payload
    assert hypothesis["chart_id"] == CHART_ID
    assert "heldout-structural-probe" not in json.dumps(hypothesis)


def test_quantifier_repair_is_not_counted_as_a_raw_frozen_solve() -> None:
    source = (ROOT / "data/fixtures/2019IranTSTp15.jgex.txt").read_text(
        encoding="utf-8"
    )
    natural = json.loads(
        (ROOT / "data/hageo-409-natural-language-2026-08-26.json").read_text(
            encoding="utf-8"
        )
    )["2019IranTSTp15"]
    result = certify_jgex_with_exact_chart_portfolio(
        source,
        include_diagram=False,
        natural_statement=natural,
    )
    summary = _attempt_summary(result)

    assert summary["raw_chart_solved"]
    assert summary["proved_after_quantifier_repair_only"]
    assert not summary["solved"]
