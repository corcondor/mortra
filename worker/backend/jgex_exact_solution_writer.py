"""Render a human-auditable Japanese solution from one exact certificate.

This writer does not invent proof steps.  Every sentence is a deterministic
projection of a replayed field in ``JGEXExactObligation`` so the readable
solution and the machine certificate cannot silently diverge.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class ExactSolutionStep:
    title: str
    text: str
    certificate_fields: tuple[str, ...]


@dataclass(frozen=True)
class JGEXExactSolutionArtifact:
    status: str
    statement_jgex: str
    conclusion_ja: str
    steps: tuple[ExactSolutionStep, ...]
    proof_identity: str
    machine_appendix: dict[str, Any]
    certificate_sha256: str
    solution_sha256: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["steps"] = [asdict(step) for step in self.steps]
        return payload

    def to_markdown(self) -> str:
        lines = [
            "# MORTRA 模範解答",
            "",
            "## 問題",
            "",
            "```text",
            self.statement_jgex,
            "```",
            "",
            "## 解答",
            "",
        ]
        for index, step in enumerate(self.steps, start=1):
            lines.extend((f"### {index}. {step.title}", "", step.text, ""))
        lines.extend(
            (
                "## 結論",
                "",
                self.conclusion_ja,
                "",
                "## 検証情報",
                "",
                f"- 状態: `{self.status}`",
                f"- 証明恒等式: `{self.proof_identity}`",
                f"- 証明書 SHA-256: `{self.certificate_sha256}`",
                f"- 解答 SHA-256: `{self.solution_sha256}`",
                "",
                "## 機械検証付録",
                "",
                "### 目標多項式",
                "",
                "```text",
                str(self.machine_appendix.get("goal_polynomial", "")),
                "```",
                "",
                "### 構成方程式",
                "",
                "```text",
                "\n".join(
                    map(str, self.machine_appendix.get("construction_equations", ()))
                ),
                "```",
                "",
                "### Groebner 基底",
                "",
                "```text",
                "\n".join(map(str, self.machine_appendix.get("groebner_basis", ()))),
                "```",
                "",
                "### 商と余り",
                "",
                "```text",
                "\n".join(
                    map(str, self.machine_appendix.get("quotient_certificate", ()))
                ),
                f"remainder = {self.machine_appendix.get('remainder', '')}",
                "```",
                "",
            )
        )
        return "\n".join(lines)


def _sequence(value: object) -> tuple[object, ...]:
    return tuple(value) if isinstance(value, (list, tuple)) else ()


def _relation_conclusion(channel: str, points: Sequence[object]) -> str:
    p = tuple(map(str, points))
    if channel == "midp" and len(p) == 3:
        return f"したがって、{p[0]} は線分 {p[1]}{p[2]} の中点である。"
    if channel == "coll" and len(p) >= 3:
        return "したがって、" + "、".join(p) + " は一直線上にある。"
    if channel == "cyclic" and len(p) >= 4:
        return "したがって、" + "、".join(p) + " は同一円周上にある。"
    if channel == "cong" and len(p) == 4:
        return f"したがって、|{p[0]}{p[1]}|=|{p[2]}{p[3]}| である。"
    if channel == "perp" and len(p) == 4:
        return f"したがって、{p[0]}{p[1]} と {p[2]}{p[3]} は垂直である。"
    if channel == "para" and len(p) == 4:
        return f"したがって、{p[0]}{p[1]} と {p[2]}{p[3]} は平行である。"
    if channel in {"simtri", "simtrir"} and len(p) == 6:
        return (
            f"したがって、三角形 {p[0]}{p[1]}{p[2]} と"
            f"三角形 {p[3]}{p[4]}{p[5]} は相似である。"
        )
    return f"したがって、{channel}({', '.join(p)}) が成り立つ。"


def _joined_lines(values: Sequence[object], *, limit: int = 12) -> str:
    rendered = [str(value) for value in values[:limit]]
    if len(values) > limit:
        rendered.append(f"ほか {len(values) - limit} 式")
    return "\n".join(f"  {index + 1}. {value}" for index, value in enumerate(rendered))


_CONSTRUCTION_JA = {
    "triangle": "三角形の3頂点を置く",
    "quadrangle": "四角形の4頂点を置く",
    "segment": "独立な2点から線分を置く",
    "on_line": "指定された直線上に点を取る",
    "on_circle": "指定された円上に点を取る",
    "midpoint": "中点条件を置く",
    "mirror": "点対称の条件を置く",
    "reflect": "直線に関する対称点の条件を置く",
    "foot": "垂線の足を取る",
    "circumcenter": "3点から等距離となる外心条件を置く",
    "orthocenter": "3本の高さに対応する垂直条件を置く",
    "eqdistance": "2つの距離が等しい条件を置く",
}


def _construction_outline(certificate: Mapping[str, Any]) -> tuple[str, ...]:
    vocabulary = tuple(map(str, _sequence(certificate.get("construction_vocabulary"))))
    return tuple(_CONSTRUCTION_JA.get(item, item) for item in vocabulary)


def build_jgex_exact_solution_artifact(
    statement_jgex: str,
    certificate: Mapping[str, Any],
) -> JGEXExactSolutionArtifact:
    exact_replay = certificate.get("exact_replay") is True
    vacuous = certificate.get("vacuous_unit_ideal") is True
    consistency = str(certificate.get("construction_consistency", ""))
    verified = exact_replay and not vacuous and consistency != "unit_ideal_without_nonempty_witness"
    channel = str(certificate.get("channel", "relation"))
    points = _sequence(certificate.get("points"))
    steps: list[ExactSolutionStep] = []

    normalizations = _sequence(certificate.get("normalization_assumptions"))
    if normalizations:
        steps.append(
            ExactSolutionStep(
                "座標設定",
                "図形の自由度を保つ次の座標規格化を用いる。\n"
                + _joined_lines(normalizations),
                ("normalization_assumptions",),
            )
        )

    equations = _sequence(certificate.get("reduced_construction_equations"))
    construction_outline = _construction_outline(certificate)
    steps.append(
        ExactSolutionStep(
            "作図条件の式",
            (
                f"作図条件を {len(equations)} 本の多項式制約へ変換する。"
                + (
                    " 用いた幾何学的条件は次の通りである。\n"
                    + _joined_lines(construction_outline)
                    if construction_outline
                    else ""
                )
            ),
            ("construction_equations", "reduced_construction_equations"),
        )
    )

    local = _sequence(certificate.get("local_lemma_certificates"))
    structural = _sequence(certificate.get("structural_lemma_certificates"))
    if local or structural:
        local_summary = [
            f"{item.get('variable', '?')} を局所的に消去"
            for item in local
            if isinstance(item, Mapping)
        ]
        structural_summary = [
            (
                f"構造補題: {item.get('theorem', '?')} -> {item.get('output', '?')} "
                f"（合成再生={item.get('composition_replayed') is True}）"
            )
            for item in structural
            if isinstance(item, Mapping)
        ]
        steps.append(
            ExactSolutionStep(
                "中間補題",
                "大域消去の前に、次の局所証明を再生する。\n"
                + _joined_lines((*local_summary, *structural_summary), limit=8),
                ("local_lemma_certificates", "structural_lemma_certificates"),
            )
        )

    decomposition = certificate.get("goal_decomposition_certificate")
    if isinstance(decomposition, Mapping):
        components = _sequence(decomposition.get("component_polynomials"))
        remainders = _sequence(decomposition.get("component_remainders"))
        component_lines = [
            f"{component} = 0（余り {remainders[index] if index < len(remainders) else '?'}）"
            for index, component in enumerate(components)
        ]
        steps.append(
            ExactSolutionStep(
                "型付き中間命題",
                f"{decomposition.get('theorem', 'goal decomposition')} により目標を分解する。\n"
                + _joined_lines(component_lines),
                ("goal_decomposition_certificate",),
            )
        )

    goal = str(certificate.get("goal_polynomial", "?"))
    multiplier = str(certificate.get("saturation_multiplier", "1"))
    basis = _sequence(certificate.get("groebner_basis"))
    quotients = _sequence(certificate.get("quotient_certificate"))
    remainder = str(certificate.get("remainder", "?"))
    proof_identity = f"M G = sum_{{i=1}}^{{{len(basis)}}} q_i g_i + {remainder}"
    steps.append(
        ExactSolutionStep(
            "最終検証",
            (
                f"Groebner基底 {len(basis)} 本と商 {len(quotients)} 本を用いて次の恒等式を再生する。\n"
                f"  {proof_identity}\n"
                f"最終余りは {remainder}、証明書再生は {exact_replay} である。"
            ),
            (
                "goal_polynomial",
                "groebner_basis",
                "quotient_certificate",
                "remainder",
                "saturation_multiplier",
                "exact_replay",
            ),
        )
    )

    conclusion = (
        _relation_conclusion(channel, points)
        if verified
        else "構成の存在と証明書の再生を同時に確認できないため、結論は認証しない。"
    )
    material = {
        "statement_jgex": statement_jgex.strip(),
        "conclusion_ja": conclusion,
        "steps": [asdict(step) for step in steps],
        "proof_identity": proof_identity,
        "certificate_sha256": str(certificate.get("certificate_sha256", "")),
    }
    machine_appendix = {
        "goal_polynomial": goal,
        "saturation_multiplier": multiplier,
        "construction_equations": list(map(str, equations)),
        "groebner_basis": list(map(str, basis)),
        "quotient_certificate": list(map(str, quotients)),
        "remainder": remainder,
    }
    material["machine_appendix"] = machine_appendix
    solution_hash = hashlib.sha256(
        json.dumps(material, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return JGEXExactSolutionArtifact(
        status="verified" if verified else "rejected",
        statement_jgex=statement_jgex.strip(),
        conclusion_ja=conclusion,
        steps=tuple(steps),
        proof_identity=proof_identity,
        machine_appendix=machine_appendix,
        certificate_sha256=str(certificate.get("certificate_sha256", "")),
        solution_sha256=solution_hash,
    )


__all__ = [
    "ExactSolutionStep",
    "JGEXExactSolutionArtifact",
    "build_jgex_exact_solution_artifact",
]
