"""Read-only replay of a completed geometry contract acquisition experiment."""
from pathlib import Path
import argparse
import json
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from math_os_prototype import geometry_contracts as gc
from math_os_prototype import library_compression as library
from math_os_prototype.representation_progress import digest
from math_os_prototype.theory_geometry_acquisition import independent_replay, task_identity


def replay(folder):
    started = time.perf_counter()
    def read(name):
        return json.loads((folder/name).read_text(encoding="utf-8"))
    plan, training, learned = read("frozen-plan.json"), read("training.json"), read("acquisition.json")
    comparisons, verification = read("comparisons.json"), read("verification.json")
    errors, certificates, proofs, sources = [], [], [], []
    if verification["plan_sha256"] != digest(plan) or not verification["sources_unchanged"]:
        errors.append("plan or source freeze failed")
    if verification["archive_sha256"] != digest(read("archive.json")):
        errors.append("archive digest mismatch")
    if verification["frozen_library_sha256"] != digest(read("frozen-library.json")):
        errors.append("frozen library digest mismatch")
    known = {digest(r["proof"]): r for r in training if r["solved"]}
    corpus = {c["source_proof"]: c for c in learned["corpus"]}
    for i, row in enumerate(training):
        if not row["solved"]:
            continue
        def qualify(term):
            return gc.point(f"trace{i}_"+term["name"]) if term["op"] == "var" else {
                "op": term["op"], "args": [qualify(a) for a in term["args"]]}
        if corpus.get(digest(row["proof"]), {}).get("program") != qualify(row["proof"]["term"]):
            errors.append("training proof and abstraction input differ")
    for h in learned["archive"]:
        valid, cost = gc.replay_contract(h)
        certificates.append({"id": h["id"], "passed": valid, "cost": cost})
        if not valid:
            errors.append("contract mismatch: "+h["id"])
        for source in h["source_proof_traces"]:
            original = known.get(source["source_proof"])
            c = corpus.get(source["source_proof"])
            with library.grammar(gc.validate):
                matches = library.match_sites(h["template"], c["program"]) if c else []
                body = gc.body_from_template(h["template"])
                roundtrip = all(library.instantiate_term(h["template"], m["binding"]) == m["subterm"] for m in matches)
            passed = bool(original and c and matches == source["matches"] and matches and roundtrip
                          and body == h["body"] and task_identity(original["task"]) == source["task_sha256"])
            sources.append({"id": h["id"], "source": source["source_proof"], "passed": passed})
            if not passed:
                errors.append("acquisition source mismatch: "+h["id"])
    if [task_identity(r["task"]) for r in training] != [task_identity(t) for t in plan["training"]]:
        errors.append("training task sequence mismatch")
    for label, rows in {"training": training, **comparisons}.items():
        if label != "training" and [task_identity(r["task"]) for r in rows] != [task_identity(t) for t in plan["evaluation"]]:
            errors.append("evaluation task sequence mismatch: "+label)
        for result in rows:
            archive = {h["id"]: h for h in learned["archive"]}
            if result["solved"]:
                actual_calls = []
                for action in result["proof_actions"]:
                    if action["family"] not in archive:
                        continue
                    h = archive[action["family"]]
                    binding = dict(zip(gc.parameters(h["body"]), action["inputs"], strict=True))
                    def instantiate(node):
                        return result["state"]["terms"][binding[node["name"]]] if node["op"] == "var" else {
                            "op": node["op"], "args": [instantiate(a) for a in node["args"]]}
                    if h["body"] != action["body"] or instantiate(h["body"]) != action["term"]:
                        errors.append("H execution/body mismatch: "+action["family"])
                    actual_calls.append(h["id"])
                if actual_calls != result["goal_acquired_calls"]:
                    errors.append("proof dependency call mismatch")
            checked = independent_replay(result)
            proofs.append({"phase": label, "task": result["task"]["id"], **checked})
            if checked["checked"] and not checked["passed"]:
                errors.append("invalid proof: "+label+"/"+result["task"]["id"])
    return {"passed": not errors, "errors": errors, "certificates": certificates,
            "sources": sources, "proofs": proofs, "seconds": time.perf_counter()-started,
            "scope": gc.SCOPE, "independence": "primitive execution bypasses stored H witnesses; shares existing exact arithmetic backend",
            "minimal_chain_passed": verification["minimal_chain_passed"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--require-chain", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("do not overwrite a previous replay")
    result = replay(args.run)
    args.output.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] and (result["minimal_chain_passed"] or not args.require_chain) else 1


if __name__ == "__main__":
    raise SystemExit(main())
