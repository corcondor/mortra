"""Preregistered tests of structure-preserving reductions on fresh chain complexes.

See docs/research/ALGEBRAIC-STRUCTURES-20260917.md, section 5. Inside one run:
  1. training and fresh seeds are derived from a drand round fixed before publication;
  2. primary: Betti numbers with representatives, computed directly and after
     certified collapses, at the declared operation count;
  3. secondary: certified minimal models by the default ordering, by an ordering rule
     learned from the system's own reductions of training complexes, by exploration,
     and by every fixed ordering;
  4. every answer is audited independently with python-flint.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import random
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from math_os_prototype import algebraic_cohort as ac
from math_os_prototype import algebraic_minimal_models as amm
from math_os_prototype import algebraic_reduction_search as ars
from math_os_prototype import algebraic_structures as alg
from scripts.run_relational_geometry_eval import fetch_beacon, loaded_project_modules


def flint_rank(columns, nrows):
    from flint import fmpq, fmpq_mat
    if not columns or nrows == 0:
        return 0
    matrix = fmpq_mat(nrows, len(columns))
    for j, column in enumerate(columns):
        for i, value in column.items():
            value = Fraction(value)
            matrix[i, j] = fmpq(value.numerator, value.denominator)
    return matrix.rank()


def audit(simplices, K, truth, record, minimal_model=True):
    """Independent answer check with python-flint: Betti numbers, zero differential (minimal models),
    representative count, degree labels, cycles, and independence modulo boundaries."""
    if not record.get("solved"):
        return {"passed": False, "reason": record.get("failure", "unsolved")}
    if record["betti"] != truth:
        return {"passed": False, "reason": f"betti {record['betti']} != reference {truth}"}
    if minimal_model and record.get("remaining_differential_entries") != 0:
        return {"passed": False, "reason": "minimal model differential is not zero"}
    for q, expected in enumerate(truth):
        reps = record["representatives"].get(q, [])
        if len(reps) != expected:
            return {"passed": False, "reason": f"degree {q}: {len(reps)} representatives for Betti {expected}"}
        if any(d != q for r in reps for (d, _) in r):
            return {"passed": False, "reason": f"degree {q}: representative uses a cell of another degree"}
        vectors = [{i: v for (_, i), v in r.items()} for r in reps]
        if any(K.d(q).apply(v) for v in vectors):
            return {"passed": False, "reason": f"degree {q} representative is not a cycle"}
        boundaries = K.d(q+1).columns if q+1 < len(K.dims) else []
        base = flint_rank(boundaries, K.dims[q])
        if flint_rank(list(boundaries)+vectors, K.dims[q]) != base+len(vectors):
            return {"passed": False, "reason": f"degree {q} representatives dependent modulo boundaries"}
    return {"passed": True}


def task_key(task):
    return sha256(json.dumps([sorted(map(tuple, task["points"])), task["r2"]]).encode()).hexdigest()


def binding_checks(protocol, config_path):
    """A binding run is a CI run of tracked, unchanged code with a published round fixed after the config commit."""
    problems = []
    if not os.environ.get("GITHUB_RUN_ID"):
        problems.append("not a GitHub Actions run")
    round_ = protocol["fresh_seed_source"].get("round")
    if not isinstance(round_, int):
        problems.append("round is not an integer")
    else:
        committed = subprocess.run(["git", "log", "-1", "--format=%ct", "--", config_path], cwd=ROOT,
                                   capture_output=True, text=True).stdout.strip()
        publication = 1595431050+(round_-1)*30
        if not committed or publication <= int(committed):
            problems.append("round is not published after the commit that fixed it")
    for path in loaded_project_modules():
        tracked = subprocess.run(["git", "ls-files", "--error-unmatch", path], cwd=ROOT, capture_output=True).returncode == 0
        unchanged = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", path], cwd=ROOT).returncode == 0
        if not (tracked and unchanged):
            problems.append(f"module not tracked or changed: {path}")
    return problems


def bootstrap_ratio(pairs, seed, samples=10000):
    """95% percentile interval of sum(new)/sum(baseline) over task resamples."""
    rng = random.Random(seed)
    ratios = []
    for _ in range(samples):
        draw = [pairs[rng.randrange(len(pairs))] for _ in pairs]
        base = sum(b for _, b in draw)
        ratios.append(sum(n for n, _ in draw)/base if base else 1.0)
    ratios.sort()
    return ratios[int(0.025*samples)], ratios[int(0.975*samples)-1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--non-binding", action="store_true")
    args = parser.parse_args()
    if os.environ.get("PYTHONHASHSEED") != "0":
        raise SystemExit("PYTHONHASHSEED=0 is required")
    started = time.perf_counter()
    config = json.loads((ROOT/args.config).read_text())
    protocol = config["protocol"]
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    def write(name, value):
        (output/name).write_text(json.dumps(value, indent=1, default=str)+"\n", encoding="utf-8")

    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    modules_before = loaded_project_modules()
    problems = [] if args.non_binding else binding_checks(protocol, args.config)
    if problems:
        raise SystemExit("binding run refused: "+json.dumps(problems))
    if args.non_binding and isinstance(protocol.get("development_fresh_seed"), int):
        seed, beacon = protocol["development_fresh_seed"], None
        training_seed = protocol["development_training_seed"]
    else:
        seed, beacon = fetch_beacon(protocol["fresh_seed_source"])
        training_seed, _ = fetch_beacon(dict(protocol["fresh_seed_source"], salt=protocol["training_salt"]))
    used = set(protocol["development_seeds"])
    if (seed in used or training_seed in used or seed == training_seed) and not args.non_binding:
        raise SystemExit("seed collides with a development seed or with the training seed")
    write("environment.json", {"sha": sha, "binding": not args.non_binding, "python": sys.version,
                               "platform": platform.platform(), "config": config, "fresh_seed": seed,
                               "training_seed": training_seed, "beacon": beacon, "modules": modules_before,
                               "workflow_run_id": os.environ.get("GITHUB_RUN_ID")})
    budget = protocol["operation_cap"]

    # 1. Training on the system's own reductions of development complexes.
    training_started = time.perf_counter()
    training_cohort = ac.generate_model_tasks(training_seed, protocol["training_count"])
    training = []
    for task in training_cohort["tasks"]:
        simplices = ac.rips_simplices([tuple(p) for p in task["points"]], task["r2"])
        K = alg.simplicial_chain_complex(simplices)
        costs = {o: amm.minimal_model(K, o, budget=budget)["algebraic_operations"] for o in amm.ORDERINGS}
        training.append({"features": amm.complex_features(K), "costs": costs})
    rule = amm.learn_ordering_rule(training)
    write("training.json", {"cohort_rule": training_cohort["rule"], "items": training, "rule": rule.description,
                            "seconds": time.perf_counter()-training_started})

    # 2-3. Fresh cohort.
    cohort = ac.generate_model_tasks(seed, protocol["fresh_count"])
    exposed = {task_key(t) for t in training_cohort["tasks"]}
    for development_seed in protocol["development_seeds"]:
        generator = getattr(ac, protocol["development_generators"][str(development_seed)])
        exposed |= {task_key(t) for t in generator(development_seed, protocol["development_counts"][str(development_seed)])["tasks"]}
    overlap = [i for i, t in enumerate(cohort["tasks"]) if task_key(t) in exposed]
    write("fresh-cohort.json", dict(cohort, overlap_with_exposed_tasks=overlap))
    if overlap and not args.non_binding:
        raise SystemExit("fresh cohort overlaps development tasks")
    conditions = [protocol["baseline"], protocol["primary"], "explore"]+[o for o in amm.ORDERINGS if o != protocol["baseline"]]
    rows = []
    for i, task in enumerate(cohort["tasks"]):
        simplices = ac.rips_simplices([tuple(p) for p in task["points"]], task["r2"])
        K = alg.simplicial_chain_complex(simplices)
        truth = ac.reference_betti(simplices)
        row = {"index": i, "shape": task["shape"], "dims": K.dims, "features": amm.complex_features(K)}
        for strategy in (("direct", "collapse") if i % 2 == 0 else ("collapse", "direct")):
            begin = time.perf_counter()
            try:
                record = ars.solve_homology(K, strategy, budget=budget, top=1)
                verdict = audit(simplices, K, truth, record, minimal_model=False)
            except Exception as exc:
                record, verdict = {"solved": True, "operations": {}}, {"passed": False, "reason": repr(exc)}
            row["betti:"+strategy] = {"solved": bool(record.get("solved")) and verdict["passed"],
                                      "claimed": bool(record.get("solved")), "audit": verdict,
                                      "operations": record.get("operations", {}).get("total"),
                                      "breakdown": record.get("operations"), "reduced_size": record.get("reduced_size"),
                                      "seconds": time.perf_counter()-begin}
        for condition in conditions[i % len(conditions):]+conditions[:i % len(conditions)]:
            begin = time.perf_counter()
            try:
                record = amm.minimal_model(K, condition, budget=budget, rule=rule)
                verdict = audit(simplices, K, truth, record)
            except Exception as exc:          # recorded as a failed claim, never a crash of the run
                record, verdict = {"solved": True, "failure": repr(exc)}, {"passed": False, "reason": repr(exc)}
            row[condition] = {"solved": bool(record.get("solved")) and verdict["passed"], "claimed": bool(record.get("solved")),
                              "audit": verdict, "operations": record.get("operations"),
                              "algebraic_operations": record.get("algebraic_operations"),
                              "queue_operations": record.get("queue_operations"), "chosen": record.get("chosen"),
                              "model_size": record.get("model_size"), "seconds": time.perf_counter()-begin}
        rows.append(row)
        print(json.dumps({"index": i, "dims": K.dims,
                          **{c: (row[c]["solved"], row[c]["operations"]) for c in ("betti:direct", "betti:collapse")},
                          **{c: (row[c]["solved"], row[c]["algebraic_operations"]) for c in conditions}}), flush=True)
        write("fresh-rows.json", rows)

    def betti_cost(row, strategy):
        cell = row["betti:"+strategy]
        return cell["operations"] if cell["solved"] else budget
    betti_pairs = [(betti_cost(r, "collapse"), betti_cost(r, "direct")) for r in rows]
    betti_low, betti_high = bootstrap_ratio(betti_pairs, seed)
    betti = {"tasks": len(rows),
             "solved": {s: sum(r["betti:"+s]["solved"] for r in rows) for s in ("direct", "collapse")},
             "incorrect_claims": {s: sum(1 for r in rows if r["betti:"+s]["claimed"] and not r["betti:"+s]["audit"]["passed"])
                                  for s in ("direct", "collapse")},
             "total_operations": {"direct": sum(b for _, b in betti_pairs), "collapse": sum(c for c, _ in betti_pairs)},
             "ratio_collapse_to_direct": sum(c for c, _ in betti_pairs)/max(1, sum(b for _, b in betti_pairs)),
             "bootstrap_95": [betti_low, betti_high],
             "wins": sum(1 for c, b in betti_pairs if c < b), "losses": sum(1 for c, b in betti_pairs if c > b)}

    baseline, primary = protocol["baseline"], protocol["primary"]
    def cost(row, condition, kind="algebraic_operations"):
        return row[condition][kind] if row[condition]["solved"] else budget
    pairs = [(cost(r, primary), cost(r, baseline)) for r in rows]
    low, high = bootstrap_ratio(pairs, seed)
    total_primary, total_baseline = sum(p for p, _ in pairs), sum(b for _, b in pairs)
    oracle = sum(min(cost(r, o) for o in amm.ORDERINGS) for r in rows)
    summary = {
        "tasks": len(rows), "solved": {c: sum(r[c]["solved"] for r in rows) for c in conditions},
        "incorrect_claims": {c: sum(1 for r in rows if r[c]["claimed"] and not r[c]["audit"]["passed"]) for c in conditions},
        "total_operations": {c: sum(cost(r, c) for r in rows) for c in conditions},
        "ratio_primary_to_baseline": total_primary/total_baseline, "bootstrap_95": [low, high],
        "wins": sum(1 for p, b in pairs if p < b), "losses": sum(1 for p, b in pairs if p > b),
        "oracle_ratio_to_baseline": oracle/total_baseline,
        "explore_ratio_to_baseline": sum(cost(r, "explore") for r in rows)/total_baseline,
        "total_operations_including_queue": {c: sum(cost(r, c, "operations") for r in rows) for c in conditions},
        "queue_operations": {c: sum(cost(r, c, "queue_operations") for r in rows) for c in conditions},
        "acquired_choices": {o: sum(1 for r in rows if r[primary]["chosen"] == o) for o in amm.ORDERINGS}}
    modules_after = loaded_project_modules()
    unchanged = all(modules_after.get(k) == v for k, v in modules_before.items())
    criterion = {"binding": not args.non_binding, "sources_unchanged": unchanged, "no_overlap": not overlap,
                 "zero_incorrect_answers": all(v == 0 for v in betti["incorrect_claims"].values())
                                           and all(v == 0 for v in summary["incorrect_claims"].values()),
                 "all_tasks_solved_direct_and_collapse": betti["solved"]["direct"] == betti["solved"]["collapse"] == len(rows),
                 "collapse_total_lower": betti["total_operations"]["collapse"] < betti["total_operations"]["direct"],
                 "bootstrap_upper_below_1": betti_high < 1.0}
    criterion["improvement"] = all(criterion.values())
    secondary = {"acquired_total_lower_than_min_fill": total_primary < total_baseline,
                 "acquired_bootstrap_upper_below_1": high < 1.0}
    report = {"primary_betti": betti, "criterion": criterion, "secondary_minimal_models": summary,
              "secondary_flags": secondary, "rule": rule.description, "sha": sha,
              "total_seconds": time.perf_counter()-started,
              "claims_not_made": ["the minimal model and its homotopy data are classical linear algebra over QQ",
                                  "orderings are supplied; training runs every ordering and fits a one-split selection rule",
                                  "the primary metric counts all operations of solve_homology including the queue; for minimal models algebraic work and queue work are reported separately",
                                  "operation counts are a declared deterministic cost, not wall time"]}
    write("result.json", report)
    print(json.dumps(report, indent=1, default=str))
    return 0 if unchanged else 1


if __name__ == "__main__":
    raise SystemExit(main())
