"""Whether a representation may be used for a task, and the refusal when it may not.

The layered counting DP merges two words when their observations agree. That is
sound only under the conditions of the lemma in `quotient_counting`, and this
module is where those conditions are checked, one at a time, for one task:

    transition   Phi(T_g(x)) = B_g Phi(x) for every label. Taken from the
                 closure prover as a polynomial identity, so it holds at every
                 state and for every finite word.
    observable   the quantity the task evaluates must be a function of Phi.
                 Where the task states it as an expression in the state
                 variables this is DECIDED, by asking whether it lies in the
                 linear span of the basis. A positive answer also yields the
                 read-out `qbar(z) = sum_i coefficient_i z_i`, which is what the
                 reduced DP then uses -- not the first basis coordinate, which
                 is only the right answer by accident when the candidate happens
                 to be the quantity itself.
    legality     legal(x, g) must be a function of (Phi(x), g). Checked per
                 label, not per word.
    goal         where a task has one, it must be a function of Phi too.
    start        the start state must map to the observation the reduced DP
                 begins at.

THE DOMAIN OF THE CONTRACT

The DP merges states only WITHIN one layer: two words of different lengths are
never identified. So a pair of words of different lengths is not a
counterexample to anything the DP does, and comparing across lengths would
refuse representations that are in fact sound for the use they are being put to.
Every congruence search here therefore compares words of EQUAL length only, and
records that as the domain it searched.

TWO VERDICTS, NOT SYMMETRIC

    refused      a counterexample inside the domain: two words of the same
                 length with the same observation and different values. A proof
                 of failure for this task.
    admitted     either a symbolic decision, which holds at every state, or no
                 counterexample within the searched depth. The second is scoped,
                 not a proof, and the record carries the depth and the number of
                 words compared. Setting a flag is not a proof and no flag here
                 stands in for one.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import sympy as sp

from math_os_prototype import fold_observable_system as observables

SCHEMA = "mortra.representation-certificate.v2"


@dataclass(frozen=True)
class TaskSpec:
    """What a task needs preserved. Supplied by the task, not the representation.

    `legal_step(state, symbol)` is a function of the STATE, which means the task
    is responsible for carrying enough state to decide it. A task whose legality
    depends on the path must say so by putting the path in its state; see
    `fold_tasks.PANEL_SEED`. That is what makes a refusal here a statement about
    the representation rather than about the task being badly posed.
    """

    name: str
    alphabet: tuple
    seed_state: tuple
    step: Callable                       # (state, symbol) -> state
    legal_step: Callable                 # (state, symbol) -> bool
    value: Callable                      # state -> exact evaluation
    #: the same quantity in the state variables, when the task can write it.
    #: Present means the observable check is decided rather than sampled.
    observable_expression: object = None
    goal_from_state: Callable = None     # state -> hashable, when there is one
    goal: str = "read the evaluation"
    counted: str = "words of the given length"
    length_means: str = "that many labels"
    state_contract: str = ""
    #: the task declares that `legal_step` is true by construction. This is a
    #: fact about how the task is written, not something observed on samples,
    #: so it licenses a proof rather than a depth-bounded search.
    legal_always: bool = False
    notes: str = ""
    coefficient_field: str = "QQ"
    required_observables: tuple = ()

    def legal_word(self, word):
        """A word is legal when every step of it was."""
        state = self.seed_state
        for symbol in word:
            if not self.legal_step(state, symbol):
                return False
            state = self.step(state, symbol)
        return True


# ---- what the checks run over ----------------------------------------------

def layers(task, depth, *, legal_only=True):
    """Words grouped by length, with the state each reaches.

    Grouped by length because that is the only grouping the DP ever merges
    inside. `legal_only` drops words the task would never have walked, so the
    check is run on the states the DP actually reaches.
    """
    found = {0: [("", tuple(task.seed_state))]}
    frontier = found[0]
    for level in range(1, depth + 1):
        following = []
        for word, state in frontier:
            for symbol in task.alphabet:
                if legal_only and not task.legal_step(state, symbol):
                    continue
                following.append((word + symbol, tuple(task.step(state, symbol))))
        found[level] = following
        frontier = following
    return found


def compiled_observation(closure):
    """`Phi` as exact rational arithmetic, compiled once from its polynomial form.

    Integral coefficients use an integer fast path. Compiled because a
    certificate compares thousands of words, and a sympy substitution per basis
    element per word would cost more than the task it is certifying. Only the
    first twelve entries of a state are read, so a task that carries extra
    history behind them is observed unchanged.
    """
    programs = []
    for expression in closure["_basis"]:
        polynomial = sp.Poly(sp.expand(expression), *observables.VARIABLES)
        programs.append([(tuple(int(e) for e in monomial),
                          int(coefficient) if coefficient.is_Integer else sp.Rational(coefficient))
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
    if premise is not None:
        exact = exact and bool(premise.get("exact") and premise.get("frames_closed"))
    return {"name": "transition", "holds": exact,
            "kind": "proof" if exact else "refusal",
            "statement": "Phi(T_g(x)) = B_g Phi(x) for every label g",
            "from": ("finite_generator_problem_dna."
                     "discover_action_observable_basis, checked as a polynomial "
                     "identity, which is a different claim from the one-step "
                     "correspondence between the kinematics and the matrices"),
            "scope": (closure_record.get("closure_scope")
                      or closure_record.get("scope")
                      or "all finite words; linear closure of the observations"),
            "premise": premise}


def _coordinate_columns(polynomials, extra):
    monomials = sorted({m for p in list(polynomials) + [extra]
                        for m in sp.Poly(p, *observables.VARIABLES).monoms()})

    def column(polynomial):
        poly = sp.Poly(polynomial, *observables.VARIABLES)
        table = dict(zip(poly.monoms(), poly.coeffs()))
        return [table.get(m, sp.S.Zero) for m in monomials]

    return monomials, column


def span_membership(closure, expression):
    """Is `expression` an exact linear combination of the basis? A decision.

    Exact linear algebra on shared monomial coordinates, so an answer here is
    about every state rather than about sampled ones. The coefficients come back
    with it, because they are the read-out the reduced DP needs.
    """
    if expression is None:
        return None
    target = sp.expand(sp.sympify(expression))
    basis = [sp.expand(b) for b in closure["_basis"]]
    _, column = _coordinate_columns(basis, target)
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


def same_span(left, right):
    """Do two closures span the same linear space? Decided by rank.

    A reordering or a rescaling of a basis is the same space and is reported as
    such, so two candidates are not counted as two representations when they are
    one.
    """
    left_basis = [sp.expand(b) for b in left["_basis"]]
    right_basis = [sp.expand(b) for b in right["_basis"]]
    if not left_basis or not right_basis:
        return {"same": not left_basis and not right_basis}
    _, column = _coordinate_columns(left_basis + right_basis, sp.S.Zero)
    left_matrix = sp.Matrix.hstack(*[sp.Matrix(column(p)) for p in left_basis])
    right_matrix = sp.Matrix.hstack(*[sp.Matrix(column(p)) for p in right_basis])
    joint = sp.Matrix.hstack(left_matrix, right_matrix)
    left_rank, right_rank, joint_rank = (left_matrix.rank(), right_matrix.rank(),
                                         joint.rank())
    return {"same": left_rank == right_rank == joint_rank,
            "left_rank": left_rank, "right_rank": right_rank,
            "joint_rank": joint_rank,
            "decided_by": "exact rank on shared monomial coordinates"}


def congruence_check(task, predicate, *, depth, label, observe, per_label=False):
    """Is `predicate` constant on the classes `Phi` induces, inside each layer?

    Two words OF THE SAME LENGTH with the same observation and different values
    is a counterexample and refuses the representation. Words of different
    lengths are never compared, because the DP never merges across layers and a
    cross-layer pair would refuse a representation for something it is not asked
    to do.
    """
    grouped = layers(task, depth)
    compared = 0
    for level, words in grouped.items():
        classes = {}
        for word, state in words:
            compared += 1
            key = observe(state)
            entries = ([(symbol, predicate(state, symbol))
                        for symbol in task.alphabet] if per_label
                       else [(None, predicate(state))])
            if key in classes:
                first_entries, first_word, first_state = classes[key]
                for (symbol, value), (_, first_value) in zip(entries,
                                                             first_entries):
                    if value != first_value:
                        return {
                            "name": label, "holds": False, "kind": "refusal",
                            "counterexample": {
                                "length": level, "label": symbol,
                                "observation": [str(v) for v in key],
                                "word_a": first_word,
                                "value_a": str(first_value),
                                "state_a": list(first_state)[:12],
                                "word_b": word, "value_b": str(value),
                                "state_b": list(state)[:12]},
                            "words_compared": compared, "depth": depth,
                            "domain": ("words of EQUAL length, which is the only "
                                       "pairing the DP ever merges"),
                            "statement": (f"{label} is constant on the classes "
                                          "Phi induces inside a layer")}
            else:
                classes[key] = (entries, word, state)
    return {"name": label, "holds": True,
            "kind": "no counterexample within depth",
            "words_compared": compared, "depth": depth,
            "layers_checked": sorted(grouped),
            "domain": "words of EQUAL length, layer by layer",
            "statement": f"{label} is constant on the classes Phi induces inside a layer",
            "scope": (f"checked on every legal word of length at most {depth}; "
                      "this is not a proof for longer words")}


# ---- the certificate --------------------------------------------------------

def certify(closure_record, task, *, depth=5, premise=None):
    """Every condition the counting lemma needs, checked one at a time."""
    closure = observables.closure_from_record(closure_record)
    observe = compiled_observation(closure)
    checks = [transition_check(closure_record, premise)]
    from math_os_prototype import fold_tasks
    binding = task.step in (fold_tasks.step, fold_tasks.panel_step) and tuple(task.alphabet) == observables.ALPHABET
    checks[0]["action_binding"] = {"supported_fold_adapter": binding,
                                    "coefficient_field": task.coefficient_field}
    if not binding or task.coefficient_field != "QQ":
        checks[0].update(holds=False, kind="refusal")
    readout = None

    membership = span_membership(closure, task.observable_expression)
    if membership and membership["member"]:
        readout = membership["coefficients"]
        checks.append({
            "name": "observable", "holds": True, "kind": "proof",
            "statement": ("the evaluated quantity is an exact linear "
                          "combination of the basis, so Phi determines it at "
                          "every state"),
            "coefficients": readout,
            "readout": ("qbar(z) = sum_i coefficient_i * z_i; this is what the "
                        "reduced DP evaluates, not the first basis coordinate"),
            "scope": "every state, not only the reachable ones"})
    elif membership is not None:
        checks.append({
            "name": "observable", "holds": False, "kind": "refusal",
            "statement": ("the evaluated quantity is not in the linear span of "
                          "the basis, so Phi does not determine it"),
            "scope": "decided exactly, by rank"})
    else:
        checks.append(congruence_check(task, lambda s: task.value(s),
                                       depth=depth, label="observable",
                                       observe=observe))

    if task.legal_always:
        checks.append({
            "name": "legality", "holds": True, "kind": "proof",
            "statement": ("the task declares every step legal by construction, "
                          "so legality is trivially a function of Phi"),
            "scope": "every state and every label",
            "from": "the task contract, not a sample"})
    else:
        checks.append(congruence_check(task, task.legal_step, depth=depth,
                                       label="legality", observe=observe,
                                       per_label=True))

    if task.goal_from_state is None:
        checks.append({
            "name": "goal", "holds": True, "kind": "structural",
            "statement": ("the goal is stated on the evaluated value, so it is "
                          "preserved exactly when the observable is"),
            "goal": task.goal, "depends_on": "observable"})
    else:
        checks.append(congruence_check(task, task.goal_from_state, depth=depth,
                                       label="goal", observe=observe))

    start = observe(task.seed_state)
    checks.append({"name": "start", "holds": True, "kind": "proof",
                   "statement": "the start state maps to the observation the DP begins at",
                   "observation": [str(v) for v in start]})
    if task.observable_expression is not None:
        try:
            value_matches = sp.expand(task.value(observables.VARIABLES)
                                      - task.observable_expression) == 0
        except (TypeError, ValueError, IndexError):
            value_matches = False
        checks[1]["evaluation_matches_declared_expression"] = value_matches
        if not value_matches:
            checks[1].update(holds=False, kind="refusal")

    refusals = [check for check in checks if not check["holds"]]
    proved = all(check["kind"] in ("proof", "structural") for check in checks)
    result = {
        "schema": SCHEMA, "task": task.name,
        "observable": closure_record.get("observable"),
        "dimension": len(closure_record["basis"]),
        "admissible": not refusals,
        "verdict": ("refused" if refusals else
                    "admitted, proved" if proved else
                    "admitted, no counterexample within depth"),
        "checks": checks,
        "readout": readout,
        "start_observation": [str(v) for v in start],
        "refused_by": [check["name"] for check in refusals],
        "may_merge_states": not refusals,
        "depth": depth,
        "domain": ("states reached by legal words of equal length. The DP merges "
                   "only inside a layer, so that is what was checked and that is "
                   "all this certificate licenses."),
        "sense": ("a refusal is a counterexample inside the domain and is final "
                  "for this task. An admission is either decided symbolically, "
                  "which holds everywhere, or bounded by the depth it was "
                  "searched to -- the checks say which."),
        "task_contract": {"state": task.state_contract, "counted": task.counted,
                          "length_means": task.length_means,
                          "goal": task.goal, "notes": task.notes}}
    from math_os_prototype.representation_reuse import task_key, coverage, representation_key
    result["reuse_key"] = task_key(task)
    result["representation_key"] = representation_key(closure_record)
    result["coverage"] = coverage(result, task, premise)
    result["required_readouts"] = []
    for expression in task.required_observables:
        membership = span_membership(closure, expression)
        result["required_readouts"].append(membership)
        if not membership or not membership["member"]:
            result["admissible"] = result["may_merge_states"] = False
            result["verdict"] = "refused"
            result["refused_by"].append("required observable")
    return result


def admissible(certificate):
    return bool(certificate and certificate.get("admissible"))


# ---- using an admitted certificate ----------------------------------------

def abstract_routes(closure, certificate, task):
    """The abstract step, legality and evaluation this certificate licenses.

    `qbar` is the certified read-out. Where the certificate admitted the
    observable by span membership that read-out is an exact linear combination
    and the reduced run never touches a concrete state at all.

    A representative concrete state is carried beside the observation ONLY when
    something still needs it: a legality that is not vacuous, or an observable
    admitted by congruence rather than by span membership, which leaves no
    linear read-out to evaluate. Carrying it unconditionally would make the
    reduced run call the original update once per class and quietly put the very
    primitive the representation is supposed to replace back into the
    measurement.
    """
    if not admissible(certificate):
        raise ValueError("this certificate does not admit the representation")
    matrices = closure["_matrices"]
    # exact rationals, NOT coerced to integers: a read-out like 3/4 z0 + 1/4 z3
    # is an ordinary outcome of solving in the basis, and rounding it to zero
    # silently turns the evaluation into a constant
    coefficients = ([sp.nsimplify(sp.sympify(c), rational=True)
                     for c in certificate["readout"]]
                    if certificate.get("readout") else None)
    needs_witness = (not task.legal_always) or coefficients is None
    reason = ("legality is not vacuous for this task"
              if not task.legal_always else
              "the observable was admitted by congruence, so there is no linear "
              "read-out to evaluate") if needs_witness else None

    if not needs_witness:
        def step(vector, symbol):
            return tuple(matrices[symbol] * sp.Matrix(list(vector)))

        def legal(vector, symbol):
            return True

        def value(vector):
            return sum(c * v for c, v in zip(coefficients, vector))

        return {"step": step, "legal": legal, "value": value,
                "key": lambda vector: vector,
                "readout_is_linear": True, "carries_witness": False,
                "start_from": lambda state, observe: tuple(observe(state)),
                "note": ("the reduced run carries the observation and nothing "
                         "else; the original update is never called")}

    def step(carried, symbol):
        vector, witness = carried
        moved = tuple(matrices[symbol] * sp.Matrix(list(vector)))
        return (moved, task.step(witness, symbol))

    def legal(carried, symbol):
        return task.legal_step(carried[1], symbol)

    def value(carried):
        vector, witness = carried
        if coefficients is None:
            return task.value(witness)
        return sum(c * v for c, v in zip(coefficients, vector))

    return {"step": step, "legal": legal, "value": value,
            "key": lambda carried: carried[0],
            "readout_is_linear": coefficients is not None,
            "carries_witness": True, "witness_reason": reason,
            "start_from": lambda state, observe: (tuple(observe(state)), state),
            "witness_note": ("one representative concrete state is carried per "
                             "class. The certificate is what makes any "
                             "representative of the class do; the merging key "
                             "stays the observation alone. The cost of this is "
                             "visible in the primitive counts and is not hidden")}
