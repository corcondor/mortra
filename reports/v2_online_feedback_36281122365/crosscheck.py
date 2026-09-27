"""Read-only crosscheck of the supplied Linux bundle against canonical Actions."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

SEEDS = range(79020000, 79020008)
MODES = {"A_frozen": "frozen", "B_record_replan": "record_and_replan", "C_record_replan_explore": "record_replan_and_explore"}
PREFIX = "mortra_online_feedback_20260927/"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--actions", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    zipped = args.zip.read_bytes()
    assert digest(zipped) == "63ee96fb9fea4001318e73fef2b8f39cb47ea5d27dcbafaa09027555af1af924"
    checks, differences, float_rows, sources = [], [], [], []
    transitions = trials_count = snapshots = eval_actions = input_files = 0
    with zipfile.ZipFile(args.zip) as bundle:
        for line in bundle.read(PREFIX + "CHECKSUMS.sha256").decode().splitlines():
            if not line.strip():
                continue
            expected, name = line.split(maxsplit=1)
            name = name.lstrip("*")
            full = name if name.startswith(PREFIX) else PREFIX + name
            actual = digest(bundle.read(full))
            checks.append({"name": name, "sha256": actual})
            assert actual == expected, name
        for name in ("verify_checkout.py", "reference/v2_source_excerpt.py"):
            path = args.output / "unchanged_verifier" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(bundle.read(PREFIX + name))
        for name in bundle.namelist():
            base = PREFIX + "vendor/experiments/task_agent/"
            if name.startswith(base) and name.endswith(".py"):
                canonical = args.repo / "experiments/task_agent" / name.removeprefix(base)
                supplied = bundle.read(name).replace(b"\r\n", b"\n")
                current = canonical.read_bytes().replace(b"\r\n", b"\n")
                sources.append({"file": name.removeprefix(PREFIX), "identical_lf": supplied == current,
                                "supplied_sha256_lf": digest(supplied), "canonical_sha256_lf": digest(current)})
        verification = subprocess.run([sys.executable, str(args.output / "unchanged_verifier/verify_checkout.py"), str(args.repo)], text=True, capture_output=True)
        (args.output / "verify_checkout.stdout.json").write_text(verification.stdout, encoding="utf-8")
        (args.output / "verify_checkout.stderr.log").write_text(verification.stderr, encoding="utf-8")
        assert verification.returncode == 0, verification.stderr or verification.stdout
        def load(name):
            return json.loads(bundle.read(PREFIX + name))
        for seed in SEEDS:
            world = args.actions / "worlds" / f"feedback-{seed}-36281122365" / f"feedback_{seed}"
            originals = args.actions / "gates/reports/registered_inputs/inputs" / str(seed)
            for name in ("game.json", "learner.json", "metrics.json", "audit.json", "training.jsonl.gz", "actions.jsonl.gz"):
                same = (originals / name).read_bytes() == bundle.read(PREFIX + f"inputs/{seed}/{name}")
                assert same, (seed, name)
                input_files += 1
            for reference_arm, arm in MODES.items():
                base = f"results/{seed}/{reference_arm}/"
                path = world / arm
                ref_trace = [json.loads(s) for s in gzip.decompress(bundle.read(PREFIX + base + "training_trace.jsonl.gz")).splitlines()]
                with gzip.open(path / "training_actions.jsonl.gz", "rt") as stream:
                    actual_trace = list(map(json.loads, stream))
                assert len(ref_trace) == len(actual_trace) == 5000
                float_differences = []
                for i, (a, b) in enumerate(zip(actual_trace, ref_trace), 1):
                    mapping = {"step": "additional_action", "rollout_step": "step_in_trial", **{k: k for k in
                        ("trial", "state", "action", "next_state", "success", "fallback", "selector_called")}}
                    unequal = [k for k, other in mapping.items() if a[k] != b[other]]
                    if unequal:
                        differences.append({"seed": seed, "arm": arm, "step": i, "fields": unequal})
                    float_differences.append(abs(a["best_value"] - b["legacy_best_value"]))
                float_rows.append({"seed": seed, "arm": arm, "float_values_compared": len(float_differences),
                    "exactly_different_values": sum(x != 0 for x in float_differences),
                    "max_absolute_difference": max(float_differences)})
                transitions += len(actual_trace)
                for budget in (0, 1000, 5000):
                    snapshot = json.loads((path / f"checkpoint_{budget}/learner.json").read_text())
                    reference = load(base + f"snapshot_{budget}.json")
                    if snapshot != reference:
                        differences.append({"seed": seed, "arm": arm, "budget": budget, "kind": "snapshot"})
                    snapshots += 1
                    evaluation = load(base + f"evaluation_{budget}.json")
                    with gzip.open(path / f"checkpoint_{budget}/evaluation_trials.jsonl.gz", "rt") as stream:
                        actual_trials = list(map(json.loads, stream))
                    assert len(actual_trials) == len(evaluation["replays"]) == 50
                    for a, b in zip(actual_trials, evaluation["replays"]):
                        if a != {"trial": b["trial"], "actions": b["actions"], "states": b["states"], "success": b["reached_goal"]}:
                            differences.append({"seed": seed, "arm": arm, "budget": budget, "trial": a["trial"], "kind": "evaluation"})
                        eval_actions += len(a["actions"])
                        trials_count += 1
    result = {"bundle_sha256": digest(zipped), "checked_manifest_files": len(checks), "identical_input_files": input_files,
        "compared_training_actions": transitions, "compared_snapshots": snapshots,
        "compared_evaluation_trials": trials_count, "compared_evaluation_actions": eval_actions,
        "discrete_and_snapshot_differences": differences, "action_value_float_comparison": float_rows,
        "canonical_excerpt_ast_verification": json.loads(verification.stdout),
        "task_agent_source_comparison": sources,
        "scope": "Read-only comparison; no bundle policy execution or experiment rerun",
        "schema_notes": ["Condition names and trace field names mapped explicitly.",
                         "Bundle reset_calls includes initial placement; Actions resets excludes it.",
                         "Bundle first_goal_observation_action denotes first known model goal, including 0; Actions also separately records first goal hit during additional play.",
                         "CPU/wall time and floating-point action values are not hidden by snapshot or action comparisons."]}
    (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    assert not differences, differences[:3]
    print(json.dumps({k: v for k, v in result.items() if k != "action_value_float_comparison"}, indent=2))


if __name__ == "__main__":
    main()
