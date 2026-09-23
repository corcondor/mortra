"""Export only fresh, validated Python experiment records, never a browser solver."""
import argparse
import hashlib
import json
from collections import deque
from pathlib import Path

from evaluate_autonomous_game_design_loop import MicroGame, evaluate_random_player

ROOT = Path(__file__).resolve().parents[1]


def load_game(data):
    game = MicroGame(data["width"], data["height"])
    for name, value in data.items():
        if name in ("walls", "hazards"):
            value = {tuple(cell) for cell in value}
        elif name.endswith("_pos") or name in ("teleport_a", "teleport_b"):
            value = tuple(value) if value is not None else None
        setattr(game, name, value)
    return game


def validate_metrics(data, metrics):
    game = load_game(data)
    trials = metrics["trials"]
    for count, rate in [("successes", "success_rate"), ("random_successes", "random_success_rate")]:
        if not 0 <= metrics[count] <= trials or metrics[rate] != round(metrics[count] / trials, 4):
            raise ValueError(f"Invalid success count: {count}")
    random_result = evaluate_random_player(game, trials, metrics["max_play_steps"])
    if random_result["successes"] != metrics["random_successes"]:
        raise ValueError("Random baseline does not reproduce")
    for name in ("mortra_replay", "random_replay"):
        replay = metrics[name]
        state = game.get_initial_state()
        if len(replay["states"]) != len(replay["actions"]) + 1 or list(state) != replay["states"][0]:
            raise ValueError("Invalid replay initial state or length")
        for action, expected in zip(replay["actions"], replay["states"][1:]):
            if game.is_goal(state) or action not in range(5):
                raise ValueError("Invalid post-goal action or action id")
            state = game.step(state, action)
            if list(state) != expected:
                raise ValueError("Recorded replay differs from Python transition")
        if bool(game.is_goal(state)) != replay["reached_goal"]:
            raise ValueError("Replay outcome mismatch")


def public_metrics(metrics):
    return {key: value for key, value in metrics.items()
            if key not in ("mortra_replay", "random_replay", "sample_trajectories")}


def transition_fixture(games):
    result = []
    for data in games:
        game = load_game(data)
        queue = deque([game.get_initial_state()])
        seen = set(queue)
        cases = []
        while queue and len(cases) < 1500:
            state = queue.popleft()
            outputs = [game.step(state, action) for action in range(5)]
            cases.append({"state": state, "outputs": outputs})
            for nxt in outputs:
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        result.append({"game": data, "cases": cases, "exhausted": not queue})
    return result


def export(source, canonical, mirror):
    read = lambda name: json.loads((source / name).read_text(encoding="utf-8"))
    metadata = read("metadata.json")
    if metadata["version"] != 2 or metadata["status"] != "complete":
        raise ValueError("Only a completed v2 run can be published")
    metadata.pop("command", None)  # Do not publish local workstation paths.
    initial, final = read("game_initial.json"), read("game_final.json")
    history, metrics = read("evolution_history.json"), read("self_play_metrics.json")
    for condition in history.values():
        previous = condition[0]["game"]
        for entry in condition:
            validate_metrics(entry["game"], entry["metrics"])
            if entry["iteration"]:
                validate_metrics(entry["candidate_game"], entry["candidate_metrics"])
                expected = entry["candidate_game"] if entry["accepted"] else previous
                if entry["game"] != expected:
                    raise ValueError("Accepted/rejected edit history is inconsistent")
            previous = entry["game"]
    designer = history["designer_history"]
    if initial != designer[0]["game"] or final != designer[-1]["game"]:
        raise ValueError("Published initial/final do not match the fresh history")
    timeline = [{**{k: v for k, v in entry.items() if k not in ("metrics", "candidate_metrics")},
                 "metrics": public_metrics(entry["metrics"]),
                 "candidate_metrics": public_metrics(entry["candidate_metrics"]) if "candidate_metrics" in entry else None}
                for entry in designer]
    replays = {phase: {"mortra": metrics[key]["mortra_replay"], "random": metrics[key]["random_replay"]}
               for phase, key in [("initial", "initial_metrics"), ("final", "final_designer_metrics")]}
    payload = {"metadata": metadata, "initial": initial, "final": final,
               "control": history["control_history"][-1]["game"],
               "timeline": timeline, "replays": replays,
               "metrics": {k: public_metrics(v) if k.endswith("metrics") else v for k, v in metrics.items()}}
    files = {"experiment.json": payload, "game_initial.json": initial, "game_final.json": final,
             "accepted_edits.json": [entry for entry in timeline if entry["iteration"] and entry["accepted"]],
             "replays.json": replays, "metadata.json": metadata}
    manifest = {}
    for name, data in files.items():
        raw = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        manifest[name] = hashlib.sha256(raw).hexdigest()
        for root in (canonical, mirror):
            destination = root / metadata["experiment_id"]
            destination.mkdir(parents=True, exist_ok=True)
            if (destination / name).exists() and (destination / name).read_bytes() != raw:
                raise ValueError(f"Refusing to replace published experiment bytes: {destination / name}")
            (destination / name).write_bytes(raw)
    for root in (canonical, mirror):
        (root / metadata["experiment_id"] / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (source / "browser_transition_fixture.json").write_text(json.dumps(transition_fixture([initial, final])), encoding="utf-8")
    legacy_path = ROOT / "reports/self_game_design/self_play_metrics.json"
    old = json.loads(legacy_path.read_text(encoding="utf-8"))
    comparison = {"legacy_status": "UNREPAIRED historical run with double-counted random successes; not comparable corrected estimates",
                  "old_artifacts_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in legacy_path.parent.iterdir() if p.is_file()},
                  "old_reported": {k: public_metrics(v) if k.endswith("metrics") else v for k, v in old.items()},
                  "fresh_v2": payload["metrics"], "web_sha256": manifest,
                  "validation": "All main/control current and candidate random counts recomputed; all recorded actions replayed in Python"}
    (source / "export_verification.json").write_text(json.dumps(comparison, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"experiment_id": metadata["experiment_id"], "validated_history_entries": sum(map(len, history.values())),
                      "canonical": str(canonical), "mirror": str(mirror), "files": manifest}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "reports/self_game_design_v2")
    args = parser.parse_args()
    export(args.source, ROOT / "web/public/mortra/runs", ROOT / "public/mortra/runs")
