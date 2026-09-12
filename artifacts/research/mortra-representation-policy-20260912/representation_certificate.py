"""Whether a representation may be used for a task, and the refusal when it may not.

Merging two words because their observation vectors agree is only sound when the
representation preserves what the task actually depends on. Four things are
checked, separately, and a failure in any one of them refuses the representation
for that task rather than lowering a score:

    transition   `Phi(T_g(x)) = B_g Phi(x)` for every letter. This comes from the
                 closure prover as a polynomial identity, so it holds for every
                 state and every finite word.
    observable   the quantity the task reads must be a function of `Phi`. Where
                 the task states it symbolically this is decided exactly, by
                 asking whether the expression lies in the linear span of the
                 basis -- a proof for every state. Where it does not, the weaker
                 congruence search below is used and the result says so.
    goal         the goal must be decidable from the observable. A goal given as
                 a predicate on the observed value is preserved exactly when the
                 observable is; a goal given on the raw state is searched.
    legality     whichever words the task is allowed to use must be decidable
                 from `Phi` too. This is the one that most often fails. Legality
                 is checked over WORDS, not over states, because a constraint
                 like "the folded chain does not intersect itself" is a property
                 of the whole word and no function of the final state expresses
                 it -- which is exactly why the refusal is structural rather than
                 a matter of checking further.

The two verdicts are not symmetric, and the record says which one it is:

    refused      a counterexample was exhibited -- two words with the same `Phi`
                 and different values. That is a proof of failure, and the
                 representation is then not offered for the task at all.
    admitted     either a symbolic proof, or no counterexample within the
                 checked depth. The second is scoped, not a proof, and the
                 record carries the depth and how many words were compared.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Callable

import sympy as sp

from math_os_prototype import fold_observable_system as observables

SCHEMA = "mortra.representation-certificate.v1"


@dataclass(frozen=True)
class TaskSpec:
    """What a task needs preserved. Supplied by the task, not the representation.

    Every predicate takes `(state, word)`. Passing the word is not a convenience:
    a legality constraint on the path cannot be written as a function of the
    state, and a certificate that only ever saw states could not notice that.
    """

    name: str
    alphabet: tuple
    seed_state: tuple
    step: Callable                      # (state, symbol) -> state
    observable_value: Callable          # (state, word) -> exact value
    #: the same quantity written in the state variables, when the task can say
    #: it. Present means the observable check is decided rather than sampled.
    observable_expression: object = None
    goal: str = "read the observable"
    goal_from_state: Callable = None    # (state, word) -> hashable verdict
    legal: Callable = None              # (state, word) -> bool; None means all
    notes: str = ""


# ---- what the checks run over ----------------------------------------------

def reachable_words(task, depth):
    """Every word up to `depth`, with the state it reaches.

    Words, not deduplicated states: the search that these certificates license
    merges words, so that is the set a congruence has to hold on.
    """
    out = [("", tuple(task.seed_state))]
    frontier = [("", tuple(task.seed_state))]
    for _ in range(depth):
        following = []
        for word, state in frontier:
            for symbol in task.alphabet:
                following.append((word + symbol, tuple(task.step(state, symbol))))
        out.extend(following)
        frontier = following
    return out


def compiled_observation(closure):
    """`Phi` as integer arithmetic, compiled once from its polynomial form.

    Exact: coefficients and state are integers throughout. Compiled because a
    certificate compares thousands of words, and a sympy substitution per basis
    element per word would cost more than the task it is certifying.
    """
    programs = []
    for expression in closure["_basis"]:
        polynomial = sp.Poly(sp.expand(expression), *observables.VARIABLES)
        programs.append([(tuple(int(e) for e in monomial), int(coefficient))
                         for monomial, coefficient
                         in zip(polynomial.monoms(), polynomial.coeffs())])

    def observe(state):
        out = []
        for terms in programs:
            total = 0
            for exponents, coefficient in terms:
                value = coefficient
                for index, power in enumerate(exponents):
                    for _ in range(power):
                        value *= state[index]
                total += value
            out.append(total)
        return tuple(out)

    return observe


# ---- the individual checks -------------------------------------------------

def transition_check(closure_record, premise=None):
    """Read off the closure prover; not re-derived here."""
    exact = bool(closure_record.get("identity_residuals_all_zero"))
    return {"name": "transition", "holds": exact,
            "kind": "proof" if exact else "refusal",
            "statement": "Phi(T_g(x)) = B_g Phi(x) for every letter g",
            "from": ("finite_generator_problem_dna."
                     "discover_action_observable_basis, checked as a polynomial "
                     "identity"),
            "scope": (closure_record.get("closure_scope")
                      or closure_record.get("scope")
                      or "all finite words; linear closure of the observations"),
            "premise": premise}


def span_membership(closure, expression):
    """Is `expression` an exact linear combination of the basis? A decision.

    Exact linear algebra over the monomials that occur, so an answer here is a
    statement about every state, not about the sampled ones.
    """
    if expression is None:
        return None
    target = sp.expand(sp.sympify(expression))
    basis = [sp.expand(b) for b in closure["_basis"]]
    monomials = sorted({m for p in basis + [target]
                        for m in sp.Poly(p, *observables.VARIABLES).monoms()})

    def column(polynomial):
        poly = sp.Poly(polynomial, *observables.VARIABLES)
        table = dict(zip(poly.monoms(), poly.coeffs()))
        return [table.get(m, sp.S.Zero) for m in monomials]

    columns = [sp.Matrix(column(p)) for p in basis]
    if not columns:
        return {"member": False, "coefficients": None}
    matrix = sp.Matrix.hstack(*columns)
    vector = sp.Matrix(column(target))
    if matrix.rank() != sp.Matrix.hstack(matrix, vector).rank():
        return {"member": False, "coefficients": None}
    solution, parameters = matrix.gauss_jordan_solve(vector)
    solution = solution.subs({parameter: 0 for parameter in parameters})
    if sp.expand(matrix * solution - vector) != sp.zeros(matrix.rows, 1):
        return {"member": False, "coefficients": None}
    return {"member": True, "coefficients": [str(c) for c in solution]}


def congruence_check(closure, task, predicate, *, depth, label, observe=None):
    """Is `predicate` constant on the classes `Phi` induces over words?

    Two words with the same observation and different values is a counterexample
    and refuses the representation outright. Finding none is reported as what it
    is: no counterexample within this depth.
    """
    observe = observe or compiled_observation(closure)
    words = reachable_words(task, depth)
    classes = {}
    for word, state in words:
        key = observe(state)
        value = predicate(state, word)
        if key in classes and classes[key][0] != value:
            first_value, first_word, first_state = classes[key]
            return {"name": label, "holds": False, "kind": "refusal",
                    "counterexample": {
                        "observation": [str(v) for v in key],
                        "word_a": first_word, "value_a": str(first_value),
                        "state_a": list(first_state),
                        "word_b": word, "value_b": str(value),
                        "state_b": list(state)},
                    "words_compared": len(words), "depth": depth,
                    "statement": (f"{label} is constant on the classes Phi "
                                  "induces on words")}
        classes.setdefault(key, (value, word, state))
    return {"name": label, "holds": True,
            "kind": "no counterexample within depth",
            "words_compared": len(words), "classes": len(classes),
            "depth": depth,
            "statement": f"{label} is constant on the classes Phi induces on words",
            "scope": (f"checked on every word of length at most {depth}; this is "
                      "not a proof for longer words")}


# ---- the certificate --------------------------------------------------------

def certify(closure_record, task, *, depth=5, premise=None):
    """Four checks, kept apart, and one verdict that is their conjunction."""
    closure = observables.closure_from_record(closure_record)
    observe = compiled_observation(closure)
    checks = [transition_check(closure_record, premise)]

    membership = span_membership(closure, task.observable_expression)
    if membership and membership["member"]:
        checks.append({
            "name": "observable", "holds": True, "kind": "proof",
            "statement": ("the observable is an exact linear combination of the "
                          "basis, so Phi determines it at every state"),
            "coefficients": membership["coefficients"],
            "scope": "every state, not only the reachable ones"})
    elif membership is not None:
        checks.append({
            "name": "observable", "holds": False, "kind": "refusal",
            "statement": ("the observable is not in the linear span of the "
                          "basis, so Phi does not determine it"),
            "scope": "decided exactly, by rank"})
    else:
        checks.append(congruence_check(closure, task, task.observable_value,
                                       depth=depth, label="observable",
                                       observe=observe))

    if task.goal_from_state is None:
        checks.append({
            "name": "goal", "holds": True, "kind": "structural",
            "statement": ("the goal is stated as a predicate on the observed "
                          "value, so it is preserved exactly when the "
                          "observable is"),
            "goal": task.goal, "depends_on": "observable"})
    else:
        checks.append(congruence_check(closure, task, task.goal_from_state,
                                       depth=depth, label="goal",
                                       observe=observe))

    if task.legal is None:
        checks.append({
            "name": "legality", "holds": True, "kind": "proof",
            "statement": ("the task places no constraint on which words may be "
                          "used, so legality is trivially a function of Phi"),
            "scope": "every word"})
    else:
        checks.append(congruence_check(closure, task, task.legal,
                                       depth=depth, label="legality",
                                       observe=observe))

    refusals = [check for check in checks if not check["holds"]]
    proved = all(check["kind"] in ("proof", "structural") for check in checks)
    return {
        "schema": SCHEMA, "task": task.name,
        "observable": closure_record.get("observable"),
        "dimension": len(closure_record["basis"]),
        "admissible": not refusals,
        "verdict": ("refused" if refusals else
                    "admitted, proved" if proved else
                    "admitted, no counterexample within depth"),
        "checks": checks,
        "refused_by": [check["name"] for check in refusals],
        "may_merge_states": not refusals,
        "depth": depth,
        "sense": ("merging two words because their observations agree is sound "
                  "for this task only under this certificate. A refusal is a "
                  "counterexample and is final for the task; an admission "
                  "without a proof carries the depth it was checked to."),
        "notes": task.notes}


def admissible(certificate):
    return bool(certificate and certificate.get("admissible"))
