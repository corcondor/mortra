"""Compare every saved original trial before any revised-policy outcome."""
import argparse
import gzip
import json
from pathlib import Path

from .adapter import FrozenPlayback, load_v2, restore_game, restore_learner, fingerprint, payload
from .prepare import SEEDS, sha, write


def load_input(directory, seed, module):
    root = directory / "inputs" / str(seed)
    registry = json.loads((directory / "input_registry.json").read_text())[str(seed)]
    for name, digest in registry["files"].items():
        assert sha((root / name).read_bytes()) == digest, (seed, name)
    game = restore_game(module, json.loads((root / "game.json").read_text()))
    learner = restore_learner(module, json.loads((root / "learner.json").read_text()))
    return root, game, learner


def check_seed(directory, seed, output):
    module = load_v2()
    playback = FrozenPlayback(module)
    root, game, learner = load_input(directory, seed, module)
    result = playback.evaluate(game, learner)
    assert not game.is_goal(game.get_initial_state()), "Initial-goal budget case requires preregistration amendment"
    with gzip.open(root / "actions.jsonl.gz", "rt") as stream:
        # Random/auxiliary data are never supplied to the player.
        records = [r for r in map(json.loads, stream) if r["phase"] == "mortra"]
    metrics = json.loads((root / "metrics.json").read_text())
    expected = []
    for trial in range(50):
        rows = [r for r in records if r["trial"] == trial]
        states = [list(game.get_initial_state())] + [r["next_state"] for r in rows]
        assert all(r["state"] == states[i] for i, r in enumerate(rows))
        expected.append({"trial": trial, "actions": [r["action"] for r in rows], "states": states,
                         "success": bool(game.is_goal(tuple(states[-1])))})
    actual = json.loads(json.dumps(result["trials"]))
    differences = [{"trial": i, "expected": e, "actual": a} for i, (e, a) in enumerate(zip(expected, actual)) if e != a]
    assert result["successes"] == metrics["successes"]
    assert actual[0]["actions"] == metrics["mortra_replay"]["actions"]
    write(output / f"{seed}.json", {"seed": seed, "trial_count": len(actual), "discrete_differences": differences,
        "successes": result["successes"], "actual_actions": result["actual_actions"],
        "learner_fingerprint": fingerprint(payload(learner)), "game_fingerprint": fingerprint(game.to_dict()),
        "frozen_learner_unchanged": result["learner_unchanged"], "original_trial_ast_sha256": playback.original_trial_ast_sha,
        "historical_field_float_comparison": "NOT_AVAILABLE: old artifacts do not save psi; all discrete actions compared"})
    assert not differences, (seed, differences[:1])
    print(f"{seed}: all 50 saved trial actions, states and outcomes exactly match", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    for seed in SEEDS:
        check_seed(args.input, seed, args.output)
    write(args.output / "passed.json", {"all_seeds": SEEDS, "trials": 400, "all_discrete_traces_equal": True})


if __name__ == "__main__":
    main()
