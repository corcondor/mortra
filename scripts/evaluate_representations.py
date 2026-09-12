"""Run the representation evaluations, keep them in the ledger, and choose.

    python scripts/evaluate_representations.py --output <directory>

Writes `evaluation.json` (every component, separately), `ledger.json` (what each
representation has cost and earned, over time), `report.txt`, `policy.txt` (the
Pareto fronts and what the certificate refused) and `graphs.txt` (raw
computation graph, learned representation, reduced computation graph).
"""
from pathlib import Path
import argparse
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sympy as sp

from math_os_prototype import fold_observable_system as F
from math_os_prototype import fold_tasks
from math_os_prototype import representation_benchmarks as B
from math_os_prototype import representation_certificate as certificates
from math_os_prototype import representation_evaluation as E
from math_os_prototype import representation_ledger as ledgers
from math_os_prototype import representation_policy as policy

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
              "dimension": found["dimension"],
              "identity_residuals_all_zero": found["identity_residuals_all_zero"],
              "closure_scope": found["scope"]}
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
    return record, cost, premise


def graphs(differential, fold_repeat):
    """The one required picture, for the case the request named."""
    before = differential["primitive_reduction"]["derivative_calls_before"]
    after = differential["primitive_reduction"]["derivative_calls_after"]
    existing = differential["primitive_reduction"][
        "best_baseline_without_this_representation"]
    depth_before = fold_repeat["execution_depth"]["sequential_depth_before"]
    depth_after = fold_repeat["execution_depth"]["sequential_depth_after"]
    monoid = fold_repeat["attribution"].get("mathematical_reduction") or {}
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
            "read the rung below before crediting this to the representation:",
            f"  the existing holonomic route ({existing['rung']}) already reaches",
            f"  the same answer in {existing['primitive_calls']} primitive calls with",
            f"  {existing['derivative_calls']} derivative entries. The representation column",
            "  in `attribution` is what is left after that.",
            "",
            "the fold comparison is the same shape with the depth changing:",
            f"  chain of frame updates, depth {depth_before}",
            f"  block matrix, squared up, depth {depth_after}",
            f"  but the repository's own summary monoid already saved",
            f"  {monoid.get('fold_step_calls')} of those fold steps with nothing learned.",
        ])


def table(records):
    rows = [
        f"{'comparison':34s} {'prim.before':>11s} {'prim.after':>10s} "
        f"{'by math':>9s} {'by generic':>10s} {'by repr':>9s} "
        f"{'depth b/a':>10s} {'be(naive)':>9s} {'be(best)':>8s}"]
    rows.append("-" * len(rows[0]))
    for record in records:
        if record.get("refused"):
            rows.append(f"{record['name'][:34]:34s} "
                        f"REFUSED by {record.get('refused_by')}")
            continue
        primitive = record["primitive_reduction"]
        attribution = record["attribution"]
        depth = record["execution_depth"]
        turns = record["cumulative"]["break_evens"]

        def column(name):
            found = attribution.get(name)
            return "-" if found is None else str(found["primitive_calls"])

        rows.append(
            f"{record['name'][:34]:34s} "
            f"{primitive['primitive_calls_before']:11d} "
            f"{primitive['primitive_calls_after']:10d} "
            f"{column('mathematical_reduction'):>9s} "
            f"{column('generic_search_reduction'):>10s} "
            f"{column('representation_reduction'):>9s} "
            f"{str(depth['sequential_depth_before']) + '/' + str(depth['sequential_depth_after']):>10s} "
            f"{str(turns['compute_break_even_reuse_count']):>9s} "
            f"{str(turns['compute_break_even_reuse_count_against_best_baseline']):>8s}")
    return "\n".join(rows)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="evaluation-results")
    parser.add_argument("--upto", type=int, default=40)
    parser.add_argument("--check-terms", type=int, default=24)
    parser.add_argument("--block", default="GCC")
    parser.add_argument("--repeats", type=int, default=64)
    parser.add_argument("--search-length", type=int, default=8)
    parser.add_argument("--certificate-depth", type=int, default=5)
    arguments = parser.parse_args(argv)

    book = ledgers.Ledger()
    records = []
    for name, program, closed_form in DIFFERENTIAL_CASES:
        print(f"running {name} ...", flush=True)
        record = B.differential_comparison(
            name, program, closed_form,
            upto=arguments.upto, check_terms=arguments.check_terms)
        records.append(record)
        book.observe(record["representation"], record,
                     certificate=record["certificate"],
                     acquisition=record["acquisition_cost"])

    print("acquiring the fold observation representation ...", flush=True)
    closure_record, fold_cost, premise = fold_acquisition()

    open_task = fold_tasks.displacement_task(axis=0)
    constrained = fold_tasks.displacement_task(axis=0, collision_free=True)
    open_certificate = certificates.certify(closure_record, open_task,
                                            depth=arguments.certificate_depth,
                                            premise=premise)
    constrained_certificate = certificates.certify(
        closure_record, constrained, depth=arguments.certificate_depth,
        premise=premise)
    print(f"  certificate, unconstrained task : {open_certificate['verdict']}")
    print(f"  certificate, collision-free task: "
          f"{constrained_certificate['verdict']} "
          f"{constrained_certificate['refused_by']}")

    print("running fold repeat ...", flush=True)
    repeat = B.fold_repeat_comparison(
        f"fold repeat: {arguments.block} x {arguments.repeats}",
        closure_record, fold_cost,
        block=arguments.block, repeats=arguments.repeats,
        extra_tasks=(("ACGT", 17), ("AG", 33), ("TTGA", 9)),
        certificate=open_certificate)
    records.append(repeat)

    print("running fold search ...", flush=True)
    search = B.fold_search_comparison(
        f"fold search: length {arguments.search_length}",
        closure_record, fold_cost, task=open_task,
        length=arguments.search_length, certificate=open_certificate,
        heldout_lengths=(6, 10))
    records.append(search)

    print("running the collision-constrained variant ...", flush=True)
    constrained_record = B.fold_search_comparison(
        f"fold search, collision-free: length {arguments.search_length}",
        closure_record, fold_cost, task=constrained,
        length=arguments.search_length, certificate=constrained_certificate)
    records.append(constrained_record)

    representation = repeat["representation"]
    for record in (repeat, search):
        book.observe(representation, record, certificate=open_certificate,
                     acquisition=fold_cost)
    book.note_certificate(representation, constrained_certificate)

    output = Path(arguments.output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "evaluation.json").write_text(
        json.dumps({"records": records, "representation": closure_record,
                    "certificates": {"unconstrained": open_certificate,
                                     "collision_free": constrained_certificate},
                    "instruments": E.INSTRUMENTS}, indent=2, sort_keys=True),
        encoding="utf-8")
    book.save(output / "ledger.json")
    (output / "report.txt").write_text(table(records) + "\n", encoding="utf-8")
    (output / "policy.txt").write_text(
        policy.explain(book.all_entries(), task=open_task.name) + "\n\n" +
        policy.explain(book.all_entries(), task=constrained.name) + "\n",
        encoding="utf-8")
    (output / "graphs.txt").write_text(
        graphs(records[0], repeat) + "\n", encoding="utf-8")
    print()
    print(table(records))
    print()
    print(policy.explain(book.all_entries(), task=constrained.name))
    print()
    print(f"written to {output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
