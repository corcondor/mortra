"""Synthesize and replay short exact proof programs from primitive laws.

This module does not dispatch on a problem identifier or a named theorem
family.  It parses the current closed inequality, enumerates well-typed
primitive transformations, and accepts a program only after replaying every
side condition with exact SymPy arithmetic.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable

import sympy as sp
from sympy.parsing.latex import parse_latex


@dataclass(frozen=True)
class PrimitiveProofStep:
    rule: str
    before_lhs: sp.Expr
    before_rhs: sp.Expr
    after_lhs: sp.Expr | None = None
    after_rhs: sp.Expr | None = None
    parameter: int | None = None
    witness: sp.Expr | None = None

    def record(self) -> dict[str, Any]:
        record: dict[str, Any] = {
            "rule": self.rule,
            "before": sp.latex(sp.Lt(self.before_lhs, self.before_rhs)),
        }
        if self.after_lhs is not None and self.after_rhs is not None:
            record["after"] = sp.latex(sp.Lt(self.after_lhs, self.after_rhs))
        if self.parameter is not None:
            record["parameter"] = self.parameter
        if self.witness is not None:
            record["witness"] = sp.latex(self.witness)
        return record


@dataclass(frozen=True)
class SynthesizedInequalityProof:
    original_lhs: sp.Expr
    original_rhs: sp.Expr
    steps: tuple[PrimitiveProofStep, ...]
    hypotheses_evaluated: int
    max_depth: int

    @property
    def proof_program(self) -> tuple[dict[str, Any], ...]:
        return tuple(step.record() for step in self.steps)


@dataclass(frozen=True)
class _SearchNode:
    lhs: sp.Expr
    rhs: sp.Expr
    steps: tuple[PrimitiveProofStep, ...]


def _normalise_latex(source: str) -> str:
    value = source.replace("−", "-").replace(r"\displaystyle", "")
    # SymPy's LaTeX parser requires braces here, while ordinary mathematical
    # writing often uses the equivalent short form ``\sqrt2``.
    return re.sub(r"\\sqrt\s*([0-9]+)", r"\\sqrt{\1}", value)


def _canonical_constants(expression: sp.Basic) -> sp.Basic:
    substitutions = {
        symbol: sp.E
        for symbol in expression.free_symbols
        if symbol.name == "e"
    }
    return expression.xreplace(substitutions)


def parse_closed_strict_inequality(
    math_chunks: Iterable[str],
) -> tuple[sp.Expr, sp.Expr] | None:
    """Return ``lhs < rhs`` for one variable-free strict inequality."""

    candidates = [
        chunk
        for chunk in math_chunks
        if any(marker in chunk for marker in ("<", ">"))
    ]
    if len(candidates) != 1:
        return None
    try:
        relation = parse_latex(_normalise_latex(candidates[0]))
    except Exception:
        return None
    if isinstance(relation, sp.StrictGreaterThan):
        lhs, rhs = relation.rhs, relation.lhs
    elif isinstance(relation, sp.StrictLessThan):
        lhs, rhs = relation.lhs, relation.rhs
    else:
        return None
    lhs = sp.sympify(_canonical_constants(lhs))
    rhs = sp.sympify(_canonical_constants(rhs))
    if lhs.free_symbols or rhs.free_symbols:
        return None
    return lhs, rhs


def _is_positive(expression: sp.Expr) -> bool:
    value = sp.simplify(expression)
    if value.is_positive is True:
        return True
    if value.is_nonpositive is True:
        return False
    try:
        return sp.ask(sp.Q.positive(value)) is True
    except (TypeError, ValueError):
        return False


def _is_nonnegative(expression: sp.Expr) -> bool:
    value = sp.simplify(expression)
    if value.is_nonnegative is True:
        return True
    try:
        return sp.ask(sp.Q.nonnegative(value)) is True
    except (TypeError, ValueError):
        return False


def _is_algebraic_expression(expression: sp.Expr) -> bool:
    return not expression.has(sp.exp, sp.E, sp.pi, sp.log)


def _normalise_exponential(expression: sp.Expr) -> sp.Expr:
    return expression


def _exponential_argument(expression: sp.Expr) -> sp.Expr | None:
    if expression == sp.E:
        return sp.Integer(1)
    if expression.func == sp.exp:
        return expression.args[0]
    return None


def _taylor_partial(argument: sp.Expr, order: int) -> sp.Expr:
    return sp.factor(sum(argument**index / sp.factorial(index) for index in range(order + 1)))


def _taylor_upper(argument: sp.Expr, order: int) -> sp.Expr | None:
    ratio = sp.factor(argument / (order + 2))
    if not _is_positive(1 - ratio):
        return None
    partial = _taylor_partial(argument, order)
    tail = argument ** (order + 1) / sp.factorial(order + 1) / (1 - ratio)
    return sp.factor(partial + tail)


def _step_key(lhs: sp.Expr, rhs: sp.Expr) -> str:
    return f"{sp.srepr(sp.factor(lhs))}\0{sp.srepr(sp.factor(rhs))}"


def _close_with_taylor(
    node: _SearchNode,
    *,
    max_order: int,
) -> tuple[tuple[PrimitiveProofStep, ...] | None, int]:
    lhs = _normalise_exponential(node.lhs)
    rhs = _normalise_exponential(node.rhs)
    tested = 0

    rhs_exponent = _exponential_argument(rhs)
    lhs_exponent = _exponential_argument(lhs)
    if rhs_exponent is not None and _is_algebraic_expression(lhs):
        argument = rhs_exponent
        if _is_positive(argument):
            for order in range(max_order + 1):
                tested += 1
                partial = _taylor_partial(argument, order)
                if not _is_positive(partial - lhs):
                    continue
                return node.steps + (
                    PrimitiveProofStep(
                        "exponential_taylor_lower",
                        lhs,
                        rhs,
                        parameter=order,
                        witness=partial,
                    ),
                    PrimitiveProofStep(
                        "exact_algebraic_sign",
                        lhs,
                        partial,
                        witness=sp.factor(partial - lhs),
                    ),
                    PrimitiveProofStep(
                        "strict_transitivity",
                        lhs,
                        rhs,
                        witness=partial,
                    ),
                ), tested

    if lhs_exponent is not None and _is_algebraic_expression(rhs):
        argument = lhs_exponent
        if _is_nonnegative(argument):
            for order in range(max_order + 1):
                tested += 1
                upper = _taylor_upper(argument, order)
                if upper is None or not _is_positive(rhs - upper):
                    continue
                return node.steps + (
                    PrimitiveProofStep(
                        "exponential_taylor_upper",
                        lhs,
                        rhs,
                        parameter=order,
                        witness=upper,
                    ),
                    PrimitiveProofStep(
                        "exact_algebraic_sign",
                        upper,
                        rhs,
                        witness=sp.factor(rhs - upper),
                    ),
                    PrimitiveProofStep(
                        "strict_transitivity",
                        lhs,
                        rhs,
                        witness=upper,
                    ),
                ), tested
    return None, tested


def synthesize_closed_inequality_proof(
    lhs: sp.Expr,
    rhs: sp.Expr,
    *,
    max_depth: int = 5,
    max_taylor_order: int = 24,
) -> SynthesizedInequalityProof | None:
    """Enumerate a short proof program and replay it before returning."""

    lhs = _normalise_exponential(lhs)
    rhs = _normalise_exponential(rhs)
    queue = [_SearchNode(lhs, rhs, ())]
    seen = {_step_key(lhs, rhs)}
    hypotheses_evaluated = 0

    while queue:
        node = queue.pop(0)
        hypotheses_evaluated += 1
        if _is_algebraic_expression(node.lhs) and _is_algebraic_expression(node.rhs):
            if _is_positive(node.rhs - node.lhs):
                steps = node.steps + (
                    PrimitiveProofStep(
                        "exact_algebraic_sign",
                        node.lhs,
                        node.rhs,
                        witness=sp.factor(node.rhs - node.lhs),
                    ),
                )
                proof = SynthesizedInequalityProof(lhs, rhs, steps, hypotheses_evaluated, max_depth)
                return proof if replay_inequality_proof(proof) else None

        closed, tested = _close_with_taylor(node, max_order=max_taylor_order)
        hypotheses_evaluated += tested
        if closed is not None:
            proof = SynthesizedInequalityProof(lhs, rhs, closed, hypotheses_evaluated, max_depth)
            return proof if replay_inequality_proof(proof) else None

        if len(node.steps) >= max_depth:
            continue

        next_nodes: list[_SearchNode] = []
        left_exponential_argument = _exponential_argument(node.lhs)
        right_exponential_argument = _exponential_argument(node.rhs)
        if left_exponential_argument is not None and right_exponential_argument is not None:
            next_nodes.append(_SearchNode(
                left_exponential_argument,
                right_exponential_argument,
                node.steps + (
                    PrimitiveProofStep(
                        "exponential_monotonicity",
                        node.lhs,
                        node.rhs,
                        left_exponential_argument,
                        right_exponential_argument,
                    ),
                ),
            ))

        if node.lhs.is_Pow and right_exponential_argument is not None:
            base, exponent = node.lhs.as_base_exp()
            if _is_positive(base) and _is_positive(exponent):
                transformed_rhs = sp.exp(sp.factor(right_exponential_argument / exponent))
                next_nodes.append(_SearchNode(
                    base,
                    transformed_rhs,
                    node.steps + (
                        PrimitiveProofStep(
                            "positive_power_root_monotonicity",
                            node.lhs,
                            node.rhs,
                            base,
                            transformed_rhs,
                            witness=exponent,
                        ),
                    ),
                ))

        if node.lhs.is_Pow and node.rhs.is_Pow:
            left_base, left_exponent = node.lhs.as_base_exp()
            right_base, right_exponent = node.rhs.as_base_exp()
            if (
                sp.simplify(left_exponent - right_exponent) == 0
                and _is_positive(left_base)
                and _is_positive(right_base)
                and _is_positive(left_exponent)
            ):
                next_nodes.append(_SearchNode(
                    left_base,
                    right_base,
                    node.steps + (
                        PrimitiveProofStep(
                            "common_positive_power_monotonicity",
                            node.lhs,
                            node.rhs,
                            left_base,
                            right_base,
                            witness=left_exponent,
                        ),
                    ),
                ))

        for candidate in next_nodes:
            key = _step_key(candidate.lhs, candidate.rhs)
            if key in seen:
                continue
            seen.add(key)
            queue.append(candidate)
    return None


def replay_inequality_proof(proof: SynthesizedInequalityProof) -> bool:
    """Independently replay every primitive contract in a synthesized program."""

    current_lhs = proof.original_lhs
    current_rhs = proof.original_rhs
    certified_comparisons: list[tuple[sp.Expr, sp.Expr]] = []
    for step in proof.steps:
        rule = step.rule
        if rule in {
            "positive_power_root_monotonicity",
            "common_positive_power_monotonicity",
            "exponential_monotonicity",
        }:
            if sp.simplify(step.before_lhs - current_lhs) != 0 or sp.simplify(step.before_rhs - current_rhs) != 0:
                return False
            if step.after_lhs is None or step.after_rhs is None:
                return False
            if rule == "positive_power_root_monotonicity":
                current_exponent = _exponential_argument(current_rhs)
                if not current_lhs.is_Pow or current_exponent is None:
                    return False
                base, exponent = current_lhs.as_base_exp()
                expected_rhs = sp.exp(sp.factor(current_exponent / exponent))
                if not _is_positive(base) or not _is_positive(exponent):
                    return False
                if sp.simplify(step.after_lhs - base) != 0 or sp.simplify(step.after_rhs - expected_rhs) != 0:
                    return False
            elif rule == "common_positive_power_monotonicity":
                if not current_lhs.is_Pow or not current_rhs.is_Pow:
                    return False
                left_base, left_exponent = current_lhs.as_base_exp()
                right_base, right_exponent = current_rhs.as_base_exp()
                if sp.simplify(left_exponent - right_exponent) != 0 or not _is_positive(left_exponent):
                    return False
                if not _is_positive(left_base) or not _is_positive(right_base):
                    return False
                if sp.simplify(step.after_lhs - left_base) != 0 or sp.simplify(step.after_rhs - right_base) != 0:
                    return False
            else:
                left_exponent = _exponential_argument(current_lhs)
                right_exponent = _exponential_argument(current_rhs)
                if left_exponent is None or right_exponent is None:
                    return False
                if sp.simplify(step.after_lhs - left_exponent) != 0:
                    return False
                if sp.simplify(step.after_rhs - right_exponent) != 0:
                    return False
            current_lhs, current_rhs = step.after_lhs, step.after_rhs
            continue

        if rule == "exponential_taylor_lower":
            argument = _exponential_argument(current_rhs)
            if argument is None or step.parameter is None or step.witness is None:
                return False
            if not _is_positive(argument):
                return False
            partial = _taylor_partial(argument, step.parameter)
            if sp.simplify(step.witness - partial) != 0:
                return False
            certified_comparisons.append((partial, current_rhs))
            continue

        if rule == "exponential_taylor_upper":
            argument = _exponential_argument(current_lhs)
            if argument is None or step.parameter is None or step.witness is None:
                return False
            if not _is_nonnegative(argument):
                return False
            upper = _taylor_upper(argument, step.parameter)
            if upper is None or sp.simplify(step.witness - upper) != 0:
                return False
            certified_comparisons.append((current_lhs, upper))
            continue

        if rule == "exact_algebraic_sign":
            if not _is_algebraic_expression(step.before_lhs) or not _is_algebraic_expression(step.before_rhs):
                return False
            if not _is_positive(step.before_rhs - step.before_lhs):
                return False
            certified_comparisons.append((step.before_lhs, step.before_rhs))
            continue

        if rule == "strict_transitivity":
            if step.witness is None:
                return False
            middle = step.witness
            left_certified = any(
                sp.simplify(left - current_lhs) == 0 and sp.simplify(right - middle) == 0
                for left, right in certified_comparisons
            )
            right_certified = any(
                sp.simplify(left - middle) == 0 and sp.simplify(right - current_rhs) == 0
                for left, right in certified_comparisons
            )
            if not left_certified or not right_certified:
                return False
            continue
        return False
    return bool(proof.steps)


def proof_derivation_tex(proof: SynthesizedInequalityProof) -> tuple[str, ...]:
    lines: list[str] = []
    for step in proof.steps:
        if step.rule == "positive_power_root_monotonicity":
            lines.append(
                rf"正の数に対する正の累乗は大小関係を保つ。したがって "
                rf"\({sp.latex(sp.Lt(step.before_lhs, step.before_rhs))}\) は "
                rf"\({sp.latex(sp.Lt(step.after_lhs, step.after_rhs))}\) と同値である。"
            )
        elif step.rule == "common_positive_power_monotonicity":
            lines.append(
                rf"両辺は同じ正の指数で累乗されているので、"
                rf"\({sp.latex(sp.Lt(step.after_lhs, step.after_rhs))}\) を示せば十分である。"
            )
        elif step.rule == "exponential_monotonicity":
            lines.append(
                rf"指数関数は単調増加であるから、"
                rf"\({sp.latex(sp.Lt(step.after_lhs, step.after_rhs))}\) を示せばよい。"
            )
        elif step.rule == "exponential_taylor_lower":
            argument = _exponential_argument(step.before_rhs)
            if argument is None:
                continue
            lines.append(
                rf"\(x={sp.latex(argument)}>0\) とする。指数関数の級数の各項は正なので、"
                rf"\(e^x>{sp.latex(step.witness)}\) である。"
            )
        elif step.rule == "exponential_taylor_upper":
            lines.append(
                rf"指数関数の級数を第{step.parameter}項まで取り、残りを等比級数で上から抑えると、"
                rf"\({sp.latex(step.before_lhs)}<{sp.latex(step.witness)}\) を得る。"
            )
        elif step.rule == "exact_algebraic_sign":
            lines.append(
                rf"差は \({sp.latex(step.witness)}>0\) である。したがって "
                rf"\({sp.latex(sp.Lt(step.before_lhs, step.before_rhs))}\) が成り立つ。"
            )
        elif step.rule == "strict_transitivity":
            lines.append(
                rf"以上の二つの不等式をつなぐと、"
                rf"\({sp.latex(sp.Lt(step.before_lhs, step.before_rhs))}\) を得る。"
            )
    return tuple(lines)
