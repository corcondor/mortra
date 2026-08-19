"""Verify parsed solution steps with symbolic and experimental tools."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from itertools import product
from typing import Any

try:
    import sympy as sp
except ImportError:  # pragma: no cover
    sp = None

try:
    from math_os_prototype.solution_step_parser import ParsedSolution, SolutionStep
    from math_os_prototype.tool_adapters import WolframAdapter
except ImportError:
    from solution_step_parser import ParsedSolution, SolutionStep
    from tool_adapters import WolframAdapter


@dataclass
class StepVerification:
    step_id: str
    status: str
    method: str
    checks: list[str]
    warnings: list[str]
    result: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VerifiedSolution:
    source_url: str
    answer_id: int | None
    status: str
    verified_steps: int
    total_steps: int
    step_results: list[StepVerification]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class StepVerifier:
    def __init__(self, *, external_tools: bool = False):
        self.external_tools = external_tools

    def verify_solution(self, parsed: ParsedSolution) -> VerifiedSolution:
        results = [self.verify_step(step) for step in parsed.steps]
        verified_count = sum(1 for item in results if item.status in {"verified", "sanity_checked"})
        if verified_count == len(results) and results:
            status = "verified_or_sanity_checked"
        elif verified_count:
            status = "partially_verified"
        else:
            status = "unverified"
        return VerifiedSolution(
            source_url=parsed.source_url,
            answer_id=parsed.answer_id,
            status=status,
            verified_steps=verified_count,
            total_steps=len(results),
            step_results=results,
        )

    def verify_step(self, step: SolutionStep) -> StepVerification:
        if step.relations:
            relation_results = [verify_relation_with_sympy(relation) for relation in step.relations[:3]]
            if any(item.get("status") == "identity_verified" for item in relation_results):
                return StepVerification(
                    step_id=step.id,
                    status="verified",
                    method="sympy_identity",
                    checks=["At least one relation simplified to an identity."],
                    warnings=[],
                    result={"relations": relation_results},
                )
            if any(item.get("status") == "no_small_counterexample" for item in relation_results):
                return StepVerification(
                    step_id=step.id,
                    status="sanity_checked",
                    method="small_integer_sampling",
                    checks=["No small counterexample was found for a relation."],
                    warnings=["Sampling is not a proof."],
                    result={"relations": relation_results},
                )
            wolfram_result = self.verify_with_wolfram(step.relations[0])
            if wolfram_result.get("status") == "executed":
                return StepVerification(
                    step_id=step.id,
                    status="sanity_checked",
                    method="wolfram_fullsimplify",
                    checks=["Wolfram returned a result for the relation."],
                    warnings=["Result still needs theorem-level interpretation."],
                    result=wolfram_result,
                )
            return StepVerification(
                step_id=step.id,
                status="planned",
                method="relation_parse",
                checks=[],
                warnings=["Relations were parsed but not verified."],
                result={"relations": relation_results, "wolfram": wolfram_result},
            )

        if step.theorem_refs:
            return StepVerification(
                step_id=step.id,
                status="planned",
                method="theorem_reference",
                checks=[],
                warnings=["Theorem reference detected; formal library lookup is not wired yet."],
                result={"theorem_refs": step.theorem_refs},
            )

        return StepVerification(
            step_id=step.id,
            status="unverified",
            method="none",
            checks=[],
            warnings=["No machine-checkable relation was extracted."],
        )

    def verify_with_wolfram(self, relation: str) -> dict[str, Any]:
        adapter = WolframAdapter(timeout_seconds=15)
        code = wolfram_fullsimplify_code(relation)
        if not self.external_tools:
            return {"status": "planned", "available": adapter.is_available(), "command": code}
        return adapter.execute_code(code, label="step_verifier").to_dict()


def verify_relation_with_sympy(relation: str) -> dict[str, Any]:
    if sp is None:
        return {"status": "unavailable"}
    parsed = split_relation(relation)
    if parsed is None:
        return {"status": "no_parse", "relation": relation}
    lhs_text, op, rhs_text = parsed
    symbols = {name: sp.symbols(name) for name in sorted(set(re.findall(r"\b[a-zA-Z]\b", relation)))}
    try:
        lhs = sp.sympify(normalize_expr(lhs_text), locals=symbols)
        rhs = sp.sympify(normalize_expr(rhs_text), locals=symbols)
    except Exception as exc:
        return {"status": "no_parse", "relation": relation, "error": str(exc)}

    if op == "=":
        diff = sp.simplify(lhs - rhs)
        if diff == 0:
            return {"status": "identity_verified", "relation": relation}
        if not symbols:
            return {"status": "false_or_unresolved", "relation": relation, "residual": str(diff)}
        return {"status": "equation_not_identity", "relation": relation, "residual": str(diff)}

    comparison = make_comparison(lhs, op, rhs)
    if comparison is None:
        return {"status": "unsupported_relation", "relation": relation}
    counterexample = find_small_counterexample(comparison, symbols)
    if counterexample is None:
        return {"status": "no_small_counterexample", "relation": relation}
    return {"status": "counterexample_found", "relation": relation, "counterexample": counterexample}


def split_relation(relation: str) -> tuple[str, str, str] | None:
    for op in ("<=", ">=", "<", ">", "="):
        if op in relation:
            lhs, rhs = relation.split(op, 1)
            return lhs.strip(), op, rhs.strip()
    return None


def make_comparison(lhs: Any, op: str, rhs: Any) -> Any:
    if op == "<=":
        return lhs <= rhs
    if op == ">=":
        return lhs >= rhs
    if op == "<":
        return lhs < rhs
    if op == ">":
        return lhs > rhs
    return None


def find_small_counterexample(comparison: Any, symbols: dict[str, Any]) -> dict[str, int] | None:
    names = list(symbols)[:4]
    if not names:
        return None if bool(comparison) else {}
    for values in product(range(-4, 5), repeat=len(names)):
        assignment = dict(zip(names, values))
        try:
            if not bool(comparison.subs({symbols[name]: value for name, value in assignment.items()})):
                return assignment
        except Exception:
            continue
    return None


def normalize_expr(expr: str) -> str:
    expr = re.sub(
        r"^\s*(we have|have|then|thus|hence|therefore|so|it follows that|we get|we obtain)\s+",
        "",
        expr,
        flags=re.IGNORECASE,
    )
    expr = expr.replace("^", "**")
    expr = expr.replace("\\sqrt", "sqrt")
    expr = re.sub(r"(?<=\d)(?=[A-Za-z])", "*", expr)
    expr = re.sub(r"(?<=[A-Za-z])(?=\d)", "*", expr)
    return expr.strip()


def wolfram_fullsimplify_code(relation: str) -> str:
    expr = relation.replace("**", "^").replace("=", "==", 1)
    return f"ToString[InputForm[FullSimplify[{expr}]]]"
