"""Connect learned sensory symbols to reusable observed action relations.

The perception tree, not the position in a training trace, defines the input
state alphabet. All observed successors are retained, including disagreements.
This is an empirical symbol model, not minimal hidden-machine synthesis and
not a proof that a symbol is sufficient for the true environment's future.
The inherited rational quotient and belief/reachability algorithms are frozen.
"""
from .world import ObservedWorld


class SymbolWorld(ObservedWorld):
    def add_episode(self, symbols, actions):
        if self.certificate is not None:
            raise RuntimeError("Model frozen; rebuild before adding further evidence")
        symbols, actions = tuple(symbols), tuple(actions)
        if not symbols or len(symbols) != len(actions) + 1:
            raise ValueError("Invalid symbol episode")
        if any(a not in self.actions for a in actions):
            raise ValueError("Undeclared action")
        path = tuple(self._node(symbol, symbol) for symbol in symbols)
        self.roots.add(path[0])
        for u, action, v in zip(path[:-1], actions, path[1:], strict=True):
            self.counts[u, action][v] += 1
        self.episodes.append((symbols, actions, path))

    def connection_audit(self):
        """Check only training evidence, never held-out labels or task scores."""
        if self.certificate is None:
            raise RuntimeError("freeze() first")
        checked = 0
        for symbols, actions, path in self.episodes:
            for u, action, v in zip(path[:-1], actions, path[1:], strict=True):
                source, target = (self.certificate["blocks"][p] for p in (u, v))
                assert target in self.operators[source, action]
                checked += 1
        assert len(self.labels) == len({s for seq, _, _ in self.episodes for s in seq})
        return {
            "state_key": "learned sensory symbol, NOT history-prefix position",
            "training_transitions_checked": checked,
            "observed_symbol_states": len(self.labels),
            "quotient_states": len(self.emissions),
            "multiple_successor_rows": sum(len(row) > 1 for row in self.operators.values()),
            "missing_rows": "UNKNOWN; no modal successor, self-loop or invented edge",
            "scope": "observed symbol transition relation; predictive sufficiency is evaluated, not assumed",
        }
