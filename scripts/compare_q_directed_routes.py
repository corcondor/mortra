"""Frozen A/B/C/D experiment launcher. All mathematics runs through the normal CLI.

This is an evaluation plan, not autonomous research-topic selection. Each route
gets a fresh process and directory. D receives only the ledger saved by C.
No candidate, basis, readout, expected answer or lemma is supplied here.
"""
from pathlib import Path
import argparse
from hashlib import sha256
import json
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    names = ("axis1", "c1-plus-c2", "axis1-from-AG", "axis1-collision-free")
    plan = []
    for arm, route in (("A", "existing"), ("B", "enumerate"), ("C", "q-directed")):
        for name in names:
            plan.append({"id": f"{arm}-{name}", "arm": arm, "route": route,
                         "task": name, "answer": [6], "reuse_length": 9, "ledger": None})
    for name in names:
        source = "c1-plus-c2" if name == "c1-plus-c2" else "axis1"
        plan.append({"id": f"D-{name}", "arm": "D", "route": "reuse",
                     "task": name, "answer": [6], "reuse_length": 9,
                     "ledger": str(output / f"C-{source}" / "ledger.json")})
    for name in names[:3]:
        source = "c1-plus-c2" if name == "c1-plus-c2" else "axis1"
        plan.append({"id": f"D-long-{name}", "arm": "D-long", "route": "q-directed",
                     "task": name, "answer": [12], "reuse_length": 14,
                     "ledger": str(output / f"C-{source}" / "ledger.json")})
    for run in plan:
        command = [sys.executable, "-u", "scripts/run_representation_tasks.py",
                   "--output", str(output / run["id"]), "--route", run["route"],
                   "--task", run["task"], "--degree", "1", "--max-terms", "2",
                   "--certificate-depth", "3", "--probe-length", "3",
                   "--verify", "3", "5", "--answer", *map(str, run["answer"]),
                   "--reuse-length", str(run["reuse_length"])]
        if run["ledger"]:
            command += ["--ledger", run["ledger"]]
        run["command"] = command
    def code_hashes():
        paths = [*root.glob("math_os_prototype/*.py"),
                 root / "scripts/run_representation_tasks.py", Path(__file__)]
        return {str(p.relative_to(root)): sha256(p.read_bytes()).hexdigest()
                for p in sorted(paths)}
    frozen = code_hashes()
    (output / "plan.json").write_text(json.dumps({"runs": plan, "sources": frozen,
        "comparison": "same tasks and lengths; fresh acquisition in every A/B/C process",
        "development_fixtures": "named repository tasks, not blind novel problems",
        "D_collision": "negative control: open-fold certificate cannot prove collision legality",
        "D_long": "normal default route must retrieve without reacquisition",
        "scope": "hashes are version checks, not proof against malicious intervention"}, indent=2),
        encoding="utf-8")
    results = []
    for i, run in enumerate(plan):
        if code_hashes() != frozen:
            results.append({"id": run["id"], "stopped": "source changed before launch"})
            break
        print(f"[{i+1}/{len(plan)}] {run['id']}", flush=True)
        started = time.perf_counter()
        with (output / f"{run['id']}.log").open("w", encoding="utf-8") as log:
            process = subprocess.Popen(run["command"], cwd=root, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                       errors="replace")
            for line in process.stdout:
                log.write(line)
                log.flush()
                if line.startswith(("candidate ", "===", "selected:", "stopped:")):
                    print(line.rstrip(), flush=True)
            returncode = process.wait()
        row = {"id": run["id"], "returncode": returncode,
               "process_wall_time": round(time.perf_counter() - started, 6),
               "sources_unchanged": code_hashes() == frozen}
        trace_path = output / run["id"] / "traces.json"
        if trace_path.exists():
            payload = json.loads(trace_path.read_text(encoding="utf-8"))
            trace = payload["tasks"].get(run["task"], {})
            row.update(costs=trace.get("costs"), task_wall_time=trace.get("wall_time"),
                       candidates=len(trace.get("candidates_offered", [])),
                       selected=trace.get("selected"), stopped=trace.get("stopped"),
                       reused=trace.get("reused", False),
                       acquired_again=trace.get("acquired_again"),
                       answers=trace.get("answers"),
                       all_checks_agree=trace.get("all_checks_agree"),
                       reuse=payload["reuse"])
        results.append(row)
        (output / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"finished {run['id']}: exit={returncode}, {row['process_wall_time']}s", flush=True)
    return 0 if len(results) == len(plan) and all(r.get("returncode") == 0 and
                                                r.get("sources_unchanged") for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
