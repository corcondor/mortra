"""Time the routes against each other, one fresh process per run.

    python scripts/measure_routes.py --ledger <ledger.json> --task axis1 \
        --length 8 --repeat 5 --output <dir>

Every measurement is a separate `python scripts/run_route.py`, so no route
inherits another's warm caches or warm interpreter. Two passes are made and kept
apart:

    counted   with the primitives wrapped. These are the call counts, and their
              timings are of instrumented code and are not comparable with
              anything.
    timed     with nothing wrapped. These are the only timings worth comparing,
              and the raw values are kept alongside the median so the spread can
              be seen.

The repetition count is fixed on the command line before the run. With a handful
of repetitions a small gap between two routes is not a ranking, and the report
says so rather than ordering them.
"""
from pathlib import Path
import argparse
import json
import statistics
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def one(route, task, length, repeat, *, instrumented, ledger):
    command = [sys.executable, str(HERE / "run_route.py"),
               "--task", task, "--route", route,
               "--length", str(length), "--repeat", str(repeat)]
    if instrumented:
        command.append("--instrumented")
    if ledger:
        command += ["--ledger", str(ledger)]
    finished = subprocess.run(command, capture_output=True, text=True,
                              cwd=str(ROOT))
    if finished.returncode != 0:
        return {"route": route, "ran": False,
                "stderr": finished.stderr.strip()[-400:],
                "stdout": finished.stdout.strip()[-400:]}
    return json.loads(finished.stdout)


def report(rows):
    lines = [f"{'route':<14}{'answer v_max':>13}{'count':>10}"
             f"{'nodes':>10}{'median s':>11}{'min s':>10}{'max s':>10}"]
    lines.append("-" * len(lines[0]))
    for route, pair in rows.items():
        timed, counted = pair["timed"], pair["counted"]
        if not timed.get("ran"):
            lines.append(f"{route:<14}  did not run: {timed.get('reason') or timed.get('stderr')}")
            continue
        answer = timed["answer"]
        nodes = counted.get("counts", {}).get("search_nodes")
        lines.append(f"{route:<14}{str(answer['v_max']):>13}"
                     f"{answer['count_max']:>10}"
                     f"{(nodes if nodes is not None else '-'):>10}"
                     f"{timed['wall_time_median']:>11.4f}"
                     f"{timed['wall_time_min']:>10.4f}"
                     f"{timed['wall_time_max']:>10.4f}")
    lines.append("")
    lines.append("timings are from uninstrumented processes; the node counts "
                 "come from separate instrumented ones.")
    lines.append("raw values are in the JSON. With this many repetitions a small "
                 "gap is not a ranking.")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", default="axis1")
    parser.add_argument("--length", type=int, default=8)
    parser.add_argument("--repeat", type=int, default=5,
                        help="fixed before the run")
    parser.add_argument("--ledger", default=None)
    parser.add_argument("--output", default=None)
    parser.add_argument("--route", action="append", dest="routes", default=None)
    arguments = parser.parse_args(argv)
    routes = arguments.routes or ["enumerate", "concrete", "represented"]

    rows = {}
    for route in routes:
        print(f"measuring {route} ...", flush=True)
        rows[route] = {
            "timed": one(route, arguments.task, arguments.length,
                         arguments.repeat, instrumented=False,
                         ledger=arguments.ledger),
            "counted": one(route, arguments.task, arguments.length, 1,
                           instrumented=True, ledger=arguments.ledger)}

    answers = {route: pair["timed"].get("answer") for route, pair in rows.items()
               if pair["timed"].get("ran")}
    distributions = {route: pair["timed"].get("distribution")
                     for route, pair in rows.items() if pair["timed"].get("ran")}
    agreement = {"answers_all_equal": len(set(map(json.dumps, answers.values()))) <= 1,
                 "distributions_all_equal":
                     len(set(map(json.dumps, distributions.values()))) <= 1,
                 "answers": answers}

    payload = {"task": arguments.task, "length": arguments.length,
               "repeat": arguments.repeat, "rows": rows,
               "agreement": agreement,
               "method": ("one fresh process per route per pass; counts and "
                          "timings taken in separate passes and never added"),
               "reference": ("repeated measurement and keeping the raw values "
                             "follows Kalibera & Jones (2013); no claim of a "
                             "universal speed-up is made from this many "
                             "repetitions")}
    text = report(rows)
    print()
    print(text)
    print()
    print(f"answers all equal: {agreement['answers_all_equal']}   "
          f"distributions all equal: {agreement['distributions_all_equal']}")
    if arguments.output:
        out = Path(arguments.output)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"timings-{arguments.task}-n{arguments.length}.json").write_text(
            json.dumps(payload, indent=1, sort_keys=True), encoding="utf-8")
        (out / f"timings-{arguments.task}-n{arguments.length}.txt").write_text(
            text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
