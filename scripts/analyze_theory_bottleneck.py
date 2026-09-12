"""Post-run diagnostics on discarded copies; no result is returned to learning."""
from collections import Counter
from pathlib import Path
import cProfile
import json
import pstats
import sys
import time

CONTROL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CONTROL))
from scripts.measure_persistent_learning import (
    Domain, Theory, read, write, size, digest, evaluate, metrics, final_comparison,
    theory_module, evaluation_copy)
from scripts.analyze_capacity_study import lineage


def jsonl(path):
    with Path(path).open(encoding="utf-8") as stream:
        for line in stream:
            yield json.loads(line)


def trace_blocked(state, observation_dir, output):
    """Reconstruct only existing compose/rewrite semantics at each expansion time."""
    before = digest(state)
    output.mkdir()
    domain = Domain(state["config"]["domain"])
    report = []
    for row in jsonl(observation_dir/"expansions.jsonl"):
        parent = state["concepts"][row["parent"]]
        if parent["seed"] or row.get("raw_size_permitted", 0) or not row["generated"]:
            continue
        cycle = row["cycle"]
        archived = {cid: c for cid, c in state["concepts"].items() if c["born"] < cycle}
        rules = [r for r in state["rewrite_rules"] if state["theorems"][r["theorem"]]["born"] < cycle]
        others = [state["concepts"][cid]["definition"] for cid in row["active"]]
        candidates = []
        for t in domain.compose(parent["definition"], others):
            reduced, deps, checks = theory_module.rewrite(t, rules, domain.scope, domain)
            value = domain.evaluate(reduced)
            key = domain.semantic_key(value)
            if domain.semantic_key(domain.evaluate(t)) != key:
                raise AssertionError("diagnostic rewrite changed semantics")
            duplicates = [cid for cid, c in archived.items()
                          if c["type"] == domain.type_of(t) and c["semantic_key"] == key]
            candidates.append({"term": t, "size": size(t), "type": domain.type_of(t),
                "excess": size(t)-row["term_cap"], "decision": "rejected_before_rewrite",
                "reduced": reduced, "reduced_size": size(reduced), "rules_used": deps,
                "rule_inspections": checks, "semantic_key": key, "semantic_duplicate_ids": duplicates,
                "semantic_scope": domain.scope})
        if len(candidates) != row["generated"]:
            raise AssertionError("candidate reconstruction differs from observed generation")
        changes = [r for r in jsonl(observation_dir/"cycles.jsonl")
                   if parent["id"] in r["selection_before_step"].get("active", []) and r["cycle"] <= cycle]
        result = {"concept": parent, "storage": "concept archive", "expansion": row,
            "first_observed_frontier_selection_cycle": changes[0]["cycle"] if changes else None,
            "rules_available": [r["theorem"] for r in rules],
            "candidate_count_without_size_filter": len(candidates),
            "candidate_types": dict(Counter(c["type"] for c in candidates)),
            "reduced_back_within_cap": sum(c["reduced_size"] <= row["term_cap"] for c in candidates),
            "semantic_duplicate_candidates": sum(bool(c["semantic_duplicate_ids"]) for c in candidates),
            "candidates": candidates, "origin": "post-run diagnostic, never acquired or resumed"}
        write(output/(parent["id"]+".json"), result)
        report.append({k: result[k] for k in ["candidate_count_without_size_filter", "reduced_back_within_cap", "semantic_duplicate_candidates"]} |
                      {"concept": parent["id"], "parent_size": parent["size"], "cycle": cycle})
    assert digest(state) == before
    write(output/"summary.json", report)
    return report


def used_rules(state, full):
    result = {t for row in full["rows"] for t in row["dependencies"]}
    for row in state["downstream"]:
        result.update(row.get("theorems", []))
    for q in state["conjectures"].values():
        for attempt in q["attempts"]:
            result.update(attempt.get("dependencies", []))
        result.update(q.get("certificate", {}).get("dependencies", []))
    return result & {r["theorem"] for r in state["rewrite_rules"]}


def ablations(state, suite, oracle, out, repeats=3, bound=32):
    out.mkdir()
    # Unbounded diagnostic collects dependencies even when a bounded call stops
    # before the existing code records its reduction dependencies.
    full_unbounded = evaluate(state, suite, oracle, repeats=1)
    useful = used_rules(state, full_unbounded)
    all_rules = {r["theorem"] for r in state["rewrite_rules"]}
    disabled_sets = {"full": set(), "useful-only": all_rules-useful,
                     "unused-only": useful, "none": all_rules}
    results = {}
    for name, disabled in disabled_sets.items():
        result = evaluate(state, suite, oracle, disabled=disabled, repeats=repeats, proof_node_budget=bound)
        write(out/(name+".json"), result)
        results[name] = {"disabled": sorted(disabled), **result["summary"]}
    write(out/"unbounded.json", full_unbounded)
    write(out/"summary.json", {"useful": sorted(useful), "results": results,
         "useful_definition": "actual held-out or later recorded reductions, selected only after training",
         "scope": "disable rule execution, retain established certificates; not retracting theorem truth"})
    return results


def match_counts(state, suite, disabled=()):
    """Count actual accepted rewrites and root pattern attempts via frame returns."""
    counts = Counter()
    rewrite_code, match_code = theory_module.rewrite.__code__, theory_module.match_term.__code__
    def observe(frame, event, arg):
        if event != "return":
            return
        if frame.f_code is rewrite_code:
            counts["rule_inspections"] += frame.f_locals["checks"]
            counts["accepted_replacements"] += len(frame.f_locals["dependencies"])
        elif frame.f_code is match_code and frame.f_back.f_code.co_name == "visit":
            counts["root_pattern_success" if arg else "root_pattern_failure"] += 1
    for task in suite:
        e = evaluation_copy(state, disabled)
        e.conjecture(task["left"], task["right"], kind=task["kind"])
        qid = next(iter(e.state["conjectures"]), None)
        if qid is not None:
            sys.setprofile(observe)
            try:
                e.settle(qid)
            finally:
                sys.setprofile(None)
    counts["inspections_without_applied_rewrite"] = counts["rule_inspections"]-counts["accepted_replacements"]
    return dict(counts)


def profile_queries(state, suite, oracle, out):
    out.mkdir()
    profiler = cProfile.Profile()
    profiler.enable()
    result = evaluate(state, suite, oracle, repeats=1)
    profiler.disable()
    profiler.dump_stats(str(out/"heldout.prof"))
    stats = pstats.Stats(profiler)
    rows = [{"file": key[0], "line": key[1], "function": key[2],
             "primitive_calls": val[0], "calls": val[1], "self_seconds": val[2], "inclusive_seconds": val[3]}
            for key, val in stats.stats.items()]
    rows.sort(key=lambda r: -r["self_seconds"])
    write(out/"functions.json", rows)
    counts = match_counts(state, suite)
    domain = Domain(state["config"]["domain"])
    keys = Counter((domain.type_of(r["left"]), domain.semantic_key(domain.evaluate(r["left"])),
                    domain.semantic_key(domain.evaluate(r["right"]))) for r in state["rewrite_rules"])
    write(out/"matching.json", {**counts, "active_rules": len(state["rewrite_rules"]),
        "semantic_duplicate_rules": sum(n-1 for n in keys.values()),
        "semantic_duplicate_note": "same exact left/right function values in declared scope; NOT interchangeable rewrite patterns",
        "counts_scope": "unbounded discarded held-out solve, includes repeated applied rules",
        "timing_note": "profiled diagnostic, not primary uninstrumented answer latency",
        "profiled_answer_summary": result["summary"]})
    # Existing functions, inclusive timing; nested quantities MUST NOT be added.
    categories = {"candidate_generation": {"compose"}, "canonicalisation": {"digest", "differential_expression", "semantic_key"},
                  "rule_lookup": {"rewrite", "visit"}, "semantic_matching": {"match_term"},
                  "certificate_lookup": set(), "proof": {"prove_identity"}, "execution": {"evaluate"}}
    write(out/"phases.json", {"phases": {name: [r for r in rows if r["function"] in names] for name, names in categories.items()},
        "note": "inclusive call profiles overlap; candidate generation absent in held-out solve; certificate scope checks inline in rewrite, not separately timed"})


def profile_later_steps(state, out):
    """Diagnostic replay only, not counted as autonomous new acquisitions."""
    original = digest(state)
    engine = Theory(state["config"], state=state, **state["flags"])
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(24):
        if not engine.step(): break
    profiler.disable()
    out.mkdir()
    profiler.dump_stats(str(out/"later-steps.prof"))
    rows = [{"file": k[0], "line": k[1], "function": k[2], "calls": v[1],
             "self_seconds": v[2], "inclusive_seconds": v[3]} for k, v in pstats.Stats(profiler).stats.items()]
    write(out/"functions.json", sorted(rows, key=lambda r: -r["self_seconds"]))
    write(out/"scope.json", {"origin": "discarded replay of at most24 existing next steps from saved cycle1000",
        "start_cycle": state["cycle"], "end_cycle": engine.state["cycle"],
        "decisions": engine.state["decisions"][len(state["decisions"]):],
        "not_counted_as_acquisitions": True})
    assert digest(state) == original


def candidate_census(state, observations, output):
    """Exact semantic duplicate census of generated, size-eligible syntax.

    Scope is the generated sequence, not admission decisions. The cost of this
    discarded analysis is not charged as if the learner did this computation.
    """
    domain, counts, seen, semantics = Domain(state["config"]["domain"]), Counter(), set(), set()
    started = time.perf_counter()
    for row in jsonl(observations/"expansions.jsonl"):
        parent = state["concepts"][row["parent"]]["definition"]
        others = [state["concepts"][cid]["definition"] for cid in row["active"]]
        for t in domain.compose(parent, others):
            counts["generated"] += 1
            if size(t) > row["term_cap"]:
                counts["size_rejected"] += 1
                continue
            key = digest(t)
            counts["size_eligible"] += 1
            if key in seen:
                counts["syntactic_duplicates"] += 1
                continue
            seen.add(key)
            semantic = (domain.type_of(t), domain.semantic_key(domain.evaluate(t)))
            if semantic in semantics: counts["semantic_duplicates_among_distinct_syntax"] += 1
            semantics.add(semantic)
    result = {**counts, "distinct_eligible_syntax": len(seen), "distinct_generated_semantics": len(semantics),
        "semantic_duplicate_fraction_distinct_syntax": 1-len(semantics)/len(seen) if seen else None,
        "analysis_seconds": time.perf_counter()-started,
        "scope": "post-run census of composition output; NOT all these expressions were admitted or evaluated by learner"}
    write(output, result)
    return result


def scheduler_trace(state, observations, output):
    """Every active-but-unexpanded concept, selected by state rather than ID."""
    pending = set(state["active_concepts"])-set(state["expanded"])
    streams, summaries = {}, {}
    output.mkdir()
    try:
        for row in jsonl(observations/"cycles.jsonl"):
            selection = row["selection_before_step"]
            for cid in pending:
                order = selection.get("unexpanded_order", [])
                if cid not in order:
                    continue
                if cid not in streams:
                    streams[cid] = (output/(cid+".jsonl")).open("w", encoding="utf-8")
                    summaries[cid] = {"concept": state["concepts"][cid], "first_selection_cycle": row["cycle"]}
                streams[cid].write(json.dumps({"cycle": row["cycle"], "unexpanded_position": order.index(cid),
                    "active_position": selection["active"].index(cid), "age": row["cycle"]-state["concepts"][cid]["born"],
                    "other_unexpanded": len(order)-1, "kind_options": selection["options"],
                    "open_conjectures": selection["open_conjectures"], "pending_terms": selection["pending_terms"],
                    "chosen": row["chosen"], "proof_calls": row["proof_calls"],
                    "rule_inspections": row["rule_inspections"], "engine_seconds": row["engine_seconds"]})+"\n")
        write(output/"summary.json", summaries)
    finally:
        for stream in streams.values(): stream.close()
    return summaries
