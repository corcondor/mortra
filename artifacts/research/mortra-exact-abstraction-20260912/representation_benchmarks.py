"""Same task, once per rung of the ladder, so the saving can be attributed.

Every run here is independent: the paths start from the same input, none of them
reads another's output, and the results are compared only after all of them have
finished.

The ladder, and why each rung exists:

    naive            the obvious route, caches cleared. The number everything
                     else is measured against.
    memoised         the same route again with the caches warm. Whatever it
                     saves is remembering, not structure.
    mathematical     an existing route in this repository that is cheaper for
                     mathematical reasons and needs nothing learned -- the
                     holonomic coefficient recursion for the differential task,
                     the fold word summary monoid for the repeated block. This
                     is the strongest baseline, and the one that decides whether
                     the learned representation is worth anything at all.
    generic_search   a standard search improvement -- merging words that reach
                     equal states -- with no learned representation.
    representation   the learned representation, on top of all of the above.

The representation is not used for a task unless a certificate admits it. A
refusal is not a low score: the represented arm is not run, and the record says
which check refused it and with what counterexample.
"""
from __future__ import annotations

import itertools

import sympy as sp

from math_os_prototype import differential_representation as R
from math_os_prototype import fold_observable_system as F
from math_os_prototype import representation_certificate as certificates
from math_os_prototype import quotient_counting
from math_os_prototype import representation_evaluation as E
from math_os_prototype.holonomic_route_discovery import X, coefficients, key
from math_os_prototype.rigid_fold_problem_discovery import (
    FoldWordSummary, GENERATOR_BY_SYMBOL, IDENTITY_FRAME, apply_fold_generator,
    _summarize_single_generator, compose_fold_word_summaries)

SEED_FRAME = IDENTITY_FRAME
SEED_CENTRE = (0, 0, 0)
FOLD_STATE_DIMENSION = 12          # c1..c3 and the nine frame entries

#: the empty word under the repository's own summary composition
EMPTY_SUMMARY = FoldWordSummary(0, IDENTITY_FRAME, (0, 0, 0), (0, 0, 0), 0, ())


# ============================================================ differential ==

def pairing_premise(program, closed_form, *, terms=8):
    """That the closed form and the program are the same function.

    Checked outside every measured run. It is the premise that makes the later
    comparison a comparison at all, so its cost belongs to no rung.
    """
    expansion = sp.series(closed_form, X, 0, terms).removeO()
    reference = coefficients(program, terms)
    residuals = [sp.expand(expansion.coeff(X, index) - reference[index])
                 for index in range(terms)]
    return {"terms": terms, "exact": all(r == 0 for r in residuals),
            "route": ("sympy series of the closed form against the program's "
                      "own coefficients; neither is a route under test")}


def symbolic_derivative_run(closed_form, upto):
    """naive: differentiate again for every order asked for."""
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


def existing_holonomic_run(program, upto):
    """mathematical: the coefficient route this repository already had.

    `holonomic_route_discovery.coefficients` reaches the Taylor coefficients by
    closure arithmetic on the program tree. Differentiation is already an index
    shift there, so this route takes no derivative either -- which is exactly
    why it has to be measured. Whatever the learned representation is worth, it
    is worth it over THIS, not over repeated symbolic differentiation.
    """
    series = coefficients(program, upto + 1)
    values = [sp.factorial(index) * value for index, value in enumerate(series)]
    return {"value": [str(v) for v in values],
            "sequential_depth": upto,
            "flop_proxy": None,
            "route": "holonomic_route_discovery.coefficients, unchanged"}


def represented_derivative_run(record, upto):
    """representation: the acquired differential action, and nothing else."""
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

    naive = E.measure(lambda: symbolic_derivative_run(closed_form, upto))
    memoised = E.measure(lambda: symbolic_derivative_run(closed_form, upto),
                         cold=False)
    mathematical = E.measure(lambda: existing_holonomic_run(program, upto))
    represented = E.measure(lambda: represented_derivative_run(record, upto))

    # compared only now
    agree = [a == b for a, b in zip(naive["value"], represented["value"])]
    against_existing = [a == b for a, b in zip(mathematical["value"],
                                               represented["value"])]
    corpus = list(naive["value"])

    stored = {k: record[k] for k in ("order", "recurrence_polynomials",
                                     "first_solvable_index",
                                     "seed_coefficients")}
    return E.evaluate(
        name,
        representation={"kind": "differential action", "schema": record["schema"],
                        "program": record["program"], "stored": stored,
                        "dimension": record["order"],
                        "observable": f"jet of {record['program'][:44]}",
                        "expansion_point": record["expansion_point"],
                        "scope": record["scope"]},
        baseline=naive, represented=represented,
        ladder={"naive": naive, "memoised": memoised,
                "mathematical": mathematical, "generic_search": None,
                "representation": represented},
        certificate={"schema": "mortra.differential-verification.v1",
                     "task": name, "admissible": True,
                     "verdict": "admitted, checked against an independent route",
                     "checks": [{"name": "series", "holds": True,
                                 "kind": "checked to a stated range",
                                 "statement":
                                     record["verification"]["checked_against"],
                                 "terms": record["verification"]["terms"]}],
                     "refused_by": [],
                     "scope": record["scope"]},
        acquisition={
            "acquisition_time": acquisition["wall_time"],
            "acquisition_primitive_calls": acquisition["primitive_calls"],
            "acquisition_derivative_calls": acquisition["derivative_calls"],
            "acquisition_derivative_request_calls":
                acquisition["derivative_request_calls"],
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
        flop_proxy_note=("before: sympy operation count of every intermediate "
                         "expression the naive route built. after: the exact "
                         "number of rational operations the unrolling did. The "
                         "existing holonomic rung was not instrumented for "
                         "operations and reports null rather than a guess"),
        raw_state_dimension=naive["largest_intermediate_ops"],
        representation_dimension=record["order"],
        state_dimension_sense=(
            "the naive route carries a symbolic expression, which has no fixed "
            "dimension; the number recorded is the largest intermediate "
            "operation count it reached, and it grows with the order asked for. "
            "The representation carries a window of `order` coefficients, which "
            "does not."),
        memoisation_only={
            "primitive_calls": memoised["primitive_calls"],
            "derivative_calls": memoised["derivative_calls"],
            "wall_time": memoised["wall_time"],
            "cache_hits": memoised["cache_hits"],
            "sense": ("the naive route again with the caches left warm, so "
                      "whatever it saves is remembering, not representation")},
        successful_reuses=sum(agree[:check_terms]),
        heldout_successes=sum(agree[check_terms:]),
        failed_reuses=sum(1 for ok in agree if not ok),
        agreement={
            "orders_compared": len(agree),
            "all_agree": all(agree),
            "agrees_with_existing_holonomic_route": all(against_existing),
            "first_disagreement": next((i for i, ok in enumerate(agree)
                                        if not ok), None),
            "verified_at_acquisition_up_to": check_terms,
            "held_out": f"orders {check_terms}..{upto} were never checked "
                        f"during acquisition",
            "compared": "after every run finished, never during"},
        note=premise)


# ============================================================ fold, repeat ==

def kinematic_fold_run(word):
    """naive: fold the chain one panel at a time and read the centre."""
    frame, centre = SEED_FRAME, SEED_CENTRE
    for symbol in word:
        frame, centre = apply_fold_generator(frame, centre,
                                             GENERATOR_BY_SYMBOL[symbol])
    return {"value": str(centre[0]), "sequential_depth": len(word),
            "flop_proxy": None}


def summary_monoid_fold_run(block, repeats):
    """mathematical: the fold word summary monoid this repository already had.

    `compose_fold_word_summaries` is associative, so the repeated block can be
    squared here exactly as it can under the learned representation -- with
    nothing learned. This rung is what decides whether the depth reduction
    belongs to the learned representation or was available all along.
    """
    terminals = {symbol: _summarize_single_generator(generator)
                 for symbol, generator in GENERATOR_BY_SYMBOL.items()}
    summary, depth, compositions = EMPTY_SUMMARY, 0, 0
    for symbol in block:
        summary = compose_fold_word_summaries(summary, terminals[symbol])
        depth += 1
        compositions += 1
    result, base, remaining = EMPTY_SUMMARY, summary, repeats
    while remaining:
        if remaining & 1:
            result = compose_fold_word_summaries(result, base)
            depth += 1
            compositions += 1
        remaining >>= 1
        if remaining:
            base = compose_fold_word_summaries(base, base)
            depth += 1
            compositions += 1
    return {"value": str(result.doubled_end_center[0]),
            "sequential_depth": depth, "flop_proxy": None,
            "compositions": compositions,
            "route": ("rigid_fold_problem_discovery."
                      "compose_fold_word_summaries, unchanged")}


def represented_fold_run(closure, block, repeats):
    """representation: the same value as a matrix power of the observation."""
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
                           extra_tasks=(), certificate=None):
    closure = F.closure_from_record(closure_record)
    word = block * repeats

    naive = E.measure(lambda: kinematic_fold_run(word))
    memoised = E.measure(lambda: kinematic_fold_run(word), cold=False)
    mathematical = E.measure(lambda: summary_monoid_fold_run(block, repeats))
    represented = E.measure(lambda: represented_fold_run(closure, block, repeats))

    agree = naive["value"] == represented["value"]
    agrees_with_existing = mathematical["value"] == represented["value"]

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
                        "dimension": len(closure_record["basis"]),
                        "action_matrices": closure_record["action_matrices"],
                        "identity": "Phi(T_g(x)) = B_g Phi(x)"},
        baseline=naive, represented=represented, acquisition=acquisition,
        certificate=certificate,
        ladder={"naive": naive, "memoised": memoised,
                "mathematical": mathematical, "generic_search": None,
                "representation": represented},
        raw_description_bits=E.description_bits(
            [kinematic_fold_run(block * count)["value"]
             for count in range(1, repeats + 1)]),
        representation_bits=E.description_bits(stored),
        conditional_description_bits=E.description_bits(
            {"block": block, "repeats": list(range(1, repeats + 1))}),
        search_units="neither path searches; the rows are empty, not zero",
        flop_proxy_note=("counted exactly for the matrix route. Not "
                         "instrumented for the kinematics or the summary "
                         "monoid, so those figures are null rather than a guess"),
        raw_state_dimension=FOLD_STATE_DIMENSION,
        representation_dimension=len(closure_record["basis"]),
        state_dimension_sense=(
            "the kinematics needs the whole state -- three centre coordinates "
            "and the nine frame entries -- to take one more fold. The "
            "representation needs only the closed observable space. The summary "
            "monoid rung carries its own summary, which is larger than both."),
        memoisation_only={
            "primitive_calls": memoised["primitive_calls"],
            "fold_step_calls": memoised["fold_step_calls"],
            "wall_time": memoised["wall_time"],
            "cache_hits": memoised["cache_hits"],
            "sense": ("the kinematic route again with warm caches. The fold "
                      "kinematics is not memoised at all, so this is the "
                      "measurement that says so.")},
        successful_reuses=1 if agree else 0,
        heldout_successes=sum(1 for _, _, ok in heldout if ok),
        failed_reuses=(0 if agree else 1) + sum(1 for _, _, ok in heldout if not ok),
        agreement={"word_length": len(word), "agree": agree,
                   "agrees_with_existing_monoid_route": agrees_with_existing,
                   "held_out_tasks": [{"block": b, "repeats": r, "agree": ok}
                                      for b, r, ok in heldout],
                   "held_out_sense": ("the acquisition proved closure of the "
                                      "observable space under the four letters "
                                      "and looked at no block; every block here "
                                      "is therefore held out"),
                   "compared": "after every run finished, never during"},
        note=("depth on the naive rung is the chain of frame updates, which "
              "cannot be reordered. Both the existing summary monoid and the "
              "learned representation are associative and can be squared, so "
              "read the mathematical rung before crediting the depth reduction "
              "to the representation"))


# ============================================================ fold, search ==
#
# Every rung below calls the SAME dynamic programme in `quotient_counting`, with
# the same legality and the same evaluation, so the four answers are the same
# kind of object and the comparison is between routes rather than between
# questions. What differs between rungs is only what states are merged on.

def enumerate_rung(task, length):
    """naive: walk every legal word. The statement the others must reproduce."""
    found = quotient_counting.enumerate_count(
        start=task.seed_state, step=task.step, legal=task.legal_step,
        value=task.value, alphabet=task.alphabet, length=length)
    return _counting_run(found, length, candidates=found["words_walked"])


def concrete_merge_rung(task, length):
    """generic_search: merge equal CONCRETE states inside a layer.

    A standard technique needing nothing learned. Whatever it saves is not the
    representation saving it.
    """
    found = quotient_counting.layered_count(
        start=task.seed_state, step=task.step, legal=task.legal_step,
        value=task.value, alphabet=task.alphabet, length=length)
    return _counting_run(found, length, candidates=found["classes_at_end"])


def represented_rung(closure, certificate, task, length):
    """representation: merge on the observation the certificate admitted.

    The evaluation is the certified read-out, not the first basis coordinate.
    Where the certificate admitted the observable by span membership the
    read-out is the exact linear combination it produced.
    """
    routes = certificates.abstract_routes(closure, certificate, task)
    observe = certificates.compiled_observation(closure)
    found = quotient_counting.layered_count(
        start=routes["start_from"](task.seed_state, observe),
        step=routes["step"], legal=routes["legal"], value=routes["value"],
        alphabet=task.alphabet, length=length, key=routes["key"])
    run = _counting_run(found, length, candidates=found["classes_at_end"])
    run["readout_is_linear"] = routes["readout_is_linear"]
    run["carries_witness"] = routes["carries_witness"]
    if routes["carries_witness"]:
        run["witness_reason"] = routes["witness_reason"]
    return run


def _counting_run(found, length, *, candidates):
    answer = found["answer"]
    return {"value": answer, "distribution": found["distribution"],
            "sequential_depth": length,
            "candidates_generated": candidates,
            "search_nodes": found["nodes"],
            "transitions": found["transitions"],
            "illegal_steps": found["illegal_steps"],
            "rejected_candidates": (answer["total_words"] - answer["count_max"]),
            "states_per_layer": found.get("states_per_layer")}


def fold_search_comparison(name, closure_record, acquisition, *, task, length,
                           certificate, heldout_lengths=()):
    """The counting task, once per rung -- if the certificate admits it.

    A refusal stops the represented rung from running at all. The record is then
    a refusal record: which check refused, with its counterexample, and no
    represented measurement, because none was taken.
    """
    if not certificates.admissible(certificate):
        return {"schema": E.SCHEMA, "name": name, "refused": True,
                "certificate": certificate,
                "representation": {"kind": "observation representation",
                                   "observable": closure_record["observable"],
                                   "basis": closure_record["basis"],
                                   "dimension": len(closure_record["basis"])},
                "reason": ("the certificate does not admit this representation "
                           "for this task, so it was not used and nothing was "
                           "measured with it"),
                "refused_by": (certificate or {}).get("refused_by"),
                "counterexample": next(
                    (check["counterexample"] for check
                     in (certificate or {}).get("checks", [])
                     if check.get("counterexample")), None)}

    closure = F.closure_from_record(closure_record)

    naive = E.measure(lambda: enumerate_rung(task, length))
    memoised = E.measure(lambda: enumerate_rung(task, length), cold=False)
    generic = E.measure(lambda: concrete_merge_rung(task, length))
    represented = E.measure(lambda: represented_rung(closure, certificate, task,
                                                     length))

    agree = naive["value"] == represented["value"]
    distributions_agree = naive["distribution"] == represented["distribution"]
    generic_agrees = generic["value"] == naive["value"]
    heldout = []
    for other in heldout_lengths:
        left = concrete_merge_rung(task, other)
        right = represented_rung(closure, certificate, task, other)
        heldout.append((other, left["value"] == right["value"]
                        and left["distribution"] == right["distribution"]))

    stored = {k: closure_record[k] for k in ("observable", "basis",
                                             "action_matrices")}
    record = E.evaluate(
        name,
        representation={"kind": "observation representation",
                        "observable": closure_record["observable"],
                        "basis": closure_record["basis"],
                        "dimension": len(closure_record["basis"]),
                        "action_matrices": closure_record["action_matrices"],
                        "identity": "Phi(T_g(x)) = B_g Phi(x)"},
        baseline=naive, represented=represented, acquisition=acquisition,
        certificate=certificate,
        ladder={"naive": naive, "memoised": memoised, "mathematical": None,
                "generic_search": generic, "representation": represented},
        raw_description_bits=E.description_bits(naive["value"]),
        representation_bits=E.description_bits(stored),
        conditional_description_bits=E.description_bits({"length": length}),
        search_units=("candidates_generated counts what survived to the last "
                      "layer -- words on the naive rung, distinct concrete "
                      "states on the generic rung, distinct observations on the "
                      "represented one. search_nodes counts (state, label) "
                      "pairs examined on every rung, which is the same quantity "
                      "throughout. rejected_candidates is in WORDS on every "
                      "rung, because the merging rungs carry multiplicity"),
        flop_proxy_note=("not instrumented on any rung of this comparison; the "
                         "figures are null rather than a guess"),
        raw_state_dimension=FOLD_STATE_DIMENSION,
        representation_dimension=len(closure_record["basis"]),
        state_dimension_sense=(
            "the generic rung keeps two states apart whenever any of the twelve "
            "coordinates differs, even where the question cannot tell them "
            "apart. The observation is what the question actually reads."),
        memoisation_only={
            "primitive_calls": memoised["primitive_calls"],
            "fold_step_calls": memoised["fold_step_calls"],
            "wall_time": memoised["wall_time"],
            "cache_hits": memoised["cache_hits"],
            "sense": "the enumeration again with warm caches; it memoises nothing"},
        successful_reuses=1 if agree else 0,
        heldout_successes=sum(1 for _, ok in heldout if ok),
        failed_reuses=(0 if agree else 1) + sum(1 for _, ok in heldout if not ok),
        agreement={"agree": agree,
                   "distributions_agree": distributions_agree,
                   "naive_answer": naive["value"],
                   "generic_answer": generic["value"],
                   "represented_answer": represented["value"],
                   "generic_agrees_with_naive": generic_agrees,
                   "held_out_lengths": [{"length": n, "agree": ok}
                                        for n, ok in heldout],
                   "compared": ("after every run finished, never during. The "
                                "maximum, the count attaining it AND the whole "
                                "distribution are compared, not only the total "
                                "word count")},
        note=("every rung runs the same layered DP under the same legality, so "
              "the rungs differ only in what they merge on"))
    record["comparison_scope"] = {
        "rungs_run": ["naive enumeration", "the same route with warm caches",
                      "merging equal concrete states",
                      "merging on the certified observation"],
        "rung_not_run": {
            "name": "an existing routine that drops unneeded state components",
            "why": ("this repository has no such routine for this task. The "
                    "fold word summary monoid is the nearest thing, and for a "
                    "counting task its summary carries the same centre and "
                    "frame the concrete merge already uses, so it would not be "
                    "a further reduction. It is therefore absent rather than "
                    "assumed, and the comparison range is the four rungs above")},
        "equal_across_rungs": ("task, legality, evaluated quantity, the object "
                               "counted, and exactness. Every rung calls the "
                               "same layered DP; only the merging key differs"),
        "not_compared": ("building every panel against returning one coordinate. "
                         "No rung here builds panels for the unconstrained "
                         "task, so that difference is not being counted as a "
                         "saving")}
    record["attribution_control"] = {
        "arm": "merging equal concrete states -- a standard technique, nothing learned",
        "search_nodes": generic["search_nodes"],
        "candidates_generated": generic["candidates_generated"],
        "distinct_concrete_states_at_depth": generic["candidates_generated"],
        "distinct_observations_at_depth": represented["candidates_generated"],
        "fold_step_calls": generic["fold_step_calls"],
        "wall_time": generic["wall_time"],
        "agrees_with_naive": generic_agrees,
        "sense": ("whatever this arm saves is the merging technique. What the "
                  "represented arm saves BEYOND it is the representation, "
                  "because the only difference between the two is which state "
                  "the merging happens on.")}
    return record
