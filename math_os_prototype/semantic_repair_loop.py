"""Execution-guided semantic repair without answer or solution templates.

The loop learns which *typed operator compositions* are stable on a development
partition.  It never stores a problem answer and never promotes a rule keyed by
problem ID, title, number, or complete surface sentence.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

try:
    from math_os_prototype.category_semantics import compile_typed_semantic_graph
    from math_os_prototype.jukenmath_full_audit import (
        canonical_surface,
        fetch_public_problems,
        jaccard,
        surface_ngrams,
    )
    from math_os_prototype.structural_parser import analyze_structure
    from math_os_prototype.typed_definition_kernel import (
        LEXICON,
        compile_typed_definition_ir,
    )
except ImportError:
    from category_semantics import compile_typed_semantic_graph
    from jukenmath_full_audit import (
        canonical_surface,
        fetch_public_problems,
        jaccard,
        surface_ngrams,
    )
    from structural_parser import analyze_structure
    from typed_definition_kernel import LEXICON, compile_typed_definition_ir


DEFAULT_OUTPUT = Path("problem_synthesis/semantic_repair_loop1.json")
DEFAULT_SPLIT = Path("problem_synthesis/jukenmath_frozen_split_v1.json")
DEFAULT_HELDOUT_GUARD = Path("problem_synthesis/jukenmath_heldout_guard_v1.json")
SPLIT_NAMES = ("dev", "calibration", "heldout")
SPLIT_TARGETS = {"dev": 0.50, "calibration": 0.20, "heldout": 0.30}


@dataclass(frozen=True)
class OperatorSpec:
    name: str
    input_sort: str
    output_sort: str
    precedence: int
    theory: str


@dataclass(frozen=True)
class Lexeme:
    canonical: str
    surface: str
    start: int
    end: int


@dataclass
class RepairCandidate:
    source: str
    definitions: list[str]
    object_sorts: list[str]
    morphism_chain: list[str]
    chain_sorts: list[str]
    constraint_skeleton: list[str]
    quantifiers: list[str]
    query_signature: str
    type_checked: bool
    score: float
    warnings: list[str] = field(default_factory=list)

    def canonical_signature(self) -> str:
        payload = {
            "definitions": sorted(set(self.definitions)),
            "object_sorts": sorted(
                {normalize_indexed_sort(value) for value in self.object_sorts}
            ),
            "morphism_chain": self.morphism_chain,
            "constraint_skeleton": sorted(
                {
                    canonical_constraint_signature(value)
                    for value in self.constraint_skeleton
                }
            ),
            "quantifiers": self.quantifiers,
            "query_signature": canonical_query_signature(self.query_signature),
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return sha256(encoded.encode("utf-8")).hexdigest()[:24]


@dataclass
class CounterfactualReport:
    alpha_invariant: bool
    numeric_invariant: bool
    quantifier_sensitive: bool | None
    query_sensitive: bool | None

    @property
    def invariance_rate(self) -> float:
        checks = [self.alpha_invariant, self.numeric_invariant]
        return sum(checks) / len(checks)

    @property
    def sensitivity_rate(self) -> float:
        checks = [
            value
            for value in (self.quantifier_sensitive, self.query_sensitive)
            if value is not None
        ]
        return sum(checks) / len(checks) if checks else 1.0

    @property
    def passed(self) -> bool:
        return self.invariance_rate == 1.0 and self.sensitivity_rate == 1.0


@dataclass
class RepairRecord:
    problem_id: int
    category: str
    partition: str
    baseline_status: str
    baseline_has_query: bool
    baseline_lifted: bool
    selected: RepairCandidate
    forest_size: int
    counterfactual: CounterfactualReport
    threshold_admissible: bool
    promoted_admissible: bool = False
    promotion_missing: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["selected"]["canonical_signature"] = self.selected.canonical_signature()
        payload["counterfactual"]["invariance_rate"] = self.counterfactual.invariance_rate
        payload["counterfactual"]["sensitivity_rate"] = self.counterfactual.sensitivity_rate
        payload["counterfactual"]["passed"] = self.counterfactual.passed
        return payload


OPERATOR_SPECS: dict[str, OperatorSpec] = {
    "Equation": OperatorSpec("Equation", "Term", "Equation", 10, "equational_logic"),
    "SetComprehension": OperatorSpec("SetComprehension", "Prop", "Set(Any)", 12, "set_theory"),
    "RootSet": OperatorSpec("RootSet", "Equation", "Set(Real)", 14, "real_closed_fields"),
    "Intersection": OperatorSpec("Intersection", "Set(Any)", "Set(Any)", 20, "set_theory"),
    "Map": OperatorSpec("Map", "Set(Any)", "Set(Any)", 22, "function_theory"),
    "Image": OperatorSpec("Image", "Set(Any)", "Set(Any)", 23, "set_theory"),
    "Locus": OperatorSpec("Locus", "Prop", "Set(Point2)", 24, "set_theory"),
    "ConvexHull": OperatorSpec("ConvexHull", "Set(Point2)", "Region2", 30, "linear_real_arithmetic"),
    "Centroid": OperatorSpec("Centroid", "Set(Point2)", "Point2", 32, "linear_real_arithmetic"),
    "Tangent": OperatorSpec("Tangent", "Curve2", "Line2", 32, "differential_algebra"),
    "Projection": OperatorSpec("Projection", "Vector", "Vector", 32, "linear_algebra"),
    "Laplacian": OperatorSpec("Laplacian", "Graph", "Matrix", 30, "spectral_graph_theory"),
    "Eigenvalues": OperatorSpec("Eigenvalues", "Matrix", "Set(Number)", 34, "linear_algebra"),
    "Determinant": OperatorSpec("Determinant", "Matrix", "Number", 42, "linear_algebra"),
    "Evaluation": OperatorSpec("Evaluation", "Polynomial", "Number", 38, "function_theory"),
    "Cardinality": OperatorSpec("Cardinality", "Set(Any)", "Natural", 38, "finite_set_theory"),
    "Area": OperatorSpec("Area", "Region2", "Real", 40, "measure_theory"),
    "Volume": OperatorSpec("Volume", "Region3", "Real", 40, "measure_theory"),
    "Derivative": OperatorSpec("Derivative", "Function", "Function", 40, "differential_algebra"),
    "Integral": OperatorSpec("Integral", "Function", "Real", 42, "real_analysis"),
    "FiniteSum": OperatorSpec("FiniteSum", "Set(Any)", "Number", 42, "algebra"),
    "FiniteProduct": OperatorSpec("FiniteProduct", "Set(Any)", "Number", 42, "algebra"),
    "Expectation": OperatorSpec("Expectation", "RandomVariable", "Real", 42, "probability"),
    "Variance": OperatorSpec("Variance", "RandomVariable", "Real", 43, "probability"),
    "Covariance": OperatorSpec("Covariance", "RandomVariable", "Real", 43, "probability"),
    "Correlation": OperatorSpec("Correlation", "RandomVariable", "Real", 44, "probability"),
    "CorrelationFunction": OperatorSpec("CorrelationFunction", "StochasticProcess", "Function", 44, "probability"),
    "InnerProduct": OperatorSpec("InnerProduct", "Vector", "Real", 42, "linear_algebra"),
    "FrobeniusInnerProduct": OperatorSpec("FrobeniusInnerProduct", "Matrix", "Real", 42, "linear_algebra"),
    "Norm": OperatorSpec("Norm", "Vector", "Real", 43, "linear_algebra"),
    "NormalizedInnerProduct": OperatorSpec("NormalizedInnerProduct", "Vector", "Real", 44, "linear_algebra"),
    "Limit": OperatorSpec("Limit", "Function", "Real", 50, "real_analysis"),
    "Maximum": OperatorSpec("Maximum", "Real", "Real", 60, "optimization"),
    "Minimum": OperatorSpec("Minimum", "Real", "Real", 60, "optimization"),
    "Prime": OperatorSpec("Prime", "Integer", "Prop", 40, "number_theory"),
    "Divides": OperatorSpec("Divides", "Integer", "Prop", 40, "integer_arithmetic"),
    "GCD": OperatorSpec("GCD", "Integer", "Integer", 42, "number_theory"),
    "LCM": OperatorSpec("LCM", "Integer", "Integer", 42, "number_theory"),
    "Factorial": OperatorSpec("Factorial", "Natural", "Natural", 42, "integer_arithmetic"),
}
EXCLUSIVE_OPERATOR_GROUPS = (
    frozenset({"Maximum", "Minimum"}),
)

QUERY_DEFINITIONS = {
    "Find": "compute",
    "Decide": "decide",
    "Prove": "prove",
}
QUANTIFIER_DEFINITIONS = {"Forall": "forall", "Exists": "exists"}
ENTITY_SORTS = {
    "Point2": "Point2",
    "Line2": "Line2",
    "Curve2": "Curve2",
    "Circle": "Curve2",
    "Polygon": "Set(Point2)",
    "RegularPolygon": "Set(Point2)",
    "Region2": "Region2",
    "Integer": "Integer",
    "Natural": "Natural",
    "ProbabilitySpace": "ProbabilitySpace",
    "InnerProductSpace": "InnerProductSpace",
    "QuadraticForm": "Function",
    "Polynomial": "Polynomial",
    "Sequence": "Sequence",
    "Graph": "Graph",
    "Matrix": "Matrix",
    "Laplacian": "Matrix",
    "Eigenvalues": "Set(Number)",
}


class LexicalAutomaton:
    def __init__(self) -> None:
        self.root: dict[str, Any] = {}
        for entry in LEXICON:
            for surface in entry.surfaces:
                lowered = surface.lower()
                if not lowered or lowered in {"=", "!", "∈", "∧", "∨", "¬"}:
                    continue
                node = self.root
                for character in lowered:
                    node = node.setdefault(character, {})
                node.setdefault("_entries", []).append((entry.canonical, surface))

    def scan(self, text: str) -> list[Lexeme]:
        lowered = text.lower()
        output: list[Lexeme] = []
        index = 0
        while index < len(lowered):
            node = self.root
            cursor = index
            best: tuple[int, list[tuple[str, str]]] | None = None
            while cursor < len(lowered) and lowered[cursor] in node:
                node = node[lowered[cursor]]
                cursor += 1
                if "_entries" in node:
                    best = (cursor, list(node["_entries"]))
            if best is None:
                index += 1
                continue
            end, entries = best
            for canonical, surface in entries:
                output.append(Lexeme(canonical, surface, index, end))
            index = end
        return output


LEXICAL_AUTOMATON = LexicalAutomaton()


def compile_repair_forest(text: str) -> list[RepairCandidate]:
    structure = analyze_structure(text)
    typed = compile_typed_definition_ir(text)
    graph = compile_typed_semantic_graph(
        text,
        structural_ir=structure.to_dict(),
        typed_definition_ir=typed.to_dict(),
    )
    lexemes = LEXICAL_AUTOMATON.scan(structure.normalized_text)
    definitions = sorted(
        {
            str(item.get("canonical"))
            for item in typed.definitions_used
            if item.get("canonical")
        }
        | {lexeme.canonical for lexeme in lexemes}
    )
    declared_sorts = {
        str(item.get("type") or "Unknown")
        for item in typed.declarations
        if declaration_sort_is_grounded(
            str(item.get("type") or "Unknown"),
            definitions,
        )
    }
    object_sorts = sorted(
        declared_sorts
        | {ENTITY_SORTS[name] for name in definitions if name in ENTITY_SORTS}
    )
    constraints = constraint_skeleton(structure.to_dict(), typed.to_dict())
    quantifiers = quantifier_signature(definitions, structure.normalized_text)
    query = query_signature(definitions, typed.query)
    operator_names = [
        name for name in definitions if name in OPERATOR_SPECS
    ]
    paths = enumerate_typed_paths(operator_names)
    if not paths:
        paths = [([], [], True)]

    candidates: list[RepairCandidate] = []
    for chain, chain_sorts, type_checked in paths[:8]:
        warnings: list[str] = []
        if not object_sorts:
            warnings.append("no_typed_objects")
        if not constraints:
            warnings.append("no_constraints")
        if query.startswith("unknown"):
            warnings.append("unknown_query")
        if not chain:
            warnings.append("no_composable_morphism")
        score = candidate_score(
            definitions=definitions,
            object_sorts=object_sorts,
            constraints=constraints,
            query=query,
            chain=chain,
            type_checked=type_checked,
            warnings=warnings,
        )
        candidates.append(
            RepairCandidate(
                source="typed_lexical_composition",
                definitions=definitions,
                object_sorts=object_sorts,
                morphism_chain=chain,
                chain_sorts=chain_sorts,
                constraint_skeleton=constraints,
                quantifiers=quantifiers,
                query_signature=query,
                type_checked=type_checked,
                score=score,
                warnings=warnings,
            )
        )

    return sorted(
        candidates,
        key=lambda item: (
            -item.score,
            0 if item.source == "typed_lexical_composition" else 1,
            -len(item.morphism_chain),
            item.canonical_signature(),
        ),
    )


def declaration_sort_is_grounded(sort: str, definitions: list[str]) -> bool:
    primitive = {
        "Real",
        "Integer",
        "Natural",
        "Complex",
        "Bool",
        "Function",
        "Matrix",
        "Vector",
        "Polynomial",
        "Sequence",
        "Graph",
        "RandomVariable",
        "StochasticProcess",
    }
    base = sort.split("(", 1)[0]
    return base in primitive or base in definitions or sort in {
        ENTITY_SORTS[name] for name in definitions if name in ENTITY_SORTS
    }


def normalize_indexed_sort(value: str) -> str:
    value = re.sub(r"\[[^\]]+\]", "[#]", value)
    return re.sub(r"(?<![A-Za-z])\d+(?![A-Za-z])", "#", value)


def enumerate_typed_paths(
    operator_names: list[str],
) -> list[tuple[list[str], list[str], bool]]:
    specs = [OPERATOR_SPECS[name] for name in sorted(set(operator_names), key=lambda value: OPERATOR_SPECS[value].precedence)]
    output: list[tuple[list[str], list[str], bool]] = []

    def walk(path: list[OperatorSpec], remaining: list[OperatorSpec]) -> None:
        if path:
            output.append(
                (
                    [item.name for item in path],
                    [path[0].input_sort, *[item.output_sort for item in path]],
                    True,
                )
            )
        if len(path) >= 8:
            return
        for index, candidate in enumerate(remaining):
            if path:
                previous = path[-1]
                if candidate.precedence < previous.precedence:
                    continue
                if not sort_compatible(previous.output_sort, candidate.input_sort):
                    continue
            if any(
                candidate.name in group
                and any(item.name in group for item in path)
                for group in EXCLUSIVE_OPERATOR_GROUPS
            ):
                continue
            walk(path + [candidate], remaining[index + 1 :])

    walk([], specs)
    unique: dict[tuple[str, ...], tuple[list[str], list[str], bool]] = {}
    for item in output:
        unique[tuple(item[0])] = item
    return sorted(
        unique.values(),
        key=lambda item: (-len(item[0]), item[0]),
    )


def sort_compatible(actual: str, expected: str) -> bool:
    if expected in {"Any", "Term"}:
        return True
    if actual == expected:
        return True
    if expected.startswith("Set(") and actual.startswith("Set("):
        return True
    if expected == "Region2" and actual in {"Curve2", "Set(Point2)", "Region2"}:
        return True
    if expected == "Real" and actual in {"Natural", "Integer", "Number", "Probability", "Real"}:
        return True
    if expected == "Number" and actual in {"Natural", "Integer", "Real", "Number"}:
        return True
    if expected == "Function" and actual in {
        "Function",
        "Curve2",
        "Polynomial",
        "Sequence",
        "StochasticProcess",
    }:
        return True
    if expected == "Vector" and actual in {"Point2", "Vector2", "Vector"}:
        return True
    return False


def constraint_skeleton(
    structure: dict[str, Any],
    typed: dict[str, Any],
) -> list[str]:
    values: list[str] = []
    for constraint in structure.get("constraints", []) or []:
        kind = str(constraint.get("kind") or "constraint")
        expression = normalize_formula(str(constraint.get("expression") or ""))
        values.append(f"{kind}:{expression}")
    for predicate in typed.get("predicates", []) or []:
        kind = str(predicate.get("kind") or "predicate")
        if kind == "definition":
            continue
        expression = normalize_formula(str(predicate.get("formula") or ""))
        if expression:
            values.append(f"{kind}:{expression}")
    values.extend(infer_cardinality_skeleton(str(structure.get("normalized_text") or "")))
    return sorted(set(values))[:24]


def normalize_formula(expression: str) -> str:
    normalized = re.sub(r"\\[A-Za-z]+", "CMD", expression)
    mapping: dict[str, str] = {}
    preserved = {
        "CMD",
        "sin",
        "cos",
        "tan",
        "log",
        "exp",
        "sqrt",
        "integral",
        "limit",
        "infinity",
        "True",
        "False",
    }

    def replace_identifier(match: re.Match[str]) -> str:
        identifier = match.group(0)
        if identifier in preserved:
            return identifier
        if identifier not in mapping:
            mapping[identifier] = f"v{len(mapping)}"
        return mapping[identifier]

    normalized = re.sub(
        r"\b[A-Za-z][A-Za-z0-9_]*\b",
        replace_identifier,
        normalized,
    )
    normalized = re.sub(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?", "#", normalized)
    normalized = re.sub(r"\s+", "", normalized)
    return normalized[:320]


def canonical_constraint_signature(value: str) -> str:
    kind, _, expression = value.partition(":")
    relations = re.findall(r"<=|>=|!=|=|<|>", expression)
    operators = re.findall(r"\*\*|[+\-*/]", expression)
    functions = [
        name
        for name in (
            "sin",
            "cos",
            "tan",
            "log",
            "exp",
            "sqrt",
            "integral",
            "limit",
            "sum",
            "product",
            "Cardinality",
            "Distinct",
        )
        if name.lower() in expression.lower()
    ]
    return (
        f"{kind}|rel={','.join(relations[:8])}|"
        f"op={','.join(operators[:12])}|fn={','.join(functions)}"
    )


def canonical_query_signature(value: str) -> str:
    parts = value.split(":", 2)
    if len(parts) < 2:
        return value
    return f"{parts[0]}:{parts[1]}"


def infer_cardinality_skeleton(text: str) -> list[str]:
    collection_nouns = (
        "実根",
        "根",
        "実数解",
        "解",
        "点",
        "直線",
        "曲線",
        "整数",
        "自然数",
        "素数",
        "事象",
    )
    noun_pattern = "|".join(map(re.escape, collection_nouns))
    pattern = re.compile(
        rf"(\d+)\s*(?:個の|つの)?(?:相異なる|互いに異なる)?\s*({noun_pattern})"
    )
    return [
        f"cardinality:Cardinality(Set({match.group(2)}))=#"
        for match in pattern.finditer(text)
    ]


def quantifier_signature(definitions: list[str], text: str) -> list[str]:
    values: list[str] = []
    if "Forall" in definitions or any(marker in text for marker in ("すべて", "任意", "各")):
        values.append("forall")
    if "Exists" in definitions or any(marker in text for marker in ("存在", "ある ")):
        values.append("exists")
    if "Distinct" in definitions:
        values.append("distinct")
    return values


def query_signature(definitions: list[str], query: dict[str, Any]) -> str:
    kind = next(
        (QUERY_DEFINITIONS[name] for name in QUERY_DEFINITIONS if name in definitions),
        str(query.get("kind") or "unknown"),
    )
    outer = next(
        (
            name
            for name in (
                "Maximum",
                "Minimum",
                "Limit",
                "Area",
                "Volume",
                "Cardinality",
                "Expectation",
                "Determinant",
                "FiniteSum",
                "FiniteProduct",
                "Evaluation",
                "Prove",
                "Decide",
            )
            if name in definitions
        ),
        str(query.get("target_type") or "Unknown"),
    )
    target = normalize_formula(str(query.get("expression") or query.get("target") or ""))
    return f"{kind}:{outer}:{target or 'unknown'}"


def candidate_score(
    *,
    definitions: list[str],
    object_sorts: list[str],
    constraints: list[str],
    query: str,
    chain: list[str],
    type_checked: bool,
    warnings: list[str],
) -> float:
    score = min(2.0, len(definitions) / 4)
    score += min(2.0, len(object_sorts))
    score += min(2.0, len(constraints))
    score += 2.0 if not query.startswith("unknown") and not query.endswith(":unknown") else 0.0
    score += min(4.0, len(chain))
    score += 2.0 if type_checked else 0.0
    score -= min(3.0, 0.35 * len(warnings))
    return round(score, 3)


def counterfactual_check(text: str, selected: RepairCandidate) -> CounterfactualReport:
    alpha = mutate_alpha_names(text)
    numeric = mutate_first_number(text)
    quantifier = mutate_quantifier(text)
    query = mutate_query(text)
    alpha_signature = select_candidate(compile_repair_forest(alpha)).canonical_signature()
    numeric_signature = select_candidate(compile_repair_forest(numeric)).canonical_signature()
    quantifier_signature_value = (
        select_candidate(compile_repair_forest(quantifier)).canonical_signature()
        if quantifier is not None
        else None
    )
    query_signature_value = (
        select_candidate(compile_repair_forest(query)).canonical_signature()
        if query is not None
        else None
    )
    original = selected.canonical_signature()
    return CounterfactualReport(
        alpha_invariant=alpha_signature == original,
        numeric_invariant=numeric_signature == original,
        quantifier_sensitive=(
            quantifier_signature_value != original
            if quantifier_signature_value is not None
            else None
        ),
        query_sensitive=(
            query_signature_value != original
            if query_signature_value is not None
            else None
        ),
    )


def mutate_alpha_names(text: str) -> str:
    variables = [
        value
        for value in sorted(set(re.findall(r"\b[a-z]\b", text)))
        if value not in {"e", "i"}
    ]
    replacements = ["u", "v", "w", "p", "q", "s"]
    output = text
    for source, target in zip(variables, replacements):
        output = re.sub(rf"\b{re.escape(source)}\b", target, output)
    return output


def mutate_first_number(text: str) -> str:
    match = re.search(r"(?<![A-Za-z])(\d+)(?![A-Za-z])", text)
    if not match:
        return text
    value = int(match.group(1))
    replacement = str(value + 1 if value != 0 else 2)
    return text[: match.start(1)] + replacement + text[match.end(1) :]


def mutate_quantifier(text: str) -> str | None:
    replacements = (
        ("すべて", "ある"),
        ("任意の", "ある"),
        ("各", "ある"),
        ("存在する", "すべて満たす"),
    )
    for source, target in replacements:
        if source in text:
            return text.replace(source, target, 1)
    return None


def mutate_query(text: str) -> str | None:
    replacements = (
        ("最大値", "最小値"),
        ("最小値", "最大値"),
        ("示せ", "求めよ"),
        ("求めよ", "示せ"),
    )
    for source, target in replacements:
        if source in text:
            return text.replace(source, target, 1)
    return None


def select_candidate(forest: list[RepairCandidate]) -> RepairCandidate:
    if not forest:
        raise RuntimeError("semantic parse forest is empty")
    return forest[0]


class DisjointSet:
    def __init__(self, values: Iterable[int]) -> None:
        self.parent = {value: value for value in values}

    def find(self, value: int) -> int:
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def build_frozen_split(rows: list[dict[str, Any]]) -> dict[str, Any]:
    identifiers = [int(row["id"]) for row in rows]
    dsu = DisjointSet(identifiers)
    by_author: dict[str, list[int]] = defaultdict(list)
    grams: dict[int, frozenset[str]] = {}
    for row in rows:
        problem_id = int(row["id"])
        author = str(row.get("author_id") or f"anonymous:{problem_id}")
        by_author[author].append(problem_id)
        grams[problem_id] = surface_ngrams(str(row.get("problem_tex") or ""))
    for author_ids in by_author.values():
        first = author_ids[0]
        for problem_id in author_ids[1:]:
            dsu.union(first, problem_id)
    for left_index, left_id in enumerate(identifiers):
        left = grams[left_id]
        for right_id in identifiers[left_index + 1 :]:
            right = grams[right_id]
            if min(len(left), len(right)) < 8:
                continue
            length_ratio = min(len(left), len(right)) / max(len(left), len(right))
            if length_ratio >= 0.60 and jaccard(left, right) >= 0.86:
                dsu.union(left_id, right_id)

    groups: dict[int, list[int]] = defaultdict(list)
    for problem_id in identifiers:
        groups[dsu.find(problem_id)].append(problem_id)
    total = len(rows)
    targets = {name: total * ratio for name, ratio in SPLIT_TARGETS.items()}
    assigned_counts = {name: 0 for name in SPLIT_NAMES}
    assignments: dict[int, str] = {}
    ordered_groups = sorted(
        groups.values(),
        key=lambda group: (
            -len(group),
            sha256(",".join(map(str, sorted(group))).encode("utf-8")).hexdigest(),
        ),
    )
    for group in ordered_groups:
        partition = max(
            SPLIT_NAMES,
            key=lambda name: (
                targets[name] - assigned_counts[name],
                -assigned_counts[name],
                name,
            ),
        )
        for problem_id in group:
            assignments[problem_id] = partition
        assigned_counts[partition] += len(group)

    row_by_id = {int(row["id"]): row for row in rows}
    dataset_payload = [
        (
            problem_id,
            sha256(canonical_surface(str(row_by_id[problem_id].get("problem_tex") or "")).encode("utf-8")).hexdigest(),
        )
        for problem_id in sorted(row_by_id)
    ]
    dataset_sha = sha256(
        json.dumps(dataset_payload, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "version": 1,
        "dataset_sha256": dataset_sha,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "policy": {
            "author_disjoint": True,
            "near_duplicate_threshold": 0.86,
            "targets": SPLIT_TARGETS,
        },
        "counts": dict(Counter(assignments.values())),
        "groups": len(groups),
        "assignments": {str(key): value for key, value in sorted(assignments.items())},
        "statement_sha256": {
            str(problem_id): digest for problem_id, digest in dataset_payload
        },
    }


def load_or_create_split(
    rows: list[dict[str, Any]],
    path: Path,
    *,
    rebuild: bool = False,
) -> dict[str, Any]:
    proposed = build_frozen_split(rows)
    if path.exists() and not rebuild:
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing.get("dataset_sha256") != proposed["dataset_sha256"]:
            raise RuntimeError(
                "The public corpus changed after the split was frozen. "
                "Use --rebuild-split only for a new experiment version."
            )
        return existing
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(proposed, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return proposed


def evaluate_rows(
    rows: list[dict[str, Any]],
    assignments: dict[str, str],
    partition: str,
    *,
    threshold: float,
) -> list[RepairRecord]:
    output: list[RepairRecord] = []
    for row in rows:
        problem_id = int(row["id"])
        if assignments.get(str(problem_id)) != partition:
            continue
        text = str(row.get("problem_tex") or "")
        graph = compile_typed_semantic_graph(text)
        forest = compile_repair_forest(text)
        selected = select_candidate(forest)
        counterfactual = counterfactual_check(text, selected)
        output.append(
            RepairRecord(
                problem_id=problem_id,
                category=str(row.get("category") or "未分類"),
                partition=partition,
                baseline_status=graph.status,
                baseline_has_query=bool(graph.queries),
                baseline_lifted=any(item.admissible for item in graph.lift_certificates),
                selected=selected,
                forest_size=len(forest),
                counterfactual=counterfactual,
                threshold_admissible=(
                    selected.type_checked
                    and selected.score >= threshold
                    and counterfactual.passed
                ),
            )
        )
    return output


def calibrate_threshold(records: list[RepairRecord]) -> float:
    candidates = [float(value) for value in range(4, 13)]
    scored: list[tuple[bool, float, float, float]] = []
    for threshold in candidates:
        selected = [
            record
            for record in records
            if record.selected.type_checked and record.selected.score >= threshold
        ]
        coverage = len(selected) / len(records) if records else 0.0
        invariance = (
            sum(record.counterfactual.invariance_rate for record in selected) / len(selected)
            if selected
            else 0.0
        )
        sensitivity = (
            sum(record.counterfactual.sensitivity_rate for record in selected) / len(selected)
            if selected
            else 0.0
        )
        acceptable = invariance >= 0.98 and sensitivity >= 0.90
        scored.append((acceptable, coverage, invariance * sensitivity, -threshold))
    best = max(scored)
    return -best[3]


def learn_promotions(records: list[RepairRecord]) -> dict[str, Any]:
    edge_records: dict[str, list[RepairRecord]] = defaultdict(list)
    for record in records:
        chain = record.selected.morphism_chain
        keys = (
            [f"op:{chain[0]}"] if len(chain) == 1 else []
        ) + [
            f"edge:{left}->{right}" for left, right in zip(chain, chain[1:])
        ]
        for key in keys:
            edge_records[key].append(record)
    promoted: dict[str, Any] = {}
    rejected: dict[str, Any] = {}
    for key, items in sorted(edge_records.items()):
        categories = sorted({item.category for item in items})
        stability = sum(item.counterfactual.passed for item in items) / len(items)
        evidence = {
            "count": len(items),
            "categories": categories,
            "counterfactual_pass_rate": round(stability, 4),
        }
        if len(items) >= 2 and len(categories) >= 2 and stability >= 0.90:
            promoted[key] = evidence
        else:
            rejected[key] = evidence
    return {"promoted": promoted, "rejected": rejected}


def apply_promotions(
    records: list[RepairRecord],
    registry: dict[str, Any],
    *,
    threshold: float,
) -> None:
    promoted = set(registry["promoted"])
    for record in records:
        chain = record.selected.morphism_chain
        required = (
            [f"op:{chain[0]}"] if len(chain) == 1 else []
        ) + [
            f"edge:{left}->{right}" for left, right in zip(chain, chain[1:])
        ]
        missing = [key for key in required if key not in promoted]
        record.promotion_missing = missing
        record.promoted_admissible = bool(
            chain
            and not missing
            and record.selected.type_checked
            and record.selected.score >= threshold
            and record.counterfactual.passed
        )


def summarize_records(records: list[RepairRecord]) -> dict[str, Any]:
    total = len(records)
    return {
        "total": total,
        "baseline_type_checked": sum(record.baseline_status == "type_checked" for record in records),
        "baseline_has_query": sum(record.baseline_has_query for record in records),
        "baseline_lifted": sum(record.baseline_lifted for record in records),
        "repair_type_checked": sum(record.selected.type_checked for record in records),
        "counterfactual_passed": sum(record.counterfactual.passed for record in records),
        "threshold_admissible": sum(record.threshold_admissible for record in records),
        "promoted_admissible": sum(record.promoted_admissible for record in records),
        "mean_forest_size": round(
            sum(record.forest_size for record in records) / total, 3
        )
        if total
        else 0.0,
        "mean_invariance_rate": round(
            sum(record.counterfactual.invariance_rate for record in records) / total,
            4,
        )
        if total
        else 0.0,
        "mean_sensitivity_rate": round(
            sum(record.counterfactual.sensitivity_rate for record in records) / total,
            4,
        )
        if total
        else 0.0,
        "selected_chain_counts": dict(
            Counter(
                " -> ".join(record.selected.morphism_chain) or "<none>"
                for record in records
            ).most_common()
        ),
        "failure_counts": dict(
            Counter(
                failure_reason(record)
                for record in records
                if not record.promoted_admissible
            ).most_common()
        ),
        "category_counts": dict(Counter(record.category for record in records).most_common()),
    }


def failure_reason(record: RepairRecord) -> str:
    if not record.selected.type_checked:
        return "type_check_failed"
    if not record.selected.morphism_chain:
        return "no_composable_morphism"
    if record.selected.warnings:
        return record.selected.warnings[0]
    if not record.counterfactual.passed:
        return "counterfactual_failed"
    if record.promotion_missing:
        return "unpromoted_composition"
    return "below_threshold"


def consume_heldout_guard(path: Path, dataset_sha: str) -> None:
    if path.exists():
        guard = json.loads(path.read_text(encoding="utf-8"))
        if guard.get("dataset_sha256") == dataset_sha:
            raise RuntimeError(
                "Frozen held-out has already been evaluated for this dataset."
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "dataset_sha256": dataset_sha,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "evaluation_count": 1,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def run_semantic_repair_experiment(
    rows: list[dict[str, Any]],
    *,
    split_path: Path,
    heldout_guard_path: Path,
    rebuild_split: bool = False,
    evaluate_heldout: bool = False,
) -> dict[str, Any]:
    split = load_or_create_split(rows, split_path, rebuild=rebuild_split)
    assignments = dict(split["assignments"])
    dev_records = evaluate_rows(rows, assignments, "dev", threshold=0.0)
    promotion_registry = learn_promotions(dev_records)
    calibration_initial = evaluate_rows(rows, assignments, "calibration", threshold=0.0)
    threshold = calibrate_threshold(calibration_initial)

    for record in dev_records:
        record.threshold_admissible = bool(
            record.selected.type_checked
            and record.selected.score >= threshold
            and record.counterfactual.passed
        )
    for record in calibration_initial:
        record.threshold_admissible = bool(
            record.selected.type_checked
            and record.selected.score >= threshold
            and record.counterfactual.passed
        )
    apply_promotions(dev_records, promotion_registry, threshold=threshold)
    apply_promotions(calibration_initial, promotion_registry, threshold=threshold)

    partitions: dict[str, Any] = {
        "dev": {
            "summary": summarize_records(dev_records),
            "records": [record.to_dict() for record in dev_records],
        },
        "calibration": {
            "summary": summarize_records(calibration_initial),
            "records": [record.to_dict() for record in calibration_initial],
        },
    }
    if evaluate_heldout:
        heldout_records = evaluate_rows(
            rows,
            assignments,
            "heldout",
            threshold=threshold,
        )
        apply_promotions(heldout_records, promotion_registry, threshold=threshold)
        partitions["heldout"] = {
            "summary": summarize_records(heldout_records),
            "records": [record.to_dict() for record in heldout_records],
        }
        consume_heldout_guard(heldout_guard_path, str(split["dataset_sha256"]))

    return {
        "experiment": "SemanticRepairLoop-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": {
            "source": "jukenmath.net public problem-list RPC",
            "total": len(rows),
            "dataset_sha256": split["dataset_sha256"],
            "split_path": str(split_path),
            "split_counts": split["counts"],
            "author_and_near_duplicate_disjoint": True,
            "answers_or_solutions_used_for_rules": False,
        },
        "protocol": [
            "finite mathematical lexicon scan",
            "typed parse forest",
            "type-compatible morphism composition",
            "verifier scoring",
            "alpha and numeric invariance",
            "quantifier and query sensitivity",
            "cross-category composition promotion on dev",
            "threshold selection on calibration",
            "single frozen held-out evaluation",
        ],
        "calibrated_score_threshold": threshold,
        "promotion_registry": promotion_registry,
        "partitions": partitions,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# SemanticRepairLoop v1",
        "",
        f"- 公開問題数: {report['dataset']['total']}",
        f"- split: {report['dataset']['split_counts']}",
        f"- calibrated threshold: {report['calibrated_score_threshold']}",
        f"- 昇格した合成規則: {len(report['promotion_registry']['promoted'])}",
        "",
        "## 分割別結果",
        "",
        "| split | total | baseline type-checked | baseline lift | repaired type-checked | CF pass | promoted certificate |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name in SPLIT_NAMES:
        if name not in report["partitions"]:
            continue
        summary = report["partitions"][name]["summary"]
        lines.append(
            f"| {name} | {summary['total']} | {summary['baseline_type_checked']} | "
            f"{summary['baseline_lifted']} | {summary['repair_type_checked']} | "
            f"{summary['counterfactual_passed']} | {summary['promoted_admissible']} |"
        )
    lines.extend(
        [
            "",
            "## 昇格規則",
            "",
            "| composition | dev evidence | domains | counterfactual pass |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for key, evidence in report["promotion_registry"]["promoted"].items():
        lines.append(
            f"| `{key}` | {evidence['count']} | {len(evidence['categories'])} | "
            f"{evidence['counterfactual_pass_rate']:.1%} |"
        )
    lines.extend(
        [
            "",
            "解答文・問題ID・完全な表層文型は規則に保存していない。"
            "証明書の昇格単位は型付き演算子または演算子間の射である。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--split", type=Path, default=DEFAULT_SPLIT)
    parser.add_argument("--heldout-guard", type=Path, default=DEFAULT_HELDOUT_GUARD)
    parser.add_argument("--delay", type=float, default=0.4)
    parser.add_argument("--rebuild-split", action="store_true")
    parser.add_argument("--evaluate-heldout", action="store_true")
    args = parser.parse_args()
    rows = fetch_public_problems(delay_seconds=args.delay)
    report = run_semantic_repair_experiment(
        rows,
        split_path=args.split,
        heldout_guard_path=args.heldout_guard,
        rebuild_split=args.rebuild_split,
        evaluate_heldout=args.evaluate_heldout,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    args.output.with_suffix(".md").write_text(render_markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "dataset": report["dataset"],
                "threshold": report["calibrated_score_threshold"],
                "promoted": report["promotion_registry"]["promoted"],
                "partition_summaries": {
                    name: payload["summary"]
                    for name, payload in report["partitions"].items()
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
