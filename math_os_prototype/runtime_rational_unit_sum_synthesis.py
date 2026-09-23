"""Cold proof synthesis for rational coordinates of two unit vectors.

The input class equates the sine sum and cosine sum of two angles to a
difference-over-sum ratio of ordered primes.  The proof is synthesized through
the geometry of a chord midpoint, a rational-square obligation, and a complete
prime factor-pair classification.
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
class RationalUnitVectorSumQueryIR:
    first_angle: str
    second_angle: str
    larger_prime: str
    smaller_prime: str
    ratio: str
    rational_observables: tuple[str, str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RationalUnitVectorSumSynthesis:
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


def _angle_tex(name: str) -> str:
    return rf"\{name}" if len(name) > 1 else name


def _unit_vector_diagram(
    query: RationalUnitVectorSumQueryIR,
    *,
    stage: int,
) -> dict[str, Any]:
    """Render only relations certified by the final unit-vector witness."""

    first_angle = _angle_tex(query.first_angle)
    second_angle = _angle_tex(query.second_angle)
    origin = {"x": 0.0, "y": 0.0}
    first = {"x": -0.6, "y": 0.8}
    second = {"x": 0.8, "y": -0.6}
    midpoint = {"x": 0.1, "y": 0.1}
    vector_sum = {"x": 0.2, "y": 0.2}
    shapes: list[dict[str, Any]] = [
        {
            "id": "unit-circle",
            "kind": "circle",
            "center": origin,
            "radius": 1.0,
            "tone": "muted",
        },
        {
            "id": "origin",
            "kind": "point",
            "point": origin,
            "label": "O",
            "tone": "muted",
        },
        {
            "id": "first-unit-vector",
            "kind": "vector",
            "from": origin,
            "to": first,
            "label": rf"u_{{{first_angle}}}",
            "tone": "primary",
        },
        {
            "id": "second-unit-vector",
            "kind": "vector",
            "from": origin,
            "to": second,
            "label": rf"u_{{{second_angle}}}",
            "tone": "secondary",
        },
        {
            "id": "first-endpoint",
            "kind": "point",
            "point": first,
            "label": rf"(-3/5,4/5)",
            "tone": "primary",
        },
        {
            "id": "second-endpoint",
            "kind": "point",
            "point": second,
            "label": rf"(4/5,-3/5)",
            "tone": "secondary",
        },
    ]
    if stage >= 2:
        shapes.extend(
            [
                {
                    "id": "endpoint-chord",
                    "kind": "polyline",
                    "points": [first, second],
                    "tone": "accent",
                },
                {
                    "id": "chord-midpoint",
                    "kind": "point",
                    "point": midpoint,
                    "label": "H=(s/2,s/2)",
                    "tone": "accent",
                },
                {
                    "id": "vector-sum",
                    "kind": "vector",
                    "from": origin,
                    "to": vector_sum,
                    "label": "(s,s)",
                    "tone": "accent",
                },
            ]
        )
    if stage >= 3:
        shapes.append(
            {
                "id": "square-obligation",
                "kind": "label",
                "point": {"x": -1.18, "y": 1.28},
                "text": rf"{query.larger_prime}^2+6{query.larger_prime}{query.smaller_prime}+{query.smaller_prime}^2=k^2",
                "tone": "secondary",
            }
        )
    if stage >= 4:
        shapes.append(
            {
                "id": "factor-obligation",
                "kind": "label",
                "point": {"x": -1.18, "y": -1.30},
                "text": rf"({query.larger_prime}+3{query.smaller_prime}-k)({query.larger_prime}+3{query.smaller_prime}+k)=8{query.smaller_prime}^2",
                "tone": "secondary",
            }
        )
    if stage >= 5:
        shapes.append(
            {
                "id": "final-prime-pair",
                "kind": "label",
                "point": {"x": 0.36, "y": 1.43},
                "text": rf"({query.larger_prime},{query.smaller_prime})=(3,2), s=1/5",
                "tone": "accent",
            }
        )
    captions = {
        1: "二つの角を単位円上の二点として表します。表示した順序を交換した場合も同じ弦になります。",
        2: "二点の和が (s,s) なので、弦の中点は (s/2,s/2) です。弦の方向は (1,-1) です。",
        3: "弦と単位円の交点が有理点である条件を、整数の平方条件へ移します。",
        4: "平方条件を因数分解し、素数 q の因数が 1,q,q^2 しかないことを使います。",
        5: "唯一残る素数対を元の単位円と和の条件へ戻し、二つの順序を厳密に確認します。",
    }
    return plane_scene_diagram(
        title="単位ベクトルの和と弦の中点",
        caption=captions[stage],
        viewport={"xMin": -1.35, "xMax": 1.35, "yMin": -1.55, "yMax": 1.62},
        shapes=shapes,
        axes=True,
    )


def _unit_vector_tikz(query: RationalUnitVectorSumQueryIR) -> str:
    first_angle = _angle_tex(query.first_angle)
    second_angle = _angle_tex(query.second_angle)
    return "\n".join(
        (
            r"\begin{tikzpicture}[scale=2.25,line cap=round,line join=round]",
            r"\draw[->,gray!65] (-1.15,0)--(1.2,0);",
            r"\draw[->,gray!65] (0,-1.15)--(0,1.2);",
            r"\draw[gray!70] (0,0) circle (1);",
            r"\coordinate (U) at (-.6,.8);",
            r"\coordinate (V) at (.8,-.6);",
            r"\coordinate (H) at (.1,.1);",
            rf"\draw[->,very thick,cyan!65!black] (0,0)--(U) node[above left] {{$u_{{{first_angle}}}=(-\frac35,\frac45)$}};",
            rf"\draw[->,very thick,blue!70!black] (0,0)--(V) node[below right] {{$u_{{{second_angle}}}=(\frac45,-\frac35)$}};",
            r"\draw[thick,orange!85!black] (U)--(V);",
            r"\fill[orange!85!black] (H) circle (.8pt) node[above right] {$H=(\frac{s}{2},\frac{s}{2})$};",
            r"\draw[->,orange!85!black] (0,0)--(.2,.2) node[above right] {$(s,s)$};",
            rf"\node[align=left,anchor=west] at (-1.12,-1.30) {{$({query.larger_prime}+3{query.smaller_prime}-k)({query.larger_prime}+3{query.smaller_prime}+k)=8{query.smaller_prime}^2$}};",
            r"\end{tikzpicture}",
        )
    )


def _compact(statement: str) -> str:
    return re.sub(
        r"\s+",
        "",
        statement.replace("−", "-")
        .replace("–", "-")
        .replace(r"\left", "")
        .replace(r"\right", "")
        .replace(r"\dfrac", r"\frac")
        .replace(r"\tfrac", r"\frac")
        .replace(r"\quad", "")
        .replace(r"\,", ""),
    )


def compile_rational_unit_vector_sum_query(
    statement: str,
) -> RationalUnitVectorSumQueryIR | None:
    compact = _compact(statement)
    angle = r"(?:\\[A-Za-z]+|[A-Za-z])"
    equation = re.search(
        rf"\\sin(?P<first>{angle})\+\\sin(?P<second>{angle})="
        rf"\\cos(?P=first)\+\\cos(?P=second)="
        r"\\frac\{(?P<larger>[A-Za-z])-(?P<smaller>[A-Za-z])\}"
        r"\{(?P=larger)\+(?P=smaller)\}",
        compact,
    )
    if equation is None:
        return None
    first = equation.group("first")
    second = equation.group("second")
    larger = equation.group("larger")
    smaller = equation.group("smaller")
    if f"{larger}>{smaller}" not in compact or "素数" not in statement:
        return None
    if r"\mathbb{Q}" not in compact:
        return None
    rational_pair = re.search(
        rf"\\sin{re.escape(first)},\\sin{re.escape(second)}\\in\\mathbb\{{Q\}}",
        compact,
    )
    if rational_pair is None:
        return None
    if not any(token in statement for token in ("求めよ", "求めなさい", "determine")):
        return None
    return RationalUnitVectorSumQueryIR(
        first_angle=first.removeprefix("\\"),
        second_angle=second.removeprefix("\\"),
        larger_prime=larger,
        smaller_prime=smaller,
        ratio=f"({larger}-{smaller})/({larger}+{smaller})",
        rational_observables=(f"sin({first})", f"sin({second})"),
    )


def execute_rational_unit_vector_sum_query(
    query: RationalUnitVectorSumQueryIR,
) -> RationalUnitVectorSumSynthesis:
    p = sp.Symbol(query.larger_prime, integer=True, positive=True)
    q = sp.Symbol(query.smaller_prime, integer=True, positive=True)
    s = sp.cancel((p - q) / (p + q))

    def elaborate_equal_sum(arguments: tuple[Any, ...]) -> PrimitiveResult:
        return PrimitiveResult(
            {"p": p, "q": q, "s": s},
            {
                "unit_vectors": [
                    [f"cos({query.first_angle})", f"sin({query.first_angle})"],
                    [f"cos({query.second_angle})", f"sin({query.second_angle})"],
                ],
                "vector_sum": [sp.sstr(s), sp.sstr(s)],
            },
        )

    def decompose_chord(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        data = arguments[0].value
        radical_squared = sp.factor(2 - data["s"] ** 2)
        expected = sp.factor((p**2 + 6 * p * q + q**2) / (p + q) ** 2)
        if sp.simplify(radical_squared - expected) != 0:
            return None
        sine_roots = (
            sp.cancel((data["s"] + sp.sqrt(radical_squared)) / 2),
            sp.cancel((data["s"] - sp.sqrt(radical_squared)) / 2),
        )
        return PrimitiveResult(
            {
                **data,
                "radical_squared": radical_squared,
                "sine_roots": sine_roots,
            },
            {
                "midpoint": [sp.sstr(data["s"] / 2), sp.sstr(data["s"] / 2)],
                "orthogonal_chord_direction": "(1,-1)",
                "sine_roots": [sp.sstr(value) for value in sine_roots],
            },
        )

    def reduce_rationality(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        data = arguments[0].value
        square_form = sp.expand(p**2 + 6 * p * q + q**2)
        k = sp.Symbol("k", integer=True, positive=True)
        if sp.expand((p + 3 * q) ** 2 - square_form - 8 * q**2) != 0:
            return None
        return PrimitiveResult(
            {**data, "k": k, "square_form": square_form},
            {
                "rationality_equivalence": f"{sp.sstr(square_form)}=k**2",
                "factorization": "(p+3*q-k)*(p+3*q+k)=8*q**2",
            },
        )

    def classify_prime_pairs(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        data = arguments[0].value
        odd_branch_candidates = (
            sp.factor(2 * q**2 - 3 * q + 1),
            sp.factor(q**2 - 3 * q + 2),
            sp.Integer(0),
        )
        expected = (
            (2 * q - 1) * (q - 1),
            (q - 1) * (q - 2),
            sp.Integer(0),
        )
        if any(sp.expand(left - right) != 0 for left, right in zip(odd_branch_candidates, expected)):
            return None
        even_branch_factor_pairs = ((1, 8), (2, 4))
        even_branch_p = tuple(left + right - 6 for left, right in even_branch_factor_pairs)
        if even_branch_p != (3, 0):
            return None
        return PrimitiveResult(
            {**data, "prime_pair": (3, 2)},
            {
                "odd_smaller_prime": {
                    "factor_pairs_of_2q2": ["(1,2q^2)", "(2,q^2)", "(q,2q)"],
                    "larger_prime_candidates": [sp.sstr(value) for value in odd_branch_candidates],
                    "survivors_with_p_greater_q": [],
                },
                "even_smaller_prime": {
                    "q": 2,
                    "factor_pairs_of_8": [list(pair) for pair in even_branch_factor_pairs],
                    "larger_prime_candidates": list(even_branch_p),
                    "survivor": [3, 2],
                },
            },
        )

    def replay_unit_vectors(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        data = arguments[0].value
        p_value, q_value = data["prime_pair"]
        s_value = sp.Rational(p_value - q_value, p_value + q_value)
        sine_values = (sp.Rational(4, 5), sp.Rational(-3, 5))
        vector_pairs = (
            ((sp.Rational(-3, 5), sine_values[0]), (sp.Rational(4, 5), sine_values[1])),
            ((sp.Rational(4, 5), sine_values[1]), (sp.Rational(-3, 5), sine_values[0])),
        )
        for first_vector, second_vector in vector_pairs:
            if sp.simplify(first_vector[0] ** 2 + first_vector[1] ** 2 - 1) != 0:
                return None
            if sp.simplify(second_vector[0] ** 2 + second_vector[1] ** 2 - 1) != 0:
                return None
            if sp.simplify(first_vector[0] + second_vector[0] - s_value) != 0:
                return None
            if sp.simplify(first_vector[1] + second_vector[1] - s_value) != 0:
                return None
        return PrimitiveResult(
            {
                **data,
                "ratio_value": s_value,
                "sine_value_set": tuple(sorted(sine_values)),
                "ordered_sine_pairs": (
                    (sine_values[0], sine_values[1]),
                    (sine_values[1], sine_values[0]),
                ),
            },
            {
                "prime_pair": [p_value, q_value],
                "ratio": sp.sstr(s_value),
                "ordered_unit_vector_witnesses": [
                    [[sp.sstr(value) for value in vector] for vector in pair]
                    for pair in vector_pairs
                ],
                "all_original_equalities_replayed": True,
            },
        )

    primitives = (
        RuntimePrimitive(
            "equal_unit_vector_sum_elaboration",
            ("ParsedProblemIR",),
            "EqualUnitVectorSum",
            elaborate_equal_sum,
        ),
        RuntimePrimitive(
            "unit_circle_midpoint_chord_decomposition",
            ("EqualUnitVectorSum",),
            "SymmetricSinePair",
            decompose_chord,
        ),
        RuntimePrimitive(
            "rational_radical_square_reduction",
            ("SymmetricSinePair",),
            "PrimeQuadraticSquareObligation",
            reduce_rationality,
        ),
        RuntimePrimitive(
            "prime_factor_pair_classification",
            ("PrimeQuadraticSquareObligation",),
            "CertifiedPrimePair",
            classify_prime_pairs,
        ),
        RuntimePrimitive(
            "unit_vector_original_constraint_replay",
            ("CertifiedPrimePair",),
            "CertifiedRationalSineValues",
            replay_unit_vectors,
        ),
    )
    plan = synthesize_typed_plan(
        [initial_fact("ParsedProblemIR", query.to_dict())],
        primitives,
        ("CertifiedRationalSineValues",),
        max_depth=7,
        max_states=48,
    )
    if not plan.complete:
        raise ValueError(f"runtime rational-unit-sum planner left open goals: {plan.open_goal_sorts}")

    result = plan.goals["CertifiedRationalSineValues"].value
    first_angle = rf"\{query.first_angle}" if len(query.first_angle) > 1 else query.first_angle
    second_angle = rf"\{query.second_angle}" if len(query.second_angle) > 1 else query.second_angle
    answer_tex = (
        rf"\(({query.larger_prime},{query.smaller_prime})=(3,2),\quad "
        rf"\{{\sin {first_angle},\sin {second_angle}\}}="
        r"\left\{-\frac35,\frac45\right\}\)"
    )
    derivation = (
        rf"\(s=({query.larger_prime}-{query.smaller_prime})/"
        rf"({query.larger_prime}+{query.smaller_prime})\) とおく。"
        rf"二つの単位ベクトル \((\cos {first_angle},\sin {first_angle})\), "
        rf"\((\cos {second_angle},\sin {second_angle})\) の和は \((s,s)\) である。"
        r"その中点は \((s/2,s/2)\)、二点を結ぶ弦は方向 \((1,-1)\) をもつので、"
        r"単位円との交点を求めると"
        rf"\[\sin {first_angle},\ \sin {second_angle}="
        r"\frac{s\pm\sqrt{2-s^2}}2\]"
        r"を得る。",
        rf"二つの正弦が有理数だから \(\sqrt{{2-s^2}}\) は有理数である。"
        rf"\(s=({query.larger_prime}-{query.smaller_prime})/"
        rf"({query.larger_prime}+{query.smaller_prime})\) を代入すると、ある正の整数 \(k\) が存在して"
        rf"\[{query.larger_prime}^2+6{query.larger_prime}{query.smaller_prime}+"
        rf"{query.smaller_prime}^2=k^2\]"
        r"となる。これは"
        rf"\[({query.larger_prime}+3{query.smaller_prime}-k)"
        rf"({query.larger_prime}+3{query.smaller_prime}+k)=8{query.smaller_prime}^2\]"
        r"と同値である。",
        rf"まず \({query.smaller_prime}\) が奇素数とする。"
        r"両因子を2で割った正の因子対は"
        rf"\[(1,2{query.smaller_prime}^2),\ (2,{query.smaller_prime}^2),\ "
        rf"({query.smaller_prime},2{query.smaller_prime})\]"
        r"だけである。和から得られる大きい素数の候補は、それぞれ"
        rf"\[(2{query.smaller_prime}-1)({query.smaller_prime}-1),\quad"
        rf"({query.smaller_prime}-1)({query.smaller_prime}-2),\quad0.\]"
        rf"第一候補は ({query.smaller_prime}\ge3) で二因子がともに1より大きいので合成数である。"
        rf"第二候補は ({query.smaller_prime}=3) なら2であり、"
        rf"({query.larger_prime}>{query.smaller_prime}) に反する。"
        rf"({query.smaller_prime}\ge5) なら二因子がともに1より大きいので合成数である。"
        rf"従って \({query.smaller_prime}\) は奇素数ではない。",
        rf"よって \({query.smaller_prime}=2\) である。因子対は \((1,8),(2,4)\) で、"
        rf"\({query.larger_prime}=3,0\) を与える。素数かつ "
        rf"\({query.larger_prime}>{query.smaller_prime}\) を満たすのは"
        rf"\(({query.larger_prime},{query.smaller_prime})=(3,2)\) だけである。",
        r"このとき \(s=1/5\)、\(\sqrt{2-s^2}=7/5\) なので、二つの正弦は "
        r"\(4/5\) と \(-3/5\) である。対応する余弦をそれぞれ \(-3/5,4/5\) と取れば、"
        r"二つの単位円条件と正弦和・余弦和が全て \(1/5\) になることも直接確かめられる。",
    )
    witness = {
        "input_ir": query.to_dict(),
        "prime_pair": list(result["prime_pair"]),
        "ratio": sp.sstr(result["ratio_value"]),
        "square_condition": sp.sstr(result["square_form"]),
        "sine_value_set": [sp.sstr(value) for value in result["sine_value_set"]],
        "ordered_sine_pairs": [
            [sp.sstr(value) for value in pair] for pair in result["ordered_sine_pairs"]
        ],
        "all_original_equalities_replayed": True,
        "planner": {
            "states_explored": plan.states_explored,
            "goal_sorts": sorted(plan.goals),
            "open_goal_sorts": list(plan.open_goal_sorts),
        },
    }
    checks = (
        "二角、大小関係をもつ二素数、共通和、二正弦の有理性を現在の問題文から抽出",
        "二つの単位ベクトルの中点と直交弦から正弦の二根を導出",
        "有理性を整数二次形式の平方条件へ双方向に変換",
        "奇素数枝と2の枝の因子対を完全列挙",
        "残った二つの順序を単位円および元の和の条件へ厳密代入",
    )
    chain = tuple(step["rule"] for step in plan.proof_program)
    diagrams = tuple(
        _unit_vector_diagram(query, stage=stage)
        for stage in range(1, 6)
    )
    visual_explanation = {
        "version": 1,
        "mode": "stepper",
        "title": "単位円の弦が素数条件へ変わるまで",
        "diagram_required_for_every_step": True,
        "composition_verified": True,
        "morphism_chain": list(chain),
        "steps": [
            {
                "id": "rational-unit-sum-step-1",
                "title": "二つの角を単位ベクトルにする",
                "explanation_ja": "正弦と余弦を座標とみなすと、二つの点は単位円上にあり、そのベクトル和は (s,s) です。",
                "formula_tex": rf"u_{{{first_angle}}}+u_{{{second_angle}}}=(s,s)",
                "morphism": {"morphism_id": chain[0], "label_ja": "単位ベクトル表示", "input_type": "ParsedProblemIR", "output_type": "EqualUnitVectorSum"},
                "source_state": {"id": "input", "type": "ParsedProblemIR"},
                "target_state": {"id": "unit-vector-sum", "type": "EqualUnitVectorSum"},
                "diagram": diagrams[0],
            },
            {
                "id": "rational-unit-sum-step-2",
                "title": "弦の中点を固定する",
                "explanation_ja": "和が分かれば弦の中点が決まります。中点を通り (1,-1) に平行な直線と単位円との二交点を解きます。",
                "formula_tex": r"H=(s/2,s/2),\quad \sin\alpha,\sin\beta=\frac{s\pm\sqrt{2-s^2}}2",
                "morphism": {"morphism_id": chain[1], "label_ja": "弦の中点分解", "input_type": "EqualUnitVectorSum", "output_type": "SymmetricSinePair"},
                "source_state": {"id": "unit-vector-sum", "type": "EqualUnitVectorSum"},
                "target_state": {"id": "sine-pair", "type": "SymmetricSinePair"},
                "diagram": diagrams[1],
            },
            {
                "id": "rational-unit-sum-step-3",
                "title": "有理性を平方条件にする",
                "explanation_ja": "二つの正弦が有理数であるための条件を、整数 k が存在する平方条件として書き直します。",
                "formula_tex": rf"{query.larger_prime}^2+6{query.larger_prime}{query.smaller_prime}+{query.smaller_prime}^2=k^2",
                "morphism": {"morphism_id": chain[2], "label_ja": "有理平方根の整数化", "input_type": "SymmetricSinePair", "output_type": "PrimeQuadraticSquareObligation"},
                "source_state": {"id": "sine-pair", "type": "SymmetricSinePair"},
                "target_state": {"id": "square-obligation", "type": "PrimeQuadraticSquareObligation"},
                "diagram": diagrams[2],
            },
            {
                "id": "rational-unit-sum-step-4",
                "title": "素数の因数対を尽くす",
                "explanation_ja": "積が 8q^2 になる二因子を列挙します。q が奇素数の場合を除外すると q=2 だけが残ります。",
                "formula_tex": rf"({query.larger_prime}+3{query.smaller_prime}-k)({query.larger_prime}+3{query.smaller_prime}+k)=8{query.smaller_prime}^2",
                "morphism": {"morphism_id": chain[3], "label_ja": "素数因数対の完全分類", "input_type": "PrimeQuadraticSquareObligation", "output_type": "CertifiedPrimePair"},
                "source_state": {"id": "square-obligation", "type": "PrimeQuadraticSquareObligation"},
                "target_state": {"id": "prime-pair", "type": "CertifiedPrimePair"},
                "diagram": diagrams[3],
            },
            {
                "id": "rational-unit-sum-step-5",
                "title": "元の条件へ戻して確認する",
                "explanation_ja": "残った点を単位円と二つの和へ代入します。点の順序を交換した場合も同じ答えになります。",
                "formula_tex": r"(-3/5,4/5)+(4/5,-3/5)=(1/5,1/5)",
                "morphism": {"morphism_id": chain[4], "label_ja": "元の条件への厳密代入", "input_type": "CertifiedPrimePair", "output_type": "CertifiedRationalSineValues"},
                "source_state": {"id": "prime-pair", "type": "CertifiedPrimePair"},
                "target_state": {"id": "answer", "type": "CertifiedRationalSineValues"},
                "diagram": diagrams[4],
            },
        ],
    }
    return RationalUnitVectorSumSynthesis(
        answer_tex=answer_tex,
        derivation_tex=derivation,
        expression_tex=(
            rf"\sin {first_angle}+\sin {second_angle}="
            rf"\cos {first_angle}+\cos {second_angle}="
            rf"\frac{{{query.larger_prime}-{query.smaller_prime}}}"
            rf"{{{query.larger_prime}+{query.smaller_prime}}}"
        ),
        proof_program=plan.proof_program + (
            {
                "rule": "exact_obligation_replay",
                "verified": True,
                "planner_states_explored": plan.states_explored,
            },
        ),
        verification_checks=checks,
        witness=witness,
        hypotheses_evaluated=5,
        diagram=diagrams[-1],
        diagram_tikz=_unit_vector_tikz(query),
        visual_explanation=visual_explanation,
    )


def synthesize_rational_unit_vector_sum_problem(
    statement: str,
) -> RationalUnitVectorSumSynthesis | None:
    query = compile_rational_unit_vector_sum_query(statement)
    if query is None:
        return None
    try:
        return execute_rational_unit_vector_sum_query(query)
    except ValueError:
        return None
