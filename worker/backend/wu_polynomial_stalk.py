"""証明書付きWu擬除算を局所stalkとして交換する。"""

from __future__ import annotations

import hashlib
import io
import token
import tokenize
from dataclasses import dataclass

import sympy as sp
from sympy.polys.domains import QQ
from sympy.polys.rings import ring

from worker.backend.certified_wu_characteristic import (
    CertifiedPseudoDivision,
    CertifiedWuResult,
    _ring_main_coefficient,
)
from worker.backend.geometry_proof_hypergraph import Atom
from worker.backend.symbolic_sheaf_coordination import (
    AgentProposal,
    ExactSheafCoordinator,
    LocalCertificate,
    PredicateSignature,
    TypedVocabulary,
)


def _atom(predicate: str, expression: str) -> Atom:
    digest = hashlib.sha256(expression.encode()).hexdigest()
    return Atom(predicate, (f"p_{digest}",))


def polynomial_zero_atom(expression: str) -> Atom:
    return _atom("poly_zero", expression)


def polynomial_nonzero_atom(expression: str) -> Atom:
    return _atom("poly_nonzero", expression)


def _obligation_expression(obligation: str | None) -> str | None:
    if obligation is None:
        return None
    expression = sp.sympify(obligation)
    if not isinstance(expression, sp.Unequality):
        raise ValueError(f"expected a nonzero obligation, got {obligation}")
    left, right = expression.args
    return sp.sstr(sp.expand(left - right))


def _identity_size(step: CertifiedPseudoDivision) -> int:
    return sum(
        len(item)
        for item in (
            step.dividend,
            step.divisor,
            step.multiplier,
            step.quotient,
            step.remainder_multiplier,
            step.remainder,
        )
    )


def _replay_identity_in_sparse_ring(step: CertifiedPseudoDivision) -> bool:
    """Independently replay a certificate in an exact sparse polynomial ring."""

    texts = (
        step.dividend,
        step.divisor,
        step.multiplier,
        step.quotient,
        step.remainder_multiplier,
        step.remainder,
    )
    token_rows = tuple(_polynomial_tokens(text) for text in texts)
    names = tuple(
        sorted(
            {
                value
                for row in token_rows
                for kind, value in row
                if kind == token.NAME
            }
        )
    )
    polynomial_ring, *generators = ring(",".join(names or ("_constant",)), QQ)
    environment = dict(zip(names, generators, strict=True))

    dividend, divisor, multiplier, quotient, remainder_multiplier, remainder = tuple(
        _evaluate_polynomial_tokens(row, polynomial_ring, environment)
        for row in token_rows
    )
    return not (
        multiplier * dividend
        - quotient * divisor
        - remainder_multiplier * remainder
    )


def _polynomial_tokens(text: str) -> tuple[tuple[int, str], ...]:
    allowed_operators = {"+", "-", "*", "**", "/", "(", ")"}
    rows: list[tuple[int, str]] = []
    for item in tokenize.generate_tokens(io.StringIO(text).readline):
        if item.type in {token.ENDMARKER, token.NEWLINE}:
            continue
        if item.type == token.NUMBER:
            if not item.string.isdigit():
                raise ValueError("polynomial coefficients must be exact integers")
        elif item.type == token.NAME:
            pass
        elif item.type == token.OP and item.string in allowed_operators:
            pass
        else:
            raise ValueError(f"unsupported polynomial token: {item.string!r}")
        rows.append((item.type, item.string))
    return tuple(rows)


def _evaluate_polynomial_tokens(rows, polynomial_ring, environment):
    """Iterative exact parser for the small polynomial certificate grammar."""

    precedence = {"+": 1, "-": 1, "*": 2, "/": 2, "u+": 3, "u-": 3, "**": 4}
    right_associative = {"u+", "u-", "**"}
    output: list[tuple[str, object]] = []
    operators: list[str] = []
    expect_operand = True
    for kind, value in rows:
        if kind == token.NUMBER:
            output.append(("value", polynomial_ring.ground_new(QQ.convert(int(value)))))
            expect_operand = False
            continue
        if kind == token.NAME:
            if value not in environment:
                raise ValueError(f"unknown polynomial variable: {value}")
            output.append(("value", environment[value]))
            expect_operand = False
            continue
        if value == "(":
            operators.append(value)
            expect_operand = True
            continue
        if value == ")":
            while operators and operators[-1] != "(":
                output.append(("operator", operators.pop()))
            if not operators:
                raise ValueError("unbalanced polynomial parentheses")
            operators.pop()
            expect_operand = False
            continue
        operator = f"u{value}" if expect_operand and value in {"+", "-"} else value
        if operator not in precedence:
            raise ValueError(f"unexpected polynomial operator: {value}")
        while operators and operators[-1] != "(":
            top = operators[-1]
            if precedence[top] > precedence[operator] or (
                precedence[top] == precedence[operator]
                and operator not in right_associative
            ):
                output.append(("operator", operators.pop()))
            else:
                break
        operators.append(operator)
        expect_operand = True
    while operators:
        operator = operators.pop()
        if operator == "(":
            raise ValueError("unbalanced polynomial parentheses")
        output.append(("operator", operator))

    values: list[object] = []
    zero_monomial = (0,) * polynomial_ring.ngens
    for kind, value in output:
        if kind == "value":
            values.append(value)
            continue
        operator = str(value)
        if operator in {"u+", "u-"}:
            if not values:
                raise ValueError("missing unary polynomial operand")
            operand = values.pop()
            values.append(operand if operator == "u+" else -operand)
            continue
        if len(values) < 2:
            raise ValueError("missing binary polynomial operand")
        right = values.pop()
        left = values.pop()
        if operator == "+":
            result = left + right
        elif operator == "-":
            result = left - right
        elif operator == "*":
            result = left * right
        elif operator == "/":
            result = left.exquo(right)
        elif operator == "**":
            if set(right) != {zero_monomial}:
                raise ValueError("polynomial exponent must be a ground integer")
            exponent = right[zero_monomial]
            if exponent.denominator != 1 or exponent < 0:
                raise ValueError("polynomial exponent must be a nonnegative integer")
            result = left ** int(exponent)
        else:
            raise ValueError(f"unsupported polynomial operator: {operator}")
        values.append(result)
    if len(values) != 1:
        raise ValueError("malformed polynomial certificate")
    return values[0]


@dataclass(frozen=True)
class WuPolynomialCoordinationReport:
    local_agent_count: int
    active_agent_count: int
    initial_fact_count: int
    regularity_assumption_count: int
    input_regularity_fact_count: int
    discharged_regularity_count: int
    open_regularity_count: int
    discharged_regularity_obligations: tuple[str, ...]
    open_regularity_obligations: tuple[str, ...]
    eligible_certificate_count: int
    oversized_certificate_count: int
    expanded_micro_certificate_count: int
    skipped_micro_certificate_count: int
    content_addressed_fallback_certificate_count: int
    accepted_certificate_count: int
    rejected_certificate_count: int
    transported_polynomial_count: int
    proof_depth: int
    goal_certificate_available: bool
    conditional_goal_solved: bool
    conditional_goal_replayed: bool
    input_conditioned_goal_solved: bool
    unconditional_goal_solved: bool


@dataclass(frozen=True)
class _WuMicroIdentity:
    parent_sha256: str
    iteration: int
    phase: str
    variable: str
    previous: str
    divisor: str
    left_multiplier: str
    quotient_term: str
    right_multiplier: str
    next_remainder: str
    direction: str

    @property
    def certificate_sha256(self) -> str:
        material = "|".join(
            (
                self.parent_sha256,
                str(self.iteration),
                self.phase,
                self.variable,
                self.previous,
                self.divisor,
                self.left_multiplier,
                self.quotient_term,
                self.right_multiplier,
                self.next_remainder,
                self.direction,
            )
        )
        return hashlib.sha256(material.encode()).hexdigest()

    @property
    def conclusion(self) -> Atom:
        expression = self.next_remainder if self.direction == "forward" else self.previous
        return polynomial_zero_atom(expression)

    @property
    def regularity_expression(self) -> str | None:
        expression = (
            self.right_multiplier
            if self.direction == "forward"
            else self.left_multiplier
        )
        return None if expression == "1" else expression

    @property
    def premises(self) -> tuple[Atom, ...]:
        if self.direction == "forward":
            premises = [
                polynomial_zero_atom(self.previous),
                polynomial_zero_atom(self.divisor),
            ]
            if self.right_multiplier != "1":
                premises.append(polynomial_nonzero_atom(self.right_multiplier))
            return tuple(premises)
        premises = [
            polynomial_zero_atom(self.next_remainder),
            polynomial_zero_atom(self.divisor),
        ]
        if self.left_multiplier != "1":
            premises.append(polynomial_nonzero_atom(self.left_multiplier))
        return tuple(premises)


def _parse_sparse_polynomials(texts: tuple[str, ...]):
    token_rows = tuple(_polynomial_tokens(text) for text in texts)
    names = tuple(
        sorted(
            {
                value
                for row in token_rows
                for kind, value in row
                if kind == token.NAME
            }
        )
    )
    polynomial_ring, *generators = ring(",".join(names or ("_constant",)), QQ)
    environment = dict(zip(names, generators, strict=True))
    values = tuple(
        _evaluate_polynomial_tokens(row, polynomial_ring, environment)
        for row in token_rows
    )
    return polynomial_ring, environment, values


def _micro_identity_size(identity: _WuMicroIdentity) -> int:
    return sum(
        len(item)
        for item in (
            identity.previous,
            identity.divisor,
            identity.left_multiplier,
            identity.quotient_term,
            identity.right_multiplier,
            identity.next_remainder,
        )
    )


def _micro_identities_from_step(
    step: CertifiedPseudoDivision,
    *,
    direction: str,
) -> tuple[_WuMicroIdentity, ...]:
    """Expand one quotient-sized certificate into exact local recurrences."""

    _, environment, values = _parse_sparse_polynomials(
        (step.dividend, step.divisor, step.remainder_multiplier, step.remainder)
    )
    dividend, divisor, remainder_multiplier, normalized_remainder = values
    generator = environment[step.variable]
    variable_index = tuple(environment).index(step.variable)
    divisor_degree = divisor.degree(variable_index)
    leading = _ring_main_coefficient(divisor, variable_index)
    current = dividend
    current_degree = current.degree(variable_index)
    remaining_scale = max(0, current_degree - divisor_degree + 1)
    rows: list[_WuMicroIdentity] = []
    iteration = 0
    while current and current_degree >= divisor_degree:
        coefficient = _ring_main_coefficient(current, variable_index)
        power = current_degree - divisor_degree
        following = current * leading - divisor * coefficient * generator**power
        rows.append(
            _WuMicroIdentity(
                step.certificate_sha256,
                iteration,
                step.phase,
                step.variable,
                str(current),
                str(divisor),
                str(leading),
                str(coefficient * generator**power),
                "1",
                str(following),
                direction,
            )
        )
        current = following
        current_degree = current.degree(variable_index)
        remaining_scale -= 1
        iteration += 1
    if remaining_scale:
        following = current * leading**remaining_scale
        rows.append(
            _WuMicroIdentity(
                step.certificate_sha256,
                iteration,
                step.phase,
                step.variable,
                str(current),
                str(divisor),
                str(leading**remaining_scale),
                "0",
                "1",
                str(following),
                direction,
            )
        )
        current = following
        iteration += 1
    if current != remainder_multiplier * normalized_remainder:
        raise ValueError("micro pseudo-division does not match the published remainder")
    if remainder_multiplier != 1:
        rows.append(
            _WuMicroIdentity(
                step.certificate_sha256,
                iteration,
                step.phase,
                step.variable,
                str(current),
                str(divisor),
                "1",
                "0",
                str(remainder_multiplier),
                str(normalized_remainder),
                direction,
            )
        )
    if direction == "backward":
        rows.reverse()
    return tuple(rows)


def _replay_micro_identity(identity: _WuMicroIdentity) -> bool:
    _, _, values = _parse_sparse_polynomials(
        (
            identity.previous,
            identity.divisor,
            identity.left_multiplier,
            identity.quotient_term,
            identity.right_multiplier,
            identity.next_remainder,
        )
    )
    previous, divisor, left, quotient_term, right, next_remainder = values
    return not (left * previous - quotient_term * divisor - right * next_remainder)


def _condition_expression(condition: str) -> sp.Expr:
    text = condition.strip()
    for suffix in ("!= 0", "!=0"):
        if text.endswith(suffix):
            text = text[: -len(suffix)].strip()
            break
    expression = sp.cancel(sp.sympify(text))
    numerator, denominator = sp.fraction(expression)
    if denominator != 1:
        raise ValueError("regularity facts must be polynomial nonzero conditions")
    return sp.expand(numerator)


def _factor_keys(expression: sp.Expr) -> frozenset[str]:
    """Canonical irreducible factors over QQ, modulo nonzero constants/powers."""

    expression = sp.expand(expression)
    if expression == 0:
        return frozenset()
    symbols = tuple(sorted(expression.free_symbols, key=str))
    if not symbols:
        return frozenset()
    _, factors = sp.factor_list(expression, *symbols)
    keys: set[str] = set()
    for factor, _multiplicity in factors:
        polynomial = sp.Poly(factor, *symbols, domain=sp.QQ).monic()
        keys.add(sp.sstr(polynomial.as_expr()))
    return frozenset(keys)


def classify_regularity_obligations(
    obligations: tuple[str, ...],
    known_nonzero_conditions: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Separate obligations implied by input NDGs from open Wu branches.

    In the integral domain QQ[x_1,...,x_n], a product is nonzero iff every
    irreducible factor is nonzero.  Matching factor sets therefore handles
    constant multiples and powers without textual heuristics.
    """

    known_factors: set[str] = set()
    for condition in known_nonzero_conditions:
        known_factors.update(_factor_keys(_condition_expression(condition)))
    discharged: list[str] = []
    open_items: list[str] = []
    for obligation in obligations:
        expression = _obligation_expression(obligation)
        factors = _factor_keys(sp.sympify(expression)) if expression else frozenset()
        target = discharged if factors and factors <= known_factors else open_items
        target.append(obligation)
    return tuple(discharged), tuple(open_items)


@dataclass(frozen=True)
class _WuIdentity:
    step: CertifiedPseudoDivision
    direction: str

    @property
    def conclusion(self) -> Atom:
        expression = (
            self.step.remainder
            if self.direction == "forward"
            else self.step.dividend
        )
        return polynomial_zero_atom(expression)

    @property
    def premises(self) -> tuple[Atom, ...]:
        if self.direction == "forward":
            premises = [
                polynomial_zero_atom(self.step.dividend),
                polynomial_zero_atom(self.step.divisor),
            ]
            regularity = _obligation_expression(
                self.step.normalization_nonzero_obligation
            )
            if regularity is not None:
                premises.append(polynomial_nonzero_atom(regularity))
            return tuple(premises)

        premises = [polynomial_zero_atom(self.step.divisor)]
        if self.step.remainder.strip() != "0":
            premises.append(polynomial_zero_atom(self.step.remainder))
        regularity = _obligation_expression(self.step.nonzero_obligation)
        if regularity is not None:
            premises.append(polynomial_nonzero_atom(regularity))
        return tuple(premises)


class WuPseudoDivisionAdapter:
    imports = frozenset({"poly_zero", "poly_nonzero"})
    exports = frozenset({"poly_zero"})

    def __init__(self, identity: _WuIdentity, *, agent_id: str) -> None:
        self.agent_id = agent_id
        self.identity = identity

    def propose(
        self,
        facts: frozenset[Atom],
        goal: Atom,
        *,
        round_index: int,
    ) -> AgentProposal:
        known = {item.canonical() for item in facts}
        conclusion = self.identity.conclusion.canonical()
        premises = tuple(item.canonical() for item in self.identity.premises)
        certificates = ()
        if conclusion not in known and set(premises) <= known:
            certificates = (
                LocalCertificate(
                    agent_id=self.agent_id,
                    rule_name=self.identity.step.certificate_sha256,
                    conclusion=conclusion,
                    premises=premises,
                    native_payload={
                        "round": round_index,
                        "phase": self.identity.step.phase,
                        "variable": self.identity.step.variable,
                        "direction": self.identity.direction,
                    },
                ),
            )
        return AgentProposal(
            certificates=certificates,
            open_obligations=() if goal.canonical() in known else (goal.canonical(),),
        )

    def verify(self, certificate: LocalCertificate, facts: frozenset[Atom]) -> bool:
        identity = self.identity
        step = identity.step
        if (
            certificate.agent_id != self.agent_id
            or certificate.rule_name != step.certificate_sha256
            or certificate.conclusion.canonical() != identity.conclusion.canonical()
            or certificate.premises != tuple(
                item.canonical() for item in identity.premises
            )
            or not set(certificate.premises) <= {
                item.canonical() for item in facts
            }
        ):
            return False
        return _replay_identity_in_sparse_ring(step)


class WuMicroDivisionAdapter:
    imports = frozenset({"poly_zero", "poly_nonzero"})
    exports = frozenset({"poly_zero"})

    def __init__(self, identity: _WuMicroIdentity, *, agent_id: str) -> None:
        self.agent_id = agent_id
        self.identity = identity

    def propose(
        self,
        facts: frozenset[Atom],
        goal: Atom,
        *,
        round_index: int,
    ) -> AgentProposal:
        known = {item.canonical() for item in facts}
        conclusion = self.identity.conclusion.canonical()
        premises = tuple(item.canonical() for item in self.identity.premises)
        certificates = ()
        if conclusion not in known and set(premises) <= known:
            certificates = (
                LocalCertificate(
                    agent_id=self.agent_id,
                    rule_name=self.identity.certificate_sha256,
                    conclusion=conclusion,
                    premises=premises,
                    native_payload={
                        "round": round_index,
                        "phase": self.identity.phase,
                        "variable": self.identity.variable,
                        "direction": self.identity.direction,
                        "micro_iteration": self.identity.iteration,
                        "parent_sha256": self.identity.parent_sha256,
                    },
                ),
            )
        return AgentProposal(
            certificates=certificates,
            open_obligations=() if goal.canonical() in known else (goal.canonical(),),
        )

    def verify(self, certificate: LocalCertificate, facts: frozenset[Atom]) -> bool:
        identity = self.identity
        return (
            certificate.agent_id == self.agent_id
            and certificate.rule_name == identity.certificate_sha256
            and certificate.conclusion.canonical() == identity.conclusion.canonical()
            and certificate.premises
            == tuple(item.canonical() for item in identity.premises)
            and set(certificate.premises)
            <= {item.canonical() for item in facts}
            and _replay_micro_identity(identity)
        )


def coordinate_wu_polynomial_stalk(
    result: CertifiedWuResult,
    *,
    known_nonzero_conditions: tuple[str, ...] = (),
    max_identity_characters: int = 500_000,
) -> WuPolynomialCoordinationReport:
    """擬除算DAGを局所証明書として再生し、条件付き目標を判定する。"""

    forward = tuple(_WuIdentity(step, "forward") for step in result.triangulation_steps)
    backward = tuple(
        _WuIdentity(step, "backward") for step in reversed(result.goal_steps)
    )
    identities = (*forward, *backward)
    compact = tuple(
        item
        for item in identities
        if _identity_size(item.step) <= max_identity_characters
    )
    oversized = tuple(item for item in identities if item not in compact)
    expanded_micro: list[_WuMicroIdentity] = []
    content_addressed_fallback: list[_WuIdentity] = []
    skipped_micro = 0
    for identity in oversized:
        micro_rows = _micro_identities_from_step(
            identity.step,
            direction=identity.direction,
        )
        if micro_rows and all(
            _micro_identity_size(row) <= max_identity_characters
            for row in micro_rows
        ):
            expanded_micro.extend(micro_rows)
        else:
            skipped_micro += len(micro_rows) or 1
            # The certificate body stays inside its exact verifier; only the
            # SHA-256 rule name and typed premises cross the coordinator.
            content_addressed_fallback.append(identity)
    eligible = (*compact, *content_addressed_fallback)
    adapters = tuple(
        WuPseudoDivisionAdapter(
            identity,
            agent_id=f"wu-{identity.direction}-{index:03d}",
        )
        for index, identity in enumerate(eligible)
    )
    adapters += tuple(
        WuMicroDivisionAdapter(
            identity,
            agent_id=f"wu-micro-{identity.direction}-{index:03d}",
        )
        for index, identity in enumerate(expanded_micro)
    )

    regularity_items: list[str] = []
    for identity in eligible:
        obligation = (
            identity.step.normalization_nonzero_obligation
            if identity.direction == "forward"
            else identity.step.nonzero_obligation
        )
        expression = _obligation_expression(obligation)
        if expression is not None:
            regularity_items.append(expression)
    for identity in expanded_micro:
        if identity.regularity_expression is not None:
            regularity_items.append(identity.regularity_expression)
    regularities = tuple(dict.fromkeys(regularity_items))
    discharged, open_regularities = classify_regularity_obligations(
        tuple(f"Ne({item}, 0)" for item in regularities),
        known_nonzero_conditions,
    )
    givens = (polynomial_zero_atom("0"),)
    givens += tuple(polynomial_zero_atom(item) for item in result.initial_polynomials)
    givens += tuple(polynomial_nonzero_atom(item) for item in regularities)
    goal = polynomial_zero_atom(result.goal_polynomial)
    all_atoms = {
        *givens,
        goal,
        *(identity.conclusion for identity in eligible),
        *(premise for identity in eligible for premise in identity.premises),
        *(identity.conclusion for identity in expanded_micro),
        *(premise for identity in expanded_micro for premise in identity.premises),
    }
    entities = {
        argument
        for atom in all_atoms
        for argument in atom.canonical().arguments
    }
    coordinator = ExactSheafCoordinator(
        TypedVocabulary(
            signatures={
                "poly_zero": PredicateSignature("poly_zero", ("Polynomial",)),
                "poly_nonzero": PredicateSignature("poly_nonzero", ("Polynomial",)),
            },
            entity_sorts={entity: "Polynomial" for entity in entities},
        ),
        adapters,
    )
    coordination = coordinator.solve(
        givens,
        goal,
        max_rounds=max(1, len(adapters) + 1),
        stop_on_goal=False,
    )
    proof = coordination.proof_slice()
    conditional = (
        result.conditional_goal_proved
        and coordination.solved
        and coordination.replayed
    )
    return WuPolynomialCoordinationReport(
        local_agent_count=len(adapters),
        active_agent_count=len({item.agent_id for item in proof}),
        initial_fact_count=len(result.initial_polynomials),
        regularity_assumption_count=len(regularities),
        input_regularity_fact_count=len(known_nonzero_conditions),
        discharged_regularity_count=len(discharged),
        open_regularity_count=len(open_regularities),
        discharged_regularity_obligations=discharged,
        open_regularity_obligations=open_regularities,
        eligible_certificate_count=len(eligible),
        oversized_certificate_count=len(oversized),
        expanded_micro_certificate_count=len(expanded_micro),
        skipped_micro_certificate_count=skipped_micro,
        content_addressed_fallback_certificate_count=len(
            content_addressed_fallback
        ),
        accepted_certificate_count=len(coordination.certificates),
        rejected_certificate_count=len(coordination.rejected),
        transported_polynomial_count=sum(
            item.conclusion.canonical() in coordination.accepted_facts
            for item in forward
            if item in eligible
        ),
        proof_depth=len(proof),
        goal_certificate_available=result.conditional_goal_proved,
        conditional_goal_solved=conditional,
        conditional_goal_replayed=conditional,
        input_conditioned_goal_solved=conditional and not open_regularities,
        unconditional_goal_solved=conditional and not regularities,
    )
