"""
MORTRA Future-Equivalence Refinement Core
=========================================

Design goal
-----------
Preserve the successful structure of OLD MORTRA while removing the arbitrary
fixed history horizon and making "unknown" explicit.

The core is deliberately conservative:

1. Start from current-observation states.
2. Split ONLY when observed dynamics contain a contradiction:
       same abstract state + same action -> different successor abstract states.
3. Resolve that contradiction using the SHORTEST observable history suffix that
   distinguishes the witness histories.  There is no fixed max history depth.
4. Repeat.  A downstream split can therefore propagate backward through several
   actions, approximating multi-step future equivalence by counterexamples.
5. Merge states ONLY when an exact action-conditioned congruence is certified
   on a fully observed empirical action model.  Missing actions are UNKNOWN,
   never self-loops and never evidence for equivalence.
6. Goal/reward/q/discount/planning do not appear in this module.

This is a finite-data learner.  Its certificates concern the empirical model,
not unseen environment transitions.

Observation/action values must be hashable.  Raw images should first be mapped
to a hashable observation symbol by a separate sensory front-end; this core does
not prescribe how raw perception is performed.
"""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from typing import Any, Dict, FrozenSet, Hashable, Iterable, Mapping, Optional, Sequence, Tuple
import time


StateKey = Hashable
Action = Hashable
Observation = Hashable
F = Fraction

# Explicit epistemic marker. It is never converted into a learned world state.
UNKNOWN = ("__MORTRA_UNKNOWN_TRANSITION__",)


class Relation(str, Enum):
    DIFFERENT = "DIFFERENT"
    EQUIVALENT = "EQUIVALENT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class HistoryNode:
    parent: Optional[int]
    action_from_parent: Optional[Action]
    observation: Observation
    depth: int  # number of actions since episode/reset boundary


@dataclass(frozen=True)
class SplitEvent:
    step: int
    leaf: int
    action: Action
    depth: int
    source_nodes: Tuple[int, int]
    successor_leaves: Tuple[int, int]


@dataclass(frozen=True)
class PairCertificate:
    relation: Relation
    distinguishing_word: Optional[Tuple[Action, ...]]
    missing_pairs: int


def _numbered(values: Sequence[Hashable]) -> list[int]:
    ids: Dict[Hashable, int] = {}
    return [ids.setdefault(v, len(ids)) for v in values]


def _row_distribution(
    counts: Mapping[Tuple[int, Action], Counter],
    state: int,
    action: Action,
    partition: Sequence[int],
) -> Tuple[Tuple[int, F], ...]:
    projected = Counter()
    for dest, c in counts.get((state, action), {}).items():
        projected[partition[dest]] += c
    total = sum(projected.values())
    if total == 0:
        return ()
    return tuple(
        (dest, F(c, total))
        for dest, c in sorted(projected.items())
    )


def certified_congruence_quotient(
    labels: Sequence[Observation],
    actions: Sequence[Action],
    counts: Mapping[Tuple[int, Action], Counter],
) -> dict:
    """
    Conservative exact empirical quotient.

    A state is eligible to merge only when ALL actions have observed rows.
    Incomplete states remain distinct.  For merge-eligible states, signatures
    are exact rational action-conditioned successor distributions.

    This is intentionally stricter than OLD's empirical quotient:
    equal sets of missing actions are NOT treated as equivalence evidence.
    """
    actions = tuple(actions)
    n = len(labels)
    observed = [
        frozenset(a for (s, a) in counts if s == u and sum(counts[s, a].values()) > 0)
        for u in range(n)
    ]
    complete = [obs == frozenset(actions) for obs in observed]

    # Incomplete states receive unique tags, so UNKNOWN never becomes a merge.
    tags = [
        ("complete", labels[u]) if complete[u]
        else ("incomplete", u, labels[u], tuple(a for a in actions if a in observed[u]))
        for u in range(n)
    ]
    blocks = _numbered(tags)

    rounds = 0
    while True:
        signatures = []
        for u in range(n):
            if not complete[u]:
                signatures.append(("incomplete", u, labels[u]))
                continue
            rows = tuple(
                (a, _row_distribution(counts, u, a, blocks))
                for a in actions
            )
            signatures.append(("complete", labels[u], rows))
        new = _numbered(signatures)
        rounds += 1
        if new == blocks:
            break
        blocks = new

    groups: Dict[int, list[int]] = defaultdict(list)
    for u, b in enumerate(blocks):
        groups[b].append(u)

    # Exact certificate: every member of a merged block must be complete,
    # observation-identical, and action-row identical after projection.
    for b, members in groups.items():
        if len(members) <= 1:
            continue
        ref = members[0]
        assert complete[ref]
        for u in members[1:]:
            if not complete[u] or labels[u] != labels[ref]:
                raise AssertionError("invalid certified merge")
            for a in actions:
                if _row_distribution(counts, u, a, blocks) != _row_distribution(counts, ref, a, blocks):
                    raise AssertionError("non-congruent merge")

    # Action residual is exact: projected rows inside a block are identical.
    eps_action = F(0)
    for b, members in groups.items():
        if len(members) <= 1:
            continue
        ref = members[0]
        for a in actions:
            target = dict(_row_distribution(counts, ref, a, blocks))
            for u in members[1:]:
                row = dict(_row_distribution(counts, u, a, blocks))
                keys = row.keys() | target.keys()
                residual = sum((abs(row.get(k, F(0)) - target.get(k, F(0))) for k in keys), F(0))
                eps_action = max(eps_action, residual)

    return {
        "blocks": blocks,
        "groups": dict(groups),
        "complete_states": complete,
        "observed_actions": [tuple(a for a in actions if a in obs) for obs in observed],
        "rounds": rounds,
        "eps_action": float(eps_action),
        "scope": "fully-observed empirical action rows only; missing rows remain UNKNOWN",
    }


def pair_relation_on_empirical_model(
    labels: Sequence[Observation],
    actions: Sequence[Action],
    counts: Mapping[Tuple[int, Action], Counter],
    left: int,
    right: int,
) -> PairCertificate:
    """
    Exact three-valued relation for the deterministic part of an empirical model.

    DIFFERENT:
        an observed finite action word reaches different observations.
    EQUIVALENT:
        the reachable pair-product region is deterministic, fully observed for
        every action, and contains no observation difference.
    UNKNOWN:
        no difference is proved, but a missing or nondeterministic row prevents
        an equivalence certificate.
    """
    actions = tuple(actions)
    if labels[left] != labels[right]:
        return PairCertificate(Relation.DIFFERENT, (), 0)

    def deterministic_dest(s: int, a: Action):
        row = counts.get((s, a), Counter())
        if not row:
            return "missing", None
        if len(row) != 1:
            return "nondeterministic", None
        return "known", next(iter(row))

    start = (min(left, right), max(left, right))
    q = deque([(start, ())])
    seen = {start}
    missing = 0

    while q:
        (u, v), word = q.popleft()
        if labels[u] != labels[v]:
            return PairCertificate(Relation.DIFFERENT, word, missing)

        for a in actions:
            su, nu = deterministic_dest(u, a)
            sv, nv = deterministic_dest(v, a)
            if su != "known" or sv != "known":
                missing += 1
                continue

            next_word = word + (a,)
            if labels[nu] != labels[nv]:
                return PairCertificate(Relation.DIFFERENT, next_word, missing)

            pair = (min(nu, nv), max(nu, nv))
            if pair not in seen:
                seen.add(pair)
                q.append((pair, next_word))

    if missing:
        return PairCertificate(Relation.UNKNOWN, None, missing)
    return PairCertificate(Relation.EQUIVALENT, None, 0)


class FutureRefinementCore:
    """
    Variable-history, contradiction-driven state construction.

    History is stored as a persistent DAG of exact observed prefixes, so no
    fixed max-depth truncation is required.

    The public learned states are:
        history-refined leaves -> conservative certified quotient blocks.
    """

    BEGIN = ("__MORTRA_EPISODE_BEGIN__",)

    def __init__(self, actions: Sequence[Action]):
        if not actions:
            raise ValueError("actions must be non-empty")
        if len(set(actions)) != len(actions):
            raise ValueError("actions must be unique")
        self.actions = tuple(actions)

        self.nodes: list[HistoryNode] = []
        self.root_index: Dict[Observation, int] = {}
        self.child_index: Dict[Tuple[int, Action, Observation], int] = {}

        # Evidence graph between exact history nodes.
        self.raw: Dict[Tuple[int, Action], Counter] = defaultdict(Counter)

        # Variable-order refinement rules:
        # leaf-key -> shortest distinguishing history depth.
        self.rules: Dict[Hashable, int] = {}

        self.mapping: list[int] = []
        self.leaf_keys: list[Hashable] = []
        self.leaf_depths: list[int] = []
        self.leaf_counts: Dict[Tuple[int, Action], Counter] = defaultdict(Counter)
        self.model: Optional[dict] = None
        self.context_blocks: list[int] = []

        self.current: Optional[int] = None
        self.step = 0
        self.split_events: list[SplitEvent] = []
        self.unresolved: list[dict] = []
        self.model_seconds = 0.0

        self._suffix_cache: Dict[Tuple[int, int], Hashable] = {}

    # ------------------------------------------------------------------
    # Persistent exact history storage
    # ------------------------------------------------------------------

    def _intern_root(self, observation: Observation) -> int:
        if observation not in self.root_index:
            idx = len(self.nodes)
            self.root_index[observation] = idx
            self.nodes.append(HistoryNode(None, None, observation, 0))
        return self.root_index[observation]

    def _intern_child(self, parent: int, action: Action, observation: Observation) -> int:
        key = (parent, action, observation)
        if key not in self.child_index:
            idx = len(self.nodes)
            self.child_index[key] = idx
            self.nodes.append(
                HistoryNode(parent, action, observation, self.nodes[parent].depth + 1)
            )
        return self.child_index[key]

    def begin(self, observation: Observation) -> int:
        self.current = self._intern_root(observation)
        self.rebuild()
        return self.state()

    def observe(self, action: Action, observation: Observation) -> int:
        if self.current is None:
            raise RuntimeError("begin() must be called before observe()")
        if action not in self.actions:
            raise KeyError(f"unknown action {action!r}")

        parent = self.current
        child = self._intern_child(parent, action, observation)
        self.raw[parent, action][child] += 1
        self.current = child
        self.step += 1
        self.rebuild()
        return self.state()

    # ------------------------------------------------------------------
    # Exact suffixes and adaptive classification
    # ------------------------------------------------------------------

    def _suffix(self, node_id: int, depth: int) -> Hashable:
        """
        Exact last `depth` action-observation transitions, including the
        observation at the beginning of that suffix.

        If the requested depth crosses the episode boundary, BEGIN is included.
        No numeric padding or magic history value is introduced.
        """
        if depth < 0:
            raise ValueError("depth must be >=0")
        key = (node_id, depth)
        cached = self._suffix_cache.get(key)
        if cached is not None:
            return cached

        node = self.nodes[node_id]
        if depth == 0:
            out = (("o", node.observation),)
            self._suffix_cache[key] = out
            return out

        transitions = []
        cur = node_id
        remaining = depth
        while remaining > 0 and self.nodes[cur].parent is not None:
            n = self.nodes[cur]
            transitions.append((n.action_from_parent, n.observation))
            cur = n.parent
            remaining -= 1

        base_obs = self.nodes[cur].observation
        ordered = list(reversed(transitions))
        payload = [("o", base_obs)]
        for a, o in ordered:
            payload.extend((("a", a), ("o", o)))

        if remaining > 0:
            payload.insert(0, self.BEGIN)

        out = tuple(payload)
        self._suffix_cache[key] = out
        return out

    def _classify(self, node_id: int) -> Tuple[Hashable, int]:
        obs = self.nodes[node_id].observation
        key: Hashable = ("obs", obs)
        depth = 0
        seen = set()
        while key in self.rules:
            if key in seen:
                raise AssertionError("cyclic refinement rule")
            seen.add(key)
            depth = self.rules[key]
            key = ("refined", key, self._suffix(node_id, depth))
        return key, depth

    def _shortest_distinguishing_depth(self, left: int, right: int, current_depth: int) -> Optional[int]:
        if left == right:
            return None

        # If two observable histories differ at all, some finite suffix reaching
        # to their earliest differing point (or BEGIN boundary) distinguishes them.
        max_depth = max(self.nodes[left].depth, self.nodes[right].depth) + 1
        for depth in range(current_depth + 1, max_depth + 1):
            if self._suffix(left, depth) != self._suffix(right, depth):
                return depth
        return None

    # ------------------------------------------------------------------
    # Refinement + conservative merge
    # ------------------------------------------------------------------

    def rebuild(self) -> None:
        started = time.perf_counter()

        while True:
            info = [self._classify(i) for i in range(len(self.nodes))]
            ids: Dict[Hashable, int] = {}
            self.mapping = [ids.setdefault(key, len(ids)) for key, _ in info]
            self.leaf_keys = [None] * len(ids)
            self.leaf_depths = [0] * len(ids)

            for node_id, (key, depth) in enumerate(info):
                leaf = self.mapping[node_id]
                self.leaf_keys[leaf] = key
                self.leaf_depths[leaf] = max(self.leaf_depths[leaf], depth)

            counts: Dict[Tuple[int, Action], Counter] = defaultdict(Counter)
            witnesses: Dict[Tuple[int, Action], Dict[int, set[int]]] = defaultdict(lambda: defaultdict(set))

            for (u, a), row in self.raw.items():
                s = self.mapping[u]
                for v, c in row.items():
                    z = self.mapping[v]
                    counts[s, a][z] += c
                    witnesses[s, a][z].add(u)

            candidates = []
            unresolved_now = []

            for (s, a), by_successor in witnesses.items():
                successor_items = list(by_successor.items())
                if len(successor_items) < 2:
                    continue

                for i, (v, sources) in enumerate(successor_items):
                    for w, others in successor_items[i + 1:]:
                        for u in sorted(sources):
                            for t in sorted(others):
                                depth = self._shortest_distinguishing_depth(
                                    u, t, self.leaf_depths[s]
                                )
                                if depth is None:
                                    unresolved_now.append({
                                        "leaf": s,
                                        "action": a,
                                        "source_nodes": (u, t),
                                        "successor_leaves": (v, w),
                                        "reason": "identical observable history has multiple empirical successors",
                                    })
                                    continue
                                candidates.append((depth, s, repr(a), u, t, v, w, a))

            if not candidates:
                self.unresolved = unresolved_now
                break

            # Mathematical priority: shortest distinguishing context first.
            # Remaining tuple fields make the update deterministic only.
            candidates.sort(key=lambda x: x[:-1])
            depth, s, _, u, t, v, w, action = candidates[0]
            leaf_key = self.leaf_keys[s]

            old = self.rules.get(leaf_key)
            if old is not None and old >= depth:
                raise AssertionError("refinement failed to increase information")
            self.rules[leaf_key] = depth
            self.split_events.append(
                SplitEvent(self.step, s, action, depth, (u, t), (v, w))
            )

        self.leaf_counts = counts

        labels = [None] * len(self.leaf_keys)
        for node_id, leaf in enumerate(self.mapping):
            labels[leaf] = self.nodes[node_id].observation

        self.model = certified_congruence_quotient(
            labels, self.actions, self.leaf_counts
        )
        self.context_blocks = [
            self.model["blocks"][leaf] for leaf in self.mapping
        ]

        self.model_seconds += time.perf_counter() - started

    # ------------------------------------------------------------------
    # Readout / audit
    # ------------------------------------------------------------------

    def state(self) -> int:
        if self.current is None or self.model is None:
            raise RuntimeError("model not initialized")
        return self.context_blocks[self.current]

    def encode_known_history_node(self, node_id: int) -> int:
        if not (0 <= node_id < len(self.nodes)):
            raise IndexError(node_id)
        return self.context_blocks[node_id]

    def relation_between_leaves(self, left: int, right: int) -> PairCertificate:
        labels = [None] * len(self.leaf_keys)
        for node_id, leaf in enumerate(self.mapping):
            labels[leaf] = self.nodes[node_id].observation
        return pair_relation_on_empirical_model(
            labels, self.actions, self.leaf_counts, left, right
        )

    def _leaf_labels(self) -> list[Observation]:
        labels = [None] * len(self.leaf_keys)
        for node_id, leaf in enumerate(self.mapping):
            labels[leaf] = self.nodes[node_id].observation
        return labels

    def quotient_labels(self) -> Dict[int, Observation]:
        """Observation emitted by each certified quotient block."""
        if self.model is None:
            raise RuntimeError("model not initialized")
        leaf_labels = self._leaf_labels()
        return {
            block: leaf_labels[members[0]]
            for block, members in self.model["groups"].items()
        }

    def quotient_support(self) -> Dict[Tuple[int, Action], FrozenSet[int]]:
        """
        Known empirical successor support on quotient blocks.

        Missing action rows are omitted, never converted to self-loops.
        """
        if self.model is None:
            raise RuntimeError("model not initialized")
        support: Dict[Tuple[int, Action], set[int]] = defaultdict(set)
        blocks = self.model["blocks"]
        for (leaf, action), row in self.leaf_counts.items():
            source_block = blocks[leaf]
            for dest_leaf in row:
                support[source_block, action].add(blocks[dest_leaf])
        return {k: frozenset(v) for k, v in support.items()}

    def begin_belief(self, observation: Observation) -> FrozenSet[Hashable]:
        """
        Belief over the CURRENT LEARNED EMPIRICAL MODEL.

        This does not claim completeness of the real environment.  It contains
        all learned quotient states emitting `observation`.
        """
        labels = self.quotient_labels()
        return frozenset(b for b, o in labels.items() if o == observation)

    def update_belief(
        self,
        belief: Iterable[Hashable],
        action: Action,
        next_observation: Observation,
    ) -> FrozenSet[Hashable]:
        """
        Recursive empirical belief update with explicit UNKNOWN propagation.

        If any candidate state's action row is unobserved, UNKNOWN is retained.
        Conditioning UNKNOWN on an observation conservatively admits every
        learned state with that observation plus UNKNOWN itself.
        """
        if action not in self.actions:
            raise KeyError(action)

        labels = self.quotient_labels()
        support = self.quotient_support()
        predicted: set[Hashable] = set()
        unknown = False

        for state in belief:
            if state == UNKNOWN:
                unknown = True
                continue
            row = support.get((state, action))
            if row is None:
                unknown = True
            else:
                predicted.update(row)

        conditioned = {
            s for s in predicted
            if s != UNKNOWN and labels.get(s) == next_observation
        }

        if unknown:
            conditioned.update(
                b for b, o in labels.items()
                if o == next_observation
            )
            conditioned.add(UNKNOWN)

        return frozenset(conditioned)

    def reconstruct_belief(
        self,
        observations: Sequence[Observation],
        actions: Sequence[Action],
    ) -> FrozenSet[Hashable]:
        """Recompute empirical belief from the complete supplied history."""
        if len(observations) != len(actions) + 1:
            raise ValueError("len(observations) must equal len(actions)+1")
        belief = self.begin_belief(observations[0])
        for action, obs in zip(actions, observations[1:]):
            belief = self.update_belief(belief, action, obs)
        return belief

    def shortest_unresolved_experiment(
        self,
        left_leaf: int,
        right_leaf: int,
    ) -> Optional[Tuple[Action, ...]]:
        """
        Shortest action word that reaches an unresolved empirical transition
        between two still-indistinguishable leaf states.

        If the pair is already DIFFERENT or certified EQUIVALENT, returns None.
        This is not a scored heuristic: it is BFS by action-word length.
        """
        labels = self._leaf_labels()
        initial = pair_relation_on_empirical_model(
            labels, self.actions, self.leaf_counts, left_leaf, right_leaf
        )
        if initial.relation != Relation.UNKNOWN:
            return None

        def det_dest(s: int, a: Action):
            row = self.leaf_counts.get((s, a), Counter())
            if len(row) != 1:
                return None
            return next(iter(row))

        start = (min(left_leaf, right_leaf), max(left_leaf, right_leaf))
        queue = deque([(start, ())])
        seen = {start}

        while queue:
            (u, v), word = queue.popleft()
            for action in self.actions:
                nu = det_dest(u, action)
                nv = det_dest(v, action)
                if nu is None or nv is None:
                    return word + (action,)
                if labels[nu] != labels[nv]:
                    # This is a known distinction, not an unresolved experiment.
                    continue
                pair = (min(nu, nv), max(nu, nv))
                if pair not in seen:
                    seen.add(pair)
                    queue.append((pair, word + (action,)))
        return None

    def summary(self) -> dict:
        if self.model is None:
            return {}
        used_depths = [self.leaf_depths[self.mapping[i]] for i in range(len(self.nodes))]
        return {
            "history_nodes": len(self.nodes),
            "leaf_states": len(self.leaf_keys),
            "quotient_states": len(self.model["groups"]),
            "split_count": len(self.split_events),
            "max_selected_history_depth": max(self.leaf_depths, default=0),
            "max_observed_history_depth": max((n.depth for n in self.nodes), default=0),
            "unresolved_counterexamples": list(self.unresolved),
            "eps_action": self.model["eps_action"],
            "certificate_scope": self.model["scope"],
            "model_seconds": self.model_seconds,
            "has_fixed_history_cap": False,
            "uses_goal": False,
            "uses_reward": False,
            "uses_q": False,
            "uses_discount": False,
        }
