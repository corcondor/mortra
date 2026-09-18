"""Which stored tasks does more budget not help with?

A task where the search stops with its plans exhausted while its application
budget is still unspent cannot be solved by raising the budget: there is nothing
left to try. Those are the tasks the backward path exists for, and this script
finds them among the tasks earlier runs already posed and stored. It poses
nothing.

    python scripts/find_budget_immune_tasks.py --output reports/budget-immune
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from math_os_prototype import geometry_acquired_library as acqlib
from math_os_prototype import geometry_relational_library as lib
from math_os_prototype import geometry_self_improvement as loop

SOURCES = ("reports/geometry-ladder-hard-v2/ladders.json", "reports/geometry-ladder/ladders.json",
           "reports/geometry-self-improvement/tasks.json", "reports/geometry-self-improvement/probes.json")


def stored_tasks():
    """Every task an earlier run stored, with where it came from."""
    entries, seen = [], set()
    for source in SOURCES:
        path = ROOT/source
        if not path.exists():
            continue
        content = json.loads(path.read_text())
        groups = []
        if "trained" in content:
            for key in ("trained", "held_out"):
                for ladder in content.get(key, []):
                    groups.append((f"{source}:{key}:base", ladder["base"]))
                    groups.append((f"{source}:{key}:top", ladder["top"]))
        else:
            for key, value in content.items():
                if isinstance(value, list):
                    groups.extend((f"{source}:{key}", entry) for entry in value)
        for origin, entry in groups:
            if not isinstance(entry, dict) or "task" not in entry:
                continue
            signature = entry.get("signature", "")
            key = (signature, json.dumps(entry["task"], sort_keys=True))
            if key in seen:
                continue
            seen.add(key)
            entries.append({"origin": origin, "entry": entry})
    return entries


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--large-budget", type=int, default=600)
    parser.add_argument("--backward-applications", type=int, default=300)
    arguments = parser.parse_args()
    output = Path(arguments.output)
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    tasks = stored_tasks()
    print(f"{len(tasks)} stored tasks", flush=True)
    library = acqlib.AcquiredLibrary(lib.acquire_index(max_depth=2, stats=Counter()))
    policy = dict(loop.START_POLICY)
    immune, solved, rows = [], 0, []
    for index, item in enumerate(tasks):
        row = loop.solve(item["entry"]["task"], library=library, policy=policy,
                         applications=arguments.large_budget)
        measurement = loop.measurements(row)
        record = {"origin": item["origin"], "signature": item["entry"].get("signature", "")[:16],
                  "solved": measurement["solved"], "stop_reason": measurement["stop_reason"],
                  "applications": measurement["primitive_applications"],
                  "budget": arguments.large_budget}
        rows.append(record)
        if measurement["solved"]:
            solved += 1
        elif measurement["primitive_applications"] < arguments.large_budget:
            record["budget_immune"] = True
            immune.append(item)
        if (index+1) % 20 == 0:
            print(f"   {index+1}/{len(tasks)} scanned, {len(immune)} immune so far", flush=True)
    print(f"solved {solved}/{len(tasks)} at budget {arguments.large_budget}; "
          f"{len(immune)} unsolved with budget left over", flush=True)

    backward = dict(policy, backward_substitution=True,
                    backward_applications=arguments.backward_applications)
    answered = []
    for item in immune:
        row = loop.solve(item["entry"]["task"], library=library, policy=backward,
                         applications=arguments.large_budget)
        measurement = loop.measurements(row)
        answered.append({"origin": item["origin"], "signature": item["entry"].get("signature", "")[:16],
                         "solved": measurement["solved"], "via": (row.get("solution") or {}).get("via"),
                         "applications": measurement["primitive_applications"],
                         "specification": ((row.get("solution") or {}).get("backward") or {}).get(
                             "specification"),
                         "expression_work": {k: v for k, v in row["costs"].items() if k.startswith("backward")}})
        print(f"   {item['origin']}: backward solved={measurement['solved']} "
              f"via={(row.get('solution') or {}).get('via')}", flush=True)

    report = {"stored_tasks": len(tasks), "solved_at_large_budget": solved,
              "budget_immune": len(immune), "large_budget": arguments.large_budget,
              "backward": {"solved": sum(1 for a in answered if a["solved"]),
                           "through_a_specification": sum(1 for a in answered
                                                          if a["via"] == "backward_substitution")},
              "scan": rows, "immune_under_backward": answered,
              "seconds": time.perf_counter()-started,
              "note": "a task is called budget-immune when the search stops with plans exhausted while "
                      "its application budget is unspent: raising the budget cannot help it"}
    (output/"result.json").write_text(json.dumps(report, indent=1, default=str)+"\n", encoding="utf-8")
    (output/"immune-tasks.json").write_text(json.dumps(immune, indent=1, default=str)+"\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("stored_tasks", "solved_at_large_budget", "budget_immune",
                                             "backward")}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
