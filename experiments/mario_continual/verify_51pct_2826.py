"""Independent-process verification of the two causal interventions on episode 2826.

No policy selection occurs here.  This file only replays two fixed action
sequences in the real Mario engine:
  stage1: index 171, 9 -> 8, then six fixed PAD actions
  stage2: stage1 plus index 176, 1 -> 11

Completion is terminal audit only.
"""
from __future__ import annotations

from pathlib import Path
import json
import shutil
import sys

from experiments.mario_continual.port import MarioRGBPort
from experiments.mario_continual.backward_causal_2826 import SEED, PAD

ROOT = Path(__file__).resolve().parent


def sequence(stage):
    actions = list(SEED)
    assert actions[171] == 9
    actions[171] = 8
    actions.extend(PAD[:6])
    if stage == 2:
        assert actions[176] == 1
        actions[176] = 11
    return tuple(actions)


def replay(name, actions, out_root):
    directory = out_root / name
    if directory.exists():
        shutil.rmtree(directory)
    port = MarioRGBPort(
        ROOT / "game", ROOT / "build", ROOT / "java" / "MortraBridge.java",
        "levels/notch/lvl-1.txt", directory, seconds=60, frames_per_action=8)
    executed = 0
    try:
        _, packet = port.start()
        for action in actions:
            if packet["kind"] != "observation":
                break
            _, packet = port.step(action)
            executed += 1
        return dict(
            executed=executed,
            status=packet.get("status") if packet["kind"] == "terminal" else "SURVIVED_SEQUENCE",
            completion_audit_only=(
                packet.get("completion_audit_only")
                if packet["kind"] == "terminal" else None
            ),
        )
    finally:
        port.close()


def main():
    replica = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    out = Path(f"/tmp/verify-51pct-2826-{replica}")
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    stage1 = replay("stage1", sequence(1), out)
    stage2 = replay("stage2", sequence(2), out)
    result = dict(
        replica=replica,
        engine="Mario-AI-Framework pinned by setup_game",
        stage1_intervention={"index": 171, "from": 9, "to": 8},
        stage2_intervention={"index": 176, "from": 1, "to": 11},
        stage1=stage1,
        stage2=stage2,
        stage2_over_50=bool((stage2["completion_audit_only"] or 0.0) >= 0.5),
    )
    path = Path(f"/tmp/verify_51pct_2826_{replica}.json")
    path.write_text(json.dumps(result, indent=2, sort_keys=True))
    print("INDEPENDENT_51PCT_RESULT", json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
