"""Certificate-only union for independently scheduled proof-search agents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping


@dataclass(frozen=True)
class ProofAgentRun:
    problem: str
    agent: str
    solved: bool
    native_confirmed: bool
    artifact: str | None = None
    status: str = "completed"

    @property
    def admitted(self) -> bool:
        return self.solved and self.native_confirmed


@dataclass(frozen=True)
class CapabilityPreservingResult:
    problem: str
    admitted: bool
    admitted_agents: tuple[str, ...]
    exact_agent_admitted: bool
    rejected_claims: tuple[str, ...]
    right_censored_agents: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "problem": self.problem,
            "admitted": self.admitted,
            "admitted_agents": list(self.admitted_agents),
            "exact_agent_admitted": self.exact_agent_admitted,
            "rejected_claims": list(self.rejected_claims),
            "right_censored_agents": list(self.right_censored_agents),
        }


def coordinate_capability_preserving_runs(
    problem: str,
    runs: Iterable[ProofAgentRun],
    *,
    exact_agent: str = "exact",
) -> CapabilityPreservingResult:
    """Union native certificates without voting away the exact baseline.

    Differentiable scores and agent agreement are control-plane signals only.
    An agent enters the union precisely when its native certificate was replayed.
    """

    problem_runs = tuple(run for run in runs if run.problem == problem)
    admitted = tuple(sorted({run.agent for run in problem_runs if run.admitted}))
    rejected = tuple(
        sorted(
            {
                run.agent
                for run in problem_runs
                if run.solved and not run.native_confirmed
            }
        )
    )
    right_censored = tuple(
        sorted(
            {
                run.agent
                for run in problem_runs
                if run.status in {"timeout", "right_censored_timeout"}
            }
        )
    )
    return CapabilityPreservingResult(
        problem=problem,
        admitted=bool(admitted),
        admitted_agents=admitted,
        exact_agent_admitted=exact_agent in admitted,
        rejected_claims=rejected,
        right_censored_agents=right_censored,
    )


def summarize_capability_preserving_portfolio(
    problem_names: Iterable[str],
    runs: Iterable[ProofAgentRun],
    *,
    exact_agent: str = "exact",
) -> Mapping[str, object]:
    run_tuple = tuple(runs)
    results = tuple(
        coordinate_capability_preserving_runs(
            problem,
            run_tuple,
            exact_agent=exact_agent,
        )
        for problem in sorted(set(problem_names))
    )
    exact_solved = sum(item.exact_agent_admitted for item in results)
    portfolio_solved = sum(item.admitted for item in results)
    right_censored_unsolved = sum(
        not item.admitted and bool(item.right_censored_agents)
        for item in results
    )
    return {
        "total": len(results),
        "exact_solved": exact_solved,
        "portfolio_solved": portfolio_solved,
        "portfolio_additions": portfolio_solved - exact_solved,
        "capability_preserved": portfolio_solved >= exact_solved,
        "right_censored_unsolved": right_censored_unsolved,
        "certified_score_lower_bound": (
            portfolio_solved / len(results) if results else None
        ),
        "optimistic_score_upper_bound": (
            (portfolio_solved + right_censored_unsolved) / len(results)
            if results else None
        ),
        "results": [item.to_dict() for item in results],
    }
