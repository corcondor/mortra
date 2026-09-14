"""Read-only aggregation of geometry events; never selects or executes a task."""
from collections import Counter, defaultdict
import json


def aggregate_geometry_events(path):
    families = defaultdict(lambda: defaultdict(Counter))
    predicates = defaultdict(Counter)
    used = defaultdict(Counter)
    depth = defaultdict(Counter)
    event_types = Counter()
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            e = json.loads(line)
            event = e.get("event", "")
            event_types[event] += 1
            group = str(e.get("cohort", e.get("stage", "acquisition")))+":"+str(e.get("arm", e.get("condition", "unknown")))
            family = e.get("family")
            if event == "candidate_order":
                row = families[group][family]
                row["proposed_in_pages"] += len(e["original"])
                row["reordered_pages"] += e["original"] != e["ordered"]
                row["pages"] += 1
            elif event == "selection":
                families[group][family]["selected"] += 1
            elif event == "candidate_scan":
                families[group][family]["scanned_tuples"] += 1
                families[group][family][e["disposition"]] += 1
                families[group][family]["largest_scan_ordinal"] = max(
                    families[group][family]["largest_scan_ordinal"], e["ordinal"])
            elif event == "refusal":
                families[group][family]["refused:"+e["reason"]] += 1
            elif event == "certified_history":
                call = e["call"]
                families[group][call["morphism"]]["successful_execution"] += 1
                families[group][call["morphism"]]["primitive_replay_passed"] += e["replay"]["passed"]
                for item in call["provenance"]["used_predicates"]:
                    used[group][item["atom"]["predicate"]] += 1
            elif event == "predicate_check":
                source = e["source"] if isinstance(e["source"], str) else "construction_effect"
                predicates[group][e["predicate"]+":"+source+":"+str(e["passed"])] += 1
            elif event == "semantic_state":
                depth[group][str(e["depth"])] += 1
    return {
        "event_types": dict(event_types),
        "families": {g: {f: dict(c) for f, c in fs.items()} for g, fs in families.items()},
        "predicate_requests": {g: dict(c) for g, c in predicates.items()},
        "consumed_premises_in_successful_calls": {g: dict(c) for g, c in used.items()},
        "produced_states_by_depth": {g: dict(c) for g, c in depth.items()},
        "predicate_request_coverage": "recorded" if predicates else "not present in source log; cannot reconstruct failed requests",
        "counting_scope": "Event occurrences, not unique theorems or mathematical functions. Refusal types remain separate.",
    }
