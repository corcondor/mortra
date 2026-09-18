"""What reading the goals backwards changes, and what experience changes on top of it.

    C0  the library and policy learned at 4914838
    C1  the same library and policy, with the backward path switched on
    C2  the same, after learning on the training tasks with it switched on

C0 against C1 separates the search mechanism; C1 against C2 separates what
experience adds. Because C1 grants the backward path an allowance of its own,
C0 is also run at the same total budget and at a much larger one, so that
"solved more" cannot be confused with "given more".

The tasks are the ones already posed and stored by earlier runs. No new task is
posed here, and the development task — the one used while writing the backward
path — is reported separately and never counted as unseen.

    python scripts/run_backward_substitution_eval.py --output reports/backward-substitution
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import platform
import subprocess
import sys
import time
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from math_os_prototype import geometry_acquired_library as acqlib
from math_os_prototype import geometry_acquisition as acq
from math_os_prototype import geometry_relational_library as lib
from math_os_prototype import geometry_self_improvement as loop
from math_os_prototype import geometry_self_posing as posing
from scripts.run_relational_geometry_eval import loaded_project_modules

DEVELOPMENT_SIGNATURE = "a228fad6d5583d8b"


def say(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def write(output, name, value):
    (output/name).write_text(json.dumps(value, indent=1, default=str)+"\n", encoding="utf-8")


def measured(task, *, library, policy, applications):
    """One task under one condition, with time and peak memory."""
    tracemalloc.start()
    began = time.perf_counter()
    row = loop.solve(task, library=library, policy=policy, applications=applications)
    seconds = time.perf_counter()-began
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    measurement = loop.measurements(row)
    measurement["seconds"] = seconds
    measurement["peak_bytes"] = peak
    measurement["expression_work"] = {k: v for k, v in row["costs"].items() if k.startswith("backward")}
    measurement["via"] = (row.get("solution") or {}).get("via")
    return row, measurement


def run_set(entries, *, library, policy, applications, note):
    rows = []
    for entry in entries:
        row, measurement = measured(entry["task"], library=library, policy=policy,
                                    applications=applications)
        used = acq.used_acquired_operation(row["solution"], library) if (row.get("solved") and library) else []
        rows.append({"signature": entry["signature"][:16], "difficulty": entry.get("difficulty"),
                     "measurement": measurement,
                     "solution_point": (row.get("solution") or {}).get("point"),
                     "used_acquired_operations": [u["index"] for u in used],
                     "backward": (row.get("solution") or {}).get("backward")})
    summary = {"note": note, "tasks": len(rows),
               "solved": sum(1 for r in rows if r["measurement"]["solved"]),
               "solved_by_backward_substitution": sum(1 for r in rows
                                                      if r["measurement"]["via"] == "backward_substitution"),
               "applications": sum(r["measurement"]["primitive_applications"] for r in rows),
               "search_states": sum(r["measurement"]["search_states"] for r in rows),
               "condition_checks": sum(r["measurement"]["checking"] for r in rows),
               "expression_terms": sum(r["measurement"]["expression_work"].get("backward_expression_terms", 0)
                                       for r in rows),
               "specifications_built": sum(r["measurement"]["expression_work"].get(
                   "backward_specifications_built", 0) for r in rows),
               "seconds": sum(r["measurement"]["seconds"] for r in rows),
               "peak_bytes": max((r["measurement"]["peak_bytes"] for r in rows), default=0),
               "solved_using_an_acquired_operation": sum(1 for r in rows if r["used_acquired_operations"])}
    return {"rows": rows, "summary": summary}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--ladders", default="reports/geometry-ladder-hard-v2")
    parser.add_argument("--extra-tasks", default="reports/geometry-ladder")
    parser.add_argument("--tasks-from", default=None,
                        help="evaluate on the tasks stored by an earlier scan instead of every stored top")
    parser.add_argument("--applications", type=int, default=40)
    parser.add_argument("--backward-applications", type=int, default=300)
    arguments = parser.parse_args()
    output = Path(arguments.output)
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    report = {"environment": {
        "sha": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip(),
        "python": sys.version, "platform": platform.platform(),
        "modules_before": loaded_project_modules()},
        "protocol": {
            "C0": "the library and policy learned at 4914838",
            "C1": "the same, with the backward path switched on; library and policy fixed",
            "C2": "the same, after learning on the training tasks with the backward path on",
            "fairness": "C0 is also run at C1's total budget and at a much larger one",
            "development_task": "used while writing the backward path; reported apart, never counted "
                                "as unseen",
            "tasks": "posed by earlier runs and stored; nothing is posed here"}}

    say("rebuilding the state of 4914838")
    base_index = lib.acquire_index(max_depth=2, stats=Counter())
    ladders = json.loads((ROOT/arguments.ladders/"ladders.json").read_text())
    train_entries = [ladder["base"] for ladder in ladders["trained"]]
    evaluation = [ladder["top"] for ladder in ladders["trained"]+ladders["held_out"]]
    development = [e for e in evaluation if e["signature"].startswith(DEVELOPMENT_SIGNATURE)]
    unseen = [e for e in evaluation if not e["signature"].startswith(DEVELOPMENT_SIGNATURE)]
    if arguments.tasks_from:
        selected = json.loads((ROOT/arguments.tasks_from).read_text())
        entries = [item["entry"] if "entry" in item else item for item in selected]
        development = [e for e in entries if e["signature"].startswith(DEVELOPMENT_SIGNATURE)]
        unseen = [e for e in entries if not e["signature"].startswith(DEVELOPMENT_SIGNATURE)]
        report["protocol"]["evaluation_set"] = (
            f"the tasks in {arguments.tasks_from}: stored tasks that a large budget does not solve, "
            f"because the search runs out of plans rather than budget")
    else:
        extra = ROOT/arguments.extra_tasks/"ladders.json"
        if extra.exists():
            other = json.loads(extra.read_text())
            unseen += [ladder["top"] for ladder in other["trained"]+other["held_out"]]
    say(f"training {len(train_entries)}, unseen {len(unseen)}, development {len(development)}")

    learned = acqlib.AcquiredLibrary(base_index)
    stage = loop.learn_stage(train_entries, library=learned, policy=dict(loop.START_POLICY),
                             applications=arguments.applications)
    candidates = loop.propose_policies(stage["rows"], dict(loop.START_POLICY))[:3]
    chosen = loop.choose_policy(candidates, train_entries[:2], library=learned,
                                applications=arguments.applications, current=dict(loop.START_POLICY))
    c0_policy = chosen["policy"]
    report["c0_state"] = {"acquired": len(stage["acquisitions"]), "solved_in_training": stage["solved"],
                          "policy": chosen["chosen"], "library": learned.state()}
    say(f"C0 library: {learned.state()['acquired']} acquired, policy: {chosen['chosen']}")

    backward_policy = dict(c0_policy, backward_substitution=True,
                           backward_applications=arguments.backward_applications)

    # -- the development task, shown in full --------------------------------
    say("the development task")
    development_record = {}
    if development:
        entry = development[0]
        development_record["statement"] = posing.render(entry["task"], language="english")
        development_record["statement_japanese"] = posing.render(entry["task"])
        development_record["generator_construction"] = entry["hidden"]["steps"]
        development_record["generator_answer"] = entry["hidden"]["solution"]
        for label, policy, applications in (("C0", c0_policy, arguments.applications),
                                            ("C0 same total budget", c0_policy,
                                             arguments.applications+arguments.backward_applications),
                                            ("C0 large budget", c0_policy, 1000),
                                            ("C1", backward_policy, arguments.applications)):
            row, measurement = measured(entry["task"], library=learned, policy=policy,
                                        applications=applications)
            development_record[label] = {"measurement": measurement,
                                         "solution": {k: v for k, v in (row.get("solution") or {}).items()
                                                      if k in ("point", "via", "backward", "goals", "replay")}}
            say(f"   {label}: solved={row['solved']} stop={row['stop_reason']} "
                f"applications={measurement['primitive_applications']}")
            if row["solved"] and label == "C1":
                acquisition = acq.acquire(row["solution"], entry["task"])
                development_record["acquisition"] = {
                    k: v for k, v in acquisition.items() if k in ("acquired", "reason", "body",
                                                                  "declared", "instance_only")}
                if acquisition["acquired"]:
                    registration = acq.register(learned, acquisition,
                                                source={"from": "development task via backward substitution"})
                    development_record["registration"] = registration
                    say(f"   acquired from the development solution: {registration}")
    report["development"] = development_record

    # -- the three conditions on the unseen tasks ---------------------------
    say("C0 on the unseen tasks")
    c0 = run_set(unseen, library=learned, policy=c0_policy, applications=arguments.applications,
                 note="C0: learned library and policy")
    say(f"   solved {c0['summary']['solved']}/{len(unseen)}")
    say("C0 at the same total budget")
    c0_same = run_set(unseen, library=learned, policy=c0_policy,
                      applications=arguments.applications+arguments.backward_applications,
                      note="C0 at C1's total budget")
    say(f"   solved {c0_same['summary']['solved']}/{len(unseen)}")
    say("C1 on the unseen tasks")
    c1 = run_set(unseen, library=learned, policy=backward_policy, applications=arguments.applications,
                 note="C1: backward substitution, library and policy fixed")
    say(f"   solved {c1['summary']['solved']}/{len(unseen)}, "
        f"{c1['summary']['solved_by_backward_substitution']} of them through a specification")

    # -- C2: learn with the backward path on --------------------------------
    say("learning again with the backward path on")
    learned_two = acqlib.AcquiredLibrary(base_index)
    stage_two = loop.learn_stage(train_entries, library=learned_two, policy=backward_policy,
                                 applications=arguments.applications)
    candidates_two = loop.propose_policies(stage_two["rows"], backward_policy)[:3]
    chosen_two = loop.choose_policy(candidates_two, train_entries[:2], library=learned_two,
                                    applications=arguments.applications, current=backward_policy)
    c2_policy = dict(chosen_two["policy"], backward_substitution=True,
                     backward_applications=arguments.backward_applications)
    report["c2_state"] = {"acquired": len(stage_two["acquisitions"]), "solved_in_training": stage_two["solved"],
                          "policy": chosen_two["chosen"], "library": learned_two.state(),
                          "failures": stage_two["failures"]}
    say(f"C2 library: {learned_two.state()['acquired']} acquired, policy: {chosen_two['chosen']}")
    c2 = run_set(unseen, library=learned_two, policy=c2_policy, applications=arguments.applications,
                 note="C2: learned with the backward path on")
    say(f"   solved {c2['summary']['solved']}/{len(unseen)}")

    report["results"] = {"C0": c0["summary"], "C0_same_budget": c0_same["summary"],
                         "C1": c1["summary"], "C2": c2["summary"]}
    write(output, "rows.json", {"C0": c0["rows"], "C0_same_budget": c0_same["rows"],
                                "C1": c1["rows"], "C2": c2["rows"]})
    write(output, "learning.json", {"C0_stage": stage, "C2_stage": stage_two,
                                    "C0_policy_choice": chosen, "C2_policy_choice": chosen_two})
    modules_after = loaded_project_modules()
    report["environment"]["sources_unchanged"] = all(
        modules_after.get(key) == value for key, value in report["environment"]["modules_before"].items())
    report["total_seconds"] = time.perf_counter()-started
    report["claims_not_made"] = [
        "the backward path is a general substitution of a primitive's own output function into the goal "
        "polynomials; no formula is written for any task",
        "a point is decided against a specification by exact substitution; no polynomial system is solved",
        "reaching a degree or size bound is recorded as an incomplete search, never as an impossible goal",
        "C1 grants an allowance of its own, so C0 is reported at the same total budget and at a much "
        "larger one",
        "the development task is excluded from the unseen set",
        "no preregistered evaluation is affected"]
    write(output, "result.json", report)
    print(json.dumps({"results": report["results"], "c0_state": {k: report["c0_state"][k] for k in
                                                                ("acquired", "policy")},
                      "c2_state": {k: report["c2_state"][k] for k in ("acquired", "policy")},
                      "development": {k: v for k, v in report["development"].items()
                                      if k in ("statement", "acquisition", "registration")}},
                     indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
