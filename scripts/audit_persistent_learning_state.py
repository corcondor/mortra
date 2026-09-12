"""Post-run diagnosis only; never resumes learning or changes its archive.

Inspect an existing Actions artifact, verify matching mathematical sources, and
call the existing active-set refresh on disposable terminal-state copies. This
is an intervention for diagnosis, not a new autonomous learning run.
"""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
import argparse
import hashlib
import json
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from math_os_prototype.representation_progress import digest
from math_os_prototype.theory_formation import Theory
from math_os_prototype.theory_domain import size
from scripts.run_theory_formation import source_seal, write


def portable_seal(value):
    normalized = {PureWindowsPath(k).as_posix(): v for k, v in value.items()}
    if len(normalized) != len(value):
        raise ValueError("ambiguous source paths")
    return normalized


def inspect_state(state):
    before = digest(state)
    engine = Theory(state["config"], **state["flags"], state=state)
    problems = []
    for rule in state["rewrite_rules"]:
        tid = rule["theorem"]
        if tid not in state["theorems"] or rule["scope"] != engine.domain.scope:
            problems.append({"kind": "rule_scope_or_parent", "theorem": tid})
        if rule.get("universal_pattern") and engine.domain.kind != "differential_ring":
            problems.append({"kind": "unlicensed_pattern", "theorem": tid})
    for tid, parents in state["proof_dependencies"].items():
        for parent in parents:
            if parent not in state["theorems"] or state["theorems"][parent]["born"] >= state["theorems"][tid]["born"]:
                problems.append({"kind": "dependency_not_earlier", "child": tid, "parent": parent})

    refusal_checks = []
    for rid, representation in state["representations"].items():
        if representation["scope"] != engine.domain.scope or representation["system_key"] != engine.domain.key:
            problems.append({"kind": "representation_scope", "representation": rid})
        changed = deepcopy(representation)
        changed["scope"]["legality"] = "collision-free"
        try:
            engine.domain.recurrence(changed, next(iter(engine.domain.actions)))
        except ValueError as exc:
            refusal_checks.append({"representation": rid, "refused": True, "reason": str(exc)})
        else:
            refusal_checks.append({"representation": rid, "refused": False})
            problems.append({"kind": "scope_change_accepted", "representation": rid})

    initial_options = engine.actions()
    original_active = set(engine.state["active_concepts"])
    dormant = []
    peers = [state["concepts"][cid]["definition"] for cid in state["active_concepts"]]
    seen = set(state["seen"])
    for cid, concept in state["concepts"].items():
        if cid in state["expanded"]:
            continue
        generated = list(engine.domain.compose(concept["definition"], peers))
        within = [t for t in generated if size(t) <= engine.budget["term_size"]]
        eligible = [t for t in within if digest(t) not in seen]
        dormant.append({
            "concept": cid, "acquired_cycle": concept["born"], "stored": True,
            "seed": concept["seed"], "type": concept["type"], "size": concept["size"],
            "active_at_stop": cid in original_active, "expanded": False,
            "syntax_continuations_within_size": len(within),
            "unseen_syntax_continuations": len(eligible),
            "invent_offered_at_stop": any(a["kind"] == "invent" for a in initial_options),
            "blocking_stage": "size_budget" if not within else "seen_filter" if not eligible else "frontier_insertion",
            "eligibility_note": "existing compose with terminal active peers; syntax only, not new acquisitions",
        })
    original_archive = {k: digest(engine.state[k]) for k in
                        ("concepts", "theorems", "representations", "procedures", "conjectures", "expanded", "pending_terms", "decisions", "costs")}
    engine.refresh_active()
    refreshed_options = engine.actions()
    if any(digest(engine.state[k]) != value for k, value in original_archive.items()):
        raise AssertionError("diagnosis changed mathematical archive or executed search")
    if engine.state["cycle"] != state["cycle"] or digest(state) != before:
        raise AssertionError("diagnosis advanced learning or mutated source snapshot")

    return {
        "cycle": state["cycle"], "stop_reason": state["stop_reason"],
        "dormant_concept_trace": dormant,
        "rule_count": len(state["rewrite_rules"]),
        "universal_pattern_rules": sum(bool(r.get("universal_pattern")) for r in state["rewrite_rules"]),
        "proof_dependency_edges": sum(map(len, state["proof_dependencies"].values())),
        "scope_refusals": refusal_checks, "scope_or_dependency_issues": problems,
        "scope_check_note": "structural/provenance checks and negative controls; not an independent full reproof",
        "before_option_kinds": dict(Counter(a["kind"] for a in initial_options)),
        "after_option_kinds": dict(Counter(a["kind"] for a in refreshed_options)),
        "active_before": len(original_active), "active_after": len(engine.state["active_concepts"]),
        "activated_concepts": sorted(set(engine.state["active_concepts"])-original_active),
        "unexpanded_active_after": sum(c not in state["expanded"] for c in engine.state["active_concepts"]),
        "archive_unchanged": True, "original_snapshot_unchanged": True,
        "executed_steps": 0, "capability_growth_measured": False,
        "diagnostic_intervention": "existing refresh_active on discarded copy; not autonomous continuation",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evidence = args.artifact.resolve()/"persistent-learning"
    output = args.output.resolve()
    if output.is_relative_to(args.artifact.resolve()):
        raise ValueError("diagnosis must not write into the original artifact")
    output.mkdir(parents=True, exist_ok=False)
    read = lambda p: json.loads(p.read_text(encoding="utf-8"))
    run = read(evidence/"verification.json")
    sources = source_seal()
    if portable_seal(sources) != portable_seal(read(evidence/"source-seal.json")):
        raise ValueError("mathematical code differs from artifact; do not mix baselines")
    result = {
        "origin": "post_run_diagnostic", "not_a_new_actions_run": True,
        "source_run_id": run["workflow_run_id"], "baseline_sha": run["baseline_sha"],
        "analysis_checkout_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "analysis_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "command": sys.argv, "python": sys.version, "platform": platform.platform(),
        "generated_at": datetime.now(timezone.utc).isoformat(), "states": {}, "errors": [],
    }
    for name, item in run["results"].items():
        path = (evidence/item["final_state"]).resolve()
        if not path.is_relative_to(evidence):
            raise ValueError("state path outside artifact")
        raw = path.read_bytes()
        try:
            result["states"][name] = {"input_file_sha256": hashlib.sha256(raw).hexdigest(),
                                      **inspect_state(json.loads(raw))}
        except Exception as exc:
            result["errors"].append({"state": name, "error": repr(exc)})
        if path.read_bytes() != raw:
            raise AssertionError("original evidence changed")
    result["sources_unchanged"] = source_seal() == sources
    result["audit_passed"] = result["sources_unchanged"] and not result["errors"] and all(
        not item["scope_or_dependency_issues"] for item in result["states"].values())
    write(output/"diagnosis.json", result)
    print(json.dumps(result, indent=2))
    return 0 if result["audit_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
