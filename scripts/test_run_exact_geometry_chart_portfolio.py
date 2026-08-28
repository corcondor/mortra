import json
from pathlib import Path
import sys

from scripts.run_exact_geometry_chart_portfolio import main


ROOT = Path(__file__).resolve().parents[1]


def test_dataset_mode_materializes_only_strict_report_matches(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = (ROOT / "data" / "fixtures" / "2022G5.jgex.txt").read_text(
        encoding="utf-8"
    ).strip()
    dataset = tmp_path / "dataset.txt"
    dataset.write_text(f"known\n{source}\nignored\n{source}\n", encoding="utf-8")
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps({"sets": {"strict_matches": ["known"]}}) + "\n",
        encoding="utf-8",
    )
    natural = tmp_path / "natural.json"
    natural.write_text("{}\n", encoding="utf-8")
    output_dir = tmp_path / "artifacts"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_exact_geometry_chart_portfolio.py",
            "--dataset",
            str(dataset),
            "--problem-report",
            str(report),
            "--natural-json",
            str(natural),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert main() == 0
    artifact = json.loads(
        (output_dir / "known.artifact.json").read_text(encoding="utf-8")
    )
    assert artifact["solved"] is True
    assert artifact["problem_name"] == "known"
    assert (output_dir / "known.proof.md").is_file()
    assert not (output_dir / "ignored.artifact.json").exists()
