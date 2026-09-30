"""Causal probe: can revisit + terminal-hazard repair improve saved Mario routes?

Selection NEVER reads completion.  For each saved route, replay the original
action sequence (baseline), then replace only its final primitive by every
alternative.  If a mutation survives, continue with a fixed action cycle that
is identical for all candidates.  The selected candidate is the one that
survives the most primitive decisions; terminal completion is recorded only
after selection for audit.

This isolates one component of the proposed fix: repeated local revision using
LOSE/TIME_OUT evidence instead of one-ticket-per-context fairness.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil

from experiments.mario_continual.port import MarioRGBPort

ROOT = Path(__file__).resolve().parent
SEEDS = [
    [5,3,2,6,4,10,1,9,4,4,7,2,7,11,3,9,4,3,0,7,0,2,7,2,7,11,8,4,8,9,7,8,11,2,11,10,0,11,0,11,0,10,4,6,11,8,5,2,8,10,0,5,11,5],
    [2,7,7,1,9,6,9,9,9,1,2,7,2,7,11,1,5,3,7,7,5,9,4,4,2,7,11,6,2,9,3,3,1,1,3,10,2,7,11,2,7,8,10,1,11,1,11,9,4,4,3,6,10,7,2,7,2,7,2,7,2,7,2,7,8,2,2,6,1,4,11,0,5,11,0,2],
    [8,8,2,0,10,3,1,9,11,4,1,5,3,4,1,6,2,4,8,5],
    [6,2,7,7,9,10,9,4,9,4,4,4,4,11,8,3,6,11,2,4,9,10,9,3,3,8,8],
    [11,2,4,11,3,0,5,5,10,9,1,6,8,0,10,0,8,11,7,9,11,10,11,2,7,7,8,8,1,6,1,1,6,8,10,1,9,8,8,4,0],
    [2,7,1,9,10,9,4,9,9,1,2,7,2,6,8,4,5,9,7,9,3,5,8,2,3,8,5,9],
    [9,7,7,9,9,9,4,4,9,6,0,1,2,6,8,4,0,6,4,9,11,4,8,11,11,0],
    [1,9,5,8,1,11,9,0,11,4,11,4,11],
]
EXPECTED = [0.31170705,0.1231268,0.047109336,0.09019719,0.12702674,0.124799915,0.12720153,0.11356189]
PAD = tuple(range(12))
MAX_ACTIONS = 250


def run_trial(name, planned, out_root):
    directory = out_root / name
    if directory.exists():
        shutil.rmtree(directory)
    port = MarioRGBPort(
        ROOT/"game", ROOT/"build", ROOT/"java"/"MortraBridge.java",
        "levels/notch/lvl-1.txt", directory, seconds=60, frames_per_action=8)
    executed = 0
    planned_executed = 0
    try:
        _, packet = port.start()
        for action in planned:
            if packet["kind"] != "observation":
                break
            _, packet = port.step(action)
            executed += 1
            planned_executed += 1
        pad_index = 0
        while packet["kind"] == "observation" and executed < MAX_ACTIONS:
            _, packet = port.step(PAD[pad_index % len(PAD)])
            pad_index += 1
            executed += 1
        return dict(
            status=packet.get("status") if packet["kind"] == "terminal" else "SURVIVED_LIMIT",
            executed=executed,
            planned_executed=planned_executed,
            survived_planned=(planned_executed == len(planned) and packet["kind"] == "observation") or
                             executed > len(planned),
            completion_audit_only=packet.get("completion_audit_only") if packet["kind"] == "terminal" else None,
        )
    finally:
        port.close()


def main():
    out = Path("/tmp/mortra-revisit-causal")
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    rows = []
    for i, seed in enumerate(SEEDS):
        baseline = run_trial(f"seed{i}_baseline", seed, out)
        candidates = []
        original = seed[-1]
        for action in range(12):
            if action == original:
                continue
            trial = run_trial(f"seed{i}_alt{action}", seed[:-1] + [action], out)
            trial["action"] = action
            candidates.append(trial)

        # POLICY SELECTION: terminal survival only. No completion access here.
        selected = max(candidates, key=lambda r: (
            r["executed"],
            int(r["status"] == "TIME_OUT"),
            -r["action"],
        ))
        row = dict(
            seed=i,
            seed_length=len(seed),
            original_last_action=original,
            baseline=baseline,
            selected_action=selected["action"],
            selected={k:v for k,v in selected.items() if k != "action"},
            audit_delta_completion=(
                None if baseline["completion_audit_only"] is None or selected["completion_audit_only"] is None
                else selected["completion_audit_only"] - baseline["completion_audit_only"]
            ),
            expected_saved_completion=EXPECTED[i],
        )
        rows.append(row)
        print("SEED_RESULT", json.dumps(row, sort_keys=True), flush=True)

    comparable=[r for r in rows if r["audit_delta_completion"] is not None]
    result=dict(
        experiment="terminal_hazard_last_action_revisit",
        selection_inputs=["executed primitive count","terminal status"],
        forbidden_policy_inputs=["completion_audit_only","world coordinates"],
        seeds=len(rows),
        improved=sum(r["audit_delta_completion"] > 0 for r in comparable),
        worsened=sum(r["audit_delta_completion"] < 0 for r in comparable),
        tied=sum(r["audit_delta_completion"] == 0 for r in comparable),
        mean_baseline_completion=sum(r["baseline"]["completion_audit_only"] for r in comparable)/len(comparable),
        mean_selected_completion=sum(r["selected"]["completion_audit_only"] for r in comparable)/len(comparable),
        max_baseline_completion=max(r["baseline"]["completion_audit_only"] for r in comparable),
        max_selected_completion=max(r["selected"]["completion_audit_only"] for r in comparable),
        reached_50pct=any((r["selected"]["completion_audit_only"] or 0) >= .5 for r in rows),
        rows=rows,
    )
    Path("/tmp/revisit_causal_result.json").write_text(json.dumps(result, indent=2, sort_keys=True))
    print("CAUSAL_RESULT", json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
