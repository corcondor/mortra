"""Normal entry: fixed signature and budget, no target or mid-run input."""
from pathlib import Path
import argparse
import json
import os
import platform
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from math_os_prototype.theory_formation import Theory, assess
from math_os_prototype.representation_progress import digest


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")


def source_seal():
    files = sorted([*ROOT.joinpath("math_os_prototype").glob("*.py"),
                    ROOT/"scripts/run_theory_formation.py", ROOT/"scripts/verify_theory_formation.py",
                    ROOT/"scripts/verify_theory_tasks.py", ROOT/"scripts/verify_theory_dsl.py",
                    ROOT/"scripts/verify_theory_semantic_edit.py", ROOT/"scripts/verify_temporal_utility.py",
                    ROOT/"scripts/verify_basis_quality.py", ROOT/"scripts/verify_theory_geometry.py",
                    ROOT/"scripts/freeze_geometry_cohort.py", ROOT/"scripts/replay_geometry_contracts.py",
                    ROOT/"scripts/freeze_geometry_contraction.py", ROOT/"scripts/replay_geometry_contraction.py"])
    files += sorted(ROOT.joinpath("worker/backend").glob("*.py"))
    files += [ROOT/"requirements-geometry.txt", ROOT/"requirements-geometry-contracts.txt"]
    return {p.relative_to(ROOT).as_posix(): digest(p.read_text(encoding="utf-8")) for p in files}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--cycles", type=int)
    parser.add_argument("--queries", type=Path)
    parser.add_argument("--knowledge", type=Path)
    parser.add_argument("--exclude-primitive", action="append", default=[])
    parser.add_argument("--temporal-plan", type=Path,
                        help="frozen internal temporal holdout and active-DSL measurement plan")
    parser.add_argument("--semantic-edits", action="store_true")
    parser.add_argument("--refresh-corpus", action="store_true",
                        help="FIFO refresh of the bounded learning corpus; retain acquired source evidence")
    parser.add_argument("--eligible-sources", action="store_true",
                        help="deduplicate and prefilter abstraction sources by its existing composition contract")
    parser.add_argument("--uncached-syntax", action="store_true",
                        help="diagnostic ablation: rebuild definition tables and reparse literals")
    parser.add_argument("--execution-mode", choices=["legacy", "certified", "edited"], default="certified")
    parser.add_argument("--condition", choices=["learn", "no-theorems", "no-representations", "no-dsl", "initial-only"], default="learn")
    args = parser.parse_args(argv)
    if args.knowledge and (not args.queries or args.resume):
        parser.error("--knowledge requires --queries and cannot resume training")
    if args.queries and args.condition not in {"learn", "no-dsl", "initial-only"}:
        parser.error("query conditions are initial-only, learn, or structural-only no-dsl")
    args.output.mkdir(parents=True, exist_ok=False)
    config = json.loads(args.config.read_text(encoding="utf-8"))
    temporal = json.loads(args.temporal_plan.read_text(encoding="utf-8")) if args.temporal_plan else None
    source = source_seal()
    metadata = {"sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "source_seal": source, "config": config, "condition": args.condition,
                "python": sys.version, "platform": platform.platform(),
                "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
                "repository": os.environ.get("GITHUB_REPOSITORY"),
                "command": sys.argv, "generated_at": datetime.now(timezone.utc).isoformat(),
                "semantic_edits": args.semantic_edits, "execution_mode": args.execution_mode,
                "corpus_refresh": args.refresh_corpus,
                "eligible_sources": args.eligible_sources,
                "temporal_options": temporal,
                "primitive_exclusions": args.exclude_primitive,
                "syntax_cache_enabled": not args.uncached_syntax,
                "test_input_channel": "no interactive input or dynamic source loading",
                "intervention_claim": "fixed code/config checked; not cryptographic proof of no interference"}
    write(args.output/"input.json", metadata)
    if config["domain"].get("kind") == "geometry":
        if args.resume or args.knowledge or args.queries or args.condition != "learn":
            parser.error("Geometry uses formal task inputs, not scalar archive/queries or training conditions")
        if config["domain"].get("mode") in {"contract_acquisition", "morphism_contraction", "semantic_feedback", "selection_factorial", "complete_revalidation"}:
            from importlib.metadata import distributions
            from math_os_prototype.theory_geometry_acquisition import run_contract_geometry
            write(args.output/"environment.json", {
                "python": sys.version, "platform": platform.platform(),
                "python_hash_seed": os.environ.get("PYTHONHASHSEED"),
                "packages": {d.metadata["Name"]: d.version for d in distributions()},
                "git_remote": subprocess.check_output(["git", "remote", "get-url", "origin"], cwd=ROOT, text=True).strip(),
                "branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip(),
                "sha": metadata["sha"], "workflow_run_id": metadata["workflow_run_id"]})
            try:
                required_seed = config.get("protocol", {}).get("python_hash_seed")
                if required_seed is not None and os.environ.get("PYTHONHASHSEED") != str(required_seed):
                    raise ValueError("set PYTHONHASHSEED before launching Python as declared in the frozen protocol")
                if config["domain"]["mode"] == "complete_revalidation":
                    from math_os_prototype.theory_geometry_selection import run_complete_revalidation
                    result = run_complete_revalidation(config, args.output)
                elif config["domain"]["mode"] == "selection_factorial":
                    from math_os_prototype.theory_geometry_selection import run_selection_factorial
                    result = run_selection_factorial(config, args.output)
                elif config["domain"]["mode"] == "semantic_feedback":
                    from math_os_prototype.theory_geometry_feedback import run_semantic_feedback
                    result = run_semantic_feedback(config, args.output)
                elif config["domain"]["mode"] == "morphism_contraction":
                    from math_os_prototype.theory_geometry_contraction import run_contraction_geometry
                    result = run_contraction_geometry(config, args.output)
                else:
                    result = run_contract_geometry(config, args.output)
            except Exception:
                write(args.output/"failure.json", {"traceback": traceback.format_exc()})
                result = {"execution_completed": False, "minimal_chain_passed": False}
        else:
            from math_os_prototype.theory_geometry import run_geometry_theory
            result = run_geometry_theory(config, args.output)
        result.update(sources_unchanged=source == source_seal(), sha=metadata["sha"],
                      workflow_run_id=metadata["workflow_run_id"])
        write(args.output/"verification.json", result)
        print(json.dumps(result, indent=2))
        return 0 if result["execution_completed"] and result["sources_unchanged"] else 1
    old = None
    if args.knowledge:
        prior = json.loads((args.knowledge.parent/"input.json").read_text(encoding="utf-8"))
        if prior["source_seal"] != source or prior["config"] != config:
            raise ValueError("query archive comes from different code or inputs")
        old = json.loads(args.knowledge.read_text(encoding="utf-8"))
    if args.resume:
        prior = json.loads((args.resume.parent/"input.json").read_text(encoding="utf-8"))
        if (prior["source_seal"] != source or prior["config"] != config or prior["condition"] != args.condition
                or prior.get("semantic_edits", False) != args.semantic_edits
                or prior.get("corpus_refresh", False) != args.refresh_corpus
                or prior.get("eligible_sources", False) != args.eligible_sources
                or prior.get("temporal_options") != temporal
                or prior.get("primitive_exclusions", []) != args.exclude_primitive
                or prior.get("syntax_cache_enabled", True) != (not args.uncached_syntax)):
            raise ValueError("resume inputs or code changed; start a separately labelled experiment")
        old = json.loads(args.resume.read_text(encoding="utf-8"))
    engine = Theory(config, **old["flags"], state=old) if args.knowledge else Theory(config, theorem_reuse=args.condition != "no-theorems",
                    representation_reuse=args.condition != "no-representations",
                    dsl_reuse=args.condition not in {"no-dsl", "initial-only"}, semantic_edits=args.semantic_edits,
                    corpus_refresh=args.refresh_corpus, eligible_sources=args.eligible_sources, temporal_options=temporal,
                    primitive_exclusions=args.exclude_primitive, state=old)
    engine.domain.syntax_cache_enabled = not args.uncached_syntax
    failure = None
    queries = None
    try:
        if args.queries:
            tasks = json.loads(args.queries.read_text(encoding="utf-8"))
            write(args.output/"queries-input.json", tasks)
            queries = []
            for t in tasks:
                row = engine.vocabulary.solve_observation(t, acquired=args.condition != "initial-only",
                    definitions_enabled=args.condition != "no-dsl", execution_mode=args.execution_mode)
                queries.append(row)
                write(args.output/"queries.json", queries)
                print(json.dumps({"task": t["id"], "solved": row["solved"],
                                  "states": row["states_explored"], "seconds": row["seconds"]}), flush=True)
            engine.state["stop_reason"] = "external_queries_complete"
            state = engine.snapshot()
        else:
            state = engine.run(cycles=args.cycles) if args.condition != "initial-only" else engine.snapshot()
        if args.condition == "initial-only" and not args.queries:
            engine.state["stop_reason"] = "initial_knowledge_comparison"
            state = engine.snapshot()
    except Exception:
        failure = traceback.format_exc()
        engine.state["stop_reason"] = "exception"
        state = engine.snapshot()
        write(args.output/"failure.json", {"traceback": failure})
    persistence_start = time.perf_counter()
    write(args.output/"state.json", state)
    for field in ["events", "concepts", "conjectures", "counterexamples", "theorems", "representations",
                  "procedures", "proof_dependencies", "representation_dependencies", "decisions", "downstream",
                  "observable_spaces", "dsl"]:
        write(args.output/(field+".json"), state[field])
    if engine.vocabulary.temporal:
        write(args.output/"temporal.json", engine.vocabulary.temporal.state)
    storage = {"seconds": time.perf_counter()-persistence_start,
               "files": {p.name: p.stat().st_size for p in args.output.glob("*.json")}}
    write(args.output/"persistence.json", storage)
    result = assess(state)
    result["sources_unchanged"] = source == source_seal()
    result["execution_completed"] = failure is None
    result["sha"] = metadata["sha"]
    result["workflow_run_id"] = metadata["workflow_run_id"]
    if queries is not None:
        result["queries"] = {"count": len(queries), "solved": sum(q["solved"] for q in queries),
                             "origin": "external_heldout", "witness_supplied": False}
    write(args.output/"verification.json", result)
    print(json.dumps(result, indent=2))
    if failure:
        print(failure, file=sys.stderr)
    if failure or not result["sources_unchanged"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
