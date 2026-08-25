import json

import sympy as sp

from scripts.experiment_guarded_linear_singular import _bounded_goal_degree
from scripts.experiment_terminal_checkpoint_singular import (
    factor_terminal_systems,
    load_terminal_checkpoint,
)
from worker.backend.jgex_exact_constraint_bridge import (
    _canonical_nonconstant_factor_keys,
)


def test_terminal_checkpoint_loader_clears_only_proved_denominators(tmp_path) -> None:
    checkpoint = tmp_path / "checkpoint.json"
    checkpoint.write_text(
        json.dumps(
            {
                "schema": "mortra.terminal_groebner_system.v1",
                "certificate_sha256": "abc",
                "input_polynomials": ["(p*x + 1)/p", "x - 2"],
                "variables": ["x"],
                "coefficient_parameters": ["p"],
                "goal_polynomial": "x**2 - 4",
                "nonzero_conditions": ["p != 0"],
            }
        ),
        encoding="utf-8",
    )

    loaded = load_terminal_checkpoint(checkpoint)

    x, p = sp.symbols("x p")
    assert loaded["polynomials"] == (p * x + 1, x - 2)
    assert loaded["variables"] == (x,)
    assert loaded["coefficient_parameters"] == (p,)
    assert loaded["known_nonzero_factor_keys"] == ("p",)
    assert loaded["nonzero_factor_expressions"] == (p,)
    assert loaded["full_ring_variables"] == (x, p)
    assert loaded["goal"] == x**2 - 4
    assert loaded["cleared_denominators"] == ("p",)


def test_terminal_checkpoint_loader_rejects_unproved_denominator(tmp_path) -> None:
    checkpoint = tmp_path / "checkpoint.json"
    checkpoint.write_text(
        json.dumps(
            {
                "schema": "mortra.terminal_groebner_system.v1",
                "certificate_sha256": "abc",
                "input_polynomials": ["x/p"],
                "variables": ["x"],
                "coefficient_parameters": ["p"],
                "goal_polynomial": "x",
                "nonzero_conditions": [],
            }
        ),
        encoding="utf-8",
    )

    try:
        load_terminal_checkpoint(checkpoint)
    except ValueError as error:
        assert "unproved denominator" in str(error)
    else:
        raise AssertionError("an unproved denominator must not be cleared")


def test_terminal_checkpoint_loader_parses_large_expanded_polynomial(tmp_path) -> None:
    checkpoint = tmp_path / "checkpoint.json"
    term_count = 4_000
    expanded_polynomial = " + ".join(
        f"x**{degree}*y" for degree in range(term_count)
    )
    checkpoint.write_text(
        json.dumps(
            {
                "schema": "mortra.terminal_groebner_system.v1",
                "certificate_sha256": "large-expression",
                "input_polynomials": [expanded_polynomial],
                "variables": ["x", "y"],
                "coefficient_parameters": [],
                "goal_polynomial": "y",
                "nonzero_conditions": [],
            }
        ),
        encoding="utf-8",
    )

    loaded = load_terminal_checkpoint(checkpoint)

    x, y = sp.symbols("x y")
    polynomial = sp.Poly(loaded["polynomials"][0], x, y)
    assert polynomial.length() == term_count
    assert polynomial.total_degree() == term_count


def test_bounded_goal_degree_treats_parameters_as_coefficients() -> None:
    x, y, p = sp.symbols("x y p")

    degree = _bounded_goal_degree(
        p**20 * x**3 + p * y**5,
        variables=(x, y),
        coefficient_parameters=(p,),
    )

    assert degree == 5


def test_factor_terminal_systems_builds_complete_replayed_cover() -> None:
    x, y, p = sp.symbols("x y p")
    branches = factor_terminal_systems(
        {
            "polynomials": ((x - 1) * (x + 1), (y - p) * (y + p)),
            "variables": (x, y),
            "coefficient_parameters": (p,),
        }
    )

    assert len(branches) == 4
    assert {branch["choice_indices"] for branch in branches} == {
        (0, 0),
        (0, 1),
        (1, 0),
        (1, 1),
    }
    assert all(
        certificate["replayed"]
        for certificate in branches[0]["factorization_certificates"]
    )


def test_factor_terminal_systems_prunes_source_proved_nonzero_cases() -> None:
    x, y = sp.symbols("x y")
    branches = factor_terminal_systems(
        {
            "polynomials": ((x - 1) * (x + 1), y),
            "variables": (x, y),
            "coefficient_parameters": (),
            "known_nonzero_factor_keys": tuple(
                sorted(_canonical_nonconstant_factor_keys(x - 1))
            ),
        }
    )

    assert len(branches) == 1
    assert branches[0]["choice_indices"] == (1, 0)
    certificate = branches[0]["factorization_certificates"][0]
    assert certificate["excluded_source_nonzero_factors"] == ((0, "x - 1"),)


def test_single_admissible_factor_branch_covers_the_source_variety() -> None:
    x, y = sp.symbols("x y")
    branches = factor_terminal_systems(
        {
            "polynomials": ((x - 1) * (x + 1), y),
            "variables": (x, y),
            "coefficient_parameters": (),
            "known_nonzero_factor_keys": tuple(
                sorted(_canonical_nonconstant_factor_keys(x - 1))
            ),
        }
    )

    assert len(branches) == 1
    assert branches[0]["cover_theorem"].startswith("Over an integral domain")
