"""Fixed-input normal runs, persistent DSL replay and isolated held-out evaluation.

No learned body is supplied to a normal run. Evaluation never mutates its
archive. Computational correctness is a gate; capability improvement is a
separate measured outcome and is permitted to be absent.
"""
from pathlib import Path
import argparse
import hashlib
from copy import deepcopy
import json
import os
import random
import statistics
import subprocess
import sys
import time
from unittest.mock import patch
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from math_os_prototype import library_compression as lib
from math_os_prototype.theory_domain import Domain, term, size
from math_os_prototype.theory_formation import Theory
from math_os_prototype.theory_vocabulary import references
from math_os_prototype.representation_progress import digest
from scripts.run_theory_formation import write, source_seal
from scripts.verify_theory_formation import replay


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def heldout(config, count=48):
    d = Domain(config["domain"])
    rng = random.Random(739182)
    def generate(depth):
        if depth == 0:
            return deepcopy(rng.choice(d.seeds()))
        op = rng.choice([o for o in d.operations if o in {"add", "mul", "neg", "diff", "pull"}])
        args = [generate(depth-1)]
        if op in {"add", "mul"}:
            args.append(generate(depth-1))
        return term(op, *args, **({"label": rng.choice(list(d.actions))} if op == "pull" else {}))
    return {"seed": 739182, "origin": "external_heldout", "feedback_to_learner": False,
            "programs": [generate(rng.randrange(1, 5)) for _ in range(count)],
            "words": [[rng.choice(list(d.actions)) for _ in range(n)]
                      for n in [7, 11, 17, 23]] if d.actions else [],
            "natural_arguments": [29, 47, 71],
            "note": "words and natural arguments frozen before acquisition; observed q chosen by learner"}


def engine(state):
    return Theory(state["config"], state=state, **state["flags"])


def compress(program, e, enabled):
    result, checks = deepcopy(program), 0
    if not enabled:
        return result, checks
    with lib.grammar(e.vocabulary.accepts):
        while True:
            before = lib.cost(result)
            for d in e.state["dsl"]["definitions"]:
                checks += len(lib.subterms(result))
                sites = lib.select_sites(lib.match_sites(d["template"], result))
                changed = lib.rewrite(result, d["index"], d["template"], sites)
                if lib.cost(changed) < lib.cost(result):
                    result = changed
            if lib.cost(result) == before:
                break
    return result, checks


def evaluate(state, tasks, enabled):
    e = engine(state)
    before = digest(e.state)
    rows = []
    training = {digest(r["primitive"]) for r in e.state["dsl"]["corpus"]}
    # A stored definition may expand while disabled; no references are removed.
    with patch.object(e.domain, "acquire", side_effect=AssertionError("evaluation reacquired a representation")) as acquire, \
         patch.object(e.domain, "settle", side_effect=AssertionError("evaluation re-proved a task")) as prover:
        for i, primitive in enumerate(tasks["programs"]):
            start = time.perf_counter()
            program, checks = compress(primitive, e, enabled)
            search_seconds = time.perf_counter()-start
            start = time.perf_counter()
            actual, cost = e.vocabulary.evaluate(program)
            execution_seconds = time.perf_counter()-start
            expected = e.domain.evaluate(primitive)
            agree = e.domain.semantic_key(actual) == e.domain.semantic_key(expected)
            if not agree:
                raise AssertionError("held-out exact semantics changed")
            rows.append({"task": i, "program": program, "agree": agree,
                         "in_training": digest(primitive) in training,
                         "definitions_called": sorted(references(program)),
                         "before_bits": lib.cost(primitive), "after_bits": lib.cost(program),
                         "matching_checks": checks, "execution_cost": cost,
                         "search_seconds": search_seconds, "execution_seconds": execution_seconds})
        representation_uses, recurrence_uses, refusals = [], [], []
        if enabled:
            for rid in e.state["dsl"]["observation_operations"]:
                for word in tasks["words"]:
                    program = term("represented", term("word", letters=word), binding=rid)
                    actual, costs = e.vocabulary.evaluate(program)
                    expected = e.domain.evaluate(e.vocabulary.primitive(program))
                    if actual != expected:
                        raise AssertionError("unseen word result differs")
                    representation_uses.append({"binding": rid, "word": word,
                        "all_states_agree": True, "costs": costs, "acquisition_calls": 0,
                        "prover_calls": 0, "new_argument": not any(r["program"] == program for r in e.state["dsl"]["executions"])})
                try:
                    e.vocabulary.evaluate(program, requirements={"legality": "collision-free"})
                except ValueError as exc:
                    refusals.append({"binding": rid, "refused": True, "reason": str(exc)})
                else:
                    raise AssertionError("unsupported legality used")
            for pid in e.state["dsl"]["recurrence_operations"]:
                for n in tasks["natural_arguments"]:
                    program = term("recurrence", term("natural", value=n), procedure=pid)
                    actual, costs = e.vocabulary.evaluate(program)
                    expected = e.domain.evaluate(e.vocabulary.primitive(program))
                    if actual != expected:
                        raise AssertionError("unseen recurrence argument differs")
                    recurrence_uses.append({"procedure": pid, "n": n, "agree": True,
                        "costs": costs, "acquisition_calls": 0, "prover_calls": 0,
                        "new_argument": not any(r["program"] == program for r in e.state["dsl"]["executions"])})
        if acquire.call_count or prover.call_count:
            raise AssertionError("reacquisition or task reproving occurred")
    if digest(e.state) != before:
        raise AssertionError("held-out evaluation changed knowledge")
    return {"rows": rows, "solved": sum(r["agree"] for r in rows),
        "unseen_solved": sum(r["agree"] and not r["in_training"] for r in rows),
        "matching_checks": sum(r["matching_checks"] for r in rows),
        "program_bits": sum(r["after_bits"] for r in rows),
        "median_search_seconds": statistics.median(r["search_seconds"] for r in rows),
        "median_execution_seconds": statistics.median(r["execution_seconds"] for r in rows),
        "definition_bits": sum(d["definition_bits"] for d in e.state["dsl"]["definitions"]) if enabled else 0,
        "representation_uses": representation_uses, "recurrence_uses": recurrence_uses,
        "refusals": refusals, "archive_unchanged": True,
        "note": "expression evaluation, not a proof-search or unsolved-problem benchmark"}


def inspect(state):
    e = engine(state)
    s = e.state["dsl"]
    for definition in s["definitions"]:
        if any(int(ref) >= definition["index"] for ref in definition["dependencies"]):
            raise AssertionError("forward or cyclic acquired definition")
    for row in s["corpus"]:
        if e.vocabulary.primitive(row["program"]) != row["primitive"]:
            raise AssertionError("persistent library changed original computation")
    for row in s["executions"]:
        actual, _ = e.vocabulary.evaluate(row["program"])
        expected = e.domain.evaluate(row["primitive"])
        if e.domain.semantic_key(actual) != e.domain.semantic_key(expected):
            raise AssertionError("saved program fails fresh semantic replay")
    edges = []
    for g in s["definitions"]:
        sources = set(g["acquisition_sources"])
        for row in s["executions"]:
            if digest(row["program"]) not in sources or row["cycle"] >= g["born"]:
                continue
            for ref in references(row["program"]) & set(g["dependencies"]):
                h = s["definitions"][int(ref)]
                if h["born"] < row["cycle"]:
                    edges.append({"h": h, "execution": row, "g": g})
    primitive_bits = sum(lib.cost(r["primitive"]) for r in s["corpus"])
    corpus_bits = sum(lib.cost(r["program"]) for r in s["corpus"])
    definitions_bits = sum(d["definition_bits"] for d in s["definitions"])
    return {"definitions": len(s["definitions"]), "execution_count": len(s["executions"]),
        "max_definition_depth": max([d["depth"] for d in s["definitions"]] or [0]),
        "actual_feedback_edges": edges, "corpus_primitive_bits": primitive_bits,
        "corpus_dsl_bits": corpus_bits, "definition_bits": definitions_bits,
        "net_code_bits_saved": primitive_bits-corpus_bits-definitions_bits,
        "full_archive_bits": lib.cost(s)+lib.cost(e.state["observable_spaces"])+lib.cost(e.state["representations"]),
        "spaces": len(e.state["observable_spaces"]), "readouts": len(e.state["representations"]),
        "source_scope": e.domain.scope,
        "code_cost_note": "canonical JSON code + each body once; certificate/provenance archive measured separately",
        "cycle": state["cycle"], "costs": state["costs"], "seconds": state["seconds"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, action="append", required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    source = source_seal()
    summary = {"sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "repository": os.environ.get("GITHUB_REPOSITORY", "corcondor/mortra"),
        "ref": os.environ.get("GITHUB_REF"), "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
        "generated_at": datetime.now(timezone.utc).isoformat(), "python": sys.version,
        "source_seal": source, "commands": [], "experiments": {}, "errors": [], "passed": False}
    write(args.output/"verification.json", summary)
    # Freeze every held-out input before any acquisition subprocess is launched.
    for path in args.config:
        config = read(path)
        write(args.output/(path.stem+"-config.json"), config)
        write(args.output/(path.stem+"-heldout.json"), heldout(config))
    for path in args.config:
        try:
            config, states = read(path), {}
            tasks = read(args.output/(path.stem+"-heldout.json"))
            for condition in ["initial-only", "learn", "no-dsl"]:
                previous = None
                phases = ["initial"] if condition == "initial-only" else ["first", "resumed"]
                for phase in phases:
                    output = args.output/f"{path.stem}-{condition}-{phase}"
                    command = [sys.executable, str(ROOT/"scripts/run_theory_formation.py"),
                        "--config", str(path.resolve()), "--output", str(output.resolve()), "--condition", condition]
                    if phase == "first":
                        command += ["--cycles", str(config["budget"]["cycles"]//2)]
                    if previous:
                        command += ["--resume", str(previous/"state.json")]
                    summary["commands"].append(command)
                    write(args.output/"verification.json", summary)
                    with output.with_suffix(".log").open("w", encoding="utf-8") as log:
                        subprocess.run(command, cwd=ROOT, check=True, stdout=log, stderr=subprocess.STDOUT,
                                       timeout=config["budget"]["seconds"]+180)
                    state = read(output/"state.json")
                    if not read(output/"verification.json")["sources_unchanged"]:
                        raise AssertionError("normal-run code changed")
                    if previous:
                        prior = read(previous/"state.json")
                        for d in prior["dsl"]["definitions"]:
                            if d["template"] != state["dsl"]["definitions"][d["index"]]["template"]:
                                raise AssertionError("previous definition changed on resume")
                    previous = output
                states[condition] = state
            observations = {name: inspect(s) for name, s in states.items()}
            replays = {name: replay(s) for name, s in states.items()}
            if not all(r["passed"] for r in replays.values()):
                raise AssertionError("fresh proof replay failed")
            evaluations = {"A_initial": evaluate(states["initial-only"], tasks, False),
                "B_acquired": evaluate(states["learn"], tasks, True),
                "C_same_archive_disabled": evaluate(states["learn"], tasks, False),
                "C_no_dsl_run": evaluate(states["no-dsl"], tasks, False)}
            a, b, c = [evaluations[k] for k in ["A_initial", "B_acquired", "C_same_archive_disabled"]]
            learned = observations["learn"]
            summary["experiments"][path.stem] = {"observations": observations, "replay": replays,
                "evaluations": evaluations,
                "verdicts": {"shared_spaces": learned["readouts"] > learned["spaces"] > 0,
                    "dsl_growth": learned["definitions"] > 0,
                    "subsequent_execution": learned["execution_count"] > 0,
                    "execution_to_next_definition": bool(learned["actual_feedback_edges"]),
                    "training_net_code_reduction": learned["net_code_bits_saved"] > 0,
                    "heldout_net_code_reduction": a["program_bits"] > b["program_bits"]+b["definition_bits"],
                    "heldout_solved_gain": b["solved"]-a["solved"]},
                "heldout_bits_saved_before_definition_cost": c["program_bits"]-b["program_bits"],
                "all_original_tasks_already_evaluable": True}
            write(args.output/(path.stem+"-evaluation.json"), summary["experiments"][path.stem])
        except Exception as exc:
            import traceback
            summary["errors"].append({"config": str(path), "error": str(exc), "traceback": traceback.format_exc()})
        write(args.output/"verification.json", summary)
    summary["sources_unchanged"] = source == source_seal()
    summary["passed"] = not summary["errors"] and summary["sources_unchanged"]
    summary["artifact_sha256"] = {str(p.relative_to(args.output)): hashlib.sha256(p.read_bytes()).hexdigest() for p in args.output.rglob("*.json")
                                   if p.name != "verification.json"}
    write(args.output/"verification.json", summary)
    print(json.dumps({"passed": summary["passed"], "errors": summary["errors"],
                      "verdicts": {k: v["verdicts"] for k, v in summary["experiments"].items()}}, indent=2))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
