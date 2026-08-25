from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.update_hageo_capability_union import build_union


def _write(path: Path, payload: object) -> str:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _base(path: Path) -> Path:
    _write(
        path,
        {
            "summary": {"total": 3},
            "sets": {"primary_union": ["known"]},
        },
    )
    return path


def _frozen(path: Path, names: list[str]) -> Path:
    _write(path, {"summary": {"total": 3}, "problem_names": names})
    return path


def test_update_union_accepts_only_replayed_exact_proof(tmp_path: Path) -> None:
    proof = tmp_path / "exact.json"
    proof_file_hash = _write(
        proof,
        {
            "status": "proved",
            "certificate": {
                "exact_replay": True,
                "remainder": "0",
                "certificate_sha256": "inner",
                "local_lemma_certificates": [],
                "structural_lemma_certificates": [],
            },
        },
    )
    addition = tmp_path / "addition.json"
    _write(
        addition,
        {
            "problem_name": "new",
            "solved": True,
            "certificate": {
                "source": "jgex_exact_elimination",
                "proof_path": str(proof),
                "proof_file_sha256": proof_file_hash,
                "proof_sha256": "inner",
            },
        },
    )

    result = build_union(
        _base(tmp_path / "base.json"),
        (addition,),
        _frozen(tmp_path / "frozen.json", ["known", "new", "heldout"]),
    )

    assert result["summary"]["primary_certified_solved"] == 2
    assert result["summary"]["unresolved_frozen_problems"] == 1
    assert result["sets"]["new_certified_unique"] == ["new"]
    assert result["sets"]["unresolved_frozen_problems"] == ["heldout"]
    assert (
        result["protocol"]["addition_artifacts"]["new"]["certificate_kind"]
        == "jgex_exact_json"
    )


def test_update_union_rejects_zero_remainder_claim_without_replay(
    tmp_path: Path,
) -> None:
    proof = tmp_path / "bad-exact.json"
    proof_file_hash = _write(
        proof,
        {
            "status": "proved",
            "certificate": {
                "exact_replay": False,
                "remainder": "0",
                "certificate_sha256": "inner",
                "local_lemma_certificates": [],
                "structural_lemma_certificates": [],
            },
        },
    )
    addition = tmp_path / "bad-addition.json"
    _write(
        addition,
        {
            "problem_name": "bad",
            "solved": True,
            "certificate": {
                "source": "jgex_exact_elimination",
                "proof_path": str(proof),
                "proof_file_sha256": proof_file_hash,
                "proof_sha256": "inner",
            },
        },
    )

    with pytest.raises(ValueError, match="exact_replay"):
        build_union(
            _base(tmp_path / "base.json"),
            (addition,),
            _frozen(tmp_path / "frozen.json", ["known", "bad", "heldout"]),
        )


def test_update_union_accepts_replayed_exact_chart(tmp_path: Path) -> None:
    source_hash = "source-hash"
    chart_hash = "chart-hash"
    proof = tmp_path / "chart.json"
    proof_file_hash = _write(
        proof,
        {
            "source_sha256": source_hash,
            "solved": True,
            "conditional": False,
            "ambiguous": False,
            "selected": {
                "source_sha256": source_hash,
                "theorem": "general-chart",
                "proof_status": "proved",
                "undischarged_obligations": [],
                "chart_certificate_sha256": chart_hash,
                "certificate": {
                    "theorem": "general-chart",
                    "certificate_sha256": chart_hash,
                    "replayed": True,
                    "all_conditions_discharged": True,
                    "replay_residuals": {"identity": "0"},
                },
                "application": {
                    "theorem": "general-chart",
                    "source_sha256": source_hash,
                    "chart_certificate_sha256": chart_hash,
                    "replayed": True,
                    "undischarged_nondegeneracy_obligations": [],
                },
            },
        },
    )
    addition = tmp_path / "chart-addition.json"
    _write(
        addition,
        {
            "problem_name": "new",
            "solved": True,
            "certificate": {
                "source": "jgex_exact_chart",
                "proof_path": str(proof),
                "proof_file_sha256": proof_file_hash,
                "proof_sha256": chart_hash,
                "input_sha256": source_hash,
            },
        },
    )

    result = build_union(
        _base(tmp_path / "base.json"),
        (addition,),
        _frozen(tmp_path / "frozen.json", ["known", "new", "heldout"]),
    )

    assert result["summary"]["primary_certified_solved"] == 2
    assert (
        result["protocol"]["addition_artifacts"]["new"]["certificate_kind"]
        == "jgex_exact_chart_json"
    )


def test_update_union_rejects_vacuous_unit_ideal_proof(tmp_path: Path) -> None:
    proof = tmp_path / "unit-ideal.json"
    proof_file_hash = _write(
        proof,
        {
            "status": "proved",
            "certificate": {
                "exact_replay": True,
                "remainder": "0",
                "groebner_basis": ["1"],
                "certificate_sha256": "inner",
                "local_lemma_certificates": [],
                "structural_lemma_certificates": [],
            },
        },
    )
    addition = tmp_path / "unit-addition.json"
    _write(
        addition,
        {
            "problem_name": "vacuous",
            "solved": True,
            "certificate": {
                "source": "jgex_exact_elimination",
                "proof_path": str(proof),
                "proof_file_sha256": proof_file_hash,
                "proof_sha256": "inner",
            },
        },
    )

    with pytest.raises(ValueError, match="nonvacuous_construction"):
        build_union(
            _base(tmp_path / "base.json"),
            (addition,),
            _frozen(
                tmp_path / "frozen.json",
                ["known", "vacuous", "heldout"],
            ),
        )


def test_update_union_rejects_problem_outside_frozen_split(tmp_path: Path) -> None:
    proof = tmp_path / "exact.json"
    proof_file_hash = _write(
        proof,
        {
            "status": "proved",
            "certificate": {
                "exact_replay": True,
                "remainder": "0",
                "certificate_sha256": "inner",
                "local_lemma_certificates": [],
                "structural_lemma_certificates": [],
            },
        },
    )
    addition = tmp_path / "outside-addition.json"
    _write(
        addition,
        {
            "problem_name": "outside",
            "solved": True,
            "certificate": {
                "source": "jgex_exact_elimination",
                "proof_path": str(proof),
                "proof_file_sha256": proof_file_hash,
                "proof_sha256": "inner",
            },
        },
    )

    with pytest.raises(ValueError, match="outside the frozen split"):
        build_union(
            _base(tmp_path / "base.json"),
            (addition,),
            _frozen(tmp_path / "frozen.json", ["known", "other", "heldout"]),
        )
