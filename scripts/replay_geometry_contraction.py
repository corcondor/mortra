"""Independent contract/source/proof replay plus summary and visibility audit."""
from pathlib import Path
import argparse
import json
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.replay_geometry_contracts import replay as replay_contracts
from math_os_prototype.geometry_contraction import replay_summary, source_interfaces
from math_os_prototype.theory_geometry_acquisition import independent_replay


def audit_scientific_gate(comparisons):
    """Recompute the frozen gate from task rows, not the producer's verdict.

    This preserves the original conservative gate. Attribution is reported
    separately: a primitive-baseline loss is not automatically a hiding loss.
    """
    required = ("primitive_only", "syntactic_macro", "certified_morphism",
                "summarized", "hiding_only", "ablation")
    if any(label not in comparisons for label in required):
        raise ValueError("missing comparison condition")
    tasks = [r["task"]["id"] for r in comparisons["summarized"]]
    if not tasks or len(set(tasks)) != len(tasks) or any(
            [r["task"]["id"] for r in comparisons[label]] != tasks for label in required):
        raise ValueError("comparison task sequences differ or are empty")
    def cost(label, key):
        return sum(r["costs"].get(key, 0) for r in comparisons[label])
    def cheaper(left, right):
        return left["solved"] and (not right["solved"] or any(
            left["costs"].get(k, 0) < right["costs"].get(k, 0)
            for k in ("candidate_expansions", "goal_prover_calls", "max_state_object_count")))
    d, b, e, a = [comparisons[label] for label in ("summarized", "syntactic_macro", "hiding_only", "ablation")]
    losses = {label: [r["task"]["id"] for r, s in zip(comparisons[label], d, strict=True)
                     if r["solved"] and not s["solved"]] for label in required[:3]+("hiding_only",)}
    hiding_losses = [r["task"]["id"] for r, s in zip(b, e, strict=True) if r["solved"] and not s["solved"]]
    criteria = {
        "acquired_morphism_used": any(r["goal_acquired_calls"] for r in d),
        "no_lost_baseline_solve": not any(losses.values()),
        "no_false_proofs": not any(r["false_proofs"] for rows in comparisons.values() for r in rows),
        "internal_objects_hidden": cost("summarized", "hidden_objects") > 0,
        "no_hiding_only_lost_exposed_solve": not hiding_losses,
        "summarized_aggregate_search_lower": any(cost("summarized", k) < cost("syntactic_macro", k)
            for k in ("candidate_expansions", "goal_prover_calls")),
        "hiding_only_aggregate_search_lower": any(cost("hiding_only", k) < cost("syntactic_macro", k)
            for k in ("candidate_expansions", "goal_prover_calls")),
        "used_morphism_paired_exposed_gain": any(cheaper(s, r) and s["goal_acquired_calls"] for s, r in zip(d, b, strict=True)),
        "hiding_only_paired_exposed_gain": any(cheaper(s, r) for s, r in zip(e, b, strict=True)),
        "used_morphism_ablation_gain": any(cheaper(s, r) for s, r in zip(d, a, strict=True)),
    }
    refinement = {label: {k: cost(label, k) for k in
        ("offered_refinements", "refinement_calls", "refinement_primitive_executions", "refinement_seconds")}
        for label in ("summarized", "hiding_only", "ablation")}
    return {"passed": all(criteria.values()), "criteria": criteria,
            "failed_criteria": [k for k, ok in criteria.items() if not ok],
            "lost_solved_tasks_by_baseline": losses, "hiding_only_lost_exposed_tasks": hiding_losses,
            "paid_refinement_costs": refinement,
            "attribution_limit": "D/E changes filtering and effect ordering together; E/B changes hiding with paid refinement"}


def replay(folder):
    started = time.perf_counter()
    result = replay_contracts(folder)
    def read(name):
        return json.loads((folder/name).read_text(encoding="utf-8"))
    archive, learned, comparisons = read("frozen-library.json"), read("acquisition.json"), read("comparisons.json")
    by_id = {h["id"]: h for h in archive}
    summaries = []
    for h in archive:
        ok, cost = replay_summary(h, h["summary"])
        boundary, sources = source_interfaces(h, learned["corpus"])
        ok = ok and sources == h["interface_sources"] and boundary == sorted(h["summary"]["interface"]["boundary_outputs"])
        summaries.append({"id": h["summary"]["id"], "passed": ok, "cost": cost})
        if not ok:
            result["errors"].append("summary/source interface mismatch: "+h["id"])
    visibility_checks = 0
    for label in ("summarized", "hiding_only", "ablation"):
        for row in comparisons[label]:
            for event in row["events"]:
                if event["event"] != "apply":
                    continue
                action = event["action"]
                if action["family"] not in by_id:
                    continue
                h = by_id[action["family"]]
                interface = h["summary"]["interface"]
                if len(action["outputs"]) != len(interface["public_outputs"]):
                    result["errors"].append("private point exposed by summarized apply")
                if interface["private_locals"]:
                    d = action.get("contraction", {})
                    if (d.get("summary_id") != h["summary"]["id"] or d.get("private_locals") != interface["private_locals"]
                            or set(d.get("local_mapping", {})) != set(interface["public_outputs"])):
                        result["errors"].append("invalid contracted action interface")
                visibility_checks += 1
    regression = [independent_replay(r) for r in read("regression.json")]
    if any(r["checked"] and not r["passed"] for r in regression):
        result["errors"].append("regression false proof")
    gate = audit_scientific_gate(comparisons)
    for name in ("verification.json", "result.json"):
        if gate["passed"] != read(name)["scientific_gate_passed"]:
            result["errors"].append("scientific gate mismatch: "+name)
    for rows in comparisons.values():
        for row in rows:
            if row.get("measurement_version", 1) < 2:
                continue
            started_calls = row["planner_applications_started"]
            completed = row["planner_applications_completed"]
            if (row["states_explored"] != 1+completed or not 1 <= row["states_retained"] <= 1+completed
                    or started_calls-completed != row["planner_applications_interrupted"]
                    or not 0 <= started_calls-completed <= 1):
                result["errors"].append("inconsistent surviving planner counters: "+row["task"]["id"])
    result.update(passed=not result["errors"], summaries=summaries, visibility_checks=visibility_checks,
                  regression_replays=regression, total_seconds=time.perf_counter()-started,
                  gate_audit=gate, scientific_gate_passed=gate["passed"], minimal_chain_passed=gate["passed"])
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-scientific-pass", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("refuse to replace previous replay")
    result = replay(args.run)
    args.output.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] and (not args.require_scientific_pass or result["scientific_gate_passed"]) else 1)
