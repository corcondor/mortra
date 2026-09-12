"""Same task, twice: once without the acquired representation and once with it.

Every comparison here runs the two paths independently from the same initial
input. Neither path reads the other's output, and neither is given the answer;
the two results are compared only after both have finished.

Three comparisons, because a representation can pay off in different currencies
and one number would hide which:

    differential    repeated symbolic differentiation of a closed form, against
                    the acquired finite-dimensional differential action. The
                    thing to read is `derivative_calls_after`, and the trace
                    beside it, which is what turns "the derivative was skipped"
                    from a claim into a record.
    fold repeat     the kinematics of a repeated fold block, against the same
                    block as a matrix power of the observation representation.
                    The thing to read is the execution depth: matrix products
                    are associative and can be halved, a chain of frame updates
                    cannot.
    fold search     counting how many words of a length reach a value, by
                    enumeration against expansion over observation vectors. A
                    third arm runs the SAME merging on the raw state without the
                    representation, so the collapse can be attributed to the
                    representation rather than to the merging technique.
"""
from __future__ import annotations

import itertools

import sympy as sp

from math_os_prototype import differential_representation as R
from math_os_prototype import fold_observable_system as F
from math_os_prototype import representation_evaluation as E
from math_os_prototype.holonomic_route_discovery import X, coefficients, key
from math_os_prototype.rigid_fold_problem_discovery import (
    GENERATOR_BY_SYMBOL, apply_fold_generator)

SEED_FRAME = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
SEED_CENTRE = (0, 0, 0)
FOLD_STATE_DIMENSION = 12          # c1..c3 and the nine frame entries


# ============================================================ differential ==

def pairing_premise(program, closed_form, *, terms=8):
    """That the closed form and the program are the same function.

    Checked outside both measured runs. It is the premise that makes the later
    comparison a comparison at all, so its cost belongs to neither path.
    """
    expansion = sp.series(closed_form, X, 0, terms).removeO()
    reference = coefficients(program, terms)
    residuals = [sp.expand(expansion.coeff(X, index) - reference[index])
                 for index in range(terms)]
    return {"terms": terms, "exact": all(r == 0 for r in residuals),
            "route": ("sympy's series of the closed form against the program's "
                      "own coefficients; neither is the route under test")}


def symbolic_derivative_run(closed_form, upto):
    """The baseline: differentiate again for every order asked for."""
    expression = closed_form
    values, sizes = [], []
    for index in range(upto + 1):
        values.append(sp.expand(expression.subs(X, 0)))
        sizes.append(int(sp.count_ops(expression)))
        if index < upto:
            expression = sp.diff(expression, X)
    return {"value": [str(v) for v in values],
            "sequential_depth": upto,
            "flop_proxy": sum(sizes),
            "largest_intermediate_ops": max(sizes)}


def represented_derivative_run(record, upto):
    """The same values from the acquired representation and nothing else."""
    found = R.derivative_values(record, upto)
    return {"value": [str(v) for v in found["values"]],
            "sequential_depth": found["steps"],
            "flop_proxy": found["operations"]}


def differential_comparison(name, program, closed_form, *, upto=40,
                            check_terms=24):
    premise = pairing_premise(program, closed_form)
    if not premise["exact"]:
        raise AssertionError("the closed form and the program disagree")

    acquisition = E.measure(lambda: R.acquire(program, check_terms=check_terms))
    record = acquisition["value"]

    # the two paths, independently, from the same initial input
    baseline = E.measure(lambda: symbolic_derivative_run(closed_form, upto))
    represented = E.measure(lambda: represented_derivative_run(record, upto))
    warm = E.measure(lambda: symbolic_derivative_run(closed_form, upto), cold=False)

    # compared only now
    pairs = list(zip(baseline["value"], represented["value"]))
    agree = [left == right for left, right in pairs]
    corpus = list(baseline["value"])

    stored = {k: record[k] for k in ("order", "recurrence_polynomials",
                                     "first_solvable_index",
                                     "seed_coefficients")}
    return E.evaluate(
        name,
        representation={"kind": "differential action", "schema": record["schema"],
                        "program": record["program"], "stored": stored,
                        "expansion_point": record["expansion_point"],
                        "scope": record["scope"]},
        baseline=baseline, represented=represented,
        acquisition={
            "acquisition_time": acquisition["wall_time"],
            "acquisition_primitive_calls": acquisition["primitive_calls"],
            "acquisition_derivative_calls": acquisition["derivative_calls"],
            "acquisition_proof_calls": acquisition["proof_calls"],
            "acquisition_proof_cost": {
                "annihilator_calls": acquisition["proof_calls"],
                "series_terms_checked": check_terms,
                "checked_against": record["verification"]["checked_against"]},
            "acquisition_search_nodes": 0,
            "acquisition_search_note": ("derived from the annihilating operator "
                                        "rather than searched; there are no "
                                        "candidates to count here"),
            "acquisition_peak_memory": acquisition["peak_memory"]},
        raw_description_bits=E.description_bits(corpus),
        representation_bits=E.description_bits(stored),
        conditional_description_bits=E.description_bits({"upto": upto}),
        search_units="neither path searches; the rows are empty, not zero",
        flop_proxy_note=("before: sympy's operation count of every intermediate "
                         "expression the baseline built. after: the exact "
                         "number of rational operations the unrolling "
                         "performed"),
        raw_state_dimension=baseline["largest_intermediate_ops"],
        representation_dimension=record["order"],
        state_dimension_sense=(
            "the baseline carries a symbolic expression, which has no fixed "
            "dimension; the number recorded is the largest intermediate "
            "operation count it reached, and it grows with the order asked "
            "for. The representation carries a window of `order` coefficients, "
            "which does not."),
        memoisation_only={
            "primitive_calls": warm["primitive_calls"],
            "derivative_calls": warm["derivative_calls"],
            "wall_time": warm["wall_time"],
            "cache_hits": warm["cache_hits"],
            "sense": ("the baseline run again with the caches left warm. It is "
                      "the baseline, so whatever it saves is remembering, not "
                      "representation")},
        successful_reuses=sum(agree[:check_terms]),
        heldout_successes=sum(agree[check_terms:]),
        failed_reuses=sum(1 for ok in agree if not ok),
        agreement={
            "orders_compared": len(pairs),
            "all_agree": all(agree),
            "first_disagreement": next((index for index, ok in enumerate(agree)
                                        if not ok), None),
            "verified_at_acquisition_up_to": check_terms,
            "held_out": f"orders {check_terms}..{upto} were never checked "
                        f"during acquisition",
            "compared": "after both runs finished, never during"},
        note=premise)


# ============================================================ fold, repeat ==

def kinematic_fold_run(word):
    """The baseline: fold the chain one panel at a time and read the centre."""
    frame, centre = SEED_FRAME, SEED_CENTRE
    for symbol in word:
        frame, centre = apply_fold_generator(frame, centre,
                                             GENERATOR_BY_SYMBOL[symbol])
    return {"value": str(centre[0]), "sequential_depth": len(word),
            "flop_proxy": None}


def represented_fold_run(closure, block, repeats):
    """The same value as a matrix power of the observation representation."""
    size = len(closure["_basis"])
    matrices = closure["_matrices"]
    product, depth, multiplications = matrices[block[0]], 0, 0
    for symbol in block[1:]:
        product = matrices[symbol] * product
        depth += 1
        multiplications += 1
    powered = E.power_by_squaring(product, repeats, identity=sp.eye(size))
    vector = powered["value"] * F.initial_vector(closure)
    multiplications += powered["multiplications"]
    per_product = size ** 3 + size * size * (size - 1)
    per_action = size * size + size * (size - 1)
    return {"value": str(sp.expand(vector[0])),
            "sequential_depth": depth + powered["depth"] + 1,
            "flop_proxy": multiplications * per_product + per_action,
            "matrix_products": multiplications}


def fold_repeat_comparison(name, closure_record, acquisition, *, block, repeats,
                           extra_tasks=()):
    closure = F.closure_from_record(closure_record)
    word = block * repeats

    baseline = E.measure(lambda: kinematic_fold_run(word))
    represented = E.measure(lambda: represented_fold_run(closure, block, repeats))
    warm = E.measure(lambda: kinematic_fold_run(word), cold=False)

    agree = baseline["value"] == represented["value"]

    # every further task is held out: the acquisition looked at no block at all
    heldout = []
    for other_block, other_repeats in extra_tasks:
        left = kinematic_fold_run(other_block * other_repeats)["value"]
        right = represented_fold_run(closure, other_block, other_repeats)["value"]
        heldout.append((other_block, other_repeats, left == right))

    stored = {k: closure_record[k] for k in ("observable", "basis",
                                             "action_matrices")}
    return E.evaluate(
        name,
        representation={"kind": "observation representation",
                        "observable": closure_record["observable"],
                        "basis": closure_record["basis"],
                        "action_matrices": closure_record["action_matrices"],
                        "identity": "Phi(T_g(x)) = B_g Phi(x)"},
        baseline=baseline, represented=represented, acquisition=acquisition,
        raw_description_bits=E.description_bits(
            [kinematic_fold_run(block * count)["value"]
             for count in range(1, repeats + 1)]),
        representation_bits=E.description_bits(stored),
        conditional_description_bits=E.description_bits(
            {"block": block, "repeats": list(range(1, repeats + 1))}),
        search_units="neither path searches; the rows are empty, not zero",
        flop_proxy_note=("counted exactly for the matrix route. Not "
                         "instrumented for the kinematics, so the baseline "
                         "figure is null rather than a guess"),
        raw_state_dimension=FOLD_STATE_DIMENSION,
        representation_dimension=len(closure_record["basis"]),
        state_dimension_sense=(
            "the kinematics needs the whole state -- three centre coordinates "
            "and the nine frame entries -- to take one more fold. The "
            "representation needs only the closed observable space."),
        memoisation_only={
            "primitive_calls": warm["primitive_calls"],
            "fold_step_calls": warm["fold_step_calls"],
            "wall_time": warm["wall_time"],
            "cache_hits": warm["cache_hits"],
            "sense": ("the kinematic baseline run again with the caches warm. "
                      "The fold kinematics is not memoised at all, so this is "
                      "the measurement that says so.")},
        successful_reuses=1 if agree else 0,
        heldout_successes=sum(1 for _, _, ok in heldout if ok),
        failed_reuses=(0 if agree else 1) + sum(1 for _, _, ok in heldout if not ok),
        agreement={"word_length": len(word), "agree": agree,
                   "held_out_tasks": [{"block": b, "repeats": r, "agree": ok}
                                      for b, r, ok in heldout],
                   "held_out_sense": ("the acquisition proved closure of the "
                                      "observable space under the four letters "
                                      "and looked at no block; every block "
                                      "here is therefore held out"),
                   "compared": "after both runs finished, never during"},
        note=("depth before is the chain of frame updates, which cannot be "
              "reordered; depth after is the block product, the squarings of "
              "the power, and one action on the initial vector"))


# ============================================================ fold, search ==

def enumerated_search_run(length):
    """The baseline: every word, folded, and its centre coordinate read."""
    counts, nodes = {}, 0
    for word in itertools.product(F.ALPHABET, repeat=length):
        frame, centre = SEED_FRAME, SEED_CENTRE
        for symbol in word:
            frame, centre = apply_fold_generator(frame, centre,
                                                 GENERATOR_BY_SYMBOL[symbol])
            nodes += 1
        counts[centre[0]] = counts.get(centre[0], 0) + 1
    target = max(counts)
    return {"value": {"target": str(target), "words_at_target": counts[target],
                      "distinct_values": len(counts),
                      "total_words": sum(counts.values())},
            "sequential_depth": length,
            "candidates_generated": len(F.ALPHABET) ** length,
            "search_nodes": nodes,
            "rejected_candidates": sum(counts.values()) - counts[target]}


def raw_state_merge_run(length):
    """The control arm: the same merging, on the raw state, no representation.

    This exists so the collapse in the represented run can be attributed. If
    merging equal states were the whole story, this arm would match it.
    """
    layer, nodes = {(SEED_FRAME, SEED_CENTRE): 1}, 0
    for _ in range(length):
        following = {}
        for (frame, centre), multiplicity in layer.items():
            for symbol in F.ALPHABET:
                moved = apply_fold_generator(frame, centre,
                                             GENERATOR_BY_SYMBOL[symbol])
                nodes += 1
                following[moved] = following.get(moved, 0) + multiplicity
        layer = following
    counts = {}
    for (_, centre), multiplicity in layer.items():
        counts[centre[0]] = counts.get(centre[0], 0) + multiplicity
    target = max(counts)
    return {"value": {"target": str(target), "words_at_target": counts[target],
                      "distinct_values": len(counts),
                      "total_words": sum(counts.values())},
            "sequential_depth": length,
            "candidates_generated": len(layer),
            "search_nodes": nodes,
            "rejected_candidates": sum(counts.values()) - counts[target],
            "distinct_raw_states_at_depth": len(layer)}


def represented_search_run(closure, length):
    """Expansion over observation vectors, with the word counts carried along.

    Two words with the same observation vector are the same problem for this
    question, so they are merged -- and the multiplicity is kept, so the answer
    is still a count of words and not a count of classes.
    """
    matrices = closure["_matrices"]
    size = len(closure["_basis"])
    start = F.initial_vector(closure)
    layer, nodes = {tuple(start): 1}, 0
    for _ in range(length):
        following = {}
        for vector, multiplicity in layer.items():
            column = sp.Matrix(list(vector))
            for symbol in F.ALPHABET:
                moved = tuple(matrices[symbol] * column)
                nodes += 1
                following[moved] = following.get(moved, 0) + multiplicity
        layer = following
    counts = {}
    for vector, multiplicity in layer.items():
        counts[vector[0]] = counts.get(vector[0], 0) + multiplicity
    target = max(counts)
    return {"value": {"target": str(target), "words_at_target": counts[target],
                      "distinct_values": len(counts),
                      "total_words": sum(counts.values())},
            "sequential_depth": length,
            "candidates_generated": len(layer),
            "search_nodes": nodes,
            "rejected_candidates": sum(counts.values()) - counts[target],
            "flop_proxy": nodes * (size * size + size * (size - 1))}


def fold_search_comparison(name, closure_record, acquisition, *, length,
                           heldout_lengths=()):
    closure = F.closure_from_record(closure_record)

    baseline = E.measure(lambda: enumerated_search_run(length))
    represented = E.measure(lambda: represented_search_run(closure, length))
    warm = E.measure(lambda: enumerated_search_run(length), cold=False)
    control = E.measure(lambda: raw_state_merge_run(length))

    agree = baseline["value"] == represented["value"]
    heldout = []
    for other in heldout_lengths:
        left = raw_state_merge_run(other)["value"]      # exact, and affordable
        right = represented_search_run(closure, other)["value"]
        heldout.append((other, left == right))

    stored = {k: closure_record[k] for k in ("observable", "basis",
                                             "action_matrices")}
    record = E.evaluate(
        name,
        representation={"kind": "observation representation",
                        "observable": closure_record["observable"],
                        "basis": closure_record["basis"],
                        "action_matrices": closure_record["action_matrices"],
                        "identity": "Phi(T_g(x)) = B_g Phi(x)"},
        baseline=baseline, represented=represented, acquisition=acquisition,
        raw_description_bits=E.description_bits(baseline["value"]),
        representation_bits=E.description_bits(stored),
        conditional_description_bits=E.description_bits({"length": length}),
        search_units=("candidates_generated counts what was expanded -- words "
                      "on the baseline, distinct observation vectors on the "
                      "represented run, which is the reduction itself and not "
                      "a change of question. search_nodes counts state updates "
                      "against matrix actions. rejected_candidates is in WORDS "
                      "on both sides, because the represented run carries the "
                      "multiplicity of each vector"),
        flop_proxy_note=("counted exactly for the matrix route (one 4x4 action "
                         "per node). Not instrumented for the kinematics: the "
                         "integer arithmetic inside apply_fold_generator was "
                         "not counted, so the baseline figure is null rather "
                         "than a guess"),
        raw_state_dimension=FOLD_STATE_DIMENSION,
        representation_dimension=len(closure_record["basis"]),
        state_dimension_sense=(
            "the search over raw states keeps frame and centre apart even when "
            "the question cannot tell them apart; the observation vector is "
            "what the question actually reads"),
        memoisation_only={
            "primitive_calls": warm["primitive_calls"],
            "fold_step_calls": warm["fold_step_calls"],
            "wall_time": warm["wall_time"],
            "cache_hits": warm["cache_hits"],
            "sense": "the enumeration again with warm caches; it memoises nothing"},
        successful_reuses=1 if agree else 0,
        heldout_successes=sum(1 for _, ok in heldout if ok),
        failed_reuses=(0 if agree else 1) + sum(1 for _, ok in heldout if not ok),
        agreement={"agree": agree,
                   "baseline_answer": baseline["value"],
                   "represented_answer": represented["value"],
                   "held_out_lengths": [{"length": n, "agree": ok}
                                        for n, ok in heldout],
                   "compared": "after both runs finished, never during"},
        note=("the answer is a count of words, on both sides; the represented "
              "run merges words with equal observation vectors and carries the "
              "multiplicity, so the two answers are the same object"))
    record["attribution_control"] = {
        "arm": "the same merging, on the raw state, without the representation",
        "search_nodes": control["search_nodes"],
        "candidates_generated": control["candidates_generated"],
        "distinct_raw_states_at_depth": control["candidates_generated"],
        "distinct_observation_vectors_at_depth": represented["candidates_generated"],
        "fold_step_calls": control["fold_step_calls"],
        "wall_time": control["wall_time"],
        "agrees_with_baseline": control["value"] == baseline["value"],
        "sense": ("whatever this arm saves is merging. What the represented run "
                  "saves beyond it is the representation, because the only "
                  "difference between the two is which state is merged on.")}
    return record
