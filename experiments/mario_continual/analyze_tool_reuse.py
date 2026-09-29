"""Explain learned-tool reuse from an events.jsonl trace.

This is a structural audit, not a policy-quality score.  It reconstructs the
legacy selection theorem directly from logged decisions:

    a*(q) = base primitive policy
    tool t can be invoked only if guard(t) == q and first(t) == a*(q)

Therefore invocation(t) is impossible if guard(t) is never seen at a later
decision boundary.  The report measures that condition exactly.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path


def load(path):
    with Path(path).open(encoding="utf8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def analyze(events):
    learned = {}
    invoked = Counter()
    first_step = {}
    all_steps = []

    for event in events:
        kind = event.get("event")
        if kind == "tool_learned":
            learned[event["tool"]] = event
        elif kind == "tool_invoked":
            invoked[event["tool"]] += 1
        elif kind == "primitive_step":
            all_steps.append(event)
            first_step.setdefault(int(event["decisions"]), event)

    rows = []
    for token, record in learned.items():
        learned_at = int(record["decisions"])
        guard = int(record["guard"])
        actions = tuple(int(a) for a in record["actions"])
        decision_visits = 0
        primitive_visits = 0
        first_action_matches = 0
        for decision, step in first_step.items():
            if decision <= learned_at:
                continue
            if step.get("source_candidates") == [guard]:
                decision_visits += 1
                if int(step["action"]) == actions[0]:
                    first_action_matches += 1
        for step in all_steps:
            if int(step["decisions"]) <= learned_at:
                continue
            if step.get("source_candidates") == [guard]:
                primitive_visits += 1

        rows.append({
            "tool": token,
            "guard": guard,
            "actions": list(actions),
            "length": len(actions),
            "learned_at_decision": learned_at,
            "future_guard_decision_visits": decision_visits,
            "future_guard_primitive_visits": primitive_visits,
            "future_first_action_matches": first_action_matches,
            "invocations": invoked[token],
        })

    programs = defaultdict(list)
    for row in rows:
        programs[tuple(row["actions"])].append(row)

    # Counterfactual opportunity only: same logged base first action after the
    # earliest discovery of a program. It does not claim the trajectory would
    # stay unchanged after actually transferring programs.
    program_opportunities = []
    for actions, records in programs.items():
        learned_at = min(r["learned_at_decision"] for r in records)
        later_first_action = sum(
            1 for decision, step in first_step.items()
            if decision > learned_at and int(step["action"]) == actions[0]
        )
        program_opportunities.append({
            "actions": list(actions),
            "records": len(records),
            "earliest_learned_at": learned_at,
            "later_same_first_action_decisions": later_first_action,
            "legacy_invocations": sum(r["invocations"] for r in records),
        })

    report = {
        "learned_tool_records": len(rows),
        "unique_executable_programs": len(programs),
        "duplicate_context_records": len(rows) - len(programs),
        "tool_invocations": sum(invoked.values()),
        "distinct_invoked_tool_records": sum(v > 0 for v in invoked.values()),
        "records_with_future_guard_decision_visit":
            sum(r["future_guard_decision_visits"] > 0 for r in rows),
        "records_with_no_future_guard_decision_visit":
            sum(r["future_guard_decision_visits"] == 0 for r in rows),
        "records_with_any_future_guard_primitive_visit":
            sum(r["future_guard_primitive_visits"] > 0 for r in rows),
        "programs_with_later_same_first_action_opportunity":
            sum(r["later_same_first_action_decisions"] > 0 for r in program_opportunities),
        "rows": rows,
        "programs": sorted(program_opportunities, key=lambda r: tuple(r["actions"])),
    }

    # This implication must hold for the legacy implementation.
    impossible_but_invoked = [
        r for r in rows
        if r["future_guard_decision_visits"] == 0 and r["invocations"] > 0
    ]
    report["legacy_guard_theorem_violations"] = impossible_but_invoked
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("events", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = analyze(load(args.events))
    text = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf8")
    print(text, end="")


if __name__ == "__main__":
    main()
