"""Cheap algebraic alignment between separator messages and typed demands."""

from __future__ import annotations

from collections.abc import Iterable
from functools import lru_cache

import sympy as sp


@lru_cache(maxsize=131_072)
def _monomial_support(value: str) -> frozenset[tuple[tuple[str, int], ...]]:
    expression = sp.expand(sp.sympify(value))
    if expression == 0 or not expression.free_symbols:
        return frozenset()
    variables = tuple(sorted(expression.free_symbols, key=str))
    polynomial = sp.Poly(expression, *variables, domain=sp.QQ)
    return frozenset(
        tuple(
            (str(variable), exponent)
            for variable, exponent in zip(variables, powers, strict=True)
            if exponent
        )
        for powers, _ in polynomial.terms()
    )


def polynomial_obligation_alignment_rank(
    candidates: Iterable[sp.Expr],
    targets: Iterable[sp.Expr],
) -> tuple[int, int]:
    """Prefer shared monomial structure without treating it as a proof."""

    candidate_supports = tuple(
        support
        for support in (_monomial_support(sp.sstr(item)) for item in candidates)
        if support
    )
    target_supports = tuple(
        support
        for support in (_monomial_support(sp.sstr(item)) for item in targets)
        if support
    )
    if not candidate_supports or not target_supports:
        return (0, 0)
    pairs = tuple(
        (len(candidate & target), len(candidate ^ target))
        for candidate in candidate_supports
        for target in target_supports
    )
    maximum_overlap = max(item[0] for item in pairs)
    minimum_difference = min(
        difference
        for overlap, difference in pairs
        if overlap == maximum_overlap
    )
    return (-maximum_overlap, minimum_difference)


__all__ = ["polynomial_obligation_alignment_rank"]
