"""Read the run's artifacts and answer the questions the experiment was run to answer.

    what the unseen tasks cost before and after learning;
    one posed task in full: the statement, the construction that was hidden, and
    the construction the solver found;
    each acquired operation: its body, the guarantees it carries, and where it
    was used again;
    whether anything acquired later was built on something acquired earlier;
    what improved, what did not, and what dominated the cost.

    python scripts/analyse_geometry_self_improvement.py --run reports/geometry-self-improvement
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path


def load(run, name):
    path = run/name
    return json.loads(path.read_text()) if path.exists() else None


def is_subsequence(needle, haystack):
    if not needle:
        return False
    position = 0
    for item in haystack:
        if item == needle[position]:
            position += 1
            if position == len(needle):
                return True
    return False


def statement(task):
    points = ", ".join(f"{name}({x}, {y})" for name, (x, y) in
                       ((n, v) for n, v in task["points"].items()))
    goals = " and ".join(f"{goal['predicate']}({', '.join(goal['points'])})" for goal in task["goals"])
    return f"given {points}, find u with {goals}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    arguments = parser.parse_args()
    run = Path(arguments.run)
    result = load(run, "result.json")
    stages = load(run, "stages.json")
    tasks = load(run, "tasks.json")
    rows = load(run, "final-rows.json")
    middle = load(run, "after-stage-1.json")
    analysis = {}

    # 1. unseen tasks before and after
    unseen = {"A (start library, start policy)": result["final"]["A"],
              "B (learned library, start policy)": result["final"]["B"],
              "C (learned library, learned policy)": result["final"]["C"]}
    if middle:
        unseen["after stage 1 (stage-1 library, start policy)"] = middle["final_after_stage_1"]
    analysis["unseen"] = {name: {k: summary[k] for k in
                                 ("tasks", "solved", "total_search_states", "total_applications",
                                  "total_checking", "total_wall_seconds",
                                  "solved_with_an_acquired_operation")}
                          for name, summary in unseen.items()}
    analysis["unseen_needing_composition"] = result.get("final_needing_composition")

    # 2. one task in full
    examples = []
    for entry, row in zip(tasks["final"], rows["C"], strict=True):
        if row["measurements"]["solved"] and not entry.get("one_step_reachable"):
            examples.append({
                "statement": statement(entry["task"]),
                "task": entry["task"],
                "hidden_construction": entry["hidden"]["steps"],
                "hidden_answer": entry["hidden"]["solution"],
                "candidates_the_conditions_allow": entry["hidden"]["candidate_count"],
                "solver_construction_families": row["solution_families"],
                "solver_used_acquired": row["used_acquired_operations"],
                "cost": row["measurements"]})
        if len(examples) >= 3:
            break
    analysis["examples"] = examples

    # 3. acquired operations and where they were used again
    acquired = result["states"]["after_stage_2"]["library"]["acquired_operations"]
    reuse = Counter()
    for condition, condition_rows in rows.items():
        for row in condition_rows:
            for used in row["used_acquired_operations"]:
                reuse[(condition, used["index"])] += 1
    bodies = {}
    for stage in ("stage_1", "stage_2"):
        for item in stages[stage]["acquisitions"]:
            bodies[item["index"]] = {"body": item["body"], "declared": item["declared"],
                                     "patterns": item["patterns"]}
    analysis["acquired_operations"] = [
        {"index": operation["index"], "steps": operation["steps"],
         "guarantees": operation["patterns"], "from_task": operation["source"],
         "body": bodies.get(operation["index"], {}).get("body"),
         "reused_on_unseen_tasks": {condition: reuse[(condition, operation["index"])]
                                    for condition in rows}}
        for operation in acquired]

    # 4. a second generation?
    known, generations = [], []
    for stage in ("stage_1", "stage_2"):
        for record in stages[stage]["rows"]:
            families = record.get("solution_families") or []
            built_on = [entry for entry in known if is_subsequence(entry["families"], families)]
            acquisition = record.get("acquisition") or {}
            if acquisition.get("registered"):
                body = acquisition["body"]
                generations.append({"stage": stage, "index": acquisition["index"],
                                    "families": [step["prim"] for step in body["steps"]],
                                    "built_on_earlier_acquisitions": [e["index"] for e in built_on]})
                known.append({"index": acquisition["index"],
                              "families": [step["prim"] for step in body["steps"]]})
    analysis["generations"] = {
        "acquired": generations,
        "second_generation": [g for g in generations if g["built_on_earlier_acquisitions"]]}

    # 5-6. what did not improve, and what dominated
    failures = Counter()
    for stage in ("stage_1", "stage_2"):
        failures.update(stages[stage]["failures"])
    unsolved = [row for row in rows["C"] if not row["measurements"]["solved"]]
    analysis["did_not_improve"] = {
        "tasks_unsolved_in_every_condition": sum(
            1 for a, b, c in zip(rows["A"], rows["B"], rows["C"], strict=True)
            if not (a["measurements"]["solved"] or b["measurements"]["solved"] or c["measurements"]["solved"])),
        "policy_changed_nothing": result["final"]["B"] == result["final"]["C"],
        "stop_reasons_when_unsolved": dict(Counter(row["measurements"]["stop_reason"] for row in unsolved)),
        "failure_counts": dict(failures)}
    analysis["bottleneck"] = {
        "acquisition_refusals": {key: value for key, value in failures.items() if key.startswith("acquisition")},
        "registration_duplicates": {key: value for key, value in failures.items()
                                    if key.startswith("registration")},
        "learning_cost": result["learning_cost"],
        "posing_rejections": result["pools"]["train"]["rejections"]}
    (run/"analysis.json").write_text(json.dumps(analysis, indent=1, default=str)+"\n", encoding="utf-8")
    print(json.dumps({k: analysis[k] for k in ("unseen", "unseen_needing_composition", "generations",
                                               "did_not_improve")}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
