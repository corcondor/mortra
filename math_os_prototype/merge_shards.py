"""並列シャードの成果を1つのプールにまとめる（構造商＋族上限）。"""
from __future__ import annotations
import argparse, json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:
    from math_os_prototype.autonomous_loop import PER_FAMILY_CAP, POOL
    from math_os_prototype.difficulty_field import (
        difficulty_band as _difficulty_band,
        difficulty_score as _difficulty_score,
    )
    from math_os_prototype.jukenmath_full_audit import canonical_surface
except ImportError:
    from autonomous_loop import PER_FAMILY_CAP, POOL
    from difficulty_field import (
        difficulty_band as _difficulty_band,
        difficulty_score as _difficulty_score,
    )
    from jukenmath_full_audit import canonical_surface


def _structure_signature(problem: dict) -> tuple[str, tuple[str, ...], tuple[str, ...], str]:
    """数値や表層文ではなく、型付き構造で候補を同一視する。"""
    lift = problem.get("lift_certificate") or {}
    return (
        str(problem.get("family_id") or ""),
        tuple(str(item) for item in lift.get("morphism_chain") or ()),
        tuple(str(item) for item in lift.get("constraint_skeleton") or ()),
        str(lift.get("query_signature") or ""),
    )


def _semantic_payload(payload: dict) -> dict:
    """実行時刻だけの変化を研究成果として扱わない。"""
    return {key: value for key, value in payload.items() if key != "generated_at"}


def _load(path: Path) -> dict:
    if not path.exists():
        return {"problems": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"problems": []}


def merge(paths: list[Path], *, base: Path | None = None) -> dict:
    seen_stmt: set[str] = set()
    seen_structure: set[tuple[str, tuple[str, ...], tuple[str, ...], str]] = set()
    merged: list[dict] = []
    ordered_paths = ([base] if base is not None else []) + paths
    for path in ordered_paths:
        if path is None:
            continue
        payload = _load(path)
        for p in payload.get("problems", []):
            skey = canonical_surface(str(p.get("statement_tex", "")))
            structure_key = _structure_signature(p)
            if (
                structure_key in seen_structure
                or skey in seen_stmt
            ):
                continue
            seen_structure.add(structure_key)
            seen_stmt.add(skey)
            merged.append(p)

    by_family: dict[str, list[dict]] = defaultdict(list)
    for r in sorted(merged, key=lambda r: -_difficulty_score(r)):
        if len(by_family[r["family_id"]]) >= PER_FAMILY_CAP:
            continue
        by_family[r["family_id"]].append(r)
    out: list[dict] = []
    queues = list(by_family.values())
    while any(queues):
        for q in queues:
            if q:
                out.append(q.pop(0))
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": {
            "name": "MathOS autonomous pool (parallel shards merged)",
            "selection_unit": (
                "family_id + morphism_chain + constraint_skeleton + "
                "query_signature"
            ),
            "numeric_variants_count_as_new": False,
        },
        "summary": {
            "total": len(out),
            "shards": len(paths),
            "certified_structures": len({_structure_signature(r) for r in out}),
            "family_counts": dict(Counter(r["family_id"] for r in out)),
            "band_counts": dict(Counter(_difficulty_band(r) for r in out)),
        },
        "problems": out,
    }
    previous = _load(base) if base is not None else {"problems": []}
    if _semantic_payload(report) == _semantic_payload(previous):
        return previous
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", nargs="+", type=Path, required=True)
    ap.add_argument(
        "--base",
        type=Path,
        default=None,
        help="既存プール。先に読み、同一構造を安定して保持する",
    )
    ap.add_argument("--output", type=Path, default=POOL)
    args = ap.parse_args()
    previous = _load(args.base) if args.base is not None else {"problems": []}
    report = merge(list(args.inputs), base=args.base)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    previous_signatures = {
        _structure_signature(problem) for problem in previous.get("problems", [])
    }
    current_signatures = {
        _structure_signature(problem) for problem in report.get("problems", [])
    }
    run_summary = {
        **report["summary"],
        "added_structures_this_run": len(current_signatures - previous_signatures),
        "removed_structures_this_run": len(previous_signatures - current_signatures),
        "semantic_change": _semantic_payload(report) != _semantic_payload(previous),
    }
    print(json.dumps(run_summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
