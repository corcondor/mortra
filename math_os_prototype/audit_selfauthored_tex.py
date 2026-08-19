"""Parse every self-authored TeX problem and attach available answer evidence."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from math_os_prototype.category_semantics import compile_typed_semantic_graph
    from math_os_prototype.creative_tex_corpus import extract_itembox_problems
    from math_os_prototype.domain_registry import DomainRegistry
    from math_os_prototype.formal_language import compile_formal_ir
    from math_os_prototype.latex_frontend import (
        normalize_latex_text,
        split_tex_text_math,
        strip_comments,
    )
    from math_os_prototype.structural_parser import analyze_structure
    from math_os_prototype.typed_definition_kernel import compile_typed_definition_ir
except ImportError:  # pragma: no cover
    from category_semantics import compile_typed_semantic_graph
    from creative_tex_corpus import extract_itembox_problems
    from domain_registry import DomainRegistry
    from formal_language import compile_formal_ir
    from latex_frontend import normalize_latex_text, split_tex_text_math, strip_comments
    from structural_parser import analyze_structure
    from typed_definition_kernel import compile_typed_definition_ir


ANSWER_HEADING = re.compile(r"\\section\*\{問題(?P<number>\d+)解答\}")
SECTION_BOUNDARY = re.compile(
    r"\\(?:section|subsection|subsubsection)\*?\{(?P<title>[^{}]*)\}"
)
ENV_BOUNDARY = re.compile(
    r"\\(?:begin|end)\{(?:proof|lemma|claim|enumerate|align\*?|equation\*?)\}"
)
CONCLUSION_MARKERS = ("よって", "したがって", "従って", "ゆえに", "以上より", "これより")
DEFINITION_MARKERS = ("とおく", "と定め", "とする", "を置く", "定義")
META_MORPHISMS = {
    "And", "Or", "Not", "Implies", "Forall", "Exists", "Equals", "Member",
    "Satisfies", "Find", "Prove", "Decide", "Equation", "SetComprehension",
}

# These are design-level lenses, not problem families.  They describe why a
# construction is interesting across domains and are intentionally many-to-many.
DESIGN_LENSES: tuple[dict[str, Any], ...] = (
    {
        "id": "moving_configuration_to_global_region",
        "label": "動く配置から大域的な領域・軌跡を取り出す",
        "surface": ("通過領域", "軌跡", "動くとき", "自由に動か", "滑ることなく", "正射影"),
        "morphisms": ("Locus", "Image", "Projection", "Area"),
        "theory": ("配置空間", "包絡線", "Minkowski和", "実代数幾何"),
    },
    {
        "id": "discrete_continuous_bridge",
        "label": "離散対象を連続量・図形へ移す",
        "surface": ("格子点", "素数", "整数", "自然数", "床", "小数部分", "回帰直線"),
        "co_surface": ("面積", "体積", "角", "曲線", "円", "極限", "相関"),
        "morphisms": ("ModResidue", "Lattice", "Regression", "Limit", "Integral"),
        "theory": ("数論幾何", "格子点幾何", "漸近解析", "測度への極限"),
    },
    {
        "id": "symmetry_to_dimension_reduction",
        "label": "対称性を商にして自由度を落とす",
        "surface": ("正三角形", "正方形", "正六角形", "正十二面体", "正$n$角形", "正 \\(n\\) 角形", "置換", "相異なる3点"),
        "morphisms": ("Symmetric", "Permutation", "Rotation", "RegularPolygon"),
        "theory": ("群作用", "対称式", "軌道空間", "不変量論"),
    },
    {
        "id": "representation_change",
        "label": "同じ対象を別表現へ移して可解化する",
        "surface": ("複素数平面", "根", "変換", "折り返", "回転", "積分方程式", "回帰直線"),
        "morphisms": ("Coordinate", "Complex", "Root", "Image", "Differentiation", "Polynomial"),
        "theory": ("座標化", "複素表示", "Vieta写像", "微分による方程式化"),
    },
    {
        "id": "iteration_and_fixed_structure",
        "label": "反復から固定点・極限構造を抽出する",
        "surface": ("不動点", "反復", "漸化式", "数列", "関数列", "f_{n+1}", "a_{n+1}", "x_{n+2}"),
        "morphisms": ("Recurrence", "Iteration", "FixedPoint", "Limit"),
        "theory": ("離散力学系", "縮小写像", "スペクトル", "安定性"),
    },
    {
        "id": "arithmetic_rigidity",
        "label": "連続的な候補を整数・素数条件で剛直化する",
        "surface": ("素数", "整数", "自然数", "格子点", "有理数", "無理数", "約数", "gcd", "\\gcd"),
        "morphisms": ("Divides", "GCD", "ModResidue", "Diophantine"),
        "theory": ("合同式", "Diophantine方程式", "代数的整数", "局所障害"),
    },
    {
        "id": "boundary_extremum",
        "label": "可動範囲の境界を特定して極値・測度を得る",
        "surface": ("最大値", "最小値", "値域", "存在範囲", "通過領域", "囲まれた領域", "面積"),
        "morphisms": ("Maximum", "Minimum", "Range", "Boundary", "Area"),
        "theory": ("凸解析", "境界パラメータ化", "半代数的消去", "変分"),
    },
    {
        "id": "asymptotic_renormalization",
        "label": "発散・退化を尺度変更して有限な構造として観測する",
        "surface": ("lim", "\\lim", "極限", "n\\to\\infty", "theta \\to 0", "\\theta \\to 0"),
        "morphisms": ("Limit", "Scaling", "Normalization"),
        "theory": ("漸近解析", "スケーリング極限", "局所線形化"),
    },
    {
        "id": "inverse_existence_design",
        "label": "答を計算せず、条件を満たす対象の存在・分類を問う",
        "surface": ("存在するか", "存在しない", "すべて求めよ", "全て求めよ", "必要十分条件", "示せ"),
        "morphisms": ("Exists", "Classify", "Prove"),
        "theory": ("構成問題", "反証", "分類", "存在障害"),
    },
)


def analyze_design_lenses(statement: str, graph: dict[str, Any]) -> list[dict[str, Any]]:
    """Return auditable cross-domain design evidence for one statement."""
    morphisms = morphism_names(graph)
    lowered = statement.lower()
    out: list[dict[str, Any]] = []
    for lens in DESIGN_LENSES:
        surface_hits = [term for term in lens.get("surface", ()) if term.lower() in lowered]
        co_terms = lens.get("co_surface", ())
        co_hits = [term for term in co_terms if term.lower() in lowered]
        morphism_hits = [
            name for name in morphisms
            if any(token.lower() in name.lower() for token in lens.get("morphisms", ()))
        ]
        if co_terms and surface_hits and not co_hits and not morphism_hits:
            continue
        if not surface_hits and not morphism_hits:
            continue
        out.append({
            "id": lens["id"],
            "label": lens["label"],
            "surface_evidence": surface_hits,
            "semantic_evidence": morphism_hits,
            "theoretical_background": list(lens["theory"]),
            "evidence_level": "semantic+surface" if surface_hits and morphism_hits else (
                "semantic" if morphism_hits else "surface"
            ),
        })
    return out


def extract_answer_sections(text: str) -> dict[int, str]:
    matches = list(ANSWER_HEADING.finditer(text))
    answers: dict[int, str] = {}
    document_end = text.find(r"\end{document}")
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else document_end
        if end < 0:
            end = len(text)
        answers[int(match.group("number"))] = text[match.end():end].strip()
    return answers


def split_argument_units(answer_tex: str) -> list[str]:
    source = strip_comments(answer_tex)
    source = SECTION_BOUNDARY.sub(lambda match: f"\n\n{match.group('title')}。\n\n", source)
    source = ENV_BOUNDARY.sub("\n\n", source)
    source = re.sub(r"\\item(?:\[[^\]]*\])?", "\n\n", source)
    text, _ = split_tex_text_math(source)
    text = normalize_latex_text(text)
    chunks = re.split(r"(?<=[。！？])\s*|(?:\r?\n\s*){2,}", text)
    return [re.sub(r"\s+", " ", chunk).strip() for chunk in chunks if len(chunk.strip()) >= 4]


def classify_unit(text: str, relations: list[str], index: int, total: int) -> str:
    if any(marker in text for marker in CONCLUSION_MARKERS) or index == total - 1:
        return "conclusion"
    if "補題" in text or "主張" in text:
        return "lemma"
    if any(marker in text for marker in DEFINITION_MARKERS) or relations:
        return "definition_or_derivation"
    return "explanation"


def symbols_in_relations(relations: list[str]) -> tuple[set[str], set[str]]:
    defined: set[str] = set()
    used: set[str] = set()
    for relation in relations:
        if "=" in relation and not any(token in relation for token in ("<=", ">=", "!=")):
            left, right = relation.split("=", 1)
            left_symbols = set(re.findall(r"\b[A-Za-z](?:_[A-Za-z0-9]+)?\b", left))
            right_symbols = set(re.findall(r"\b[A-Za-z](?:_[A-Za-z0-9]+)?\b", right))
            defined.update(left_symbols)
            used.update(right_symbols)
        else:
            used.update(re.findall(r"\b[A-Za-z](?:_[A-Za-z0-9]+)?\b", relation))
    return defined, used


def longest_path(node_ids: list[str], edges: list[dict[str, str]]) -> int:
    outgoing: dict[str, list[str]] = defaultdict(list)
    incoming = Counter({node_id: 0 for node_id in node_ids})
    for edge in edges:
        outgoing[edge["source"]].append(edge["target"])
        incoming[edge["target"]] += 1
    queue = deque(node_id for node_id in node_ids if incoming[node_id] == 0)
    distance = {node_id: 1 for node_id in node_ids}
    while queue:
        node_id = queue.popleft()
        for target in outgoing[node_id]:
            distance[target] = max(distance[target], distance[node_id] + 1)
            incoming[target] -= 1
            if incoming[target] == 0:
                queue.append(target)
    return max(distance.values(), default=0)


def build_answer_graph(answer_tex: str, problem_graph: dict[str, Any]) -> dict[str, Any]:
    units = split_argument_units(answer_tex)
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    latest_definition: dict[str, str] = {}

    premise_symbols: dict[str, set[str]] = {}
    seen_premises: set[str] = set()
    premise_index = 0
    for constraint in problem_graph.get("constraints", []):
        if constraint.get("kind") in {"formal_goal", "formal_status"}:
            continue
        expression = str(constraint.get("expression") or "")
        canonical = re.sub(r"[\s()]", "", expression)
        if not canonical or canonical in {"ambiguous", "partial"} or canonical in seen_premises:
            continue
        seen_premises.add(canonical)
        node_id = f"p{premise_index}"
        premise_index += 1
        variables = set(re.findall(r"\b[A-Za-z](?:_[A-Za-z0-9]+)?\b", expression))
        premise_symbols[node_id] = variables
        nodes.append({
            "id": node_id,
            "kind": "premise",
            "text": expression,
            "variables": sorted(variables),
        })

    for index, unit in enumerate(units):
        structure = analyze_structure(unit).to_dict()
        relations = [str(value) for value in structure.get("relations", [])]
        variables = set(str(value) for value in structure.get("variables", []))
        defined, relation_uses = symbols_in_relations(relations)
        used = (variables | relation_uses) - defined
        node_id = f"a{index}"
        kind = classify_unit(unit, relations, index, len(units))
        nodes.append({
            "id": node_id,
            "kind": kind,
            "text": unit,
            "relations": relations,
            "defines": sorted(defined),
            "uses": sorted(used),
        })

        dependencies: set[tuple[str, str]] = set()
        for symbol in used:
            if symbol in latest_definition:
                dependencies.add((latest_definition[symbol], "symbol_dependency"))
            else:
                for premise_id, symbols in premise_symbols.items():
                    if symbol in symbols:
                        dependencies.add((premise_id, "premise_dependency"))
        if index > 0 and any(marker in unit for marker in CONCLUSION_MARKERS):
            dependencies.add((f"a{index - 1}", "logical_consequence"))
        for source, edge_kind in sorted(dependencies):
            edges.append({"source": source, "target": node_id, "kind": edge_kind})
        for symbol in defined:
            latest_definition[symbol] = node_id

    node_ids = [node["id"] for node in nodes]
    indegree = Counter(edge["target"] for edge in edges)
    answer_ids = [node["id"] for node in nodes if node["id"].startswith("a")]
    linked_answers = sum(bool(indegree[node_id]) for node_id in answer_ids)
    return {
        "nodes": nodes,
        "edges": edges,
        "metrics": {
            "argument_units": len(units),
            "premise_nodes": len(premise_symbols),
            "dependency_edges": len(edges),
            "merge_nodes": sum(indegree[node_id] >= 2 for node_id in answer_ids),
            "longest_dependency_path": longest_path(node_ids, edges),
            "linked_answer_unit_rate": round(linked_answers / len(answer_ids), 3) if answer_ids else 0.0,
        },
        "limitations": [
            "Edges are extracted from symbol definitions and explicit Japanese consequence markers.",
            "An edge is evidence of dependency, not a machine-checked proof of logical entailment.",
        ],
    }


def compile_problem(statement_tex: str) -> tuple[dict[str, Any], dict[str, Any]]:
    structure = analyze_structure(statement_tex).to_dict()
    typed = compile_typed_definition_ir(statement_tex)
    formal = compile_formal_ir(statement_tex)
    graph = compile_typed_semantic_graph(
        statement_tex,
        structural_ir=structure,
        typed_definition_ir=typed.to_dict(),
        formal_ir=formal.to_dict(),
    ).to_dict()
    return structure, graph


def morphism_names(graph: dict[str, Any]) -> list[str]:
    return sorted({str(item.get("name")) for item in graph.get("morphisms", []) if item.get("name")})


def substantive_morphism_names(graph: dict[str, Any]) -> set[str]:
    return {
        name for name in morphism_names(graph)
        if not name.startswith("observe_") and name not in META_MORPHISMS
    }


def answer_semantic_delta(answer_tex: str, problem_graph: dict[str, Any]) -> dict[str, Any]:
    answer_structure, answer_graph = compile_problem(answer_tex)
    problem_morphisms = set(morphism_names(problem_graph))
    answer_morphisms = set(morphism_names(answer_graph))
    problem_substantive = substantive_morphism_names(problem_graph)
    answer_substantive = substantive_morphism_names(answer_graph)
    problem_sorts = {str(item.get("sort")) for item in problem_graph.get("objects", []) if item.get("sort")}
    answer_sorts = {str(item.get("sort")) for item in answer_graph.get("objects", []) if item.get("sort")}
    return {
        "syntax_ir": answer_structure,
        "semantic_status": answer_graph.get("status"),
        "morphisms": sorted(answer_morphisms),
        "latent_morphisms_raw": sorted(answer_morphisms - problem_morphisms),
        "latent_morphisms": sorted(answer_substantive - problem_substantive),
        "latent_object_sorts": sorted(answer_sorts - problem_sorts),
        "lift_certificates": answer_graph.get("lift_certificates", []),
        "warnings": answer_graph.get("warnings", []),
    }


def build_audit(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    blocks = extract_itembox_problems(text)
    answers = extract_answer_sections(text)
    registry = DomainRegistry()
    records: list[dict[str, Any]] = []
    for block in blocks:
        structure, graph = compile_problem(block.statement_tex)
        domain_ir = registry.analyze(block.statement_tex).to_dict()
        answer_tex = answers.get(block.ordinal)
        answer_graph = build_answer_graph(answer_tex, graph) if answer_tex else None
        semantic_delta = answer_semantic_delta(answer_tex, graph) if answer_tex else None
        design_lenses = analyze_design_lenses(block.statement_tex, graph)
        records.append({
            "ordinal": block.ordinal,
            "label": block.label,
            "statement_tex": block.statement_tex,
            "statement_sha256": block.statement_hash,
            "syntax_ir": structure,
            "domain_ir": domain_ir,
            "semantic_graph": graph,
            "design_lenses": design_lenses,
            "answer": {
                "available": bool(answer_tex),
                "answer_tex": answer_tex,
                "dependency_graph": answer_graph,
                "semantic_delta": semantic_delta,
            },
        })

    answer_graphs = [record["answer"]["dependency_graph"] for record in records if record["answer"]["dependency_graph"]]
    unlifted = [record for record in records if not record["semantic_graph"].get("lift_certificates")]
    latent_morphisms = Counter(
        name
        for record in records
        for name in ((record["answer"].get("semantic_delta") or {}).get("latent_morphisms") or [])
    )
    design_lens_counts = Counter(
        lens["id"] for record in records for lens in record["design_lenses"]
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_path": str(path),
        "summary": {
            "problems": len(records),
            "answers_attached": len(answer_graphs),
            "domain_classified": sum(bool(record["syntax_ir"].get("entities") or record["syntax_ir"].get("operations")) for record in records),
            "semantic_type_checked": sum(record["semantic_graph"].get("status") == "type_checked" for record in records),
            "with_query": sum(bool(record["semantic_graph"].get("queries")) for record in records),
            "with_constraints": sum(bool(record["semantic_graph"].get("constraints")) for record in records),
            "with_lift_certificate": sum(bool(record["semantic_graph"].get("lift_certificates")) for record in records),
            "without_lift_certificate": len(unlifted),
            "unlifted_ordinals": [record["ordinal"] for record in unlifted],
            "unlifted_by_domain": dict(Counter(record["domain_ir"].get("domain", "unknown") for record in unlifted)),
            "needs_review_ordinals": [
                record["ordinal"] for record in records if record["semantic_graph"].get("status") != "type_checked"
            ],
            "domain_counts": dict(Counter(record["domain_ir"].get("domain", "unknown") for record in records)),
            "answer_argument_units": sum(graph["metrics"]["argument_units"] for graph in answer_graphs),
            "answer_dependency_edges": sum(graph["metrics"]["dependency_edges"] for graph in answer_graphs),
            "answer_merge_nodes": sum(graph["metrics"]["merge_nodes"] for graph in answer_graphs),
            "latent_morphism_occurrences": sum(latent_morphisms.values()),
            "latent_morphism_counts": dict(latent_morphisms.most_common()),
            "design_lens_counts": dict(design_lens_counts.most_common()),
        },
        "records": records,
    }


def build_public_summary(audit: dict[str, Any]) -> dict[str, Any]:
    records = []
    for record in audit["records"]:
        graph = record["semantic_graph"]
        answer_graph = record["answer"]["dependency_graph"]
        semantic_delta = record["answer"].get("semantic_delta")
        records.append({
            "ordinal": record["ordinal"],
            "label": record["label"],
            "statement_tex": record["statement_tex"],
            "domain": record["domain_ir"].get("domain", "unknown"),
            "semantic_status": graph.get("status"),
            "objects": graph.get("objects", []),
            "morphisms": graph.get("morphisms", []),
            "constraints": graph.get("constraints", []),
            "queries": graph.get("queries", []),
            "lift_certificates": graph.get("lift_certificates", []),
            "warnings": graph.get("warnings", []),
            "design_lenses": record.get("design_lenses", []),
            "answer_available": bool(answer_graph),
            "answer_graph": answer_graph,
            "answer_semantic_delta": semantic_delta,
        })
    return {
        "generated_at": audit["generated_at"],
        "source": "self-authored 全問題.tex",
        "summary": audit["summary"],
        "records": records,
    }


def render_report(audit: dict[str, Any]) -> str:
    summary = audit["summary"]
    lines = [
        "# 全問題.tex 構文・意味・解答依存監査",
        "",
        f"- 問題: **{summary['problems']}**",
        f"- 解答を対応付けた問題: **{summary['answers_attached']}**",
        f"- 意味グラフ type_checked: **{summary['semantic_type_checked']}**",
        f"- query 抽出: **{summary['with_query']}**",
        f"- constraint 抽出: **{summary['with_constraints']}**",
        f"- LiftCertificate: **{summary['with_lift_certificate']}**",
        f"- Lift不能: **{summary['without_lift_certificate']}** ({summary['unlifted_ordinals']})",
        f"- 解答の論証単位: **{summary['answer_argument_units']}**",
        f"- 抽出した依存辺: **{summary['answer_dependency_edges']}**",
        f"- 複数依存が合流した節点: **{summary['answer_merge_nodes']}**",
        f"- 解答で初めて検出した潜在射: **{summary['latent_morphism_occurrences']}**",
        "",
        "## 解答で初めて現れた射",
        "",
        ", ".join(f"`{name}` × {count}" for name, count in summary["latent_morphism_counts"].items()) or "抽出なし",
        "",
        "## 作問構想の横断レンズ",
        "",
        "これは完成解法のfamily分類ではなく、問題文と意味グラフから得た横断的な構想証拠である。",
        "解答未収録の問題では理論背景は仮説であり、証明済みとは扱わない。",
        "",
        "| lens | problems |",
        "|---|---:|",
        *[
            f"| `{name}` | {count} |"
            for name, count in summary["design_lens_counts"].items()
        ],
        "",
        "## 問題別",
        "",
        "| # | label | design lenses | status | objects | morphisms | constraints | query | lift | answer units / edges / merges |",
        "|---:|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for record in audit["records"]:
        graph = record["semantic_graph"]
        answer_graph = record["answer"]["dependency_graph"]
        metrics = answer_graph["metrics"] if answer_graph else None
        answer_cell = (
            f"{metrics['argument_units']} / {metrics['dependency_edges']} / {metrics['merge_nodes']}"
            if metrics else "-"
        )
        lines.append(
            f"| {record['ordinal']} | {record['label']} | "
            f"{', '.join(lens['id'] for lens in record.get('design_lenses', [])) or '-'} | "
            f"{graph['status']} | "
            f"{len(graph['objects'])} | {len(graph['morphisms'])} | {len(graph['constraints'])} | "
            f"{len(graph['queries'])} | {len(graph['lift_certificates'])} | {answer_cell} |"
        )
    lines.extend([
        "",
        "## 注意",
        "",
        "解答依存辺は、変数定義の参照と明示的な接続語から抽出した証拠グラフであり、"
        "論理的含意を形式証明したものではない。辺が少ない問題は、解答が簡単という意味ではなく、"
        "現行パーサが依存を回収できていない可能性を含む。",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--public-output", type=Path)
    args = parser.parse_args()
    audit = build_audit(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_report(audit), encoding="utf-8", newline="\n")
    if args.public_output:
        args.public_output.parent.mkdir(parents=True, exist_ok=True)
        args.public_output.write_text(
            json.dumps(build_public_summary(audit), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    print(json.dumps(audit["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
