"""Does what was learned change what gets posed, and does that produce operations built on operations?

The loop so far went one way: tasks were posed from the seven primitives, solved,
and what generalised was kept. Nothing the system learned ever reached the part
that poses, so every task stayed inside primitive depth and every acquisition was
a flat list of primitives. Three rounds measured here:

    round 0   acquire from the tasks earlier runs stored
    round 1   pose new tasks whose constructions use the acquired operations,
              solve them, and acquire from those solutions
    round 2   pose again with everything held by then

What is looked for is an acquisition whose body contains a call to an earlier
acquisition — an operation built out of an operation — and whether such an
operation is then used again.

A compression pass is reported separately: an operation already held may turn out
to factor through another one acquired later, which is a fact about the library
rather than a new capability, and is counted apart.

    python scripts/run_experience_posing.py --output reports/experience-posing
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
from math_os_prototype import geometry_relational_edit as edit
from math_os_prototype import geometry_relational_library as lib
from math_os_prototype import geometry_self_improvement as loop
from math_os_prototype import geometry_self_posing as posing
from scripts.find_budget_immune_tasks import stored_tasks


def say(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def acquired_operations(library):
    """The acquired entries as the poser needs them: an index and a runnable program."""
    return [{"index": index, "program": library.programs[index]}
            for index in sorted(library.acquired)]


def learn_from(entries, *, library, policy, applications, note):
    """Solve, acquire, register — the existing gate, unchanged."""
    acquisitions, refusals, solved, used = [], Counter(), 0, Counter()
    for entry in entries:
        row = loop.solve(entry["task"], library=library, policy=policy, applications=applications)
        if not row["solved"]:
            refusals["unsolved"] += 1
            continue
        solved += 1
        for use in acq.used_acquired_operation(row["solution"], library):
            generation = library.acquired[use["index"]]["source"].get("generation", 1)
            used[f"generation {generation}"] += 1
        result = acq.acquire(row["solution"], entry["task"], definitions=library.definitions)
        if not result["acquired"]:
            refusals[result["reason"][:56]] += 1
            continue
        registration = acq.register(library, result, source={"note": note,
                                                             "signature": entry["signature"][:16]})
        if not registration.get("registered"):
            refusals[registration["reason"][:56]] += 1
            continue
        acquisitions.append({"index": registration["index"], "generation": registration["generation"],
                             "parents": registration["parents"], "calls": registration["calls"],
                             "steps": registration["steps"], "patterns": registration["patterns"],
                             "body": result["body"],
                             "posed_with": entry.get("hidden", {}).get("acquired_operations_used", [])})
    return {"solved": solved, "tasks": len(entries), "acquisitions": acquisitions,
            "used_acquired_operations": dict(used), "refusals": dict(refusals)}


def compress(library):
    """Which operations already held factor through another one held.

    Nothing new is learned here: it is a statement about the library, reported
    apart from what the rounds acquired.
    """
    factored = []
    definitions = dict(library.definitions)
    for identifier, definition in definitions.items():
        others = {k: v for k, v in definitions.items() if k != identifier}
        body, parents, _ = acq.fold_known_operations(definition["body"], others)
        if parents:
            factored.append({"definition": identifier[:12], "factors_through": [p[:12] for p in parents],
                             "steps_before": len(definition["body"]["steps"]),
                             "steps_after": len(body["steps"])})
    return factored


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed-tasks", type=int, default=30)
    parser.add_argument("--posed", type=int, default=8)
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--applications", type=int, default=40)
    parser.add_argument("--depth", type=int, default=2)
    parser.add_argument("--seed", type=int, default=20261019)
    arguments = parser.parse_args()
    output = Path(arguments.output)
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    library = acqlib.AcquiredLibrary(lib.acquire_index(max_depth=2, stats=Counter()))
    policy = dict(loop.START_POLICY, backward_substitution=True)
    report = {"environment": {"sha": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                                    capture_output=True, text=True).stdout.strip()},
              "protocol": {
                  "round 0": "acquire from the tasks earlier runs stored",
                  "later rounds": "pose tasks whose constructions use the acquired operations, "
                                  "solve them, acquire from those solutions",
                  "looked for": "an acquisition whose body calls an earlier acquisition",
                  "compression": "reported apart: an operation that factors through another is a fact "
                                 "about the library, not a new capability"},
              "rounds": []}

    seed_entries = [item["entry"] for item in stored_tasks()][:arguments.seed_tasks]
    say(f"round 0: learning from {len(seed_entries)} stored tasks")
    round_zero = learn_from(seed_entries, library=library, policy=policy,
                            applications=arguments.applications, note="round 0, stored tasks")
    round_zero["round"] = 0
    round_zero["posed"] = 0
    round_zero["library"] = library.state()
    report["rounds"].append(round_zero)
    say(f"   solved {round_zero['solved']}/{len(seed_entries)}, acquired {len(round_zero['acquisitions'])}, "
        f"generations {library.state()['generations']}")

    for index in range(1, arguments.rounds+1):
        operations = acquired_operations(library)
        if not operations:
            say(f"round {index}: nothing acquired to pose with")
            break
        say(f"round {index}: posing with {len(operations)} acquired operations")
        began = time.perf_counter()
        batch = posing.pose_batch_from_experience(arguments.seed+index, arguments.posed, operations,
                                                  depth=arguments.depth, attempts=2500)
        say(f"   posed {len(batch['tasks'])} in {time.perf_counter()-began:.0f}s; "
            f"rejections {json.dumps(batch['rejections'])[:160]}")
        for entry in batch["tasks"]:
            verdict = loop.screen(entry["task"], library=library, policy=policy)
            entry["difficulty"] = verdict["class"]
        record = learn_from(batch["tasks"], library=library, policy=policy,
                            applications=arguments.applications, note=f"round {index}, posed from experience")
        record["round"] = index
        record["posed"] = len(batch["tasks"])
        record["difficulty"] = dict(Counter(e["difficulty"] for e in batch["tasks"]))
        record["posing_rejections"] = batch["rejections"]
        record["tasks"] = [{"signature": e["signature"][:16], "difficulty": e["difficulty"],
                            "statement": posing.render(e["task"], language="english"),
                            "statement_japanese": posing.render(e["task"]),
                            "hidden": e["hidden"]} for e in batch["tasks"]]
        record["library"] = library.state()
        report["rounds"].append(record)
        say(f"   solved {record['solved']}/{record['posed']}, acquired {len(record['acquisitions'])}, "
            f"generations {library.state()['generations']}, used {record['used_acquired_operations']}")

    built_on = [item for row in report["rounds"] for item in row["acquisitions"] if item["parents"]]
    report["operations_built_on_operations"] = built_on
    report["generations_present"] = library.state()["generations"]
    report["compression"] = compress(library)
    report["seconds"] = time.perf_counter()-started
    (output/"result.json").write_text(json.dumps(report, indent=1, default=str)+"\n", encoding="utf-8")
    print(json.dumps({"rounds": [{k: row.get(k) for k in ("round", "posed", "solved", "difficulty",
                                                          "used_acquired_operations")}
                                 for row in report["rounds"]],
                      "acquired_per_round": [len(row["acquisitions"]) for row in report["rounds"]],
                      "operations_built_on_operations": built_on,
                      "generations_present": report["generations_present"],
                      "compression": report["compression"]}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
