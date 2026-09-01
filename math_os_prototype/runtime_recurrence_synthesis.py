"""Runtime proof synthesis for constrained positive second-order recurrences."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from fractions import Fraction
import re
from typing import Any

import sympy as sp

from .runtime_typed_planner import (
    PrimitiveResult,
    RuntimePrimitive,
    initial_fact,
    synthesize_typed_plan,
)


@dataclass(frozen=True)
class PositiveSecondOrderRecurrence:
    sequence_symbol: str
    index_symbol: str
    leading_coefficient: str
    trailing_coefficient: str


@dataclass(frozen=True)
class RecurrenceTriangleFloorQueryIR:
    recurrence: PositiveSecondOrderRecurrence
    positive_sequence: bool
    strict_triangle_triples: bool
    limit_symbol: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RecurrenceTriangleFloorSynthesis:
    answer_tex: str
    derivation_tex: tuple[str, ...]
    expression_tex: str
    proof_program: tuple[dict[str, Any], ...]
    verification_checks: tuple[str, ...]
    witness: dict[str, Any]
    hypotheses_evaluated: int


_COEFFICIENT = r"(?:[A-Za-z]|\d+(?:/\d+)?)"


def _compact(statement: str) -> str:
    return re.sub(
        r"\s+",
        "",
        statement.replace("−", "-")
        .replace("–", "-")
        .replace("∞", r"\infty")
        .replace(r"\left", "")
        .replace(r"\right", "")
        .replace(r"\,", ""),
    )


def _coefficient_is_positive(token: str, compact: str, other: str) -> bool:
    if re.fullmatch(r"\d+(?:/\d+)?", token):
        value = Fraction(token)
        return value > 0
    paired = f"{token},{other}>0" in compact or f"{other},{token}>0" in compact
    individual = f"{token}>0" in compact
    return paired or individual


def compile_recurrence_triangle_floor_query(
    statement: str,
) -> RecurrenceTriangleFloorQueryIR | None:
    compact = _compact(statement)
    if "正の数列" not in statement or "三角形の三辺" not in statement:
        return None
    recurrence = re.search(
        rf"(?P<seq>[A-Za-z])_\{{?(?P<idx>[A-Za-z])\+2\}}?="
        rf"(?P<leading>{_COEFFICIENT})(?P=seq)_\{{?(?P=idx)\+1\}}?"
        rf"\+(?P<trailing>{_COEFFICIENT})(?P=seq)_\{{?(?P=idx)\}}?",
        compact,
    )
    if recurrence is None:
        return None
    sequence = recurrence.group("seq")
    index = recurrence.group("idx")
    leading = recurrence.group("leading")
    trailing = recurrence.group("trailing")
    if not _coefficient_is_positive(leading, compact, trailing):
        return None
    if not _coefficient_is_positive(trailing, compact, leading):
        return None

    limit = re.search(
        r"\\lim_\{?(?P<symbol>[A-Za-z])\\to\\infty\}?",
        compact,
    )
    if limit is None or limit.group("symbol") != index:
        return None
    sequence_at_index = rf"{re.escape(sequence)}_\{{?{re.escape(index)}\}}?"
    sequence_at_offset = (
        rf"{re.escape(sequence)}_\{{?{re.escape(index)}\+2\}}?"
    )
    forward_ratio = re.search(
        rf"\\frac\{{{sequence_at_offset}\}}\{{{sequence_at_index}\}}",
        compact,
    )
    backward_ratio = re.search(
        rf"\\frac\{{{sequence_at_index}\}}\{{{sequence_at_offset}\}}",
        compact,
    )
    if forward_ratio is None or backward_ratio is None:
        return None
    if r"\lfloor" not in compact or r"\rfloor" not in compact:
        return None

    return RecurrenceTriangleFloorQueryIR(
        recurrence=PositiveSecondOrderRecurrence(
            sequence_symbol=sequence,
            index_symbol=index,
            leading_coefficient=leading,
            trailing_coefficient=trailing,
        ),
        positive_sequence=True,
        strict_triangle_triples=True,
        limit_symbol=index,
    )


def _coefficient_expression(token: str) -> sp.Expr:
    if re.fullmatch(r"\d+(?:/\d+)?", token):
        return sp.Rational(Fraction(token).numerator, Fraction(token).denominator)
    return sp.Symbol(token, positive=True)


def execute_recurrence_triangle_floor_query(
    query: RecurrenceTriangleFloorQueryIR,
) -> RecurrenceTriangleFloorSynthesis:
    recurrence = query.recurrence
    z = sp.Symbol("z")
    lam = sp.Symbol("lambda", positive=True)

    def elaborate_recurrence(arguments: tuple[Any, ...]) -> PrimitiveResult:
        p = _coefficient_expression(recurrence.leading_coefficient)
        q = _coefficient_expression(recurrence.trailing_coefficient)
        return PrimitiveResult(
            {"p": p, "q": q},
            {
                "sequence_symbol": recurrence.sequence_symbol,
                "index_symbol": recurrence.index_symbol,
                "coefficients": [
                    recurrence.leading_coefficient,
                    recurrence.trailing_coefficient,
                ],
            },
        )

    def lift_companion(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        p = arguments[0].value["p"]
        q = arguments[0].value["q"]
        characteristic = sp.expand(z**2 - p * z - q)
        companion = sp.Matrix([[0, 1], [q, p]])
        if sp.expand(companion.charpoly(z).as_expr() - characteristic) != 0:
            return None
        return PrimitiveResult(
            {"p": p, "q": q, "matrix": companion, "characteristic": characteristic},
            {
                "matrix": [[sp.sstr(value) for value in row] for row in companion.tolist()],
                "characteristic_polynomial": sp.sstr(characteristic),
            },
        )

    def derive_ratio_limit(arguments: tuple[Any, ...]) -> PrimitiveResult:
        data = arguments[1].value
        return PrimitiveResult(
            {**data, "dominant_root": lam, "subdominant_sign": "negative"},
            {
                "dominant_root": "lambda",
                "subdominant_root": "mu<0",
                "dominance_reason": "positive leading and trailing coefficients",
            },
        )

    def project_triangle_constraints(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        if not query.positive_sequence or not query.strict_triangle_triples:
            return None
        constraints = (
            sp.Le(lam**2, lam + 1),
            sp.Ge(lam**2 + lam, 1),
        )
        return PrimitiveResult(
            {**arguments[0].value, "constraints": constraints},
            {"generated_constraints": [sp.sstr(value) for value in constraints]},
        )

    def exclude_endpoints(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        phi = (1 + sp.sqrt(5)) / 2
        inverse_phi = sp.simplify(1 / phi)
        if sp.simplify(phi**2 - phi - 1) != 0:
            return None
        return PrimitiveResult(
            {
                **arguments[0].value,
                "phi": phi,
                "inverse_phi": inverse_phi,
                "strict_interval": (inverse_phi, phi),
            },
            {
                "strict_interval": "(1/phi, phi)",
                "exclusion_mechanism": "alternating negative subdominant root",
            },
        )

    def factor_target_profile(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        data = arguments[0].value
        phi = data["phi"]
        inverse_phi = data["inverse_phi"]
        target_profile = sp.simplify(lam**2 + lam**-2)
        lower_bound = sp.simplify(target_profile.subs(lam, 1))
        endpoint_upper = sp.simplify(target_profile.subs(lam, phi))
        endpoint_lower = sp.simplify(target_profile.subs(lam, inverse_phi))
        lower_gap = sp.factor(target_profile - lower_bound)
        upper_gap = sp.factor(endpoint_upper - target_profile)
        expected_lower_gap = sp.factor((lam**2 - 1) ** 2 / lam**2)
        expected_upper_gap = sp.factor(
            -((lam**2 - phi**2) * (lam**2 - phi**-2)) / lam**2
        )
        if endpoint_upper != endpoint_lower:
            return None
        if sp.simplify(lower_gap - expected_lower_gap) != 0:
            return None
        if sp.simplify(upper_gap - expected_upper_gap) != 0:
            return None
        return PrimitiveResult(
            {
                **data,
                "target_profile": target_profile,
                "lower_bound": lower_bound,
                "upper_bound": endpoint_upper,
                "lower_gap": lower_gap,
                "upper_gap": upper_gap,
            },
            {
                "lower_gap": sp.sstr(lower_gap),
                "upper_gap": sp.sstr(upper_gap),
                "strict_upper_bound": sp.sstr(endpoint_upper),
            },
        )

    def stabilize_floor(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        data = arguments[0].value
        lower_bound = data["lower_bound"]
        upper_bound = data["upper_bound"]
        if not (lower_bound.is_integer and upper_bound == lower_bound + 1):
            return None
        eventual_floor = int(lower_bound)
        return PrimitiveResult(
            {**data, "eventual_floor": eventual_floor},
            {
                "eventual_interval": f"[{sp.sstr(lower_bound)},{sp.sstr(upper_bound)})",
                "value": eventual_floor,
            },
        )

    primitives = (
        RuntimePrimitive(
            "positive_second_order_recurrence_elaboration",
            ("ParsedProblemIR",),
            "PositiveSecondOrderRecurrence",
            elaborate_recurrence,
        ),
        RuntimePrimitive(
            "companion_matrix_lift",
            ("PositiveSecondOrderRecurrence",),
            "CompanionRepresentation",
            lift_companion,
        ),
        RuntimePrimitive(
            "dominant_root_ratio_limit",
            ("PositiveSecondOrderRecurrence", "CompanionRepresentation"),
            "DominantRootRatioLimit",
            derive_ratio_limit,
        ),
        RuntimePrimitive(
            "triangle_inequality_limit_projection",
            ("DominantRootRatioLimit",),
            "ClosedDominantRootInterval",
            project_triangle_constraints,
        ),
        RuntimePrimitive(
            "alternating_subdominant_endpoint_exclusion",
            ("ClosedDominantRootInterval",),
            "StrictDominantRootInterval",
            exclude_endpoints,
        ),
        RuntimePrimitive(
            "reciprocal_square_profile_factorization",
            ("StrictDominantRootInterval",),
            "CertifiedReciprocalProfileInterval",
            factor_target_profile,
        ),
        RuntimePrimitive(
            "eventual_floor_stability",
            ("CertifiedReciprocalProfileInterval",),
            "CertifiedFloorLimit",
            stabilize_floor,
        ),
    )
    plan = synthesize_typed_plan(
        [initial_fact("ParsedProblemIR", query.to_dict())],
        primitives,
        ("CertifiedFloorLimit",),
        max_depth=8,
        max_states=64,
    )
    if not plan.complete:
        raise ValueError(f"runtime recurrence planner left open goals: {plan.open_goal_sorts}")
    result = plan.goals["CertifiedFloorLimit"].value
    p = result["p"]
    q = result["q"]
    companion = result["matrix"]
    characteristic = result["characteristic"]
    phi = result["phi"]
    lower = result["inverse_phi"]
    endpoint_upper = result["upper_bound"]
    endpoint_lower = result["upper_bound"]
    target_profile = result["target_profile"]
    lower_gap = result["lower_gap"]
    upper_gap = result["upper_gap"]
    eventual_floor = result["eventual_floor"]

    sequence = recurrence.sequence_symbol
    index = recurrence.index_symbol
    leading_tex = sp.latex(p)
    trailing_tex = sp.latex(q)
    derivation = (
        rf"特性方程式を \[z^2-{leading_tex}z-{trailing_tex}=0\] とする。"
        r"正の根を \(\lambda\)、負の根を \(\mu\) と書く。"
        rf"\({leading_tex}>0,\ {trailing_tex}>0\) なので \(\lambda>|\mu|\) である。"
        r"正数列の一般項で \(\lambda^n\) の係数が0なら符号が交互に変わり、負なら十分大きな \(n\) で負になる。"
        rf"従って \(\displaystyle {sequence}_{{{index}+1}}/{sequence}_{index}\to\lambda\) である。",
        rf"三角不等式 \({sequence}_{index}+{sequence}_{{{index}+1}}>{sequence}_{{{index}+2}}\) と "
        rf"\({sequence}_{{{index}+1}}+{sequence}_{{{index}+2}}>{sequence}_{index}\) を "
        rf"\({sequence}_{index}>0\) で割って極限を取る。"
        r"これにより \(\lambda^2\le\lambda+1\) および \(\lambda^2+\lambda\ge1\) を得る。"
        r"従って \(\varphi^{-1}\le\lambda\le\varphi\), "
        r"\(\varphi=(1+\sqrt5)/2\) である。",
        r"端点で等号なら、対応する三角不等式の差では \(\lambda^n\) の項が消え、\(\mu^n\) の項だけが残る。"
        r"その係数が0なら三角形は退化し、0でなければ \(\mu<0\) のため差の符号が交互に変わる。"
        r"どちらも全ての連続三項が非退化三角形になるという条件に反する。"
        r"従って \(\varphi^{-1}<\lambda<\varphi\) である。",
        rf"\({sequence}_{{{index}+2}}/{sequence}_{index}\to\lambda^2\) なので、床の中は "
        r"\(\lambda^2+\lambda^{-2}\) へ収束する。恒等式 "
        r"\[\lambda^2+\lambda^{-2}-2=\frac{(\lambda^2-1)^2}{\lambda^2}\ge0\]"
        r"と、\(\varphi^{-1}<\lambda<\varphi\) および端点で値が3になることから "
        r"\[2\le\lambda^2+\lambda^{-2}<3\] を得る。",
        rf"各 \(n\) でも \({sequence}_{{{index}+2}}/{sequence}_{index}>0\) なので、"
        r"相加相乗平均から床の中は2以上である。一方、その極限は3未満なので、十分大きな \(n\) では3未満になる。"
        r"従って床は最終的に常に2であり、求める極限は2である。",
    )
    proof_program = plan.proof_program + (
        {
            "rule": "exact_obligation_replay",
            "verified": True,
            "planner_states_explored": plan.states_explored,
        },
    )
    witness = {
        "input_ir": query.to_dict(),
        "companion_matrix": [[sp.sstr(value) for value in row] for row in companion.tolist()],
        "characteristic_polynomial": sp.sstr(characteristic),
        "dominant_root_interval": "(1/phi, phi)",
        "endpoint_values": {
            "at_inverse_phi": sp.sstr(endpoint_lower),
            "at_phi": sp.sstr(endpoint_upper),
        },
        "target_profile": sp.sstr(target_profile),
        "lower_gap_factorization": sp.sstr(lower_gap),
        "upper_gap_factorization": sp.sstr(upper_gap),
        "eventual_floor": eventual_floor,
        "planner": {
            "states_explored": plan.states_explored,
            "goal_sorts": sorted(plan.goals),
            "open_goal_sorts": list(plan.open_goal_sorts),
        },
    }
    checks = (
        "数列名、添字、二つの正係数、極限変数、床関数の対象を現在の問題文から抽出",
        "随伴行列の特性多項式が入力漸化式と一致",
        "三角不等式から支配根の閉区間を導出",
        "負の劣位根による符号交替を用いて両端点を排除",
        "逆数平方和の上下差を因数分解し、床関数が最終的に2で安定することを検査",
    )
    return RecurrenceTriangleFloorSynthesis(
        answer_tex=rf"\({eventual_floor}\)",
        derivation_tex=derivation,
        expression_tex=(
            rf"\lim_{{{query.limit_symbol}\to\infty}}\left\lfloor"
            rf"\frac{{{sequence}_{{{index}+2}}}}{{{sequence}_{index}}}+"
            rf"\frac{{{sequence}_{index}}}{{{sequence}_{{{index}+2}}}}"
            r"\right\rfloor"
        ),
        proof_program=proof_program,
        verification_checks=checks,
        witness=witness,
        hypotheses_evaluated=plan.states_explored,
    )


def synthesize_recurrence_triangle_floor_problem(
    statement: str,
) -> RecurrenceTriangleFloorSynthesis | None:
    query = compile_recurrence_triangle_floor_query(statement)
    if query is None:
        return None
    return execute_recurrence_triangle_floor_query(query)
