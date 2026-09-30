"""Conditional program transfer learned from structural action-response evidence.

A learned program is not merely an action word.  Each exact-context certificate
provides evidence of the form

    {P(q)} program {R(q, program)}

where P is built only from already-observed local action responses and R is the
state-ID-invariant relation induced by the remaining program steps.

No Mario coordinate, direction, sprite, reward, or hand-labelled scene feature
appears here.  Predictive-state IDs and raw observation hashes are used only for
local equality tests, so the learned predicates survive arbitrary renaming.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass


UNRESOLVED = "UNRESOLVED"
PREDICTED = "PREDICTED"


def _modal_target(memory, q, action):
    row = memory.counts.get((int(q), int(action)))
    if not row:
        return None
    return max(row.items(), key=lambda item: (item[1], -item[0]))[0]


def local_context(memory, q, first_action):
    """Minimal state-ID-invariant context known before macro transfer.

    Transfer is only considered after the first primitive edge is observed.
    Therefore its two directly evidenced relations are available without any
    extra probe.  They are deliberately used instead of a full local graph
    fingerprint: P should express a reusable condition, not memorize a scene.
    """
    q = int(q)
    first = _modal_target(memory, q, int(first_action))
    if first is None:
        return None
    obs = memory.state_observation
    return {
        ("first_self",): first == q,
        ("first_same_observation",): obs[first] == obs[q],
    }


def transition_relation(memory, source, target):
    source, target = int(source), int(target)
    obs = memory.state_observation
    return (
        bool(target == source),
        bool(obs[target] == obs[source]),
    )


def certified_effect(memory, guard, expected_states):
    """State-ID-invariant relation sequence for an exact-context certificate."""
    source = int(guard)
    rows = []
    for target in expected_states:
        target = int(target)
        if not (0 <= source < len(memory.id_to_state) and
                0 <= target < len(memory.id_to_state)):
            return None
        rows.append(transition_relation(memory, source, target))
        source = target
    return tuple(rows)


@dataclass(frozen=True)
class Prediction:
    status: str
    effect: tuple | None
    support: int
    competing_support: int
    required_literals: tuple
    compatible_examples: int


class ConditionalProgramModel:
    """Version-space style conditional effect learner.

    Rules are hypotheses, not universal identities.  A rule is emitted only
    after the same program/effect has been observed in at least two distinct
    exact guards.  Its precondition begins with the already-known first-edge
    response and adds only literals needed to separate observed countereffects.
    """

    def __init__(self, minimum_contexts=2):
        self.minimum_contexts = int(minimum_contexts)
        self.extra_examples = defaultdict(list)
        self._rule_cache = {}

    def _tool_examples(self, tools, memory, actions):
        examples = []
        actions = tuple(int(a) for a in actions)
        for token, record in tools.records.items():
            if tuple(tools.flatten_token(token)) != actions:
                continue
            effect = certified_effect(memory, record["guard"], record["expected_states"])
            context = local_context(memory, record["guard"], actions[0])
            if effect is None or context is None:
                continue
            examples.append((int(record["guard"]), context, effect, "certificate"))
        examples.extend(self.extra_examples.get(actions, ()))
        return examples

    @staticmethod
    def _common_literals(rows):
        if not rows:
            return {}
        common = dict(rows[0])
        for row in rows[1:]:
            for key in tuple(common):
                if key not in row or row[key] != common[key]:
                    del common[key]
        return common

    @staticmethod
    def _matches(context, literals):
        # A missing literal is unresolved, not false.
        for key, value in literals.items():
            if key not in context:
                return None
            if context[key] != value:
                return False
        return True

    def rules(self, tools, memory, actions):
        actions = tuple(int(a) for a in actions)
        cache = getattr(self, "_rule_cache", None)
        if cache is None:
            self._rule_cache = {}
            cache = self._rule_cache
        cache_key = (
            actions,
            len(tools.records),
            len(self.extra_examples.get(actions, ())),
        )
        if cache_key in cache:
            return cache[cache_key]

        examples = self._tool_examples(tools, memory, actions)
        by_effect = defaultdict(list)
        for guard, context, effect, source in examples:
            by_effect[effect].append((guard, context, source))

        rules = []
        for effect, positives in by_effect.items():
            guards = {g for g, _, _ in positives}
            if len(guards) < self.minimum_contexts:
                continue

            pos_contexts = [c for _, c, _ in positives]
            common = self._common_literals(pos_contexts)
            # With the minimal context, these are exactly the observed response
            # of the already-known first primitive edge.
            selected = dict(common)

            competing = 0
            for other, rows in by_effect.items():
                if other == effect:
                    continue
                for _, context, _ in rows:
                    if self._matches(context, selected) is True:
                        competing += 1

            rules.append(dict(
                effect=effect,
                support=len(guards),
                examples=len(positives),
                competing_support=competing,
                literals=selected,
            ))
        cache[cache_key] = rules
        # Keep only recent cache generations; tools only grow monotonically in
        # this experiment, so older entries cannot be selected again.
        if len(cache) > 256:
            newest = list(cache.items())[-128:]
            self._rule_cache = dict(newest)
        return rules

    def predict(self, tools, memory, q, actions):
        actions = tuple(int(a) for a in actions)
        context = local_context(memory, q, actions[0])
        if context is None:
            return Prediction(UNRESOLVED, None, 0, 0, (), 0)

        matches = []
        examples = self._tool_examples(tools, memory, actions)
        for rule in self.rules(tools, memory, actions):
            status = self._matches(context, rule["literals"])
            if status is True and rule["competing_support"] == 0:
                matches.append(rule)

        if not matches:
            return Prediction(
                UNRESOLVED, None, 0, 0, (), len(examples))

        matches.sort(key=lambda r: (
            -r["support"], r["competing_support"],
            -len(r["literals"]), repr(r["effect"])))
        best = matches[0]
        # Multiple surviving effects means the current evidence is insufficient.
        effects = {r["effect"] for r in matches}
        if len(effects) != 1:
            return Prediction(
                UNRESOLVED, None, best["support"],
                sum(r["competing_support"] for r in matches),
                tuple(sorted(best["literals"].items(), key=repr)),
                len(examples))

        return Prediction(
            PREDICTED, best["effect"], best["support"],
            best["competing_support"],
            tuple(sorted(best["literals"].items(), key=repr)),
            len(examples))

    def observe_transfer(self, memory, source_q, actions, state_path):
        """Add an executed unseen-context example after its result is observed."""
        actions = tuple(int(a) for a in actions)
        state_path = tuple(int(q) for q in state_path)
        if len(state_path) != len(actions) + 1:
            raise ValueError("state_path must contain source plus one target per action")
        context = local_context(memory, state_path[0], actions[0])
        if context is None:
            return None
        effect = tuple(
            transition_relation(memory, state_path[i], state_path[i+1])
            for i in range(len(actions)))
        self.extra_examples[actions].append(
            (state_path[0], context, effect, "transfer"))
        self._rule_cache = {}
        return effect
