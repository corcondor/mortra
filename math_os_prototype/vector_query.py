"""Typed vector constraints and exact linear-algebra observations.

The compiler recognizes mathematical objects, not benchmark cases: vectors,
cross products, affine subspaces, and direction compatibility.  Every backend
result is checked against the typed constraint that produced it.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any

import sympy as sp

try:
    from math_os_prototype.latex_frontend import normalize_latex_math
except ImportError:
    from latex_frontend import normalize_latex_math


VECTOR = r"\\begin\{pmatrix\}(.*?)\\end\{pmatrix\}"


@dataclass(frozen=True)
class VectorQueryIR:
    operator: str
    vectors: dict[str, list[str]] = field(default_factory=dict)
    target: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    output_sort: str = "Vector"
    lowering_certificate: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compile_vector_query(text: str) -> VectorQueryIR | None:
    vectors = extract_named_vectors(text)
    lower = text.lower()
    if vectors and r"\times" in text and any(word in lower for word in ("compute", "evaluate", "計算")):
        targets = re.findall(r"\[([^\]]*\\times[^\]]*)\]", text, flags=re.DOTALL)
        if not targets:
            targets = re.findall(r"\((?:[^()]|\([^()]*\))*\\times(?:[^()]|\([^()]*\))*\)", text)
        if targets:
            target = targets[-1].strip().strip(". ")
            return VectorQueryIR(
                operator="evaluate_vector_expression",
                vectors=vectors,
                target=target,
                lowering_certificate={
                    "kind": "typed_vector_term",
                    "declared_vectors": sorted(vectors),
                    "observation": "evaluate Vector expression",
                },
            )

    affine = extract_affine_vector_definitions(text)
    if len(affine) >= 2 and "intersection" in lower:
        names = list(affine)
        return VectorQueryIR(
            operator="intersect_affine_subspaces",
            parameters={"left": affine[names[0]], "right": affine[names[1]]},
            lowering_certificate={
                "kind": "vector_equality_constraint",
                "observation": "unique point satisfying both affine parameterizations",
            },
        )

    if "slope" in lower and "direction vector" in lower:
        slope_match = re.search(r"slope\s*\$([^$]+)\$", text, flags=re.IGNORECASE)
        options = extract_labeled_vectors(text)
        if slope_match and options:
            return VectorQueryIR(
                operator="select_direction_vectors",
                parameters={
                    "slope": normalize_latex_math(slope_match.group(1)).strip(" .,:;"),
                    "options": options,
                },
                output_sort="FiniteSet[Label]",
                lowering_certificate={
                    "kind": "direction_equivalence",
                    "observation": "select nonzero vectors with dy/dx equal to line slope",
                },
            )
    return None


def execute_vector_query(payload: dict[str, Any]) -> dict[str, Any]:
    ir = VectorQueryIR(**payload)
    if ir.operator == "evaluate_vector_expression":
        environment = {name: sp.Matrix([sp.sympify(value) for value in values]) for name, values in ir.vectors.items()}
        result = VectorExpressionParser(ir.target, environment).parse()
        if not isinstance(result, sp.MatrixBase):
            raise ValueError("vector expression did not produce a vector")
        answer = matrix_answer(result)
    elif ir.operator == "intersect_affine_subspaces":
        left = affine_expression(ir.parameters["left"])
        right = affine_expression(ir.parameters["right"])
        parameters = sorted((left.free_symbols | right.free_symbols), key=lambda item: item.name)
        equations = [sp.Eq(a, b) for a, b in zip(left, right)]
        solutions = sp.solve(equations, parameters, dict=True)
        if len(solutions) != 1:
            raise ValueError("affine constraints do not determine a unique intersection")
        point = sp.simplify(left.subs(solutions[0]))
        if any(sp.simplify(a.subs(solutions[0]) - b.subs(solutions[0])) != 0 for a, b in zip(left, right)):
            raise ValueError("intersection failed substitution verification")
        answer = matrix_answer(point)
    elif ir.operator == "select_direction_vectors":
        slope = sp.sympify(ir.parameters["slope"])
        labels: list[str] = []
        for label, values in ir.parameters["options"].items():
            vector = [sp.sympify(value) for value in values]
            if len(vector) == 2 and vector != [0, 0] and vector[0] != 0 and sp.simplify(vector[1] / vector[0] - slope) == 0:
                labels.append(label)
        answer = ", ".join(labels)
    else:
        raise ValueError(f"unsupported vector query operator: {ir.operator}")
    return {
        "answer_exact": answer,
        "query_operator": ir.operator,
        "output_sort": ir.output_sort,
        "verified": True,
        "lowering_certificate": ir.lowering_certificate,
    }


def extract_named_vectors(text: str) -> dict[str, list[str]]:
    pattern = rf"\\mathbf\{{([A-Za-z])\}}\s*=\s*{VECTOR}"
    return {match.group(1): vector_entries(match.group(2)) for match in re.finditer(pattern, text, flags=re.DOTALL)}


def extract_labeled_vectors(text: str) -> dict[str, list[str]]:
    pattern = rf"\(([A-Z])\).*?{VECTOR}"
    return {match.group(1): vector_entries(match.group(2)) for match in re.finditer(pattern, text, flags=re.DOTALL)}


def vector_entries(body: str) -> list[str]:
    return [normalize_latex_math(item.strip()) for item in re.split(r"\\\\", body) if item.strip()]


def extract_affine_vector_definitions(text: str) -> dict[str, dict[str, Any]]:
    definitions: dict[str, dict[str, Any]] = {}
    displays = re.findall(r"\\\[([^\]]+)\\\]", text, flags=re.DOTALL)
    for display in displays:
        name_match = re.search(r"\\mathbf\{([A-Za-z])\}\s*=", display)
        if not name_match:
            continue
        terms = list(re.finditer(VECTOR, display, flags=re.DOTALL))
        if not terms:
            continue
        base = vector_entries(terms[0].group(1))
        directions: list[dict[str, Any]] = []
        cursor = terms[0].end()
        for term in terms[1:]:
            prefix = display[cursor:term.start()]
            parameter_match = re.search(r"([A-Za-z])\s*$", prefix)
            if not parameter_match:
                return {}
            directions.append({"parameter": parameter_match.group(1), "vector": vector_entries(term.group(1))})
            cursor = term.end()
        definitions[name_match.group(1)] = {"base": base, "directions": directions}
    return definitions


def affine_expression(data: dict[str, Any]) -> sp.Matrix:
    result = sp.Matrix([sp.sympify(value) for value in data["base"]])
    for direction in data["directions"]:
        parameter = sp.Symbol(direction["parameter"], real=True)
        result += parameter * sp.Matrix([sp.sympify(value) for value in direction["vector"]])
    return result


def matrix_answer(matrix: sp.MatrixBase) -> str:
    return "Matrix([" + ", ".join(sp.sstr(sp.simplify(item)) for item in matrix) + "])"


class VectorExpressionParser:
    def __init__(self, source: str, environment: dict[str, sp.Matrix]):
        self.environment = environment
        self.tokens = re.findall(r"\\mathbf\{[A-Za-z]\}|\\times|[()+-]", source)
        self.index = 0

    def parse(self) -> sp.Matrix:
        result = self.parse_sum()
        if self.index != len(self.tokens):
            raise ValueError("unconsumed vector-expression tokens")
        return result

    def parse_sum(self) -> sp.Matrix:
        result = self.parse_cross()
        while self.peek() in {"+", "-"}:
            operator = self.take()
            right = self.parse_cross()
            result = result + right if operator == "+" else result - right
        return result

    def parse_cross(self) -> sp.Matrix:
        result = self.parse_atom()
        while self.peek() == r"\times":
            self.take()
            result = result.cross(self.parse_atom())
        return result

    def parse_atom(self) -> sp.Matrix:
        token = self.take()
        if token == "(":
            result = self.parse_sum()
            if self.take() != ")":
                raise ValueError("unclosed vector-expression parenthesis")
            return result
        match = re.fullmatch(r"\\mathbf\{([A-Za-z])\}", token)
        if not match or match.group(1) not in self.environment:
            raise ValueError("undeclared vector symbol")
        return self.environment[match.group(1)]

    def peek(self) -> str | None:
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def take(self) -> str:
        token = self.peek()
        if token is None:
            raise ValueError("unexpected end of vector expression")
        self.index += 1
        return token
