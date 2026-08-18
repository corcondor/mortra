"""Certified Groebner closure for zero/nonzero polynomial branch loci."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Iterable

import sympy as sp

from worker.backend.certified_buchberger import (
    CertifiedBuchbergerDAGResult,
    CertifiedDAGIdealMembership,
    certified_buchberger_dag,
    certify_dag_ideal_membership,
)


@dataclass(frozen=True)
class ConstructibleGroebnerCertificate:
    status: str
    saturated_equations: tuple[str, ...]
    saturation_variables: tuple[str, ...]
    buchberger: CertifiedBuchbergerDAGResult
    emptiness: CertifiedDAGIdealMembership
    goal_membership: CertifiedDAGIdealMembership | None
    all_identities_replayed: bool
    certificate_sha256: str

    @property
    def proved(self) -> bool:
        return self.status in {"empty", "goal_proved"}


def certify_constructible_groebner_branch(
    equations: Iterable[sp.Expr],
    variables: Iterable[sp.Symbol],
    goal: sp.Expr,
    *,
    nonzero_factors: Iterable[sp.Expr] = (),
    max_pairs: int = 2_000,
    max_basis_size: int = 128,
    max_polynomial_terms: int = 2_000,
    max_certificate_terms: int = 20_000,
) -> ConstructibleGroebnerCertificate:
    """Prove a goal on ``V(P) intersect D(product(nonzero_factors))``.

    Rabinowitsch equations ``u_i f_i - 1`` encode every nonzero condition.
    A branch closes only through replayed DAG identities and final membership.
    """

    base_variables = tuple(variables)
    base_names = {str(variable) for variable in base_variables}
    factors = tuple(sp.expand(item) for item in nonzero_factors if item != 0)
    saturation_variables: list[sp.Symbol] = []
    saturation_equations: list[sp.Expr] = []
    for index, factor in enumerate(factors):
        name = f"__sat_{index}"
        while name in base_names:
            name = "_" + name
        variable = sp.Symbol(name)
        base_names.add(name)
        saturation_variables.append(variable)
        saturation_equations.append(sp.expand(variable * factor - 1))
    system = tuple(
        dict.fromkeys(
            sp.expand(item)
            for item in (*tuple(equations), *saturation_equations)
            if sp.expand(item) != 0
        )
    )
    ring_variables = (*base_variables, *saturation_variables)
    result = certified_buchberger_dag(
        system,
        ring_variables,
        max_pairs=max_pairs,
        max_basis_size=max_basis_size,
        max_polynomial_terms=max_polynomial_terms,
        max_certificate_terms=max_certificate_terms,
        membership_target=sp.expand(goal),
    )
    emptiness = certify_dag_ideal_membership(sp.Integer(1), result)
    goal_membership = (
        None
        if emptiness.proved
        else certify_dag_ideal_membership(sp.expand(goal), result)
    )
    replayed = (
        result.all_identities_replayed
        and emptiness.replayed
        and (goal_membership is None or goal_membership.replayed)
    )
    status = (
        "empty"
        if emptiness.proved and replayed
        else "goal_proved"
        if goal_membership is not None and goal_membership.proved and replayed
        else "unresolved"
    )
    material = "|".join(
        (
            status,
            *(sp.sstr(item) for item in system),
            *(str(item) for item in ring_variables),
            *(item.certificate_sha256 for item in result.identities),
            emptiness.certificate_sha256,
            goal_membership.certificate_sha256 if goal_membership else "empty",
        )
    )
    return ConstructibleGroebnerCertificate(
        status=status,
        saturated_equations=tuple(sp.sstr(item) for item in system),
        saturation_variables=tuple(str(item) for item in saturation_variables),
        buchberger=result,
        emptiness=emptiness,
        goal_membership=goal_membership,
        all_identities_replayed=replayed,
        certificate_sha256=hashlib.sha256(material.encode()).hexdigest(),
    )
