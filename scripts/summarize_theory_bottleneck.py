"""Read-only post-run aggregation. Imports no MORTRA mathematical machinery."""
import argparse
from collections import Counter
import json
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def rows(path):
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            yield json.loads(line)


def untimed(obj):
    if isinstance(obj, list):
        return [untimed(x) for x in obj]
    if isinstance(obj, dict):
        return {k: untimed(v) for k, v in obj.items()
                if "second" not in k and k not in {"elapsed", "runtime", "sha256", "config"}}
    return obj


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.artifact / "bottleneck-study"
    record = read(root / "verification.json")
    assert record["infrastructure_passed"] and record["sources_unchanged"]
    result = {"origin": "post-run analysis, never supplied to a learner",
              "mathematical_sha": record["mathematical_sha"],
              "control_sha": record["control_sha"], "run_id": record["run_id"],
              "arms": {}, "proof_budget_comparison": [], "blocked": {}, "scheduler": {}}
    states = {}
    for name, row in record["results"].items():
        directory = root / name
        state = read(directory / "normal/state.json")
        states[name] = state
        concepts = state["concepts"]
        gained = set(row["capability_change"]["newly_solved_heldout_tasks"])
        final = read(directory / "final-heldout.json")
        examples = []
        for task in final["rows"]:
            if task["task"] in gained:
                examples.append({"task": task["task"], "status": task["status"],
                    "prover_input_nodes": task["prover_input_ast_nodes"],
                    "exact_training_query_seen": task["exact_training_query_seen"],
                    "dependencies": {tid: state["theorems"][tid] for tid in task["dependencies"]}})
        result["arms"][name] = {
            "cycle": state["cycle"], "stop_reason": state["stop_reason"],
            "censored": row["diagnostic_censored"], "knowledge": row["knowledge_size"],
            "new_semantic_concepts": row["semantic_concepts_acquired"],
            "expanded_acquired_concepts": sum(cid in state["expanded"] for cid, c in concepts.items() if not c["seed"]),
            "representation_spaces": row["new_semantic_representations"],
            "concept_parent_depth": row["lineage"]["maximum_recorded_concept_depth"],
            "proof_depth": row["maximum_dependency_depth"], "heldout": row["heldout"],
            "any_exact_training_query_seen": any(t["exact_training_query_seen"] for t in final["rows"]),
            "costs": row["acquisition_costs"], "normal_wall_seconds": row["normal_wall_seconds"],
            "engine_action_seconds": row["training_seconds"],
            "complete_wall_seconds": row["complete_arm_wall_seconds"],
            "observer": row["observer"], "census": row["candidate_census"],
            "replay_checks": row["regression"]["checks"], "ablations": row["ablations"],
            "examples_of_newly_solved": examples}
        for snapshot in read(directory / "trajectory.json"):
            if snapshot["snapshot"].startswith("proof-"):
                result["proof_budget_comparison"].append({
                    "arm": name, "snapshot": snapshot["snapshot"], "cycle": snapshot["cycle"],
                    "heldout": snapshot["heldout"], "costs": snapshot["acquisition_costs"],
                    "engine_action_seconds": snapshot["training_seconds"]})
        trace_dir = directory / "blocked-concepts"
        if trace_dir.exists():
            counts, sizes, excesses, types = Counter(), Counter(), Counter(), Counter()
            for file in trace_dir.glob("C-*.json"):
                trace = read(file)
                counts["parents"] += 1
                for candidate in trace["candidates"]:
                    counts["generated"] += 1
                    within = candidate["reduced_size"] <= trace["expansion"]["term_cap"]
                    duplicate = bool(candidate["semantic_duplicate_ids"])
                    counts["reduced_within_cap"] += within
                    counts["semantic_duplicate"] += duplicate
                    counts["within_cap_and_new_semantics"] += within and not duplicate
                    sizes[candidate["size"]] += 1
                    excesses[candidate["excess"]] += 1
                    types[candidate["type"]] += 1
            result["blocked"][name] = dict(counts, raw_sizes=dict(sizes), excesses=dict(excesses), types=dict(types))
    for domain in record["plan"]["domains"]:
        base = states[f"{domain}-size-{record['plan']['term_caps'][0]}"]
        base_semantics = {(c["type"], c["semantic_key"]) for c in base["concepts"].values()}
        for name, state in states.items():
            if not name.startswith(domain + "-"):
                continue
            semantic_set = {(c["type"], c["semantic_key"]) for c in state["concepts"].values()}
            arm = result["arms"][name]
            arm["additional_archived_semantics_vs_size9"] = len(semantic_set - base_semantics)
            arm["missing_archived_semantics_vs_size9"] = len(base_semantics - semantic_set)
            arm["additional_theorems_vs_size9"] = len(set(state["theorems"]) - set(base["theorems"]))
            arm["missing_theorems_vs_size9"] = len(set(base["theorems"]) - set(state["theorems"]))
    base_name = "theory-fold-frames-size-9"
    extended_name = "theory-fold-frames-extended"
    if extended_name in states:
        base, extended = states[base_name], states[extended_name]
        pending = set(base["active_concepts"]) - set(base["expanded"])
        for cid in sorted(pending):
            selections = list(rows(root / base_name / "scheduler" / (cid + ".jsonl")))
            expanded = [r for r in rows(root / extended_name / "observations/expansions.jsonl") if r["parent"] == cid]
            result["scheduler"][cid] = {"concept": base["concepts"][cid],
                "first_observation": selections[0], "last_observation": selections[-1],
                "observations": len(selections), "positions": dict(Counter(r["unexpanded_position"] for r in selections)),
                "chosen_kinds": dict(Counter(r["chosen"]["kind"] for r in selections)),
                "extension_expansion": expanded}
        mark = f"proof-{record['plan']['scheduler_proof_calls']}.json"
        a = read(root / base_name / "observations" / mark)
        b = read(root / extended_name / "observations" / mark)
        equal = untimed(a) == untimed(b)
        result["scheduler"]["equal_at_fixed_proof_budget_excluding_config_and_timings"] = equal
        assert equal, "cycle-only experiment changed its deterministic prefix"
    result["replay_checks"] = sum(r["regression"]["checks"] for r in record["results"].values())
    result["normal_wall_seconds"] = sum(r["normal_wall_seconds"] for r in record["results"].values())
    result["complete_arm_wall_seconds"] = sum(r["complete_arm_wall_seconds"] for r in record["results"].values())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"arms": len(result["arms"]), "replay_checks": result["replay_checks"],
                      "blocked": result["blocked"], "normal_wall_seconds": result["normal_wall_seconds"],
                      "complete_arm_wall_seconds": result["complete_arm_wall_seconds"]}, indent=2))


if __name__ == "__main__":
    main()
