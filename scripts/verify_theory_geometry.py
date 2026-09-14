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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    write(args.output/"plan.json", plan)
    seal = source_seal()
    write(args.output/"source-seal.json", seal)
    rows = []
    for index, task in enumerate(plan["tasks"]):
        config = {"domain": {"kind": "geometry"}, "task": task, "search": plan["search"]}
        config_path = args.output/f"task-{index}.json"
        write(config_path, config)
        output = args.output/f"run-{index}"
        command = [sys.executable, str(ROOT/"scripts/run_theory_formation.py"),
                   "--config", str(config_path), "--output", str(output)]
        start = time.perf_counter()
        with (args.output/f"task-{index}.log").open("w", encoding="utf-8") as log:
            try:
                completed = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                           timeout=plan["task_timeout_seconds"])
                result_path = output/"verification.json"
                result = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else {
                    "proved": False, "status": "process_failure", "returncode": completed.returncode}
            except subprocess.TimeoutExpired:
                result = {"proved": False, "status": "timeout", "false_proofs": 0}
        row = {"id": task["id"], "command": command, "result": result,
               "subprocess_wall_seconds": time.perf_counter()-start}
        rows.append(row)
        write(args.output/"results.json", rows)
        print(json.dumps({"id": task["id"], "status": result["status"],
                          "proved": result["proved"], "aux": result.get("auxiliary_count")}), flush=True)
    summary = {"total": len(rows), "proved": sum(r["result"]["proved"] for r in rows),
        "solved_only_after_auxiliary": sum(r["result"]["proved"] and r["result"].get("auxiliary_count", 0)>0
            and r["result"].get("initial_closure_exhausted", False) for r in rows),
        "statuses": {s: sum(r["result"]["status"] == s for r in rows)
                     for s in sorted({r["result"]["status"] for r in rows})},
        "false_proofs_detected": sum(r["result"].get("false_proofs", 0) for r in rows),
        "sources_unchanged": source_seal() == seal,
        "sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
        "acquired_comparison": "unavailable: no provenance-certified acquired geometry library",
        "global_unseen_claim": False}
    write(args.output/"verification.json", summary)
    print(json.dumps(summary, indent=2))
    return int(not summary["sources_unchanged"] or any(r["result"]["status"] in {
        "solver_failure", "process_failure"} for r in rows))


if __name__ == "__main__":
    raise SystemExit(main())
