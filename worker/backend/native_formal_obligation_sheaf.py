"""Heterogeneous sheaf coordination for native formal proof obligations.

Each symbolic engine keeps its own local coordinate system.  A Newclid view may
score relation atoms, a GCLC/Wu view may score polynomial and non-degeneracy
obligations, and a construction synthesizer may score typed actions.  The
engines communicate only through explicit restriction maps into shared edge
stalks.  ADMM coordinates finite search budgets; native certificate replay is
the only truth criterion.

This is intentionally different from assigning every engine one vector over a
global predicate vocabulary.  Local stalk dimensions may differ, and two
coordinates interact only when the elaborator gives them the same typed shared
channel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

import numpy as np


@dataclass(frozen=True, order=True)
class SharedChannel:
    """A typed boundary object shared by two formal languages."""

    kind: str
    signature: str
    sort: str = "Proposition"

    @property
    def key(self) -> str:
        return f"{self.sort}:{self.kind}:{self.signature}"


@dataclass(frozen=True)
class LocalCoordinate:
    """One coordinate in an agent's private formal language."""

    local_name: str
    shared: SharedChannel
    scale: float = 1.0

    def __post_init__(self) -> None:
        if not self.local_name:
            raise ValueError("local coordinate name must not be empty")
        if self.scale == 0:
            raise ValueError("restriction scale must be nonzero")


@dataclass(frozen=True)
class FormalLocalView:
    """A finite local view produced by one native formal-language agent."""

    agent_id: str
    formal_language: str
    coordinates: tuple[LocalCoordinate, ...]
    preferences: Mapping[str, float] = field(compare=False)

    def __post_init__(self) -> None:
        names = [coordinate.local_name for coordinate in self.coordinates]
        if len(names) != len(set(names)):
            raise ValueError(f"duplicate local coordinates for {self.agent_id}")
        unknown = set(self.preferences) - set(names)
        if unknown:
            raise ValueError(
                f"preferences reference unknown coordinates for {self.agent_id}: "
                f"{sorted(unknown)}"
            )

    @property
    def dimension(self) -> int:
        return len(self.coordinates)

    def preference_vector(self) -> np.ndarray:
        return np.asarray(
            [max(float(self.preferences.get(item.local_name, 0.0)), 0.0) for item in self.coordinates],
            dtype=float,
        )


@dataclass(frozen=True)
class RestrictionEdge:
    """Two restriction maps into a common edge stalk."""

    left: str
    right: str
    channels: tuple[SharedChannel, ...]
    left_map: np.ndarray = field(compare=False, repr=False)
    right_map: np.ndarray = field(compare=False, repr=False)

    def __post_init__(self) -> None:
        if self.left == self.right:
            raise ValueError("restriction edge endpoints must differ")
        if self.left_map.shape[0] != len(self.channels):
            raise ValueError("left restriction map has the wrong edge-stalk dimension")
        if self.right_map.shape[0] != len(self.channels):
            raise ValueError("right restriction map has the wrong edge-stalk dimension")


@dataclass(frozen=True)
class HeterogeneousAdmmTrace:
    iteration: int
    primal_residual: float
    dual_residual: float
    sheaf_residual: float


@dataclass(frozen=True)
class HeterogeneousAdmmResult:
    agent_ids: tuple[str, ...]
    x: Mapping[str, np.ndarray] = field(compare=False, repr=False)
    z: Mapping[str, np.ndarray] = field(compare=False, repr=False)
    u: Mapping[str, np.ndarray] = field(compare=False, repr=False)
    edges: tuple[RestrictionEdge, ...]
    trace: tuple[HeterogeneousAdmmTrace, ...]

    def score(self, agent_id: str, local_name: str, views: Sequence[FormalLocalView]) -> float:
        view = next((item for item in views if item.agent_id == agent_id), None)
        if view is None:
            return 0.0
        index = next(
            (i for i, coordinate in enumerate(view.coordinates) if coordinate.local_name == local_name),
            None,
        )
        if index is None:
            return 0.0
        return float(max(self.z[agent_id][index], 0.0))

    def shared_scores(self, views: Sequence[FormalLocalView]) -> dict[str, float]:
        """Aggregate only coordinates identified by explicit restriction maps."""

        totals: dict[str, float] = {}
        counts: dict[str, int] = {}
        by_agent = {view.agent_id: view for view in views}
        for edge in self.edges:
            left = edge.left_map @ self.z[edge.left]
            right = edge.right_map @ self.z[edge.right]
            section = 0.5 * (left + right)
            for channel, value in zip(edge.channels, section, strict=True):
                totals[channel.key] = totals.get(channel.key, 0.0) + float(max(value, 0.0))
                counts[channel.key] = counts.get(channel.key, 0) + 1
        # Isolated local coordinates are deliberately not promoted to global
        # scores: they have no typed overlap and therefore no sheaf evidence.
        _ = by_agent
        return {key: totals[key] / counts[key] for key in totals}


def build_pairwise_restriction_edges(
    views: Sequence[FormalLocalView],
) -> tuple[RestrictionEdge, ...]:
    """Build selector maps from exact typed-channel overlap.

    A local view may expose at most one coordinate for a shared channel.  This
    keeps the restriction map an auditable projection instead of a hidden
    learned merger.  Richer linear maps can be introduced later only with an
    explicit adapter and a replayed equivalence certificate.
    """

    edges: list[RestrictionEdge] = []
    for left_index, left in enumerate(views):
        left_by_channel = {coordinate.shared: index for index, coordinate in enumerate(left.coordinates)}
        if len(left_by_channel) != len(left.coordinates):
            raise ValueError(f"{left.agent_id} maps multiple coordinates to one shared channel")
        for right in views[left_index + 1 :]:
            right_by_channel = {
                coordinate.shared: index for index, coordinate in enumerate(right.coordinates)
            }
            if len(right_by_channel) != len(right.coordinates):
                raise ValueError(
                    f"{right.agent_id} maps multiple coordinates to one shared channel"
                )
            shared = tuple(sorted(set(left_by_channel) & set(right_by_channel)))
            if not shared:
                continue
            left_map = np.zeros((len(shared), left.dimension), dtype=float)
            right_map = np.zeros((len(shared), right.dimension), dtype=float)
            for row, channel in enumerate(shared):
                left_coordinate = left.coordinates[left_by_channel[channel]]
                right_coordinate = right.coordinates[right_by_channel[channel]]
                left_map[row, left_by_channel[channel]] = left_coordinate.scale
                right_map[row, right_by_channel[channel]] = right_coordinate.scale
            edges.append(
                RestrictionEdge(
                    left=left.agent_id,
                    right=right.agent_id,
                    channels=shared,
                    left_map=left_map,
                    right_map=right_map,
                )
            )
    return tuple(edges)


class HeterogeneousSheafADMM:
    """Scaled ADMM on heterogeneous vertex stalks.

    For the block vector ``z`` and coboundary ``delta_F``, the consensus step is

        (rho I + gamma delta_F^T delta_F) z = rho (x + u).

    The local proximal step stays private to each agent.  Here it is the exact
    proximal map of a quadratic preference; native agents can later replace it
    with a bounded local search while preserving the same boundary contract.
    """

    def __init__(
        self,
        views: Sequence[FormalLocalView],
        *,
        edges: Sequence[RestrictionEdge] | None = None,
        rho: float = 1.0,
        gamma: float = 1.0,
        trust_by_agent: Mapping[str, float] | None = None,
        iterations: int = 24,
        tolerance: float = 1e-9,
    ) -> None:
        if not views:
            raise ValueError("at least one local view is required")
        if rho <= 0 or gamma < 0 or iterations < 1:
            raise ValueError("rho and iterations must be positive; gamma must be nonnegative")
        ids = [view.agent_id for view in views]
        if len(ids) != len(set(ids)):
            raise ValueError("agent_id must be unique")
        if any(view.dimension == 0 for view in views):
            raise ValueError("local views must have positive dimension")
        self.views = tuple(views)
        self.edges = tuple(edges) if edges is not None else build_pairwise_restriction_edges(views)
        self.rho = float(rho)
        self.gamma = float(gamma)
        supplied_trust = dict(trust_by_agent or {})
        unknown_trust = set(supplied_trust) - set(ids)
        if unknown_trust:
            raise ValueError(f"trust references unknown local views: {sorted(unknown_trust)}")
        if any(float(value) <= 0 for value in supplied_trust.values()):
            raise ValueError("all local trust weights must be positive")
        self.trust_by_agent = {
            view.agent_id: float(supplied_trust.get(view.agent_id, 1.0))
            for view in self.views
        }
        self.iterations = int(iterations)
        self.tolerance = float(tolerance)
        self._offsets: dict[str, slice] = {}
        start = 0
        for view in self.views:
            self._offsets[view.agent_id] = slice(start, start + view.dimension)
            start += view.dimension
        self.dimension = start
        self._validate_edges()
        self._delta = self._build_coboundary()
        self._channel_blocks = self._build_channel_blocks()

    def _validate_edges(self) -> None:
        by_id = {view.agent_id: view for view in self.views}
        for edge in self.edges:
            if edge.left not in by_id or edge.right not in by_id:
                raise ValueError("restriction edge references an unknown local view")
            if edge.left_map.shape[1] != by_id[edge.left].dimension:
                raise ValueError("left restriction map has the wrong vertex-stalk dimension")
            if edge.right_map.shape[1] != by_id[edge.right].dimension:
                raise ValueError("right restriction map has the wrong vertex-stalk dimension")

    def _build_coboundary(self) -> np.ndarray:
        rows = sum(len(edge.channels) for edge in self.edges)
        delta = np.zeros((rows, self.dimension), dtype=float)
        row = 0
        for edge in self.edges:
            width = len(edge.channels)
            delta[row : row + width, self._offsets[edge.left]] = edge.left_map
            delta[row : row + width, self._offsets[edge.right]] = -edge.right_map
            row += width
        return delta

    def _split(self, vector: np.ndarray) -> dict[str, np.ndarray]:
        return {
            view.agent_id: vector[self._offsets[view.agent_id]].copy()
            for view in self.views
        }

    def _build_channel_blocks(self) -> tuple[np.ndarray, ...] | None:
        """Find the exact direct-sum decomposition of selector restrictions."""

        by_channel: dict[SharedChannel, list[int]] = {}
        for view in self.views:
            offset = self._offsets[view.agent_id].start
            for index, coordinate in enumerate(view.coordinates):
                if coordinate.scale != 1.0:
                    return None
                by_channel.setdefault(coordinate.shared, []).append(offset + index)
        expected_edges = sum(
            len(indices) * (len(indices) - 1) // 2
            for indices in by_channel.values()
        )
        if expected_edges != sum(len(edge.channels) for edge in self.edges):
            return None
        if any(
            not np.all(np.logical_or(edge.left_map == 0.0, edge.left_map == 1.0))
            or not np.all(np.logical_or(edge.right_map == 0.0, edge.right_map == 1.0))
            for edge in self.edges
        ):
            return None
        return tuple(
            np.asarray(indices, dtype=int)
            for _channel, indices in sorted(by_channel.items())
        )

    def _consensus_solve(
        self,
        rhs: np.ndarray,
        dense_system: np.ndarray | None,
    ) -> np.ndarray:
        if self._channel_blocks is None:
            if dense_system is None:
                raise RuntimeError("dense consensus system was not built")
            return np.linalg.solve(dense_system, rhs)
        result = np.empty_like(rhs)
        for indices in self._channel_blocks:
            size = len(indices)
            block_rhs = rhs[indices]
            diagonal = self.rho + self.gamma * size
            result[indices] = (
                block_rhs / diagonal
                + self.gamma * float(np.sum(block_rhs))
                / (diagonal * self.rho)
            )
        return result

    def solve(self) -> HeterogeneousAdmmResult:
        preferences = np.concatenate([view.preference_vector() for view in self.views])
        trust = np.concatenate(
            [
                np.full(view.dimension, self.trust_by_agent[view.agent_id], dtype=float)
                for view in self.views
            ]
        )
        x = preferences.copy()
        z = preferences.copy()
        u = np.zeros_like(preferences)
        system = None
        if self._channel_blocks is None:
            laplacian = self._delta.T @ self._delta
            system = self.rho * np.eye(self.dimension) + self.gamma * laplacian
        trace: list[HeterogeneousAdmmTrace] = []
        for iteration in range(1, self.iterations + 1):
            z_previous = z.copy()
            x = np.maximum(
                (trust * preferences + self.rho * (z - u)) / (trust + self.rho),
                0.0,
            )
            z = self._consensus_solve(self.rho * (x + u), system)
            u = u + x - z
            primal = float(np.linalg.norm(x - z))
            dual = float(self.rho * np.linalg.norm(z - z_previous))
            sheaf = (
                float(np.sqrt(np.mean(np.square(self._delta @ z))))
                if self._delta.shape[0]
                else 0.0
            )
            trace.append(HeterogeneousAdmmTrace(iteration, primal, dual, sheaf))
            if primal <= self.tolerance and dual <= self.tolerance:
                break
        return HeterogeneousAdmmResult(
            agent_ids=tuple(view.agent_id for view in self.views),
            x=self._split(x),
            z=self._split(z),
            u=self._split(u),
            edges=self.edges,
            trace=tuple(trace),
        )


def candidate_channel(candidate_key: str) -> SharedChannel:
    """Typed channel used by construction-search agents for one candidate."""

    return SharedChannel("construction_candidate", candidate_key, "Construction")


def build_candidate_local_view(
    *,
    agent_id: str,
    formal_language: str,
    scores: Mapping[str, float],
    eligible_candidates: Iterable[str] | None = None,
) -> FormalLocalView:
    """Create a partial local view without inventing missing observations."""

    eligible = set(scores) if eligible_candidates is None else set(eligible_candidates)
    names = sorted(eligible & set(scores))
    coordinates = tuple(
        LocalCoordinate(candidate, candidate_channel(candidate)) for candidate in names
    )
    return FormalLocalView(
        agent_id=agent_id,
        formal_language=formal_language,
        coordinates=coordinates,
        preferences={candidate: float(scores[candidate]) for candidate in names},
    )


def coordinate_candidate_scores(
    views: Sequence[FormalLocalView],
    *,
    rho: float = 1.0,
    gamma: float = 1.0,
    trust_by_agent: Mapping[str, float] | None = None,
    iterations: int = 24,
) -> tuple[dict[str, float], HeterogeneousAdmmResult]:
    """Coordinate candidate priorities and return only typed-overlap scores."""

    result = HeterogeneousSheafADMM(
        views,
        rho=rho,
        gamma=gamma,
        trust_by_agent=trust_by_agent,
        iterations=iterations,
    ).solve()
    shared = result.shared_scores(views)
    prefix = "Construction:construction_candidate:"
    scores = {
        key[len(prefix) :]: value
        for key, value in shared.items()
        if key.startswith(prefix)
    }
    return scores, result


def capability_preserving_candidate_order(
    consensus_ranking: Sequence[str],
    views: Sequence[FormalLocalView],
) -> tuple[str, ...]:
    """Interleave consensus and native local rankings without dropping either."""

    rankings: list[list[str]] = [list(consensus_ranking)]
    for view in views:
        rankings.append(
            sorted(
                view.preferences,
                key=lambda name: (-float(view.preferences[name]), name),
            )
        )
    ordered: list[str] = []
    seen: set[str] = set()
    width = max((len(values) for values in rankings), default=0)
    for index in range(width):
        for values in rankings:
            if index >= len(values) or values[index] in seen:
                continue
            seen.add(values[index])
            ordered.append(values[index])
    return tuple(ordered)
