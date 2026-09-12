"""The fold action as a linear system, so the existing observable machinery runs on it.

Everything that decides anything here already existed:

    closure of an observable space   `finite_generator_problem_dna
                                      .discover_action_observable_basis`
                                     -- smallest linear space containing the
                                     supplied observations and closed under every
                                     generator, checked as a polynomial identity
                                     per generator, scope "all finite words"
    a law for every word length      `finite_affine_word_law
                                      .discover_affine_feature_law`
                                     -- base case plus every generator step,
                                     checked symbolically
    the kinematics                   `rigid_fold_problem_discovery
                                      .apply_fold_generator` / `build_square_fold_chain`

What was missing is the three joints between them, and that is all this module is:

* the fold step is **measured** into a linear map on the state, rather than read
  off a description of it. The state is the panel's doubled centre and its frame,
  `(c1,c2,c3, F11..F33)`, and one fold sends `c -> c + w_g F`, `F -> M_g F`, both
  linear in that vector, so the whole action is a 12x12 integer matrix per letter.
  `M_g` and `w_g` are recovered by running `apply_fold_generator` on probe frames
  and solving, and the result is checked against replayed words.

* candidate observables are **enumerated**, not supplied. A caller says how far to
  go (a degree, a count); which observables those are is the enumeration's
  business, and which of them close into something small is the closure prover's.

* a proved law is **used**: the value of an observable on a word can be computed
  from the law without running the kinematics, and that prediction is checked
  against actually running it.

No observable, conserved quantity or formula is written into this file.
"""
from __future__ import annotations

import itertools

import sympy as sp

from math_os_prototype.finite_affine_word_law import (
    FiniteFeatureMachine, discover_affine_feature_law)
from math_os_prototype.finite_generator_problem_dna import (
    FiniteGeneratorSystem, LinearGenerator, discover_action_observable_basis,
    discover_linear_observation_recurrence)
from math_os_prototype.rigid_fold_problem_discovery import (
    FOLD_GENERATORS, GENERATOR_BY_SYMBOL, IDENTITY_FRAME, apply_fold_generator)

SCHEMA = "mortra.fold-observable-system.v1"

#: the state one fold acts on: the doubled centre, then the frame row by row
VARIABLE_NAMES = ("c1", "c2", "c3",
                  "F11", "F12", "F13", "F21", "F22", "F23", "F31", "F32", "F33")
VARIABLES = sp.symbols(VARIABLE_NAMES)
CENTRE = VARIABLES[:3]
FRAME = VARIABLES[3:]
ALPHABET = tuple(generator.symbol for generator in FOLD_GENERATORS)
SEED = (0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1)


# ---- the fold step, measured ----------------------------------------------

def reachable_frames(depth=4):
    """Every frame the alphabet reaches from the identity within `depth` folds."""
    seen, frontier = {IDENTITY_FRAME}, [IDENTITY_FRAME]
    for _ in range(depth):
        grown = []
        for frame in frontier:
            for generator in FOLD_GENERATORS:
                nxt, _ = apply_fold_generator(frame, (0, 0, 0), generator)
                if nxt not in seen:
                    seen.add(nxt)
                    grown.append(nxt)
        frontier = grown
    return tuple(sorted(seen, key=repr))


def measured_step(symbol, probes=None):
    """`M_g` and `w_g` for one letter, solved from runs of the kinematics.

    `F' = M F` and `c' = c + w F`, so `M = F' F^-1` and `w = d F^-1` for each
    probe frame. Every probe must give the same pair; disagreement means the step
    is not of this shape and is raised rather than averaged away.
    """
    generator = GENERATOR_BY_SYMBOL[symbol]
    matrix = offset = None
    for frame in (probes or reachable_frames()):
        current = sp.Matrix([list(row) for row in frame])
        moved_frame, moved_centre = apply_fold_generator(frame, (0, 0, 0), generator)
        candidate_matrix = sp.Matrix([list(r) for r in moved_frame]) * current.inv()
        candidate_offset = sp.Matrix([list(moved_centre)]) * current.inv()
        if matrix is None:
            matrix, offset = candidate_matrix, candidate_offset
        elif candidate_matrix != matrix or candidate_offset != offset:
            raise ValueError(f"letter {symbol!r} does not act as one linear step")
    return matrix, offset


def generator_rows(symbol):
    """The 12x12 integer action of one letter on the state vector."""
    matrix, offset = measured_step(symbol)
    index = {name: position for position, name in enumerate(VARIABLE_NAMES)}
    rows = []
    for i in range(3):                       # c'_i = c_i + sum_j w_j F_ji
        row = [0] * len(VARIABLE_NAMES)
        row[index[f"c{i + 1}"]] = 1
        for j in range(3):
            row[index[f"F{j + 1}{i + 1}"]] += offset[j]
        rows.append(row)
    for i in range(3):                       # F'_ij = sum_k M_ik F_kj
        for j in range(3):
            row = [0] * len(VARIABLE_NAMES)
            for k in range(3):
                row[index[f"F{k + 1}{j + 1}"]] += matrix[i, k]
            rows.append(row)
    return rows


def fold_system():
    """The fold alphabet as a linear system the existing provers accept."""
    return FiniteGeneratorSystem(
        name="square_fold_chain",
        variable_names=VARIABLE_NAMES,
        generators=tuple(LinearGenerator.from_rows(symbol, generator_rows(symbol))
                         for symbol in ALPHABET),
        seed=tuple(sp.Integer(v) for v in SEED))


def replay(word):
    """The state after a word, from the kinematics itself."""
    frame, centre = IDENTITY_FRAME, (0, 0, 0)
    for symbol in word:
        frame, centre = apply_fold_generator(frame, centre, GENERATOR_BY_SYMBOL[symbol])
    return frame, centre


def state_vector(word):
    """The same state as a column, for evaluating an observable on it."""
    frame, centre = replay(word)
    return sp.Matrix([*centre] + [entry for row in frame for entry in row])


def verify_step(system, *, depth=4):
    """Check `encode(apply_fold_generator(x, g)) = M_g encode(x)` exactly.

    Not on sampled words. The frame of any chain state is one the alphabet
    reaches, and its centre is an arbitrary integer vector, so the applicable
    range is `reachable_frames() x Z^3`. That whole range is covered here by
    running the kinematics on every reachable frame with a **symbolic** centre
    and normalising the difference to zero. `apply_fold_generator` adds the
    displacement to the centre and never inspects it, so a symbolic centre
    stands for every integer one.

    Reported as what it is: exact over the frames reached within `depth`, and
    for every centre.
    """
    centre = sp.symbols("x1 x2 x3")
    by_name = {generator.name: sp.Matrix(generator.rows)
               for generator in system.generators}
    frames = reachable_frames(depth)
    residuals, checks = [], 0
    for frame in frames:
        encoded = sp.Matrix([*centre] + [e for row in frame for e in row])
        for generator in FOLD_GENERATORS:
            moved_frame, moved_centre = apply_fold_generator(
                frame, tuple(centre), generator)
            left = sp.Matrix([*moved_centre]
                             + [e for row in moved_frame for e in row])
            residual = sp.expand(left - by_name[generator.symbol] * encoded)
            checks += 1
            if any(entry != 0 for entry in residual):
                residuals.append({"frame": repr(frame),
                                  "letter": generator.symbol,
                                  "residual": [str(e) for e in residual]})
    closed = all(apply_fold_generator(frame, (0, 0, 0), g)[0] in frames
                 for frame in frames for g in FOLD_GENERATORS)
    return {"exact": not residuals,
            "frames_closed": closed,
            "verified_frames": [[list(row) for row in frame] for frame in frames],
            "frames_checked": len(frames),
            "letters": len(FOLD_GENERATORS),
            "identities_checked": checks,
            "centre": "symbolic; every integer centre is covered",
            "scope": ("exact for every frame the alphabet reaches within "
                      f"{depth} folds and every centre"),
            "failures": residuals}


def agrees_with_kinematics(system, words):
    """Does the measured linear action reproduce what running the folds gives?"""
    by_name = {generator.name: sp.Matrix(generator.rows)
               for generator in system.generators}
    for word in words:
        vector = sp.Matrix(list(system.seed))
        for symbol in word:
            vector = by_name[symbol] * vector
        if tuple(vector) != tuple(state_vector(word)):
            return False, word
    return True, None


# ---- candidate observables, enumerated ------------------------------------

def candidate_observables(*, degree=2, max_terms=1, coefficients=(1,),
                          limit=None, include_constant=False):
    """Candidate observables, from a stated grammar.

    The grammar, in full:

        variables    the 12 state coordinates c1..c3, F11..F33 and nothing else
        monomials    every product of at most `degree` variables, repeats
                     allowed (combinations_with_replacement), so c1**2 and
                     F11*c1 are both reachable
        terms        a candidate is a sum of at most `max_terms` DISTINCT
                     monomials. With the default max_terms=1 only monomials are
                     offered, and that limitation is what the default means.
        coefficients each later term carries one coefficient drawn from
                     `coefficients`; the leading term always takes 1, so a
                     candidate and its scalar multiples are not both offered
        order        monomials by ascending degree, then by the variable order
                     above; sums by ascending term count, then by that order

    Nothing beyond this is applied. No quantity is named, preferred or
    excluded, and `limit` truncates this fixed order rather than selecting
    within it.
    """
    if degree < 1:
        raise ValueError("a candidate degree of at least one is needed")
    if max_terms < 1:
        raise ValueError("a candidate needs at least one term")
    monomials = []
    for order in range(1, degree + 1):
        for combination in itertools.combinations_with_replacement(VARIABLES, order):
            monomials.append(sp.prod(combination))

    offered = [sp.Integer(1)] if include_constant else []
    for count in range(1, max_terms + 1):
        for chosen in itertools.combinations(monomials, count):
            if count == 1:
                offered.append(chosen[0])
                if limit is not None and len(offered) >= limit:
                    return offered
                continue
            for weights in itertools.product(coefficients, repeat=count - 1):
                offered.append(sp.expand(
                    chosen[0] + sum(sp.Integer(w) * m
                                    for w, m in zip(weights, chosen[1:]))))
                if limit is not None and len(offered) >= limit:
                    return offered
    return offered


# ---- what the closure prover says about one candidate ---------------------

def acquire_closure(system, observable, *, maximum_dimension=64):
    """Hand one candidate to the existing closure prover and keep its verdict."""
    try:
        found = discover_action_observable_basis(
            system, [observable], maximum_dimension=maximum_dimension)
    except (ValueError, AssertionError) as exc:
        return {"observable": str(observable), "closed": False,
                "reason": str(exc)[:120], "dimension": None}
    return {"observable": str(observable),
            "closed": bool(found["certificate_passed"]),
            "dimension": len(found["basis"]),
            "basis": [str(b) for b in found["basis"]],
            "action_matrices": {name: [[str(v) for v in matrix.row(r)]
                                       for r in range(matrix.rows)]
                                for name, matrix in zip(found["generator_names"],
                                                        found["action_matrices"])},
            "identity_residuals_all_zero": all(
                all(v == 0 for v in residual)
                for residual in found["identity_residuals"]),
            "scope": found["scope"],
            "_basis": found["basis"],
            "_matrices": dict(zip(found["generator_names"], found["action_matrices"]))}


# ---- a law for every word length, from the existing word-law prover -------

def block_matrix(closure, word):
    """The closed space's action for a whole word, as one matrix."""
    matrix = sp.eye(len(closure["_basis"]))
    for symbol in word:
        matrix = closure["_matrices"][symbol] * matrix
    return matrix


def block_order(matrix, *, cap=64):
    """How many repeats bring the action back to the identity, if any."""
    power, identity = sp.eye(matrix.rows), sp.eye(matrix.rows)
    for order in range(1, cap + 1):
        power = matrix * power
        if power == identity:
            return order
    return None


def _cycle_machine(states, symbol="b"):
    """One letter, `states` feature states in a cycle: the repeat count mod m."""
    names = [f"q{index}" for index in range(states)]
    return FiniteFeatureMachine(
        name=f"repeats_mod_{states}", symbols=(symbol,), initial_state=names[0],
        transitions=tuple((names[i], symbol, names[(i + 1) % states])
                          for i in range(states)),
        public_complexity=states)


def prove_repeat_law(closure, word, *, states=None, cap=64):
    """Is the closed observable affine in the number of repeats of one block?

    The prover is the existing word law. It enumerates every word of its alphabet
    up to `3 * states + 2`, so it is usable only over a small machine: the full
    fold alphabet with the 24 reachable orientations would ask it for 4**74 words.
    Repeating one block is a one-letter alphabet, and the feature states are the
    repeat count modulo the order of that block's action -- which is measured
    here, not chosen.
    """
    if not closure.get("closed"):
        return {"proved": False, "reason": "the observable space did not close"}
    matrix = block_matrix(closure, word)
    order = block_order(matrix, cap=cap)
    machine = _cycle_machine(states or order or 1)
    basis = closure["_basis"]
    initial = sp.Matrix([sp.expand(expression).subs(
        dict(zip(VARIABLES, [sp.Integer(v) for v in SEED]))) for expression in basis])
    names = tuple(f"b{index}" for index in range(len(basis)))
    try:
        found = discover_affine_feature_law(
            {"b": matrix}, initial, machine, component_names=names)
    except (ValueError, TypeError) as exc:
        return {"proved": False, "block": word, "block_order": order,
                "reason": f"{type(exc).__name__}: {str(exc)[:100]}"}
    if not found.get("passed"):
        return {"proved": False, "block": word, "block_order": order,
                "reason": (found.get("counterexample") or {}).get(
                    "kind", "the word law refused it"),
                "counterexample": found.get("counterexample")}
    return {"proved": True, "block": word, "block_order": order,
            "scope": found["scope"], "feature_states": len(found["feature_state_formulas"]),
            "base_case_exact": found["initial_identity_exact"],
            "generator_steps": found["generator_transition_identity_count"],
            "all_steps_exact": found["all_generator_transition_identities_exact"],
            "fit_used_as_proof": found["finite_sample_fit_used_as_proof"],
            "formulas": {state: {"slope": formula["slope"][names[0]],
                                 "intercept": formula["intercept"][names[0]]}
                         for state, formula in found["feature_state_formulas"].items()}}


# ---- loading an acquisition back, and the three ways of using it ----------

def closure_from_record(record):
    """Rebuild a usable acquisition from what was stored.

    The basis expressions and the action matrices are parsed back out of the
    record, so a later computation reads the stored representation instead of
    recomputing it.
    """
    basis = [sp.sympify(entry) for entry in record["basis"]]
    matrices = {name: sp.Matrix([[sp.sympify(v) for v in row] for row in rows])
                for name, rows in record["action_matrices"].items()}
    # the record exists only for a closure the prover passed, so reading it back
    # carries that verdict with it rather than losing it to a missing key
    return dict(record, closed=True, _basis=basis, _matrices=matrices)


def initial_vector(closure):
    """The basis evaluated at the starting state."""
    return sp.Matrix([sp.expand(expression).subs(
        dict(zip(VARIABLES, [sp.Integer(v) for v in SEED])))
        for expression in closure["_basis"]])


def apply_word(closure, word):
    """One named word: the letters matrices multiplied in word order."""
    vector = initial_vector(closure)
    for symbol in word:
        vector = closure["_matrices"][symbol] * vector
    return sp.expand(vector[0])


def apply_block_power(closure, block, repeats):
    """One block repeated: the block matrix raised to that power."""
    matrix = sp.eye(len(closure["_basis"]))
    for symbol in block:
        matrix = closure["_matrices"][symbol] * matrix
    return sp.expand((matrix ** repeats * initial_vector(closure))[0])


def sum_over_all_words(closure, length):
    """The total over EVERY word of this length: the sum of the letter
    matrices, raised to that power.

    This is the sum over all len(ALPHABET) ** length words, collision-free or
    not. It is not a sum over the collision-free ones, and the two are not
    interchangeable.
    """
    size = len(closure["_basis"])
    total = sp.zeros(size, size)
    for symbol in ALPHABET:
        total = total + closure["_matrices"][symbol]
    return sp.expand((total ** length * initial_vector(closure))[0])


def brute_force_sum(closure, length):
    """The same total, by enumerating the words. For checking the matrix route."""
    return sp.expand(sum(observed(closure, "".join(word))
                         for word in itertools.product(ALPHABET, repeat=length)))


def prove_repeat_recurrence(closure, block):
    """The exact scalar recurrence of the observable along repeats of one block.

    This is the other existing prover, used where its premises fit and not
    otherwise. `discover_linear_observation_recurrence` wants one exact square
    transition, a column seed and a row functional; a block gives exactly that --
    the block matrix, the basis at the starting state, and the row that reads the
    observable off the basis. It certifies the relation on `d` consecutive
    residuals, after which the characteristic recurrence of the transition
    carries it.

    It is not a length-one law and does not need one: a block whose observable
    grows is refused by `prove_repeat_law` and can still have a recurrence here.
    A failure of either leaves the closure untouched.
    """
    if not closure.get("closed"):
        return {"proved": False, "reason": "the observable space did not close"}
    size = len(closure["_basis"])
    matrix = block_matrix(closure, block)
    functional = sp.zeros(1, size)
    functional[0, 0] = 1
    try:
        found = discover_linear_observation_recurrence(
            matrix, initial_vector(closure), functional)
    except (ValueError, AssertionError) as exc:
        return {"proved": False, "block": block,
                "reason": f"{type(exc).__name__}: {str(exc)[:110]}"}
    return {"proved": True, "block": block,
            "order": found.order,
            "coefficients": [str(c) for c in found.coefficients],
            "characteristic_polynomial": str(found.characteristic_polynomial),
            "characteristic_factorization": str(found.characteristic_factorization),
            "initial_values": [str(v) for v in found.initial_values],
            "residuals_all_zero": all(r == 0 for r in found.verification_residuals),
            "scope": ("exact scalar recurrence of the observable along repeats "
                      "of this block, certified on consecutive residuals and "
                      "carried by the characteristic recurrence of the block "
                      "matrix")}


def recurrence_values(recurrence, closure, block, count):
    """Unroll a proved recurrence to the n-th repeat, using only its own data."""
    order = recurrence["order"]
    values = [sp.sympify(v) for v in recurrence["initial_values"]]
    weights = [sp.sympify(c) for c in recurrence["coefficients"]]
    # the coefficients come back oldest term first, so v[n] = sum_j w[j] v[n-k+j].
    # Determined from the prover's own output rather than assumed.
    while len(values) <= count:
        position = len(values)
        values.append(sp.expand(sum(
            weight * values[position - order + offset]
            for offset, weight in enumerate(weights))))
    return values[count]


# ---- using what was acquired ----------------------------------------------

def predict(closure, word):
    """The observable on a word, from the acquired action matrices alone.

    No fold is executed here. This is the acquired representation being used: the
    basis is carried forward by matrix multiplication and the observable is read
    off its first coordinate.
    """
    vector = sp.Matrix([sp.expand(expression).subs(
        dict(zip(VARIABLES, [sp.Integer(v) for v in SEED])))
        for expression in closure["_basis"]])
    for symbol in word:
        vector = closure["_matrices"][symbol] * vector
    return sp.expand(vector[0])


def observed(closure, word):
    """The same observable, by running the folds and evaluating the expression."""
    return sp.expand(sp.sympify(closure["observable"]).subs(
        dict(zip(VARIABLES, list(state_vector(word))))))


def check_prediction(closure, words):
    """Predicted against executed, word by word."""
    rows = []
    for word in words:
        predicted, actual = predict(closure, word), observed(closure, word)
        rows.append({"word": word, "predicted": str(predicted),
                     "observed": str(actual), "agree": predicted == actual})
    return rows
