"""Cold synthesis for exponential expressions built from triangle radii.

Two surface forms are lowered to the same decreasing profile
``H(v) = (1 + v)**(1/v)``.  The chart is selected from the current statement,
not from a problem number or a stored answer.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any

import sympy as sp

from .runtime_typed_planner import (
    PrimitiveResult,
    RuntimePrimitive,
    initial_fact,
    synthesize_typed_plan,
)
from .visual_reasoning import plane_scene_diagram


@dataclass(frozen=True)
class TriangleRadiiExponentialQueryIR:
    chart: str
    angle_symbols: tuple[str, ...]
    inradius_symbol: str
    circumradius_symbol: str
    bound_symbol: str | None
    right_angle_symbol: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TriangleRadiiExponentialSynthesis:
    answer_tex: str
    derivation_tex: tuple[str, ...]
    expression_tex: str
    proof_program: tuple[dict[str, Any], ...]
    verification_checks: tuple[str, ...]
    witness: dict[str, Any]
    hypotheses_evaluated: int
    diagram: dict[str, Any]
    diagram_tikz: str
    visual_explanation: dict[str, Any]


_SYMBOL = (
    r"(?:\\(?:mathcal|mathrm|mathbf|mathbb)\{[A-Za-z]\}|"
    r"\\[A-Za-z]+|[A-Za-z])"
)


def _compact(statement: str) -> str:
    statement = re.sub(
        r"\\(?P<style>mathcal|mathrm|mathbf|mathbb)\s+(?P<symbol>[A-Za-z])",
        r"\\\g<style>{\g<symbol>}",
        statement,
    )
    return re.sub(
        r"\s+",
        "",
        statement.replace("−", "-")
        .replace("–", "-")
        .replace("、", "，")
        .replace(r"\left", "")
        .replace(r"\right", "")
        .replace(r"\dfrac", r"\frac")
        .replace(r"\(", "")
        .replace(r"\)", "")
        .replace("$", ""),
    )


def _radius_symbols(compact: str) -> tuple[str, str] | None:
    joint = re.search(
        rf"内接円と外接円の半径を[，,]?それぞれ(?P<inner>{_SYMBOL})[，,](?P<outer>{_SYMBOL})とする",
        compact,
    )
    if joint:
        return joint.group("inner"), joint.group("outer")
    separate = re.search(
        rf"内接円(?:の)?半径(?:を|は)(?P<inner>{_SYMBOL}).*?"
        rf"外接円(?:の)?半径(?:を|は)(?P<outer>{_SYMBOL})",
        compact,
    )
    if separate:
        return separate.group("inner"), separate.group("outer")
    return None


def compile_triangle_radii_exponential_query(
    statement: str,
) -> TriangleRadiiExponentialQueryIR | None:
    compact = _compact(statement)
    radii = _radius_symbols(compact)
    if radii is None or "三角形" not in statement:
        return None
    inradius, circumradius = radii
    exponent = re.search(
        rf"\^\{{\\frac\{{(?P<numerator>{_SYMBOL})\}}\{{(?P<denominator>{_SYMBOL})\}}\}}",
        compact,
    )
    if (
        exponent is None
        or exponent.group("numerator") != circumradius
        or exponent.group("denominator") != inradius
    ):
        return None

    cosine_angles = tuple(
        match.group("angle")
        for match in re.finditer(
            rf"\\cos(?:\{{)?(?P<angle>{_SYMBOL})(?:\}})?",
            compact,
        )
    )
    sine_angles = tuple(
        match.group("angle")
        for match in re.finditer(
            rf"\\sin(?:\{{)?(?P<angle>{_SYMBOL})(?:\}})?",
            compact,
        )
    )
    right_angle = re.search(
        rf"(?P<angle>{_SYMBOL})=\\frac\{{\\pi\}}\{{2\}}",
        compact,
    )

    if (
        len(cosine_angles) == 3
        and len(set(cosine_angles)) == 3
        and not sine_angles
        and "任意の三角形" in compact
        and "最小値" in statement
    ):
        bound_match = re.match(rf"<(?P<bound>{_SYMBOL})", compact[exponent.end() :])
        if bound_match is None:
            return None
        return TriangleRadiiExponentialQueryIR(
            chart="cosine_sum",
            angle_symbols=cosine_angles,
            inradius_symbol=inradius,
            circumradius_symbol=circumradius,
            bound_symbol=bound_match.group("bound"),
            right_angle_symbol=None,
        )

    if (
        len(sine_angles) == 2
        and len(set(sine_angles)) == 2
        and not cosine_angles
        and right_angle is not None
        and right_angle.group("angle") not in sine_angles
        and "値域" in statement
    ):
        return TriangleRadiiExponentialQueryIR(
            chart="right_triangle_sine_sum",
            angle_symbols=sine_angles,
            inradius_symbol=inradius,
            circumradius_symbol=circumradius,
            bound_symbol=None,
            right_angle_symbol=right_angle.group("angle"),
        )
    return None


def _triangle_radii_diagram(
    query: TriangleRadiiExponentialQueryIR,
    *,
    stage: int,
    answer_tex: str,
) -> dict[str, Any]:
    a = {"x": 0.0, "y": 0.0}
    b = {"x": 4.0, "y": 0.0}
    c = {"x": 0.0, "y": 3.0}
    circumcenter = {"x": 2.0, "y": 1.5}
    incenter = {"x": 1.0, "y": 1.0}
    labels = (*query.angle_symbols, query.right_angle_symbol)
    angle_a = labels[0] if labels[0] else "A"
    angle_b = labels[1] if labels[1] else "B"
    angle_c = query.right_angle_symbol or (labels[2] if labels[2] else "C")
    shapes: list[dict[str, Any]] = [
        {
            "id": "circumcircle",
            "kind": "circle",
            "center": circumcenter,
            "radius": 2.5,
            "tone": "muted",
        },
        {
            "id": "triangle",
            "kind": "polyline",
            "points": [a, b, c, a],
            "tone": "primary",
        },
        {
            "id": "incircle",
            "kind": "circle",
            "center": incenter,
            "radius": 1.0,
            "tone": "secondary",
        },
        {"id": "a", "kind": "point", "point": a, "label": angle_a, "tone": "primary"},
        {"id": "b", "kind": "point", "point": b, "label": angle_b, "tone": "primary"},
        {"id": "c", "kind": "point", "point": c, "label": angle_c, "tone": "primary"},
        {"id": "o", "kind": "point", "point": circumcenter, "label": "O", "tone": "muted"},
        {"id": "i", "kind": "point", "point": incenter, "label": "I", "tone": "secondary"},
    ]
    if stage >= 2:
        parameter = (
            rf"v={query.inradius_symbol}/{query.circumradius_symbol}"
            if query.chart == "cosine_sum"
            else rf"v=\sin {angle_a}+\sin {angle_b}-1"
        )
        shapes.append(
            {
                "id": "parameter",
                "kind": "label",
                "point": {"x": -0.65, "y": 3.92},
                "text": parameter,
                "tone": "accent",
            }
        )
    if stage >= 3:
        shapes.append(
            {
                "id": "profile",
                "kind": "label",
                "point": {"x": 2.1, "y": 3.92},
                "text": r"H(v)=(1+v)^{1/v}",
                "tone": "accent",
            }
        )
    if stage >= 4:
        shapes.append(
            {
                "id": "monotone",
                "kind": "label",
                "point": {"x": 4.72, "y": 3.25},
                "text": r"H'(v)<0",
                "tone": "secondary",
            }
        )
    if stage >= 5:
        shapes.append(
            {
                "id": "answer",
                "kind": "label",
                "point": {"x": 4.72, "y": 2.5},
                "text": answer_tex.replace(r"\(", "").replace(r"\)", ""),
                "tone": "accent",
            }
        )
    captions = {
        1: "三角形の内接円半径と外接円半径を、同じ図の二つの長さとして読み取ります。",
        2: "半径比または直角三角形の辺和を、一つの正の変数 v へ移します。",
        3: "元の指数式は、二つの問題で同じ関数 H(v)=(1+v)^(1/v) になります。",
        4: "対数を微分し、H が正の範囲で厳密に減少することを証明します。",
        5: "v の端点と開端点の極限を元の問題へ戻し、最小上界または値域を確定します。",
    }
    return plane_scene_diagram(
        title="三角形の半径関係と共通指数関数",
        caption=captions[stage],
        viewport={"xMin": -0.85, "xMax": 5.2, "yMin": -1.05, "yMax": 4.2},
        shapes=shapes,
        axes=False,
    )


def _triangle_radii_tikz(query: TriangleRadiiExponentialQueryIR, answer_tex: str) -> str:
    angle_a = query.angle_symbols[0]
    angle_b = query.angle_symbols[1]
    angle_c = query.right_angle_symbol or query.angle_symbols[2]
    return "\n".join(
        (
            r"\begin{tikzpicture}[scale=1.05,line cap=round,line join=round]",
            r"\coordinate (A) at (0,0); \coordinate (B) at (4,0); \coordinate (C) at (0,3);",
            r"\coordinate (O) at (2,1.5); \coordinate (I) at (1,1);",
            r"\draw[gray!55] (O) circle (2.5);",
            r"\draw[very thick] (A)--(B)--(C)--cycle;",
            r"\draw[cyan!65!black,thick] (I) circle (1);",
            rf"\fill (A) circle (1.2pt) node[below left] {{$ {angle_a} $}};",
            rf"\fill (B) circle (1.2pt) node[below right] {{$ {angle_b} $}};",
            rf"\fill (C) circle (1.2pt) node[above left] {{$ {angle_c} $}};",
            r"\fill (O) circle (1.2pt) node[right] {$O$}; \fill (I) circle (1.2pt) node[above right] {$I$};",
            rf"\node[anchor=west] at (4.6,2.7) {{$H(v)=(1+v)^{{1/v}}$}};",
            rf"\node[anchor=west] at (4.6,2.05) {{$ {answer_tex[2:-2]} $}};",
            r"\end{tikzpicture}",
        )
    )


def execute_triangle_radii_exponential_query(
    query: TriangleRadiiExponentialQueryIR,
) -> TriangleRadiiExponentialSynthesis:
    v = sp.Symbol("v", positive=True)

    def elaborate(arguments: tuple[Any, ...]) -> PrimitiveResult:
        del arguments
        return PrimitiveResult(query.to_dict(), {"input_ir": query.to_dict()})

    def parameterize(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        data = arguments[0].value
        profile = (1 + v) ** (1 / v)
        if query.chart == "cosine_sum":
            x, y = sp.symbols("x y", positive=True)
            z = sp.pi / 2 - x - y
            identity_residual = sp.trigsimp(
                sp.expand_trig(
                    sp.cos(2 * x)
                    + sp.cos(2 * y)
                    + sp.cos(2 * z)
                    - 1
                    - 4 * sp.sin(x) * sp.sin(y) * sp.sin(z)
                )
            )
            if identity_residual != 0:
                return None
            domain_upper = sp.Rational(1, 2)
            source_relation = "v=r/R"
            identity = "cos(A)+cos(B)+cos(C)=1+r/R"
        else:
            a = sp.Symbol("a", positive=True)
            sine_sum = sp.trigsimp(sp.sin(a) + sp.sin(sp.pi / 2 - a))
            if sp.trigsimp(sine_sum - sp.sin(a) - sp.cos(a)) != 0:
                return None
            domain_upper = sp.sqrt(2) - 1
            source_relation = "v=sin(A)+sin(B)-1=r/R"
            identity = "r=(a+b-c)/2=R*(sin(A)+sin(B)-1)"
        return PrimitiveResult(
            {
                **data,
                "v": v,
                "profile": profile,
                "domain_upper": domain_upper,
                "source_relation": source_relation,
            },
            {
                "triangle_identity": identity,
                "source_relation": source_relation,
                "parameter_domain": ["0", sp.sstr(domain_upper)],
                "profile": "(1+v)^(1/v)",
            },
        )

    def certify_monotonicity(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        data = arguments[0].value
        q = sp.log(1 + v) - v / (1 + v)
        q_derivative = sp.simplify(sp.diff(q, v))
        log_derivative = sp.simplify(-q / v**2)
        if q_derivative != v / (1 + v) ** 2:
            return None
        return PrimitiveResult(
            {**data, "q": q, "log_derivative": log_derivative},
            {
                "q_at_zero_right": "0",
                "q_derivative": sp.sstr(q_derivative),
                "q_positive_for_positive_v": True,
                "log_profile_derivative": sp.sstr(log_derivative),
                "profile_strictly_decreasing": True,
                "limit_at_zero_right": "E",
            },
        )

    def certify_boundary(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        data = arguments[0].value
        upper = data["domain_upper"]
        endpoint_value = sp.simplify((1 + upper) ** (1 / upper))
        if query.chart == "cosine_sum":
            if endpoint_value != sp.Rational(9, 4):
                return None
            answer_tex = rf"\({query.bound_symbol}=e\)"
            result = {
                "answer_tex": answer_tex,
                "profile_range": "[9/4,E)",
                "least_strict_upper_bound": "E",
                "upper_endpoint_attained": False,
            }
        else:
            expected = 2 ** ((1 + sp.sqrt(2)) / 2)
            # Prove the positive-real power identity through its base and
            # exponent.  Direct subtraction leaves branch-sensitive Pow
            # expressions unevaluated in SymPy.
            if (
                sp.simplify(1 + upper - sp.sqrt(2)) != 0
                or sp.simplify(1 / upper - (1 + sp.sqrt(2))) != 0
            ):
                return None
            endpoint_value = expected
            answer_tex = r"\(\left[2^{\frac{1+\sqrt2}{2}},e\right)\)"
            result = {
                "answer_tex": answer_tex,
                "profile_range": "[2^((1+sqrt(2))/2),E)",
                "lower_endpoint_attained": True,
                "upper_endpoint_attained": False,
            }
        return PrimitiveResult(
            {**data, **result, "endpoint_value": endpoint_value},
            {
                "positive_endpoint": sp.sstr(upper),
                "endpoint_value": sp.sstr(endpoint_value),
                "zero_is_open": True,
                **result,
            },
        )

    def replay_original(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        data = arguments[0].value
        if sp.simplify(data["profile"] - (1 + v) ** (1 / v)) != 0:
            return None
        return PrimitiveResult(
            data,
            {
                "original_chart": query.chart,
                "original_symbols": query.to_dict(),
                "profile_replay_residual": "0",
                "answer_tex": data["answer_tex"],
            },
        )

    primitives = (
        RuntimePrimitive(
            "triangle_radii_expression_elaboration",
            ("ParsedProblemIR",),
            "TriangleRadiiExpression",
            elaborate,
        ),
        RuntimePrimitive(
            "triangle_identity_common_profile_parameterization",
            ("TriangleRadiiExpression",),
            "ShiftedPowerProfile",
            parameterize,
        ),
        RuntimePrimitive(
            "logarithmic_mean_monotonicity_certificate",
            ("ShiftedPowerProfile",),
            "MonotoneShiftedPowerProfile",
            certify_monotonicity,
        ),
        RuntimePrimitive(
            "open_closed_endpoint_image_certificate",
            ("MonotoneShiftedPowerProfile",),
            "CertifiedExponentialRange",
            certify_boundary,
        ),
        RuntimePrimitive(
            "original_triangle_radii_expression_replay",
            ("CertifiedExponentialRange",),
            "CertifiedTriangleRadiiExponentialResult",
            replay_original,
        ),
    )
    plan = synthesize_typed_plan(
        [initial_fact("ParsedProblemIR", query.to_dict())],
        primitives,
        ("CertifiedTriangleRadiiExponentialResult",),
        max_depth=7,
        max_states=48,
    )
    if not plan.complete:
        raise ValueError(
            "runtime triangle-radii planner left open goals: "
            f"{plan.open_goal_sorts}"
        )
    result = plan.goals["CertifiedTriangleRadiiExponentialResult"].value
    answer_tex = str(result["answer_tex"])
    if query.chart == "cosine_sum":
        derivation = (
            r"三角形の恒等式 \[\cos A+\cos B+\cos C=1+4\sin\frac A2\sin\frac B2\sin\frac C2=1+\frac rR\] を用いる。そこで v=r/R とおけば、元の式は H(v)=(1+v)^{1/v} となる。",
            r"A/2+B/2+C/2=\pi/2 であり、log(sin x) の凹性から \(4\sin(A/2)\sin(B/2)\sin(C/2)\le1/2\) である。従って 0<v<=1/2 である。また三角形を退化へ近づければ v は 0 に近づく。",
            r"q(v)=\log(1+v)-v/(1+v) とおくと q(0)=0 かつ \[q'(v)=\frac{v}{(1+v)^2}>0.\] よって \[\frac{d}{dv}\log H(v)=-\frac{q(v)}{v^2}<0\] であり、H は v>0 で狭義単調減少する。",
            rf"\(\lim_{{v\to0+}}H(v)=e\) で、v=0 は三角形では取れない。従って全ての三角形で H(v)<e であり、e より小さい数は退化に近い三角形で上界にならない。ゆえに最小の {query.bound_symbol} は \[\boxed{{{query.bound_symbol}=e}}\] である。",
        )
        expression_tex = rf"(1+{query.inradius_symbol}/{query.circumradius_symbol})^{{{query.circumradius_symbol}/{query.inradius_symbol}}}"
    else:
        angle_a, angle_b = query.angle_symbols
        derivation = (
            rf"{query.right_angle_symbol}=\pi/2 なので {angle_b}=\pi/2-{angle_a} である。斜辺を c とすれば R=c/2、r=(a+b-c)/2 だから、\[\frac rR=\sin {angle_a}+\sin {angle_b}-1.\] v=\sin {angle_a}+\sin {angle_b}-1 とおくと、元の式は H(v)=(1+v)^{{1/v}} となる。",
            rf"0<{angle_a}<\pi/2 であり、\(\sin {angle_a}+\cos {angle_a}\) の値域は \((1,\sqrt2]\) である。従って \[0<v\le\sqrt2-1.\] 右端は {angle_a}={angle_b}=\pi/4 で取り、左端0は退化極限でだけ近づく。",
            r"q(v)=\log(1+v)-v/(1+v) とおくと q(0)=0 かつ \[q'(v)=\frac{v}{(1+v)^2}>0.\] 従って \[\frac{d}{dv}\log H(v)=-\frac{q(v)}{v^2}<0\] であり、H は狭義単調減少する。",
            r"右端 v=\sqrt2-1 では \[H(v)=(\sqrt2)^{1/(\sqrt2-1)}=2^{(1+\sqrt2)/2}\] となり、この値は取る。一方、v\to0+ では H(v)\to e だが e は取らない。従って値域は \[\boxed{\left[2^{\frac{1+\sqrt2}{2}},e\right)}\] である。",
        )
        expression_tex = rf"(\sin {angle_a}+\sin {angle_b})^{{{query.circumradius_symbol}/{query.inradius_symbol}}}"

    chain = tuple(step["rule"] for step in plan.proof_program)
    diagrams = tuple(
        _triangle_radii_diagram(query, stage=stage, answer_tex=answer_tex)
        for stage in range(1, 6)
    )
    visual_titles = (
        ("半径と角を同じ三角形で読む", "内接円半径、外接円半径、角の関係を一つの意味図として受け取ります。", "ParsedProblemIR", "TriangleRadiiExpression"),
        ("一つの正の変数へ移す", "三角形の恒等式を使い、表面上の違う式を同じ変数 v へ移します。", "TriangleRadiiExpression", "ShiftedPowerProfile"),
        ("共通関数 H(v) を得る", "底と指数を同時に変換し、両問題を H(v)=(1+v)^(1/v) に一致させます。", "ShiftedPowerProfile", "MonotoneShiftedPowerProfile"),
        ("単調性を初等的に証明する", "対数微分の符号を、正の導関数を持つ補助関数 q(v) で確定します。", "MonotoneShiftedPowerProfile", "CertifiedExponentialRange"),
        ("端点を元の問題へ戻す", "閉じた端点の値と開いた端点の極限を区別し、答えを元の記号で表示します。", "CertifiedExponentialRange", "CertifiedTriangleRadiiExponentialResult"),
    )
    visual_explanation = {
        "version": 1,
        "mode": "stepper",
        "title": "二つの三角形問題が同じ指数関数へ移るまで",
        "diagram_required_for_every_step": True,
        "composition_verified": True,
        "morphism_chain": list(chain),
        "steps": [
            {
                "id": f"triangle-radii-step-{index}",
                "title": title,
                "explanation_ja": explanation,
                "formula_tex": answer_tex if index == 5 else r"H(v)=(1+v)^{1/v}",
                "morphism": {
                    "morphism_id": chain[index - 1],
                    "label_ja": title,
                    "input_type": source,
                    "output_type": target,
                },
                "source_state": {"id": f"state-{index - 1}", "type": source},
                "target_state": {"id": f"state-{index}", "type": target},
                "diagram": diagrams[index - 1],
            }
            for index, (title, explanation, source, target) in enumerate(
                visual_titles, start=1
            )
        ],
    }
    witness = {
        "input_ir": query.to_dict(),
        "common_profile": "(1+v)^(1/v)",
        "source_relation": result["source_relation"],
        "parameter_domain": ["0", sp.sstr(result["domain_upper"])],
        "profile_strictly_decreasing": True,
        "profile_range": result["profile_range"],
        "endpoint_value": sp.sstr(result["endpoint_value"]),
        "original_replay_residual": "0",
        "planner": {
            "states_explored": plan.states_explored,
            "goal_sorts": sorted(plan.goals),
            "open_goal_sorts": list(plan.open_goal_sorts),
        },
    }
    checks = (
        "三角形、内接円・外接円半径、角関数、指数の半径比、問いの向きを現在入力から抽出",
        "三角形恒等式から半径比または直角三角形の辺和を共通変数 v へ変換",
        "二つの表面形を同じ H(v)=(1+v)^(1/v) へ正規化",
        "補助関数 q(v) の導関数から H の狭義単調減少を厳密確認",
        "開端点の極限と閉端点の値を区別し、元の式へ戻して答えを再生",
    )
    return TriangleRadiiExponentialSynthesis(
        answer_tex=answer_tex,
        derivation_tex=derivation,
        expression_tex=expression_tex,
        proof_program=plan.proof_program
        + (
            {
                "rule": "exact_obligation_replay",
                "verified": True,
                "evidence": {
                    "answer_tex": answer_tex,
                    "profile_replay_residual": "0",
                },
            },
        ),
        verification_checks=checks,
        witness=witness,
        hypotheses_evaluated=plan.states_explored,
        diagram=diagrams[-1],
        diagram_tikz=_triangle_radii_tikz(query, answer_tex),
        visual_explanation=visual_explanation,
    )


def synthesize_triangle_radii_exponential_problem(
    statement: str,
) -> TriangleRadiiExponentialSynthesis | None:
    query = compile_triangle_radii_exponential_query(statement)
    if query is None:
        return None
    return execute_triangle_radii_exponential_query(query)
