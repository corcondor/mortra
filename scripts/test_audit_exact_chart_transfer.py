import json
from pathlib import Path

from scripts.audit_exact_chart_transfer import audit_transfer


ROOT = Path(__file__).resolve().parents[1]


def test_audit_transfer_uses_deterministic_complement(tmp_path: Path) -> None:
    source = (ROOT / "data" / "fixtures" / "2022G5.jgex.txt").read_text(
        encoding="utf-8"
    ).strip()
    dataset = tmp_path / "dataset.txt"
    dataset.write_text(
        f"known\n{source}\nunknown\n{source.rsplit('?', 1)[0]}? coll a b c\n",
        encoding="utf-8",
    )
    natural = tmp_path / "natural.json"
    natural.write_text("{}\n", encoding="utf-8")
    union = tmp_path / "union.json"
    union.write_text(
        json.dumps({"sets": {"primary_union": ["unknown"]}}) + "\n",
        encoding="utf-8",
    )

    report = audit_transfer(
        excluded_union_path=union,
        dataset_path=dataset,
        natural_dataset_path=natural,
        progress_every=0,
    )

    assert report["summary"]["dataset_total"] == 2
    assert report["summary"]["excluded_certified"] == 1
    assert report["summary"]["evaluated"] == 1
    assert report["summary"]["strict_matches"] == 1
    assert report["summary"]["ambiguous"] == 0
    assert report["sets"]["strict_matches"] == ["known"]
    assert report["results"]["known"]["chart_id"] == (
        "parallel-transversal-perpendicular-triangle-circles-tangent"
    )


def test_audit_transfer_excludes_observed_development_problems(
    tmp_path: Path,
) -> None:
    source = (ROOT / "data" / "fixtures" / "2022G5.jgex.txt").read_text(
        encoding="utf-8"
    ).strip()
    dataset = tmp_path / "dataset.txt"
    dataset.write_text(
        f"development\n{source}\nheld_out\n{source}\n",
        encoding="utf-8",
    )
    natural = tmp_path / "natural.json"
    natural.write_text("{}\n", encoding="utf-8")
    union = tmp_path / "union.json"
    union.write_text('{"sets": {"primary_union": []}}\n', encoding="utf-8")
    development = tmp_path / "development.txt"
    development.write_text("# chart source\ndevelopment\n", encoding="utf-8")

    report = audit_transfer(
        excluded_union_path=union,
        dataset_path=dataset,
        natural_dataset_path=natural,
        development_problems_path=development,
        progress_every=0,
    )

    assert report["summary"]["excluded_development"] == 1
    assert report["summary"]["evaluated"] == 1
    assert report["sets"]["excluded_development"] == ["development"]
    assert set(report["results"]) == {"held_out"}
