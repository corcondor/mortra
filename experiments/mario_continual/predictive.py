"""Online predictive-state memory for effectful, non-resettable play.

Only predictive representatives become graph states.  Ambiguity is carried as a
candidate set; histories are not materialized as provisional graph nodes.  A
confirmed one-step behavioural counterexample can split two visually identical
contexts into different predictive states.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class PredictiveBelief:
    observation: object
    candidates: tuple[int, ...]
    new_state_possible: bool
    source: str = "observation"

    @property
    def resolved_state(self):
        return self.candidates[0] if len(self.candidates) == 1 else None


class PredictiveRegistry:
    """StructuralLearner-compatible predictive graph plus live belief updates."""

    def __init__(self, action_count):
        self.num_actions = int(action_count)
        self.state_to_id = {}
        self.id_to_state = []
        self.node_visits = Counter()
        self.action_visits = Counter()
        self.counts = {}
        self.dest_map = {}

        self.state_observation = []
        self.representative_history = []
        self.observation_states = defaultdict(set)
        self.events = []
        self.goal_states = set()

    @staticmethod
    def state_token(q):
        return ("predictive", int(q))

    def add_state(self, observation, history, *, reason):
        q = len(self.id_to_state)
        token = self.state_token(q)
        self.state_to_id[token] = q
        self.id_to_state.append(token)
        self.state_observation.append(observation)
        self.representative_history.append(tuple(history))
        self.observation_states[observation].add(q)
        self.events.append(dict(event="predictive_state_added", state=q,
                                observation=observation, history=list(history),
                                reason=reason))
        return q

    def get_or_add_id(self, state):
        if state not in self.state_to_id:
            raise KeyError("predictive states are created by evidence, not by core")
        return self.state_to_id[state]

    def record_transition(self, u, action, v):
        u, action, v = int(u), int(action), int(v)
        key = (u, action)
        self.action_visits[key] += 1
        row = self.counts.setdefault(key, {})
        row[v] = row.get(v, 0) + 1
        self.dest_map[key] = max(row.items(), key=lambda item: (item[1], -item[0]))[0]

    def belief(self, observation, history):
        states = sorted(self.observation_states.get(observation, ()))
        if not states:
            q = self.add_state(observation, history, reason="new_observation_class")
            return PredictiveBelief(observation, (q,), False, "new_observation")
        # Same current observation need not imply same predictive state.
        return PredictiveBelief(observation, tuple(states), True, "visual_alias_possible")

    def _compatible_targets(self, q, action, observation):
        row = self.counts.get((q, action))
        if not row:
            return None
        return {v for v in row if self.state_observation[v] == observation}

    def update(self, source, action, target_observation, source_history, target_history,
               *, terminal_status=None):
        """Update after one real action and return the target predictive belief."""
        action = int(action)
        source_candidates = set(source.candidates)
        compatible_sources, unknown_sources, contradicted_sources = set(), set(), set()
        predicted_targets = set()

        for q in source_candidates:
            compatible = self._compatible_targets(q, action, target_observation)
            if compatible is None:
                unknown_sources.add(q)
            elif compatible:
                compatible_sources.add(q)
                predicted_targets.update(compatible)
            else:
                contradicted_sources.add(q)

        # If every known candidate predicted a different observation and no
        # candidate had an untried transition, the source itself is a new hidden
        # predictive state despite sharing its current observation.
        source_resolved = None
        if source_candidates and not compatible_sources and not unknown_sources:
            source_resolved = self.add_state(
                source.observation, source_history,
                reason="confirmed_one_step_counterexample_to_all_visual_candidates")
            self.events.append(dict(
                event="predictive_split", new_state=source_resolved,
                prior_candidates=sorted(source_candidates), action=action,
                observed_target=target_observation))
        else:
            possible_sources = compatible_sources | unknown_sources
            if len(possible_sources) == 1:
                source_resolved = next(iter(possible_sources))

        if terminal_status == "WIN":
            terminal_observation = ("terminal", "WIN")
            states = sorted(self.observation_states.get(terminal_observation, ()))
            if states:
                target_candidates = {states[0]}
            else:
                target_candidates = {
                    self.add_state(terminal_observation, target_history,
                                   reason="observed_terminal_win")
                }
            target_new_possible = False
            self.goal_states.update(target_candidates)
        else:
            visual_targets = set(self.observation_states.get(target_observation, ()))
            if predicted_targets:
                target_candidates = predicted_targets & visual_targets
                if not target_candidates:
                    target_candidates = predicted_targets
            else:
                target_candidates = set(visual_targets)

            if not target_candidates:
                target_candidates = {
                    self.add_state(target_observation, target_history,
                                   reason="new_observation_class_after_action")
                }
                target_new_possible = False
            else:
                # Even one visually matching known state may hide another
                # predictive state until future behaviour separates it.
                target_new_possible = True

        target = PredictiveBelief(
            ("terminal", "WIN") if terminal_status == "WIN" else target_observation,
            tuple(sorted(target_candidates)), target_new_possible,
            "transition_update")

        if source_resolved is not None and target.resolved_state is not None:
            self.record_transition(source_resolved, action, target.resolved_state)
            self.events.append(dict(
                event="predictive_transition", source=source_resolved,
                action=action, target=target.resolved_state,
                source_was_split=source_resolved not in source_candidates))

        self.events.append(dict(
            event="predictive_belief_update", action=action,
            source_candidates=sorted(source_candidates),
            compatible_sources=sorted(compatible_sources),
            unknown_sources=sorted(unknown_sources),
            contradicted_sources=sorted(contradicted_sources),
            target_candidates=list(target.candidates),
            target_new_state_possible=target.new_state_possible))
        return target, source_resolved

    def choose_identifying_action(self, belief):
        """Pick a real action that best separates current candidate states."""
        candidates = tuple(sorted(belief.candidates))
        if len(candidates) < 2:
            return None
        scored = []
        for action in range(self.num_actions):
            signatures = []
            unknown = 0
            visits = 0
            for q in candidates:
                row = self.counts.get((q, action))
                visits += self.action_visits.get((q, action), 0)
                if not row:
                    signatures.append(None)
                    unknown += 1
                    continue
                modal = max(row.items(), key=lambda item: (item[1], -item[0]))[0]
                signatures.append(self.state_observation[modal])
            separated = 0
            for i in range(len(signatures)):
                for j in range(i+1, len(signatures)):
                    if signatures[i] is not None and signatures[j] is not None \
                            and signatures[i] != signatures[j]:
                        separated += 1
            scored.append((separated, unknown, -visits, -action, action))
        return max(scored)[-1]

    def completeness(self):
        total = len(self.id_to_state) * self.num_actions
        known = sum((q, a) in self.counts for q in range(len(self.id_to_state))
                    for a in range(self.num_actions))
        return dict(states=len(self.id_to_state), known_pairs=known,
                    possible_pairs=total, fraction=known/max(1, total))
