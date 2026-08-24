"""Bounded normal-form residuals for open typed proof branches.

The residual is a search signal, not an acceptance rule.  A zero remainder is
nevertheless a valid ideal-membership proof because the reduction certificate
is replayed against a basis whose every element is certified to follow from the
current generators.  A nonzero remainder is only a bounded observation when
the Buchberger basis is incomplete.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import sympy as sp

from worker.backend.certified_buchberger import (
    certified_buchberger_dag,
    certify_dag_ideal_membership,
)


@dataclass(frozen=True)
class PolynomialAtomResidual:
    target_polynomial: str
    remainder: str
    proved: bool
    replayed: bool
    term_count: int
    total_degree: int
    operation_count: int

    @property
    def rank(self) -> tuple[int, int, int, int]:
        return (
            0 if self.proved and self.replayed else 1,
            self.term_count,
            self.total_degree,
            self.operation_count,
        )


@dataclass(frozen=True)
class PolynomialBranchResidual:
    branch_index: int
    atoms: tuple[PolynomialAtomResidual, ...]
    open_atom_count: int
    total_term_count: int
    maximum_total_degree: int
    total_operation_count: int

    @property
    def rank(self) -> tuple[int, int, int, int]:
        return (
            self.open_atom_count,
            self.total_term_count,
            self.maximum_total_degree,
            self.total_operation_count,
        )


@dataclass(frozen=True)
class PolynomialProofResidual:
    branches: tuple[PolynomialBranchResidual, ...]
    selected_branch_index: int | None
    selected_rank: tuple[int, int, int, int]
    basis_polynomials: tuple[str, ...]
    basis_complete: bool
    basis_replayed: bool
    processed_pair_count: int
    stopped_reason: str | None


def _complexity(expression: sp.Expr) -> tuple[int, int, int]:
    expanded = sp.expand(expression)
    if expanded == 0:
        return (0, 0, 0)
    variables = tuple(sorted(expanded.free_symbols, key=str))
    if not variables:
        return (1, 0, int(sp.count_ops(expanded)))
    polynomial = sp.Poly(expanded, *variables, domain=sp.QQ)
    return (
        polynomial.length(),
        int(polynomial.total_degree()),
        int(sp.count_ops(expanded)),
    )


def _linear_row_basis(
    rows: list[list[sp.Rational]],
) -> tuple[tuple[tuple[sp.Rational, ...], tuple[sp.Rational, ...], int], ...]:
    """RREF rows while retaining each row's exact generator combination."""

    if not rows:
        return ()
    count = len(rows)
    width = len(rows[0])
    transforms = [
        [sp.Rational(1 if left == right else 0) for right in range(count)]
        for left in range(count)
    ]
    pivot_row = 0
    output = []
    for column in range(width):
        selected = next(
            (row for row in range(pivot_row, count) if rows[row][column]),
            None,
        )
        if selected is None:
            continue
        rows[pivot_row], rows[selected] = rows[selected], rows[pivot_row]
        transforms[pivot_row], transforms[selected] = (
            transforms[selected], transforms[pivot_row]
        )
        scale = rows[pivot_row][column]
        rows[pivot_row] = [value / scale for value in rows[pivot_row]]
        transforms[pivot_row] = [value / scale for value in transforms[pivot_row]]
        for row in range(count):
            if row == pivot_row or not rows[row][column]:
                continue
            factor = rows[row][column]
            rows[row] = [
                value - factor * pivot
                for value, pivot in zip(rows[row], rows[pivot_row], strict=True)
            ]
            transforms[row] = [
                value - factor * pivot
                for value, pivot in zip(
                    transforms[row], transforms[pivot_row], strict=True
                )
            ]
        output.append(
            (tuple(rows[pivot_row]), tuple(transforms[pivot_row]), column)
        )
        pivot_row += 1
        if pivot_row == count:
            break
    return tuple(output)


def _linear_span_reduce(
    target: sp.Expr,
    generators: tuple[sp.Expr, ...],
    variables: tuple[sp.Symbol, ...],
) -> tuple[sp.Expr, bool]:
    """Reduce in the exact QQ-vector space of coordinate monomials."""

    expressions = (*generators, sp.expand(target))
    polynomials = tuple(
        sp.Poly(item, *variables, domain=sp.QQ) for item in expressions
    )
    monomials = tuple(
        sorted(
            {
                monomial
                for polynomial in polynomials
                for monomial, _coefficient in polynomial.terms()
            },
            reverse=True,
        )
    )
    if not monomials:
        return sp.Integer(0), True
    generator_rows = [
        [
            sp.Rational(polynomial.coeff_monomial(monomial))
            for monomial in monomials
        ]
        for polynomial in polynomials[:-1]
    ]
    residual = [
        sp.Rational(polynomials[-1].coeff_monomial(monomial))
        for monomial in monomials
    ]
    combination = [sp.Rational(0) for _ in generators]
    for row, transform, pivot in _linear_row_basis(generator_rows):
        factor = residual[pivot]
        if not factor:
            continue
        residual = [
            value - factor * basis
            for value, basis in zip(residual, row, strict=True)
        ]
        combination = [
            value + factor * coefficient
            for value, coefficient in zip(combination, transform, strict=True)
        ]
    remainder = sp.expand(
        sum(
            (
                coefficient
                * sp.prod(
                    variable**power
                    for variable, power in zip(variables, monomial, strict=True)
                )
                for coefficient, monomial in zip(residual, monomials, strict=True)
            ),
            sp.Integer(0),
        )
    )
    replay_residual = sp.expand(
        target
        - sum(
            (
                coefficient * generator
                for coefficient, generator in zip(
                    combination, generators, strict=True
                )
            ),
            sp.Integer(0),
        )
        - remainder
    )
    return remainder, replay_residual == 0


def bounded_normal_form_residual(
    generators: Iterable[sp.Expr],
    obligation_branches: Iterable[Iterable[sp.Expr]],
    *,
    max_pairs: int = 8,
    max_basis_size: int = 48,
    max_polynomial_terms: int = 512,
    max_certificate_terms: int = 4_096,
    direct_message_reduction: bool = False,
    linear_span_reduction: bool = False,
) -> PolynomialProofResidual:
    """Reduce each coherent AND branch against one bounded certified basis.

    OR is represented by the outer iterable and AND by each inner iterable.
    The selected rank is the best coherent branch rank, so atoms from mutually
    incompatible branches can never be combined for search credit.
    """

    if min(
        max_pairs,
        max_basis_size,
        max_polynomial_terms,
        max_certificate_terms,
    ) < 0:
        raise ValueError("normal-form residual budgets must be nonnegative")
    if max_basis_size < 1 or max_polynomial_terms < 1 or max_certificate_terms < 1:
        raise ValueError("normal-form residual size budgets must be positive")
    if direct_message_reduction and linear_span_reduction:
        raise ValueError("select only one incremental residual reduction mode")

    generator_expressions = tuple(
        dict.fromkeys(
            sp.expand(sp.sympify(item))
            for item in generators
            if sp.expand(sp.sympify(item)) != 0
        )
    )
    raw_branches = tuple(tuple(branch) for branch in obligation_branches)
    branches = tuple(
        tuple(
            dict.fromkeys(
                sp.expand(sp.sympify(item)) for item in branch
            )
        )
        for branch in raw_branches
        if branch
    )
    if not branches:
        return PolynomialProofResidual(
            branches=(),
            selected_branch_index=None,
            selected_rank=(0, 0, 0, 0),
            basis_polynomials=(),
            basis_complete=True,
            basis_replayed=True,
            processed_pair_count=0,
            stopped_reason=None,
        )

    variables = tuple(
        sorted(
            set().union(
                *(item.free_symbols for item in generator_expressions),
                *(
                    item.free_symbols
                    for branch in branches
                    for item in branch
                ),
            ),
            key=str,
        )
    )
    # The certified backend requires a nonempty ring even for constant goals.
    ring_variables = variables or (sp.Symbol("_residual_unit"),)
    basis = None
    ordered_generators = tuple(
        sorted(
            generator_expressions,
            key=lambda item: (
                len(sp.Add.make_args(sp.expand(item))),
                int(sp.count_ops(item)),
                sp.sstr(item),
            ),
        )
    )
    if not direct_message_reduction and not linear_span_reduction:
        basis = certified_buchberger_dag(
            ordered_generators,
            ring_variables,
            max_pairs=max_pairs,
            max_basis_size=max_basis_size,
            max_polynomial_terms=max_polynomial_terms,
            max_certificate_terms=max_certificate_terms,
        )

    branch_records: list[PolynomialBranchResidual] = []
    for branch_index, branch in enumerate(branches):
        atom_records: list[PolynomialAtomResidual] = []
        for target in branch:
            if linear_span_reduction:
                remainder, replayed = _linear_span_reduce(
                    target,
                    ordered_generators,
                    ring_variables,
                )
                remainder_text = sp.sstr(remainder)
                proved = remainder == 0
                target_text = sp.sstr(sp.expand(target))
            elif direct_message_reduction:
                if ordered_generators:
                    quotients, remainder = sp.reduced(
                        target,
                        ordered_generators,
                        *ring_variables,
                    )
                    replay_residual = sp.expand(
                        target
                        - sum(
                            (
                                quotient * generator
                                for quotient, generator in zip(
                                    quotients,
                                    ordered_generators,
                                    strict=True,
                                )
                            ),
                            sp.Integer(0),
                        )
                        - remainder
                    )
                else:
                    remainder = sp.expand(target)
                    replay_residual = sp.Integer(0)
                remainder = sp.expand(remainder)
                remainder_text = sp.sstr(remainder)
                proved = remainder == 0
                replayed = replay_residual == 0
                target_text = sp.sstr(sp.expand(target))
            else:
                if basis is None:
                    raise AssertionError("certified basis was not initialized")
                membership = certify_dag_ideal_membership(target, basis)
                remainder = sp.expand(sp.sympify(membership.remainder))
                remainder_text = membership.remainder
                proved = membership.proved
                replayed = membership.replayed
                target_text = membership.goal_polynomial
            terms, degree, operations = _complexity(remainder)
            atom_records.append(
                PolynomialAtomResidual(
                    target_polynomial=target_text,
                    remainder=remainder_text,
                    proved=proved,
                    replayed=replayed,
                    term_count=terms,
                    total_degree=degree,
                    operation_count=operations,
                )
            )
        atoms = tuple(atom_records)
        branch_records.append(
            PolynomialBranchResidual(
                branch_index=branch_index,
                atoms=atoms,
                open_atom_count=sum(not (item.proved and item.replayed) for item in atoms),
                total_term_count=sum(item.term_count for item in atoms),
                maximum_total_degree=max(
                    (item.total_degree for item in atoms), default=0
                ),
                total_operation_count=sum(item.operation_count for item in atoms),
            )
        )
    ordered = tuple(branch_records)
    selected = min(ordered, key=lambda item: (item.rank, item.branch_index))
    return PolynomialProofResidual(
        branches=ordered,
        selected_branch_index=selected.branch_index,
        selected_rank=selected.rank,
        basis_polynomials=(
            tuple(map(sp.sstr, ordered_generators))
            if direct_message_reduction or linear_span_reduction
            else basis.basis_polynomials
            if basis is not None
            else ()
        ),
        basis_complete=bool(basis is not None and basis.groebner_complete),
        basis_replayed=(
            all(atom.replayed for branch in ordered for atom in branch.atoms)
            if direct_message_reduction or linear_span_reduction
            else bool(basis is not None and basis.all_identities_replayed)
        ),
        processed_pair_count=(basis.processed_pair_count if basis is not None else 0),
        stopped_reason=(
            "linear_span_reduction"
            if linear_span_reduction
            else "direct_message_reduction"
            if direct_message_reduction
            else basis.stopped_reason
            if basis is not None
            else None
        ),
    )


__all__ = [
    "PolynomialAtomResidual",
    "PolynomialBranchResidual",
    "PolynomialProofResidual",
    "bounded_normal_form_residual",
]
