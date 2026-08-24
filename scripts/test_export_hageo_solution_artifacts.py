from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from scripts import export_hageo_solution_artifacts as exporter


@dataclass
class _FakeArtifact:
    status: str = "unproved"
    solved: bool = False
    error: str | None = None
    diagram_svg: str = "<svg xmlns='http://www.w3.org/2000/svg'></svg>"
    proof_text: str | None = None
    proof_length: int = 0
    coordinates: tuple[object, ...] = ()
    construction_nodes: tuple[object, ...] = ()
    construction_edges: tuple[object, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {"status": self.status, "solved": self.solved}


def test_certified_trace_is_exported_without_second_auxiliary_search(
    tmp_path: Path, monkeypatch
) -> None:
    calls: list[bool] = []

    def fake_build(source: str, *, seed: int, include_auxiliary: bool):
        calls.append(include_auxiliary)
        return _FakeArtifact()

    monkeypatch.setattr(exporter, "build_newclid_solution_artifact", fake_build)
    _, row = exporter._export_one(
        "sample",
        "sample = free a b ? coll a b a",
        "certified artifact",
        True,
        str(tmp_path),
        0,
        "# audited proof\n",
        "data/sample.proof-trace.md",
    )

    assert calls == [False]
    assert row["solved"] is True
    assert row["certified_proof_text"] is True
    assert (tmp_path / "sample.proof.md").read_text(encoding="utf-8") == (
        "# audited proof\n"
    )


def test_unproved_export_writes_nonempty_status_document(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        exporter,
        "build_newclid_solution_artifact",
        lambda source, *, seed, include_auxiliary: _FakeArtifact(),
    )
    _, row = exporter._export_one(
        "open",
        "open = free a b ? coll a b a",
        "frozen formulation",
        False,
        str(tmp_path),
        0,
        None,
        None,
    )

    assert row["solved"] is False
    assert row["certified_proof_text"] is False
    assert "must not be counted as a solution" in (
        tmp_path / "open.proof.md"
    ).read_text(encoding="utf-8")
