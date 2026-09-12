"""Exact affine-register laws for arbitrary finite-generator words.

The module is domain independent.  A caller supplies exact affine generator
matrices and finite feature machines.  Candidate affine laws are proposed from
bounded words, then certified for every finite word by checking the generator
action identities.  Failed feature summaries retain a shortest collision or
non-affine witness.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from itertools import product
from typing import Mapping, Sequence

import sympy as sp


@dataclass(frozen=True)
class FiniteFeatureMachine:
    name: str
    symbols: tuple[str, ...]
    initial_state: str
    transitions: tuple[tuple[str, str, str], ...]
    public_complexity: int

    def __post_init__(self) -> None:
        if not self.symbols or len(set(self.symbols)) != len(self.symbols):
            raise ValueError("feature-machine symbols must be nonempty and distinct")
        table = {(source, symbol): target for source, symbol, target in self.transitions}
        if len(table) != len(self.transitions):
            raise ValueError("feature-machine transitions must be deterministic")
        reached = set(self.reachable_states())
        missing = [
            (state, symbol)
            for state in reached
            for symbol in self.symbols
            if (state, symbol) not in table
        ]
        if missing:
            raise ValueError(f"feature-machine transition table is incomplete: {missing[:3]}")

    @property
    def transition_table(self) -> dict[tuple[str, str], str]:
        return {
            (source, symbol): target
            for source, symbol, target in self.transitions
        }

    def step(self, state: str, symbol: str) -> str:
        return self.transition_table[(state, symbol)]

    def run(self, word: Sequence[str]) -> str:
        state = self.initial_state
        for symbol in word:
            state = self.step(state, str(symbol))
        return state

    def reachable_states(self) -> tuple[str, ...]:
        table = self.transition_table
        reached = {self.initial_state}
        queue = [self.initial_state]
        while queue:
            state = queue.pop(0)
            for symbol in self.symbols:
                target = table.get((state, symbol))
                if target is not None and target not in reached:
                    reached.add(target)
                    queue.append(target)
        return tuple(sorted(reached))

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _all_words(symbols: Sequence[str], maximum_length: int):
    for length in range(maximum_length + 1):
        for word in product(symbols, repeat=length):
            yield tuple(str(symbol) for symbol in word)


def _serialize_vector(vector: sp.MatrixBase) -> list[str]:
    return [str(sp.cancel(value)) for value in vector]


def _vector_equal(left: sp.MatrixBase, right: sp.MatrixBase) -> bool:
    return left.shape == right.shape and all(
        sp.cancel(left[index] - right[index]) == 0
        for index in range(left.rows * left.cols)
    )


def _reachable_state_graph(
    machine: FiniteFeatureMachine,
) -> tuple[tuple[str, ...], dict[str, tuple[str, ...]]]:
    states = machine.reachable_states()
    adjacency = {
        state: tuple(
            sorted({machine.step(state, symbol) for symbol in machine.symbols})
        )
        for state in states
    }
    return states, adjacency


def _transitive_closure(
    states: Sequence[str],
    adjacency: Mapping[str, Sequence[str]],
) -> dict[str, frozenset[str]]:
    closure: dict[str, frozenset[str]] = {}
    for start in states:
        reached: set[str] = set()
        queue = list(adjacency[start])
        while queue:
            state = queue.pop(0)
            if state in reached:
                continue
            reached.add(state)
            queue.extend(adjacency[state])
        closure[start] = frozenset(reached)
    return closure


def _unbounded_states(machine: FiniteFeatureMachine) -> frozenset[str]:
    states, adjacency = _reachable_state_graph(machine)
    closure = _transitive_closure(states, adjacency)
    cyclic = {
        state
        for state in states
        if state in closure[state]
    }
    unbounded = {
        target
        for cycle_state in cyclic
        for target in ({cycle_state} | set(closure[cycle_state]))
    }
    return frozenset(unbounded)


def _reachable_lengths(
    machine: FiniteFeatureMachine,
    maximum_length: int,
) -> dict[str, tuple[int, ...]]:
    current = {machine.initial_state}
    lengths: dict[str, set[int]] = {state: set() for state in machine.reachable_states()}
    lengths[machine.initial_state].add(0)
    for length in range(1, maximum_length + 1):
        current = {
            machine.step(state, symbol)
            for state in current
            for symbol in machine.symbols
        }
        for state in current:
            lengths[state].add(length)
    return {
        state: tuple(sorted(values))
        for state, values in lengths.items()
        if values
    }


def _fit_affine_vector(
    samples: Mapping[int, sp.MatrixBase],
    *,
    state: str,
    unbounded: bool,
) -> tuple[sp.ImmutableMatrix, sp.ImmutableMatrix] | dict[str, object]:
    lengths = tuple(sorted(samples))
    if not lengths:
        return {"kind": "unreachable_feature_state", "feature_state": state}
    if len(lengths) == 1:
        if unbounded:
            return {
                "kind": "insufficient_unbounded_samples",
                "feature_state": state,
                "sample_length": lengths[0],
            }
        value = sp.ImmutableMatrix(samples[lengths[0]])
        return sp.zeros(value.rows, 1), value
    first, second = lengths[:2]
    slope = sp.ImmutableMatrix(
        (samples[second] - samples[first]) / sp.Rational(second - first)
    )
    intercept = sp.ImmutableMatrix(samples[first] - slope * first)
    for length in lengths:
        predicted = slope * length + intercept
        if not _vector_equal(predicted, samples[length]):
            return {
                "kind": "non_affine_length_dependence",
                "feature_state": state,
                "length": length,
                "observed": _serialize_vector(samples[length]),
                "predicted": _serialize_vector(predicted),
            }
    return slope, intercept


def discover_affine_feature_law(
    generator_matrices: Mapping[str, sp.MatrixBase],
    initial: sp.MatrixBase,
    machine: FiniteFeatureMachine,
    *,
    component_names: Sequence[str],
    proposal_depth: int | None = None,
) -> dict[str, object]:
    """Discover and prove a feature-indexed affine law for every word length."""

    symbols = tuple(sorted(generator_matrices))
    if symbols != tuple(sorted(machine.symbols)):
        raise ValueError("generator and feature-machine alphabets differ")
    dimension = initial.rows
    if initial.cols != 1 or len(component_names) != dimension:
        raise ValueError("initial state and component names differ")
    matrices = {
        symbol: sp.ImmutableMatrix(generator_matrices[symbol])
        for symbol in symbols
    }
    if any(matrix.shape != (dimension, dimension) for matrix in matrices.values()):
        raise ValueError("every generator must be a square matrix matching the state")
    state_count = len(machine.reachable_states())
    depth = proposal_depth or max(8, 3 * state_count + 2)

    concrete_by_key: dict[tuple[str, int], tuple[tuple[str, ...], sp.ImmutableMatrix]] = {}
    collision = None
    for word in _all_words(symbols, depth):
        concrete = sp.ImmutableMatrix(initial)
        for symbol in word:
            concrete = sp.ImmutableMatrix(matrices[symbol] * concrete)
        feature_state = machine.run(word)
        key = feature_state, len(word)
        previous = concrete_by_key.get(key)
        if previous is not None and not _vector_equal(previous[1], concrete):
            collision = {
                "kind": "same_feature_and_length_have_different_states",
                "feature_state": feature_state,
                "length": len(word),
                "first_word": "".join(previous[0]),
                "second_word": "".join(word),
                "first_state": _serialize_vector(previous[1]),
                "second_state": _serialize_vector(concrete),
            }
            break
        concrete_by_key[key] = (word, concrete)
    if collision is not None:
        return {
            "schema": "mortra.finite-affine-word-law.v1",
            "passed": False,
            "feature_machine": machine.to_dict(),
            "proposal_depth": depth,
            "counterexample": collision,
            "finite_sample_fit_used_as_proof": False,
        }

    unbounded = _unbounded_states(machine)
    formulas: dict[str, tuple[sp.ImmutableMatrix, sp.ImmutableMatrix]] = {}
    failures = []
    for feature_state in machine.reachable_states():
        samples = {
            length: concrete
            for (state, length), (_word, concrete) in concrete_by_key.items()
            if state == feature_state
        }
        fitted = _fit_affine_vector(
            samples,
            state=feature_state,
            unbounded=feature_state in unbounded,
        )
        if isinstance(fitted, dict):
            failures.append(fitted)
        else:
            formulas[feature_state] = fitted
    if failures:
        return {
            "schema": "mortra.finite-affine-word-law.v1",
            "passed": False,
            "feature_machine": machine.to_dict(),
            "proposal_depth": depth,
            "counterexample": failures[0],
            "finite_sample_fit_used_as_proof": False,
        }

    reachable_lengths = _reachable_lengths(machine, max(depth, state_count * 3 + 3))
    transition_failures = []
    transition_checks = 0
    for source in machine.reachable_states():
        source_slope, source_intercept = formulas[source]
        for symbol in symbols:
            target = machine.step(source, symbol)
            target_slope, target_intercept = formulas[target]
            matrix = matrices[symbol]
            if source in unbounded:
                slope_residual = sp.ImmutableMatrix(matrix * source_slope - target_slope)
                intercept_residual = sp.ImmutableMatrix(
                    matrix * source_intercept - target_slope - target_intercept
                )
                transition_checks += 2 * dimension
                if any(value != 0 for value in slope_residual) or any(
                    value != 0 for value in intercept_residual
                ):
                    transition_failures.append({
                        "source": source,
                        "symbol": symbol,
                        "target": target,
                        "scope": "all_reachable_lengths",
                        "slope_residual": _serialize_vector(slope_residual),
                        "intercept_residual": _serialize_vector(intercept_residual),
                    })
            else:
                for length in reachable_lengths[source]:
                    source_value = source_slope * length + source_intercept
                    target_value = target_slope * (length + 1) + target_intercept
                    residual = sp.ImmutableMatrix(matrix * source_value - target_value)
                    transition_checks += dimension
                    if any(value != 0 for value in residual):
                        transition_failures.append({
                            "source": source,
                            "symbol": symbol,
                            "target": target,
                            "scope": f"length_{length}",
                            "residual": _serialize_vector(residual),
                        })
    initial_slope, initial_intercept = formulas[machine.initial_state]
    initial_residual = sp.ImmutableMatrix(initial_intercept - initial)
    initial_exact = all(value == 0 for value in initial_residual)
    passed = initial_exact and not transition_failures
    serialized_formulas = {
        state: {
            "slope": dict(zip(component_names, _serialize_vector(slope), strict=True)),
            "intercept": dict(zip(component_names, _serialize_vector(intercept), strict=True)),
            "unbounded_length_class": state in unbounded,
            "sampled_lengths": list(reachable_lengths[state]),
        }
        for state, (slope, intercept) in formulas.items()
    }
    return {
        "schema": "mortra.finite-affine-word-law.v1",
        "passed": passed,
        "scope": "all_finite_words" if passed else "rejected",
        "feature_machine": machine.to_dict(),
        "state_dimension": dimension,
        "component_names": list(component_names),
        "proposal_depth": depth,
        "feature_state_formulas": serialized_formulas,
        "unbounded_feature_states": sorted(unbounded),
        "initial_identity_exact": initial_exact,
        "generator_transition_identity_count": transition_checks,
        "all_generator_transition_identities_exact": not transition_failures,
        "transition_counterexamples": transition_failures[:8],
        "proof": (
            "Affine formulas were proposed from bounded words, then every "
            "generator transition was checked symbolically.  Initial identity "
            "and induction certify every finite word."
        ),
        "finite_sample_fit_used_as_proof": False,
        "minimal_feature_machine_claimed": False,
        "problem_difficulty_claimed": False,
    }


def binary_feature_machines(symbols: Sequence[str]) -> tuple[FiniteFeatureMachine, ...]:
    """Return target-free finite summaries for a two-generator word."""

    alphabet = tuple(str(symbol) for symbol in symbols)
    if len(alphabet) != 2 or len(set(alphabet)) != 2:
        raise ValueError("binary feature grammar requires two distinct symbols")
    left, right = alphabet

    seen_states = ("none", left, right, left + right)
    seen_transitions = []
    for state in seen_states:
        seen = set() if state == "none" else set(state)
        for symbol in alphabet:
            target_set = seen | {symbol}
            target = (
                next(iter(target_set))
                if len(target_set) == 1
                else left + right
            )
            seen_transitions.append((state, symbol, target))

    last_states = ("none", left, right)
    last_transitions = [
        (state, symbol, symbol)
        for state in last_states
        for symbol in alphabet
    ]
    first_transitions = []
    for state in last_states:
        for symbol in alphabet:
            first_transitions.append((
                state,
                symbol,
                symbol if state == "none" else state,
            ))

    first_last_states = ("none",) + tuple(
        f"{first}:{last}"
        for first in alphabet
        for last in alphabet
    )
    first_last_transitions = []
    for state in first_last_states:
        for symbol in alphabet:
            if state == "none":
                target = f"{symbol}:{symbol}"
            else:
                first, _last = state.split(":")
                target = f"{first}:{symbol}"
            first_last_transitions.append((state, symbol, target))

    seen_last_states = ("none",) + tuple(
        f"{seen}|{last}"
        for seen in (left, right, left + right)
        for last in alphabet
        if last in seen
    )
    seen_last_transitions = []
    for state in seen_last_states:
        for symbol in alphabet:
            if state == "none":
                target = f"{symbol}|{symbol}"
            else:
                seen, _last = state.split("|")
                target_seen = "".join(item for item in alphabet if item in set(seen) | {symbol})
                target = f"{target_seen}|{symbol}"
            seen_last_transitions.append((state, symbol, target))

    return (
        FiniteFeatureMachine(
            "last_generator",
            alphabet,
            "none",
            tuple(last_transitions),
            1,
        ),
        FiniteFeatureMachine(
            "first_generator",
            alphabet,
            "none",
            tuple(first_transitions),
            1,
        ),
        FiniteFeatureMachine(
            "first_and_last_generators",
            alphabet,
            "none",
            tuple(first_last_transitions),
            2,
        ),
        FiniteFeatureMachine(
            "seen_generator_subset",
            alphabet,
            "none",
            tuple(seen_transitions),
            2,
        ),
        FiniteFeatureMachine(
            "seen_subset_and_last_generator",
            alphabet,
            "none",
            tuple(seen_last_transitions),
            3,
        ),
    )


__all__ = [
    "FiniteFeatureMachine",
    "binary_feature_machines",
    "discover_affine_feature_law",
]
