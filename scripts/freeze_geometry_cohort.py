"""Freeze a source-defined cohort without inspecting solutions or solver results."""
from pathlib import Path
import argparse
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from newclid.jgex.formulation import JGEXFormulation
    from worker.backend.jgex_exact_constraint_bridge import SUPPORTED_CONSTRUCTION_VOCABULARY
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--count", type=int, default=8)
    args = parser.parse_args()
    lines = [s.strip() for s in args.dataset.read_text(encoding="utf-8").splitlines() if s.strip()]
    candidates = []
    for name, text in zip(lines[::2], lines[1::2], strict=True):
        try:
            f = JGEXFormulation.from_text(text)
            f.auxiliary_clauses = ()
            vocab = {c.name for clause in f.setup_clauses for c in clause.constructions}
            if not (3 <= len(f.points) <= 7 and len(f.goals) == 1
                    and vocab <= SUPPORTED_CONSTRUCTION_VOCABULARY):
                continue
            statement = str(f)
            key = hashlib.sha256(("geometry-cohort-917401:"+statement).encode()).hexdigest()
            candidates.append({"id": name, "statement": statement, "selection_key": key})
        except ValueError:
            continue
    tasks = sorted(candidates, key=lambda t: t["selection_key"])[:args.count]
    plan = {"origin": "Newclid pinned dataset, supplied auxiliary clauses removed",
            "unseen_scope": "not used in this adapter's development; global historical exposure unverified",
            "source_file": args.dataset.name,
            "source_sha256": hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
            "selection": "first count by sha256(geometry-cohort-917401:statement), 3..7 initial points; supported syntax only",
            "eligible_count": len(candidates), "tasks": tasks,
            "search": {"seed": 917401, "max_depth": 2, "max_states": 65,
                       "per_family_limit": 8, "closure_steps": 1000},
            "task_timeout_seconds": 180}
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(plan, f, indent=2)
        f.write("\n")
    print(json.dumps({"count": len(tasks), "eligible": len(candidates), "ids": [t["id"] for t in tasks]}))


if __name__ == "__main__":
    main()
