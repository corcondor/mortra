"""Fixed-stream prequential experiment, then isolated external evaluation.

The common stream is produced by the existing normal Theory entry. Four masks
share one certified archive at each prefix. This is NOT four adaptive curricula.
"""
from pathlib import Path
import argparse
import json
import os
import platform
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.run_theory_formation import source_seal, write
from scripts.verify_theory_tasks import freeze
from scripts.verify_theory_semantic_edit import summarize
from math_os_prototype.theory_formation import Theory
from math_os_prototype.representation_progress import digest, encoding
from math_os_prototype.temporal_utility import POLICIES


def read(p):
    return json.loads(p.read_text(encoding="utf-8"))


def audit(state):
    t = state["dsl"]["temporal"]
    future = t["future_evidence"]
    return {
        "experience_count": t["sequence"], "producer_experience_count": state["dsl"]["experience_count"],
        "archive_size": len(t["entries"]), "active_size": len(t["active"]),
        "future_samples": len(future), "selections": len(t["selections"]),
        "future_strictly_later": all(r["sequence"] > r["acquired_after"] for r in future),
        "acquisition_sources_excluded": all(r["source"] not in t["entries"][r["operation"]]["acquisition_sample"] for r in future),
        "no_lookahead": all(r["evidence_through"] <= r["acquired_through"] for r in t["selections"]),
        "active_bounded": all(len(r["after"]) <= t["options"]["active_capacity"] for r in t["selections"]),
        "all_counterfactuals_exact_or_budget_refused": all(
            r["with"]["solved"] or r["with"]["stop"] in {"measurement_work_budget", "work_budget_exhausted", "bounded_search_exhausted"}
            for r in future),
        "stream_digest": t["stream_digest"], "costs": t["costs"],
        "storage_bytes": {"temporal_state": len(encoding(t)), "active_sample": len(encoding(state["dsl"]["corpus"])),
                          "execution_history": len(encoding(state["dsl"]["executions"])),
                          "acquisition_provenance": len(encoding(state["dsl"]["acquisition_evidence"]))},
        "exhausted": t["exhausted"], "producer_stop": state["stop_reason"]}


def render_report(result, state):
    t = state["dsl"]["temporal"]
    lines = ["# Temporal future utility", "",
        "Each row processes the SAME naturally produced window. A=all, B=acquisition-only, C=temporal, D=initial.",
        "C-fixed uses the active set frozen BEFORE that window. Costs do not include shared acquisition; those are separate below.",
        "No zero cost is assigned to unmeasured mathematical semantic depth. Call depth is syntax only.", "",
        "| Prior experiences | Next window | Policy | Correct | Program bits | Normal work | Seconds | Reuse | Archive | Active | Call depth |",
        "| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for w in t["windows"].values():
        for p, c in w["conditions"].items():
            lines.append(f"| {w['start']} | {w['start']+1}..{w['end']} | {p} | {c['solved']}/{c['experiences']} | {c['bits']} | {sum(c['costs'].values())} | {c['seconds']:.3f} | {c['reuse']} | {w['archive_at_end']} | {w['active_at_end']} | {w['definition_call_depth']} |")
    lines += ["", "## Search on internal future observations", "",
              "Values, not witness programs, are supplied to the existing planner. Proof calls and independent replay remain separately recorded.", "",
              "| Experience | Policy | Solved | Candidates | Normal work | Replay work | Seconds |",
              "| ---: | --- | --- | ---: | ---: | ---: | ---: |"]
    for s in t["searches"]:
        for p, r in s["conditions"].items():
            lines.append(f"| {s['sequence']} | {p} | {r['solved']} | {r['states_explored']} | {r['normal_work_used']} | {r['independent_replay_work']['used']} | {r['seconds']:.3f} |")
        if s["ablation"]:
            r = s["ablation"]["result"]
            lines.append(f"| {s['sequence']} | C without {s['ablation']['disabled']} | {r['solved']} | {r['states_explored']} | {r['normal_work_used']} | {r['independent_replay_work']['used']} | {r['seconds']:.3f} |")
    lines += ["", "## Accounting and external results", "", "```json", json.dumps(result, indent=2), "```", "",
        "Library bits include archived dependencies, once per window, and are in temporal.json. Window gains are not accumulated across changing corpora.",
        "Finite-frame scope does not imply collision legality or use of panel-structure definitions. No new mathematical abstraction algorithm claim is made."]
    return "\n".join(lines)+"\n"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--plan", type=Path, default=ROOT/"configs/theory-temporal-utility.json")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--development", action="store_true")
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    plan = read(a.plan)
    config = read(ROOT/plan["config"])
    config["budget"].update(plan["budget_overrides"])
    if a.development:
        plan["temporal"].update(experiences=600, window=100, search_interval=200, shadow_interval=32, acquisition_sample=8)
        plan["adaptive_producer_experiences"] = 100
        plan["regression_seeds"], plan["external_seeds"] = [], []
    write(a.output/"plan.json", plan)
    write(a.output/"config.json", config)
    write(a.output/"temporal-plan.json", plan["temporal"])
    targets = {}
    for cohort, seeds in [("regression", plan["regression_seeds"]), ("external", plan["external_seeds"])]:
        for seed in seeds:
            tasks, witnesses = freeze(config, seed)
            targets[f"{cohort}-{seed}"] = tasks
            write(a.output/f"{cohort}-{seed}-tasks.json", tasks)
            write(a.output/f"{cohort}-{seed}-evaluator-only.json", witnesses)
    sources = source_seal()
    result = {"schema": "mortra.temporal-experiment.v1", "sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "repository": subprocess.check_output(["git", "remote", "get-url", "origin"], cwd=ROOT, text=True).strip(),
        "ref": subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT, text=True).strip(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workflow_run_id": os.environ.get("GITHUB_RUN_ID"), "source_seal": sources, "plan_sha": digest(plan),
        "python": sys.version, "platform": platform.platform(), "commands": [], "process_seconds": {},
        "passed": False, "development": a.development, "errors": [], "external": {},
        "comparison": "same exogenous normal stream; common causal archive; four operation masks, not four curricula"}
    (a.output/"dependencies.txt").write_text(subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True), encoding="utf-8")
    began = time.perf_counter()
    def normal(name, temporal):
        write(a.output/f"{name}-plan.json", temporal)
        cmd = [sys.executable, str(ROOT/"scripts/run_theory_formation.py"), "--config", str((a.output/"config.json").resolve()),
               "--temporal-plan", str((a.output/f"{name}-plan.json").resolve()), "--semantic-edits", "--refresh-corpus", "--eligible-sources",
               "--output", str((a.output/name).resolve())]
        result["commands"].append(cmd)
        write(a.output/"verification.json", result)
        start = time.perf_counter()
        with (a.output/f"{name}.log").open("w", encoding="utf-8") as log:
            done = subprocess.run(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=plan["normal_limit_seconds"])
        result["process_seconds"][name] = time.perf_counter()-start
        if done.returncode:
            raise RuntimeError(f"{name} failed: inspect preserved log")
        return read(a.output/name/"state.json")
    try:
        state = normal("common-stream", plan["temporal"])
        result["internal"] = audit(state)
        write(a.output/"learning-curve.json", state["dsl"]["temporal"]["windows"])
        result["shared_acquisition_costs"] = state["costs"]
        result["total_internal_seconds"] = state["seconds"]
        # This second normal stream demonstrates that selection reaches the
        # ordinary generator. It is not paired against the common stream.
        adaptive = dict(plan["temporal"], producer_policy="temporal", experiences=plan["adaptive_producer_experiences"])
        other = normal("adaptive-producer", adaptive)
        result["adaptive_producer"] = audit(other)
        result["adaptive_generator_events"] = sum(e["kind"] == "dsl_active_generation" for e in other["events"])
        # Evaluation starts only now; results never enter record(), sync(), or selector.
        e = Theory(config, **state["flags"], state=state)
        v = e.vocabulary
        before = digest(e.state)
        masks = {policy: v.temporal.choose(policy) for policy in POLICIES}
        write(a.output/"external-frozen-masks.json", masks)
        for cohort, tasks in targets.items():
            for policy in POLICIES:
                rows = []
                start = time.perf_counter()
                for task in tasks:
                    if time.perf_counter()-start > plan["query_limit_seconds"]:
                        raise RuntimeError("external cohort time budget")
                    rows.append(v.solve_observation(task, operation_keys=masks[policy], execution_mode="edited"))
                    write(a.output/f"{cohort}-{policy}.json", rows)
                result["external"][f"{cohort}-{policy}"] = summarize(rows)
                print(json.dumps({"cohort": cohort, "policy": policy, "solved": sum(r["solved"] for r in rows)}), flush=True)
        result["external_did_not_update_state"] = digest(e.state) == before
        result["sources_unchanged"] = sources == source_seal()
        checks = ("future_strictly_later", "acquisition_sources_excluded", "no_lookahead", "active_bounded", "all_counterfactuals_exact_or_budget_refused")
        result["passed"] = (all(result["internal"][k] for k in checks) and result["sources_unchanged"] and result["external_did_not_update_state"]
                            and result["internal"]["experience_count"] == plan["temporal"]["experiences"]
                            and result["adaptive_generator_events"] > 0)
    except Exception:
        result["errors"].append(traceback.format_exc())
    result["wall_seconds"] = time.perf_counter()-began
    if "state" in locals():
        (a.output/"report.md").write_text(render_report(result, state), encoding="utf-8")
    result["artifact_sha256"] = {p.relative_to(a.output).as_posix(): __import__("hashlib").sha256(p.read_bytes()).hexdigest()
                                for p in sorted(a.output.rglob("*")) if p.is_file() and p.name != "verification.json"}
    write(a.output/"verification.json", result)
    print(json.dumps({k: v for k, v in result.items() if k not in {"source_seal", "shared_acquisition_costs"}}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
