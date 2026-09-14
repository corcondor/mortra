"""Freeze specifications before contraction evaluation; witnesses stay separate."""
from pathlib import Path
import argparse
import json
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import sympy as sp
from math_os_prototype import geometry_contracts as gc
from math_os_prototype.representation_progress import digest


def specification(body, names):
    h, _ = gc.certify_body(body)
    symbols = {n+a: sp.Symbol(n+a, real=True) for n in [*names, "u"] for a in ("x", "y")}
    equations = []
    for axis, expression in zip(("x", "y"), h["witness"][h["output"]]):
        value = sp.cancel(symbols["u"+axis]-gc.parse(expression, symbols))
        equations.append(str(sp.Poly(value.as_numer_denom()[0], *symbols.values(), domain=sp.QQ).monic().as_expr()))
    return {"points": names, "goal_polynomials": equations,
            "nonzero": h["applicability"]["input_nonzero_polynomials"]}


def freeze():
    protocol = {"seeds": [101, 211], "training_depths": [1, 2, 3, 1, 2, 3],
        "evaluation_depths": [1, 2, 3, 4], "python_hash_seed": 0,
        "grammar": "chain: midpoint(previous, earlier point) or foot(previous, distinct base pair); width alternates 3/4",
        "rejection": "undefined/duplicate specification or initial-point output only; never solver results",
        "conditions": ["primitive_only", "syntactic_macro", "certified_morphism", "summarized", "hiding_only"],
        "ablation": "single most used summarized H, tie by content ID; all evaluation tasks",
        "regression": "original four tasks, excluded from fresh cohort",
        "witness_channel": "evaluator-only file; no file path or program supplied to solver",
        "scientific_gate": "no lost baseline/exposed solve; hidden objects; lower expansion/state/goal cost vs exposed; used-H causal ablation; exact replay",
        "tuning": "no task, seed, budget changes after mechanism evaluation"}
    old = json.loads((ROOT/"configs/theory-geometry-contract-acquisition.json").read_text())
    seen = set()
    for t in old["training"]+old["evaluation"]:
        symbols = {n+a: sp.Symbol(n+a, real=True) for n in [*t["points"], "u"] for a in ("x", "y")}
        normal = {"points": t["points"], "goal_polynomials": [str(sp.Poly(gc.parse(e, symbols), *symbols.values(), domain=sp.QQ).monic().as_expr()) for e in t["goal_polynomials"]],
                  "nonzero": sorted({f for e in t["nonzero"] for f in gc.factors(gc.parse(e, symbols))})}
        seen.add(digest(normal))
    tasks = {"training": [], "evaluation": []}
    witnesses = []
    for phase in tasks:
        for seed in protocol["seeds"]:
            rng = random.Random(f"geometry-contraction-v1:{phase}:{seed}")
            for index, depth in enumerate(protocol[phase+"_depths"]):
                names = ["a", "b", "c"] if index % 2 == 0 else ["a", "b", "c", "d"]
                for attempt in range(100):
                    previous = gc.point(rng.choice(names))
                    available = [gc.point(n) for n in names]
                    for _ in range(depth):
                        if rng.randrange(2):
                            pair = rng.sample(names, 2)
                            previous = {"op": "foot", "args": [previous, *map(gc.point, pair)]}
                        else:
                            others = [p for p in available if p != previous]
                            previous = {"op": "midpoint", "args": [previous, rng.choice(others)]}
                        available.append(previous)
                    spec = specification(previous, names)
                    key = digest(spec)
                    if key in seen:
                        continue
                    seen.add(key)
                    task = {"id": f"fresh-{phase}-{seed}-{index}", **spec}
                    tasks[phase].append(task)
                    witnesses.append({"task_sha256": key, "task_id": task["id"], "body": previous,
                                      "seed": seed, "requested_depth": depth, "draw_attempt": attempt})
                    break
                else:
                    raise RuntimeError("fixed generator exhausted; do not retune based on solver outcomes")
    config = {"domain": {"kind": "geometry", "mode": "morphism_contraction"},
        "protocol": protocol, "search": {"seed": 17, "max_states": 120,
            "max_primitive_operations": 360, "wall_seconds": 120, "per_family_limit": 12,
            "max_input_tuples_per_family": 256},
        "acquisition": {**old["acquisition"], "max_parameters": 4, "capacity": 4},
        **tasks, "regression": old["evaluation"]}
    return config, {"protocol_sha256": digest(protocol), "specifications_sha256": digest(tasks),
                    "generator_sha256": digest(Path(__file__).read_text()), "witnesses": witnesses}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--witnesses", type=Path, required=True)
    args = parser.parse_args()
    if args.config.exists() or args.witnesses.exists():
        raise SystemExit("refuse to replace a frozen cohort")
    config, witnesses = freeze()
    for path, value in [(args.config, config), (args.witnesses, witnesses)]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"config_sha256": digest(config), "witness_sha256": digest(witnesses),
                      "training": len(config["training"]), "evaluation": len(config["evaluation"])}))
