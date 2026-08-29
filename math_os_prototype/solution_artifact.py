"""Build a reproducible TeX solution artifact from MORTRA's verified output.

The renderer is intentionally downstream of verification.  It receives only
the statement, the verified answer, the solver-produced explanation, and the
executed morphism chain.  It therefore cannot invent mathematical content.
"""

from __future__ import annotations

import re
from typing import Any, Iterable


ARTIFACT_VERSION = 2


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
    return re.sub(r"\\(?:begin|end)\{(?:enumerate|itemize)\}", "", standalone)


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
    "TypedSemanticIR": "型付き意味表現",
    "VerifiedAnswer": "検証済み解答",
}


def _display_stage_ja(stage: str) -> str:
    return _STAGE_LABELS_JA.get(stage, stage.replace("_", " "))


def _roadmap_from_chain(chain: Iterable[str]) -> list[dict[str, str]]:
    """Expose the executed chain when a solver has no authored route prose yet."""
    nodes = _chain_nodes(chain)
    roadmap: list[dict[str, str]] = []
    for index in range(1, len(nodes)):
        morphism_id = nodes[index]
        if morphism_id == "TypedSemanticIR":
            label = "問題文を型付き意味へ展開"
            role = "指示対象、量化、型を確定し、後段が実行できる中間表現へ移す。"
        elif morphism_id == "VerifiedAnswer":
            label = "証明書を再生して結論を認証"
            role = "実行記録と証明義務を再生し、元の問題条件に対する結論を確定する。"
            morphism_id = "certificate.replay.verify"
        else:
            label = _display_stage_ja(morphism_id)
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
{_escape_text(str(entry.get('role_ja') or '型を保ったまま中間表現を変換する。'))}\\
\texttt{{{_escape_text(str(entry.get('morphism_id') or 'unrecorded'))}}}"""
        for index, entry in enumerate(roadmap, start=1)
    )


def _obligation_items(obligations: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for item in obligations:
        status = str(item.get("status") or "unknown")
        readable_status = "検証済み" if status == "verified" else status
        lines.append(
            rf"\item \textbf{{{_escape_text(str(item.get('id') or '?'))}}}: "
            rf"{_escape_text(str(item.get('claim_ja') or '証明義務'))} "
            rf"（{_escape_text(readable_status)}）"
        )
    return "\n".join(lines)


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
    trace_items = "\n".join(
        rf"\item {_escape_text(str(step))}" for step in trace if str(step).strip()
    )
    method = _escape_text(verification_method)
    return rf"""\documentclass[uplatex,dvipdfmx,11pt]{{jsarticle}}
\usepackage{{amsmath,amssymb,amsthm,mathtools}}
\usepackage{{geometry}}
\usepackage{{bm}}
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
{{\small 問題・解答・図・証明経路・検証証明書}}
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
\noindent\texttt{{{method}}}
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
    trace_list = [str(step) for step in trace if str(step).strip()]
    verification = enriched.get("verification") or {}
    method = str(verification.get("method") or "verified exact execution")
    certificate_sha256 = str(verification.get("certificate_sha256") or "") or None
    solution_diagram_tikz = (
        str(enriched["diagram_tikz"]) if enriched.get("diagram_tikz") else None
    )
    display_diagram = enriched.get("diagram") or proof_diagram(chain)
    display_diagram_tikz = solution_diagram_tikz or _roadmap_tikz(roadmap, chain)
    enriched.update(
        {
            "artifact_version": ARTIFACT_VERSION,
            "morphism_chain": chain,
            "proof_trace": trace_list,
            "proof_roadmap": roadmap,
            "proof_obligations": obligations,
            "diagram": display_diagram,
            "diagram_tikz": display_diagram_tikz,
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
            ),
        }
    )
    return enriched
