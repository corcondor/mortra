"""Tasks stated on the fold kinematics, independently of any representation.

A task says what it needs: the transition it runs on, the quantity it reads, the
goal it is trying to reach, and which words it is allowed to use. It does not
say which representation to use, and it does not mention an observable basis.
Whether some acquired representation happens to preserve what the task needs is
the certificate's business, not the task's.

Legality is deliberately allowed to depend on the WORD and not only on the state
it ends in. Self-intersection of the folded chain is exactly such a property, and
the fact that no state function can express it is the reason a representation
gets refused for the collision-constrained version of a task it is admitted for
otherwise.
"""
from __future__ import annotations

import itertools

import sympy as sp

from math_os_prototype import fold_observable_system as observables
from math_os_prototype.representation_certificate import (
    TaskSpec, compiled_observation)
from math_os_prototype.rigid_fold_problem_discovery import (
    GENERATOR_BY_SYMBOL, IDENTITY_FRAME, apply_fold_generator,
    build_square_fold_chain)

SEED_FRAME = IDENTITY_FRAME
SEED_CENTRE = (0, 0, 0)
SEED_STATE = tuple(SEED_CENTRE) + tuple(e for row in SEED_FRAME for e in row)
ALPHABET = observables.ALPHABET


def unpack(state):
    centre = tuple(state[:3])
    frame = (tuple(state[3:6]), tuple(state[6:9]), tuple(state[9:12]))
    return frame, centre


def pack(frame, centre):
    return tuple(centre) + tuple(e for row in frame for e in row)


def step(state, symbol):
    """One fold, on the flat 12-vector the observables are written in."""
    frame, centre = unpack(state)
    moved_frame, moved_centre = apply_fold_generator(
        frame, centre, GENERATOR_BY_SYMBOL[symbol])
    return pack(moved_frame, moved_centre)


def run_word(word):
    state = SEED_STATE
    for symbol in word:
        state = step(state, symbol)
    return state


# ---- evaluating an observation quickly and exactly -------------------------

#: re-exported from the certificate module, which is where the checks that
#: need it live. Same function, one definition.
_ = compiled_observation

def words_up_to(depth, alphabet=ALPHABET):
    for length in range(depth + 1):
        for word in itertools.product(alphabet, repeat=length):
            yield "".join(word)


# ---- the tasks -------------------------------------------------------------

def displacement_task(*, axis=0, name=None, collision_free=False):
    """Count the words of a length that push the panel centre furthest along one axis.

    The quantity is the centre coordinate, stated in the state variables so the
    certificate can decide membership exactly rather than sample it. Nothing
    here names a basis or a candidate observable.
    """
    expression = observables.VARIABLES[axis]
    title = name or (f"fold displacement along axis {axis + 1}"
                     + (", collision-free words only" if collision_free else ""))

    def legality(state, word):
        return not build_square_fold_chain(word).proper_intersection_pairs

    return TaskSpec(
        name=title,
        alphabet=ALPHABET,
        seed_state=SEED_STATE,
        step=step,
        observable_value=lambda state, word: state[axis],
        observable_expression=expression,
        goal=(f"the words of a given length whose value of {expression} is "
              "maximal, and how many there are"),
        goal_from_state=None,
        legal=legality if collision_free else None,
        notes=("the collision-free variant constrains the WORD, not the state "
               "it ends in, so no function of the final state can express it"
               if collision_free else
               "every word of the length is allowed"))


def answer_by_enumeration(task, length):
    """The task solved the obvious way, for checking anything else against."""
    counts = {}
    for word in itertools.product(task.alphabet, repeat=length):
        joined = "".join(word)
        state = run_word(joined)
        if task.legal is not None and not task.legal(state, joined):
            continue
        value = task.observable_value(state, joined)
        counts[value] = counts.get(value, 0) + 1
    if not counts:
        return {"target": None, "words_at_target": 0, "distinct_values": 0,
                "total_words": 0}
    target = max(counts)
    return {"target": str(target), "words_at_target": counts[target],
            "distinct_values": len(counts),
            "total_words": sum(counts.values())}
