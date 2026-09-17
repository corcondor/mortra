"""How the cost of a family grows, before and after a structure is discovered.

The question is not whether a search finds an answer faster. It is whether a
structure discovered from the operations turns a family of problems into
computations of a lower order, with the same output required of both routes.

For each family the record keeps the dimension of the given description, the
dimension after merging, the degree of the relation, the cost of discovering it
once, and then, for every length: the cost of enumerating the sequences, of
iterating the operator, and of evaluating the discovered relation, with the
answers checked against an independent route.

    python scripts/run_structure_scaling_eval.py --output reports/structure-scaling
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import json
import math
import platform
import random
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.set_int_max_str_digits(2_000_000)

from math_os_prototype import structure_discovery as sd
from math_os_prototype import structure_families as fam
from math_os_prototype.algebraic_structures import OperationCounter, SparseMatrix

LENGTHS = (4, 8, 16, 32, 64, 128, 256, 512, 1024, 4096, 16384, 65536)
ENUMERATION_BUDGET = 2_000_000


def slope(points):
    """Least squares slope of log(cost) against log(length): the empirical exponent."""
    usable = [(math.log(x), math.log(y)) for x, y in points if x > 0 and y > 0]
    if len(usable) < 2:
        return None
    mean_x = sum(x for x, _ in usable)/len(usable)
    mean_y = sum(y for _, y in usable)/len(usable)
    denominator = sum((x-mean_x)**2 for x, _ in usable)
    if not denominator:
        return None
    return sum((x-mean_x)*(y-mean_y) for x, y in usable)/denominator


def measure_family(family, *, lengths=LENGTHS, reference_limit=4096):
    counter = OperationCounter()
    began = time.perf_counter()
    structure = fam.discover(family, counter=counter)
    discovery = {"operations": counter["total"], "seconds": time.perf_counter()-began}
    rows = []
    for length in lengths:
        row = {"length": length}
        enumeration = OperationCounter()
        try:
            if family.letters**length <= 1_000_000:
                began = time.perf_counter()
                value = fam.count_by_enumeration(family, length, counter=enumeration,
                                                 budget=ENUMERATION_BUDGET)
                row["enumerate"] = {"operations": enumeration["total"],
                                    "seconds": time.perf_counter()-began, "value_matches": True}
                row["enumerate"]["value_matches"] = None      # filled in below
                row["_enumerated"] = value
            else:
                row["enumerate"] = {"refused": "the number of sequences exceeds the budget",
                                    "sequences": f"{family.letters}^{length}"}
        except sd.NoStructure as error:
            row["enumerate"] = {"refused": str(error)}
        iteration = OperationCounter()
        began = time.perf_counter()
        by_iteration = fam.count_by_iteration(family, length, counter=iteration)
        row["iterate"] = {"operations": iteration["total"], "seconds": time.perf_counter()-began}
        compiled = OperationCounter()
        began = time.perf_counter()
        by_structure = fam.count_by_structure(structure, length, counter=compiled)
        row["structure"] = {"operations": compiled["total"], "seconds": time.perf_counter()-began}
        row["same_answer"] = by_iteration == by_structure
        if "_enumerated" in row:
            row["enumerate"]["value_matches"] = row.pop("_enumerated") == by_structure
        if length <= reference_limit:
            row["independent_reference_agrees"] = fam.reference_count(family, length) == by_structure
        row["digits"] = len(str(int(by_structure))) if by_structure == int(by_structure) else None
        rows.append(row)
    exponents = {
        "iterate": slope([(row["length"], row["iterate"]["operations"]) for row in rows]),
        "structure": slope([(row["length"], row["structure"]["operations"]) for row in rows])}
    return {"family": family.name, "note": family.note,
            "given_dimension": structure["given_dimension"],
            "reachable_dimension": structure["reachable_dimension"],
            "merged_dimension": structure["merged_dimension"],
            "hidden_dimension": structure["hidden_dimension"],
            "relation_degree": structure["degree"], "relation_coefficients": structure["coefficients"],
            "relation_certified": structure["certified"],
            "relation_holds_for_every_start": structure["holds_for_every_start"],
            "discovery": discovery, "lengths": rows, "empirical_exponents": exponents,
            "all_answers_agree": all(row["same_answer"] for row in rows),
            "independent_reference_agrees": all(row.get("independent_reference_agrees", True) for row in rows)}


def random_family(seed, *, states=12, letters=2, window=3):
    """A family generated after the code was written, to check the procedure rather than a memory."""
    rng = random.Random(seed)
    size = states
    matrices = []
    for _ in range(letters):
        columns = [dict() for _ in range(size)]
        for source in range(size):
            for target in rng.sample(range(size), rng.randint(0, 2)):
                columns[source][target] = Fraction(rng.randint(1, 2))
        matrices.append(SparseMatrix(size, columns))
    start = {rng.randrange(size): Fraction(1)}
    functional = {index: Fraction(1) for index in rng.sample(range(size), max(1, size//3))}
    return fam.Family(f"random family seed {seed}", matrices, start, functional,
                      note="generated from a seed, never seen while the discovery was written")


def bilinear_evidence(*, seed=0, sizes=(2, 4, 8, 16, 32), search_steps=200_000):
    tensor = sd.matrix_multiplication_tensor(2, 2, 2)
    counter = OperationCounter()
    began = time.perf_counter()
    found = sd.search_decomposition(tensor, target_rank=7, steps=search_steps, seed=seed, counter=counter)
    search_seconds = time.perf_counter()-began
    record = {"tensor": "2x2 by 2x2 matrix multiplication", "obvious_rank": 8,
              "searched_rank": found["rank"], "history": found["history"],
              "exact_over_gf2": found["exact_over_gf2"],
              "discovery": {"operations": counter["total"], "seconds": search_seconds}}
    if not found["reached_target"]:
        record["lifted_to_rationals"] = False
        return record
    lifted = sd.lift_to_rationals(tensor, found["terms"], counter=counter)
    record["lifted_to_rationals"] = lifted is not None
    if lifted is None:
        return record
    terms = lifted["terms"]
    record["residual_over_the_rationals"] = sd.decomposition_error(tensor, terms)
    record["exponent"] = sd.exponent(lifted["rank"], 2)
    record["obvious_exponent"] = 3.0
    record["terms"] = [[{str(k): str(v) for k, v in factor.items()} for factor in term] for term in terms]
    rng = random.Random(seed+1)
    rows = []
    for size in sizes:
        A = [[Fraction(rng.randint(-4, 4)) for _ in range(size)] for _ in range(size)]
        B = [[Fraction(rng.randint(-4, 4)) for _ in range(size)] for _ in range(size)]
        discovered_counter, naive_counter = OperationCounter(), OperationCounter()
        began = time.perf_counter()
        discovered = sd.recursive_multiply(terms, 2, A, B, size, counter=discovered_counter)
        discovered_seconds = time.perf_counter()-began
        began = time.perf_counter()
        naive = sd.naive_multiply(A, B, size, counter=naive_counter)
        rows.append({"size": size, "same_output": discovered == naive,
                     "discovered_multiplications": discovered_counter["execute:multiply"],
                     "obvious_multiplications": naive_counter["baseline:multiply"],
                     "discovered_additions": discovered_counter["execute:add"],
                     "obvious_additions": naive_counter["baseline:add"],
                     "discovered_seconds": discovered_seconds, "obvious_seconds": time.perf_counter()-began})
    record["sizes"] = rows
    record["multiplication_exponents"] = {
        "discovered": slope([(row["size"], row["discovered_multiplications"]) for row in rows]),
        "obvious": slope([(row["size"], row["obvious_multiplications"]) for row in rows])}
    record["same_output_everywhere"] = all(row["same_output"] for row in rows)
    return record


def larger_tensor_evidence(*, seed=0, target_rank=23, steps=600_000, restarts=12, attempts=8,
                           sign_budget=1 << 12):
    tensor = sd.matrix_multiplication_tensor(3, 3, 3)
    best, counter = None, OperationCounter()
    began = time.perf_counter()
    for attempt in range(attempts):
        found = sd.search_decomposition(tensor, target_rank=target_rank, steps=steps,
                                        seed=seed*100+attempt, counter=counter, restarts=restarts)
        if best is None or found["rank"] < best["rank"]:
            best = found
        if found["reached_target"]:
            break
    lifted = (sd.lift_to_rationals(tensor, best["terms"], counter=counter, sign_budget=sign_budget)
              if best["rank"] < 27 else None)
    return {"tensor": "3x3 by 3x3 matrix multiplication", "obvious_rank": 27,
            "sign_patterns_searched_for_the_lift": sign_budget,
            "best_rank": best["rank"], "target_rank": target_rank,
            "reached_target": best["reached_target"], "exact_over_gf2": best["exact_over_gf2"],
            "exponent_over_gf2": sd.exponent(best["rank"], 3),
            "lifted_to_rationals": lifted is not None,
            "discovery": {"operations": counter["total"], "seconds": time.perf_counter()-began}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--random-families", type=int, default=6)
    parser.add_argument("--skip-large-tensor", action="store_true")
    arguments = parser.parse_args()
    output = Path(arguments.output)
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    report = {"environment": {
        "sha": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip(),
        "python": sys.version, "platform": platform.platform()},
        "protocol": {
            "question": "does a structure discovered from the operations lower the order of a family, "
                        "with the same output required of every route",
            "routes": {"enumerate": "one operation sequence at a time",
                       "iterate": "the sum of the operations applied L times",
                       "structure": "merge, find the relation, evaluate x^L mod p"},
            "costs_separated": ["discovery once per family", "transform and execute per length",
                                "the answers are checked against an independent matrix power"],
            "lengths": list(LENGTHS)}}

    families = [fam.window_family(4), fam.window_family(8), fam.window_family(10),
                fam.typed_skeleton_family()]
    report["families"] = [measure_family(family) for family in families]
    # what the system decides by itself, on families and on a tensor
    report["decisions"] = [fam.autonomous_search(family) for family in families]
    report["decisions"].extend(fam.autonomous_search(random_family(seed), target_length=4096)
                               for seed in range(arguments.random_families))
    for decision in report["decisions"]:
        decision.pop("structure", None)
    report["bilinear_decision"] = {k: v for k, v in fam.autonomous_bilinear_search(2).items()
                                   if k != "terms"}
    report["random_families"] = [measure_family(random_family(seed), lengths=(8, 64, 512, 4096))
                                 for seed in range(arguments.random_families)]
    report["bilinear"] = bilinear_evidence()
    if not arguments.skip_large_tensor:
        report["larger_tensor"] = larger_tensor_evidence()
    report["total_seconds"] = time.perf_counter()-started
    report["claims_not_made"] = [
        "the operation counts ignore the size of the numbers: an answer with twenty thousand digits "
        "costs more per operation than a short one, and the counts do not say so",
        "the discovered bilinear decomposition lowers the number of multiplications; it raises the "
        "number of additions, and in this implementation it is slower in wall time at these sizes",
        "the search over GF(2) certifies a decomposition over GF(2); a decomposition over the "
        "rationals is claimed only when the lift is found and its residual is empty",
        "the families here are small; nothing is claimed about families whose merged dimension grows",
        "no preregistered evaluation is affected: the frozen configurations, runners and results are untouched"]
    (output/"result.json").write_text(json.dumps(report, indent=1, default=str)+"\n", encoding="utf-8")
    summary = {"families": [{k: row[k] for k in ("family", "given_dimension", "merged_dimension",
                                                 "relation_degree", "empirical_exponents",
                                                 "all_answers_agree")}
                            for row in report["families"]],
               "random_families": [{k: row[k] for k in ("family", "given_dimension", "merged_dimension",
                                                        "relation_degree", "all_answers_agree")}
                                   for row in report["random_families"]],
               "bilinear": {k: report["bilinear"].get(k) for k in
                            ("searched_rank", "lifted_to_rationals", "exponent", "same_output_everywhere",
                             "multiplication_exponents")},
               "larger_tensor": report.get("larger_tensor"),
               "decisions": [{"family": row["family"], "decision": row["decision"],
                              "priced_at": row.get("priced_at")} for row in report["decisions"]],
               "bilinear_decision": report["bilinear_decision"].get("decision")}
    print(json.dumps(summary, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
