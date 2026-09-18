"""Does an operation learned on the first half of a construction help on the whole of it?

A ladder is one construction posed twice: the base task asks for the point the
first steps produce, the top task asks for the point the whole construction
produces. Both are published the same way — the input configuration and the goal
relations — and neither reveals a construction.

The experiment trains only on base tasks and is evaluated on two sets it never
trained on:

    transfer        the tops of the ladders whose bases were trained on. The
                    acquired operation is, by construction, the block the top
                    task needs; whether the search finds and uses it is the
                    question.
    generalisation  the tops of ladders whose bases were never seen.

Every condition starts from the same vocabulary the repository already
enumerates, so what is compared is only what the run acquired:

    A  starting vocabulary, starting policy
    B  starting vocabulary and what was acquired, starting policy
    C  the same, with the learned policy

    python scripts/run_geometry_ladder_experiment.py --output reports/geometry-ladder
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
from math_os_prototype import geometry_relational_library as lib
from math_os_prototype import geometry_self_improvement as loop
from math_os_prototype import geometry_self_posing as posing
from scripts.run_relational_geometry_eval import loaded_project_modules


def say(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def write(output, name, value):
    (output/name).write_text(json.dumps(value, indent=1, default=str)+"\n", encoding="utf-8")


def screened(entries, *, library, policy):
    for entry in entries:
        verdict = loop.screen(entry["task"], library=library, policy=policy)
        entry["screen"] = verdict
        entry["difficulty"] = verdict["class"]
    return entries


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--ladders", type=int, default=20)
    parser.add_argument("--trained", type=int, default=12)
    parser.add_argument("--validation", type=int, default=4)
    parser.add_argument("--applications", type=int, default=40)
    parser.add_argument("--seed", type=int, default=20261001)
    parser.add_argument("--extra-steps", type=int, default=1)
    parser.add_argument("--input-points", type=int, default=5)
    parser.add_argument("--distinct-points", type=int, default=4,
                        help="how many named points the goals must mention; above the three retrieval "
                             "slots the library cannot answer the goal directly")
    arguments = parser.parse_args()
    output = Path(arguments.output)
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    report = {"environment": {
        "sha": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip(),
        "python": sys.version, "platform": platform.platform(),
        "modules_before": loaded_project_modules()},
        "protocol": {
            "ladder": "one construction posed twice: the point the first steps make, and the point the "
                      "whole construction makes; the extension consumes the point the base produced",
            "training": "base tasks only",
            "evaluation": {"transfer": "tops of the ladders whose bases were trained on",
                           "generalisation": "tops of ladders never seen"},
            "conditions": {"A": "starting vocabulary, starting policy",
                           "B": "plus what was acquired, starting policy",
                           "C": "plus what was acquired, learned policy"},
            "carried_between_tasks": ["the library", "the policy"],
            "applications_per_task": arguments.applications,
            "harder_family": {"input_points": arguments.input_points,
                              "goals_mention_at_least": arguments.distinct_points,
                              "why": "retrieval binds at most three fixed names, so a goal mentioning "
                                     "more of them cannot be answered from the library directly"}}}

    say("building the vocabulary the system starts with")
    statistics = Counter()
    began = time.perf_counter()
    base_index = lib.acquire_index(max_depth=2, stats=statistics)
    report["starting_vocabulary"] = {"programs": len(base_index.programs),
                                     "patterns": len(base_index.membership),
                                     "seconds": time.perf_counter()-began}
    say(f"{len(base_index.programs)} programs in {report['starting_vocabulary']['seconds']:.0f}s")

    say("posing ladders")
    began = time.perf_counter()
    batch = posing.pose_ladders(arguments.seed, arguments.ladders, base_depth=2,
                                extra_steps=arguments.extra_steps, goal_count=3, attempts=6000,
                                input_points=arguments.input_points,
                                minimum_distinct_points=arguments.distinct_points)
    say(f"{len(batch['ladders'])} ladders in {time.perf_counter()-began:.0f}s")
    report["posing"] = {"requested": arguments.ladders, "posed": len(batch["ladders"]),
                        "rejections": batch["rejections"], "seconds": time.perf_counter()-began}

    ladders = batch["ladders"]
    trained_ladders = ladders[:arguments.trained]
    held_out = ladders[arguments.trained:]
    start_library = acqlib.AcquiredLibrary(base_index)
    start_policy = dict(loop.START_POLICY)

    say("screening")
    train_entries = screened([ladder["base"] for ladder in trained_ladders],
                             library=start_library, policy=start_policy)
    transfer_entries = screened([ladder["top"] for ladder in trained_ladders],
                                library=start_library, policy=start_policy)
    generalisation_entries = screened([ladder["top"] for ladder in held_out],
                                      library=start_library, policy=start_policy)
    validation_entries = [ladder["base"] for ladder in held_out][:arguments.validation]
    for entry in validation_entries:
        entry.setdefault("difficulty", "unscreened")
    report["sets"] = {
        "train_bases": {"count": len(train_entries),
                        "difficulty": dict(Counter(e["difficulty"] for e in train_entries))},
        "transfer_tops": {"count": len(transfer_entries),
                          "difficulty": dict(Counter(e["difficulty"] for e in transfer_entries))},
        "generalisation_tops": {"count": len(generalisation_entries),
                                "difficulty": dict(Counter(e["difficulty"] for e in generalisation_entries))},
        "validation_bases": {"count": len(validation_entries)},
        "signature_overlap_train_vs_evaluation": sorted(
            {e["signature"] for e in train_entries}
            & ({e["signature"] for e in transfer_entries} | {e["signature"] for e in generalisation_entries}))}
    write(output, "ladders.json", {"trained": trained_ladders, "held_out": held_out})
    say(f"train {len(train_entries)} transfer {len(transfer_entries)} generalisation {len(generalisation_entries)}")

    def evaluate_all(library, policy, note):
        return {"transfer": loop.evaluate(transfer_entries, library=library, policy=policy,
                                          applications=arguments.applications, note=note+" transfer"),
                "generalisation": loop.evaluate(generalisation_entries, library=library, policy=policy,
                                                applications=arguments.applications,
                                                note=note+" generalisation")}

    say("condition A")
    condition_a = evaluate_all(start_library, start_policy, "A")
    say(f"A transfer {condition_a['transfer']['summary']['solved']}/{len(transfer_entries)}, "
        f"generalisation {condition_a['generalisation']['summary']['solved']}/{len(generalisation_entries)}")

    library = acqlib.AcquiredLibrary(base_index)
    say("learning on the base tasks")
    stage = loop.learn_stage(train_entries, library=library, policy=start_policy,
                             applications=arguments.applications)
    say(f"solved {stage['solved']}/{stage['tasks']}, acquired {len(stage['acquisitions'])}")
    candidates = loop.propose_policies(stage["rows"], start_policy)[:3]
    chosen = loop.choose_policy(candidates, validation_entries, library=library,
                                applications=arguments.applications, current=start_policy)
    say(f"policy: {chosen['chosen']}")
    report["learning"] = {k: stage[k] for k in ("solved", "tasks", "failures", "seconds",
                                                "acquisition_seconds")}
    report["learning"]["acquired"] = len(stage["acquisitions"])
    report["library_after"] = library.state()
    report["policy"] = {"chosen": chosen["chosen"], "policy": chosen["policy"], "trials": chosen["trials"]}
    write(output, "learning.json", {"stage": stage, "policy_choice": chosen})

    say("condition B")
    condition_b = evaluate_all(library, start_policy, "B")
    say(f"B transfer {condition_b['transfer']['summary']['solved']}/{len(transfer_entries)}, "
        f"generalisation {condition_b['generalisation']['summary']['solved']}/{len(generalisation_entries)}")
    say("condition C")
    condition_c = evaluate_all(library, chosen["policy"], "C")
    say(f"C transfer {condition_c['transfer']['summary']['solved']}/{len(transfer_entries)}, "
        f"generalisation {condition_c['generalisation']['summary']['solved']}/{len(generalisation_entries)}")

    report["results"] = {name: {which: value[which]["summary"] for which in ("transfer", "generalisation")}
                         for name, value in (("A", condition_a), ("B", condition_b), ("C", condition_c))}
    write(output, "rows.json", {"A": {k: v["rows"] for k, v in condition_a.items()},
                                "B": {k: v["rows"] for k, v in condition_b.items()},
                                "C": {k: v["rows"] for k, v in condition_c.items()}})

    modules_after = loaded_project_modules()
    report["environment"]["sources_unchanged"] = all(
        modules_after.get(key) == value for key, value in report["environment"]["modules_before"].items())
    report["total_seconds"] = time.perf_counter()-started
    report["claims_not_made"] = [
        "the ladder is a supplied curriculum: a person decided that a construction may be posed twice, "
        "once for its first steps and once for the whole. No solution is supplied",
        "the transfer set shares its ladders with the training set by design; the generalisation set "
        "does not, and the two are reported apart",
        "an acquired operation is spliced in as its own steps and each is charged",
        "no preregistered evaluation is affected"]
    write(output, "result.json", report)
    print(json.dumps({"sets": report["sets"], "learning": report["learning"],
                      "results": report["results"], "policy": report["policy"]["chosen"]},
                     indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
