"""Read-only observers around the frozen normal entry; no action/result replacement.

Every original method is called once with unchanged inputs. Checkpoint files are
output-only and are never loaded by the learner. Observer parity is tested.
"""
from collections import Counter
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
import argparse
import json
import os
import sys
import time

CONTROL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CONTROL))
from scripts.measure_persistent_learning import ROOT, Theory, Domain, size, write
from scripts.run_theory_formation import main as normal_main


def peak_memory():
    if sys.platform == "win32":
        return None
    import resource
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value * 1024


class Observer:
    def __init__(self, output, *, cycles=(), proof_calls=()):
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=False)
        self.cycle_marks, self.proof_marks = set(cycles), set(proof_calls)
        self.saved = set()
        self.current = None
        self.latest_options = []
        self.selection = {}
        self.generated = Counter()
        self.started = time.perf_counter()
        self.bookkeeping_seconds = 0.0
        self.streams = {}

    def emit(self, name, row):
        if name not in self.streams:
            self.streams[name] = (self.output/(name+".jsonl")).open("w", encoding="utf-8")
        self.streams[name].write(json.dumps(row, separators=(",", ":"))+"\n")

    def save(self, engine, label):
        if label in self.saved:
            return
        began = time.perf_counter()
        write(self.output/(label+".json"), engine.snapshot())
        self.saved.add(label)
        self.bookkeeping_seconds += time.perf_counter()-began

    def attach(self, stack):
        original_step, original_actions, original_compose = Theory.step, Theory.actions, Domain.compose

        def actions(engine):
            result = original_actions(engine)
            if self.current is engine:
                s = engine.state
                unexpanded = [c for c in s["active_concepts"] if c not in s["expanded"]]
                self.latest_options = result
                self.selection = {
                    "active": list(s["active_concepts"]), "unexpanded_order": unexpanded,
                    "pending_terms": len(s["pending_terms"]),
                    "open_conjectures": result[0]["proof_bottleneck"] if result else 0,
                    "options": result,
                    "priority_note": "concepts have FIFO active position, not a numeric priority; kind priority in options",
                }
            return result

        def compose(domain, parent, others):
            engine = self.current
            if engine is None:
                yield from original_compose(domain, parent, others)
                return
            s = engine.state
            counts, sizes = Counter(), Counter()
            for candidate in original_compose(domain, parent, others):
                count = size(candidate)
                counts["generated"] += 1
                sizes[count] += 1
                counts["raw_size_rejected" if count > engine.budget["term_size"] else "raw_size_permitted"] += 1
                yield candidate
            self.generated.update(counts)
            self.emit("expansions", {
                "cycle": s["cycle"], "parent": s["expanded"][-1],
                "active": list(s["active_concepts"]), "parent_size": size(parent),
                "term_cap": engine.budget["term_size"], "sizes": dict(sizes), **counts,
            })

        def step(engine):
            if not self.saved:
                self.save(engine, "K0")
            self.current = engine
            start = time.perf_counter()
            try:
                result = original_step(engine)
            finally:
                self.current = None
            s = engine.state
            calls = s["costs"].get("certification", {}).get("proof_calls", 0)
            row = {"cycle": s["cycle"], "progressed": result,
                   "step_wall_seconds": time.perf_counter()-start,
                   "elapsed_wall_seconds": time.perf_counter()-self.started,
                   "engine_seconds": s["seconds"], "peak_rss_bytes": peak_memory(),
                   "concepts": len(s["concepts"]), "theorems": len(s["theorems"]),
                   "representations": len(s["representations"]),
                   "expanded": len(s["expanded"]), "seen": len(s["seen"]),
                   "proof_calls": calls,
                   "prover_input_nodes": s["costs"].get("certification", {}).get("semantic_nodes", 0),
                   "rule_inspections": s["costs"].get("rewrite", {}).get("rule_matches_checked", 0),
                   "generated": dict(self.generated), "selection_before_step": self.selection,
                   "chosen": s["decisions"][-1]["chosen"] if result else None}
            self.emit("cycles", row)
            if s["cycle"] in self.cycle_marks:
                self.save(engine, f"cycle-{s['cycle']}")
            if calls in self.proof_marks:
                self.save(engine, f"proof-{calls}")
            return result

        stack.enter_context(patch.object(Theory, "step", step))
        stack.enter_context(patch.object(Theory, "actions", actions))
        stack.enter_context(patch.object(Domain, "compose", compose))

    def close(self):
        for stream in self.streams.values():
            stream.close()
        write(self.output/"observer.json", {
            "saved": sorted(self.saved), "generated": dict(self.generated),
            "observer_wall_seconds": time.perf_counter()-self.started,
            "checkpoint_write_seconds": self.bookkeeping_seconds, "peak_rss_bytes": peak_memory(),
            "normal_entry": str(ROOT/"scripts/run_theory_formation.py"),
            "role": "fixed measurement wrappers only; original methods and decisions unchanged",
            "clock_note": "observer time affects real wall time; engine.seconds is the original action-body timer",
        })


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--cycle-marks", type=int, nargs="*", default=[1000, 4000, 12000])
    parser.add_argument("--proof-marks", type=int, nargs="*", default=[1000, 11338])
    args = parser.parse_args()
    observer = Observer(args.observations, cycles=args.cycle_marks, proof_calls=args.proof_marks)
    try:
        with ExitStack() as stack:
            observer.attach(stack)
            return normal_main(["--config", str(args.config), "--output", str(args.output)])
    finally:
        observer.close()


if __name__ == "__main__":
    raise SystemExit(main())
