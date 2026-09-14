"""Read completed JSON evidence only; never execute or choose a search task."""
import argparse
import hashlib
import json
from pathlib import Path


def depth(term):
    return 0 if term["op"] == "var" else 1 + max(map(depth, term["args"]))


def macro_depth(row):
    if not row["solved"]:
        return None
    levels = dict.fromkeys(row["task"]["points"], 0)
    for action in row["proof_actions"]:
        level = 1 + max(levels[n] for n in action["inputs"])
        levels.update(dict.fromkeys(action["outputs"], level))
    return levels[row["proof"]["point"]]


def summarize(folder):
    def read(name):
        return json.loads((folder/name).read_text(encoding="utf-8"))
    verification, comparisons = read("verification.json"), read("comparisons.json")
    training, acquisition, library = read("training.json"), read("acquisition.json"), read("frozen-library.json")
    rows, paired = {}, []
    for label, results in comparisons.items():
        rows[label] = [{"task": r["task"]["id"], "solved": r["solved"],
            "stop_reason": r["stop_reason"], "costs": r["costs"],
            "states_explored": r["states_explored"], "states_retained": r["states_retained"],
            "active_final_points": len(r["state"]["points"]) if r["solved"] else None,
            "macro_action_count_in_proof": r["macro_proof_length"],
            "macro_dependency_depth": macro_depth(r),
            "expanded_primitive_dag_nodes": r["expanded_primitive_proof_depth"],
            "expanded_primitive_dependency_depth": depth(r["proof"]["term"]) if r["solved"] else None,
            "acquired_calls_in_proof": r["goal_acquired_calls"],
            "wall_seconds": r["wall_seconds"], "independent_replay": r["independent_replay"]}
            for r in results]
    h_ids = {h["id"] for h in library}
    for exposed, hidden in zip(comparisons["syntactic_macro"], comparisons["hiding_only"], strict=True):
        def examples(row):
            found = {}
            for i, e in enumerate(row["events"]):
                if e["event"] != "apply" or e["action"]["family"] not in h_ids:
                    continue
                action = e["action"]
                if not set(action["inputs"]) <= set(row["task"]["points"]):
                    continue
                later = [{"event_index": j, "family": t["family"],
                    "active_points": t["active_points"], "offered": len(t["candidates"])}
                    for j, t in enumerate(row["events"])
                    if t["event"] == "enumerate" and t["parent"] == e["child"]]
                if later:
                    found.setdefault((action["family"], tuple(action["inputs"])),
                        {"apply_event_index": i, "action": action, "child": e["child"], "later": later})
            return found
        left, right = examples(exposed), examples(hidden)
        common = [k for k in left if k in right]
        if common:
            key = common[0]
            paired.append({"task": exposed["task"]["id"], "exposed": left[key], "hidden": right[key]})
    timed_out = {label: [r["task"]["id"] for r in rs if r["states_explored"] is None]
                 for label, rs in comparisons.items()}
    # Files are only read. Byte hashes make the post-run interpretation auditable.
    hashes = {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(folder.rglob("*")) if p.is_file()}
    return {"schema": "mortra.geometry-contraction-readonly-analysis.v1",
        "code_sha": verification["sha"], "workflow_run_id": verification["workflow_run_id"],
        "plan_sha256": verification["plan_sha256"], "scientific_gate_passed": verification["scientific_gate_passed"],
        "summary": verification["summary"], "per_task": rows, "paired_root_applications": paired,
        "incomplete_state_counts": timed_out,
        "acquisition": {"training_solved": sum(r["solved"] for r in training), "training_total": len(training),
            "training_search_seconds": sum(r["wall_seconds"] for r in training),
            "training_replay_seconds": sum(r["independent_replay"].get("seconds", 0) for r in training),
            "acquisition_seconds": acquisition["wall_seconds"],
            "pairs_tried": acquisition["proposals"]["pairs_tried"],
            "definition_count": len(library),
            "compression_active_count": len(acquisition["compression_active"]),
            "contracts": [{"id": h["id"], "source_proofs": len(h["source_proof_traces"]),
                "body": h["body"], "summary": h["summary"], "compilation_cost": h["summary_cost"]} for h in library]},
        "artifact_file_sha256": hashes,
        "limitations": ["No new search or task selection in this post-run observer.",
            "Means weight goal-checked states. Null state counts remain unknown, not zero.",
            "Dependency depths are derived here from saved programs; the runtime depth field counted DAG nodes.",
            "Inclusive timers overlap; do not sum them into a total.",
            "Timeout attempt counts are machine-dependent; report paired solved tasks separately."]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.run.resolve() in args.output.resolve().parents:
        parser.error("use a new output outside the observed run")
    result = summarize(args.run)
    args.output.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("code_sha", "workflow_run_id", "scientific_gate_passed")}, indent=2))
