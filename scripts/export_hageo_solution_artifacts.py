"""Export MORTRA diagrams and proof text for an explicit HAGeo problem cohort."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from worker.backend.newclid_solution_artifact import (  # noqa: E402
    build_newclid_solution_artifact,
)


def _display(path: Path) -> str:
    resolved = path.resolve()
    return (
        resolved.relative_to(ROOT).as_posix()
        if resolved.is_relative_to(ROOT)
        else resolved.as_posix()
    )


def _dataset_entries(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) % 2:
        raise ValueError("JGEX dataset must contain name/formulation line pairs")
    return {
        lines[index].strip(): lines[index + 1].strip()
        for index in range(0, len(lines), 2)
    }


def _export_one(
    name: str,
    formulation: str,
    formulation_source: str,
    include_auxiliary: bool,
    output_dir_raw: str,
    seed: int,
    certified_proof_markdown: str | None,
    certificate_trace_source: str | None,
) -> tuple[str, dict[str, Any]]:
    output_dir = Path(output_dir_raw)
    artifact = build_newclid_solution_artifact(
        f"{name}\n{formulation}",
        seed=seed,
        # A certified formulation already contains its accepted construction path.
        # Searching for another auxiliary point here changes the audited problem.
        include_auxiliary=False,
    )
    payload = artifact.to_dict()
    svg_path = output_dir / f"{name}.diagram.svg"
    proof_path = output_dir / f"{name}.proof.md"
    json_path = output_dir / f"{name}.artifact.json"
    if artifact.diagram_svg:
        svg_path.write_text(artifact.diagram_svg, encoding="utf-8")
    proof_document = certified_proof_markdown or artifact.proof_text or (
        f"# {name}: no certified proof\n\n"
        "This search did not produce a certified proof. This file records status "
        "only and must not be counted as a solution.\n\n"
        f"- Solver status: `{artifact.status}`\n"
        f"- Error: `{artifact.error}`\n"
    )
    proof_path.write_text(proof_document, encoding="utf-8")
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    row = {
        "status": "proved" if certified_proof_markdown else artifact.status,
        "solved": True if certified_proof_markdown else artifact.solved,
        "render_solver_status": artifact.status,
        "render_solver_solved": artifact.solved,
        "error": artifact.error,
        "formulation_sha256": hashlib.sha256(
            formulation.encode("utf-8")
        ).hexdigest(),
        "formulation_source": formulation_source,
        "includes_certified_auxiliary_path": include_auxiliary,
        "coordinates": len(artifact.coordinates),
        "construction_nodes": len(artifact.construction_nodes),
        "construction_edges": len(artifact.construction_edges),
        "proof_length": artifact.proof_length,
        "certified_proof_text": bool(
            certified_proof_markdown or (artifact.solved and artifact.proof_text)
        ),
        "certificate_trace_source": certificate_trace_source,
        "diagram_generated": bool(artifact.diagram_svg),
        "diagram": _display(svg_path) if artifact.diagram_svg else None,
        "proof_text": _display(proof_path),
        "artifact": _display(json_path),
    }
    return name, row


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--problem-file", type=Path, required=True)
    parser.add_argument("--cohort-report", type=Path)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    entries = _dataset_entries(args.dataset.resolve())
    requested = [
        line.strip()
        for line in args.problem_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    missing = sorted(set(requested) - set(entries))
    if missing:
        raise ValueError("problem IDs missing from dataset: " + ", ".join(missing))
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    certified_formulations: dict[str, str] = {}
    certified_artifacts: dict[str, str] = {}
    certified_proof_markdown: dict[str, str] = {}
    certified_trace_sources: dict[str, str] = {}
    if args.cohort_report is not None:
        if args.audit is None:
            raise ValueError("--cohort-report requires --audit")
        cohort = json.loads(args.cohort_report.read_text(encoding="utf-8"))
        audit = json.loads(args.audit.read_text(encoding="utf-8"))
        accepted = {
            str(name)
            for name, row in audit.get("audits", {}).items()
            if isinstance(row, dict)
            and row.get("accepted") is True
            and row.get("trace_integrity") is True
        }
        for run in cohort.get("runs", ()):
            if not isinstance(run, dict) or run.get("solved") is not True:
                continue
            name = str(run["problem"])
            if name not in accepted:
                raise ValueError(
                    f"solved cohort item is not accepted by the replay audit: {name}"
                )
            artifact_value = run.get("artifact")
            if not artifact_value:
                continue
            artifact_path = ROOT / str(artifact_value)
            artifact_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
            constructed = artifact_payload.get("constructed_formulation")
            if not constructed:
                raise ValueError(
                    f"solved artifact has no constructed formulation: {artifact_path}"
                )
            certified_formulations[name] = str(constructed)
            certified_artifacts[name] = artifact_path.relative_to(ROOT).as_posix()
            audit_row = audit["audits"][name]
            trace_value = audit_row.get("proof_trace_markdown")
            if not trace_value:
                raise ValueError(f"accepted solve has no proof trace: {name}")
            trace_path = ROOT / str(trace_value)
            if not trace_path.is_file():
                raise ValueError(f"accepted proof trace is missing: {trace_path}")
            certified_proof_markdown[name] = trace_path.read_text(encoding="utf-8")
            certified_trace_sources[name] = trace_path.relative_to(ROOT).as_posix()
    rows: dict[str, dict[str, Any]] = {}
    with ProcessPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {
            executor.submit(
                _export_one,
                name,
                certified_formulations.get(name, entries[name]),
                (
                    f"certified auxiliary artifact: {certified_artifacts[name]}"
                    if name in certified_artifacts
                    else "frozen JGEX formulation"
                ),
                name in certified_formulations,
                str(output_dir),
                args.seed,
                certified_proof_markdown.get(name),
                certified_trace_sources.get(name),
            ): name
            for name in requested
        }
        for future in as_completed(futures):
            name, row = future.result()
            rows[name] = row
            print(
                json.dumps(
                    {
                        "problem": name,
                        "diagram_generated": row["diagram_generated"],
                        "solver_status": row["status"],
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )

    diagrams = sum(row["diagram_generated"] is True for row in rows.values())
    expected_certified = set(certified_formulations)
    exported_certified = {
        name
        for name, row in rows.items()
        if row.get("certified_proof_text") is True
    }
    missing_certified = sorted(expected_certified - exported_certified)
    manifest = {
        "experiment": "hageo_mortra_solution_artifact_export",
        "protocol": {
            "uses_external_llm": False,
            "source": "same JGEX formulation used by the benchmark",
            "certified_auxiliary_source": (
                args.cohort_report.resolve().relative_to(ROOT).as_posix()
                if args.cohort_report is not None
                else None
            ),
            "certificate_audit": (
                args.audit.resolve().relative_to(ROOT).as_posix()
                if args.audit is not None
                else None
            ),
            "diagram_success_is_not_proof_success": True,
        },
        "summary": {
            "requested": len(requested),
            "artifacts_exported": len(rows),
            "diagrams_generated": diagrams,
            "diagram_failures": len(requested) - diagrams,
            "certified_solutions_expected": len(expected_certified),
            "certified_solutions_exported": len(exported_certified),
            "missing_certified_solution_text": missing_certified,
        },
        "results": dict(sorted(rows.items())),
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest["summary"], ensure_ascii=False), flush=True)
    return 0 if diagrams == len(requested) and not missing_certified else 1


if __name__ == "__main__":
    raise SystemExit(main())
