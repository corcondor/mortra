"""Compact continual tool library.

Primitive actions and learned programs share one executable word semantics.
Exact code equalities are checked by expansion.  Behavioural relations are
scoped to the currently learned predictive quotient and are never promoted to
universal identities without further evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json

SAME = "SAME"
DIFFERENT = "DIFFERENT"
UNRESOLVED = "UNRESOLVED"


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class ToolExecution:
    tool: str
    status: str
    executed: tuple[int, ...]
    evidence: tuple
    reason: str


class ProgramLibrary:
    def __init__(self, action_count):
        self.action_count = int(action_count)
        self.definitions = {}
        self.records = {}
        self.events = []
        self.relations = []

    def primitive(self, action):
        action = int(action)
        if not 0 <= action < self.action_count:
            raise ValueError("primitive action outside alphabet")
        return f"a{action}"

    def flatten_token(self, token, stack=()):
        if token.startswith("a") and token[1:].isdigit():
            action = int(token[1:])
            if not 0 <= action < self.action_count:
                raise ValueError("corrupt primitive token")
            return (action,)
        if token not in self.definitions:
            raise KeyError(token)
        if token in stack:
            raise ValueError("cyclic program definition")
        result = []
        for child in self.definitions[token]:
            result.extend(self.flatten_token(child, stack + (token,)))
        return tuple(result)

    def flatten(self, word):
        result = []
        for token in word:
            result.extend(self.flatten_token(token))
        return tuple(result)

    def compile(self, actions):
        """Shortest exact word over primitives and already learned programs."""
        raw = tuple(int(a) for a in actions)
        if any(not 0 <= a < self.action_count for a in raw):
            raise ValueError("action outside alphabet")
        inventory = [(self.primitive(a), (a,)) for a in range(self.action_count)]
        inventory += [(token, self.flatten_token(token)) for token in sorted(self.definitions)]
        best = {0: ()}
        for i in range(len(raw)):
            if i not in best:
                continue
            for token, expansion in inventory:
                if raw[i:i+len(expansion)] != expansion:
                    continue
                candidate = best[i] + (token,)
                end = i + len(expansion)
                if end not in best or (len(candidate), candidate) < (len(best[end]), best[end]):
                    best[end] = candidate
        word = best[len(raw)]
        if self.flatten(word) != raw:
            raise AssertionError("program compilation changed primitive behaviour")
        return word

    def register(self, actions, *, guard, expected_states, source, metadata=None):
        actions = tuple(int(a) for a in actions)
        word = self.compile(actions)
        token = "t" + digest([guard, actions, source])[:16]
        if token in self.definitions:
            return token
        self.definitions[token] = tuple(word)
        if self.flatten_token(token) != actions:
            raise AssertionError("stored tool does not expand to source trace")
        self.records[token] = {
            "token": token,
            "guard": guard,
            "expected_states": tuple(expected_states),
            "source": source,
            "metadata": metadata or {},
            "primitive_actions": actions,
            "word": tuple(word),
            "status": "candidate",
        }
        self.events.append({"event": "tool_registered", "tool": token, "source": source})
        return token

    def guard_status(self, tool, belief):
        """Compare a predictive-state guard with a SignatureBelief-like object."""
        expected = tool["guard"]
        resolved = getattr(belief, "resolved_state", None)
        if resolved is not None:
            return SAME if resolved == expected else DIFFERENT
        candidates = set(getattr(belief, "candidates", ()))
        new_possible = bool(getattr(belief, "new_state_possible", True))
        if expected not in candidates and not new_possible:
            return DIFFERENT
        return UNRESOLVED

    def begin(self, token, belief):
        tool = self.records[token]
        status = self.guard_status(tool, belief)
        if status != SAME:
            return ToolExecution(token, status, (), (), "guard not confirmed")
        return _RunningTool(self, tool)

    def relation(self, kind, left, right, *, status, scope, evidence):
        if status not in (SAME, DIFFERENT, UNRESOLVED):
            raise ValueError("invalid relation status")
        row = dict(kind=kind, left=tuple(left), right=tuple(right), status=status,
                   scope=scope, evidence=evidence)
        if row not in self.relations:
            self.relations.append(row)
        return row

    def discover_quotient_relations(self, graph):
        """Mine simple laws on the complete currently learned quotient.

        These are exact on the supplied finite graph only. They are not used as
        primitive-trace rewrites and later counterexamples may refute them.
        """
        states = range(len(graph.id_to_state))

        def apply(q, actions):
            for action in actions:
                key = (q, int(action))
                if key not in graph.dest_map:
                    return None
                q = graph.dest_map[key]
            return q

        found = []
        for token in sorted(self.records):
            word = self.flatten_token(token)
            once = [apply(q, word) for q in states]
            if any(v is None for v in once):
                continue
            twice = [apply(v, word) for v in once]
            if twice == once:
                found.append(self.relation(
                    "idempotent", (token, token), (token,), status=SAME,
                    scope="current_complete_predictive_quotient",
                    evidence={"states_checked": len(once)}))
            if twice == list(states):
                found.append(self.relation(
                    "involution", (token, token), (), status=SAME,
                    scope="current_complete_predictive_quotient",
                    evidence={"states_checked": len(once)}))
        return found


class _RunningTool:
    def __init__(self, library, tool):
        self.library = library
        self.tool = tool
        self.actions = library.flatten_token(tool["token"])
        self.index = 0
        self.evidence = []

    @property
    def done(self):
        return self.index >= len(self.actions)

    def next_action(self):
        return None if self.done else self.actions[self.index]

    def observe(self, belief):
        if self.done:
            raise RuntimeError("tool already complete")
        expected = self.tool["expected_states"][self.index]
        resolved = getattr(belief, "resolved_state", None)
        candidates = set(getattr(belief, "candidates", ()))
        new_possible = bool(getattr(belief, "new_state_possible", True))
        if resolved is not None:
            status = SAME if resolved == expected else DIFFERENT
        elif expected not in candidates and not new_possible:
            status = DIFFERENT
        else:
            status = UNRESOLVED
        self.evidence.append(status)
        self.index += 1
        if status == DIFFERENT:
            self.tool["status"] = "refuted"
            self.library.events.append({"event": "tool_counterexample", "tool": self.tool["token"],
                                        "step": self.index-1})
            return ToolExecution(self.tool["token"], DIFFERENT,
                                 self.actions[:self.index], tuple(self.evidence),
                                 "confirmed predictive-state counterexample")
        if status == UNRESOLVED:
            self.library.events.append({"event": "tool_unresolved", "tool": self.tool["token"],
                                        "step": self.index-1})
            return ToolExecution(self.tool["token"], UNRESOLVED,
                                 self.actions[:self.index], tuple(self.evidence),
                                 "observation unresolved; tool retained")
        if self.done:
            self.tool["status"] = "reused"
            self.library.events.append({"event": "tool_reused", "tool": self.tool["token"]})
            return ToolExecution(self.tool["token"], SAME, self.actions,
                                 tuple(self.evidence), "later execution confirmed")
        return None
