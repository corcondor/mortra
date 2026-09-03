"""Build a reproducible TeX solution artifact from MORTRA's verified output.

The renderer is intentionally downstream of verification.  It receives only
the statement, the verified answer, the solver-produced explanation, and the
executed morphism chain.  It therefore cannot invent mathematical content.
"""

from __future__ import annotations

import math
import re
from typing import Any, Iterable

from math_os_prototype.visual_reasoning import (
    compile_plane_scene_timeline,
    progressive_diagram_frames,
)


ARTIFACT_VERSION = 4


_FIELD_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("確率・統計", ("確率", "期待値", "分散", "共分散", "相関係数", "無作為", "カード")),
    ("整数", ("整数", "自然数", "素数", "合同", "整除", "約数", "倍数", "mod")),
    ("数列", ("数列", "漸化式", "フィボナッチ", "一般項")),
    ("解析", ("積分", "極限", "微分", "導関数", "不等式", "最大値", "最小値", r"\int", r"\lim")),
    ("幾何", ("三角形", "円", "図形", "面積", "体積", "多角形", "接線", "外接", "内接")),
    ("代数", ("方程式", "多項式", "行列", "複素", "解け", "solve.exact.solve")),
    ("三角関数", (r"\sin", r"\cos", r"\tan", "正弦", "余弦", "正接")),
)


def _escape_text(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "^": r"\^{}",
        "~": r"\~{}",
        "{": r"\{",
        "}": r"\}",
    }
    return "".join(replacements.get(character, character) for character in value)


def _safe_statement(value: str) -> str:
    """Keep mathematical TeX while making extracted list items standalone."""
    standalone = re.sub(
        r"\\item\s*(?:\[([^]]+)\])?",
        lambda match: rf"\par\medskip\noindent\textbf{{{match.group(1) or '・'}}}\quad ",
        value.strip(),
    )
    # Every item is now an explicit paragraph.  Leaving its former list wrapper
    # behind creates an invalid empty enumerate/itemize environment.
    normalized = re.sub(r"\\(?:begin|end)\{(?:enumerate|itemize)\}", "", standalone)
    return "\n".join(line.rstrip() for line in normalized.splitlines())


def _field_labels(card: dict[str, Any]) -> list[str]:
    explicit = card.get("field_labels")
    if isinstance(explicit, list):
        labels = [str(label).strip() for label in explicit if str(label).strip()]
        if labels:
            return labels[:2]

    corpus = " ".join(
        str(card.get(key) or "")
        for key in ("statement_tex", "domain", "family_id")
    ).lower()
    labels = [
        label
        for label, keywords in _FIELD_KEYWORDS
        if any(keyword.lower() in corpus for keyword in keywords)
    ]
    return labels[:2] or ["数学"]


def _editorial_from_card(
    card: dict[str, Any],
    roadmap: list[dict[str, Any]],
    fields: list[str],
) -> dict[str, str]:
    explicit = card.get("editorial")
    supplied = dict(explicit) if isinstance(explicit, dict) else {}

    route_labels: list[str] = []
    for entry in roadmap:
        label = str(entry.get("label_ja") or "").strip()
        if label and label not in route_labels:
            route_labels.append(label)
    route_summary = "、".join(route_labels[:3]) or "型付き変換と証明書再生"
    field_summary = "・".join(fields)
    statistics_context = "確率・統計" in fields

    defaults = {
        "intent": (
            f"{field_summary}の条件を実行可能な関係へ移し、"
            f"{route_summary}を一つの証明として組み立てる力を問う。"
        ),
        "admissions_context": (
            "新課程の確率・統計を含む記述式入試を想定し、数値だけでなく確率変数の定義、"
            "期待値・分散・共分散の導出までを採点対象とする。"
            if statistics_context
            else "記述式の大学入試または数学コンテストを想定し、変換の根拠と最終検証までを採点対象とする。"
        ),
        "distinctive_point": (
            "数値近似や答えの照合で終えず、問題文から答えまで実際に通過した射と証明義務を再生できる。"
        ),
    }
    return {
        key: str(supplied.get(key) or value).strip()
        for key, value in defaults.items()
    }


def _chain_nodes(chain: Iterable[str]) -> list[str]:
    nodes = [str(node).strip() for node in chain if str(node).strip()]
    if len(nodes) >= 2:
        return nodes
    return ["ProblemText", "TypedSemanticIR", "VerifiedAnswer"]


def proof_diagram(chain: Iterable[str]) -> dict[str, Any]:
    nodes = _chain_nodes(chain)
    return {
        "version": ARTIFACT_VERSION,
        "kind": "morphism",
        "title": "解答で実行した変換",
        "caption": "問題文から検証済み解答まで、実際に通過した型付き変換を示します。",
        "nodes": nodes,
    }


def proof_diagram_tikz(chain: Iterable[str]) -> str:
    nodes = _chain_nodes(chain)
    lines = [
        r"\begin{tikzpicture}[",
        r"  node distance=8mm and 5mm,",
        r"  stage/.style={draw,rounded corners=1pt,align=center,text width=29mm,minimum height=10mm,inner xsep=3pt,inner ysep=3pt,font=\footnotesize},",
        r"  flow/.style={-{Latex[length=2mm]},thick}",
        r"]",
    ]
    for index, node in enumerate(nodes):
        # The exact identifier remains in the audit trail below the diagram;
        # the visual node uses readable words and legal wrap points.
        display_node = node.replace("_", " ")
        label = _escape_text(re.sub(r"([./])", r"\1 ", display_node))
        if index == 0:
            options = "stage"
        elif index % 4:
            options = rf"stage,right=of n{index - 1}"
        else:
            options = rf"stage,below=of n{index - 1},xshift=-30mm"
        lines.append(rf"\node[{options}] (n{index}) {{{label}}};")
        if index:
            lines.append(rf"\draw[flow] (n{index - 1}) -- (n{index});")
    lines.append(r"\end{tikzpicture}")
    return "\n".join(lines)


def _certificate_chart(card: dict[str, Any]) -> dict[str, Any]:
    certificate = card.get("execution_certificate")
    if not isinstance(certificate, dict):
        return {}
    witness = certificate.get("witness")
    if not isinstance(witness, dict):
        return {}
    chart = witness.get("shared_chart")
    return chart if isinstance(chart, dict) else {}


_STAGE_LABELS_JA = {
    "ProblemText": "問題文",
    "LatexSyntaxTree": "読み取った数式",
    "SymPyExpression": "厳密計算用の式",
    "TypedSemanticIR": "型付き意味表現",
    "ExecutableConstraint": "実行可能な条件",
    "sympy.solve": "解の候補",
    "sympy.diff": "導関数",
    "sympy.integrate": "定積分の値",
    "sympy.limit": "極限値",
    "sympy.cubic_trigonometric_chart": "三角関数で表した三つの実根",
    "NumberedObligationDecomposition": "番号付きの設問",
    "TypedObligationConjunction": "共通条件を引き継いだ各設問",
    "IndependentChildCertificateReplay": "再生済みの部分証明",
    "VerifiedAnswerBundle": "全設問の検証済み解答",
    "VerifiedAnswer": "検証済み解答",
    "mortra.runtime_sine_cosine_tangent_bound": "凹性から得た接線上界",
    "mortra.runtime_sine_cosine_fixed_point": "一意な固定点とその位置",
    "mortra.runtime_sine_cosine_two_step_bound": "二段反復の一次上界",
    "mortra.runtime_sine_cosine_iteration_integral_bound": "積分列の二段縮小評価",
    "mortra.runtime_rotated_parabola_blowup_distance": "回転放物線の交点と距離極限",
    "mortra.runtime_rotated_parabola_boundary_moment": "回転放物線領域の体積極限",
    "elaborate_origin_centered_rotation_of_quadratic_graph": "原点中心の二次曲線回転",
    "conjugate_rotation_by_tangent_half_angle": "回転の半角有理化",
    "factor_rotated_curve_intersection": "交点式の因数分解",
    "isolate_unique_nonzero_real_intersection": "原点以外の実交点の分離",
    "restore_distance_scale_and_take_limit": "距離尺度の復元",
    "convert_solid_volume_to_boundary_moment": "回転体積の境界積分",
    "reflect_negative_rotation": "負の回転角への反転対称性",
    "mortra.runtime_elementary_inequality_envelope": "初等関数の厳密な上下界",
    "elaborate_elementary_inequality_query": "初等不等式の型付け",
    "construct_alternating_series_envelope": "交代級数の上下包絡",
    "transport_order_through_definite_integral": "不等式の定積分への移送",
    "enclose_pi_by_archimedean_rationals": "円周率の有理区間評価",
    "bound_positive_series_tail_geometrically": "正項級数の尾項評価",
    "compare_positive_radicals_by_squaring": "正の根号の平方比較",
    "derive_sine_below_identity": "正弦の直線上界",
    "trap_positive_integral_between_consecutive_integers": "連続する整数による排除",
    "substitute_reciprocal_domain": "逆数による区間変換",
    "compare_log_power_series_coefficientwise": "対数級数の係数比較",
    "transport_bound_through_increasing_tangent": "正接による上界の移送",
    "maximize_convex_function_at_interval_endpoints": "凸関数の端点最大",
    "solve.exact.mortra.runtime_sine_cosine_tangent_bound": "凹性から得た接線上界",
    "solve.exact.mortra.runtime_sine_cosine_fixed_point": "一意な固定点とその位置",
    "solve.exact.mortra.runtime_sine_cosine_two_step_bound": "二段反復の一次上界",
    "solve.exact.mortra.runtime_sine_cosine_iteration_integral_bound": "積分列の二段縮小評価",
}


_MORPHISM_PRESENTATION_JA: dict[str, tuple[str, str]] = {
    "LatexSyntaxTree": (
        "数式を正確に読み取る",
        "文字、演算、等号、積分区間を区別し、元の数式の構造を保つ。",
    ),
    "SymPyExpression": (
        "計算できる式に直す",
        "読み取った数式を、分数や根号を保った厳密計算用の式へ移す。",
    ),
    "TypedSemanticIR": (
        "条件と対象を整理する",
        "何が与えられ、何を求めるのかを区別し、後の計算で使える形にする。",
    ),
    "ExecutableConstraint": (
        "条件を同時に満たす形へ直す",
        "問題文の条件を、元の意味を変えずに計算・検証できる式へまとめる。",
    ),
    "sympy.solve": (
        "方程式を厳密に解く",
        "因数分解または代数的な消去を行い、得た候補を元の方程式へ戻して確かめる。",
    ),
    "sympy.diff": (
        "各項を微分する",
        "微分公式を各項へ適用し、整理した導関数を元の関数と対応させる。",
    ),
    "sympy.integrate": (
        "面積を定積分で求める",
        "原始関数を求め、上端と下端の値の差を分数のまま厳密に計算する。",
    ),
    "sympy.limit": (
        "極限を厳密に求める",
        "式を変形して未定形を解消し、極限値を元の条件の範囲で確かめる。",
    ),
    "sympy.cubic_trigonometric_chart": (
        "三次方程式を角度へ移す",
        "三倍角の公式へ対応させ、三つの実根を角度の違いとして求める。",
    ),
    "NumberedObligationDecomposition": (
        "設問ごとに分ける",
        "共通の問題文を保ったまま、求める内容を番号付きの設問へ分ける。",
    ),
    "TypedObligationConjunction": (
        "共通条件を各設問へ引き継ぐ",
        "数列の定義と初期値を各設問へ引き継ぎ、四つの証明対象を確定する。",
    ),
    "IndependentChildCertificateReplay": (
        "各設問の証明書を再生する",
        "各設問の計算と論証を独立に再実行し、全ての結論を検証する。",
    ),
    "VerifiedAnswerBundle": (
        "全設問の証明を一つにまとめる",
        "独立に検証した四つの結論を、元の問題に対する一つの解答としてまとめる。",
    ),
    "mortra.runtime_sine_cosine_tangent_bound": (
        "凹性から接線上界を得る",
        "二階導関数の符号を確かめ、接点での値と傾きから区間全体の上界を得る。",
    ),
    "mortra.runtime_sine_cosine_fixed_point": (
        "固定点の個数と位置を決める",
        "差の単調性で解の一意性を示し、接線上界でその位置を比較する。",
    ),
    "mortra.runtime_sine_cosine_two_step_bound": (
        "二段反復を一次式で押さえる",
        "比較差の端点値と導関数の形を確かめ、区間全体で成り立つ一次上界を得る。",
    ),
    "mortra.runtime_sine_cosine_iteration_integral_bound": (
        "点ごとの上界を積分へ移す",
        "二段反復の一次上界を積分し、偶数番目と奇数番目をそれぞれ帰納する。",
    ),
    "mortra.runtime_rotated_parabola_blowup_distance": (
        "半角変数で遠方交点の距離を求める",
        "回転を半角変数の有理式へ移し、交点式を因数分解してから距離の尺度を元へ戻す。",
    ),
    "mortra.runtime_rotated_parabola_boundary_moment": (
        "境界積分で回転体積の極限を求める",
        "二曲線の交点を確定し、囲まれた領域の境界積分と反転対称性から左右の極限を求める。",
    ),
    "elaborate_origin_centered_rotation_of_quadratic_graph": (
        "原点中心の回転を座標で表す",
        "二次曲線上の点へ回転行列を作用させ、交点条件へ代入できる座標表示を得る。",
    ),
    "conjugate_rotation_by_tangent_half_angle": (
        "回転を半角変数の有理式へ移す",
        "正弦と余弦を半角変数で表し、交点と極限を有理式として扱えるようにする。",
    ),
    "factor_rotated_curve_intersection": (
        "交点式を因数分解する",
        "回転後の点を元の二次曲線へ代入し、各因子と判別式を厳密に検査する。",
    ),
    "isolate_unique_nonzero_real_intersection": (
        "原点以外の実交点を一つに定める",
        "判別式が負の因子を除き、残る一次因子から交点の媒介変数と座標を求める。",
    ),
    "restore_distance_scale_and_take_limit": (
        "交点距離の尺度を元へ戻す",
        "交点座標から距離を作り、半角変数と回転角の比を用いて極限を求める。",
    ),
    "convert_solid_volume_to_boundary_moment": (
        "回転体積を境界積分へ直す",
        "円環法を境界に沿う積分へまとめ、固定曲線と回転曲線の寄与を別々に計算する。",
    ),
    "reflect_negative_rotation": (
        "負の回転角を反転対称性で扱う",
        "領域の体積が回転角の偶関数であることを用い、左右の片側極限を比較する。",
    ),
    "mortra.runtime_elementary_inequality_envelope": (
        "初等関数を厳密な上下界で挟む",
        "級数の剰余、単調性、積分による順序保存を組み合わせ、浮動小数近似なしで不等式を閉じる。",
    ),
    "elaborate_elementary_inequality_query": (
        "初等不等式を型付きの証明義務へ移す",
        "関数、区間、比較対象、整数判定を問題文から取り出し、必要な上下界の向きを確定する。",
    ),
    "construct_alternating_series_envelope": (
        "交代級数から多項式の上下界を作る",
        "項の絶対値が減少する区間を確認し、切り捨て次数に応じた剰余の符号を利用する。",
    ),
    "transport_order_through_definite_integral": (
        "点ごとの不等式を定積分へ移す",
        "区間上の上下関係と正の乗数を保ったまま、関数の比較を積分値の比較へ変える。",
    ),
    "enclose_pi_by_archimedean_rationals": (
        "円周率を有理数の区間で挟む",
        "円周率を含む多項式を有理区間で外側から評価し、最後の符号判定を有理数計算へ落とす。",
    ),
    "bound_positive_series_tail_geometrically": (
        "正項級数の残りを等比級数で抑える",
        "有限部分和より後の分母増加を共通比へ変換し、無限の尾項に有理数上界を与える。",
    ),
    "compare_positive_radicals_by_squaring": (
        "正の根号を平方して比較する",
        "両辺の正値を確認してから平方し、根号を含む大小比較を有理数の符号判定へ変える。",
    ),
    "derive_sine_below_identity": (
        "正弦を直線で上から抑える",
        "x-sin(x) の導関数を調べ、正の区間で sin(x)<x を得る。",
    ),
    "trap_positive_integral_between_consecutive_integers": (
        "正の積分を連続する二整数の間へ置く",
        "比較積分を厳密に評価し、対象が整数になれない開区間へ閉じ込める。",
    ),
    "substitute_reciprocal_domain": (
        "逆数で無限区間を単位区間へ移す",
        "x>1 を y=1/x によって 0<y<1 へ変え、同値な一変数不等式を作る。",
    ),
    "compare_log_power_series_coefficientwise": (
        "二つの対数級数を係数ごとに比べる",
        "同じべきに掛かる正の係数を比較し、区間全体で成り立つ指数関数の上界を得る。",
    ),
    "transport_bound_through_increasing_tangent": (
        "上界を単調な正接へ通す",
        "二つの角が正接の単調区間にあることを確認し、角の大小を正接値の大小へ移す。",
    ),
    "maximize_convex_function_at_interval_endpoints": (
        "凸関数の最大値を端点で評価する",
        "二階導関数の正値から凸性を確認し、閉区間全体の上界を二つの端点へ縮約する。",
    ),
}

for _runtime_morphism in (
    "mortra.runtime_sine_cosine_tangent_bound",
    "mortra.runtime_sine_cosine_fixed_point",
    "mortra.runtime_sine_cosine_two_step_bound",
    "mortra.runtime_sine_cosine_iteration_integral_bound",
    "mortra.runtime_rotated_parabola_blowup_distance",
    "mortra.runtime_rotated_parabola_boundary_moment",
    "mortra.runtime_elementary_inequality_envelope",
):
    _MORPHISM_PRESENTATION_JA[f"solve.exact.{_runtime_morphism}"] = (
        _MORPHISM_PRESENTATION_JA[_runtime_morphism]
    )


def _display_stage_ja(stage: str) -> str:
    return _STAGE_LABELS_JA.get(stage, stage.replace("_", " "))


def _readable_audit_text(value: str) -> str:
    """Keep implementation identifiers in JSON while presenting readable prose."""

    text = value
    for technical_id, label in sorted(
        _STAGE_LABELS_JA.items(), key=lambda item: len(item[0]), reverse=True
    ):
        text = text.replace(technical_id, label)
    if "current-input typed program synthesis" in text:
        return "現在の問題文から合成した証明を、厳密な記号計算と図の根拠から再生"
    return text


def _roadmap_from_chain(chain: Iterable[str]) -> list[dict[str, str]]:
    """Expose the executed chain when a solver has no authored route prose yet."""
    nodes = _chain_nodes(chain)
    roadmap: list[dict[str, str]] = []
    for index in range(1, len(nodes)):
        morphism_id = nodes[index]
        presentation = _MORPHISM_PRESENTATION_JA.get(morphism_id)
        if presentation:
            label, role = presentation
        elif morphism_id == "VerifiedAnswer":
            label = "証明書を再生して結論を認証"
            role = "実行記録と証明義務を再生し、元の問題条件に対する結論を確定する。"
            morphism_id = "certificate.replay.verify"
        else:
            label = "記録された変換を実行する"
            role = "証明書に記録された型付き射を実行し、次の表現へ変換する。"
        roadmap.append(
            {
                "morphism_id": morphism_id,
                "label_ja": label,
                "source_ja": _display_stage_ja(nodes[index - 1]),
                "target_ja": _display_stage_ja(nodes[index]),
                "role_ja": role,
            }
        )
    return roadmap


def _roadmap_tikz(
    roadmap: list[dict[str, Any]], fallback_chain: Iterable[str]
) -> str:
    if not roadmap:
        return proof_diagram_tikz(fallback_chain)

    first_source = str(roadmap[0].get("source_ja") or "問題文")
    lines = [
        r"\begin{tikzpicture}[",
        r"  node distance=3.5mm,",
        r"  stage/.style={draw,rounded corners=1pt,align=left,text width=118mm,minimum height=7mm,inner xsep=4pt,inner ysep=2pt,font=\small},",
        r"  flow/.style={-{Latex[length=2mm]},thick,cyan!55!black},",
        r"  edge label/.style={fill=white,inner xsep=3pt,font=\scriptsize\bfseries}",
        r"]",
        rf"\node[stage] (n0) {{{_escape_text(first_source)}}};",
    ]
    for index, entry in enumerate(roadmap, start=1):
        target = _escape_text(str(entry.get("target_ja") or "中間表現"))
        label = _escape_text(str(entry.get("label_ja") or f"射 M{index}"))
        lines.append(rf"\node[stage,below=of n{index - 1}] (n{index}) {{{target}}};")
        lines.append(
            rf"\draw[flow] (n{index - 1}) -- node[edge label] {{{label}}} (n{index});"
        )
    lines.append(r"\end{tikzpicture}")
    return "\n".join(lines)


def _roadmap_items(roadmap: list[dict[str, Any]]) -> str:
    return "\n".join(
        rf"""\item \textbf{{M{index}: {_escape_text(str(entry.get('label_ja') or '型付き変換'))}}}\\
{_escape_text(str(entry.get('source_ja') or '入力'))}
$\longrightarrow$
{_escape_text(str(entry.get('target_ja') or '出力'))}\\
{_escape_text(str(entry.get('role_ja') or '型を保ったまま中間表現を変換する。'))}"""
        for index, entry in enumerate(roadmap, start=1)
    )


def _obligation_items(obligations: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for item in obligations:
        status = str(item.get("status") or "unknown")
        readable_status = "検証済み" if status == "verified" else status
        obligation_id = str(item.get("id") or "?")
        part_match = re.fullmatch(r"part-(\d+)", obligation_id)
        readable_id = f"設問({part_match.group(1)})" if part_match else obligation_id
        lines.append(
            rf"\item \textbf{{{_escape_text(readable_id)}}}: "
            rf"{_escape_text(str(item.get('claim_ja') or '証明義務'))} "
            rf"（{_escape_text(readable_status)}）"
        )
    return "\n".join(lines)


_DIAGRAM_TONES = {
    "primary": "draw=cyan!65!black,fill=cyan!10",
    "secondary": "draw=black!80,fill=black!3",
    "accent": "draw=magenta!70!black,fill=magenta!12",
    "muted": "draw=black!38,fill=black!3",
}


def _diagram_style(shape: dict[str, Any], *, allow_fill: bool = True) -> str:
    tone = str(shape.get("tone") or "muted")
    base = _DIAGRAM_TONES.get(tone, _DIAGRAM_TONES["muted"])
    if not allow_fill or not shape.get("fill"):
        base = base.split(",fill=", 1)[0]
    extras = ["line width=.7pt"]
    if shape.get("dashed"):
        extras.append("densely dashed")
    if shape.get("fill") and allow_fill:
        extras.append("fill opacity=.55")
    return ",".join([base, *extras])


def _plane_diagram_tex(diagram: dict[str, Any]) -> str:
    viewport = diagram.get("viewport") or {}
    try:
        x_min = float(viewport["xMin"])
        x_max = float(viewport["xMax"])
        y_min = float(viewport["yMin"])
        y_max = float(viewport["yMax"])
    except (KeyError, TypeError, ValueError):
        return ""
    width = max(1e-9, x_max - x_min)
    height = max(1e-9, y_max - y_min)
    scale = min(12.5 / width, 7.2 / height)
    lines = [
        rf"\begin{{tikzpicture}}[scale={scale:.6f},line cap=round,line join=round]",
        rf"\path[use as bounding box] ({x_min:.8f},{y_min:.8f}) rectangle ({x_max:.8f},{y_max:.8f});",
    ]
    if diagram.get("axes"):
        if y_min <= 0 <= y_max:
            lines.append(
                rf"\draw[->,black!35] ({x_min:.8f},0)--({x_max:.8f},0);"
            )
        if x_min <= 0 <= x_max:
            lines.append(
                rf"\draw[->,black!35] (0,{y_min:.8f})--(0,{y_max:.8f});"
            )
    for shape in diagram.get("shapes") or []:
        if not isinstance(shape, dict):
            continue
        kind = shape.get("kind")
        if kind == "polyline":
            points = shape.get("points") or []
            if len(points) < 2:
                continue
            path = " -- ".join(
                rf"({float(point['x']):.8f},{float(point['y']):.8f})"
                for point in points
            )
            if shape.get("closed"):
                path += " -- cycle"
            lines.append(rf"\draw[{_diagram_style(shape)}] {path};")
        elif kind == "circle":
            center = shape.get("center") or {}
            try:
                cx, cy = float(center["x"]), float(center["y"])
                radius = float(shape["radius"])
            except (KeyError, TypeError, ValueError):
                continue
            lines.append(
                rf"\draw[{_diagram_style(shape, allow_fill=False)}] "
                rf"({cx:.8f},{cy:.8f}) circle ({radius:.8f});"
            )
        elif kind == "point":
            point = shape.get("point") or {}
            try:
                px, py = float(point["x"]), float(point["y"])
            except (KeyError, TypeError, ValueError):
                continue
            tone = str(shape.get("tone") or "muted")
            color = {
                "primary": "cyan!65!black",
                "secondary": "black!80",
                "accent": "magenta!70!black",
                "muted": "black!45",
            }.get(tone, "black!45")
            lines.append(rf"\fill[{color}] ({px:.8f},{py:.8f}) circle (1.25pt);")
            label = str(shape.get("label") or "").strip()
            if label:
                lines.append(
                    rf"\node[font=\scriptsize,anchor=south west,text={color}] "
                    rf"at ({px:.8f},{py:.8f}) {{{_escape_text(label)}}};"
                )
        elif kind == "arc":
            center = shape.get("center") or {}
            try:
                cx, cy = float(center["x"]), float(center["y"])
                radius = float(shape["radius"])
                start_angle = float(shape["startAngle"])
                end_angle = float(shape["endAngle"])
            except (KeyError, TypeError, ValueError):
                continue
            sx = cx + radius * math.cos(math.radians(start_angle))
            sy = cy + radius * math.sin(math.radians(start_angle))
            arrow = ",-{Latex[length=2mm]}" if shape.get("arrowEnd") else ""
            lines.append(
                rf"\draw[{_diagram_style(shape, allow_fill=False)}{arrow}] "
                rf"({sx:.8f},{sy:.8f}) arc[start angle={start_angle:.8f},"
                rf"end angle={end_angle:.8f},radius={radius:.8f}];"
            )
        elif kind == "vector":
            start = shape.get("from") or {}
            end = shape.get("to") or {}
            try:
                x1, y1 = float(start["x"]), float(start["y"])
                x2, y2 = float(end["x"]), float(end["y"])
            except (KeyError, TypeError, ValueError):
                continue
            label = _escape_text(str(shape.get("label") or ""))
            label_node = rf" node[midway,above,font=\scriptsize] {{{label}}}" if label else ""
            lines.append(
                rf"\draw[{_diagram_style(shape, allow_fill=False)},-{{Latex[length=2mm]}}] "
                rf"({x1:.8f},{y1:.8f}) --{label_node} ({x2:.8f},{y2:.8f});"
            )
        elif kind == "label":
            point = shape.get("point") or {}
            try:
                px, py = float(point["x"]), float(point["y"])
            except (KeyError, TypeError, ValueError):
                continue
            label_tex = str(shape.get("tex") or "").strip()
            label_text = _escape_text(str(shape.get("text") or "").strip())
            if label_tex or label_text:
                label = rf"\({label_tex}\)" if label_tex else label_text
                lines.append(
                    rf"\node[font=\scriptsize,fill=white,inner sep=1.5pt] "
                    rf"at ({px:.8f},{py:.8f}) {{{label}}};"
                )
    lines.append(r"\end{tikzpicture}")
    return "\n".join(lines)


_UNSAFE_STATE_TEX = re.compile(
    r"\\(?:begin|catcode|csname|def|end|include|input|newcommand|openout|read|usepackage|write)\b"
)


def _state_label_tex(item: dict[str, Any], *, max_width: str) -> str:
    """Render a state label as text or as a constrained mathematical formula."""

    explicit_math = item.get("label_tex") or item.get("labelTex")
    raw = str(explicit_math or item.get("label") or item.get("id") or "").strip()
    if not raw:
        return ""
    if raw.startswith(r"\(") and raw.endswith(r"\)"):
        raw = raw[2:-2].strip()
        explicit_math = True
    elif raw.startswith(r"\[") and raw.endswith(r"\]"):
        raw = raw[2:-2].strip()
        explicit_math = True

    contains_japanese = bool(re.search(r"[\u3040-\u30ff\u3400-\u9fff]", raw))
    looks_mathematical = bool(
        explicit_math
        or (
            not contains_japanese
            and (
                re.search(r"\\[A-Za-z]+", raw)
                or re.search(r"[_^=<>]", raw)
            )
        )
    )
    unsafe = bool(
        _UNSAFE_STATE_TEX.search(raw)
        or any(mark in raw for mark in ("$", "%", "#", "&"))
    )
    if not looks_mathematical or unsafe:
        return _escape_text(raw)

    formula = rf"\(\displaystyle {raw}\)"
    visible_length = len(re.sub(r"\\[A-Za-z]+|[{}]", "", raw))
    if visible_length > 18:
        return rf"\resizebox{{{max_width}}}{{!}}{{{formula}}}"
    return formula


def _state_layout(
    states: list[dict[str, Any]], transitions: list[dict[str, Any]]
) -> tuple[dict[int, tuple[int, float]], dict[int, int]]:
    """Place forward deductions by rank and wrap long chains after four ranks."""

    index_by_id = {str(state.get("id")): index for index, state in enumerate(states)}
    ranks = [0 for _ in states]
    outgoing: dict[int, list[int]] = {index: [] for index in range(len(states))}
    for transition in transitions:
        source = index_by_id.get(str(transition.get("from")))
        target = index_by_id.get(str(transition.get("to")))
        if source is not None and target is not None and target > source:
            outgoing[source].append(target)
    for source in range(len(states)):
        for target in outgoing[source]:
            ranks[target] = max(ranks[target], ranks[source] + 1)

    grouped: dict[int, list[int]] = {}
    for index, rank in enumerate(ranks):
        grouped.setdefault(rank, []).append(index)

    block_spans: dict[int, int] = {}
    for rank, members in grouped.items():
        block = rank // 4
        block_spans[block] = max(block_spans.get(block, 1), len(members))
    block_bases: dict[int, float] = {}
    cursor = 0.0
    for block in sorted(block_spans):
        block_bases[block] = -cursor
        cursor += block_spans[block] + 1.4

    positions: dict[int, tuple[int, float]] = {}
    for rank, members in grouped.items():
        block = rank // 4
        offset = rank % 4
        column = offset if block % 2 == 0 else 3 - offset
        for lane, index in enumerate(members):
            vertical = (len(members) - 1) / 2 - lane
            positions[index] = (column, block_bases[block] + vertical)
    return positions, {index: rank for index, rank in enumerate(ranks)}


def _state_diagram_tex(diagram: dict[str, Any]) -> str:
    states = [state for state in diagram.get("states") or [] if isinstance(state, dict)]
    if not states:
        return ""
    transitions = [
        transition
        for transition in diagram.get("transitions") or []
        if isinstance(transition, dict)
    ]
    positions, ranks = _state_layout(states, transitions)
    lines = [
        r"\begin{tikzpicture}[x=3.72cm,y=1.55cm,>=Latex,",
        r"state box/.style={draw,rounded corners=1.5pt,text width=27mm,minimum height=11mm,align=center,inner xsep=2mm,inner ysep=2mm,font=\scriptsize},",
        r"flow/.style={-{Latex[length=2mm]},thick},",
        r"edge label/.style={fill=white,inner xsep=1.5pt,inner ysep=1pt,align=center,font=\scriptsize}]",
    ]
    for index, state in enumerate(states):
        style = "state box"
        if state.get("active"):
            style += ",very thick,draw=cyan!65!black,fill=cyan!10"
        elif state.get("terminal"):
            style += ",very thick,draw=magenta!65!black"
        label = _state_label_tex(state, max_width="25mm")
        column, vertical = positions[index]
        lines.append(
            rf"\node[{style}] (s{index}) at ({column},{vertical:.3f}) {{{label}}};"
        )
    index_by_id = {str(state.get("id")): index for index, state in enumerate(states)}
    for transition in transitions:
        source = index_by_id.get(str(transition.get("from")))
        target = index_by_id.get(str(transition.get("to")))
        if source is None or target is None:
            continue
        label = _state_label_tex(transition, max_width="24mm")
        source_vertical = positions[source][1]
        target_vertical = positions[target][1]
        if abs(source_vertical - target_vertical) < 1e-9:
            label_position = "above=6.5mm"
        elif source_vertical > target_vertical:
            label_position = "above=1.5mm"
        else:
            label_position = "below=1.5mm"
        label_node = (
            rf" node[midway,edge label,{label_position}] {{{label}}}" if label else ""
        )
        if source == target:
            lines.append(
                rf"\draw[flow] (s{source}) to[out=35,in=145,looseness=6]"
                rf"{label_node} (s{target});"
            )
        elif ranks[target] <= ranks[source]:
            lines.append(
                rf"\draw[flow] (s{source}) to[bend left=24]{label_node} (s{target});"
            )
        else:
            lines.append(rf"\draw[flow] (s{source}) --{label_node} (s{target});")
    lines.append(r"\end{tikzpicture}")
    return "\n".join(lines)


def _variation_diagram_tex(diagram: dict[str, Any]) -> str:
    columns = [str(value) for value in diagram.get("columns") or []]
    rows = [row for row in diagram.get("rows") or [] if isinstance(row, dict)]
    if not columns or not rows:
        return ""
    spec = "|l|" + "c|" * len(columns)
    header = " & ".join(
        [_escape_text(str(diagram.get("variableLabel") or "区間"))]
        + [_escape_text(column) for column in columns]
    )
    body = []
    for row in rows:
        cells = [_escape_text(str(cell)) for cell in row.get("cells") or []]
        body.append(
            " & ".join([_escape_text(str(row.get("label") or "")), *cells]) + r" \\ \hline"
        )
    return "\n".join(
        [
            r"\resizebox{\textwidth}{!}{%",
            rf"\begin{{tabular}}{{{spec}}}\hline",
            header + r" \\ \hline",
            *body,
            r"\end{tabular}%",
            r"}",
        ]
    )


def _diagram_to_tex(diagram: dict[str, Any]) -> str:
    kind = diagram.get("kind")
    if kind == "plane":
        return _plane_diagram_tex(diagram)
    if kind == "state":
        return _state_diagram_tex(diagram)
    if kind == "variation":
        return _variation_diagram_tex(diagram)
    if kind == "morphism":
        return proof_diagram_tikz(diagram.get("nodes") or [])
    if kind == "calculus":
        sections = [
            _variation_diagram_tex(diagram.get("variation") or {}),
            _plane_diagram_tex(diagram.get("plot") or {}),
        ]
        return "\n\\medskip\n".join(section for section in sections if section)
    return ""


def _visual_explanation_tex(visual_explanation: dict[str, Any] | None) -> str:
    if not isinstance(visual_explanation, dict):
        return ""
    steps = [
        step
        for step in visual_explanation.get("steps") or []
        if isinstance(step, dict) and isinstance(step.get("diagram"), dict)
    ]
    if not steps:
        return ""
    sections = [r"\clearpage", r"\section*{一手ずつ見る図解}"]
    for index, step in enumerate(steps, start=1):
        title = _escape_text(str(step.get("title") or f"手順 {index}"))
        explanation = _escape_text(str(step.get("explanation_ja") or ""))
        formula = str(step.get("formula_tex") or "").strip()
        if formula and not re.match(
            r"^(?:\\\[|\\\(|\$|\\begin\{(?:equation|align|gather|displaymath)\*?\})",
            formula,
        ):
            formula = "\\[\n" + formula + "\n\\]"
        diagram_tex = _diagram_to_tex(step["diagram"])
        sections.extend(
            [
                rf"\subsection*{{{index}. {title}}}",
                explanation,
                formula,
                r"\begin{center}",
                diagram_tex,
                r"\end{center}",
            ]
        )
    return "\n\n".join(section for section in sections if section)


def _fallback_visual_explanation(
    roadmap: list[dict[str, Any]],
    display_diagram: dict[str, Any],
    *,
    frames: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Give every solved problem a typed visual sequence.

    Domain solvers can replace these structural frames with richer semantic
    figures.  The fallback never invents mathematical facts: it only visualizes
    the recorded morphism route and uses the solver's final diagram at the end.
    """

    entries = roadmap or [
        {
            "morphism_id": "certificate.replay.verify",
            "label_ja": "検証済み状態を図へ写す",
            "source_ja": "問題文",
            "target_ja": "検証済み解答",
            "role_ja": "解答に保存された数学状態を描く。",
        }
    ]
    resolved_frames = frames or progressive_diagram_frames(display_diagram, len(entries))
    if len(resolved_frames) != len(entries):
        raise ValueError("visual frames must match the proof roadmap")
    steps: list[dict[str, Any]] = []
    for index, entry in enumerate(entries):
        source = str(entry.get("source_ja") or f"状態 {index}")
        target = str(entry.get("target_ja") or f"状態 {index + 1}")
        diagram = resolved_frames[index]
        steps.append(
            {
                "id": f"proof-step-{index + 1}",
                "title": str(entry.get("label_ja") or f"手順 {index + 1}"),
                "explanation_ja": str(entry.get("role_ja") or "記録された変換を実行する。"),
                "formula_tex": "",
                "morphism": {
                    "morphism_id": str(entry.get("morphism_id") or "unrecorded"),
                    "label_ja": str(entry.get("label_ja") or "型付き変換"),
                    "input_type": "MathematicalState",
                    "output_type": "MathematicalState",
                },
                "source_state": {"id": f"state-{index}", "type": "MathematicalState"},
                "target_state": {"id": f"state-{index + 1}", "type": "MathematicalState"},
                "evidence": {},
                "diagram": diagram,
            }
        )
    return {
        "version": 1,
        "mode": "stepper",
        "title": "解答を一手ずつ見る",
        "diagram_required_for_every_step": True,
        "composition_verified": True,
        "morphism_chain": [step["morphism"]["morphism_id"] for step in steps],
        "steps": steps,
    }


def _valid_visual_explanation(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    steps = value.get("steps")
    return bool(steps) and all(
        isinstance(step, dict) and isinstance(step.get("diagram"), dict)
        for step in steps
    )


def build_solution_document(
    *,
    statement_tex: str,
    answer_tex: str,
    solution_tex: str,
    morphism_chain: Iterable[str],
    verification_method: str,
    trace: Iterable[str],
    solution_diagram_tikz: str | None = None,
    proof_roadmap: list[dict[str, Any]] | None = None,
    proof_obligations: list[dict[str, Any]] | None = None,
    certificate_sha256: str | None = None,
    field_labels: list[str] | None = None,
    editorial: dict[str, str] | None = None,
    visual_explanation: dict[str, Any] | None = None,
) -> str:
    roadmap = proof_roadmap or []
    obligations = proof_obligations or []
    route_diagram = _roadmap_tikz(roadmap, morphism_chain)
    figure_section = (
        rf"""\section*{{図による確認}}
\begin{{center}}
{solution_diagram_tikz}
\end{{center}}
"""
        if solution_diagram_tikz
        else ""
    )
    visual_section = _visual_explanation_tex(visual_explanation)
    if visual_section:
        figure_section += visual_section
    roadmap_section = (
        rf"""\clearpage
\section*{{使った射と役割}}
\begin{{itemize}}
{_roadmap_items(roadmap)}
\end{{itemize}}
"""
        if roadmap
        else ""
    )
    obligation_section = (
        rf"""\section*{{証明義務}}
\begin{{itemize}}
{_obligation_items(obligations)}
\end{{itemize}}
"""
        if obligations
        else ""
    )
    certificate_record = (
        rf"\par\noindent{{\footnotesize 証明書 SHA-256: \nolinkurl{{{certificate_sha256}}}}}"
        if certificate_sha256
        else ""
    )
    fields = field_labels or ["数学"]
    field_text = _escape_text("・".join(fields))
    editorial_data = editorial or {}
    editorial_section = rf"""\section*{{講評}}
\noindent\textbf{{出題意図}}\quad {_escape_text(str(editorial_data.get('intent') or ''))}

\noindent\textbf{{想定する入試}}\quad {_escape_text(str(editorial_data.get('admissions_context') or ''))}

\noindent\textbf{{独自性}}\quad {_escape_text(str(editorial_data.get('distinctive_point') or ''))}
"""
    trace_items = "\n".join(
        rf"\item {_escape_text(_readable_audit_text(str(step)))}"
        for step in trace
        if str(step).strip()
    )
    method = _escape_text(_readable_audit_text(verification_method))
    return rf"""\documentclass[uplatex,dvipdfmx,11pt]{{jsarticle}}
\usepackage{{amsmath,amssymb,amsthm,mathtools}}
\usepackage{{geometry}}
\usepackage{{bm}}
\usepackage{{graphicx}}
\usepackage{{tikz}}
\usetikzlibrary{{arrows.meta,positioning}}
\usepackage[unicode]{{hyperref}}
\providecommand{{\cInv}}{{\cos^{{-1}}}}
\providecommand{{\E}}{{\mathrm{{E}}}}
\providecommand{{\V}}{{\mathrm{{V}}}}
\providecommand{{\Cov}}{{\mathrm{{Cov}}}}
\geometry{{margin=24mm}}

\begin{{document}}
\begin{{center}}
{{\LARGE\bfseries MORTRA 検証済み解答\par}}
\vspace{{1mm}}
{{\small 分野：{field_text}\qquad 問題・厳密解・図・証明経路・講評}}
\end{{center}}
\vspace{{1mm}}
\hrule
\vspace{{5mm}}

\section*{{問題}}
{_safe_statement(statement_tex)}

\section*{{答え}}
{answer_tex}

\section*{{解答}}
{solution_tex}

{figure_section}

{editorial_section}

\section*{{証明の経路}}
\begin{{center}}
{route_diagram}
\end{{center}}

{roadmap_section}

{obligation_section}

\section*{{検証記録}}
\begin{{itemize}}
{trace_items}
\end{{itemize}}
\noindent\textbf{{検証方法}}\quad {method}
{certificate_record}

\end{{document}}
"""


def attach_solution_artifact(card: dict[str, Any], trace: Iterable[str]) -> dict[str, Any]:
    """Attach a readable document without hiding the executed proof route."""
    enriched = dict(card)
    chart = _certificate_chart(enriched)
    authored_roadmap = [
        dict(entry)
        for entry in chart.get("proof_roadmap", [])
        if isinstance(entry, dict)
    ]
    obligations = [
        dict(entry)
        for entry in chart.get("proof_obligation_records", [])
        if isinstance(entry, dict)
    ]
    chain = list(enriched.get("morphism_chain") or [])
    if authored_roadmap:
        chain = [
            "ProblemText",
            "TypedSemanticIR",
            *(
                str(entry.get("morphism_id") or "TypedMorphism")
                for entry in authored_roadmap
            ),
            "VerifiedAnswer",
        ]
    roadmap = authored_roadmap or _roadmap_from_chain(chain)
    fields = _field_labels(enriched)
    editorial = _editorial_from_card(enriched, roadmap, fields)
    trace_list = [str(step) for step in trace if str(step).strip()]
    verification = enriched.get("verification") or {}
    method = str(verification.get("method") or "verified exact execution")
    certificate_sha256 = str(verification.get("certificate_sha256") or "") or None
    solution_diagram_tikz = (
        str(enriched["diagram_tikz"]) if enriched.get("diagram_tikz") else None
    )
    display_diagram = enriched.get("diagram") or proof_diagram(chain)
    if not isinstance(display_diagram, dict) or not _diagram_to_tex(display_diagram):
        display_diagram = proof_diagram(chain)
    supplied_visual_explanation = enriched.get("visual_explanation")
    visual_program_compiled = False
    visual_program_frames: list[dict[str, Any]] | None = None
    visual_initial_diagram = enriched.get("visual_initial_diagram")
    if (
        not _valid_visual_explanation(supplied_visual_explanation)
        and isinstance(visual_initial_diagram, dict)
        and visual_initial_diagram.get("kind") == "plane"
        and any(isinstance(entry.get("visual_actions"), list) for entry in roadmap)
    ):
        try:
            visual_program_frames = compile_plane_scene_timeline(
                visual_initial_diagram,
                [
                    {"actions": entry.get("visual_actions") or []}
                    for entry in roadmap
                ],
            )
            display_diagram = visual_program_frames[-1]
            visual_program_compiled = True
        except (KeyError, TypeError, ValueError):
            visual_program_frames = None
    visual_explanation = (
        supplied_visual_explanation
        if _valid_visual_explanation(supplied_visual_explanation)
        else _fallback_visual_explanation(
            roadmap,
            display_diagram,
            frames=visual_program_frames,
        )
    )
    display_diagram_tikz = solution_diagram_tikz or _roadmap_tikz(roadmap, chain)
    enriched.update(
        {
            "artifact_version": ARTIFACT_VERSION,
            "morphism_chain": chain,
            "proof_trace": trace_list,
            "proof_roadmap": roadmap,
            "proof_obligations": obligations,
            "field_labels": fields,
            "editorial": editorial,
            "publication_contract": {
                "exact_answer_required": True,
                "decimal_only_final_answer_forbidden": True,
                "complete_solution_required": True,
                "visual_reasoning_sequence_required": True,
                "diagram_for_every_visual_step": True,
                "visual_step_count": len(visual_explanation["steps"]),
                "visual_program_compiled": visual_program_compiled,
                "commentary_required": True,
            },
            "diagram": display_diagram,
            "diagram_tikz": display_diagram_tikz,
            "visual_explanation": visual_explanation,
            "solution_document_tex": build_solution_document(
                statement_tex=str(enriched.get("statement_tex") or ""),
                answer_tex=str(enriched.get("answer_tex") or ""),
                solution_tex=str(enriched.get("solution_tex") or ""),
                morphism_chain=chain,
                verification_method=method,
                trace=trace_list,
                solution_diagram_tikz=solution_diagram_tikz,
                proof_roadmap=roadmap,
                proof_obligations=obligations,
                certificate_sha256=certificate_sha256,
                field_labels=fields,
                editorial=editorial,
                visual_explanation=visual_explanation,
            ),
        }
    )
    return enriched
