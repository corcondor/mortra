"""Finite observed-history model and exact belief reasoning without discounting.

This is NOT minimum-machine or all-completions model synthesis. Its states come
from recorded observation/action prefixes; only the frozen observed model is
quotiented. Missing rows have explicit open-world uncertainty. Certificates do
not assert that sampled transitions exhaust the real environment's behavior.
"""
from __future__ import annotations

from collections import Counter, defaultdict, deque
from dataclasses import dataclass


UNKNOWN = -1
UNKNOWN_OBSERVATION = object()


@dataclass(frozen=True)
class Plan:
    status: str
    actions: tuple
    guaranteed_steps: int | None
    belief_nodes: int
    ranks: dict


class ObservedWorld:
    def __init__(self, actions):
        self.actions = tuple(actions)
        if not self.actions or len(set(self.actions)) != len(self.actions):
            raise ValueError("A nonempty unique action alphabet is required")
        self.nodes = {}
        self.labels = []
        self.roots = set()
        self.counts = defaultdict(Counter)
        self.episodes = []
        self.certificate = None

    def _node(self, key, symbol):
        if key not in self.nodes:
            self.nodes[key] = len(self.labels)
            self.labels.append(symbol)
        return self.nodes[key]

    def add_episode(self, symbols, actions):
        if self.certificate is not None:
            raise RuntimeError("Model frozen; rebuild before adding further evidence")
        symbols, actions = tuple(symbols), tuple(actions)
        if len(symbols) != len(actions) + 1:
            raise ValueError("Invalid symbol episode")
        if any(a not in self.actions for a in actions):
            raise ValueError("Undeclared action")
        u = self._node((None, None, symbols[0]), symbols[0])
        self.roots.add(u)
        path = [u]
        for a, symbol in zip(actions, symbols[1:], strict=True):
            v = self._node((u, a, symbol), symbol)
            self.counts[u, a][v] += 1
            u = v
            path.append(u)
        self.episodes.append((symbols, actions, tuple(path)))

    def freeze(self):
        if not self.labels:
            raise ValueError("No experience")
        # Reuse exact rational congruence; its q-dependent solver is never called.
        from scripts.evaluate_adaptive_refinement import exact_quotient

        indices = {a: i for i, a in enumerate(self.actions)}
        counts = {(s, indices[a]): c for (s, a), c in self.counts.items()}
        self.certificate = exact_quotient(
            self.labels, [tuple(range(len(self.actions)))] * len(self.labels), counts)
        blocks = self.certificate["blocks"]
        self.emissions = {b: self.labels[members[0]]
                          for b, members in self.certificate["groups"].items()}
        self.operators = {(b, self.actions[a]): frozenset(row)
                          for (b, a), row in self.certificate["rows"].items()}
        self.initial = frozenset(blocks[s] for s in self.roots)
        return self

    def begin(self, symbol):
        if self.certificate is None:
            raise RuntimeError("freeze() first")
        compatible = frozenset(s for s in self.initial if self.emissions[s] == symbol)
        return compatible or frozenset({UNKNOWN})

    def predict(self, belief, action):
        if action not in self.actions:
            raise ValueError("Undeclared action")
        successors = set()
        for s in belief:
            if s == UNKNOWN:
                successors.add(UNKNOWN)
            else:
                successors.update(self.operators.get((s, action), {UNKNOWN}))
        return frozenset(successors)

    def update(self, belief, action, symbol):
        predicted = self.predict(belief, action)
        retained = frozenset(s for s in predicted
                             if s == UNKNOWN or self.emissions[s] == symbol)
        # A model contradiction is not silently converted into a guessed state.
        return retained

    def reconstruct(self, symbols, actions):
        """Independent path enumeration from all reset states, not recursive update."""
        if len(symbols) != len(actions) + 1:
            raise ValueError("Invalid history")
        current = set(self.begin(symbols[0]))
        for a, symbol in zip(actions, symbols[1:], strict=True):
            following = set()
            for s in current:
                if s == UNKNOWN or (s, a) not in self.operators:
                    following.add(UNKNOWN)
                    continue
                for v in self.operators[s, a]:
                    if self.emissions[v] == symbol:
                        following.add(v)
            current = following
        return frozenset(current)

    def outcomes(self, belief, action):
        predicted = self.predict(belief, action)
        observations = {self.emissions[s] for s in predicted if s != UNKNOWN}
        result = {o: self.update(belief, action, o) for o in observations}
        if UNKNOWN in predicted:
            result[UNKNOWN_OBSERVATION] = frozenset({UNKNOWN})
        return result

    def reachable_beliefs(self, initial):
        """Enumerate to set closure; there is no depth or iteration budget."""
        queue = deque([initial])
        seen = {initial}
        graph = {}
        while queue:
            belief = queue.popleft()
            for action in self.actions:
                destinations = frozenset(self.outcomes(belief, action).values())
                graph[belief, action] = destinations
                for child in destinations:
                    if child not in seen:
                        seen.add(child)
                        queue.append(child)
        return seen, graph

    def _attractor(self, initial, terminal):
        beliefs, graph = self.reachable_beliefs(initial)
        ranks = {b: 0 for b in beliefs if terminal(b)}
        while True:
            additions = {}
            for b in beliefs - ranks.keys():
                values = [1 + max(ranks[c] for c in graph[b, a])
                          for a in self.actions if graph[b, a] and all(c in ranks for c in graph[b, a])]
                if values:
                    additions[b] = min(values)
            if not additions:
                break
            ranks.update(additions)
        return beliefs, graph, ranks

    def _result(self, initial, terminal, absent, resolved, found):
        if not initial:
            return Plan("MODEL CONTRADICTION", (), None, 0, {})
        beliefs, graph, ranks = self._attractor(initial, terminal)
        if initial not in ranks:
            return Plan(absent, (), None, len(beliefs), ranks)
        distance = ranks[initial]
        choices = tuple(a for a in self.actions if distance and graph[initial, a]
                        and all(c in ranks for c in graph[initial, a])
                        and 1 + max(ranks[c] for c in graph[initial, a]) == distance)
        return Plan(resolved if distance == 0 else found, choices, distance, len(beliefs), ranks)

    def plan(self, initial, goal_states):
        """Least attractor for guaranteed reachability on the frozen model."""
        goals = frozenset(goal_states)
        if UNKNOWN in goals or not goals <= self.emissions.keys():
            raise ValueError("Goals must name known model states")
        return self._result(initial, lambda b: b and UNKNOWN not in b and b <= goals,
                            "NO GUARANTEE UNDER CURRENT MODEL/DATA", "GOAL ALREADY SATISFIED", "GUARANTEED")

    def identify(self, initial):
        """A finite forcing policy to a singleton known state, or no such policy."""
        return self._result(initial, lambda b: len(b) == 1 and UNKNOWN not in b,
                            "NOT IDENTIFIABLE UNDER CURRENT MODEL/DATA", "RESOLVED", "FINITE IDENTIFYING POLICY")
