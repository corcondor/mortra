from worker.backend.capability_preserving_portfolio import (
    ProofAgentRun,
    coordinate_capability_preserving_runs,
    summarize_capability_preserving_portfolio,
)


def test_unconfirmed_agent_claim_is_never_admitted() -> None:
    result = coordinate_capability_preserving_runs(
        "p",
        (ProofAgentRun("p", "differentiable", True, False),),
    )
    assert not result.admitted
    assert result.rejected_claims == ("differentiable",)


def test_differentiable_certificate_can_add_without_removing_exact() -> None:
    summary = summarize_capability_preserving_portfolio(
        ("p", "q"),
        (
            ProofAgentRun("p", "exact", True, True),
            ProofAgentRun("p", "differentiable", False, False),
            ProofAgentRun("q", "exact", False, False),
            ProofAgentRun("q", "differentiable", True, True),
        ),
    )
    assert summary["exact_solved"] == 1
    assert summary["portfolio_solved"] == 2
    assert summary["portfolio_additions"] == 1
    assert summary["capability_preserved"]


def test_results_ignore_other_problem_runs() -> None:
    result = coordinate_capability_preserving_runs(
        "p",
        (
            ProofAgentRun("q", "exact", True, True),
            ProofAgentRun("p", "hybrid", True, True),
        ),
    )
    assert result.admitted_agents == ("hybrid",)


def test_timeout_is_an_unknown_upper_bound_not_a_wrong_answer() -> None:
    summary = summarize_capability_preserving_portfolio(
        ("p", "q"),
        (
            ProofAgentRun("p", "exact", True, True),
            ProofAgentRun(
                "q",
                "unified",
                False,
                False,
                status="right_censored_timeout",
            ),
        ),
    )
    assert summary["portfolio_solved"] == 1
    assert summary["right_censored_unsolved"] == 1
    assert summary["certified_score_lower_bound"] == 0.5
    assert summary["optimistic_score_upper_bound"] == 1.0
