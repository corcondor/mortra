"""Parse human solution text into a lightweight step tree."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SolutionStep:
    id: str
    kind: str
    text: str
    expressions: list[str] = field(default_factory=list)
    relations: list[str] = field(default_factory=list)
    theorem_refs: list[str] = field(default_factory=list)
    children: list["SolutionStep"] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "text": self.text,
            "expressions": self.expressions,
            "relations": self.relations,
            "theorem_refs": self.theorem_refs,
            "children": [child.to_dict() for child in self.children],
        }


@dataclass
class ParsedSolution:
    source_url: str
    answer_id: int | None
    steps: list[SolutionStep]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SolutionStepParser:
    def parse_answer(self, body_text: str, *, source_url: str = "", answer_id: int | None = None) -> ParsedSolution:
        chunks = split_solution_text(body_text)
        steps = []
        for index, chunk in enumerate(chunks, start=1):
            kind = classify_step(chunk, index=index, total=len(chunks))
            steps.append(
                SolutionStep(
                    id=f"step-{index}",
                    kind=kind,
                    text=chunk,
                    expressions=extract_math_expressions(chunk),
                    relations=extract_relations(chunk),
                    theorem_refs=extract_theorem_refs(chunk),
                )
            )
        return ParsedSolution(source_url=source_url, answer_id=answer_id, steps=steps)


def split_solution_text(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = [part.strip() for part in re.split(r"\n{2,}|(?<=[.!?。])\s+(?=(?:Assume|Suppose|Let|Then|Thus|Hence|Therefore|So|We|Now|It|If|Since|By)\b)", normalized) if part.strip()]
    chunks: list[str] = []
    for paragraph in paragraphs:
        if len(paragraph) <= 420:
            chunks.append(paragraph)
            continue
        sentences = re.split(r"(?<=[.!?。])\s+", paragraph)
        buffer = ""
        for sentence in sentences:
            if len(buffer) + len(sentence) < 420:
                buffer = f"{buffer} {sentence}".strip()
            else:
                if buffer:
                    chunks.append(buffer)
                buffer = sentence
        if buffer:
            chunks.append(buffer)
    return chunks[:32]


def classify_step(text: str, *, index: int, total: int) -> str:
    lower = text.lower()
    if index == total or contains_any(lower, ("therefore", "hence", "thus", "so we have", "conclude", "よって", "したがって")):
        return "conclude"
    if contains_any(lower, ("assume", "suppose", "let ", "仮定", "とする")):
        return "assume"
    if contains_any(lower, ("substitute", "plug", "replace", "代入")):
        return "substitute"
    if contains_any(lower, ("by ", "using", "from", "cauchy", "am-gm", "jensen", "fermat", "euler", "theorem", "lemma")):
        return "apply_theorem"
    if extract_relations(text):
        return "transform"
    return "explain"


def extract_math_expressions(text: str) -> list[str]:
    expressions = []
    expressions.extend(match.strip() for match in re.findall(r"\$([^$]+)\$", text) if match.strip())
    expressions.extend(match.strip() for match in re.findall(r"\\\((.*?)\\\)", text) if match.strip())
    expressions.extend(match.strip() for match in re.findall(r"\\\[(.*?)\\\]", text, flags=re.DOTALL) if match.strip())
    return dedupe(normalize_expr(item) for item in expressions)


def extract_relations(text: str) -> list[str]:
    sources = [text, *extract_math_expressions(text)]
    relations: list[str] = []
    relation_pattern = r"([A-Za-z0-9_\\+\-*/^().{}\[\]\s]+(?:<=|>=|=|<|>|\\leq|\\geq)[A-Za-z0-9_\\+\-*/^().{}\[\]\s]+)"
    for source in sources:
        for match in re.finditer(relation_pattern, source):
            relation = normalize_expr(match.group(1))
            if relation and len(relation) <= 220:
                relations.append(relation)
    return dedupe(relations)


def extract_theorem_refs(text: str) -> list[str]:
    refs = []
    patterns = (
        "cauchy",
        "cauchy-schwarz",
        "am-gm",
        "jensen",
        "holder",
        "fermat",
        "euler",
        "binomial theorem",
        "mean value theorem",
        "intermediate value theorem",
        "squeeze theorem",
    )
    lower = text.lower()
    for pattern in patterns:
        if pattern in lower:
            refs.append(pattern)
    return refs


def normalize_expr(expr: str) -> str:
    expr = re.sub(
        r"^\s*(we have|have|then|thus|hence|therefore|so|it follows that|we get|we obtain)\s+",
        "",
        expr,
        flags=re.IGNORECASE,
    )
    expr = expr.replace("\\leq", "<=").replace("\\geq", ">=")
    expr = expr.replace("^", "**")
    expr = expr.replace("{", "").replace("}", "")
    expr = re.sub(r"\s+", " ", expr)
    return expr.strip(" ,.;:")


def contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def dedupe(items: Any) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
