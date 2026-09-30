"""Second-stage backward causal sweep from the independently verified 48.886% route.

The seed comes from episode 2826.  A previous GitHub Actions intervention
changed index 171 from action 9 to action 8 and independently reached
completion_audit_only=0.48886192 before LOSE.

This experiment fixes that intervention, reconstructs the six actions that
followed the saved 175-action seed under the previous fixed PAD continuation,
then changes exactly one of the last ten actions at a time.

IMPORTANT: candidate selection never reads completion/world coordinates.
It ranks only by executed primitive count and terminal status.  Completion is
recorded after a trial solely as an external audit.  A separate post-hoc
"audit_best" is reported and repeated, but is explicitly not a policy choice.
"""
from __future__ import annotations

from pathlib import Path
import json
import shutil

from experiments.mario_continual.port import MarioRGBPort
from experiments.mario_continual.backward_causal_2826 import SEED, PAD

ROOT = Path(__file__).resolve().parent
MAX_ACTIONS = 250
SWEEP_OFFSETS = tuple(range(1, 11))
REPEATS = 5

# Verified first-stage intervention: index 171, action 9 -> 8.
BASE = list(SEED)
assert BASE[171] == 9
BASE[171] = 8
# In the first-stage probe the improved route executed six PAD actions
# (0..5) after the 175-action seed before terminal at action 181.
BASE.extend(PAD[:6])
BASE = tuple(BASE)
assert len(BASE) == 181


def run_trial(name, planned, out_root):
    directory = out_root / name
    if directory.exists():
        shutil.rmtree(directory)
    port = MarioRGBPort(
        ROOT / "game", ROOT / "build", ROOT / "java" / "MortraBridge.java",
        "levels/notch/lvl-1.txt", directory, seconds=60, frames_per_action=8)
    executed = 0
    try:
        _, packet = port.start()
        for action in planned:
            if packet["kind"] != "observation":
                break
            _, packet = port.step(action)
            executed += 1

        survived_reference_horizon = (
            executed >= len(BASE) and packet["kind"] == "observation"
        )

        pad_index = 0
        while packet["kind"] == "observation" and executed < MAX_ACTIONS:
            _, packet = port.step(PAD[pad_index % len(PAD)])
            executed += 1
            pad_index += 1

        return dict(
            executed=executed,
            status=packet.get("status") if packet["kind"] == "terminal" else "SURVIVED_LIMIT",
            survived_reference_horizon=survived_reference_horizon,
            completion_audit_only=(
                packet.get("completion_audit_only")
                if packet["kind"] == "terminal" else None
            ),
        )
    finally:
        port.close()


def allowed_rank(row):
    # No completion/world-coordinate input.
    return (
        int(row["survived_reference_horizon"]),
        row["executed"],
        int(row["status"] == "TIME_OUT"),
        -row["offset"],
        -row["action"],
    )


def main():
    out = Path("/tmp/backward-causal-improved-2826")
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    baseline = run_trial("baseline", BASE, out)
    print("SECOND_BASELINE", json.dumps(baseline, sort_keys=True), flush=True)

    trials = []
    by_offset = []
    for offset in SWEEP_OFFSETS:
        index = len(BASE) - offset
        original = BASE[index]
        rows = []
        for action in range(12):
            if action == original:
                continue
            planned = list(BASE)
            planned[index] = action
            row = run_trial(f"off{offset}_a{action}", planned, out)
            row.update(
                offset=offset, index=index,
                original_action=original, action=action,
            )
            rows.append(row)
            trials.append(row)

        summary = dict(
            offset=offset,
            index=index,
            original_action=original,
            alternatives=len(rows),
            survived_reference=sum(r["survived_reference_horizon"] for r in rows),
            max_executed=max(r["executed"] for r in rows),
            max_completion_audit_only=max(
                (r["completion_audit_only"] or 0.0) for r in rows
            ),
            reached_50pct=any(
                (r["completion_audit_only"] or 0.0) >= 0.5 for r in rows
            ),
        )
        by_offset.append(summary)
        print("SECOND_OFFSET_RESULT", json.dumps(summary, sort_keys=True), flush=True)

    # Causal-policy choice: only survival/executed/status.
    selected = max(trials, key=allowed_rank)
    selected_plan = list(BASE)
    selected_plan[selected["index"]] = selected["action"]
    selected_repeats = [
        run_trial(f"selected_repeat_{i}", selected_plan, out)
        for i in range(REPEATS)
    ]

    # Post-hoc audit only.  This candidate is NOT a valid policy choice.
    audit_trials = [r for r in trials if r["completion_audit_only"] is not None]
    audit_best = max(audit_trials, key=lambda r: r["completion_audit_only"])
    audit_plan = list(BASE)
    audit_plan[audit_best["index"]] = audit_best["action"]
    audit_repeats = [
        run_trial(f"audit_repeat_{i}", audit_plan, out)
        for i in range(REPEATS)
    ]

    result = dict(
        experiment="second_stage_backward_single_action_intervention_episode_2826",
        first_stage_intervention=dict(index=171, original_action=9, action=8),
        policy_selection_inputs=["survived reference horizon", "executed primitive count", "terminal status"],
        forbidden_policy_inputs=["completion_audit_only", "world coordinates"],
        baseline=baseline,
        offsets=by_offset,
        selected_by_allowed_signal=selected,
        selected_repeats=selected_repeats,
        selected_repeat_exact=all(r == selected_repeats[0] for r in selected_repeats),
        audit_best_posthoc=audit_best,
        audit_best_repeats=audit_repeats,
        audit_repeat_exact=all(r == audit_repeats[0] for r in audit_repeats),
        any_50pct=any((r["completion_audit_only"] or 0.0) >= 0.5 for r in trials),
        selected_reaches_50pct=any(
            (r["completion_audit_only"] or 0.0) >= 0.5
            for r in selected_repeats
        ),
        audit_best_reaches_50pct=any(
            (r["completion_audit_only"] or 0.0) >= 0.5
            for r in audit_repeats
        ),
    )
    Path("/tmp/backward_causal_improved_2826.json").write_text(
        json.dumps(result, indent=2, sort_keys=True)
    )
    print(
        "SECOND_CAUSAL_RESULT",
        json.dumps({k: v for k, v in result.items() if k not in ("offsets",)}, sort_keys=True),
        flush=True,
    )


if __name__ == "__main__":
    main()
