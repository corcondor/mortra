"""Preregistered comparison of the relational geometry DSL with the existing point-construction search.

See docs/research/GEOMETRY-RELATIONAL-DSL-20260917.md, section 8. One process
runs every condition on every task; condition order follows a Williams Latin
square over the task index. Shared state (the producer index certification
cache, SymPy caches) is recorded, and timings are reported as warm-cache.

The fresh cohort seed is derived inside the run from a public drand beacon round
fixed in the configuration before that round was published. A binding run needs
a clean source tree.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import sympy as sp

from math_os_prototype import geometry_relational_cohort as cohort
from math_os_prototype import geometry_relational_dsl as rdsl
from math_os_prototype import geometry_relational_library as lib
from math_os_prototype.geometry_relational_search import RelationalSynthesis, independent_replay
from math_os_prototype.representation_progress import digest
from math_os_prototype.theory_geometry_feedback import GeometryLibrary
from math_os_prototype.theory_geometry_selection import SelectionDomain, read_inputs

RELATIONAL = {"N0": {"transfer": False, "library": False, "fallback": False},
              "N": {"transfer": True, "library": False, "fallback": False},
              "NL": {"transfer": True, "library": True, "fallback": False},
              "NLF": {"transfer": True, "library": True, "fallback": True}}


def goal_text(task):
    return " & ".join(g["predicate"]+"("+",".join(g["points"])+")" for g in task["goals"])


def audit_solution(task, solution):
    """Independent check shared by every condition: primitive re-execution and exact goal atoms."""
    if solution is None:
        return None
    inputs = {n: tuple(sp.Rational(v) for v in xy) for n, xy in task["points"].items()}
    try:
        xy, _ = independent_replay(solution["term"], inputs)
    except (ValueError, KeyError) as exc:
        return {"passed": False, "reason": "replay: "+str(exc)}
    xy = tuple(sp.cancel(v) for v in xy)
    if xy in set(inputs.values()):
        return {"passed": False, "reason": "input point"}
    local = dict(inputs, u=xy)
    ok = all(rdsl.atom_holds(g["predicate"], tuple(g["points"]), local) for g in task["goals"])
    return {"passed": ok, "point": [str(v) for v in xy], "reason": None if ok else "goal atom fails"}


def one_sided_binomial(wins, losses):
    n = wins+losses
    if n == 0:
        return 1.0
    return sum(math.comb(n, k) for k in range(wins, n+1))/2**n


def williams_order(conditions, index):
    """Row `index` of a Williams Latin square (balanced for first-order carry-over when n is even)."""
    n = len(conditions)
    first, low, high = [0], 1, n-1
    while len(first) < n:
        first.append(low)
        low += 1
        if len(first) < n:
            first.append(high)
            high -= 1
    row = [(value+index) % n for value in first]
    if n % 2 and (index // n) % 2:
        row = row[::-1]
    return [conditions[k] for k in row]


def fetch_beacon(source):
    """Fetch a drand round from independent endpoints, check chain, round and randomness = sha256(signature)."""
    records = []
    for endpoint in source["endpoints"]:
        url = f"{endpoint}/{source['chain_hash']}/public/{source['round']}"
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                record = json.loads(response.read())
        except OSError as exc:
            records.append({"endpoint": endpoint, "error": str(exc)})
            continue
        records.append({"endpoint": endpoint, "record": record})
    fetched = [r["record"] for r in records if "record" in r]
    if not fetched:
        raise SystemExit("beacon round not available: "+json.dumps(records))
    first = fetched[0]
    if any(r.get("randomness") != first.get("randomness") or r.get("round") != source["round"] for r in fetched):
        raise SystemExit("beacon endpoints disagree")
    if sha256(bytes.fromhex(first["signature"])).hexdigest() != first["randomness"]:
        raise SystemExit("beacon randomness is not sha256(signature)")
    seed = int(sha256((source["salt"]+":"+first["randomness"]).encode()).hexdigest()[:8], 16)
    return seed, records


def loaded_project_modules():
    digests = {}
    for module in list(sys.modules.values()):
        path = getattr(module, "__file__", None)
        if not path:
            continue
        path = Path(path).resolve()
        if ROOT in path.parents and path.suffix == ".py":
            digests[str(path.relative_to(ROOT)).replace("\\", "/")] = sha256(path.read_bytes()).hexdigest()
    return dict(sorted(digests.items()))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--non-binding", action="store_true",
                        help="development run: allows a dirty tree and a literal seed; never a result")
    args = parser.parse_args()
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("PYTHONHASHSEED=0 is required")
    started = time.perf_counter()
    config = json.loads((ROOT/args.config).read_text())
    protocol = config["protocol"]
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    def write(name, value):
        (output/name).write_text(json.dumps(value, indent=1)+"\n", encoding="utf-8")

    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT,
                           capture_output=True, text=True).stdout.strip()
    if dirty and not args.non_binding:
        raise SystemExit("binding run requires a clean tree:\n"+dirty)
    modules_before = loaded_project_modules()
    environment = {"sha": sha, "dirty": dirty, "binding": not args.non_binding, "python": sys.version,
                   "platform": platform.platform(), "sympy": sp.__version__, "config": config,
                   "modules": modules_before, "workflow_run_id": os.environ.get("GITHUB_RUN_ID")}

    cohorts, beacon = {}, None
    if "regression" in protocol["cohorts"]:
        _, plan, _ = read_inputs(config["regression_source"], ROOT)
        cohorts["regression"] = [{"points": t["points"], "goals": t["goals"]} for t in plan["evaluation"]]
    if "fresh" in protocol["cohorts"]:
        if args.non_binding and isinstance(protocol.get("development_fresh_seed"), int):
            seed = protocol["development_fresh_seed"]
        else:
            seed, beacon = fetch_beacon(protocol["fresh_seed_source"])
        if seed in protocol["development_seeds"] and not args.non_binding:
            raise SystemExit("fresh seed collides with a development seed")
        environment.update(fresh_seed=seed, beacon=beacon)
        cohorts["fresh"] = None          # generated when its turn comes, after the regression cohort
    write("environment.json", environment)

    deadline = started+protocol["max_total_seconds"]
    acquisition_started = time.perf_counter()
    index = lib.acquire_index(max_depth=protocol["library_max_depth"])
    library_record = {"digest": index.digest(), "costs_after_acquisition": dict(index.costs),
                      "seconds": time.perf_counter()-acquisition_started, "programs": len(index.programs),
                      "patterns": len(index.membership), "spec": lib.SPEC, "reads_tasks": False}
    write("library.json", library_record)

    bank = GeometryLibrary()
    search = config["existing_search"]
    budget = protocol["applications"]
    wall = config["relational_search"]["wall_seconds"]

    def existing(task, guided, applications, wall_seconds):
        domain = SelectionDomain(task, dict(search, wall_seconds=wall_seconds), bank, guided=guided,
                                 original_order_every=4, active=())
        row = domain.search(applications)
        return row, row["costs"].get("candidate_expansions", 0)

    def fallback(task, remaining, wall_remaining):
        row, used = existing(task, config["relational_search"]["fallback"] == "B", remaining, wall_remaining)
        return {"solved": row["solved"], "solution": row["solution"], "stop_reason": row["stop_reason"],
                "applications": used, "costs": row["costs"]}

    def run(task, condition, applications):
        begin = time.perf_counter()
        if condition in {"A", "B"}:
            row, used = existing(task, condition == "B", applications, wall)
        else:
            flags = RELATIONAL[condition]
            synthesis = RelationalSynthesis(task, config["relational_search"], transfer=flags["transfer"],
                                            library=index if flags["library"] else None,
                                            fallback=fallback if flags["fallback"] else None)
            row = synthesis.search(applications)
            used = row["costs"].get("applications", 0)
        solution = row["solution"] if row["solved"] else None
        audit = audit_solution(task, solution)
        seconds = time.perf_counter()-begin
        return {"goal": goal_text(task), "claimed": bool(row["solved"]),
                "solved": bool(row["solved"]) and bool(audit and audit["passed"]) and seconds <= wall*1.05,
                "audit": audit, "applications": used, "seconds": seconds, "stop_reason": row["stop_reason"],
                "term": solution["term"] if solution else None, "via": (solution or {}).get("via"),
                "costs": {k: v for k, v in row["costs"].items() if isinstance(v, (int, float))}}

    results, unrun = {}, []
    order = ["regression", "fresh"]
    for name in [c for c in order if c in cohorts]:
        if name not in protocol["cohorts"]:
            continue
        tasks = cohorts[name]
        if name == "fresh":
            generation_started = time.perf_counter()
            generated = cohort.generate(environment["fresh_seed"], protocol["fresh_count"])
            generated["seconds"] = time.perf_counter()-generation_started
            tasks = [{"points": t["points"], "goals": t["goals"]} for t in generated["tasks"]]
            exposed = {digest(t) for t in cohorts.get("regression", [])}
            for development_seed in protocol["development_seeds"]:
                count = protocol["development_counts"][str(development_seed)]
                exposed |= {digest({"points": t["points"], "goals": t["goals"]})
                            for t in cohort.generate(development_seed, count)["tasks"]}
            overlap = [i for i, t in enumerate(tasks) if digest(t) in exposed]
            generated["overlap_with_exposed_tasks"] = overlap
            write("fresh-cohort.json", generated)
            if overlap and not args.non_binding:
                raise SystemExit("fresh cohort overlaps exposed tasks: "+json.dumps(overlap))
            cohorts[name] = tasks
        write(f"{name}-tasks.json", {"hashes": [digest(t) for t in tasks], "tasks": tasks})
        rows = {c: [] for c in protocol["conditions"]}
        for i, task in enumerate(tasks):
            if time.perf_counter() > deadline:
                unrun.append({"cohort": name, "index": i})
                continue
            for condition in williams_order(protocol["conditions"], i):
                rows[condition].append(dict(run(task, condition, budget), index=i))
            print(json.dumps({"cohort": name, "index": i, "goal": goal_text(task),
                              **{c: rows[c][-1]["solved"] for c in protocol["conditions"]}}), flush=True)
            write(f"{name}-rows.json", rows)
        results[name] = rows

    robustness = []
    spec = protocol["robustness"]
    if "fresh" in results:
        primary, baseline = protocol["primary"], protocol["baseline"]
        for p, b in zip(results["fresh"][primary], results["fresh"][baseline]):
            if p["solved"] and not b["solved"] and time.perf_counter() <= deadline:
                task = cohorts["fresh"][p["index"]]
                row = run(task, baseline, spec["baseline_applications"])
                robustness.append(dict(row, index=p["index"], applications_budget=spec["baseline_applications"]))
        write("robustness.json", robustness)

    summary = {}
    for name, rows in results.items():
        primary, baseline = protocol["primary"], protocol["baseline"]
        paired = [(p, b) for p, b in zip(rows[primary], rows[baseline]) if p["index"] == b["index"]]
        wins = sum(1 for p, b in paired if p["solved"] and not b["solved"])
        losses = sum(1 for p, b in paired if b["solved"] and not p["solved"])
        summary[name] = {
            "tasks": len(cohorts[name]), "completed": len(rows[primary]),
            "solved_audited": {c: sum(r["solved"] for r in rows[c]) for c in rows},
            "claimed": {c: sum(r["claimed"] for r in rows[c]) for c in rows},
            "false_solutions": {c: sum(1 for r in rows[c] if r["claimed"] and not (r["audit"] or {}).get("passed"))
                                for c in rows},
            "via_fallback": {c: sum(1 for r in rows[c] if r["solved"] and r["via"] == "fallback") for c in rows},
            "primary": primary, "baseline": baseline, "discordant_wins": wins, "discordant_losses": losses,
            "one_sided_binomial_p": one_sided_binomial(wins, losses),
            "applications": {c: sum(r["applications"] for r in rows[c]) for c in rows},
            "seconds_warm_cache": {c: sum(r["seconds"] for r in rows[c]) for c in rows},
            "exact_checks": {c: sum(r["costs"].get(k, 0) for r in rows[c] for k in
                                    ("predicate_prover_calls", "polynomial_checks", "fallback_predicate_prover_calls"))
                             for c in rows},
            "library_exact_certifications": {c: sum(r["costs"].get("library_exact_certifications", 0) for r in rows[c])
                                             for c in rows}}
    if robustness:
        summary["robustness"] = {"baseline_applications": spec["baseline_applications"], "tasks": len(robustness),
                                 "baseline_solved": sum(r["solved"] for r in robustness)}

    modules_after = loaded_project_modules()
    unchanged = all(modules_after.get(k) == v for k, v in modules_before.items())
    fresh, regression = summary.get("fresh"), results.get("regression")
    criterion = {"complete": not unrun and "fresh" in summary and regression is not None,
                 "binding": not args.non_binding, "sources_unchanged": unchanged}
    if fresh:
        primary, baseline = protocol["primary"], protocol["baseline"]
        losses_regression = None if regression is None else [
            p["index"] for p, b in zip(regression[primary], regression[baseline]) if b["solved"] and not p["solved"]]
        criterion.update({
            "more_solved": fresh["solved_audited"][primary] > fresh["solved_audited"][baseline],
            "p_below_0_05": fresh["one_sided_binomial_p"] < 0.05,
            "zero_false_solutions": all(v == 0 for s in summary.values() if "false_solutions" in s
                                        for v in s["false_solutions"].values()),
            "no_regression_losses": None if losses_regression is None else not losses_regression,
            "regression_losses": losses_regression})
    criterion["improvement"] = bool(fresh) and all(criterion.get(k) is True for k in (
        "complete", "binding", "sources_unchanged", "more_solved", "p_below_0_05",
        "zero_false_solutions", "no_regression_losses"))
    report = {"summary": summary, "criterion": criterion, "unrun": unrun, "sha": sha,
              "library": dict(library_record, costs_after_runs=dict(index.costs)),
              "modules_after": modules_after, "total_seconds": time.perf_counter()-started,
              "claims_not_made": [
                  "instance-level constructions are not universal theorems",
                  "metarules, the producer enumeration grammar and the fallback are supplied search machinery",
                  "a charged application in N counts one distinct execution per task; in A and B one attempt per state",
                  "the solve comparison does not exercise the edit or abstraction operations (R2/R3); "
                  "those are covered only by the structural tests",
                  "a budget stop is not impossibility"]}
    write("result.json", report)
    print(json.dumps({k: v for k, v in report.items() if k not in {"library", "modules_after"}}, indent=1))
    return 0 if unchanged else 1


if __name__ == "__main__":
    raise SystemExit(main())
