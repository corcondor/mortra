"""Execute the original design loop with only its training selector replaced."""
import argparse
from contextlib import redirect_stdout
import gzip
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback

import psutil

from .adapter import Integration, load_v2, json_default
from .verify import ROOT, write, source_audit

MANIFEST = json.loads((Path(__file__).parent / "manifest.json").read_text())


class Tee:
    def __init__(self, stream, log):
        self.stream, self.log = stream, log
    def write(self, text):
        self.stream.write(text)
        self.log.write(text)
    def flush(self):
        self.stream.flush()
        self.log.flush()


def peak_memory():
    info = psutil.Process().memory_info()
    if hasattr(info, "peak_wset"):
        return info.peak_wset
    import resource
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024)


def execute(seed, method, iterations, control, directory):
    module = load_v2()
    game = module.MicroGame(seed=seed)
    game.generate_random(wall_density=MANIFEST["wall_density"])
    directory.mkdir(parents=True, exist_ok=False)
    write(directory / "game_initial.json", game.to_dict())
    bridge = Integration(module, method, directory / "evaluations")
    bridge.install()
    previous = sys.getprofile()
    cpu, wall = time.process_time(), time.perf_counter()
    status = "RUN_NOT_COMPLETED"
    with (directory / "loop_events.jsonl").open("x", encoding="utf-8") as events, (directory / "run.log").open("x", encoding="utf-8", buffering=1) as log:
        observed = {getattr(module, name).__code__: name for name in
                    ("critique_game", "apply_targeted_mutation", "apply_random_mutation", "decide_acceptance")}
        def observe(frame, event, result):
            if event == "call" and "oracle" in frame.f_code.co_name.lower():
                raise RuntimeError("Oracle call outside evaluation is prohibited")
            name = observed.get(frame.f_code)
            if event == "return" and name:
                if name in ("apply_targeted_mutation", "apply_random_mutation"):
                    value = {"game": result[0].to_dict(), "description": result[1]}
                else:
                    value = result
                events.write(json.dumps({"function": name, "result": value}, default=json_default) + "\n")
                events.flush()
        try:
            sys.setprofile(observe)
            with redirect_stdout(Tee(sys.stdout, log)):
                final, history, accepted = module.run_self_design_loop(game, num_iterations=iterations,
                    is_control=(control == "random_mutation"), seed=seed)
            assert len(history) == iterations + 1
            assert len(bridge.evaluations) == iterations + 1
            write(directory / "game_final.json", final.to_dict())
            write(directory / "history.json", history)
            status = "COMPLETED"
        except BaseException as exc:
            with (directory / "traceback.txt").open("x", encoding="utf-8") as stream:
                traceback.print_exc(file=stream)
            write(directory / "incomplete.json", {"status": "RUN_NOT_COMPLETED", "reason": repr(exc),
                                                   "completed_evaluations": len(bridge.evaluations)})
            if bridge.recorder:
                for name, rows in (("partial_training.jsonl.gz", bridge.recorder.training), ("partial_actions.jsonl.gz", bridge.recorder.actions)):
                    with gzip.open(directory / name, "xt", encoding="utf-8") as stream:
                        for row in rows:
                            stream.write(json.dumps(row, default=json_default) + "\n")
            raise
        finally:
            sys.setprofile(previous)
            bridge.restore()
            write(directory / "resources.json", {"status": status, "cpu_seconds": time.process_time() - cpu,
                "wall_seconds": time.perf_counter() - wall, "peak_process_memory_bytes": peak_memory(),
                "scope": "loop, observation, replay verification and serialization; process high-water memory"})
    summary = {"seed": seed, "method": method, "control": control, "iterations": iterations,
               "accepted_edits": accepted, "initial": history[0]["metrics"], "final": history[-1]["metrics"],
               "evaluations": bridge.evaluations, "status": status}
    write(directory / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("smoke", "full"), required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--method", choices=MANIFEST["methods"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert args.seed in (MANIFEST["fresh_creation_seeds"] if args.stage == "full" else [MANIFEST["smoke_seed"]])
    args.output.mkdir(parents=True, exist_ok=False)
    sources = source_audit()
    assert all(s["identical_lf"] for s in sources)
    integration_hashes = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in Path(__file__).parent.glob("*") if p.is_file()}
    write(args.output / "source_snapshot.json", {
        "sources": sources, "integration_hashes": integration_hashes, "manifest": MANIFEST,
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "command": sys.argv, "python": sys.version, "platform": platform.platform(),
        "dependencies": {n: importlib.metadata.version(n) for n in ("numpy", "scipy", "matplotlib", "pytest", "psutil")},
        "github_run_id": os.environ.get("GITHUB_RUN_ID"), "attempt": os.environ.get("GITHUB_RUN_ATTEMPT")})
    iterations = MANIFEST["smoke_iterations"] if args.stage == "smoke" else MANIFEST["full_iterations"]
    summaries = [execute(args.seed, args.method, iterations, control, args.output / control)
                 for control in MANIFEST["controls"]]
    assert sources == source_audit()
    write(args.output / "completed.json", {"seed": args.seed, "method": args.method, "stage": args.stage,
          "status": "COMPLETED", "iterations": iterations,
          "controls": [{"control": r["control"], "accepted_edits": r["accepted_edits"], "final": r["final"]} for r in summaries]})


if __name__ == "__main__":
    main()
