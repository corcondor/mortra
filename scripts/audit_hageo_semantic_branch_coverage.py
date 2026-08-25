"""Audit source-conditioned semialgebraic branch coverage on frozen HAGeo."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from newclid.jgex.formulation import jgex_formulation_from_txt_file  # noqa: E402

from worker.backend.geometry_semantic_constraints import (  # noqa: E402
    parse_geometry_semantic_context,
)
from worker.backend.jgex_exact_constraint_bridge import (  # noqa: E402
    inspect_jgex_semantic_branch_matches,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    return (
        resolved.relative_to(ROOT).as_posix()
        if resolved.is_relative_to(ROOT)
        else resolved.as_posix()
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--semantic-dataset", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    formulations = jgex_formulation_from_txt_file(args.dataset.resolve())
    semantics = json.loads(args.semantic_dataset.read_text(encoding="utf-8"))
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    certified = set(map(str, baseline["sets"]["primary_union"]))
    unresolved = set(map(str, baseline["sets"]["unresolved_frozen_problems"]))
    frozen = certified | unresolved

    results: dict[str, object] = {}
    for name in sorted(frozen):
        formulation = formulations[name]
        text = str(formulation)
        natural_language = str(semantics.get(name, ""))
        context = parse_geometry_semantic_context(natural_language)
        matches = inspect_jgex_semantic_branch_matches(
            text,
            natural_language=natural_language,
        )
        results[name] = {
            "certified_before_audit": name in certified,
            "half_plane_relations": len(context.half_plane_relations),
            "paired_tangent_candidates": len(matches),
            "source_selected_candidates": sum(
                match.same_side_derivation_rule is not None for match in matches
            ),
            "matches": [
                {
                    "theorem": match.theorem,
                    "source_clause_indices": list(match.source_clause_indices),
                    "points": list(match.points),
                    "same_side_derivation_rule": match.same_side_derivation_rule,
                }
                for match in matches
            ],
        }

    unresolved_results = {
        name: results[name]
        for name in unresolved
    }
    selected = sorted(
        name
        for name, item in results.items()
        if int(item["source_selected_candidates"]) > 0
    )
    unresolved_selected = sorted(set(selected) & unresolved)
    report = {
        "experiment": "hageo_semialgebraic_branch_coverage_audit",
        "uses_external_llm": False,
        "uses_expected_answer": False,
        "uses_problem_identifier_dispatch": False,
        "sources": {
            "dataset": {
                "path": _display_path(args.dataset),
                "sha256": _sha256(args.dataset),
            },
            "semantic_dataset": {
                "path": _display_path(args.semantic_dataset),
                "sha256": _sha256(args.semantic_dataset),
            },
            "baseline": {
                "path": _display_path(args.baseline),
                "sha256": _sha256(args.baseline),
            },
        },
        "summary": {
            "total": len(frozen),
            "certified_before_audit": len(certified),
            "unresolved_before_audit": len(unresolved),
            "problems_with_half_plane_relations": sum(
                int(item["half_plane_relations"]) > 0
                for item in results.values()
            ),
            "problems_with_paired_tangent_candidates": sum(
                int(item["paired_tangent_candidates"]) > 0
                for item in results.values()
            ),
            "problems_with_source_selected_candidates": len(selected),
            "unresolved_with_source_selected_candidates": len(unresolved_selected),
        },
        "sets": {
            "source_selected": selected,
            "unresolved_source_selected": unresolved_selected,
        },
        "unresolved_results": dict(sorted(unresolved_results.items())),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
