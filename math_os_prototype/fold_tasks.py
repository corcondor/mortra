"""Tasks stated on the fold kinematics, independently of any representation.

A task fixes its own contract and nothing else: the concrete states and the
start, the labels and their update, when a step is legal, what is evaluated at
the end, what the length counts, and what is being counted. It never names an
observable basis, a candidate or an action matrix. Whether some acquired
representation happens to preserve what it needs is the certificate's business.

Two families here, and the difference between them is the point:

    every word          legality is vacuous. The concrete state is the panel's
                        doubled centre and its frame, twelve integers, because
                        nothing else is consulted.
    collision-free      legality says the folded chain does not cross itself.
                        That is NOT a function of the centre and frame, so the
                        concrete state for this task carries the placed panels
                        as well. The task is therefore stated on a
                        history-sufficient state, and a representation that
                        fails here fails against a state that really does decide
                        legality -- which is a statement about that
                        representation, not about every possible one.

Counted objects are WORDS of the given length, not end states and not shapes.
"""
from __future__ import annotations

import itertools

import sympy as sp

from math_os_prototype import fold_observable_system as observables
from math_os_prototype import quotient_counting
from math_os_prototype.representation_certificate import (
    TaskSpec, compiled_observation)
from math_os_prototype.rigid_fold_problem_discovery import (
    GENERATOR_BY_SYMBOL, IDENTITY_FRAME, _normal_axis, _panel,
    _properly_intersects, apply_fold_generator, build_square_fold_chain)

SEED_FRAME = IDENTITY_FRAME
SEED_CENTRE = (0, 0, 0)
#: the twelve coordinates the observable grammar is written in
COORDINATES = tuple(SEED_CENTRE) + tuple(e for row in SEED_FRAME for e in row)
ALPHABET = observables.ALPHABET

#: re-exported; the certificate module owns the single definition
_ = compiled_observation


def unpack(state):
    centre = tuple(state[:3])
    frame = (tuple(state[3:6]), tuple(state[6:9]), tuple(state[9:12]))
    return frame, centre


def pack(frame, centre):
    return tuple(centre) + tuple(e for row in frame for e in row)


def step(state, symbol):
    """One fold on the twelve coordinates. Any trailing history is dropped."""
    frame, centre = unpack(state)
    moved_frame, moved_centre = apply_fold_generator(
        frame, centre, GENERATOR_BY_SYMBOL[symbol])
    return pack(moved_frame, moved_centre)


def run_word(word):
    state = COORDINATES
    for symbol in word:
        state = step(state, symbol)
    return state


# ---- the history-sufficient state, for tasks whose legality needs it -------

#: what `_properly_intersects` actually consults about a panel
def panel_signature(centre, frame):
    return (tuple(centre), _normal_axis(_panel(0, None, centre, frame)))


PANEL_SEED = COORDINATES + ((panel_signature(SEED_CENTRE, SEED_FRAME),),)


def panel_step(state, symbol):
    """One fold, carrying the panels placed so far.

    The first twelve entries stay the twelve coordinates, so an observation
    written in those coordinates reads this state unchanged; the thirteenth is
    the history that legality needs.
    """
    moved = step(state[:12], symbol)
    frame, centre = unpack(moved)
    return moved + (tuple(state[12]) + (panel_signature(centre, frame),),)


def panel_legal_step(state, symbol):
    """Whether the panel this fold places crosses an earlier one.

    A pure function of this state: the placed panels are in it. The immediately
    preceding panel is skipped, matching `build_square_fold_chain`, which does
    not test a panel against the one it is hinged to.
    """
    moved = step(state[:12], symbol)
    frame, centre = unpack(moved)
    placed = state[12]
    arriving = _panel(len(placed), symbol, centre, frame)
    for index, (earlier_centre, earlier_normal) in enumerate(placed[:-1]):
        earlier = _panel(index, None, earlier_centre,
                         _frame_with_normal(earlier_normal))
        if _properly_intersects(earlier, arriving):
            return False
    return True


def _frame_with_normal(axis):
    """A frame whose normal is this axis. `_properly_intersects` reads no more.

    Only `_normal_axis(panel.frame)` and the doubled centre are consulted, so a
    frame that agrees on the normal decides intersection identically. The test
    `test_panel_legality_matches_the_chain_builder` is what holds this honest.
    """
    rows = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
    rows[2][axis] = 1
    rows[0][(axis + 1) % 3] = 1
    rows[1][(axis + 2) % 3] = 1
    return (tuple(rows[0]), tuple(rows[1]), tuple(rows[2]))


# ---- the tasks -------------------------------------------------------------

def displacement_task(*, axis=0, name=None, collision_free=False,
                      start_word=""):
    """Maximise a centre coordinate over words of a length, and count the winners.

    `start_word` moves the start without changing anything else, so a task with
    a different initial state is the same contract from a different place.
    """
    expression = observables.VARIABLES[axis]
    title = name or (f"fold axis {axis + 1} displacement"
                     + (f" from {start_word}" if start_word else "")
                     + (", collision-free words only" if collision_free else ""))

    if collision_free:
        seed = PANEL_SEED
        for symbol in start_word:
            seed = panel_step(seed, symbol)
        return TaskSpec(
            name=title, alphabet=ALPHABET, seed_state=seed,
            step=panel_step, legal_step=panel_legal_step,
            value=lambda state: state[axis],
            observable_expression=expression,
            counted="words of the given length over the label alphabet",
            length_means="that many folds",
            goal=(f"the maximum of {expression} over collision-free words of a "
                  "given length, and how many attain it"),
            state_contract=("twelve coordinates plus the placed panels. The "
                            "panels are carried because legality consults them; "
                            "a state of only the centre and frame would not "
                            "decide this task"),
            notes=("legality here is a genuine function of THIS state. A "
                   "representation refused for it is refused against a state "
                   "that does decide legality, which says something about that "
                   "representation and nothing about every representation"))

    seed = COORDINATES
    for symbol in start_word:
        seed = step(seed, symbol)
    return TaskSpec(
        name=title, alphabet=ALPHABET, seed_state=seed,
        step=step, legal_step=lambda state, symbol: True,
        value=lambda state: state[axis],
        observable_expression=expression,
        counted="words of the given length over the label alphabet",
        length_means="that many folds",
        goal=(f"the maximum of {expression} over all words of a given length, "
              "and how many attain it"),
        state_contract=("the twelve coordinates: the doubled centre and the "
                        "frame. Nothing else is consulted, because legality is "
                        "vacuous here"),
        legal_always=True,
        notes="every word of the length is legal")


def sum_of_centre_task(*, name=None, start_word=""):
    """Maximise c1 + c2 instead. Same contract, a different evaluation.

    Fixed before any run. The point is that the quantity is not a coordinate of
    any single candidate the grammar offers first, so the representation that
    serves it has to be found rather than reached for.
    """
    expression = observables.VARIABLES[0] + observables.VARIABLES[1]
    seed = COORDINATES
    for symbol in start_word:
        seed = step(seed, symbol)
    return TaskSpec(
        name=name or ("fold c1+c2 displacement"
                      + (f" from {start_word}" if start_word else "")),
        alphabet=ALPHABET, seed_state=seed,
        step=step, legal_step=lambda state, symbol: True,
        value=lambda state: state[0] + state[1],
        observable_expression=expression,
        counted="words of the given length over the label alphabet",
        length_means="that many folds",
        goal="the maximum of c1 + c2 over all words of a given length, and how "
             "many attain it",
        state_contract="the twelve coordinates",
        legal_always=True,
        notes="every word of the length is legal")


# ---- solving a task without any representation ----------------------------

def enumerate_answer(task, length):
    """Every word walked. The statement any other route has to reproduce."""
    return quotient_counting.enumerate_count(
        start=task.seed_state, step=task.step, legal=task.legal_step,
        value=task.value, alphabet=task.alphabet, length=length)


def concrete_answer(task, length):
    """The same DP, merging equal CONCRETE states inside a layer.

    A standard technique that needs nothing learned. Whatever this saves is not
    the representation saving it.
    """
    return quotient_counting.layered_count(
        start=task.seed_state, step=task.step, legal=task.legal_step,
        value=task.value, alphabet=task.alphabet, length=length)


def words_up_to(depth, alphabet=ALPHABET):
    for length in range(depth + 1):
        for word in itertools.product(alphabet, repeat=length):
            yield "".join(word)


# ---- the tasks used by the runners, fixed here rather than at call time ----

#: Named so a run can be reproduced from a command line without any of the
#: task's content being retyped. The two beyond the first are the variations
#: the brief asks for: one changes the evaluated quantity, one changes the
#: initial state. Both were written here before any of them was run.
TASKS = {
    "axis1": lambda: displacement_task(axis=0),
    "axis1-collision-free": lambda: displacement_task(axis=0,
                                                      collision_free=True),
    "c1-plus-c2": sum_of_centre_task,
    "axis1-from-AG": lambda: displacement_task(axis=0, start_word="AG"),
}


def task_by_name(name):
    if name not in TASKS:
        raise ValueError(f"unknown task {name!r}; known: {sorted(TASKS)}")
    return TASKS[name]()
