"""Build readable MORTRA solutions for audited exact HAGeo certificates."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from worker.backend.jgex_exact_solution_writer import (  # noqa: E402
    build_jgex_exact_solution_artifact,
)


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalized_text_sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_text(encoding="utf-8").strip().encode("utf-8")
    ).hexdigest()


def _find_input(
    problem: str,
    artifact_path: Path,
    input_sha256: str,
) -> Path | None:
    direct = artifact_path.parent.parent / "inputs" / f"{problem}.txt"
    candidates = (
        direct,
        *ROOT.glob(f"data/**/inputs/{problem}.txt"),
        *ROOT.glob(f"data/**/{problem}*.txt"),
    )
    seen: set[Path] = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in seen or not candidate.is_file():
            continue
        seen.add(candidate)
        if not input_sha256 or _normalized_text_sha256(candidate) == input_sha256:
            return candidate
    return None


def build_readable_solutions(audit_path: Path, output_dir: Path) -> dict[str, object]:
    audit = _load(audit_path)
    records = audit.get("audited_incremental_artifacts", {})
    if not isinstance(records, dict):
        raise ValueError("audit has no incremental artifact map")
    output_dir.mkdir(parents=True, exist_ok=True)
    built: dict[str, dict[str, object]] = {}
    skipped: dict[str, str] = {}
    for problem, raw in records.items():
        if not isinstance(raw, dict) or raw.get("certificate_kind") != "jgex_exact_json":
            continue
        artifact_path = ROOT / str(raw["artifact"])
        proof_path = ROOT / str(raw["proof_path"])
        artifact = _load(artifact_path)
        proof = _load(proof_path)
        outer_certificate = artifact.get("certificate", {})
        input_hash = (
            str(outer_certificate.get("input_sha256", ""))
            if isinstance(outer_certificate, dict)
            else ""
        )
        input_path = _find_input(str(problem), artifact_path, input_hash)
        if input_path is None:
            skipped[str(problem)] = "matching JGEX input was not found"
            continue
        certificate = proof.get("certificate")
        if not isinstance(certificate, dict):
            skipped[str(problem)] = "exact certificate is missing"
            continue
        solution = build_jgex_exact_solution_artifact(
            input_path.read_text(encoding="utf-8").strip(),
            certificate,
        )
        if solution.status != "verified":
            skipped[str(problem)] = "solution projection rejected the certificate"
            continue
        output_path = output_dir / f"{problem}.json"
        output_path.write_text(
            json.dumps(solution.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        markdown_path = output_dir / f"{problem}.md"
        markdown_path.write_text(solution.to_markdown(), encoding="utf-8")
        built[str(problem)] = {
            "input": input_path.relative_to(ROOT).as_posix(),
            "proof": proof_path.relative_to(ROOT).as_posix(),
            "solution": output_path.relative_to(ROOT).as_posix(),
            "readable_solution": markdown_path.relative_to(ROOT).as_posix(),
            "solution_file_sha256": _sha256(output_path),
            "readable_solution_file_sha256": _sha256(markdown_path),
            "solution_sha256": solution.solution_sha256,
        }
    report = {
        "experiment": "hageo_readable_solution_projection",
        "protocol": {
            "uses_external_llm": False,
            "source_audit": audit_path.relative_to(ROOT).as_posix(),
            "projection": "deterministic fields from replayed exact certificate",
        },
        "summary": {
            "built": len(built),
            "skipped": len(skipped),
        },
        "solutions": built,
        "skipped": skipped,
    }
    report_path = output_dir / "report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = build_readable_solutions(args.audit.resolve(), args.output_dir.resolve())
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
