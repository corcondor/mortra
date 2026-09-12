"""Run ONE route for ONE task in a fresh process, and print what it cost.

    python scripts/run_route.py --task axis1 --route enumerate --length 8 --repeat 3

One process per invocation, so a route never inherits another route's warm
caches or warm interpreter. `--instrumented` turns on the call counters; without
it nothing is wrapped and the timings are of the unmodified code, which is the
only timing worth comparing. The two are printed separately and are never added
together.

`--route represented` reads the basis and the action matrices out of a ledger
file. Nothing is acquired here: if the ledger has no entry with a certificate
admitting it for this task, the run says so and stops.
"""
from pathlib import Path
import argparse
import json
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from math_os_prototype import fold_observable_system as observables
from math_os_prototype import fold_tasks
from math_os_prototype import representation_benchmarks as benchmarks
from math_os_prototype import representation_evaluation as E
from math_os_prototype import representation_ledger as ledgers
from math_os_prototype import representation_policy as policy

ROUTES = ("enumerate", "concrete", "represented")


def build(route, task, ledger_path):
    if route == "enumerate":
        return lambda length: benchmarks.enumerate_rung(task, length), None
    if route == "concrete":
        return lambda length: benchmarks.concrete_merge_rung(task, length), None
    book = ledgers.Ledger.load(Path(ledger_path))
    entries = book.admissible_for(task.name)
    if not entries:
        raise SystemExit(json.dumps({
            "route": route, "task": task.name, "ran": False,
            "reason": ("no stored representation carries a certificate "
                       "admitting it for this task"),
            "stored_entries": len(book.entries)}, indent=1))
    entry = entries[0]
    certificate = policy.certificate_for(entry, task.name)
    representation = entry["representation"]
    record = {"observable": representation["observable"],
              "basis": representation["basis"],
              "action_matrices": representation["action_matrices"],
              "dimension": representation["dimension"],
              "identity_residuals_all_zero": True,
              "closure_scope": "read from the ledger"}
    closure = observables.closure_from_record(record)
    used = {"from_entry": entry["id"],
            "observable": representation["observable"],
            "dimension": representation["dimension"],
            "certificate_verdict": certificate.get("verdict"),
            "readout": certificate.get("readout"),
            "acquired_in_this_process": False}
    return (lambda length: benchmarks.represented_rung(closure, certificate,
                                                       task, length)), used


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", default="axis1")
    parser.add_argument("--route", choices=ROUTES, required=True)
    parser.add_argument("--length", type=int, required=True)
    parser.add_argument("--repeat", type=int, default=3,
                        help="fixed before the run, not tuned to the result")
    parser.add_argument("--instrumented", action="store_true",
                        help="wrap the primitives and count calls. Off by "
                             "default so timings are of unmodified code")
    parser.add_argument("--ledger", default=None)
    arguments = parser.parse_args(argv)

    task = fold_tasks.task_by_name(arguments.task)
    run, used = build(arguments.route, task, arguments.ledger)

    report = {"task": arguments.task, "task_name": task.name,
              "route": arguments.route, "length": arguments.length,
              "repeat": arguments.repeat,
              "instrumented": arguments.instrumented,
              "representation_used": used, "ran": True,
              "process": "fresh; one route per process"}

    if arguments.instrumented:
        measured = [E.measure(lambda: run(arguments.length)) for _ in
                    range(arguments.repeat)]
        first = measured[0]
        report["answer"] = first["value"]
        report["distribution"] = first["distribution"]
        report["counts"] = {
            "primitive_calls": first["primitive_calls"],
            "fold_step_calls": first["fold_step_calls"],
            "derivative_calls": first["derivative_calls"],
            "derivative_request_calls": first["derivative_request_calls"],
            "search_nodes": first["search_nodes"],
            "transitions": first["transitions"],
            "candidates_generated": first["candidates_generated"],
            "illegal_steps": first["illegal_steps"]}
        report["instrumented_wall_times"] = [m["wall_time"] for m in measured]
        report["note"] = ("these times are of INSTRUMENTED code and are not "
                          "comparable with the bare timings; the counts are "
                          "what this mode is for")
    else:
        times, answer, distribution = [], None, None
        for _ in range(arguments.repeat):
            started = time.perf_counter()
            found = run(arguments.length)
            times.append(round(time.perf_counter() - started, 6))
            answer, distribution = found["value"], found["distribution"]
        report["answer"] = answer
        report["distribution"] = distribution
        report["wall_times"] = times
        report["wall_time_median"] = round(statistics.median(times), 6)
        report["wall_time_min"] = min(times)
        report["wall_time_max"] = max(times)
        if len(times) > 1:
            report["wall_time_stdev"] = round(statistics.stdev(times), 6)
        report["note"] = ("raw values kept. With this few repetitions a small "
                          "difference between routes is not a ranking; the "
                          "spread is reported so that can be judged")
    print(json.dumps(report, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
