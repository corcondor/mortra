"""Run frozen formal tasks through the normal Theory entry, preserving failures."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from run_theory_formation import source_seal


def write(path, value):
    path.write_text(json.dumps(value, indent=2)+"\n", encoding="utf-8")


def execute(config, config_path, output, log_path, timeout):
    write(config_path, config)
    command = [sys.executable, str(ROOT/"scripts/run_theory_formation.py"),
               "--config", str(config_path), "--output", str(output)]
    start = time.perf_counter()
    with log_path.open("w", encoding="utf-8") as log:
        try:
            process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=os.name != "nt",
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0)
            process.wait(timeout=timeout)
            path = output/"verification.json"
            result = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
                "proved": False, "status": "process_failure", "returncode": process.returncode}
            result.setdefault("proved", False)
            result.setdefault("status", "solver_failure")
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               capture_output=True, check=False)
            else:
                import signal
                os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            result = {"proved": False, "status": "timeout", "false_proofs": 0}
    return result, command, time.perf_counter()-start


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--backend", choices=["exact", "yuclid", "python"])
    parser.add_argument("--require-no-yuclid", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    if "task_source" in plan:
        from math_os_prototype.representation_progress import digest
        source = json.loads((ROOT/plan["task_source"]["path"]).read_text(encoding="utf-8"))
        if digest(source["tasks"]) != plan["task_source"]["tasks_sha256"]:
            raise ValueError("frozen task source changed")
        plan["tasks"] = source["tasks"]
    write(args.output/"source-plan.json", plan)
    if args.backend:
        plan["search"]["deduction_backend"] = args.backend
    import importlib.util
    import platform
    import shutil
    environment = {"python": sys.version, "platform": platform.platform(),
        "py_yuclid_installed": importlib.util.find_spec("py_yuclid") is not None,
        "yuclid_executable": shutil.which("yuclid"),
        "repository": os.environ.get("GITHUB_REPOSITORY"),
        "ref": os.environ.get("GITHUB_REF"), "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
        "command": sys.argv}
    write(args.output/"environment.json", environment)
    if args.require_no_yuclid and (environment["py_yuclid_installed"] or environment["yuclid_executable"]
                                  or plan["search"]["deduction_backend"] != "exact"):
        raise RuntimeError("Internal reproduction requires absence of Yuclid package and executable")
    write(args.output/"plan.json", plan)
    seal = source_seal()
    write(args.output/"source-seal.json", seal)
    rows = []
    for index, task in enumerate(plan["tasks"]):
        config = {"domain": plan.get("domain", {"kind": "geometry"}),
                  "task": task, "search": plan["search"]}
        if "protocol" in plan:
            config["protocol"] = plan["protocol"]
        if "source_archive" in plan:
            config.update(source_archive=plan["source_archive"], use_acquired=plan.get("use_acquired", True))
        config_path = args.output/f"task-{index}.json"
        output = args.output/f"run-{index}"
        result, command, seconds = execute(config, config_path, output,
            args.output/f"task-{index}.log", plan["task_timeout_seconds"])
        row = {"id": task["id"], "command": command, "result": result,
               "subprocess_wall_seconds": seconds}
        events_path = output/"events.jsonl"
        events = []
        if events_path.exists():
            for line in events_path.read_text(encoding="utf-8").splitlines():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    # A timed-out process may leave an incomplete final record.
                    pass
        symbolic_applications = [e for e in events if e["event"] == "symbolic_dsl_apply"]
        row["symbolic_trace_counts"] = {
            "executed": len(symbolic_applications),
            "acquired": sum(e["action"]["call"].get("op") == "use" for e in symbolic_applications),
            "proof_attempts": sum(e["event"] == "proof_dsl_attempt" for e in events),
            "proof_timeouts": sum(e["event"] == "proof_dsl_attempt" and e.get("timed_out", False) for e in events)}
        applications = [e for e in events if e["event"] == "apply"]
        row["trace_counts"] = {
            "native_backward_compilations": sum(e["event"] == "native_backward_compilation" for e in events),
            "native_compilations_using_certified_relations": sum(e["event"] == "native_backward_compilation"
                and bool(e.get("certified_relations_used")) for e in events),
            "native_contract_applications": sum(bool(e["action"].get("native_contract_selected")) for e in applications),
            "completed_morphism_applications": len(applications),
            "rejected_constructions": sum(e["event"] == "rejected_construction" for e in events),
            "new_relations_with_multiplicity": sum(len(e["new_relations"]) for e in applications),
            "maximum_path_depth": max((len(e["state"]["path"]) for e in applications), default=0),
            "child_states_enumerated": len({e["state_key"] for e in events if e["event"] == "enumerate"}
                & {e["child"] for e in applications}),
            "native_exact_checks_started": sum(e["event"] == "exact_check_started" for e in events),
            "native_exact_checks_completed": sum(e["event"] == "exact_check_completed" for e in events),
            "certified_new_relations": sum(e["event"] == "exact_relation_check" and e["accepted"] for e in events),
            "relation_changed_rankings": sum(e["event"] == "enumerate" and e.get("native_relations_changed_ranking", False) for e in events),
        }
        row["native_contract_edges"] = [{"state_key": e["state_key"],
            "certified_relations_used": e["certified_relations_used"],
            "obligations": e["obligations"],
            "actions": [a["action"] for a in applications if a["parent"] == e["state_key"]
                        and a["action"].get("native_contract_selected")]}
            for e in events if e["event"] == "native_backward_compilation"
            and any(a["parent"] == e["state_key"] and a["action"].get("native_contract_selected")
                    for a in applications)]
        # Only count a causal edge when that exact child is later enumerated.
        row["native_feedback_edges"] = [{"parent": a["parent"], "child": a["child"],
            "action": a["action"], "derived_relations": sorted(set(a["state"]["relations"])-
                set(a["state"].get("relations_before_exact_closure", a["state"]["relations"]))),
            "next_families": [e["family"] for e in events if e["event"] == "enumerate"
                and e["state_key"] == a["child"] and e.get("native_relations_changed_ranking")]}
            for a in applications if any(e["event"] == "enumerate" and e["state_key"] == a["child"]
                and e.get("native_relations_changed_ranking") for e in events)]
        if result["proved"] and result.get("auxiliary_count", 0):
            from newclid.jgex.formulation import JGEXFormulation
            formulation = JGEXFormulation.from_text(task["statement"])
            renamed = formulation.renamed({str(p): f"v{i}" for i, p in enumerate(sorted(formulation.points))})
            original = json.loads((output/"state.json").read_text(encoding="utf-8"))
            row["stability"] = []
            for name, variant in [
                ("renamed", dict(config, task=dict(task, statement=str(renamed)))),
                ("similarity", dict(config, search=dict(config["search"], diagram_similarity=[3, 4, -2]))),
            ]:
                destination = args.output/f"run-{index}-{name}"
                checked, cmd, elapsed = execute(variant, args.output/f"task-{index}-{name}.json",
                    destination, args.output/f"task-{index}-{name}.log", plan["task_timeout_seconds"])
                state_path = destination/"state.json"
                state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
                row["stability"].append({"variant": name, "result": checked, "command": cmd,
                    "seconds": elapsed, "same_path": state.get("path") == original["path"],
                    "same_exact_certificates": state.get("certificates") == original["certificates"]})
        rows.append(row)
        write(args.output/"results.json", rows)
        print(json.dumps({"id": task["id"], "status": result["status"],
                          "proved": result["proved"], "aux": result.get("auxiliary_count")}), flush=True)
    summary = {"total": len(rows), "proved": sum(r["result"]["proved"] for r in rows),
        "solved_only_after_auxiliary": sum(r["result"]["proved"] and r["result"].get("auxiliary_count", 0)>0
            and not r["result"].get("initial_goal_certified", r["result"].get("initial_deduction_proved", True)) for r in rows),
        "statuses": {s: sum(r["result"]["status"] == s for r in rows)
                     for s in sorted({r["result"]["status"] for r in rows})},
        "false_proofs_detected": sum(r["result"].get("false_proofs", 0) for r in rows),
        "sources_unchanged": source_seal() == seal,
        "sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
        "acquired_comparison": "stored archive" if plan.get("source_archive") else "initial library only",
        "global_unseen_claim": False}
    summary["execution_completed"] = sum(r["result"].get("execution_completed", False) for r in rows)
    summary["native_feedback_edges"] = sum(len(r["native_feedback_edges"]) for r in rows)
    summary["native_contract_edges"] = sum(len(r["native_contract_edges"]) for r in rows)
    summary["native_contract_edges_using_certified_relations"] = sum(
        bool(e["certified_relations_used"]) for r in rows for e in r["native_contract_edges"])
    summary["minimum_scientific_success"] = any(r["result"]["proved"]
        and not r["result"].get("initial_goal_certified", True)
        and r["result"].get("auxiliary_count", 0) > 0
        and r["native_feedback_edges"] and r["result"].get("replay_passed", False) for r in rows)
    summary["auxiliary_stability"] = [
        {"id": r["id"], "passed": all(v["result"]["proved"] and v["same_path"] and
            v["same_exact_certificates"] for v in r["stability"])} for r in rows if "stability" in r]
    write(args.output/"verification.json", summary)
    print(json.dumps(summary, indent=2))
    return int(not summary["sources_unchanged"] or any(r["result"]["status"] in {
        "solver_failure", "process_failure", "replay_failure"} for r in rows))


if __name__ == "__main__":
    raise SystemExit(main())
