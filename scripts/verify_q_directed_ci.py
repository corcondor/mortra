"""Fresh, fail-closed reproduction through the existing normal CLI.

This is a test harness, not an acquisition mechanism. Only repository task
names and workload settings are supplied. The saved ledger is produced by the
normal run in this invocation, never copied from historical success artifacts.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time
import traceback
import unittest


CONTROL = Path(__file__).resolve().parents[1]


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n",
                          encoding="utf-8")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args],
                                   text=True, encoding="utf-8").strip()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def source_hashes(repo):
    names = git(repo, "ls-files").splitlines()
    return {name: digest(repo / name) for name in names
            if name.endswith((".py", ".yml", ".yaml"))
            or name.startswith("requirements") or name == "configs/q-directed-verification.json"}


def environment():
    return {
        "python": platform.python_version(), "executable": sys.executable,
        "platform": platform.platform(), "machine": platform.machine(),
        "dependencies": dict(sorted((d.metadata["Name"], d.version)
                                    for d in importlib.metadata.distributions()
                                    if d.metadata["Name"])),
        "github_actions": os.environ.get("GITHUB_ACTIONS") == "true",
        "runner_os": os.environ.get("RUNNER_OS"),
        "runner_image": os.environ.get("ImageVersion"),
        "workflow_sha": os.environ.get("GITHUB_WORKFLOW_SHA"),
        "workflow_ref": os.environ.get("GITHUB_WORKFLOW_REF"),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
    }


def check_small(trace, lengths):
    rows = trace["verification"]
    require([r["length"] for r in rows] == lengths, "missing independent enumeration lengths")
    require(trace["all_checks_agree"] is True, "trace reports disagreement")
    for row in rows:
        require(row["answers_agree"] is True, "maximum / attaining count disagree")
        require(row["by_enumeration"] == row["by_representation"], "recorded answers differ")
        require(row["distributions_agree"] is True, "observation distributions disagree")
        require(bool(row["distribution"]), "missing observation distribution")
        require(row["nodes_enumerating"] > 0, "enumeration was not executed")
        require(row["by_enumeration"]["total_words"] > 0, "empty enumeration")
    require(bool(trace["answers"]), "no subsequent answer")


def no_acquisition(trace):
    require(trace.get("candidates_offered", []) == [], "reuse offered candidates")
    for phase in ("acquisition", "certification"):
        costs = trace["costs"][phase]
        for key in ("prover_calls", "task_certifier_calls", "search_nodes", "wall_time"):
            require(costs[key] == 0, f"reuse performed {phase}: {key}")


def check_reuse(trace, allowed_entries):
    require(trace["reused"] is True, "stored representation was not reused")
    require(trace["acquired_again"] is False, "representation was acquired again")
    require(trace["from_entry"] in allowed_entries, "reuse came from a different store")
    require(trace["cost"]["proof_calls"] == 0, "reuse invoked a prover")
    require(trace["cost"]["task_certifier_calls"] == 0, "reuse re-proved Task")
    no_acquisition(trace)
    scope = trace["reuse_contract"]["scope"]
    require(scope["kind"] == "all_finite_words", "long reuse exceeds certificate scope")
    require(scope["coefficient_field"] == "QQ" and scope["centre_domain"] == "Z^3",
            "unexpected certified domain")
    require(bool(trace["answers"]), "reused trace has no answer")


def check_normal(trace, ledger):
    require(trace["route"] == "q-directed", "not the q-directed route")
    require(trace["closure_method"] == "task-directed minimal common invariant linear space",
            "not direct closure")
    require(trace["grammar"]["source"] == "TaskSpec.observable_expression and required_observables",
            "observable did not come from Task")
    require(len(trace["candidates_offered"]) == 1, "not one task evaluation")
    require(trace["candidates_offered"] == trace["required_observables"][:1],
            "candidate differs from Task evaluation")
    require(trace["costs"]["acquisition"]["prover_calls"] == 1, "closure prover not executed once")
    require(trace["costs"]["certification"]["task_certifier_calls"] == 1,
            "Task certificate not constructed once")
    summaries = []
    for entry in ledger["entries"].values():
        rep = entry["representation"]
        if not rep.get("basis"):
            continue
        for cert in entry["certificates"]:
            if not cert["admissible"]:
                continue
            require(rep["observable"] == trace["candidates_offered"][0], "wrong stored observation")
            dim = rep["dimension"]
            require(dim > 0 and len(rep["basis"]) == dim, "missing derived basis")
            require(rep["identity_residuals_all_zero"] is True, "nonzero action residual")
            premise = rep["step_premise"]
            require(premise["exact"] is True and premise["frames_closed"] is True,
                    "unproved action binding")
            require(premise["identities_checked"] > 0, "no action identities checked")
            require(set(rep["action_matrices"]) == set(cert["reuse_key"]["action_system"]["alphabet"]),
                    "missing generator matrix")
            for matrix in rep["action_matrices"].values():
                require(len(matrix) == dim and all(len(row) == dim for row in matrix),
                        "invalid derived matrix shape")
            checks = {c["name"]: c for c in cert["checks"]}
            require(set(checks) >= {"transition", "observable", "legality", "goal", "start"},
                    "missing certificate obligations")
            require(all(c["holds"] is True for c in checks.values()), "failed certificate")
            require(checks["observable"]["kind"] == "proof"
                    and checks["observable"]["evaluation_matches_declared_expression"] is True,
                    "readout not proved against evaluated q")
            require(cert["readout"] == checks["observable"]["coefficients"]
                    and len(cert["readout"]) == dim, "missing derived readout")
            require(cert["coverage"]["kind"] == "all_finite_words", "only bounded certificate")
            summaries.append({"entry_id": entry["id"], "representation": rep, "certificate": cert})
    require(len(summaries) == 1, "expected one newly certified representation")
    return summaries


def check_refusal(trace):
    require(trace.get("fallback") is True, "missing exact fallback")
    require(trace["selected"].get("basis") is None, "inadmissible representation was used")
    require(trace.get("admitted") == [], "collision observation was admitted")
    witnesses = [r["counterexample"] for r in trace["refused_by_certificate"]
                 if "legality" in r["refused_by"] and r.get("counterexample")]
    require(bool(witnesses), "missing legality counterexample")
    for w in witnesses:
        require(w["check"] == "legality" and w["value_a"] != w["value_b"],
                "invalid legality witness")
        require(len(w["word_a"]) == len(w["word_b"]) == w["length"],
                "counterexample is not in one layer")
    return witnesses


def check_stopped(trace):
    require(bool(trace.get("stopped")), "reuse-only did not stop")
    require(trace["reused"] is False, "incompatible certificate reused")
    require(not trace.get("answers"), "inadmissible reuse produced an answer")
    no_acquisition(trace)


def tests_child(repo, config, result_path):
    # Only test discovery/execution occurs here; the normal runs are separate processes.
    sys.path.insert(0, str(repo))
    modules = config["test_modules"]
    print("unittest module set:", " ".join(modules), flush=True)
    suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    imported = {name: str(Path(module.__file__).resolve())
                for name, module in list(sys.modules.items())
                if (name.startswith("math_os_prototype.") or name in modules)
                and getattr(module, "__file__", None)}
    wrong = {name: path for name, path in imported.items()
             if not Path(path).is_relative_to(repo)}
    failed = len(result.failures) + len(result.errors) + len(result.unexpectedSuccesses)
    report = {
        "run": result.testsRun, "passed": result.testsRun - failed - len(result.skipped)
        - len(result.expectedFailures), "failed": failed, "skipped": len(result.skipped),
        "expected_failures": len(result.expectedFailures),
        "successful": result.wasSuccessful() and not wrong,
        "wrong_import_locations": wrong, "source_imports": imported,
    }
    write_json(result_path, report)
    return 0 if report["successful"] else 1


def run_process(command, repo, logfile, timeout=900):
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.update(PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1",
               PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    started = time.perf_counter()
    print("COMMAND:", json.dumps(command), flush=True)
    with logfile.open("w", encoding="utf-8") as log:
        try:
            proc = subprocess.run(command, cwd=repo, env=env, stdout=log,
                                  stderr=subprocess.STDOUT, timeout=timeout)
            code, error = proc.returncode, None
        except subprocess.TimeoutExpired:
            code, error = 124, f"timeout after {timeout}s"
    print(logfile.read_text(encoding="utf-8", errors="replace"), flush=True)
    return {"command": command, "cwd": str(repo), "returncode": code, "error": error,
            "wall_seconds": time.perf_counter() - started, "log": logfile.name}


def prepare(args):
    out, repo = args.output, args.repo
    out.mkdir(parents=True, exist_ok=False)
    sha = git(repo, "rev-parse", "HEAD")
    report = {
        "schema": "mortra.q-directed-ci-verification.v1",
        "repository": args.repository, "ref": args.ref, "sha": sha,
        "expected_sha": args.expected_sha,
        "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
        "workflow_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "harness_sha": git(CONTROL, "rev-parse", "HEAD"),
        "workflow_sha": os.environ.get("GITHUB_WORKFLOW_SHA"),
        "workflow_run_url": (f"https://github.com/{args.repository}/actions/runs/"
                             + os.environ["GITHUB_RUN_ID"]) if os.environ.get("GITHUB_RUN_ID") else None,
        "status": "prepared_not_executed", "tests_passed": 0, "tests_failed": 0,
        "normal_run_passed": False, "reuse_passed": False, "refusal_passed": False,
        "generated_at": now(), "errors": [], "runs": [],
    }
    write_json(out / "verification.json", report)
    try:
        require(not args.expected_sha or re.fullmatch("[0-9a-fA-F]{40}", args.expected_sha),
                "expected SHA must be a full 40-character commit")
        require(not args.expected_sha or sha == args.expected_sha.lower(), "HEAD mismatch")
        require(git(repo, "status", "--porcelain", "--untracked-files=all") == "", "target is dirty")
        require(git(repo, "remote", "get-url", "origin").rstrip("/").removesuffix(".git")
                == f"https://github.com/{args.repository}", "repository origin mismatch")
        config = read_json(args.config)
        write_json(out / "config.json", config)
        write_json(out / "environment-before-install.json", environment())
        write_json(out / "sources.json", source_hashes(repo))
        write_json(out / "harness-sources.json", {
            str(p.relative_to(CONTROL)): digest(p) for p in
            (Path(__file__), args.config, CONTROL / "requirements.txt", CONTROL / "requirements-test.txt")})
        (out / "git-sha.txt").write_text(sha + "\n", encoding="utf-8")
        commands = []
        for row in config["runs"]:
            command = [sys.executable, "-u", "scripts/run_representation_tasks.py",
                       "--output", str(out / row["id"]), "--task", row["task"],
                       "--route", row["route"], *config["common_arguments"],
                       "--answer", str(row["answer"]), "--reuse-length", str(row["reuse_length"])]
            if row.get("ledger"):
                command += ["--ledger", str(out / row["ledger"])]
            commands.append({**row, "command": command})
        test_command = [sys.executable, str(Path(__file__).resolve()), "--repo", str(repo),
                        "--config", str(out / "config.json"), "--tests-child",
                        "--test-result", str(out / "test-result.json")]
        write_json(out / "plan.json", {"sha": sha, "test_command": test_command,
                                      "runs": commands, "config_sha256": digest(out / "config.json")})
    except Exception as exc:
        report.update(status="preparation_failed", errors=[str(exc)])
        write_json(out / "verification.json", report)
        raise


def execute(args):
    repo, out = args.repo, args.output
    report = read_json(out / "verification.json")
    require(report["status"] == "prepared_not_executed", "use a fresh verification directory")
    config, plan = read_json(out / "config.json"), read_json(out / "plan.json")
    report["status"] = "running"
    def persist():
        report["generated_at"] = now()
        write_json(out / "verification.json", report)
    def unchanged():
        require(git(repo, "rev-parse", "HEAD") == report["sha"], "HEAD changed")
        require(git(repo, "status", "--porcelain", "--untracked-files=all") == "", "target source changed")
        require(source_hashes(repo) == read_json(out / "sources.json"), "source hashes changed")
        require(digest(out / "config.json") == plan["config_sha256"], "run config changed")
        require(all(digest(CONTROL / p) == h for p, h in
                    read_json(out / "harness-sources.json").items()), "harness changed")
    persist()
    try:
        unchanged()
        write_json(out / "environment.json", environment())
        freeze = subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True)
        (out / "dependencies.txt").write_text(freeze, encoding="utf-8")
        tests = run_process(plan["test_command"], repo, out / "tests.log")
        report["test_process"] = tests
        test_result = read_json(out / "test-result.json")
        report.update(tests_passed=test_result["passed"], tests_failed=test_result["failed"],
                      tests_run=test_result["run"], tests_skipped=test_result["skipped"])
        report["test_suite_passed"] = (
            tests["returncode"] == 0 and test_result["successful"]
            and test_result["passed"] == config["expected_tests"]
            and test_result["run"] == config["expected_tests"])
        persist()
        # Retain independent run diagnostics even when the test stage fails.
        for row in plan["runs"]:
            unchanged()
            result = {"id": row["id"], "passed": False}
            report["runs"].append(result)
            try:
                if row.get("ledger"):
                    require((out / row["ledger"]).is_file(), "fresh source ledger missing")
                result.update(run_process(row["command"], repo, out / (row["id"] + ".log")))
                require(result["returncode"] == 0, "normal CLI failed")
                seal = read_json(out / row["id"] / "result-seal.json")
                require(seal["completed"] is True and seal["sources_unchanged"] is True,
                        "run did not complete with unchanged sources")
                payload = read_json(out / row["id"] / "traces.json")
                trace, later = payload["tasks"][row["task"]], payload["reuse"][row["task"]]
                if row["id"] == "normal":
                    check_small(trace, config["verify_lengths"])
                    summaries = check_normal(trace, read_json(out / "normal/ledger.json"))
                    write_json(out / "representation-summary.json", summaries)
                    check_reuse(later, {s["entry_id"] for s in summaries})
                    require([a["length"] for a in later["answers"]] == [row["reuse_length"]],
                            "missing later reuse length")
                    report["normal_run_passed"] = True
                elif row["id"] == "reuse":
                    check_small(trace, config["verify_lengths"])
                    entries = read_json(out / "normal/ledger.json")["entries"]
                    check_reuse(trace, entries)
                    check_reuse(later, entries)
                    require([a["length"] for a in trace["answers"]] == [row["answer"]]
                            and [a["length"] for a in later["answers"]] == [row["reuse_length"]],
                            "missing long reuse answers")
                    input_seal = read_json(out / "reuse/input-seal.json")
                    require(input_seal["ledger_sha256"] == digest(out / "normal/ledger.json"),
                            "reuse did not read this run's ledger")
                    original = entries[trace["from_entry"]]["certificates"][-1]
                    require(trace["reuse_contract"]["source_task"] != trace["task"],
                            "reuse did not change task / start")
                    require(trace["reuse_contract"]["scope"] == original["coverage"],
                            "reuse silently extended certificate scope")
                    report["reuse_passed"] = True
                elif row["id"] == "refusal":
                    check_small(trace, config["verify_lengths"])
                    write_json(out / "refusal-summary.json", check_refusal(trace))
                    require(later["reused"] is False, "later collision reuse was accepted")
                else:
                    check_stopped(trace)
                    require(later["reused"] is False, "later reuse-only collision was accepted")
                result["passed"] = True
            except Exception as exc:
                result["error"] = str(exc)
                report["errors"].append(f"{row['id']}: {exc}")
            persist()
        passed = {r["id"]: r["passed"] for r in report["runs"]}
        report["refusal_passed"] = passed.get("refusal", False) and passed.get("refusal-reuse", False)
        unchanged()
        report["sources_unchanged"] = True
        report["status"] = "passed" if (
            report["test_suite_passed"] and report["normal_run_passed"]
            and report["reuse_passed"] and report["refusal_passed"]
            and not report["errors"]) else "failed"
    except Exception as exc:
        report["status"] = "failed"
        report["errors"].append(str(exc))
        (out / "harness-error.log").write_text(traceback.format_exc(), encoding="utf-8")
    persist()
    print(json.dumps(report, indent=2), flush=True)
    return 0 if report["status"] == "passed" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=CONTROL)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--config", type=Path, default=CONTROL / "configs/q-directed-verification.json")
    parser.add_argument("--repository", default="corcondor/mortra")
    parser.add_argument("--ref", default=os.environ.get("GITHUB_REF", "local"))
    parser.add_argument("--expected-sha", default="")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--tests-child", action="store_true")
    parser.add_argument("--test-result", type=Path)
    args = parser.parse_args()
    args.repo, args.config = args.repo.resolve(), args.config.resolve()
    if args.tests_child:
        return tests_child(args.repo, read_json(args.config), args.test_result)
    require(args.output is not None, "--output required")
    args.output = args.output.resolve()
    require(not args.output.is_relative_to(args.repo), "outputs must be outside tested checkout")
    if args.prepare:
        prepare(args)
        return 0
    return execute(args)


if __name__ == "__main__":
    raise SystemExit(main())
