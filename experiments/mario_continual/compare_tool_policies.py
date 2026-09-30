"""Compare two real-Mario tool policies at equal primitive-action budget."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import statistics


def read_events(root):
    path = Path(root) / "events.jsonl"
    with path.open(encoding="utf8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def summarize(root):
    root = Path(root)
    status = json.loads((root / "status.json").read_text())
    events = read_events(root)

    learned = [e for e in events if e.get("event") == "tool_learned"]
    exact_invoked = [e for e in events if e.get("event") == "tool_invoked"]
    transfer_invoked = [e for e in events if e.get("event") == "program_transfer_invoked"]
    transfer_completed = [e for e in events if e.get("event") == "program_transfer_completed"]
    terminals = [e for e in events if e.get("event") == "episode_terminal"]
    primitive = [e for e in events if e.get("event") == "primitive_step"]

    programs = {tuple(e["actions"]) for e in learned}
    transferred_programs = {tuple(e["actions"]) for e in transfer_invoked}
    exact_tools = {e["tool"] for e in exact_invoked}

    per_episode_actions = Counter()
    action_hist = Counter()
    for e in primitive:
        per_episode_actions[int(e["episode"])] += 1
        action_hist[int(e["action"])] += 1

    completions = [
        float(e["completion_audit_only"])
        for e in terminals if e.get("completion_audit_only") is not None
    ]
    terminal_status = Counter(str(e.get("status")) for e in terminals)

    lengths = list(per_episode_actions.values())
    return {
        "status": status,
        "learned_tool_records": len(learned),
        "unique_programs": len(programs),
        "legacy_tool_invocations": len(exact_invoked),
        "distinct_legacy_tools_invoked": len(exact_tools),
        "program_transfer_invocations": len(transfer_invoked),
        "distinct_programs_transferred": len(transferred_programs),
        "program_transfer_completions": len(transfer_completed),
        "episode_terminals": len(terminals),
        "terminal_status": dict(terminal_status),
        "completion_max": max(completions) if completions else None,
        "completion_mean": statistics.mean(completions) if completions else None,
        "episode_primitive_actions_max": max(lengths) if lengths else 0,
        "episode_primitive_actions_mean": statistics.mean(lengths) if lengths else 0.0,
        "action_histogram": dict(sorted(action_hist.items())),
        "primitive_steps_logged": len(primitive),
        "first_clear": status.get("first_clear"),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--legacy", type=Path, required=True)
    p.add_argument("--program-frontier", type=Path, required=True)
    p.add_argument("--conditional-frontier", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = {
        "legacy": summarize(args.legacy),
        "program_frontier": summarize(args.program_frontier),
    }
    if args.conditional_frontier is not None:
        result["conditional_frontier"] = summarize(args.conditional_frontier)
    l = result["legacy"]
    pfr = result["program_frontier"]
    result["delta_program_frontier_minus_legacy"] = {
        "completion_max": (
            None if l["completion_max"] is None or pfr["completion_max"] is None
            else pfr["completion_max"] - l["completion_max"]
        ),
        "episode_primitive_actions_max":
            pfr["episode_primitive_actions_max"] - l["episode_primitive_actions_max"],
        "distinct_reused_programs":
            pfr["distinct_programs_transferred"] - l["distinct_legacy_tools_invoked"],
        "predictive_states":
            pfr["status"]["predictive_states"] - l["status"]["predictive_states"],
        "observation_classes":
            pfr["status"]["observation_classes"] - l["status"]["observation_classes"],
    }
    if "conditional_frontier" in result:
        cfr = result["conditional_frontier"]
        result["delta_conditional_minus_legacy"] = {
            "completion_max": (None if l["completion_max"] is None or cfr["completion_max"] is None else cfr["completion_max"] - l["completion_max"]),
            "episode_primitive_actions_max": cfr["episode_primitive_actions_max"] - l["episode_primitive_actions_max"],
            "predictive_states": cfr["status"]["predictive_states"] - l["status"]["predictive_states"],
            "observation_classes": cfr["status"]["observation_classes"] - l["status"]["observation_classes"],
            "conditional_precision": cfr["status"].get("conditional_precision"),
            "conditional_predictions": cfr["status"].get("conditional_predictions"),
            "conditional_unresolved": cfr["status"].get("conditional_unresolved"),
        }
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
