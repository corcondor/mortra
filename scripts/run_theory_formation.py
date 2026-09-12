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
    parser.add_argument("--condition", choices=["learn", "no-theorems", "no-representations"], default="learn")
    args = parser.parse_args(argv)
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
    if args.resume:
        prior = json.loads((args.resume.parent/"input.json").read_text(encoding="utf-8"))
        if prior["source_seal"] != source or prior["config"] != config or prior["condition"] != args.condition:
            raise ValueError("resume inputs or code changed; start a separately labelled experiment")
        old = json.loads(args.resume.read_text(encoding="utf-8"))
    engine = Theory(config, theorem_reuse=args.condition != "no-theorems",
                    representation_reuse=args.condition != "no-representations", state=old)
    failure = None
    try:
        state = engine.run(cycles=args.cycles)
    except Exception:
        failure = traceback.format_exc()
        engine.state["stop_reason"] = "exception"
        state = engine.snapshot()
        write(args.output/"failure.json", {"traceback": failure})
    write(args.output/"state.json", state)
    for field in ["events", "concepts", "conjectures", "counterexamples", "theorems", "representations",
                  "procedures", "proof_dependencies", "representation_dependencies", "decisions", "downstream"]:
        write(args.output/(field+".json"), state[field])
    result = assess(state)
    result["sources_unchanged"] = source == source_seal()
    result["execution_completed"] = failure is None
    result["sha"] = metadata["sha"]
    result["workflow_run_id"] = metadata["workflow_run_id"]
    write(args.output/"verification.json", result)
    print(json.dumps(result, indent=2))
    if failure:
        print(failure, file=sys.stderr)
    if failure or not result["sources_unchanged"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
