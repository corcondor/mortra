"""Fixed-library factorial evaluation. Ranking proposes; exact execution proves."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
from itertools import combinations, islice
import json
from pathlib import Path
import random
import time
import zipfile

from math_os_prototype import geometry_semantic_dsl as dsl
from math_os_prototype.representation_progress import digest
from math_os_prototype.runtime_typed_planner import RankedAlternative, _proof_program
from math_os_prototype.theory_geometry_feedback import GeometryLibrary, SemanticGeometryDomain
from worker.backend.geometry_proof_hypergraph import Atom, euclidean_relation_theorems
from worker.backend.typed_candidate_alignment import align_candidate_atoms, _forward_predicate_distances


def transferred_instances(tasks, seed, coordinate_range):
    """Freeze new inputs without executing a construction or reading a library."""
    rng = random.Random(seed)
    result = []
    low, high = coordinate_range
    for task in tasks:
        if task.get("predicates"):
            raise ValueError("random instances cannot silently drop input premises")
        for _ in range(10000):
            points = {n: [rng.randint(low, high), rng.randint(low, high)] for n in task["points"]}
            xy = list(points.values())
            if len({tuple(p) for p in xy}) != len(xy):
                continue
            if any((b[0]-a[0])*(c[1]-a[1]) == (b[1]-a[1])*(c[0]-a[0])
                   for a, b, c in combinations(xy, 3)):
                continue
            result.append(dict(deepcopy(task), points=points))
            break
        else:
            raise ValueError("instance generator exhausted declared rejection bound")
    return result


def read_inputs(spec, root):
    start = time.perf_counter()
    payload = (root/spec["path"]).read_bytes()
    if sha256(payload).hexdigest() != spec["sha256"]:
        raise ValueError("source evidence archive hash mismatch")
    with zipfile.ZipFile(root/spec["path"]) as z:
        def read(name, expected):
            data = z.read(spec["member_prefix"]+name)
            if sha256(data).hexdigest() != expected:
                raise ValueError("frozen input member hash mismatch: "+name)
            return json.loads(data)
        definitions = read("C-archive.json", spec["library_sha256"])
        plan = read("frozen-plan.json", spec["plan_sha256"])
    return definitions, plan, time.perf_counter()-start


class SelectionDomain(SemanticGeometryDomain):
    def __init__(self, *args, guided=False, original_order_every=4, **kwargs):
        self.rank_fair_rounds = guided
        self.original_order_every = original_order_every
        self.solutions_by_state = {}
        self.proposal_audit = []
        super().__init__(*args, policy="SOLVE", **kwargs)
        started = time.perf_counter()
        self.relation_distances = ({p: _forward_predicate_distances(euclidean_relation_theorems(), {p})
            for p in {g["predicate"] for g in self.task["goals"]}} if guided else {})
        self.costs["selection_setup_seconds"] += time.perf_counter()-started

    def alignment(self, family, inputs):
        cert = (self.contracts[family]["exact_certificate"] if family in self.contracts
                else self.bank.schemas[family])
        names = [p["name"] for p in cert["typed_parameters"]]
        binding = dict(zip(names, inputs, strict=True))
        # Fresh symbolic names denote promised construction outputs, never
        # guessed coordinates. All goal conjuncts refer to the SAME output.
        namespace = "__pending_"+digest([family, inputs])+"_"
        if any(n.startswith(namespace) for n in inputs):
            raise ValueError("ranking placeholder collision")
        for step in cert["composition"]:
            binding[step["output"]] = namespace+step["output"]
        output = binding[cert["output"]]
        effects = [Atom(r["predicate"], tuple(binding[n] for n in r["points"]))
                   for r in cert["guaranteed_relation"]]
        goals = [Atom(g["predicate"], tuple(output if n == "u" else n for n in g["points"]))
                 for g in self.task["goals"]]
        return align_candidate_atoms(effects, goals, self.relation_distances)

    def proposals(self, family, state, rows=None, offset=0):
        # Ranking may permute a page but never removes its remaining stream.
        rows = self.candidate_rows(family, state) if rows is None else rows
        rows = [r for r in rows if (family, self.key(state), tuple(r.inputs)) not in self.attempted]
        start = time.perf_counter()
        scores = [self.alignment(family, tuple(r.inputs)) for r in rows] if self.rank_fair_rounds else [None]*len(rows)
        order = list(range(len(rows)))
        if self.rank_fair_rounds:
            order.sort(key=lambda i: scores[i].rank)
            self.costs["selection_alignment_calls"] += len(scores)
        self.costs["selection_seconds"] += time.perf_counter()-start
        before = [(r.family, list(r.inputs)) for r in rows]
        after = [before[i] for i in order]
        invariant = sorted(before) == sorted(after)
        if not invariant:
            raise ValueError("selection changed candidate membership")
        audit = {"event": "candidate_order", "state": self.key(state), "family": family, "offset": offset,
            "original": before, "ordered": after, "set_sha256": digest(sorted(before)),
            "permutation_passed": invariant, "guided": self.rank_fair_rounds,
            "alignment": [s.to_dict() if s else None for s in scores],
            "postconditions_are_conditional_proposals_not_facts": True}
        self.proposal_audit.append({"state": audit["state"], "family": family,
                                    "set_sha256": audit["set_sha256"], "count": len(rows), "offset": offset})
        self.costs["proposed_candidates"] += len(rows)
        self.emit(audit)
        return [(rows[i], scores[i], i, rank) for rank, i in enumerate(order)]

    def alternatives(self, family, state):
        def pages():
            if self.enumeration == "legacy_prefix":
                yield self.proposals(family, state)
                return
            stream, offset = iter(self.candidate_rows(family, state)), 0
            width = self.config.get("ranking_window", 16)
            if width < 1:
                raise ValueError("ranking window must be positive")
            while page := list(islice(stream, width)):
                yield self.proposals(family, state, page, offset)
                offset += len(page)
        for row, alignment, original, rank in (row for page in pages() for row in page):
            attempt = (family, self.key(state), tuple(row.inputs))
            def invoke(row=row, attempt=attempt, alignment=alignment, original=original, rank=rank):
                self.emit({"event": "selection", "family": family, "inputs": list(row.inputs),
                    "state": self.key(state), "original_position": original, "ordered_position": rank,
                    "alignment": alignment.to_dict() if alignment else None})
                result = self.apply(state, row, attempt)
                self.emit({"event": "selected_execution", "family": family, "inputs": list(row.inputs),
                    "state": self.key(state), "produced_state": result is not None})
                return result
            yield RankedAlternative(invoke, alignment.rank if alignment else ())

    def is_goal(self, state):
        key = self.key(state)
        if key in self.solutions_by_state:
            self.solution = deepcopy(self.solutions_by_state[key])
            return True
        passed = super().is_goal(state)
        if passed:
            self.solution.update(state_hash=key,
                construction_ancestors=[asdict(call) for call in state.history])
            self.solutions_by_state[key] = deepcopy(self.solution)
        return passed

    def search(self, applications):
        row = super().search(applications)
        row["proposal_sets"] = self.proposal_audit
        if row["solved"]:
            goal_fact = next(f for f in self.facts if self.key(f.value) == self.solution["state_hash"])
            row["construction_proof_dag"] = _proof_program([goal_fact], {f.id: f for f in self.facts})
            row["acquired_ancestor_calls"] = [c["morphism"] for c in self.solution["construction_ancestors"]
                if c["provenance"]["origin"] == "acquired"]
        return row


def compare_memberships(left, right):
    def index(rows):
        return {(r["state"], r["family"], r.get("offset", 0), r.get("count", 0)): r["set_sha256"] for r in rows}
    a, b = index(left), index(right)
    common = a.keys() & b.keys()
    return {"common_state_families": len(common),
            "mismatches": sum(a[k] != b[k] for k in common)}


def summarize(rows):
    costs = Counter()
    for row in rows:
        costs.update(row["costs"])
    return {"tasks": len(rows), "solved": sum(r["solved"] for r in rows),
        "task_seconds": sum(r["total_task_seconds"] for r in rows), "costs": dict(costs),
        "answer_term_acquired_calls": sum(len(r["solution"]["acquired_calls"]) for r in rows if r["solved"]),
        "solved_with_acquired_ancestors": sum(bool(r.get("acquired_ancestor_calls")) for r in rows)}


def factorial(rows):
    summaries = {k: summarize(v) for k, v in rows.items()}
    fields = ("solved", "task_seconds")
    interaction = {f: (summaries["D"][f]-summaries["C"][f])-(summaries["B"][f]-summaries["A"][f]) for f in fields}
    interaction["costs"] = {key: (summaries["D"]["costs"].get(key, 0)-summaries["C"]["costs"].get(key, 0))
        -(summaries["B"]["costs"].get(key, 0)-summaries["A"]["costs"].get(key, 0))
        for key in set().union(*(r["costs"] for r in summaries.values()))}
    paired = [{"task_sha256": a["task_sha256"],
        "solved": {k: rows[k][i]["solved"] for k in rows},
        "solve_interaction": int(rows["D"][i]["solved"])-int(rows["C"][i]["solved"])
            -int(rows["B"][i]["solved"])+int(a["solved"])} for i, a in enumerate(rows["A"])]
    common = [i for i in range(len(rows["A"])) if all(rows[k][i]["solved"] for k in rows)]
    return {"arms": summaries, "interaction_D_minus_C_minus_B_plus_A": interaction,
        "paired": paired, "common_solved_count": len(common),
        "common_solved_costs": {k: summarize([v[i] for i in common]) for k, v in rows.items()},
        "interpretation": "Counts: positive favors complementarity. Costs: negative favors cost reduction. Not a scalar reward or a statistical population claim."}


def run_selection_factorial(config, output, *, frozen_inputs=None):
    started = time.perf_counter()
    root = Path(__file__).resolve().parents[1]
    io_seconds = 0.0
    def write(name, data):
        nonlocal io_seconds
        start = time.perf_counter()
        (output/name).write_text(json.dumps(data, indent=2)+"\n", encoding="utf-8")
        io_seconds += time.perf_counter()-start
    definitions, source_plan, load_seconds = (read_inputs(config["source_archive"], root)
        if frozen_inputs is None else frozen_inputs)
    protocol = config["protocol"]
    cohorts = {"regression": source_plan["evaluation"], "transfer": transferred_instances(
        source_plan["evaluation"], protocol["holdout_seed"], protocol["holdout_coordinate_range"])}
    frozen = {k: [digest(t) for t in tasks] for k, tasks in cohorts.items()}
    if set(frozen["transfer"]) & {digest(t) for t in source_plan["training"]+source_plan["evaluation"]}:
        raise ValueError("new instance overlaps old input")
    write("frozen-tasks.json", {"tasks": cohorts, "hashes": frozen, "protocol": protocol})
    archive_hash = digest(definitions)
    write("library-provenance.json", {"source": config["source_archive"], "library_sha256": archive_hash,
        "definitions": [{k: h[k] for k in ("id", "parameters", "body", "parents", "generation", "exact_certificate")} for h in definitions]})
    setup = time.perf_counter()
    bank = GeometryLibrary()
    for h in definitions:
        bank.register(h)
    setup_seconds = time.perf_counter()-setup
    sealed = digest(bank.archive)
    events = (output/"events.jsonl").open("w", encoding="utf-8")
    event_seconds = 0.0
    def emitter(cohort, label, index):
        def emit(event):
            nonlocal event_seconds
            start = time.perf_counter()
            events.write(json.dumps({"cohort": cohort, "arm": label, "task_index": index, **event})+"\n")
            event_seconds += time.perf_counter()-start
        return emit
    conditions = protocol["conditions"]
    if conditions != {"A": [False, False], "B": [False, True], "C": [True, False], "D": [True, True]}:
        raise ValueError("expected preregistered 2x2 design")
    def execute(task, label, cohort, index, search, applications):
        begin = time.perf_counter()
        enabled, guided = conditions[label]
        domain = SelectionDomain(task, search, bank, guided=guided,
            original_order_every=protocol["fair_original_round_every"],
            active=[h["id"] for h in bank.archive] if enabled else (), emit=emitter(cohort, label, index))
        row = domain.search(applications)
        row["total_task_seconds"] = time.perf_counter()-begin
        row["active_size"] = len(domain.active)
        row["archive_sha256"] = sealed
        if row["solved"] and not row["solution"]["replay"]["passed"]:
            raise ValueError("unreplayed solution")
        print(json.dumps({"cohort": cohort, "arm": label, "index": index,
            "solved": row["solved"], "candidates": row["costs"].get("candidate_expansions", 0)}), flush=True)
        return row
    results, checks = {}, []
    try:
        for cohort, tasks in cohorts.items():
            rows = {k: [] for k in conditions}
            # Rotate execution order without changing input order or RNG.
            for i, task in enumerate(tasks):
                labels = list(conditions)
                labels = labels[i % 4:]+labels[:i % 4]
                for label in labels:
                    rows[label].append(execute(task, label, cohort, i, config["search"], config["applications"]))
                    write(cohort+"-"+label+".json", rows[label])
                for a, b in (("A", "B"), ("C", "D")):
                    check = compare_memberships(rows[a][-1]["proposal_sets"], rows[b][-1]["proposal_sets"])
                    checks.append(dict(check, cohort=cohort, task=i, arms=[a, b]))
                    if check["mismatches"]:
                        raise ValueError("same-state candidate membership differed")
            results[cohort] = rows
            write(cohort+"-comparison.json", factorial(rows))
        diagnostic = []
        spec = config["diagnostic"]
        if spec["enabled"]:
            for i, task in enumerate(cohorts["regression"]):
                if results["regression"]["A"][i]["solved"]:
                    continue
                for label in spec["conditions"]:
                    search = dict(config["search"], max_primitive_operations=spec["max_primitive_operations"],
                                  wall_seconds=spec["wall_seconds"])
                    row = execute(task, label, "diagnostic", i, search, spec["applications"])
                    diagnostic.append({"index": i, "arm": label, "result": row,
                        "conclusion": "replayed_existence_witness" if row["solved"] else "unresolved_within_budget"})
                    write("diagnostic.json", diagnostic)
    finally:
        close_started = time.perf_counter()
        events.close()
        event_seconds += time.perf_counter()-close_started
    if sealed != digest(bank.archive) or archive_hash != digest(definitions):
        raise ValueError("fixed library changed during evaluation")
    write("candidate-membership-checks.json", checks)
    report = {"execution_completed": True, "experiment": "fixed_library_by_contract_order_2x2",
        "summary": {k: factorial(v) for k, v in results.items()}, "library_size": len(bank.archive),
        "library_unchanged": True, "reacquisitions": 0, "policy_learning": False,
        "source_load_seconds": load_seconds, "shared_certificate_revalidation_seconds": setup_seconds,
        "shared_certificate_costs": dict(bank.costs), "json_output_seconds": io_seconds,
        "event_output_seconds_included_in_task_time": event_seconds,
        "candidate_membership_checks": len(checks), "candidate_membership_mismatches": 0,
        "diagnostic_witnesses": sum(r["result"]["solved"] for r in diagnostic),
        "diagnostic_tasks": len(diagnostic), "total_seconds": time.perf_counter()-started,
        "scope": "exact rational configurations; transfer instances use previously seen goal templates",
        "selection_postconditions_not_used_as_proof": True,
        "diagnostic_failures_are_not_impossibility_proofs": True}
    write("result.json", report)
    return report


def run_complete_revalidation(config, output):
    """Reacquire from initial DSL, then freeze that run's library for selection."""
    from math_os_prototype.theory_geometry_feedback import run_semantic_feedback
    from math_os_prototype.geometry_execution_audit import aggregate_geometry_events
    root = Path(__file__).resolve().parents[1]
    acquisition_path = root/config["acquisition_config"]
    selection_path = root/config["selection_config"]
    acquisition = json.loads(acquisition_path.read_text(encoding="utf-8"))
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    source_hashes = {str(p.relative_to(root)): sha256(p.read_bytes()).hexdigest()
                     for p in (acquisition_path, selection_path)}
    for stage in (acquisition, selection):
        stage["search"].pop("per_family_limit", None)
        stage["search"].pop("max_input_tuples", None)
        stage["search"].update(config["search_overrides"])
        if stage["search"]["candidate_enumeration"] != "complete":
            raise ValueError("revalidation must enumerate complete candidate streams")
    if config.get("development_cycles") is not None:
        acquisition["cycles"] = config["development_cycles"]
    selection.pop("source_archive")
    (output/"frozen-stage-inputs.json").write_text(json.dumps({
        "acquisition": acquisition, "selection": selection,
        "source_config_hashes": source_hashes,
        "old_library_loaded": False}, indent=2)+"\n", encoding="utf-8")
    aout, sout = output/"acquisition", output/"selection"
    aout.mkdir()
    sout.mkdir()
    acquired = run_semantic_feedback(acquisition, aout)
    current_library = aout/"C-archive.json"
    source_plan = aout/"frozen-plan.json"
    definitions = json.loads(current_library.read_text(encoding="utf-8"))
    plan = json.loads(source_plan.read_text(encoding="utf-8"))
    selection["source_archive"] = {"kind": "current_normal_run_acquisition",
        "path": "acquisition/C-archive.json",
        "sha256": sha256(current_library.read_bytes()).hexdigest(),
        "plan_sha256": sha256(source_plan.read_bytes()).hexdigest()}
    compared = run_selection_factorial(selection, sout, frozen_inputs=(definitions, plan, 0.0))
    for folder in (aout, sout):
        (folder/"operation-predicate-audit.json").write_text(
            json.dumps(aggregate_geometry_events(folder/"events.jsonl"), indent=2)+"\n", encoding="utf-8")
    unchanged = all(sha256((root/p).read_bytes()).hexdigest() == h for p, h in source_hashes.items())
    return {"execution_completed": acquired["execution_completed"] and compared["execution_completed"] and unchanged,
        "candidate_enumeration": "complete", "old_library_loaded": False,
        "acquisition": acquired, "selection": compared,
        "source_configs_unchanged": unchanged}
