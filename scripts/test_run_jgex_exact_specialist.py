from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "data" / "fixtures" / "jgex-exact-right-triangle-locus.txt"
CHN_2022_FIXTURE = (
    ROOT / "data" / "fixtures" / "2022CHNSouthEastMOg11p6.jgex.txt"
)
PROCESS_TIMEOUT_SECONDS = 120


def test_file_boundary_preserves_goal_and_exact_certificate(tmp_path: Path) -> None:
    output = tmp_path / "certificate.json"
    progress = tmp_path / "progress.json"
    completed = subprocess.run(
        (
            sys.executable,
            "-B",
            str(ROOT / "scripts" / "run_jgex_exact_specialist.py"),
            "--input",
            str(FIXTURE),
            "--output",
            str(output),
            "--progress-output",
            str(progress),
            "--representation",
            "explicit",
            "--max-saturation-rounds",
            "1",
        ),
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=PROCESS_TIMEOUT_SECONDS,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "proved"
    assert payload["certificate"]["exact_replay"] is True
    assert payload["certificate"]["channel"] == "cong"
    readable = output.with_suffix(".solution.md")
    assert readable.is_file()
    readable_text = readable.read_text(encoding="utf-8")
    assert "# MORTRA 模範解答" in readable_text
    assert payload["solution"]["certificate_sha256"] in readable_text
    checkpoint = json.loads(progress.read_text(encoding="utf-8"))
    assert checkpoint["status"] == "running"
    assert checkpoint["progress"]


def test_process_boundary_certifies_2022_chn_with_constructive_local_lemmas(
    tmp_path: Path,
) -> None:
    output = tmp_path / "2022-chn-certificate.json"
    completed = subprocess.run(
        (
            sys.executable,
            "-B",
            str(ROOT / "scripts" / "run_jgex_exact_specialist.py"),
            "--input",
            str(CHN_2022_FIXTURE),
            "--output",
            str(output),
            "--representation",
            "goal_local_relational",
            "--enable-affine-local-lemmas",
            "--max-saturation-rounds",
            "1",
        ),
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=PROCESS_TIMEOUT_SECONDS,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    certificate = payload["certificate"]
    assert payload["status"] == "proved"
    assert certificate["exact_replay"] is True
    assert certificate["remainder"] == "0"
    assert any(
        item["theorem"] == "circle_circle_known_root_deflation"
        for item in certificate["structural_lemma_certificates"]
    )


def test_ground_goal_override_certifies_an_intermediate_obligation(
    tmp_path: Path,
) -> None:
    output = tmp_path / "lemma.json"
    completed = subprocess.run(
        (
            sys.executable,
            "-B",
            str(ROOT / "scripts" / "run_jgex_exact_specialist.py"),
            "--input",
            str(FIXTURE),
            "--output",
            str(output),
            "--representation",
            "explicit",
            "--goal",
            "coll c d x",
        ),
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=PROCESS_TIMEOUT_SECONDS,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "proved"
    assert payload["certificate"]["channel"] == "coll"


def test_typed_relation_separator_accepts_replayed_native_facts(
    tmp_path: Path,
) -> None:
    source = tmp_path / "typed-source.txt"
    facts = tmp_path / "native-facts.json"
    output = tmp_path / "typed-certificate.json"
    source.write_text(
        "a b c = triangle a b c; d = free d; e = free e; f = free f "
        "? cong a b e f\n",
        encoding="utf-8",
    )
    facts.write_text(
        json.dumps(
            [
                {"predicate": "cong", "arguments": ["a", "b", "c", "d"]},
                {"predicate": "cong", "arguments": ["c", "d", "e", "f"]},
            ]
        ),
        encoding="utf-8",
    )
    completed = subprocess.run(
        (
            sys.executable,
            "-B",
            str(ROOT / "scripts" / "run_jgex_exact_specialist.py"),
            "--input",
            str(source),
            "--output",
            str(output),
            "--representation",
            "typed_relation_separator",
            "--native-facts",
            str(facts),
            "--goal",
            "cong a b e f",
        ),
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "proved"
    assert payload["certificate"]["exact_replay"] is True
    assert (
        payload["certificate"]["macaulay_attempts"][0]["certificate"][
            "replay_residual"
        ]
        == "0"
    )


def test_construction_block_dag_is_available_at_process_boundary(
    tmp_path: Path,
) -> None:
    source = tmp_path / "block-dag-source.txt"
    guidance = tmp_path / "guidance-relations.json"
    output = tmp_path / "block-dag-certificate.json"
    source.write_text(
        "a b c = triangle a b c; m = midpoint m a b ? coll a m b\n",
        encoding="utf-8",
    )
    guidance.write_text(
        json.dumps(
            [
                {
                    "predicate": "cong",
                    "arguments": ["a", "m", "m", "b"],
                }
            ]
        ),
        encoding="utf-8",
    )
    completed = subprocess.run(
        (
            sys.executable,
            "-B",
            str(ROOT / "scripts" / "run_jgex_exact_specialist.py"),
            "--input",
            str(source),
            "--output",
            str(output),
            "--representation",
            "construction_block_dag",
            "--guidance-relations",
            str(guidance),
        ),
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "proved"
    assert payload["certificate"]["root"]["proved"] is True
    assert payload["certificate"]["all_local_certificates_replayed"] is True
    assert (
        payload["certificate"]["elimination_ordering_strategy"]
        == "obligation_conditioned"
    )


def test_and_or_guidance_survives_the_process_boundary(tmp_path: Path) -> None:
    source = tmp_path / "branch-source.txt"
    relations = tmp_path / "relations.json"
    branches = tmp_path / "branches.json"
    output = tmp_path / "branch-certificate.json"
    relation = {
        "predicate": "cong",
        "arguments": ["a", "m", "m", "b"],
    }
    source.write_text(
        "a b c = triangle a b c; m = midpoint m a b ? coll a m b\n",
        encoding="utf-8",
    )
    relations.write_text(json.dumps([relation]), encoding="utf-8")
    branches.write_text(json.dumps([[relation]]), encoding="utf-8")

    completed = subprocess.run(
        (
            sys.executable,
            "-B",
            str(ROOT / "scripts" / "run_jgex_exact_specialist.py"),
            "--input",
            str(source),
            "--output",
            str(output),
            "--representation",
            "construction_block_dag",
            "--guidance-relations",
            str(relations),
            "--guidance-branches",
            str(branches),
        ),
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    certificate = payload["certificate"]
    assert certificate["elimination_ordering_strategy"] == "residual_conditioned"
    assert certificate["guidance_relation_branches"] == [["cong(a,m,m,b)"]]
    assert certificate["exact_replay"] is True
