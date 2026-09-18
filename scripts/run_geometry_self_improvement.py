"""The self-improvement cycle on posed geometry tasks, run end to end and measured.

    pose -> screen -> solve -> certify -> register -> choose the next tasks -> measure

Three states of the system are kept: before learning, after the first stage, and
after the second. The final tasks are posed and screened before any learning
happens, are never used to choose a policy, and share no construction signature
with the training or validation tasks. They are then answered three times:

    A  the starting library with the starting policy
    B  the learned library with the starting policy
    C  the learned library with the learned policy

so that what the operations did and what the policy did can be told apart.

    python scripts/run_geometry_self_improvement.py --output reports/geometry-self-improvement
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import platform
import random
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from math_os_prototype import geometry_acquired_library as acqlib
from math_os_prototype import geometry_self_improvement as loop
from math_os_prototype import geometry_self_posing as posing
from scripts.run_relational_geometry_eval import loaded_project_modules


def write(output, name, value):
    (output/name).write_text(json.dumps(value, indent=1, default=str)+"\n", encoding="utf-8")


def say(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def probe_sets(train_entries, seed, *, library, policy, count=4):
    """Three contrasts: the same structure moved, a similar structure with other relations,
    and an unseen recombination that is deeper than anything trained on."""
    rng = random.Random(seed)
    renamed = []
    for entry in train_entries:
        if len(renamed) >= count:
            break
        moved = posing.rename_and_move(entry, rng)
        if moved is not None:
            moved["difficulty"] = entry.get("difficulty")
            renamed.append(moved)
    trained_families = {tuple(entry["hidden"]["families"]) for entry in train_entries}
    trained_signatures = {entry["signature"] for entry in train_entries}
    similar, deeper = [], []
    batch = posing.pose_many(seed+1, count*4, depth=2, goal_count=3, attempts=2500, exclude=trained_signatures)
    for record in batch["posed"]:
        if len(similar) >= count:
            break
        if tuple(record["hidden"]["families"]) in trained_families:
            record = dict(record, probe="same_construction_other_relations", difficulty="probe")
            similar.append(record)
    batch3 = posing.pose_many(seed+2, count*3, depth=3, goal_count=3, attempts=2500,
                              exclude=trained_signatures | {r["signature"] for r in similar})
    for record in batch3["posed"]:
        if len(deeper) >= count:
            break
        record = dict(record, probe="unseen_recombination", difficulty="probe")
        deeper.append(record)
    for record in renamed:
        record["probe"] = "renamed_and_moved"
    return {"renamed_and_moved": renamed, "same_construction_other_relations": similar,
            "unseen_recombination": deeper}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--train", type=int, default=24)
    parser.add_argument("--validation", type=int, default=12)
    parser.add_argument("--final", type=int, default=24)
    parser.add_argument("--applications", type=int, default=40)
    parser.add_argument("--seed", type=int, default=20260918)
    parser.add_argument("--goals", type=int, default=3)
    parser.add_argument("--enumerated-library", dest="enumerated", action="store_true", default=True,
                        help="start from the task-independent enumeration the repository already builds")
    parser.add_argument("--empty-library", dest="enumerated", action="store_false")
    arguments = parser.parse_args()
    output = Path(arguments.output)
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    report = {"environment": {
        "sha": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip(),
        "python": sys.version, "platform": platform.platform(),
        "modules_before": loaded_project_modules()},
        "protocol": {
            "posing": "a construction is composed and executed exactly, the relations that hold are "
                      "decided exactly, and the construction and its intermediate points are hidden",
            "carried_between_tasks": ["the library of certified operations", "the policy"],
            "not_carried": ["coordinates", "solutions", "the per-task solver state", "any cache of answers"],
            "conditions": {"A": "starting library, starting policy",
                           "B": "learned library, starting policy",
                           "C": "learned library, learned policy"},
            "applications_per_task": arguments.applications}}

    base = None
    if arguments.enumerated:
        from collections import Counter as _Counter
        from math_os_prototype import geometry_relational_library as lib
        say("building the task-independent enumeration the system starts with")
        statistics = _Counter()
        began = time.perf_counter()
        base = lib.acquire_index(max_depth=2, stats=statistics)
        report["starting_vocabulary"] = {
            "programs": len(base.programs), "patterns": len(base.membership),
            "seconds": time.perf_counter()-began, "stats": dict(statistics),
            "note": "enumerated without reading any task; the same starting vocabulary is given to "
                    "every condition, so what is compared is only what the run acquired"}
        say(f"enumerated {len(base.programs)} programs in {report['starting_vocabulary']['seconds']:.0f}s")
    start_library = acqlib.AcquiredLibrary(base)
    start_policy = dict(loop.START_POLICY)

    # -- pools, all posed and screened before any learning ------------------
    say("posing and screening the training pool")
    train_pool = loop.build_pool(arguments.seed, arguments.train+10, depth=2, goal_count=arguments.goals,
                                 library=start_library, policy=start_policy, attempts=4000)
    train_entries = loop.curriculum(train_pool["pool"], easy=6, boundary=12, hard=6)[:arguments.train]
    used = {entry["signature"] for entry in train_entries}
    say(f"training tasks: {len(train_entries)} {dict(Counter(e['difficulty'] for e in train_entries))}")

    say("posing and screening the validation pool")
    validation_pool = loop.build_pool(arguments.seed+101, arguments.validation+6, depth=2, goal_count=arguments.goals,
                                      library=start_library, policy=start_policy, exclude=used, attempts=4000)
    validation_entries = loop.curriculum(validation_pool["pool"], easy=3, boundary=6, hard=3)[:arguments.validation]
    used |= {entry["signature"] for entry in validation_entries}
    say(f"validation tasks: {len(validation_entries)}")

    say("posing and screening the final pool")
    final_pool = loop.build_pool(arguments.seed+202, arguments.final+10, depth=2, goal_count=arguments.goals,
                                 library=start_library, policy=start_policy, exclude=used, attempts=5000)
    final_entries = loop.curriculum(final_pool["pool"], easy=8, boundary=10, hard=6)[:arguments.final]
    used |= {entry["signature"] for entry in final_entries}
    say(f"final tasks: {len(final_entries)} {dict(Counter(e['difficulty'] for e in final_entries))}")

    def composition_split(entries):
        return {"needs_composition": sum(1 for e in entries if not e.get("one_step_reachable")),
                "one_step": sum(1 for e in entries if e.get("one_step_reachable"))}

    report["pools"] = {
        "train": {"count": len(train_entries), "difficulty": dict(Counter(e["difficulty"] for e in train_entries)),
                  "composition": composition_split(train_entries), "rejections": train_pool["rejections"]},
        "validation": {"count": len(validation_entries),
                       "difficulty": dict(Counter(e["difficulty"] for e in validation_entries)),
                       "composition": composition_split(validation_entries)},
        "final": {"count": len(final_entries), "difficulty": dict(Counter(e["difficulty"] for e in final_entries)),
                  "composition": composition_split(final_entries), "rejections": final_pool["rejections"]},
        "signature_overlap": sorted({e["signature"] for e in train_entries}
                                    & {e["signature"] for e in final_entries})}
    write(output, "tasks.json", {"train": train_entries, "validation": validation_entries,
                                 "final": final_entries})

    say("probes")
    probes = probe_sets(train_entries, arguments.seed+303, library=start_library, policy=start_policy)
    report["probes"] = {name: len(entries) for name, entries in probes.items()}
    write(output, "probes.json", probes)

    # -- stage 0: the starting state on the final tasks ---------------------
    say("condition A: starting library, starting policy, on the final tasks")
    condition_a = loop.evaluate(final_entries, library=start_library, policy=start_policy,
                                applications=arguments.applications, note="A: start library, start policy")
    say(f"A solved {condition_a['summary']['solved']}/{len(final_entries)}")
    report["states"] = {"start": {"library": start_library.state(), "policy": start_policy}}

    # -- stage 1 ------------------------------------------------------------
    library = acqlib.AcquiredLibrary(base)
    policy = dict(start_policy)
    stage_one = loop.learn_stage(train_entries[:len(train_entries)//2], library=library, policy=policy,
                                 applications=arguments.applications)
    say(f"stage 1: solved {stage_one['solved']}/{stage_one['tasks']}, "
        f"acquired {len(stage_one['acquisitions'])}, {stage_one['seconds']:.0f}s")
    candidates = loop.propose_policies(stage_one["rows"], policy)[:3]
    chosen_one = loop.choose_policy(candidates, validation_entries, library=library,
                                    applications=arguments.applications, current=policy)
    policy_one = chosen_one["policy"]
    say(f"stage 1 policy: {chosen_one['chosen']}")
    report["states"]["after_stage_1"] = {"library": library.state(), "policy": policy_one,
                                         "policy_choice": chosen_one["trials"]}

    # -- stage 2 ------------------------------------------------------------
    stage_two = loop.learn_stage(train_entries[len(train_entries)//2:], library=library, policy=policy_one,
                                 applications=arguments.applications)
    say(f"stage 2: solved {stage_two['solved']}/{stage_two['tasks']}, "
        f"acquired {len(stage_two['acquisitions'])}, {stage_two['seconds']:.0f}s")
    candidates_two = loop.propose_policies(stage_one["rows"]+stage_two["rows"], policy_one)[:3]
    chosen_two = loop.choose_policy(candidates_two, validation_entries, library=library,
                                    applications=arguments.applications, current=policy_one)
    policy_two = chosen_two["policy"]
    say(f"stage 2 policy: {chosen_two['chosen']}")
    report["states"]["after_stage_2"] = {"library": library.state(), "policy": policy_two,
                                         "policy_choice": chosen_two["trials"]}
    report["stages"] = {"stage_1": {k: stage_one[k] for k in ("solved", "tasks", "failures", "seconds",
                                                              "acquisition_seconds")},
                        "stage_2": {k: stage_two[k] for k in ("solved", "tasks", "failures", "seconds",
                                                              "acquisition_seconds")}}
    report["learning_cost"] = {
        "seconds": stage_one["seconds"]+stage_two["seconds"],
        "acquisition_seconds": stage_one["acquisition_seconds"]+stage_two["acquisition_seconds"],
        "policy_trial_seconds": sum(trial["summary"]["total_wall_seconds"]
                                    for trial in chosen_one["trials"]+chosen_two["trials"]),
        "training_tasks": len(train_entries), "validation_tasks": len(validation_entries)}
    write(output, "stages.json", {"stage_1": stage_one, "stage_2": stage_two,
                                  "policy_choice_1": chosen_one, "policy_choice_2": chosen_two})

    # -- final comparison ---------------------------------------------------
    say("condition B: learned library, starting policy")
    condition_b = loop.evaluate(final_entries, library=library, policy=start_policy,
                                applications=arguments.applications, note="B: learned library, start policy")
    say(f"B solved {condition_b['summary']['solved']}/{len(final_entries)}")
    say("condition C: learned library, learned policy")
    condition_c = loop.evaluate(final_entries, library=library, policy=policy_two,
                                applications=arguments.applications, note="C: learned library, learned policy")
    say(f"C solved {condition_c['summary']['solved']}/{len(final_entries)}")
    def restrict(result, keep):
        rows = [row for row, entry in zip(result["rows"], final_entries, strict=True) if keep(entry)]
        return {"tasks": len(rows), "solved": sum(1 for r in rows if r["measurements"]["solved"]),
                "total_search_states": sum(r["measurements"]["search_states"] for r in rows),
                "total_applications": sum(r["measurements"]["primitive_applications"] for r in rows),
                "total_checking": sum(r["measurements"]["checking"] for r in rows),
                "solved_with_an_acquired_operation": sum(1 for r in rows if r["used_acquired_operations"])}

    needs = lambda entry: not entry.get("one_step_reachable")
    report["final"] = {"A": condition_a["summary"], "B": condition_b["summary"], "C": condition_c["summary"]}
    report["final_needing_composition"] = {"A": restrict(condition_a, needs), "B": restrict(condition_b, needs),
                                           "C": restrict(condition_c, needs)}
    write(output, "final-rows.json", {"A": condition_a["rows"], "B": condition_b["rows"], "C": condition_c["rows"]})

    # -- probes under A and C ------------------------------------------------
    probe_results = {}
    for name, entries in probes.items():
        if not entries:
            continue
        say(f"probe {name}: {len(entries)} tasks")
        before = loop.evaluate(entries, library=start_library, policy=start_policy,
                               applications=arguments.applications, note=f"{name} before")
        after = loop.evaluate(entries, library=library, policy=policy_two,
                              applications=arguments.applications, note=f"{name} after")
        probe_results[name] = {"before": before["summary"], "after": after["summary"],
                               "rows_after": after["rows"]}
    report["probe_results"] = {name: {"before": value["before"], "after": value["after"]}
                               for name, value in probe_results.items()}
    write(output, "probe-rows.json", probe_results)

    modules_after = loaded_project_modules()
    report["environment"]["modules_after"] = modules_after
    report["environment"]["sources_unchanged"] = all(
        modules_after.get(key) == value for key, value in report["environment"]["modules_before"].items())
    report["total_seconds"] = time.perf_counter()-started
    report["claims_not_made"] = [
        "the primitives, the predicates, the posing rules, the screening thresholds and the shape of the "
        "policy candidates are supplied by a person; what is learned is which operations to keep and "
        "which policy to use",
        "an acquired operation is inserted as its own primitive steps and every step is charged, so a "
        "reused operation is not free",
        "the final tasks were posed and screened before learning and were never used to choose a policy, "
        "but they were screened with the starting solver, so the mixture of difficulties is defined "
        "relative to that state",
        "a task is refused unless a rational non-input solution exists; nothing here decides real "
        "solvability",
        "no preregistered evaluation is affected"]
    write(output, "result.json", report)
    print(json.dumps({"final": report["final"], "stages": report["stages"],
                      "learning_cost": report["learning_cost"],
                      "probes": report["probe_results"],
                      "library": {"after_stage_2": report["states"]["after_stage_2"]["library"]["acquired"]}},
                     indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
