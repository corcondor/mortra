"""Run the representation evaluations and write down what they cost.

    python scripts/evaluate_representations.py --output <directory>

Writes `evaluation.json` (every component, separately), `report.txt` (the same
numbers as a table) and `graphs.txt` (raw computation graph, learned
representation, reduced computation graph).
"""
from pathlib import Path
import argparse
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sympy as sp

from math_os_prototype import fold_observable_system as F
from math_os_prototype import representation_benchmarks as B
from math_os_prototype import representation_evaluation as E

X = sp.Symbol("x")
EXPONENTIAL = {"op": "hyper", "a": ["1"], "b": ["1"]}
GEOMETRIC = {"op": "hyper", "a": ["1", "1"], "b": ["1"]}

DIFFERENTIAL_CASES = (
    ("differential: exp(x)/(1-x)",
     {"op": "mul", "left": EXPONENTIAL, "right": GEOMETRIC},
     sp.exp(X) / (1 - X)),
    ("differential: exp(x**2)",
     {"op": "pullback", "child": EXPONENTIAL,
      "numerator": ["0", "0", "1"], "denominator": ["1"]},
     sp.exp(X ** 2)),
    ("differential: x*exp(x) + 1/(1-x)",
     {"op": "add",
      "left": {"op": "mul", "left": {"op": "poly", "coefficients": ["0", "1"]},
               "right": EXPONENTIAL},
      "right": GEOMETRIC},
     X * sp.exp(X) + 1 / (1 - X)),
)


def fold_acquisition():
    """Acquire the observation representation, and price it.

    The premise -- that one fold really is the linear action on the encoded
    state, over every reachable frame and every centre -- is acquired here too,
    because without it the representation licenses nothing.
    """
    def work():
        system = F.fold_system()
        premise = F.verify_step(system, depth=4)
        if not premise["exact"]:
            raise AssertionError("the one-step correspondence is not exact")
        found = F.acquire_closure(system, F.VARIABLES[0], maximum_dimension=64)
        if not found["closed"]:
            raise AssertionError("the observable space did not close")
        return {"value": {"premise": premise, "closure": found}}

    measured = E.measure(work)
    premise = measured["value"]["premise"]
    found = measured["value"]["closure"]
    record = {"observable": found["observable"], "basis": found["basis"],
              "action_matrices": found["action_matrices"],
              "dimension": found["dimension"]}
    cost = {
        "acquisition_time": measured["wall_time"],
        "acquisition_primitive_calls": measured["primitive_calls"],
        "acquisition_proof_calls": measured["proof_calls"],
        "acquisition_fold_step_calls": measured["fold_step_calls"],
        "acquisition_search_nodes": premise["frames_checked"],
        "acquisition_search_note": ("the frames the alphabet reaches, each "
                                    "enumerated once for the premise"),
        "acquisition_proof_cost": {
            "identities_checked": premise["identities_checked"],
            "frames_checked": premise["frames_checked"],
            "centre": premise["centre"],
            "closure_identity_residuals_all_zero":
                found["identity_residuals_all_zero"],
            "closure_scope": found["scope"]},
        "acquisition_peak_memory": measured["peak_memory"]}
    return record, cost


def graphs(differential, fold_repeat):
    """The one required picture, for the case the request named."""
    before = differential["primitive_reduction"]["derivative_calls_before"]
    after = differential["primitive_reduction"]["derivative_calls_after"]
    depth_before = fold_repeat["execution_depth"]["sequential_depth_before"]
    depth_after = fold_repeat["execution_depth"]["sequential_depth_after"]
    return E.ascii_graphs(
        "exp(x)/(1-x): every derivative value at 0 up to order 40",
        raw=[
            "f0 = exp(x)/(1-x) ------> [Expr.diff] --> f1 --> [Expr.diff] --> f2 --> ... --> f40",
            "                              |                |                |              |",
            "                           subs x=0         subs x=0         subs x=0       subs x=0",
            "                              v                v                v              v",
            "                            f(0)             f'(0)            f''(0)       f^(40)(0)",
            "",
            f"  every arrow enters the derivative primitive: {before} entries measured",
            "  the expression carried from step to step is symbolic and grows",
        ],
        representation=[
            "annihilating operator   sum_j c_j(x) D^j  f = 0",
            "         |",
            "         |  read coefficientwise: D becomes an index shift",
            "         v",
            "   P0(n) a_n + P1(n) a_(n-1) + ... + P4(n) a_(n-4) = 0     (n >= 2)",
            "         |",
            "         |  window J_m = (a_(m-4), ..., a_(m-1))",
            "         v",
            "   J_(m+1) = B(m) J_m          B(m) the 4x4 companion matrix",
            "",
            "  stored: the five polynomials, the first solvable index, two seeds.",
            "  not stored: any derivative value.",
        ],
        reduced=[
            "a0,a1 --> [B(2)] --> a2 --> [B(3)] --> a3 --> ... --> [B(40)] --> a40",
            "             |          |         |                       |",
            "            x 2!       x 3!      x 4!                   x 40!",
            "             v          v         v                       v",
            "           f''(0)    f'''(0)   f''''(0)               f^(40)(0)",
            "",
            f"  entries to the derivative primitive: {after}",
            "  the state carried from step to step is four rational numbers",
        ],
        legend=[
            "[Expr.diff]  the derivative primitive, counted at sympy.Expr.diff,",
            "             which every derivative in sympy passes through",
            "[B(m)]       one companion-matrix action: the acquired representation",
            "",
            "the fold comparison is the same shape with the depth changing instead:",
            f"  chain of frame updates, depth {depth_before}",
            f"  block matrix, squared up, depth {depth_after}",
        ])


def table(records):
    rows = [
        f"{'comparison':38s} {'prim.before':>11s} {'prim.after':>10s} "
        f"{'deriv.before':>12s} {'deriv.after':>11s} {'depth b/a':>11s} "
        f"{'break-even':>10s}"]
    rows.append("-" * len(rows[0]))
    for record in records:
        primitive = record["primitive_reduction"]
        depth = record["execution_depth"]
        break_even = record["cumulative"]["break_even_reuse_count"]
        rows.append(
            f"{record['name'][:38]:38s} "
            f"{primitive['primitive_calls_before']:11d} "
            f"{primitive['primitive_calls_after']:10d} "
            f"{primitive['derivative_calls_before']:12d} "
            f"{primitive['derivative_calls_after']:11d} "
            f"{str(depth['sequential_depth_before']) + '/' + str(depth['sequential_depth_after']):>11s} "
            f"{('none' if break_even is None else str(break_even)):>10s}")
    return "\n".join(rows)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="evaluation-results")
    parser.add_argument("--upto", type=int, default=40)
    parser.add_argument("--check-terms", type=int, default=24)
    parser.add_argument("--block", default="GCC")
    parser.add_argument("--repeats", type=int, default=64)
    parser.add_argument("--search-length", type=int, default=8)
    arguments = parser.parse_args(argv)

    records = []
    for name, program, closed_form in DIFFERENTIAL_CASES:
        print(f"running {name} ...", flush=True)
        records.append(B.differential_comparison(
            name, program, closed_form,
            upto=arguments.upto, check_terms=arguments.check_terms))

    print("acquiring the fold observation representation ...", flush=True)
    closure_record, fold_cost = fold_acquisition()

    print("running fold repeat ...", flush=True)
    repeat = B.fold_repeat_comparison(
        f"fold repeat: {arguments.block} x {arguments.repeats}",
        closure_record, fold_cost,
        block=arguments.block, repeats=arguments.repeats,
        extra_tasks=(("ACGT", 17), ("AG", 33), ("TTGA", 9)))
    records.append(repeat)

    print("running fold search ...", flush=True)
    records.append(B.fold_search_comparison(
        f"fold search: length {arguments.search_length}",
        closure_record, fold_cost,
        length=arguments.search_length, heldout_lengths=(6, 10)))

    output = Path(arguments.output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "evaluation.json").write_text(
        json.dumps({"records": records,
                    "representation": closure_record,
                    "instruments": E.INSTRUMENTS}, indent=2, sort_keys=True),
        encoding="utf-8")
    (output / "report.txt").write_text(table(records) + "\n", encoding="utf-8")
    (output / "graphs.txt").write_text(
        graphs(records[0], repeat) + "\n", encoding="utf-8")
    print()
    print(table(records))
    print()
    print(f"written to {output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
