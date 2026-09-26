"""Exact, fail-closed reproduction gate. No exploration algorithms are defined here."""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import gzip
import hashlib
import importlib.util
import itertools
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import traceback
import types
import zipfile

ROOT = Path(__file__).resolve().parents[2]
ZIP = ROOT / "experiments/task_agent/data/pretraining_reference/original.zip"
ZIP_SHA = "b483aeb976826ac993a17dde0e43b45e4fbf7b2c86776e22f24566f6f97ccf64"
BASE = "154f7a62988a52265b17c4dd0ad02839c9e32cc3"
FROZEN = "24c44da50aac2c084a91fdd9f6754f0429da9350"
SEEDS = tuple(range(73000000, 73000008))
METHODS = ("structural", "frontier_t0", "virtual_frontier")
BUDGETS = (128, 512, 2048)
TIME_FIELDS = {"eval_cpu_seconds", "eval_wall_seconds"}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def unpack(output):
    assert sha(ZIP) == ZIP_SHA, "Original ZIP digest mismatch"
    output.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(ZIP) as archive:
        for item in archive.infolist():
            target = (output / item.filename).resolve()
            assert target.is_relative_to(output.resolve()), item.filename
        archive.extractall(output)
    bundle = output / "mortra_pretraining_smoke"
    checked = []
    for line in (bundle / "SHA256SUMS.txt").read_text().splitlines():
        expected, name = line.split("  ", 1)
        assert sha(bundle / name) == expected, name
        checked.append(name)
    return bundle, checked


def source_audit(bundle):
    import numpy
    import scipy
    import pytest
    manifest = read(bundle / "manifest_before.json")
    hashes = {}
    for name, detail in manifest["full_file_checks"].items():
        assert sha(ROOT / name) == detail["expected"], name
    names = [p.as_posix() for folder in ("experiments/task_agent", "experiments/game_frontier_v1",
             "experiments/game_frontier_v11") for p in Path(folder).glob("*.py")]
    # Check all files already present at the specified report commit, not new harnesses.
    for name in names + ["scripts/evaluate_cross_domain_generalization.py"]:
        old = subprocess.run(["git", "show", f"{BASE}:{name}"], cwd=ROOT, capture_output=True)
        if old.returncode == 0:
            assert (ROOT / name).read_bytes() == old.stdout, name
            hashes[name] = sha(ROOT / name)
    for name in manifest["full_file_checks"]:
        old = subprocess.check_output(["git", "show", f"{FROZEN}:{name}"], cwd=ROOT)
        assert (ROOT / name).read_bytes() == old, name
    pretraining = ROOT / "experiments/task_agent/pretraining.py"
    assert pretraining.read_bytes() == (bundle / "vendor/experiments/task_agent/pretraining.py").read_bytes()
    source = (ROOT / "scripts/evaluate_cross_domain_generalization.py").read_text()
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == "StructuralLearner")
    excerpt = (bundle / "reference/structural_learner_excerpt.py").read_text()
    reference = next(n for n in ast.parse(excerpt).body if isinstance(n, ast.ClassDef))
    assert ast.get_source_segment(source, node) == ast.get_source_segment(excerpt, reference)
    return {"zip_sha256": ZIP_SHA, "frozen_commit": FROZEN, "report_commit": BASE,
            "exact_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            "branch": subprocess.check_output(["git", "branch", "--show-current"], text=True).strip(),
            "git_status": subprocess.check_output(["git", "status", "--short"], text=True),
            "pretraining_sha256": sha(pretraining), "source_sha256": hashes,
            "python": sys.version, "numpy": numpy.__version__, "scipy": scipy.__version__,
            "pytest": pytest.__version__, "platform": platform.platform(),
            "numerical_build": numpy.show_config(mode="dicts"), "command": sys.argv,
            "run_id": os.getenv("GITHUB_RUN_ID"), "attempt": os.getenv("GITHUB_RUN_ATTEMPT"),
            "thread_env": {k: os.getenv(k) for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")}}


def load_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def canonical_context(bundle):
    """Only import wiring differs. The supplied runner/evaluator/tests stay unedited."""
    from experiments.game_frontier_v1.frozen import StructuralLearner
    from experiments.game_frontier_v11.world import Engine
    from experiments.task_agent import pretraining
    assert Path(pretraining.__file__).resolve() == ROOT / "experiments/task_agent/pretraining.py"
    # These two in-memory aliases stop the standalone import helpers selecting vendor/.
    # No ZIP shim replaces a file in the canonical checkout.
    sys.modules["bootstrap"] = types.ModuleType("bootstrap")
    aliases = types.ModuleType("reference_loader")
    aliases.Engine, aliases.StructuralLearner = Engine, StructuralLearner
    sys.modules["reference_loader"] = aliases
    load_file("io_utils", bundle / "io_utils.py")
    module = load_file("run_smoke", bundle / "run_smoke.py")
    assert module.Engine is Engine
    assert module.train_snapshots_with_policy is pretraining.train_snapshots_with_policy
    return module


def integration_run(bundle, output):
    # A separate test fixture preserves every supplied file for its unchanged sealing
    # checks. Its vendor/ is never put on sys.path or used by the canonical run.
    shutil.copytree(bundle, output, ignore=shutil.ignore_patterns("results", "__pycache__", "*.pyc"))
    (output / "results").mkdir()
    run = canonical_context(output)
    import pytest
    code = pytest.main([str(output / "tests"), "-q", "--import-mode=importlib",
                        f"--junitxml={output / 'results/tests.xml'}"])
    if code:
        raise RuntimeError(f"Unmodified bundled tests failed in canonical context: {code}")
    run.reproduce()
    for seed in SEEDS:
        run.compare_world(seed)
    run.summarize()
    load_file("pretraining_reference_audit", output / "audit_results.py")
    imports = {name: str(Path(mod.__file__).resolve()) for name, mod in sys.modules.items()
               if name.startswith("experiments.") and getattr(mod, "__file__", None)}
    assert all(Path(p).is_relative_to(ROOT) for p in imports.values())
    assert not any("/vendor/" in p.replace("\\", "/") for p in imports.values())
    save(output / "canonical_imports.json", imports)


def table(rows):
    keys = [(r["seed"], r["method"], r["budget"], r["task_id"]) for r in rows]
    expected = set(itertools.product(SEEDS, METHODS, BUDGETS, range(12)))
    assert len(keys) == len(set(keys)) == 864, "Duplicate or missing episode keys"
    assert set(keys) == expected, "Wrong episode key set"
    return dict(zip(keys, rows))


def exact_compare(bundle, rerun, output):
    differences, details = [], []
    total_traces = Counter()
    originals, reproduced = [], []
    for seed in SEEDS:
        old, new = bundle / "results" / str(seed), rerun / "results" / str(seed)
        originals.extend(read(old / "episodes.json"))
        reproduced.extend(read(new / "episodes.json"))
        for method, budget in itertools.product(METHODS, BUDGETS):
            name = f"snapshot_{method}_{budget}.json"
            a, b = read(old / name), read(new / name)
            if a != b:
                differences.append({"kind": "snapshot", "seed": seed, "name": name,
                                    "different_attributes": [k for k in a if a[k] != b.get(k)]})
        for name in ("training_trace.jsonl.gz", "evaluation_trace.jsonl.gz"):
            counts, same = Counter(), True
            with gzip.open(old / name, "rt") as a, gzip.open(new / name, "rt") as b:
                for index, (x, y) in enumerate(itertools.zip_longest(a, b)):
                    total_traces[name] += 1
                    if x is None or y is None:
                        differences.append({"kind": "trace_length", "seed": seed, "file": name, "row": index})
                        same = False
                        continue
                    left, right = json.loads(x), json.loads(y)
                    if left != right:
                        same = False
                        fields = [k for k in left.keys() | right.keys() if left.get(k) != right.get(k)]
                        counts.update(fields)
                        differences.append({"kind": "trace", "seed": seed, "file": name, "row": index,
                                            "reference": left, "actual": right, "fields": fields})
            details.append({"seed": seed, "file": name, "exact": same, "different_fields": dict(counts)})
    old_rows, new_rows = table(originals), table(reproduced)
    for key in sorted(old_rows):
        a, b = old_rows[key], new_rows[key]
        assert set(a) == set(b)
        for field in set(a) - TIME_FIELDS:
            if a[field] != b[field]:
                differences.append({"kind": "episode", "key": key, "field": field,
                                    "reference": a[field], "actual": b[field]})
    result = {"passed": not differences, "rows": 864, "snapshots": 72,
              "trace_rows": dict(total_traces), "trace_details": details,
              "difference_counts": dict(Counter(d["kind"] for d in differences)),
              "difference_count": len(differences), "comparison": "exact values; no tolerance; timing columns excluded"}
    save(output / "comparison.json", result)
    with gzip.open(output / "all_differences.jsonl.gz", "wt", encoding="utf-8") as stream:
        for item in differences:
            stream.write(json.dumps(item) + "\n")
    return result


def command(args, log):
    started = time.monotonic()
    with log.open("x", encoding="utf-8") as stream:
        process = subprocess.Popen(args, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            stream.write(line)
            stream.flush()
            print(line, end="", flush=True)
        code = process.wait()
    return {"command": args, "exit_code": code, "wall_seconds": time.monotonic() - started}


def gate(output):
    output.mkdir(parents=True, exist_ok=False)
    bundle, checked = unpack(output / "original")
    save(output / "source_snapshot.json", source_audit(bundle))
    save(output / "original_integrity.json", {"zip_sha256": ZIP_SHA, "checked": checked})
    attempts = []
    comparisons = {}
    for mode in ("standalone", "canonical"):
        dest = output / mode
        if mode == "standalone":
            args = [sys.executable, str(bundle / "reproduce_local.py"), "--output", str(dest)]
        else:
            args = [sys.executable, "-m", "experiments.task_agent.pretraining_reproduction", "canonical",
                    "--bundle", str(bundle), "--output", str(dest)]
        attempts.append({"mode": mode, **command(args, output / f"{mode}.log")})
        try:
            comparisons[mode] = exact_compare(bundle, dest, output / mode)
        except Exception:
            comparisons[mode] = {"passed": False, "exception": traceback.format_exc()}
            save(output / mode / "comparison_error.json", comparisons[mode])
        save(output / "attempts.json", attempts)
    import resource
    passed = all(c["passed"] for c in comparisons.values()) and all(a["exit_code"] == 0 for a in attempts)
    summary = {"passed": passed, "fresh_allowed": passed, "comparisons": comparisons,
               "attempts": attempts, "child_cpu_seconds": resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime + resource.getrusage(resource.RUSAGE_CHILDREN).ru_stime,
               "children_peak_rss_bytes": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss * 1024,
               "status": "REPRODUCTION_PASS" if passed else "REPRODUCTION_MISMATCH_OR_INCOMPLETE",
               "policy_failure": False, "fresh_worlds_evaluated": 0}
    save(output / "gate.json", summary)
    print(json.dumps(summary, indent=2), flush=True)
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("gate", "canonical"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bundle", type=Path)
    args = parser.parse_args()
    if args.mode == "gate":
        gate(args.output.resolve())
    else:
        integration_run(args.bundle.resolve(), args.output.resolve())
