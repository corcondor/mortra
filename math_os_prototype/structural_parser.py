"""Domain-agnostic structural parser for math problems.

This layer is deliberately not a solver and not a list of benchmark-specific
detectors. It extracts reusable problem structure: operations, constraints,
objects, quantities, and tool affordances.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

try:
    from math_os_prototype.latex_frontend import looks_like_latex, parse_latex_problem
except ImportError:  # Allows local script use.
    from latex_frontend import looks_like_latex, parse_latex_problem


@dataclass
class StructuralEntity:
    kind: str
    name: str
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class StructuralOperation:
    kind: str
    target: str
    qualifiers: dict[str, Any] = field(default_factory=dict)


@dataclass
class StructuralConstraint:
    kind: str
    expression: str
    variables: list[str] = field(default_factory=list)


@dataclass
class StructuralIR:
    source_text: str
    normalized_text: str
    variables: list[str]
    expressions: list[str]
    relations: list[str]
    entities: list[StructuralEntity]
    constraints: list[StructuralConstraint]
    operations: list[StructuralOperation]
    quantities: list[str]
    tool_affordances: list[str]
    confidence: float
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


ENTITY_KEYWORDS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("circle", "circle", ("円", "circle")),
    ("square", "square", ("正方形", "square")),
    ("equilateral_triangle", "equilateral triangle", ("正三角形", "equilateral")),
    ("triangle", "triangle", ("三角形", "triangle")),
    ("line", "line", ("直線", "line")),
    ("curve", "curve", ("曲線", "curve")),
    ("function", "function", ("関数", "function")),
    ("sequence", "sequence", ("数列", "sequence")),
    ("polynomial", "polynomial", ("多項式", "方程式", "polynomial")),
    ("card_deck", "cards", ("カード", "card")),
    ("graph", "graph", ("グラフ", "graph")),
    ("complex_plane", "complex plane", ("複素数平面", "complex plane")),
)


QUANTITY_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("area", ("面積", "area")),
    ("volume", ("体積", "volume")),
    ("length", ("長さ", "距離", "length", "distance")),
    ("probability", ("確率", "probability")),
    ("expectation", ("期待値", "平均", "expectation", "mean")),
    ("correlation", ("相関係数", "correlation")),
    ("maximum", ("最大", "max", "maximum")),
    ("minimum", ("最小", "min", "minimum")),
    ("remainder", ("余り", "remainder")),
)


def analyze_structure(text: str) -> StructuralIR:
    normalized, expressions, notes = normalize_problem_text(text)
    variables = extract_variables(normalized, expressions)
    relations = extract_relations(normalized, expressions)
    entities = extract_entities(normalized)
    constraints = extract_constraints(normalized, relations, variables)
    operations = extract_operations(normalized, relations)
    quantities = extract_quantities(normalized)
    tool_affordances = infer_tool_affordances(
        operations=operations,
        constraints=constraints,
        entities=entities,
        relations=relations,
        quantities=quantities,
    )
    confidence = score_structure(operations, constraints, entities, relations, expressions)
    return StructuralIR(
        source_text=text,
        normalized_text=normalized,
        variables=variables,
        expressions=expressions,
        relations=relations,
        entities=entities,
        constraints=constraints,
        operations=operations,
        quantities=quantities,
        tool_affordances=tool_affordances,
        confidence=confidence,
        notes=notes,
    )


def normalize_problem_text(text: str) -> tuple[str, list[str], list[str]]:
    notes: list[str] = []
    expressions: list[str] = []
    if looks_like_latex(text):
        parsed = parse_latex_problem(text)
        normalized = parsed.normalized_text
        expressions.extend(parsed.math_segments)
        notes.append("LaTeX normalized before structural parsing.")
    else:
        normalized = text
        expressions.extend(match.strip() for match in re.findall(r"\$([^$]+)\$", text) if match.strip())
    normalized = normalize_spacing(normalized)
    expressions.extend(extract_inline_math_candidates(normalized))
    expressions = unique_preserve_order(clean_expression(expr) for expr in expressions if clean_expression(expr))
    return normalized, expressions, notes


def extract_inline_math_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    relation_pattern = r"[A-Za-z0-9_+\-*/^().,\s]+(?:<=|>=|!=|=|<|>)[A-Za-z0-9_+\-*/^().,\s]+"
    candidates.extend(match.group(0).strip() for match in re.finditer(relation_pattern, text))
    function_pattern = r"\b(?:sin|cos|tan|log|exp|sqrt|limit|integral|sum|product)\s*[^，。;\n]*"
    candidates.extend(match.group(0).strip() for match in re.finditer(function_pattern, text, flags=re.IGNORECASE))
    candidates.extend(extract_targets_before_query_keywords(text))
    return candidates


def extract_targets_before_query_keywords(text: str) -> list[str]:
    candidates: list[str] = []
    for marker in ("を求め", "の値", "を計算", "を簡単", "を因数分解", "を展開"):
        if marker not in text:
            continue
        prefix = text.split(marker, 1)[0]
        math_chunks = re.findall(r"[A-Za-z0-9_+\-*/^().]+", prefix)
        expression_chunks = [
            chunk
            for chunk in math_chunks
            if re.search(r"[A-Za-z]", chunk) and any(op in chunk for op in ("+", "-", "*", "/", "^"))
        ]
        if expression_chunks:
            candidates.append(expression_chunks[-1])
    return candidates


def extract_variables(text: str, expressions: list[str]) -> list[str]:
    names = set()
    joined = " ".join([text, *expressions])
    for match in re.finditer(r"\b[a-zA-Z](?:_[a-zA-Z0-9]+)?\b", joined):
        name = match.group(0)
        if name.lower() in {
            "i",
            "e",
            "pi",
            "sin",
            "cos",
            "tan",
            "log",
            "exp",
            "sqrt",
            "limit",
            "integral",
            "sum",
            "product",
            "re",
            "im",
        }:
            continue
        names.add(name)
    return sorted(names, key=lambda item: (len(item), item))[:16]


def extract_relations(text: str, expressions: list[str]) -> list[str]:
    relations: list[str] = []
    sources = [text, *expressions]
    relation_pattern = r"([A-Za-z0-9_+\-*/^().\s]+(?:<=|>=|!=|=|<|>)[A-Za-z0-9_+\-*/^().\s]+)"
    relations.extend(extract_japanese_named_relations(text))
    for source in sources:
        for part in re.split(r"[,，、;；]", source):
            for chain_match in re.finditer(r"[A-Za-z0-9_+\-*/^().]+\s*(?:<=|>=|<|>)\s*[A-Za-z0-9_+\-*/^().]+\s*(?:<=|>=|<|>)\s*[A-Za-z0-9_+\-*/^().]+", part):
                relations.extend(expand_chain_relation(chain_match.group(0)))
            for match in re.finditer(relation_pattern, part):
                relation = clean_expression(match.group(1))
                if relation:
                    relations.extend(expand_chain_relation(relation))
    return unique_preserve_order(relations)


def extract_japanese_named_relations(text: str) -> list[str]:
    relations: list[str] = []
    variables = [
        name
        for name in re.findall(r"\b[A-Za-z]\b", text)
        if name not in {"R", "Z"} and name.lower() not in {"sin", "cos", "tan", "log", "exp", "sqrt"}
    ]
    variables = unique_preserve_order(variables)
    if len(variables) < 2:
        return relations
    x_var, y_var = variables[0], variables[1]
    sum_match = re.search(r"和(?:が|は)\s*([+-]?\d+(?:/\d+)?(?:\.\d+)?)", text)
    product_match = re.search(r"積(?:が|は)\s*([+-]?\d+(?:/\d+)?(?:\.\d+)?)", text)
    if sum_match:
        relations.append(f"{x_var}+{y_var}={sum_match.group(1)}")
    if product_match:
        relations.append(f"{x_var}*{y_var}={product_match.group(1)}")
    return relations


def expand_chain_relation(relation: str) -> list[str]:
    compact = clean_expression(relation)
    chain_match = re.fullmatch(
        r"(.+?)(<=|>=|<|>)(.+?)(<=|>=|<|>)(.+)",
        compact,
    )
    if not chain_match:
        return [compact]
    left, op1, middle, op2, right = (chain_match.group(index).strip() for index in range(1, 6))
    return [f"{left}{op1}{middle}", f"{middle}{op2}{right}"]


def extract_entities(text: str) -> list[StructuralEntity]:
    entities: list[StructuralEntity] = []
    lower = text.lower()
    for kind, name, keywords in ENTITY_KEYWORDS:
        if any(keyword.lower() in lower for keyword in keywords):
            entities.append(StructuralEntity(kind=kind, name=name))
    return entities


def extract_constraints(text: str, relations: list[str], variables: list[str]) -> list[StructuralConstraint]:
    constraints: list[StructuralConstraint] = []
    lower = text.lower()

    domain_rules = (
        ("positive_integer", ("正の整数", "positive integer")),
        ("nonnegative_integer", ("非負整数", "nonnegative integer")),
        ("integer", ("整数", "integer", " in z")),
        ("real", ("実数", "real", " in r")),
        ("complex", ("複素数", "complex")),
        ("prime", ("素数", "prime")),
    )
    for kind, keywords in domain_rules:
        if kind == "prime" and "複素数" in lower:
            continue
        if any(keyword in lower for keyword in keywords):
            target_vars = variables or extract_nearby_variables(text, keywords)
            expression = ", ".join(target_vars) if target_vars else kind
            constraints.append(StructuralConstraint(kind=kind, expression=expression, variables=target_vars))

    for relation in relations:
        relation_vars = [var for var in variables if re.search(rf"\b{re.escape(var)}\b", relation)]
        kind = "equation" if "=" in relation and not any(op in relation for op in ("<", ">")) else "inequality"
        constraints.append(StructuralConstraint(kind=kind, expression=relation, variables=relation_vars))

    # ``in`` must be a token and an interval must have explicit delimiters.
    # The old optional-delimiter pattern read prose fragments such as
    # ``m in mini cupcakes`` as a mathematical interval constraint.
    interval_pattern = (
        r"(?<![A-Za-z])([A-Za-z])\s*(?:\bin\b|∈)\s*"
        r"([\[(])\s*([^,\]]+)\s*,\s*([^\])]+)\s*([\])])"
    )
    for match in re.finditer(interval_pattern, lower):
        var = match.group(1)
        left = match.group(2)
        right = match.group(5)
        constraints.append(
            StructuralConstraint(
                kind="interval",
                expression=f"{var} in {left}{match.group(3).strip()}, {match.group(4).strip()}{right}",
                variables=[var],
            )
        )
    return dedupe_constraints(constraints)


def extract_operations(text: str, relations: list[str]) -> list[StructuralOperation]:
    lower = text.lower()
    operations: list[StructuralOperation] = []

    def add(kind: str, target: str, **qualifiers: Any) -> None:
        operations.append(StructuralOperation(kind=kind, target=target, qualifiers=qualifiers))

    if contains_any(lower, ("示せ", "証明", "prove", "show that")):
        add("prove", latest_relation(relations), proof_style="informal_or_formal")
    if contains_any(lower, ("すべて求め", "組をすべて", "all pairs", "all solutions")):
        add("solve_all", latest_relation(relations), scope="all")
    elif contains_any(lower, ("求めよ", "求める", "解け", "find", "solve")):
        add("compute_or_solve", latest_relation(relations))

    # Mathematical interrogatives are observation operators, not word-problem
    # templates. Keeping this vocabulary finite types the requested output
    # without making assumptions about the solution law.
    interrogative = extract_interrogative_operation(text)
    if interrogative is not None:
        add(interrogative.kind, interrogative.target, **interrogative.qualifiers)
    if contains_any(lower, ("因数分解", "factor")):
        add("factor", extract_last_expression(text) or latest_relation(relations))
    if contains_any(lower, ("簡単", "simplify")):
        add("simplify", extract_last_expression(text) or latest_relation(relations))
    if contains_any(lower, ("展開", "expand")):
        add("expand", extract_last_expression(text) or latest_relation(relations))
    if contains_any(lower, ("limit", "極限", "lim")):
        add("limit", extract_target_after_keywords(text, ("limit", "lim", "極限")) or latest_relation(relations))
    if contains_any(lower, ("integral", "積分", "int")):
        add("integral", extract_target_after_keywords(text, ("integral", "積分")) or "")
    if contains_any(lower, ("最大", "maximum", "max")):
        add("optimize", extract_target_after_keywords(text, ("最大", "maximum", "max")) or "", sense="max")
    if contains_any(lower, ("最小", "minimum", "min")):
        add("optimize", extract_target_after_keywords(text, ("最小", "minimum", "min")) or "", sense="min")
    if contains_any(lower, ("面積", "area")):
        add("measure", "area")
    if contains_any(lower, ("体積", "volume")):
        add("measure", "volume")
    if contains_any(lower, ("通過領域", "passing region")):
        add("passing_region", "")
    if contains_any(lower, ("包絡線", "envelope")):
        add("envelope", "")
    if contains_any(lower, ("軌跡", "locus")):
        add("locus", "")
    if contains_any(lower, ("相関係数", "correlation")):
        add("correlation", "")
    if contains_any(lower, ("期待値", "expectation")):
        add("expectation", "")
    if re.search(r"\bsum of\b", lower) or "総和" in lower or "和を求め" in lower:
        add("aggregate", extract_last_expression(text) or latest_relation(relations), operation="sum")
    if re.search(r"\bproduct of\b", lower) or "総積" in lower or "積を求め" in lower:
        add("aggregate", extract_last_expression(text) or latest_relation(relations), operation="product")

    return dedupe_operations(operations)


def extract_interrogative_operation(text: str) -> StructuralOperation | None:
    """Map a surface question form to a typed observation operation."""
    normalized = normalize_spacing(text)
    lower = normalized.lower()
    forms: tuple[tuple[str, str, str], ...] = (
        (r"\bhow many\b", "query_count", "Integer"),
        (r"\bwhat percentage\b", "query_measure", "Real"),
        (r"\bhow (?:much|far|long)\b", "query_measure", "Real"),
        (r"\bhow big\b", "query_measure", "Real"),
        (
            r"\bwhat\s+(?:speed|distance|time|length|area|volume|price|cost|profit|value|number|angle)\b",
            "query_measure",
            "Real",
        ),
        (r"\bwhich\b", "query_select", "Set"),
        (r"\benter\b", "query_classify", "Fin"),
        (r"\b(?:evaluate|calculate|determine)\b", "query_compute", "Real"),
        (r"\bwhat(?:'s|\s+(?:is|are|was|were))\b", "query_compute", "Real"),
    )
    for pattern, kind, target_type in forms:
        match = re.search(pattern, lower)
        if match is None:
            continue
        target = normalized[match.end() :]
        target = re.split(r"[?？]", target, maxsplit=1)[0]
        target = target.strip(" \t\r\n,.:;\"'")
        if kind == "query_compute":
            target = extract_last_expression(normalized) or target
        return StructuralOperation(
            kind=kind,
            target=target or "requested_value",
            qualifiers={"target_type": target_type, "surface_form": match.group(0)},
        )
    return None


def extract_quantities(text: str) -> list[str]:
    lower = text.lower()
    quantities = [name for name, keywords in QUANTITY_KEYWORDS if any(keyword.lower() in lower for keyword in keywords)]
    return unique_preserve_order(quantities)


def infer_tool_affordances(
    *,
    operations: list[StructuralOperation],
    constraints: list[StructuralConstraint],
    entities: list[StructuralEntity],
    relations: list[str],
    quantities: list[str],
) -> list[str]:
    op_kinds = {operation.kind for operation in operations}
    constraint_kinds = {constraint.kind for constraint in constraints}
    entity_kinds = {entity.kind for entity in entities}
    affordances: list[str] = []

    if relations and op_kinds & {"compute_or_solve", "solve_all"}:
        affordances.append("sympy.solve")
    if "limit" in op_kinds:
        affordances.extend(["sympy.limit", "wolfram.limit"])
    if "integral" in op_kinds:
        affordances.extend(["sympy.integrate", "wolfram.integrate"])
    if op_kinds & {"factor", "simplify", "expand"}:
        affordances.append("sympy.expression")
    if "prove" in op_kinds and any(kind == "inequality" for kind in constraint_kinds):
        affordances.extend(["numeric_counterexample_search", "sos_or_convexity_proof", "lean.formalize"])
    if constraint_kinds & {"integer", "positive_integer", "nonnegative_integer", "prime"}:
        affordances.extend(["integer_model_search", "z3.smt", "sympy.ntheory"])
    if entity_kinds & {"circle", "square", "triangle", "equilateral_triangle", "line", "curve"}:
        affordances.extend(["coordinate_geometry_model", "wolfram.reduce", "sympy.eliminate"])
    if op_kinds & {"passing_region", "locus", "envelope"}:
        affordances.extend(["quantifier_elimination", "resultant_elimination"])
    if "probability" in quantities or op_kinds & {"correlation", "expectation"}:
        affordances.extend(["finite_probability_model", "symbolic_moments", "monte_carlo_sanity_check"])
    if op_kinds & {"optimize"}:
        affordances.extend(["critical_point_search", "boundary_case_analysis", "wolfram.maximize"])
    return unique_preserve_order(affordances)


def score_structure(
    operations: list[StructuralOperation],
    constraints: list[StructuralConstraint],
    entities: list[StructuralEntity],
    relations: list[str],
    expressions: list[str],
) -> float:
    score = 0.15
    score += min(0.25, 0.06 * len(operations))
    score += min(0.25, 0.04 * len(constraints))
    score += min(0.15, 0.04 * len(entities))
    score += min(0.15, 0.03 * len(relations))
    score += min(0.05, 0.01 * len(expressions))
    return round(min(score, 0.95), 3)


def extract_target_after_keywords(text: str, keywords: tuple[str, ...]) -> str | None:
    for keyword in keywords:
        match = re.search(rf"{re.escape(keyword)}[^。．.\n]*", text, flags=re.IGNORECASE)
        if match:
            return clean_expression(match.group(0))
    return None


def extract_last_expression(text: str) -> str | None:
    candidates = re.findall(r"[A-Za-z0-9_+\-*/^().\s]+", text)
    for candidate in reversed(candidates):
        cleaned = clean_expression(candidate)
        if cleaned and re.search(r"[A-Za-z]", cleaned) and any(op in cleaned for op in ("+", "-", "*", "/", "**", "^")):
            return cleaned
    return None


def latest_relation(relations: list[str]) -> str:
    return relations[-1] if relations else ""


def extract_nearby_variables(text: str, keywords: tuple[str, ...]) -> list[str]:
    variables: list[str] = []
    for keyword in keywords:
        index = text.find(keyword)
        if index < 0:
            continue
        window = text[max(0, index - 30) : index + 30]
        variables.extend(re.findall(r"\b[a-zA-Z]\b", window))
    return unique_preserve_order(variables)


def clean_expression(expr: str) -> str:
    expr = normalize_math_symbols(expr)
    expr = expr.replace("^", "**")
    expr = re.sub(r"(?<=\d)(?=[A-Za-z_(])", "*", expr)
    expr = re.sub(r"(?<=[A-Za-z])(?=\d)", "*", expr)
    expr = re.sub(r"(?<=\))(?=[A-Za-z_0-9(])", "*", expr)
    expr = re.sub(r"\s+", " ", expr)
    return expr.strip(" ,，。.;")


def normalize_spacing(text: str) -> str:
    text = normalize_math_symbols(text)
    text = text.replace("　", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_math_symbols(text: str) -> str:
    return (
        text.replace("＋", "+")
        .replace("－", "-")
        .replace("−", "-")
        .replace("×", "*")
        .replace("＊", "*")
        .replace("・", "*")
        .replace("＾", "^")
        .replace("＝", "=")
    )


def contains_any(text: str, needles: tuple[str, ...]) -> bool:
    lower = text.lower()
    for needle in needles:
        lowered = needle.lower()
        if re.fullmatch(r"[a-z]+", lowered):
            if re.search(rf"(?<![a-z]){re.escape(lowered)}(?![a-z])", lower):
                return True
        elif lowered in lower:
            return True
    return False


def unique_preserve_order(items: list[str] | Any) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if not item:
            continue
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def dedupe_constraints(items: list[StructuralConstraint]) -> list[StructuralConstraint]:
    seen = set()
    result = []
    for item in items:
        key = (item.kind, item.expression, tuple(item.variables))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def dedupe_operations(items: list[StructuralOperation]) -> list[StructuralOperation]:
    seen = set()
    result = []
    for item in items:
        key = (item.kind, item.target, tuple(sorted(item.qualifiers.items())))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result
