"""Tiny Math Tool OS prototype.

This file is intentionally self-contained. It demonstrates a small router that
turns a math problem into a typed intermediate representation, then delegates
work to symbolic, geometric, or formal-proof backends.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

try:
    from math_os_prototype.arithmetic_nl import detect_arithmetic_nl_problem, solve_arithmetic_nl_problem
    from math_os_prototype.asymptote_geometry import detect_asymptote_geometry_problem, solve_asymptote_geometry_problem
    from math_os_prototype.container_geometry import detect_container_problem, solve_container_problem
    from math_os_prototype.cubic_centroid_locus import (
        compile_cubic_centroid_locus_query,
        execute_cubic_centroid_locus_query,
    )
    from math_os_prototype.discrete_constraint_query import compile_discrete_constraint_query, execute_discrete_constraint_query
    from math_os_prototype.field_adapters import detect_specialized_problem, solve_specialized_problem
    from math_os_prototype.finite_relation_query import compile_finite_relation_query, execute_finite_relation_query
    from math_os_prototype.geometry_dsl import inspect_geometry_dsl, run_geometry_dsl
    from math_os_prototype.geometry_nl import convert_geometry_nl
    from math_os_prototype.iteration_query import compile_iteration_query, execute_iteration_query
    from math_os_prototype.hilbert_witness_query import compile_hilbert_witness_query, execute_hilbert_witness_query
    from math_os_prototype.latex_frontend import looks_like_latex, parse_latex_problem
    from math_os_prototype.linear_constraint_query import compile_linear_constraint_query, execute_linear_constraint_query
    from math_os_prototype.matrix_semantic_query import compile_matrix_semantic_query, execute_matrix_semantic_query
    from math_os_prototype.progression_query import compile_progression_query, execute_progression_query
    from math_os_prototype.prime_structure_query import compile_prime_structure_query, execute_prime_structure_query
    from math_os_prototype.symbolic_query import compile_symbolic_query, execute_symbolic_query
    from math_os_prototype.typed_analysis_query import compile_typed_analysis_query, execute_typed_analysis_query
    from math_os_prototype.vector_query import compile_vector_query, execute_vector_query
    from math_os_prototype.tool_adapters import ToolRegistry
except ImportError:  # Allows `python math_os_prototype\math_os.py ...`.
    from arithmetic_nl import detect_arithmetic_nl_problem, solve_arithmetic_nl_problem
    from asymptote_geometry import detect_asymptote_geometry_problem, solve_asymptote_geometry_problem
    from container_geometry import detect_container_problem, solve_container_problem
    from cubic_centroid_locus import compile_cubic_centroid_locus_query, execute_cubic_centroid_locus_query
    from discrete_constraint_query import compile_discrete_constraint_query, execute_discrete_constraint_query
    from field_adapters import detect_specialized_problem, solve_specialized_problem
    from finite_relation_query import compile_finite_relation_query, execute_finite_relation_query
    from geometry_dsl import inspect_geometry_dsl, run_geometry_dsl
    from geometry_nl import convert_geometry_nl
    from iteration_query import compile_iteration_query, execute_iteration_query
    from hilbert_witness_query import compile_hilbert_witness_query, execute_hilbert_witness_query
    from latex_frontend import looks_like_latex, parse_latex_problem
    from linear_constraint_query import compile_linear_constraint_query, execute_linear_constraint_query
    from matrix_semantic_query import compile_matrix_semantic_query, execute_matrix_semantic_query
    from progression_query import compile_progression_query, execute_progression_query
    from prime_structure_query import compile_prime_structure_query, execute_prime_structure_query
    from symbolic_query import compile_symbolic_query, execute_symbolic_query
    from typed_analysis_query import compile_typed_analysis_query, execute_typed_analysis_query
    from vector_query import compile_vector_query, execute_vector_query
    from tool_adapters import ToolRegistry

try:
    import sympy as sp
except ImportError:  # pragma: no cover - exercised only when SymPy is missing.
    sp = None


LABELS = (
    "symbolic_algebra",
    "calculus",
    "geometry_symbolic",
    "convex_geometry",
    "formal_proof",
    "numeric_search",
    "vision_geometry",
)


BASE_WEIGHTS: dict[str, dict[str, float]] = {
    "solve": {"symbolic_algebra": 2.0},
    "equation": {"symbolic_algebra": 1.5},
    "factor": {"symbolic_algebra": 1.5},
    "simplify": {"symbolic_algebra": 1.5},
    "方程式": {"symbolic_algebra": 2.0},
    "解け": {"symbolic_algebra": 1.0},
    "因数分解": {"symbolic_algebra": 2.0},
    "微分": {"calculus": 2.0},
    "積分": {"calculus": 2.0},
    "極限": {"calculus": 2.0},
    "derivative": {"calculus": 2.0},
    "integral": {"calculus": 2.0},
    "limit": {"calculus": 2.0},
    "包絡線": {"geometry_symbolic": 3.5},
    "通過領域": {"geometry_symbolic": 3.0},
    "軌跡": {"geometry_symbolic": 2.5},
    "envelope": {"geometry_symbolic": 3.5},
    "locus": {"geometry_symbolic": 2.5},
    "eliminate": {"geometry_symbolic": 2.0},
    "ミンコフスキー": {"convex_geometry": 4.0},
    "minkowski": {"convex_geometry": 4.0},
    "凸包": {"convex_geometry": 2.5},
    "convex": {"convex_geometry": 2.0},
    "support": {"convex_geometry": 1.5},
    "証明": {"formal_proof": 3.0},
    "prove": {"formal_proof": 3.0},
    "lean": {"formal_proof": 4.0},
    "theorem": {"formal_proof": 2.5},
    "mathlib": {"formal_proof": 3.0},
    "近似": {"numeric_search": 2.0},
    "探索": {"numeric_search": 2.0},
    "反例": {"numeric_search": 2.0},
    "numeric": {"numeric_search": 2.0},
    "counterexample": {"numeric_search": 2.0},
    "図": {"vision_geometry": 2.0},
    "画像": {"vision_geometry": 3.0},
    "vision": {"vision_geometry": 3.0},
    "diagram": {"vision_geometry": 2.5},
    "接線": {"geometry_symbolic": 1.0, "calculus": 1.0},
}


JAPANESE_KEYWORDS = tuple(BASE_WEIGHTS.keys())
SYMPY_FUNCTIONS = ("sin", "cos", "tan", "log", "exp", "sqrt")


@dataclass
class RouteDecision:
    label: str
    scores: dict[str, float]
    nonzero_parameters: int

    @property
    def ranked(self) -> list[tuple[str, float]]:
        return sorted(self.scores.items(), key=lambda item: item[1], reverse=True)


@dataclass
class ToolCall:
    name: str
    command: str
    executable: bool
    status: str = "planned"
    result: Any | None = None
    error: str | None = None


@dataclass
class MathIR:
    problem: str
    route: str
    intent: str
    symbols: list[str]
    givens: dict[str, Any]
    goal: str
    plan: list[str]
    tool_calls: list[ToolCall] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    route_scores: dict[str, float] = field(default_factory=dict)
    router_parameters: int = 0

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


class TinyRouter:
    """A tiny trainable router.

    It is deliberately small: each feature-label edge is one scalar parameter.
    The default model is a hand-seeded prior; `train_jsonl` can refine it with a
    perceptron update without importing machine-learning frameworks.
    """

    def __init__(self, weights: dict[str, dict[str, float]] | None = None):
        self.weights: dict[str, dict[str, float]] = {
            feature: dict(label_weights)
            for feature, label_weights in (weights or BASE_WEIGHTS).items()
        }

    @classmethod
    def load(cls, path: Path) -> "TinyRouter":
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls(payload["weights"])

    def save(self, path: Path) -> None:
        payload = {"labels": LABELS, "weights": self.weights}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @property
    def nonzero_parameters(self) -> int:
        return sum(len(label_weights) for label_weights in self.weights.values())

    def route(self, text: str) -> RouteDecision:
        scores = {label: 0.0 for label in LABELS}
        for feature in self.features(text):
            for label, weight in self.weights.get(feature, {}).items():
                scores[label] += weight
        if "=" in text:
            scores["symbolic_algebra"] += 0.25
            scores["geometry_symbolic"] += 0.25
        if any(ch in text for ch in ("(", "[", "{")):
            scores["convex_geometry"] += 0.1
            scores["symbolic_algebra"] += 0.1
        label = max(scores, key=scores.get)
        return RouteDecision(label, scores, self.nonzero_parameters)

    def train_jsonl(self, path: Path, epochs: int = 8, learning_rate: float = 1.0) -> None:
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        for _ in range(epochs):
            for row in rows:
                expected = row["label"]
                decision = self.route(row["text"])
                if decision.label == expected:
                    continue
                for feature in self.features(row["text"]):
                    label_weights = self.weights.setdefault(feature, {})
                    label_weights[expected] = label_weights.get(expected, 0.0) + learning_rate
                    label_weights[decision.label] = label_weights.get(decision.label, 0.0) - learning_rate

    def features(self, text: str) -> list[str]:
        lower = normalize_math_text(text.lower())
        tokens = re.findall(r"[a-zA-Z_][a-zA-Z_0-9]*|\d+(?:\.\d+)?", lower)
        features = list(tokens)
        for keyword in JAPANESE_KEYWORDS:
            if keyword in text or keyword in lower:
                features.append(keyword)
        if re.search(r"\by\s*=", lower):
            features.append("equation")
        return features


class ProblemCompiler:
    def __init__(self, router: TinyRouter | None = None, *, allow_specialized: bool = False):
        self.router = router or TinyRouter()
        self.allow_specialized = allow_specialized

    def compile(self, text: str) -> MathIR:
        specialized_problem = detect_specialized_problem(text) if self.allow_specialized else None
        if specialized_problem is not None:
            return MathIR(
                problem=text,
                route=specialized_problem.domain,
                intent=specialized_problem.intent,
                symbols=specialized_problem.symbols,
                givens=specialized_problem.givens,
                goal=specialized_problem.goal,
                plan=specialized_problem.plan,
                tool_calls=[
                    ToolCall(
                        specialized_problem.tool_name,
                        specialized_problem.command,
                        executable=specialized_problem.executable,
                    )
                ],
            )
        if self.allow_specialized and looks_like_latex(text):
            specialized_latex = parse_latex_problem(text)
            specialized_problem = detect_specialized_problem(specialized_latex.normalized_text)
            if specialized_problem is not None:
                return MathIR(
                    problem=text,
                    route=specialized_problem.domain,
                    intent=f"latex_to_{specialized_problem.intent}",
                    symbols=specialized_problem.symbols,
                    givens={**specialized_problem.givens, "latex_parse": asdict(specialized_latex)},
                    goal=specialized_problem.goal,
                    plan=specialized_problem.plan,
                    tool_calls=[
                        ToolCall(
                            specialized_problem.tool_name,
                            specialized_problem.command,
                            executable=specialized_problem.executable,
                        )
                    ],
                    notes=[f"Normalized LaTeX problem text: {specialized_latex.normalized_text}"],
                )

        cubic_centroid_query = compile_cubic_centroid_locus_query(text)
        if cubic_centroid_query is not None:
            payload = cubic_centroid_query.to_dict()
            return MathIR(
                problem=text,
                route="geometry_symbolic",
                intent="cubic_equilateral_centroid_locus_area",
                symbols=[cubic_centroid_query.variable],
                givens={"cubic_centroid_locus_query": payload},
                goal="Derive and integrate the centroid locus of equilateral triples on a cubic.",
                plan=[
                    "Translate and, if needed, reflect the cubic by Euclidean isometries.",
                    "Represent equilateral vertices by three phase-shifted radius vectors.",
                    "Eliminate phase through the aliased Fourier-mode constraints.",
                    "Integrate the verified algebraic boundary branches.",
                ],
                tool_calls=[ToolCall("sympy.cubic_centroid_locus", "eliminate phase and integrate locus", executable=True)],
            )

        iteration_query = compile_iteration_query(text)
        if iteration_query is not None:
            payload = iteration_query.to_dict()
            return MathIR(
                problem=text,
                route="calculus",
                intent="iteration_convergence",
                symbols=[],
                givens={"iteration_query": payload},
                goal="Determine the convergence of a self-similar scalar iteration.",
                plan=[
                    "Recover the repeated layer as a scalar iteration map.",
                    "Compare the map with the diagonal through an exact logarithmic minimum.",
                    "Use monotonicity and the fixed-point condition to decide convergence.",
                    "Return the limit with a reusable convergence certificate.",
                ],
                tool_calls=[ToolCall("sympy.iteration_query", iteration_query.operator, executable=True)],
            )

        analysis_query = compile_typed_analysis_query(text)
        if analysis_query is not None:
            payload = analysis_query.to_dict()
            route = "calculus" if analysis_query.operator in {"limit", "integral"} else "formal_proof"
            return MathIR(
                problem=text,
                route=route,
                intent=f"typed_analysis_{analysis_query.operator}",
                symbols=[],
                givens={"typed_analysis_query": payload},
                goal=f"Execute the closed typed analysis observation {analysis_query.operator}.",
                plan=[
                    "Parse the complete LaTeX operator tree and reject partial multi-part matches.",
                    "Type-check bound variables, constants, and the requested output sort.",
                    "Execute the exact symbolic operation.",
                    "Reject results containing unevaluated operators or indeterminate values.",
                ],
                tool_calls=[ToolCall("sympy.typed_analysis_query", analysis_query.operator, executable=True)],
            )

        progression_query = compile_progression_query(text)
        if progression_query is not None:
            payload = progression_query.to_dict()
            return MathIR(
                problem=text,
                route="symbolic_algebra",
                intent=f"progression_{progression_query.progression}_constraint",
                symbols=[],
                givens={"progression_query": payload},
                goal="Solve a finite progression relation by its algebraic definition.",
                plan=[
                    "Parse the ordered terms without attaching a problem-family template.",
                    "Lower the progression definition to an exact algebraic relation.",
                    "Eliminate auxiliary trigonometric coordinates with their defining identity.",
                    "Filter candidates by the source domain and substitute them back.",
                ],
                tool_calls=[ToolCall("sympy.progression_query", progression_query.progression, executable=True)],
            )

        hilbert_query = compile_hilbert_witness_query(text)
        if hilbert_query is not None:
            payload = hilbert_query.to_dict()
            return MathIR(
                problem=text,
                route="functional_analysis",
                intent="hilbert_normalized_inner_product_witness",
                symbols=[hilbert_query.variable],
                givens={"hilbert_witness_query": payload},
                goal="Construct a pair with the requested normalized inner product.",
                plan=[
                    "Parse the common integration interval and target correlation.",
                    "Construct an explicit orthonormal pair in the interval L2 space.",
                    "Rotate in the resulting two-dimensional subspace.",
                    "Verify both norms and the inner product by exact integration.",
                ],
                tool_calls=[ToolCall("sympy.hilbert_witness_query", "construct orthonormal witness", executable=True)],
            )

        prime_query = compile_prime_structure_query(text)
        if prime_query is not None:
            payload = prime_query.to_dict()
            return MathIR(
                problem=text,
                route="number_theory",
                intent=f"prime_structure_{prime_query.operator}",
                symbols=[],
                givens={"prime_structure_query": payload},
                goal="Discharge the theorem by reusable consequences of the Prime type.",
                plan=[
                    "Elaborate primality into parity and integer-set constraints.",
                    "Split the finite parity cases or embed primes into a tractable superset.",
                    "Reduce the goal to exact rational, zeta, or quadratic-residue obligations.",
                    "Replay every branch and reject the theorem if one branch remains open.",
                ],
                tool_calls=[ToolCall("sympy.prime_structure_query", prime_query.operator, executable=True)],
            )

        finite_relation = compile_finite_relation_query(text)
        if finite_relation is not None:
            payload = finite_relation.to_dict()
            return MathIR(
                problem=text,
                route="symbolic_algebra",
                intent=f"finite_relation_{finite_relation.relation}",
                symbols=[finite_relation.variable],
                givens={"finite_relation_query": payload},
                goal="Solve a typed finite relation with exactly one hole.",
                plan=[
                    "Lift values into a finite partition or state-transition relation.",
                    "Check that every numeric premise is consumed exactly once.",
                    "Solve the one-hole equation with exact arithmetic.",
                    "Substitute the observation back into the typed relation.",
                ],
                tool_calls=[ToolCall("sympy.finite_relation_query", finite_relation.equation, executable=True)],
            )

        arithmetic_problem = detect_arithmetic_nl_problem(
            text,
            allow_surface_morphisms=self.allow_specialized,
        )
        if arithmetic_problem is not None:
            return MathIR(
                problem=text,
                route="symbolic_algebra",
                intent=f"arithmetic_nl_{arithmetic_problem.intent}",
                symbols=[],
                givens={"arithmetic_problem": arithmetic_problem.to_dict()},
                goal="Evaluate an arithmetic expression compiled from deterministic natural-language syntax.",
                plan=[
                    "Scan the problem with finite natural-language arithmetic templates.",
                    "Compile the matched construction into an explicit arithmetic expression.",
                    "Evaluate the expression exactly with rational arithmetic.",
                    "Return the answer plus the compiled expression for verification.",
                ],
                tool_calls=[
                    ToolCall(
                        "arithmetic.nl",
                        arithmetic_problem.expression,
                        executable=True,
                    )
                ],
            )

        asymptote_problem = detect_asymptote_geometry_problem(text)
        if asymptote_problem is not None:
            return MathIR(
                problem=text,
                route="geometry_symbolic",
                intent="asymptote_coordinate_area",
                symbols=list(asymptote_problem.polygon),
                givens={"asymptote_geometry": asymptote_problem.to_dict()},
                goal="Evaluate the embedded coordinate construction and its requested area.",
                plan=[
                    "Parse the embedded Asymptote coordinate program.",
                    "Evaluate point constructions and line intersections exactly.",
                    "Apply any stated regular-polygon side-length scale.",
                    "Verify the requested polygon area by the shoelace determinant.",
                ],
                tool_calls=[ToolCall("geometry.asymptote_exact", "execute typed coordinate construction", executable=True)],
            )

        discrete_query = compile_discrete_constraint_query(text)
        if discrete_query is not None:
            payload = discrete_query.to_dict()
            return MathIR(
                problem=text,
                route="discrete_mathematics",
                intent=f"discrete_constraint_{discrete_query.operator}",
                symbols=[],
                givens={"discrete_constraint_query": payload},
                goal=f"Execute the typed discrete observation {discrete_query.observation}.",
                plan=[
                    "Elaborate a finite domain or congruence-class domain.",
                    "Compile textual conditions to typed predicates.",
                    "Execute exact modular arithmetic or finite-set enumeration.",
                    "Recheck every accepted member against the source predicates.",
                ],
                tool_calls=[ToolCall("sympy.discrete_constraint_query", discrete_query.operator, executable=True)],
            )

        vector_query = compile_vector_query(text)
        if vector_query is not None:
            payload = vector_query.to_dict()
            return MathIR(
                problem=text,
                route="linear_algebra",
                intent=f"vector_query_{vector_query.operator}",
                symbols=sorted(vector_query.vectors),
                givens={"vector_query": payload},
                goal=f"Execute the typed vector observation {vector_query.operator}.",
                plan=[
                    "Parse vector declarations and affine constraints with explicit sorts.",
                    "Type-check vector, scalar, and cross-product operations.",
                    "Execute the resulting exact linear-algebra constraint system.",
                    "Re-verify the result against the source constraints.",
                ],
                tool_calls=[ToolCall("sympy.vector_query", vector_query.operator, executable=True)],
            )

        matrix_query = compile_matrix_semantic_query(text)
        if matrix_query is not None:
            payload = matrix_query.to_dict()
            return MathIR(
                problem=text,
                route="matrix_geometry",
                intent=f"matrix_semantic_{matrix_query.query_operator}",
                symbols=matrix_query.variables,
                givens={"matrix_semantic_query": payload},
                goal=f"Execute {matrix_query.query_operator} in the typed chart {matrix_query.chart}.",
                plan=[
                    "Elaborate polynomial, point, root, or conic objects from TeX.",
                    "Lower them to an evaluation matrix or homogeneous quadratic form.",
                    "Execute the requested observation with exact matrix algebra.",
                    "Recheck the source incidence, determinant, and domain constraints.",
                ],
                tool_calls=[
                    ToolCall(
                        "sympy.matrix_semantic_query",
                        f"{matrix_query.query_operator}({matrix_query.representation['kind']})",
                        executable=True,
                    )
                ],
            )

        linear_query = compile_linear_constraint_query(text)
        if linear_query is not None:
            payload = linear_query.to_dict()
            return MathIR(
                problem=text,
                route="symbolic_algebra",
                intent="linear_constraint_projection",
                symbols=linear_query.variables,
                givens={"linear_constraint_query": payload},
                goal="Evaluate a typed observation over a rational linear constraint graph.",
                plan=[
                    "Lift named quantities to alpha-renamable typed vertices.",
                    "Compile weighted equality clauses into rational linear constraints.",
                    "Project the requested scalar through exact elimination.",
                    "Substitute the result back into every source constraint.",
                ],
                tool_calls=[
                    ToolCall(
                        "sympy.linear_constraint_query",
                        "solve typed rational constraints and evaluate projection",
                        executable=True,
                    )
                ],
            )

        symbolic_query = compile_symbolic_query(text)
        if symbolic_query is not None:
            payload = symbolic_query.to_dict()
            return MathIR(
                problem=text,
                route="symbolic_algebra",
                intent=f"symbolic_query_{symbolic_query.query_operator}",
                symbols=symbolic_query.variables,
                givens={"symbolic_query": payload},
                goal=f"Execute the typed query operator {symbolic_query.query_operator} over parsed constraints.",
                plan=[
                    "Parse TeX math spans separately from prose.",
                    "Build Constraint + QueryOperator + OutputSort IR.",
                    "Execute the query operator with exact symbolic arithmetic.",
                    "Return the result with its query provenance.",
                ],
                tool_calls=[
                    ToolCall(
                        "sympy.semantic_query",
                        f"{symbolic_query.query_operator}({symbolic_query.target})",
                        executable=True,
                    )
                ],
            )

        if looks_like_latex(text):
            latex_problem = parse_latex_problem(text)
            can_reparse = (
                latex_problem.normalized_text != text
                and latex_problem.normalized_text
                and not looks_like_latex(latex_problem.normalized_text)
            )
            if can_reparse:
                normalized_specialized = (
                    detect_specialized_problem(latex_problem.normalized_text)
                    if self.allow_specialized
                    else None
                )
                if normalized_specialized is not None:
                    return MathIR(
                        problem=text,
                        route=normalized_specialized.domain,
                        intent=f"latex_to_{normalized_specialized.intent}",
                        symbols=normalized_specialized.symbols,
                        givens={
                            **normalized_specialized.givens,
                            "latex_parse": asdict(latex_problem),
                        },
                        goal=normalized_specialized.goal,
                        plan=normalized_specialized.plan,
                        tool_calls=[
                            ToolCall(
                                normalized_specialized.tool_name,
                                normalized_specialized.command,
                                executable=normalized_specialized.executable,
                            )
                        ],
                        notes=[f"Normalized LaTeX problem text: {latex_problem.normalized_text}"],
                    )
                ir = self.compile(latex_problem.normalized_text)
                ir.problem = text
                ir.intent = f"latex_to_{ir.intent}"
                ir.givens["latex_parse"] = asdict(latex_problem)
                ir.notes.append(f"Normalized LaTeX problem text: {latex_problem.normalized_text}")
                return ir

        if looks_like_geometry_dsl(text):
            return self._compile_geometry_dsl_source(text)

        polynomial_remainder = detect_polynomial_remainder_problem(text)
        if polynomial_remainder is not None:
            dividend, divisor, variable = polynomial_remainder
            return MathIR(
                problem=text,
                route="symbolic_algebra",
                intent="polynomial_remainder",
                symbols=[variable],
                givens={"dividend": dividend, "divisor": divisor, "variable": variable},
                goal="Compute the polynomial remainder after division.",
                plan=[
                    "Parse the dividend, divisor, and polynomial variable.",
                    "Run polynomial division over the symbolic polynomial ring.",
                    "Return the remainder.",
                    "Verify that dividend - remainder is divisible by the divisor.",
                ],
                tool_calls=[
                    ToolCall(
                        "sympy.polynomial_remainder",
                        f"rem({dividend}, {divisor}, {variable})",
                        executable=True,
                    )
                ],
            )

        container_problem = detect_container_problem(text)
        if container_problem is not None:
            return MathIR(
                problem=text,
                route="geometry_symbolic",
                intent="container_square_in_equilateral_triangle_sweep",
                symbols=[],
                givens={"container_problem": asdict(container_problem)},
                goal="Compute the swept area of a moving equilateral triangle constrained to contain a fixed square.",
                plan=[
                    "Parse the fixed square side and moving equilateral triangle side.",
                    "Convert containment into support-function inequalities.",
                    "Use D4 symmetry and the swept hexagon-vertex boundary.",
                    "Evaluate the exact line integral for the swept area.",
                ],
                tool_calls=[
                    ToolCall(
                        "container.square_in_equilateral_triangle",
                        "support-function boundary integration",
                        executable=True,
                    )
                ],
            )

        nl_conversion = convert_geometry_nl(text)
        if nl_conversion is not None:
            ir = self._compile_geometry_dsl_source(nl_conversion.dsl)
            ir.problem = text
            ir.intent = f"geometry_nl_to_dsl_{nl_conversion.task}"
            ir.givens["nl_conversion"] = asdict(nl_conversion)
            ir.notes.append(f"Converted natural language to Geometry DSL: {nl_conversion.dsl}")
            return ir

        decision = self.router.route(text)
        route = decision.label
        if contains_any(text, ("包絡線", "envelope", "通過領域", "軌跡")):
            route = "geometry_symbolic"
        if contains_any(text, ("ミンコフスキー", "minkowski")):
            route = "convex_geometry"
        if contains_any(text, ("Lean", "lean", "証明", "prove", "theorem")):
            route = "formal_proof"

        if route == "geometry_symbolic":
            ir = self._compile_geometry_symbolic(text)
        elif route == "convex_geometry":
            ir = self._compile_convex_geometry(text)
        elif route == "formal_proof":
            ir = self._compile_formal_proof(text)
        elif route == "calculus":
            ir = self._compile_calculus(text)
        elif route == "vision_geometry":
            ir = self._compile_vision_geometry(text)
        else:
            ir = self._compile_symbolic_algebra(text)

        ir.route_scores = decision.scores
        ir.router_parameters = decision.nonzero_parameters
        return ir

    def _compile_geometry_dsl_source(self, text: str) -> MathIR:
        inspection = inspect_geometry_dsl(text)
        problem = inspection["problem"]
        return MathIR(
            problem=text,
            route="geometry_symbolic",
            intent=f"geometry_dsl_{problem['task']}",
            symbols=["x", "y", problem["parameter"]],
            givens={"dsl_source": text, "geometry_problem": problem},
            goal="Execute a strict geometry DSL instead of relying on free-form text.",
            plan=[
                "Parse the dedicated geometry DSL.",
                "Lower the problem to algebraic equations and parameter constraints.",
                "Use resultants or finite candidate reduction where supported.",
                "Return an exact relation or a tool-ready quantifier-elimination form.",
            ],
            tool_calls=[
                ToolCall(
                    "geometry.dsl",
                    inspection["command"],
                    executable=inspection["executable"],
                )
            ],
        )

    def _compile_geometry_symbolic(self, text: str) -> MathIR:
        centroid_problem = detect_equilateral_centroid_locus_area_problem(text)
        if centroid_problem is not None:
            return MathIR(
                problem=text,
                route="geometry_symbolic",
                intent="equilateral_triangle_centroid_locus_area",
                symbols=["u", "v", "w", "X", "Y"],
                givens=centroid_problem,
                goal="Formalize the centroid-locus area problem as executable geometric constraints.",
                plan=[
                    "Introduce free point variables P1, P2, P3, and G.",
                    "Emit PointOnCurve constraints for all triangle vertices.",
                    "Emit Equilateral and Centroid constraints without using a memorized formula.",
                    "Return a LocusQuery plus AreaQuery that downstream CAS/proof/search tools must solve and verify.",
                ],
                tool_calls=[
                    ToolCall(
                        "geometry.constraint_ir",
                        "emit GeometryConstraintIR(PointOnCurve, Equilateral, Centroid, LocusQuery, AreaQuery)",
                        executable=True,
                    )
                ],
            )

        expr = extract_y_expression(text)
        parameter = extract_parameter(text, expr or "")
        if expr:
            command = (
                "SymPy resultant: eliminate parameter from "
                f"F = y - ({expr}) and dF/d{parameter} = 0"
            )
            return MathIR(
                problem=text,
                route="geometry_symbolic",
                intent="envelope_by_elimination",
                symbols=["x", "y", parameter],
                givens={"family": f"y = {expr}", "parameter": parameter},
                goal="Compute the envelope relation in x and y.",
                plan=[
                    "Translate the curve family to F(x, y, parameter) = 0.",
                    "Add the stationarity condition dF/d(parameter) = 0.",
                    "Eliminate the parameter with a resultant.",
                    "Factor the relation and report the geometric curve.",
                ],
                tool_calls=[ToolCall("sympy.envelope", command, executable=True)],
            )

        command = (
            "Mathematica Reduce/Eliminate or SymPy quantifier elimination over "
            "the parameters that define the locus/passing region"
        )
        return MathIR(
            problem=text,
            route="geometry_symbolic",
            intent="region_or_locus_elimination",
            symbols=[],
            givens={},
            goal="Convert the geometric condition to an eliminable formula.",
            plan=[
                "Identify parameters and inequalities that define the moving object.",
                "Build an existential formula for the target point.",
                "Eliminate parameters to get the region boundary or locus.",
                "Use numeric sampling only as a conjecture generator.",
            ],
            tool_calls=[ToolCall("cas.eliminate", command, executable=False)],
            notes=["No explicit y = ... family was detected, so this stays as a planned tool call."],
        )

    def _compile_convex_geometry(self, text: str) -> MathIR:
        polygons = extract_polygons(text)
        calls = []
        notes = []
        if len(polygons) >= 2:
            command = f"convex_hull(pairwise_sums({polygons[0]}, {polygons[1]}))"
            calls.append(ToolCall("geometry.minkowski_sum", command, executable=True))
            givens: dict[str, Any] = {"polygon_a": polygons[0], "polygon_b": polygons[1]}
        else:
            command = "Shapely/CGAL Minkowski sum after parsing polygon vertices"
            calls.append(ToolCall("geometry.minkowski_sum", command, executable=False))
            givens = {}
            notes.append("Provide polygons like [(0,0),(1,0),(1,1),(0,1)] + [(0,0),(2,0),(0,1)].")
        return MathIR(
            problem=text,
            route="convex_geometry",
            intent="minkowski_sum_or_convex_operation",
            symbols=[],
            givens=givens,
            goal="Compute a convex-geometric object, preferably as vertices or inequalities.",
            plan=[
                "Parse convex sets into vertex or half-space form.",
                "For polygons, compute all pairwise vertex sums.",
                "Take the convex hull to remove redundant points.",
                "Return both vertices and a command that can be delegated to a geometry engine.",
            ],
            tool_calls=calls,
            notes=notes,
        )

    def _compile_formal_proof(self, text: str) -> MathIR:
        theorem_name = "generated_problem"
        lean_stub = (
            "import Mathlib\n\n"
            f"-- Problem: {text}\n"
            f"theorem {theorem_name} : True := by\n"
            "  trivial\n"
        )
        return MathIR(
            problem=text,
            route="formal_proof",
            intent="lean_formalization",
            symbols=[],
            givens={"lean_stub": lean_stub},
            goal="Produce a Lean theorem skeleton and a verification command.",
            plan=[
                "Extract assumptions and target proposition.",
                "Map informal terms to Mathlib names.",
                "Generate a Lean theorem skeleton.",
                "Ask Lean to check it; use failures as feedback for repair.",
            ],
            tool_calls=[
                ToolCall(
                    "lean.check",
                    "lake env lean GeneratedProblem.lean",
                    executable=False,
                )
            ],
            notes=["The prototype emits a stub; a real Lean backend would replace True with the parsed proposition."],
        )

    def _compile_calculus(self, text: str) -> MathIR:
        derivative_request = detect_derivative_request(text)
        if derivative_request:
            expression, variable = derivative_request
        else:
            expression = extract_expression_after_keyword(text, ("微分", "derivative", "differentiate"))
            variable = extract_variable(text) or "x"
        if expression:
            command = f"diff({expression}, {variable})"
            call = ToolCall("sympy.diff", command, executable=True)
            givens = {"expression": expression, "variable": variable}
        else:
            call = ToolCall("sympy.calculus", "SymPy diff/integrate/limit after expression parsing", executable=False)
            givens = {}
        return MathIR(
            problem=text,
            route="calculus",
            intent="calculus_symbolic",
            symbols=[variable],
            givens=givens,
            goal="Delegate calculus manipulation to a CAS.",
            plan=[
                "Parse the target expression and variable.",
                "Choose diff, integrate, limit, or series expansion.",
                "Run the CAS operation.",
                "Simplify and sanity-check with numeric substitution.",
            ],
            tool_calls=[call],
        )

    def _compile_vision_geometry(self, text: str) -> MathIR:
        return MathIR(
            problem=text,
            route="vision_geometry",
            intent="diagram_to_geometry_ir",
            symbols=[],
            givens={},
            goal="Convert a diagram into points, lines, circles, constraints, and target claims.",
            plan=[
                "Detect primitives from the image: points, segments, circles, labels.",
                "Snap noisy primitives to geometric constraints.",
                "Emit Geometry IR instead of asking a language model to reason from pixels.",
                "Pass the IR to symbolic geometry or Lean.",
            ],
            tool_calls=[
                ToolCall(
                    "vision.geometry_parser",
                    "detect_primitives(image) -> GeometryIR(points, lines, circles, constraints)",
                    executable=False,
                )
            ],
        )

    def _compile_symbolic_algebra(self, text: str) -> MathIR:
        equation, variable = extract_equation(text)
        if equation:
            command = f"solve({equation}, {variable})"
            call = ToolCall("sympy.solve", command, executable=True)
            givens = {"equation": equation, "variable": variable}
        else:
            call = ToolCall("sympy.algebra", "SymPy solve/factor/simplify after expression parsing", executable=False)
            givens = {}
        return MathIR(
            problem=text,
            route="symbolic_algebra",
            intent="cas_symbolic_algebra",
            symbols=[variable] if variable else [],
            givens=givens,
            goal="Delegate algebraic manipulation to a CAS.",
            plan=[
                "Parse expressions and target variables.",
                "Choose solve, factor, simplify, or eliminate.",
                "Run the CAS operation.",
                "Format the result and optionally verify by substitution.",
            ],
            tool_calls=[call],
        )


class ToolExecutor:
    def __init__(self, external_tools: bool = False):
        self.external_tools = external_tools

    def execute(self, ir: MathIR) -> MathIR:
        for call in ir.tool_calls:
            if not call.executable:
                continue
            try:
                if call.name == "sympy.envelope":
                    call.result = run_sympy_envelope(ir.givens["family"], ir.givens["parameter"])
                elif call.name == "geometry.minkowski_sum":
                    call.result = run_minkowski_sum(ir.givens["polygon_a"], ir.givens["polygon_b"])
                elif call.name == "sympy.solve":
                    call.result = run_sympy_solve(ir.givens["equation"], ir.givens["variable"])
                elif call.name == "sympy.semantic_query":
                    call.result = execute_symbolic_query(ir.givens["symbolic_query"])
                elif call.name == "sympy.typed_analysis_query":
                    call.result = execute_typed_analysis_query(ir.givens["typed_analysis_query"])
                elif call.name == "sympy.progression_query":
                    call.result = execute_progression_query(ir.givens["progression_query"])
                elif call.name == "sympy.iteration_query":
                    call.result = execute_iteration_query(ir.givens["iteration_query"])
                elif call.name == "sympy.cubic_centroid_locus":
                    call.result = execute_cubic_centroid_locus_query(ir.givens["cubic_centroid_locus_query"])
                elif call.name == "sympy.hilbert_witness_query":
                    call.result = execute_hilbert_witness_query(ir.givens["hilbert_witness_query"])
                elif call.name == "sympy.prime_structure_query":
                    call.result = execute_prime_structure_query(ir.givens["prime_structure_query"])
                elif call.name == "sympy.vector_query":
                    call.result = execute_vector_query(ir.givens["vector_query"])
                elif call.name == "sympy.matrix_semantic_query":
                    call.result = execute_matrix_semantic_query(ir.givens["matrix_semantic_query"])
                elif call.name == "sympy.linear_constraint_query":
                    call.result = execute_linear_constraint_query(ir.givens["linear_constraint_query"])
                elif call.name == "sympy.finite_relation_query":
                    call.result = execute_finite_relation_query(ir.givens["finite_relation_query"])
                elif call.name == "sympy.discrete_constraint_query":
                    call.result = execute_discrete_constraint_query(ir.givens["discrete_constraint_query"])
                elif call.name == "sympy.diff":
                    call.result = run_sympy_diff(ir.givens["expression"], ir.givens["variable"])
                elif call.name == "sympy.polynomial_remainder":
                    call.result = run_sympy_polynomial_remainder(
                        ir.givens["dividend"],
                        ir.givens["divisor"],
                        ir.givens["variable"],
                    )
                elif call.name == "geometry.dsl":
                    call.result = run_geometry_dsl(
                        ir.givens["dsl_source"],
                        external_tools=self.external_tools,
                    )
                elif call.name == "container.square_in_equilateral_triangle":
                    call.result = solve_container_problem_from_ir(ir)
                elif call.name == "geometry.constraint_ir":
                    call.result = build_geometry_constraint_ir(ir.givens)
                elif call.name == "geometry.asymptote_exact":
                    call.result = solve_asymptote_geometry_problem(ir.givens["asymptote_geometry"])
                elif call.name == "arithmetic.nl":
                    payload = ir.givens["arithmetic_problem"]
                    call.result = solve_arithmetic_nl_problem_from_ir(payload)
                elif is_specialized_tool_name(call.name):
                    intent = ir.intent.removeprefix("latex_to_")
                    call.result = solve_specialized_problem(intent, ir.givens)
                else:
                    call.result = {"message": "No executor registered."}
                call.status = "executed"
            except Exception as exc:  # pragma: no cover - useful in CLI.
                call.status = "failed"
                call.error = str(exc)
        return ir


def is_specialized_tool_name(name: str) -> bool:
    return name.startswith(
        (
            "number_theory.",
            "inequality.",
            "probability.",
            "geometry.circle_overlap_limit",
        )
    )


def solve_arithmetic_nl_problem_from_ir(payload: dict[str, Any]) -> dict[str, Any]:
    from dataclasses import fields

    try:
        from math_os_prototype.arithmetic_nl import ArithmeticNLProblem
    except ImportError:
        from arithmetic_nl import ArithmeticNLProblem

    allowed = {field.name for field in fields(ArithmeticNLProblem)}
    problem = ArithmeticNLProblem(**{key: payload[key] for key in allowed if key in payload})
    return solve_arithmetic_nl_problem(problem)


def run_sympy_envelope(family: str, parameter: str) -> dict[str, str]:
    require_sympy()
    expr_text = family.split("=", 1)[1].strip()
    symbols = make_symbol_table(expr_text + parameter + "xy")
    x = symbols.setdefault("x", sp.symbols("x"))
    y = symbols.setdefault("y", sp.symbols("y"))
    param = symbols[parameter]
    expr = sp.sympify(normalize_math_text(expr_text), locals=make_sympy_locals(symbols))
    f_relation = y - expr
    stationary = sp.diff(f_relation, param)
    resultant = sp.resultant(f_relation, stationary, param)
    return {
        "F": str(f_relation),
        "stationary": str(stationary),
        "envelope_relation": str(sp.factor(resultant)),
        "readable": f"{sp.factor(resultant)} = 0",
    }


def solve_container_problem_from_ir(ir: MathIR) -> dict[str, Any]:
    payload = ir.givens["container_problem"]
    from_container = detect_container_problem(payload["source"])
    if from_container is None:
        raise ValueError("container problem payload could not be reconstructed")
    return solve_container_problem(from_container)


def build_geometry_constraint_ir(givens: dict[str, Any]) -> dict[str, Any]:
    curve_expr = givens.get("curve_expr", "")
    return {
        "status": "formalized",
        "kind": "GeometryConstraintIR",
        "objects": [
            {"id": "C", "type": "Curve", "equation": f"y = {curve_expr}"},
            {"id": "P1", "type": "Point", "coordinates": ["x1", "y1"]},
            {"id": "P2", "type": "Point", "coordinates": ["x2", "y2"]},
            {"id": "P3", "type": "Point", "coordinates": ["x3", "y3"]},
            {"id": "G", "type": "Point", "coordinates": ["X", "Y"]},
        ],
        "constraints": [
            {"type": "PointOnCurve", "point": "P1", "curve": "C", "equation": f"y1 = ({curve_expr}).subs(x, x1)"},
            {"type": "PointOnCurve", "point": "P2", "curve": "C", "equation": f"y2 = ({curve_expr}).subs(x, x2)"},
            {"type": "PointOnCurve", "point": "P3", "curve": "C", "equation": f"y3 = ({curve_expr}).subs(x, x3)"},
            {
                "type": "Equilateral",
                "points": ["P1", "P2", "P3"],
                "equations": [
                    "(x1-x2)^2+(y1-y2)^2 = (x2-x3)^2+(y2-y3)^2",
                    "(x2-x3)^2+(y2-y3)^2 = (x3-x1)^2+(y3-y1)^2",
                ],
            },
            {
                "type": "Centroid",
                "point": "G",
                "of": ["P1", "P2", "P3"],
                "equations": ["3*X = x1+x2+x3", "3*Y = y1+y2+y3"],
            },
        ],
        "query": {
            "type": "AreaOfBoundedLocus",
            "locus_point": "G",
            "under_constraints": ["PointOnCurve", "Equilateral", "Centroid"],
        },
        "next_tools": [
            {
                "name": "CAS elimination",
                "input": "exists x1 y1 x2 y2 x3 y3 satisfying constraints and G=(X,Y)",
                "purpose": "derive implicit or semialgebraic description of locus(G)",
            },
            {
                "name": "numeric continuation",
                "input": "same constraints plus sampling over free variables",
                "purpose": "discover connected components and bounded region candidates",
            },
            {
                "name": "proof verifier",
                "input": "candidate locus/area plus original constraints",
                "purpose": "verify no branch or component was lost",
            },
        ],
        "no_memorized_answer": True,
    }


def run_sympy_solve(equation: str, variable: str) -> dict[str, Any]:
    require_sympy()
    symbols = make_symbol_table(equation + variable)
    var = symbols[variable]
    lhs, rhs = split_equation(equation)
    locals_map = make_sympy_locals(symbols)
    expr = sp.sympify(normalize_math_text(lhs), locals=locals_map) - sp.sympify(normalize_math_text(rhs), locals=locals_map)
    result = sp.solve(expr, var)
    return {"solutions": [str(item) for item in result], "verified_equation": f"{sp.factor(expr)} = 0"}


def run_sympy_diff(expression: str, variable: str) -> dict[str, str]:
    require_sympy()
    symbols = make_symbol_table(expression + variable)
    var = symbols[variable]
    expr = sp.sympify(normalize_math_text(expression), locals=make_sympy_locals(symbols))
    result = sp.diff(expr, var)
    return {"derivative": str(sp.simplify(result))}


def run_sympy_polynomial_remainder(dividend: str, divisor: str, variable: str) -> dict[str, str]:
    require_sympy()
    symbols = make_symbol_table(dividend + divisor + variable)
    var = symbols[variable]
    locals_map = make_sympy_locals(symbols)
    dividend_expr = sp.sympify(normalize_math_text(dividend), locals=locals_map)
    divisor_expr = sp.sympify(normalize_math_text(divisor), locals=locals_map)
    if not dividend_expr.free_symbols and not divisor_expr.free_symbols:
        remainder = sp.Integer(dividend_expr) % sp.Integer(divisor_expr)
        return {
            "quotient": str(sp.Integer(dividend_expr) // sp.Integer(divisor_expr)),
            "remainder": str(remainder),
            "verification": str(sp.Integer(dividend_expr) - (sp.Integer(dividend_expr) // sp.Integer(divisor_expr)) * sp.Integer(divisor_expr) - remainder),
        }
    quotient, remainder = sp.div(dividend_expr, divisor_expr, domain="QQ")
    return {
        "quotient": str(sp.factor(quotient)),
        "remainder": str(sp.expand(remainder)),
        "verification": str(sp.simplify(dividend_expr - (quotient * divisor_expr + remainder))),
    }


def run_minkowski_sum(poly_a: list[list[float]], poly_b: list[list[float]]) -> dict[str, Any]:
    points = [[a[0] + b[0], a[1] + b[1]] for a in poly_a for b in poly_b]
    hull = convex_hull(points)
    return {"pairwise_sum_count": len(points), "vertices": hull}


def convex_hull(points: list[list[float]]) -> list[list[float]]:
    unique = sorted({(float(x), float(y)) for x, y in points})
    if len(unique) <= 1:
        return [[x, y] for x, y in unique]

    def cross(o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[tuple[float, float]] = []
    for point in unique:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)

    upper: list[tuple[float, float]] = []
    for point in reversed(unique):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    hull = lower[:-1] + upper[:-1]
    return [[clean_float(x), clean_float(y)] for x, y in hull]


def normalize_math_text(text: str) -> str:
    normalized = (
        text.replace("^", "**")
        .replace("＋", "+")
        .replace("－", "-")
        .replace("−", "-")
        .replace("×", "*")
        .replace("・", "*")
    )
    normalized = re.sub(r"(?<=\d)(?=[A-Za-z_(])", "*", normalized)
    normalized = re.sub(r"(?<=[A-Za-z])(?=\d)", "*", normalized)
    normalized = re.sub(r"(?<=\))(?=[A-Za-z_0-9(])", "*", normalized)
    for function_name in SYMPY_FUNCTIONS:
        normalized = re.sub(rf"\b{function_name}\s+([A-Za-z_]\w*)\b", rf"{function_name}(\1)", normalized)
        normalized = normalized.replace(f"{function_name}*(", f"{function_name}(")
    return normalized


def make_symbol_table(text: str) -> dict[str, Any]:
    return {
        name: sp.symbols(name)
        for name in sorted(set(re.findall(r"[a-zA-Z_]\w*", text)))
        if name not in SYMPY_FUNCTIONS
    }


def make_sympy_locals(symbols: dict[str, Any]) -> dict[str, Any]:
    functions = {
        "sin": sp.sin,
        "cos": sp.cos,
        "tan": sp.tan,
        "log": sp.log,
        "exp": sp.exp,
        "sqrt": sp.sqrt,
    }
    return {**functions, **symbols}


def contains_any(text: str, needles: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(needle.lower() in lower for needle in needles)


def detect_equilateral_centroid_locus_area_problem(text: str) -> dict[str, Any] | None:
    normalized = normalize_math_text(text)
    required_markers = ("正三角形", "重心", "軌跡", "面積")
    if not all(marker in normalized for marker in required_markers):
        return None
    curve_expr = extract_curve_expression(normalized)
    if curve_expr is None:
        return None
    return {
        "curve": f"y = {curve_expr}",
        "curve_expr": curve_expr,
        "vertices": ["(u, f(u))", "(v, f(v))", "(w, f(w))"],
        "centroid": {"X": "(u+v+w)/3", "Y": "(f(u)+f(v)+f(w))/3"},
        "constraints": [
            "|P_v-P_u|^2 = |P_w-P_u|^2",
            "(P_v-P_u) dot (P_w-P_u) = |P_v-P_u|^2/2",
        ],
        "target": "area of bounded region enclosed by centroid locus",
    }


def extract_curve_expression(text: str) -> str | None:
    normalized = normalize_math_text(text)
    match = re.search(r"\by\s*=\s*([A-Za-z0-9_+\-*/^().\s]+)", normalized)
    if not match:
        return None
    expr = match.group(1).strip()
    expr = re.split(r"\s+", expr, maxsplit=1)[0].strip()
    expr = expr.rstrip(". ")
    return expr or None


def extract_y_expression(text: str) -> str | None:
    normalized = normalize_math_text(text)
    match = re.search(r"\by\s*=\s*([^,，。;\n]+)", normalized)
    if not match:
        return None
    expr = match.group(1).strip()
    expr = re.split(
        r"\s*(?:を|の包絡線|包絡線|envelope|with\s+parameter|parameter|媒介変数|パラメータ)",
        expr,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip()
    expr = expr.rstrip(". ")
    return expr or None


def extract_parameter(text: str, expression: str) -> str:
    normalized = normalize_math_text(text)
    match = re.search(r"(?:parameter|媒介変数|パラメータ)\s*[:=]?\s*([a-zA-Z_]\w*)", normalized, re.IGNORECASE)
    if match:
        return match.group(1)
    names = re.findall(r"[a-zA-Z_]\w*", expression)
    for name in names:
        if name not in {"x", "y", "sin", "cos", "tan", "exp", "log", "sqrt"}:
            return name
    return "t"


def extract_polygons(text: str) -> list[list[list[float]]]:
    polygons = []
    for bracket in re.findall(r"\[([^\[\]]+)\]", text):
        points = []
        for x_text, y_text in re.findall(r"\((-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)\)", bracket):
            points.append([clean_float(float(x_text)), clean_float(float(y_text))])
        if points:
            polygons.append(points)
    return polygons


def detect_polynomial_remainder_problem(text: str) -> tuple[str, str, str] | None:
    normalized = normalize_math_text(text)
    compact = re.sub(r"\s+", "", normalized)
    if "余り" not in compact or "割" not in compact:
        return None
    match = re.search(r"(?P<dividend>[A-Za-z0-9_+\-*/().]+)を(?P<divisor>[A-Za-z0-9_+\-*/().]+)で割(?:った|る)?余り", compact)
    if not match:
        return None
    dividend = match.group("dividend")
    divisor = match.group("divisor")
    names = [name for name in re.findall(r"[a-zA-Z_]\w*", dividend + divisor) if name not in {"sqrt", "sin", "cos", "tan", "log", "exp"}]
    variable = names[0] if names else "x"
    return dividend, divisor, variable


def extract_expression_after_keyword(text: str, keywords: tuple[str, ...]) -> str | None:
    normalized = normalize_math_text(text)
    for keyword in keywords:
        pattern = rf"{re.escape(keyword)}(?:する|して|of)?\s*([^,，。;\n]+)"
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if match:
            expr = match.group(1).strip()
            expr = re.sub(r"\s*(を|with respect to|について).*$", "", expr, flags=re.IGNORECASE).strip()
            return expr or None
    match = re.search(r"\bdiff\s+([^,，。;\n]+)", normalized, flags=re.IGNORECASE)
    return match.group(1).strip() if match else None


def extract_variable(text: str) -> str | None:
    patterns = (
        r"(?:for|by|wrt|について|で)\s+([a-zA-Z_]\w*)",
        r"d/d([a-zA-Z_]\w*)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def detect_derivative_request(text: str) -> tuple[str, str] | None:
    normalized = normalize_math_text(text)
    match = re.search(r"(.+?)\s*を\s*([A-Za-z])\s*で微分", normalized)
    if match:
        expression = match.group(1).strip(" ,，。")
        variable = match.group(2)
        if expression:
            return expression, variable
    match = re.search(r"derivative\s+(.+?)\s+with respect to\s+([A-Za-z])", normalized, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip(), match.group(2)
    return None


def extract_equation(text: str) -> tuple[str | None, str | None]:
    normalized = normalize_math_text(text)
    variable = extract_variable(normalized) or "x"
    match = re.search(r"solve\s+(.+?)\s+for\s+([a-zA-Z_]\w*)", normalized, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip(), match.group(2)
    match = re.search(r"([a-zA-Z0-9_+\-*/().\s]+=[a-zA-Z0-9_+\-*/().\s]+)", normalized)
    if match:
        return match.group(1).strip(), variable
    return None, variable


def split_equation(equation: str) -> tuple[str, str]:
    if "=" not in equation:
        return equation, "0"
    lhs, rhs = equation.split("=", 1)
    return lhs.strip(), rhs.strip()


def clean_float(value: float) -> int | float:
    return int(value) if float(value).is_integer() else value


def require_sympy() -> None:
    if sp is None:
        raise RuntimeError("SymPy is not installed. Install sympy or use --json to inspect planned tool calls.")


def run_pipeline(
    text: str,
    router: TinyRouter | None = None,
    execute: bool = True,
    external_tools: bool = False,
    allow_specialized: bool = False,
) -> MathIR:
    compiler = ProblemCompiler(router, allow_specialized=allow_specialized)
    ir = compiler.compile(text)
    if execute:
        ToolExecutor(external_tools=external_tools).execute(ir)
    return ir


def looks_like_geometry_dsl(text: str) -> bool:
    statements = [part.strip().lower() for part in re.split(r"[;\n]+", text) if part.strip()]
    if not statements:
        return False
    has_task = any(
        statement in {"envelope", "region", "passing_region", "pass_region", "locus"}
        or statement.startswith("task ")
        for statement in statements
    )
    has_geometry_equation = any(
        statement.startswith("family ") or re.match(r"^[xy]\s*=", statement)
        for statement in statements
    )
    return has_task and has_geometry_equation


def demo_cases() -> list[str]:
    return [
        r"\begin{problem}$t\in\mathbb{R}$ とする。曲線 \( y = tx - t^2 \) の通過領域を求めよ。\end{problem}",
        "tを実数として、曲線 y = t*x - t^2 の通過領域を求めよ。",
        "曲線 y = t*x - t^2 の包絡線を求めよ。",
        "(x,y)=(t+1,2t) で表される点の軌跡を求めよ。",
        "task envelope; family y = t*x - t^2; param t",
        "task region; family y = t*x - t^2; param t in R",
        "包絡線 y = t*x - t^2 を求めて。parameter t",
        "Minkowski sum [(0,0),(1,0),(1,1),(0,1)] + [(0,0),(2,0),(0,1)]",
        "Leanで n + 0 = n を証明したい",
        "solve x^2 - 5*x + 6 = 0 for x",
        "微分 x^3 + 2*x^2 について x",
    ]


def print_human(ir: MathIR) -> None:
    print("Tiny Math Tool OS")
    print(f"route: {ir.route}")
    print(f"intent: {ir.intent}")
    print(f"router_nonzero_parameters: {ir.router_parameters}")
    print("top_routes:")
    for label, score in sorted(ir.route_scores.items(), key=lambda item: item[1], reverse=True)[:3]:
        print(f"  - {label}: {score:.2f}")
    print("plan:")
    for index, step in enumerate(ir.plan, start=1):
        print(f"  {index}. {step}")
    print("tool_calls:")
    for call in ir.tool_calls:
        print(f"  - {call.name}: {call.status}")
        print(f"    command: {call.command}")
        if call.result is not None:
            print(f"    result: {json.dumps(call.result, ensure_ascii=False)}")
        if call.error:
            print(f"    error: {call.error}")
    if ir.notes:
        print("notes:")
        for note in ir.notes:
            print(f"  - {note}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prototype for a tiny math tool router.")
    parser.add_argument("problem", nargs="*", help="Problem text. Omit with --demo.")
    parser.add_argument("--latex-file", type=Path, help="Read a LaTeX problem from a .tex file.")
    parser.add_argument("--json", action="store_true", help="Print the typed IR as JSON.")
    parser.add_argument("--no-execute", action="store_true", help="Only plan tool calls.")
    parser.add_argument("--demo", action="store_true", help="Run built-in examples.")
    parser.add_argument("--weights", type=Path, help="Load router weights from JSON.")
    parser.add_argument("--train-jsonl", type=Path, help="Train the tiny router from JSONL examples.")
    parser.add_argument("--save-weights", type=Path, help="Save router weights after optional training.")
    parser.add_argument("--epochs", type=int, default=8, help="Training epochs for --train-jsonl.")
    parser.add_argument("--external-tools", action="store_true", help="Run external tools such as Wolfram if available.")
    parser.add_argument(
        "--allow-specialized",
        action="store_true",
        help="Enable legacy benchmark-specific adapters. Keep this off for cold generalization benchmarks.",
    )
    parser.add_argument("--tool-status", action="store_true", help="Print detected local tool availability and exit.")
    parser.add_argument("--domain-benchmark", action="store_true", help="Run the bundled math domain classifier benchmark.")
    parser.add_argument(
        "--full-pipeline",
        action="store_true",
        help="Run Parser/Retrieval/Planner/Simulation/Tools/Verifier/Explanation.",
    )
    parser.add_argument(
        "--live-retrieval",
        action="store_true",
        help="Allow live Stack Exchange API retrieval in --full-pipeline.",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.tool_status:
        print(ToolRegistry().status_json())
        return 0

    if args.domain_benchmark:
        try:
            from math_os_prototype.domain_registry import run_domain_benchmark
        except ImportError:
            from domain_registry import run_domain_benchmark

        print(json.dumps(run_domain_benchmark(), ensure_ascii=False, indent=2))
        return 0

    router = TinyRouter.load(args.weights) if args.weights else TinyRouter()
    if args.train_jsonl:
        router.train_jsonl(args.train_jsonl, epochs=args.epochs)
    if args.save_weights:
        router.save(args.save_weights)

    if args.demo:
        problems = demo_cases()
    elif args.latex_file:
        problems = [args.latex_file.read_text(encoding="utf-8")]
    else:
        problems = [" ".join(args.problem).strip()]
    if not problems or not problems[0]:
        parser.error("provide a problem or use --demo")

    for index, problem in enumerate(problems):
        if index:
            print()
        if args.full_pipeline:
            try:
                from math_os_prototype.reasoning_pipeline import run_reasoning_pipeline
            except ImportError:
                from reasoning_pipeline import run_reasoning_pipeline

            result = run_reasoning_pipeline(
                problem,
                external_tools=args.external_tools,
                live_retrieval=args.live_retrieval,
                allow_specialized=args.allow_specialized,
            )
            if args.json:
                print(result.to_json())
            else:
                print(result.explanation)
            continue
        ir = run_pipeline(
            problem,
            router=router,
            execute=not args.no_execute,
            external_tools=args.external_tools,
            allow_specialized=args.allow_specialized,
        )
        if args.json:
            print(ir.to_json())
        else:
            print_human(ir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
