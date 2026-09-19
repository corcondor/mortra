"""Does an operation get built out of operations, and then used?

Rounds of the same loop over tasks earlier runs already stored: solve with what
is held, certify what generalises, keep it, and go round again. Nothing is posed
here. What is measured is whether a later acquisition contains an earlier one as
a call — a second generation — and whether such an operation is retrieved for a
task afterwards.

    python scripts/run_generation_stacking.py --output reports/generation-stacking
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from math_os_prototype import geometry_acquired_library as acqlib
from math_os_prototype import geometry_acquisition as acq
from math_os_prototype import geometry_relational_library as lib
from math_os_prototype import geometry_self_improvement as loop
from scripts.find_budget_immune_tasks import stored_tasks


def say(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--tasks", type=int, default=40)
    parser.add_argument("--applications", type=int, default=40)
    arguments = parser.parse_args()
    output = Path(arguments.output)
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    tasks = [item["entry"] for item in stored_tasks()][:arguments.tasks]
    say(f"{len(tasks)} stored tasks, {arguments.rounds} rounds")
    library = acqlib.AcquiredLibrary(lib.acquire_index(max_depth=2, stats=Counter()))
    policy = dict(loop.START_POLICY, backward_substitution=True)
    rounds = []
    for round_index in range(arguments.rounds):
        acquisitions, solved, used_acquired, refusals = [], 0, Counter(), Counter()
        for entry in tasks:
            row = loop.solve(entry["task"], library=library, policy=policy,
                             applications=arguments.applications)
            if not row["solved"]:
                refusals["unsolved"] += 1
                continue
            solved += 1
            for use in acq.used_acquired_operation(row["solution"], library):
                generation = library.acquired[use["index"]]["source"].get("generation", 1)
                used_acquired[f"generation {generation}"] += 1
            result = acq.acquire(row["solution"], entry["task"], definitions=library.definitions)
            if not result["acquired"]:
                refusals[result["reason"][:48]] += 1
                continue
            registration = acq.register(library, result,
                                        source={"round": round_index,
                                                "signature": entry["signature"][:16]})
            if registration.get("registered"):
                acquisitions.append({"index": registration["index"],
                                     "generation": registration["generation"],
                                     "parents": registration["parents"],
                                     "calls": registration["calls"],
                                     "steps": registration["steps"],
                                     "patterns": registration["patterns"],
                                     "body": result["body"]})
            else:
                refusals[registration["reason"][:48]] += 1
        rounds.append({"round": round_index, "solved": solved, "tasks": len(tasks),
                       "acquired": len(acquisitions), "acquisitions": acquisitions,
                       "used_acquired_operations": dict(used_acquired),
                       "refusals": dict(refusals),
                       "library": library.state()})
        say(f"round {round_index}: solved {solved}/{len(tasks)}, acquired {len(acquisitions)}, "
            f"generations {library.state()['generations']}, "
            f"used {dict(used_acquired)}")

    built_on_operations = [item for row in rounds for item in row["acquisitions"] if item["parents"]]
    report = {
        "environment": {"sha": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                              capture_output=True, text=True).stdout.strip()},
        "protocol": {"tasks": "stored by earlier runs; nothing is posed here",
                     "rounds": arguments.rounds,
                     "acquisition": "the solved construction is folded against the operations already "
                                    "held, so a block equal to one of them becomes a call to it; the "
                                    "fold is accepted only when the folded body unfolds to the same "
                                    "primitives"},
        "rounds": rounds,
        "second_generation": [{"index": item["index"], "generation": item["generation"],
                               "parents": item["parents"], "calls": item["calls"],
                               "patterns": item["patterns"]} for item in built_on_operations],
        "generations_present": library.state()["generations"],
        "seconds": time.perf_counter()-started}
    (output/"result.json").write_text(json.dumps(report, indent=1, default=str)+"\n", encoding="utf-8")
    print(json.dumps({"rounds": [{k: row[k] for k in ("round", "solved", "acquired",
                                                      "used_acquired_operations")} for row in rounds],
                      "second_generation": report["second_generation"],
                      "generations_present": report["generations_present"]}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
