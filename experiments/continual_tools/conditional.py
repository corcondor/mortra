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
    """Observable structural literals available before macro transfer.

    The first primitive edge must already be known by the caller.  We use its
    response plus relations to any other already-known primitive successors.
    Missing edges are not encoded as false facts; they remain unknown.
    """
    q = int(q)
    first_action = int(first_action)
    first = _modal_target(memory, q, first_action)
    if first is None:
        return None

    obs = memory.state_observation
    result = {
        ("first_self",): first == q,
        ("first_same_observation",): obs[first] == obs[q],
    }
    for action in range(memory.num_actions):
        target = _modal_target(memory, q, action)
        if target is None:
            continue
        result[("action_self", action)] = target == q
        result[("action_same_observation", action)] = obs[target] == obs[q]
        result[("action_matches_first_observation", action)] = obs[target] == obs[first]
    return result


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

            # Always anchor transfer in the observed first-edge response.  These
            # two facts are available before transfer because the first edge is
            # required to be known.
            anchor_keys = {
                ("first_self",),
                ("first_same_observation",),
            }
            selected = {k: v for k, v in common.items() if k in anchor_keys}

            negatives = [
                c for other, rows in by_effect.items() if other != effect
                for _, c, _ in rows
            ]

            # Greedily add common structural literals only when they eliminate
            # observed countereffects.  This learns a precondition rather than
            # copying a full scene fingerprint.
            surviving = list(negatives)
            pool = {k: v for k, v in common.items() if k not in selected}
            while surviving:
                best = None
                for key, value in pool.items():
                    eliminated = sum(
                        key in neg and neg[key] != value for neg in surviving)
                    if eliminated:
                        score = (eliminated, str(key))
                        if best is None or score > best[0]:
                            best = (score, key, value)
                if best is None:
                    break
                _, key, value = best
                selected[key] = value
                del pool[key]
                surviving = [
                    neg for neg in surviving
                    if not (key in neg and neg[key] != value)
                ]

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
        return effect
