"""Read fresh event logs; diagnostic witnesses are NEVER offered to search.

No monkeypatches, solver invocation, library acquisition or state insertion.
Replays refused compositions independently to inspect discarded intermediates.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import sympy as sp
from math_os_prototype import geometry_contracts as gc
from math_os_prototype import geometry_semantic_dsl as dsl
from math_os_prototype.representation_progress import digest
from worker.backend.typed_geometry_stalk import DEFAULT_POINT_FAMILIES, iter_complete_typed_candidates


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, data):
    path.write_text(json.dumps(data, indent=2)+"\n", encoding="utf-8")


def term(value):
    return gc.point(value) if isinstance(value, str) else {"op": value[0], "args": [term(v) for v in value[1:]]}


def signature(family, xy):
    xy = tuple(tuple(v) for v in xy)
    if family in {"midpoint", "circle", "orthocenter"}:
        return tuple(sorted(xy))
    if family in {"foot", "reflect"}:
        return xy[0], tuple(sorted(xy[1:]))
    if family == "intersection_ll":
        return tuple(sorted((tuple(sorted(xy[:2])), tuple(sorted(xy[2:])))))
    return xy


def goal_proofs(task, objects, output, costs):
    return [dsl.certify_atom(g["predicate"], tuple(output if n == "u" else n for n in g["points"]),
        objects, provenance="developer_diagnostic_only", stats=costs) for g in task["goals"]]


def replay(steps, objects, costs):
    """Primitive coordinates + original primitive NDGs, not contract witnesses."""
    objects = {n: dict(v) for n, v in objects.items()}
    elab = gc._JGEXElaborator()
    elab.coordinates.update({n: tuple(sp.Rational(v) for v in o["coordinates"]) for n, o in objects.items()})
    records = []
    for step in steps:
        before = time.perf_counter()
        guards = [dsl.certify_atom(p, tuple(a), objects, provenance="diagnostic_primitive_precondition", stats=costs)
            for p, a in dsl.requirements(step["family"], step["inputs"])]
        costs["precondition_seconds"] += time.perf_counter()-before
        if not all(g is not None for g in guards):
            return records, objects, "primitive_precondition_refused"
        costs["primitive_operations"] += 1
        before = time.perf_counter()
        try:
            dsl.FRAGMENT.primitive(elab, step["family"], step["output"], step["inputs"])
            if any(sp.cancel(d) == 0 for d in elab.denominators):
                return records, objects, "primitive_denominator_zero"
            xy = [str(sp.Rational(v)) for v in elab.coordinates[step["output"]]]
            if any(sp.Rational(v).is_finite is not True for v in xy):
                return records, objects, "nonfinite"
        except (ValueError, TypeError, ZeroDivisionError) as exc:
            return records, objects, type(exc).__name__+":"+str(exc)
        finally:
            costs["primitive_seconds"] += time.perf_counter()-before
        record = {"family": step["family"], "inputs": step["inputs"], "output": step["output"],
            "input_coordinates": [objects[n]["coordinates"] for n in step["inputs"]],
            "coordinates": xy, "preconditions": [asdict(g) for g in guards]}
        objects[step["output"]] = {"type": "Point", "coordinates": xy}
        records.append(record)
    return records, objects, None


def initial(task):
    if task.get("predicates"):
        raise ValueError("This audit must reconstruct declared input certificates explicitly")
    state = {"objects": {n: {"type": "Point", "coordinates": [str(sp.Rational(v)) for v in xy]}
                         for n, xy in task["points"].items()},
             "terms": {n: gc.point(n) for n in task["points"]}, "predicates": {}, "depth": 0}
    state["state_hash"] = digest({k: ([] if k == "predicates" else state[k])
                                for k in ("objects", "terms", "predicates", "depth")})
    return state


def input_state_count(states, coordinates):
    required = set(map(tuple, coordinates))
    return [s for s in states.values() if required <= {tuple(o["coordinates"]) for o in s["objects"].values()}]


def complete_grammar_probe(state, task, step):
    family = next(f for f in DEFAULT_POINT_FAMILIES if f.name == step["family"])
    graph = {n: set() for n in state["objects"]}
    for atom in state["predicates"].values():
        for a, b in combinations(atom["arguments"], 2):
            graph[a].add(b)
            graph[b].add(a)
    demand = Counter(n for g in task["goals"] for n in g["points"] if n in graph)
    target = signature(step["family"], step["input_coordinates"])
    for ordinal, row in enumerate(iter_complete_typed_candidates(points=list(graph), graph=graph,
            goal_multiplicity=demand, generated_points=set(graph)-set(task["points"]), family=family)):
        if signature(row.family, [state["objects"][n]["coordinates"] for n in row.inputs]) == target:
            return {"exists": True, "raw_ordinal": ordinal, "binding": list(row.inputs), "state": state["state_hash"]}
    return {"exists": False, "state": state["state_hash"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--witnesses", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter()
    run = args.run
    verification = read(run/"verification.json")
    if not verification.get("sources_unchanged") or not verification.get("execution_completed"):
        raise ValueError("A completed sealed normal run is required before analysis")
    tasks = read(run/"frozen-tasks.json")["tasks"]["regression"]
    specification = read(args.witnesses)
    write(args.output/"diagnostic-inputs.json", specification)
    library = {h["id"]: h for h in read(run/"library-provenance.json")["definitions"]}
    costs, witnesses, groups = Counter(), [], {}
    for i, task in enumerate(tasks):
        program = term(specification["templates"][specification["task_template_indices"][i]])
        steps, out = gc.dag(program, fragment=dsl.FRAGMENT)
        records, objects, error = replay(steps, initial(task)["objects"], costs)
        proofs = [] if error else goal_proofs(task, objects, out, costs)
        witnesses.append({"task_index": i, "task_sha256": digest(task), "program": program,
            "steps": records, "output": out, "error": error,
            "goals_passed": bool(proofs) and all(p is not None for p in proofs),
            "goal_proofs": [asdict(p) if p else None for p in proofs]})
    write(args.output/"developer-witness-checks.json", witnesses)
    if not all(w["goals_passed"] for w in witnesses):
        raise ValueError("Diagnostic witness invalid; keep failure, do not alter normal results")

    def make_group(cohort, arm, index):
        st = initial(tasks[index])
        return {"cohort": cohort, "arm": arm, "index": index, "states": {st["state_hash"]: st},
            "events": Counter(), "families": {}, "step_stages": [Counter() for s in witnesses[index]["steps"]],
            "latest_selection": None, "refused_replay": [], "successful_state_events": 0}

    event_hasher = sha256()
    with (run/"events.jsonl").open("rb") as stream:
        for line_number, raw in enumerate(stream, 1):
            event_hasher.update(raw)
            e = json.loads(raw)
            if e["cohort"] not in {"regression", "diagnostic"}:
                continue
            key = (e["cohort"], e["arm"], e["task_index"])
            g = groups.setdefault(key, None)
            if g is None:
                g = groups[key] = make_group(*key)
            event = e["event"]
            g["events"][event] += 1
            if event == "semantic_state":
                g["states"][e["state_hash"]] = e
                g["successful_state_events"] += 1
            if event == "selection":
                g["latest_selection"] = e
            if event in {"selection", "refusal", "selected_execution", "candidate_scan"}:
                family = g["families"].setdefault(e["family"], Counter())
                family[event+":"+str(e.get("reason", e.get("disposition", e.get("produced_state", ""))))] += 1
            if event in {"candidate_scan", "selection", "refusal", "selected_execution", "candidate_order"}:
                parent_id = e.get("state") or g["latest_selection"]["state"]
                st = g["states"][parent_id]
                bindings = [v[1] for v in e["ordered"]] if event == "candidate_order" else [e["inputs"]]
                for binding in bindings:
                    actual = signature(e["family"], [st["objects"][n]["coordinates"] for n in binding])
                    for j, step in enumerate(witnesses[g["index"]]["steps"]):
                        if step["family"] == e["family"] and actual == signature(step["family"], step["input_coordinates"]):
                            stage = event+":"+str(e.get("reason", e.get("disposition", e.get("produced_state", ""))))
                            g["step_stages"][j][stage] += 1

            # Exhaustive over refused learned calls in the fresh 112-attempt
            # regression runs only, never picked by whether they help a goal.
            if event == "refusal" and e["cohort"] == "regression" and e["family"] in library:
                selected = g["latest_selection"]
                if selected["family"] != e["family"] or list(selected["inputs"]) != list(e["inputs"]):
                    raise ValueError("Refusal cannot be attributed to latest selection")
                st = g["states"][selected["state"]]
                cert = library[e["family"]]["exact_certificate"]
                mapping = dict(zip([p["name"] for p in cert["typed_parameters"]], e["inputs"], strict=True))
                composition = []
                for j, s in enumerate(cert["composition"]):
                    name = "diag_local"+str(j)
                    if name in st["objects"]:
                        raise ValueError("Diagnostic variable collision")
                    composition.append({"family": s["family"], "inputs": [mapping[n] for n in s["inputs"]], "output": name})
                    mapping[s["output"]] = name
                before = time.perf_counter()
                rec, objects, error = replay(composition, st["objects"], costs)
                old = {tuple(o["coordinates"]) for o in st["objects"].values()}
                new = {}
                for r in rec:
                    if tuple(r["coordinates"]) not in old:
                        new.setdefault(tuple(r["coordinates"]), r)
                checked = []
                for r in new.values():
                    proofs = goal_proofs(tasks[g["index"]], objects, r["output"], costs)
                    checked.append({"coordinates": r["coordinates"], "output": r["output"],
                        "satisfies_goal": bool(proofs) and all(p is not None for p in proofs),
                        "witness_step_outputs": [j for j, s in enumerate(witnesses[g["index"]]["steps"]) if s["coordinates"] == r["coordinates"]]})
                row = {"line": line_number, "state": selected["state"], "family": e["family"], "inputs": e["inputs"],
                    "normal_refusal": e["reason"], "primitive_replay_error": error,
                    "primitive_steps_completed": len(rec), "new_intermediate_points": checked,
                    "final_in_parent": None if error else tuple(objects[mapping[cert["output"]]]["coordinates"]) in old,
                    "diagnostic_seconds": time.perf_counter()-before}
                g["refused_replay"].append(row)

    autonomous = {}
    for arm in "ABCD":
        for i, row in enumerate(read(run/("regression-"+arm+".json"))):
            autonomous[("regression", arm, i)] = row
    for row in read(run/"diagnostic.json"):
        autonomous[("diagnostic", row["arm"], row["index"])] = row["result"]
    summaries = []
    for key, g in groups.items():
        task, witness = tasks[g["index"]], witnesses[g["index"]]
        all_xy = {tuple(o["coordinates"]) for s in g["states"].values() for o in s["objects"].values()}
        normal = autonomous[key]
        traces = []
        for step, stages in zip(witness["steps"], g["step_stages"], strict=True):
            containing = input_state_count(g["states"], step["input_coordinates"])
            traces.append({**step, "observed_events": dict(stages),
                "input_coordinates_seen_individually": [tuple(xy) in all_xy for xy in step["input_coordinates"]],
                "input_coexisting_state_count": len(containing),
                "output_seen": tuple(step["coordinates"]) in all_xy,
                "complete_grammar_probe": complete_grammar_probe(containing[0], task, step) if containing else None})
        duplicates = [r for r in g["refused_replay"] if r["normal_refusal"] == "duplicate_output_point"]
        summary = {"cohort": key[0], "arm": key[1], "task_index": key[2],
            "solved": normal["solved"], "stop_reason": normal["stop_reason"],
            "normal_costs": normal["costs"], "normal_seconds": normal["total_task_seconds"],
            "pending_streams": normal["pending_streams"], "retained_states": normal["retained_states"],
            "observed_unique_states_including_initial": len(g["states"]),
            "observed_state_count_matches_retained": len(g["states"]) == normal["retained_states"],
            "distinct_coordinate_point_sets": len({digest(sorted({tuple(o["coordinates"]) for o in s["objects"].values()})) for s in g["states"].values()}),
            "state_depth_counts": dict(Counter(s["depth"] for s in g["states"].values())),
            "events": dict(g["events"]), "families": g["families"], "witness_trace": traces,
            "refused_acquired_replays": len(g["refused_replay"]),
            "duplicate_refusals": len(duplicates),
            "duplicate_refusals_with_new_intermediates": sum(bool(r["new_intermediate_points"]) for r in duplicates),
            "discarded_intermediate_goal_hits": sum(p["satisfies_goal"] for r in duplicates for p in r["new_intermediate_points"]),
            "discarded_intermediate_witness_matches": sum(bool(p["witness_step_outputs"]) for r in duplicates for p in r["new_intermediate_points"])}
        summaries.append(summary)
        write(args.output/("refused-replays-"+"-".join(map(str, key))+".json"), g["refused_replay"])
        print(json.dumps({"group": key, "solved": normal["solved"], "discarded_new": summary["duplicate_refusals_with_new_intermediates"]}), flush=True)
    write(args.output/"failure-locations.json", summaries)
    report = {"completed": True, "baseline_sha": verification["sha"], "autonomous_successes_added": 0,
        "developer_witnesses_accepted": sum(w["goals_passed"] for w in witnesses),
        "developer_witnesses_not_autonomous_solutions": True, "event_sha256": event_hasher.hexdigest(),
        "witness_input_sha256": sha256(args.witnesses.read_bytes()).hexdigest(),
        "script_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "diagnostic_costs": dict(costs), "total_diagnostic_seconds": time.perf_counter()-start,
        "groups": len(summaries), "all_observed_state_counts_match": all(r["observed_state_count_matches_retained"] for r in summaries),
        "limitations": ["One developer-selected route per task, not all possible proofs.",
                        "Coordinates may coincide across different construction histories.",
                        "Primitive replay does not enlarge an acquired contract's certified scope.",
                        "Refused acquired replay covers all 112-application regression refusals, not 448-application diagnostic refusals."]}
    write(args.output/"verification.json", report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
