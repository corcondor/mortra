"""Normal entry: fixed signature and budget, no target or mid-run input."""
from pathlib import Path
import argparse
import json
import os
import platform
import subprocess
import sys
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
                    ROOT/"scripts/run_theory_formation.py", ROOT/"scripts/verify_theory_formation.py"])
    return {str(p.relative_to(ROOT)): digest(p.read_text(encoding="utf-8")) for p in files}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--cycles", type=int)
    parser.add_argument("--queries", type=Path)
    parser.add_argument("--knowledge", type=Path)
    parser.add_argument("--condition", choices=["learn", "no-theorems", "no-representations", "no-dsl", "initial-only"], default="learn")
    args = parser.parse_args(argv)
    if args.knowledge and (not args.queries or args.resume):
        parser.error("--knowledge requires --queries and cannot resume training")
    args.output.mkdir(parents=True, exist_ok=False)
    config = json.loads(args.config.read_text(encoding="utf-8"))
    source = source_seal()
    metadata = {"sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "source_seal": source, "config": config, "condition": args.condition,
                "python": sys.version, "platform": platform.platform(),
                "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
                "repository": os.environ.get("GITHUB_REPOSITORY"),
                "command": sys.argv, "generated_at": datetime.now(timezone.utc).isoformat(),
                "test_input_channel": "no interactive input or dynamic source loading",
                "intervention_claim": "fixed code/config checked; not cryptographic proof of no interference"}
    write(args.output/"input.json", metadata)
    old = None
    if args.knowledge:
        prior = json.loads((args.knowledge.parent/"input.json").read_text(encoding="utf-8"))
        if prior["source_seal"] != source or prior["config"] != config:
            raise ValueError("query archive comes from different code or inputs")
        old = json.loads(args.knowledge.read_text(encoding="utf-8"))
    if args.resume:
        prior = json.loads((args.resume.parent/"input.json").read_text(encoding="utf-8"))
        if prior["source_seal"] != source or prior["config"] != config or prior["condition"] != args.condition:
            raise ValueError("resume inputs or code changed; start a separately labelled experiment")
        old = json.loads(args.resume.read_text(encoding="utf-8"))
    engine = Theory(config, **old["flags"], state=old) if args.knowledge else Theory(config, theorem_reuse=args.condition != "no-theorems",
                    representation_reuse=args.condition != "no-representations",
                    dsl_reuse=args.condition not in {"no-dsl", "initial-only"}, state=old)
    failure = None
    queries = None
    try:
        if args.queries:
            tasks = json.loads(args.queries.read_text(encoding="utf-8"))
            write(args.output/"queries-input.json", tasks)
            queries = []
            for t in tasks:
                row = engine.vocabulary.solve_observation(t, acquired=args.condition == "learn")
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
    write(args.output/"state.json", state)
    for field in ["events", "concepts", "conjectures", "counterexamples", "theorems", "representations",
                  "procedures", "proof_dependencies", "representation_dependencies", "decisions", "downstream",
                  "observable_spaces", "dsl"]:
        write(args.output/(field+".json"), state[field])
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
