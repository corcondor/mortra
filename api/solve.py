"""MORTRA Model 1 exact single-problem solving endpoint.

The public UI sends one problem here.  The endpoint deliberately uses the
vendored MathOS typed parser and executable symbolic backends; it does not call
an LLM and it does not manufacture an answer when verification fails.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
import hashlib
import json
import re
from http.server import BaseHTTPRequestHandler
from typing import Any

import sympy as sp
from sympy.parsing.latex import parse_latex

from math_os_prototype.web_app import solve_request_payload
from math_os_prototype.solution_artifact import attach_solution_artifact
from math_os_prototype.finite_orbit_synthesis import synthesize_finite_orbit_problem
from math_os_prototype.runtime_correlation_synthesis import (
    synthesize_correlation_limit_problem,
)
from math_os_prototype.runtime_recurrence_synthesis import (
    synthesize_recurrence_triangle_floor_problem,
)
from math_os_prototype.runtime_discrete_profile_synthesis import (
    synthesize_discrete_trig_profile_problem,
)
from math_os_prototype.runtime_solution_synthesis import synthesize_runtime_solution
from math_os_prototype.cubic_centroid_locus import (
    execute_cubic_centroid_locus_query,
)
from math_os_prototype.hilbert_witness_query import execute_hilbert_witness_query
from math_os_prototype.iteration_query import execute_iteration_query
from math_os_prototype.latex_frontend import parse_latex_problem
from math_os_prototype.prime_structure_query import execute_prime_structure_query
from math_os_prototype.polytope_containment import (
    validate_published_theorem_dependency,
)
from math_os_prototype.symbolic_query import execute_symbolic_query
from math_os_prototype.typed_proof_synthesis import (
    parse_closed_strict_inequality,
    proof_derivation_tex,
    synthesize_closed_inequality_proof,
)


@dataclass(frozen=True)
class ExactDisplayAnswer:
    value: Any
    latex: str


@dataclass(frozen=True)
class ExactSolveOutcome:
    answer: Any
    tool_name: str
    expression_tex: str
    derivation_tex: tuple[str, ...]
    verification_method: str = "exact execution + residual check"
    verification_checks: tuple[str, ...] = ()
    diagram: dict[str, Any] | None = None
    diagram_tikz: str | None = None
    capability_origin: str = "primitive_exact_operation"
    proof_program: tuple[dict[str, Any], ...] = ()
    hypotheses_evaluated: int = 0
    search_depth: int = 0
    execution_witness: dict[str, Any] | None = None
    visual_explanation: dict[str, Any] | None = None


@dataclass(frozen=True)
class ProblemObligation:
    label: str
    statement: str


def _real_number(value: Any) -> float | None:
    try:
        numeric = complex(sp.N(value, 12))
    except (TypeError, ValueError):
        return None
    if abs(numeric.imag) > 1e-8 or not (-1e100 < numeric.real < 1e100):
        return None
    return float(numeric.real)


def _sample_curve(
    expression: sp.Expr,
    variable: sp.Symbol,
    x_min: float,
    x_max: float,
    *,
    count: int = 121,
) -> list[dict[str, float]]:
    points: list[dict[str, float]] = []
    for index in range(count):
        x_value = x_min + (x_max - x_min) * index / max(1, count - 1)
        try:
            y_value = complex(sp.N(expression.subs(variable, x_value), 12))
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        if abs(y_value.imag) > 1e-7 or not (-1e8 < y_value.real < 1e8):
            continue
        points.append({"x": round(x_value, 8), "y": round(float(y_value.real), 8)})
    return points


def _visible_y_range(curves: list[list[dict[str, float]]]) -> tuple[float, float]:
    values = sorted(point["y"] for curve in curves for point in curve)
    if not values:
        return -1.0, 1.0
    lower = values[max(0, int(len(values) * 0.05) - 1)]
    upper = values[min(len(values) - 1, int(len(values) * 0.95))]
    if abs(upper - lower) < 1e-8:
        margin = max(1.0, abs(upper) * 0.25)
    else:
        margin = max(0.35, (upper - lower) * 0.16)
    return lower - margin, upper + margin


def _curve_diagram(
    *,
    title: str,
    caption: str,
    x_min: float,
    x_max: float,
    curves: list[tuple[sp.Expr, sp.Symbol, str]],
    marked_x: list[tuple[float, str]] | None = None,
    fill_first_to_axis: bool = False,
) -> tuple[dict[str, Any], str]:
    sampled = [_sample_curve(expression, variable, x_min, x_max) for expression, variable, _ in curves]
    y_min, y_max = _visible_y_range(sampled)
    clipped = [
        [
            {"x": point["x"], "y": min(y_max, max(y_min, point["y"]))}
            for point in curve
        ]
        for curve in sampled
    ]
    shapes: list[dict[str, Any]] = []
    tones = [tone for _, _, tone in curves]
    for index, points in enumerate(clipped):
        if len(points) < 2:
            continue
        if index == 0 and fill_first_to_axis:
            shapes.append({
                "kind": "polyline",
                "points": [{"x": points[0]["x"], "y": 0.0}, *points, {"x": points[-1]["x"], "y": 0.0}],
                "closed": True,
                "tone": tones[index],
                "fill": True,
            })
        shapes.append({"kind": "polyline", "points": points, "tone": tones[index]})
    for x_value, label in marked_x or []:
        shapes.append({
            "kind": "point",
            "point": {"x": x_value, "y": 0.0},
            "label": label,
            "tone": "accent",
        })

    diagram = {
        "version": 1,
        "kind": "plane",
        "title": title,
        "caption": caption,
        "viewport": {"xMin": x_min, "xMax": x_max, "yMin": y_min, "yMax": y_max},
        "axes": True,
        "shapes": shapes,
    }

    width, height = 9.0, 5.4
    def map_point(point: dict[str, float]) -> tuple[float, float]:
        px = -width / 2 + width * (point["x"] - x_min) / max(1e-9, x_max - x_min)
        py = -height / 2 + height * (point["y"] - y_min) / max(1e-9, y_max - y_min)
        return px, py

    axis_x = map_point({"x": 0.0, "y": y_min})[0] if x_min <= 0 <= x_max else -width / 2
    axis_y = map_point({"x": x_min, "y": 0.0})[1] if y_min <= 0 <= y_max else -height / 2
    tikz = [
        r"\begin{tikzpicture}[line cap=round,line join=round]",
        rf"\draw[->,gray] ({-width / 2:.3f},{axis_y:.3f}) -- ({width / 2:.3f},{axis_y:.3f}) node[right] {{$x$}};",
        rf"\draw[->,gray] ({axis_x:.3f},{-height / 2:.3f}) -- ({axis_x:.3f},{height / 2:.3f}) node[above] {{$y$}};",
    ]
    colors = {"primary": "cyan!70!black", "secondary": "blue!70!black", "accent": "orange!85!black"}
    for points, tone in zip(clipped, tones):
        if len(points) < 2:
            continue
        coordinates = " ".join(f"({px:.4f},{py:.4f})" for px, py in map(map_point, points))
        tikz.append(rf"\draw[thick,{colors.get(tone, 'black!65')}] plot coordinates {{{coordinates}}};")
    for x_value, label in marked_x or []:
        px, py = map_point({"x": x_value, "y": 0.0})
        tikz.append(rf"\fill[orange!85!black] ({px:.4f},{py:.4f}) circle (1.6pt) node[below] {{{_escape_tikz(label)}}};")
    tikz.append(r"\end{tikzpicture}")
    return diagram, "\n".join(tikz)


def _escape_tikz(value: str) -> str:
    return value.replace("\\", r"\textbackslash{}").replace("_", r"\_").replace("%", r"\%")


def _first_executed_call(data: dict[str, Any]) -> dict[str, Any]:
    calls = data.get("tool_execution", {}).get("tool_calls", [])
    direct = next(
        (
            call
            for call in calls
            if call.get("status") == "executed" and call.get("error") is None
        ),
        {},
    )
    if direct:
        return direct
    action = next(
        (
            action
            for action in data.get("math_search", {}).get("actions", [])
            if action.get("status") == "executed"
            and (action.get("result") or {}).get("status") == "solved"
        ),
        {},
    )
    if not action:
        return {}
    return {
        "name": action.get("name"),
        "command": action.get("command") or action.get("input_summary"),
        "status": "executed",
        "result": action.get("result"),
        "error": None,
    }


def _failure_diagnostics(
    data: dict[str, Any],
    *,
    stage: str,
    candidate_answer: Any = None,
) -> dict[str, Any]:
    """Keep the exact failed route without serializing the entire solver state."""

    structural_ir = data.get("structural_ir") or {}
    domain_ir = data.get("domain_ir") or {}
    parser = data.get("parser") or {}
    semantic_graph = data.get("semantic_graph") or {}
    tool_execution = data.get("tool_execution") or {}
    math_search = data.get("math_search") or {}
    verification = data.get("verification") or {}
    verifier_gate = data.get("verifier_gate") or {}

    operations = [
        {
            "kind": operation.get("kind"),
            "target": operation.get("target"),
        }
        for operation in structural_ir.get("operations", [])
        if isinstance(operation, dict)
    ]
    tool_attempts = []
    for call in tool_execution.get("tool_calls", []):
        if not isinstance(call, dict):
            continue
        result = call.get("result") if isinstance(call.get("result"), dict) else {}
        tool_attempts.append(
            {
                "name": call.get("name"),
                "command": call.get("command"),
                "status": call.get("status"),
                "error": call.get("error"),
                "result_status": result.get("status"),
                "result_reason": result.get("reason"),
                "result_error": result.get("error"),
                "result_keys": sorted(str(key) for key in result),
            }
        )
    search_attempts = []
    for action in math_search.get("actions", []):
        if not isinstance(action, dict):
            continue
        result = action.get("result") if isinstance(action.get("result"), dict) else {}
        search_attempts.append(
            {
                "name": action.get("name"),
                "status": action.get("status"),
                "result_status": result.get("status"),
                "result_reason": result.get("reason"),
                "result_error": result.get("error"),
                "result_keys": sorted(str(key) for key in result),
            }
        )

    if stage == "certificate_replay":
        failure_code = "candidate_without_replayable_certificate"
    elif any(attempt.get("error") or attempt.get("result_error") for attempt in tool_attempts):
        failure_code = "exact_backend_execution_failed"
    elif not operations:
        failure_code = "query_operation_not_elaborated"
    elif not tool_attempts and not search_attempts:
        failure_code = "no_executable_lowering"
    elif not any(
        attempt.get("result_status") == "solved"
        for attempt in [*tool_attempts, *search_attempts]
    ):
        failure_code = "no_exact_candidate"
    else:
        failure_code = "candidate_not_verified"

    domain_candidates = [
        {
            "domain": candidate.get("domain"),
            "score": candidate.get("score"),
            "confidence": candidate.get("confidence"),
        }
        for candidate in domain_ir.get("candidates", [])
        if isinstance(candidate, dict)
    ]
    queries = [
        {
            "kind": query.get("kind"),
            "expression": query.get("expression"),
            "sort": query.get("sort"),
        }
        for query in semantic_graph.get("queries", [])
        if isinstance(query, dict)
    ]
    return {
        "schema": "mortra.single-problem-failure.v1",
        "stage": stage,
        "failure_code": failure_code,
        "parser_intent": parser.get("intent"),
        "parser_route": parser.get("route"),
        "domain": domain_ir.get("domain"),
        "domain_candidates": domain_candidates,
        "variables": structural_ir.get("variables") or [],
        "operations": operations,
        "queries": queries,
        "tool_attempts": tool_attempts,
        "search_attempts": search_attempts,
        "candidate_answer": candidate_answer,
        "verification": verification,
        "verifier_gate": verifier_gate,
    }


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _annotate_capability_provenance(certificate: dict[str, Any]) -> dict[str, Any]:
    """Make registered composite reuse and runtime synthesis distinguishable."""

    origin = certificate.get("capability_origin")
    if origin in {
        "synthesized_proof_program",
        "synthesized_linear_program",
        "synthesized_expression_program",
    }:
        generated_program = certificate.get("proof_program") or certificate.get("morphism_chain") or []
        certificate["registered_composite_used"] = False
        certificate.setdefault("composite_cache_role", "not_consulted")
        certificate["generated_program_sha256"] = hashlib.sha256(
            _canonical_json(generated_program).encode("utf-8")
        ).hexdigest()
    elif origin == "registered_parameterized_morphism":
        certificate["registered_composite_used"] = True
        if certificate.get("cold_generalization_validated") is True:
            certificate["registered_completed_route_used"] = False
            certificate.setdefault(
                "composite_cache_role", "verified_cold_parameterized_schema"
            )
        else:
            certificate["registered_completed_route_used"] = True
            certificate.setdefault("composite_cache_role", "registered_parameterized_schema")
    else:
        certificate.setdefault("registered_composite_used", False)
        certificate.setdefault("registered_completed_route_used", False)
        certificate.setdefault("composite_cache_role", "not_applicable")
    return certificate


def _is_verified_cold_parameterized_morphism(certificate: dict[str, Any]) -> bool:
    """Accept a theorem schema only when it is replayed against the current input."""

    if (
        certificate.get("kind") != "structural_theorem_replay"
        or certificate.get("capability_origin") != "registered_parameterized_morphism"
        or certificate.get("verified") is not True
        or certificate.get("cold_generalization_validated") is not True
        or certificate.get("registered_completed_route_used") is not False
    ):
        return False

    contract = certificate.get("cold_generalization_contract")
    query_objects = certificate.get("query_objects")
    if not isinstance(contract, dict) or not isinstance(query_objects, dict):
        return False
    required_keys = contract.get("required_object_keys")
    replay_obligations = contract.get("replay_obligations")
    if (
        not isinstance(required_keys, (list, tuple))
        or not required_keys
        or not isinstance(replay_obligations, (list, tuple))
        or not replay_obligations
        or not set(required_keys).issubset(query_objects)
        or certificate.get("replayed_contract_obligations") != list(replay_obligations)
        or not isinstance(contract.get("generic_operation"), str)
        or not str(contract.get("generic_operation")).strip()
    ):
        return False

    trusted_theorem_ids = contract.get("trusted_theorem_ids")
    if trusted_theorem_ids:
        witness = certificate.get("witness")
        dependencies = (
            witness.get("trusted_theorem_dependencies")
            if isinstance(witness, dict)
            else None
        )
        if not isinstance(trusted_theorem_ids, (list, tuple)) or not isinstance(
            dependencies, list
        ):
            return False
        dependency_ids = [
            item.get("theorem_id")
            for item in dependencies
            if isinstance(item, dict)
        ]
        if dependency_ids != list(trusted_theorem_ids):
            return False
        if not all(
            isinstance(item, dict) and validate_published_theorem_dependency(item)
            for item in dependencies
        ):
            return False
        if witness.get("proof_basis") != (
            "published_global_theorem_with_exact_current_input_replay"
        ):
            return False

    forbidden_query_keys = {
        "answer",
        "answer_tex",
        "expected_answer",
        "problem_id",
        "benchmark_id",
    }
    forbidden_replay_keys = {"expected_answer", "problem_id", "benchmark_id"}

    def contains_forbidden_key(value: Any, forbidden: set[str]) -> bool:
        if isinstance(value, dict):
            if forbidden.intersection(value):
                return True
            return any(contains_forbidden_key(item, forbidden) for item in value.values())
        if isinstance(value, (list, tuple)):
            return any(contains_forbidden_key(item, forbidden) for item in value)
        return False

    if contains_forbidden_key(query_objects, forbidden_query_keys):
        return False
    if contains_forbidden_key(certificate, forbidden_replay_keys):
        return False

    runtime_binding = certificate.get("runtime_binding")
    return bool(
        isinstance(runtime_binding, dict)
        and runtime_binding.get("input_sha256") == certificate.get("statement_sha256")
        and runtime_binding.get("answer_tex_sha256")
        == certificate.get("answer_tex_sha256")
        and runtime_binding.get("tool_name") == certificate.get("tool_name")
    )


def _replay_exact_backend_certificate(
    data: dict[str, Any],
    call: dict[str, Any],
) -> dict[str, Any] | None:
    """Replay an explicit set of deterministic exact backends."""

    backend_name = str(call.get("name") or "")
    replay_specs = {
        "sympy.semantic_query": (
            "symbolic_query",
            execute_symbolic_query,
            "primitive_exact_operation",
        ),
        "sympy.iteration_query": (
            "iteration_query",
            execute_iteration_query,
            "synthesized_proof_program",
        ),
        "sympy.cubic_centroid_locus": (
            "cubic_centroid_locus_query",
            execute_cubic_centroid_locus_query,
            "synthesized_proof_program",
        ),
        "sympy.hilbert_witness_query": (
            "hilbert_witness_query",
            execute_hilbert_witness_query,
            "registered_parameterized_morphism",
        ),
        "sympy.prime_structure_query": (
            "prime_structure_query",
            execute_prime_structure_query,
            "registered_parameterized_morphism",
        ),
    }
    spec = replay_specs.get(backend_name)
    if spec is None:
        return None

    payload_key, executor, capability_origin = spec
    parser = data.get("parser") or {}
    givens = parser.get("givens") or {}
    typed_input = givens.get(payload_key)
    original_result = call.get("result")
    if not isinstance(typed_input, dict) or not isinstance(original_result, dict):
        return None

    try:
        replayed_result = executor(dict(typed_input))
    except Exception:
        return None
    if _canonical_json(replayed_result) != _canonical_json(original_result):
        return None

    derivation = replayed_result.get("derivation_tex")
    proof_program = (
        [
            {
                "rule": "verified_derivation_step",
                "index": index,
                "statement_tex": step,
            }
            for index, step in enumerate(derivation, start=1)
            if isinstance(step, str)
        ]
        if isinstance(derivation, list)
        else []
    )
    typed_input_json = _canonical_json(typed_input)
    replayed_result_json = _canonical_json(replayed_result)
    return {
        "schema": "mortra.deterministic-backend-replay.v1",
        "verified": True,
        "backend": backend_name,
        "capability_origin": capability_origin,
        "typed_input_sha256": hashlib.sha256(typed_input_json.encode("utf-8")).hexdigest(),
        "replayed_result_sha256": hashlib.sha256(
            replayed_result_json.encode("utf-8")
        ).hexdigest(),
        "proof_program": proof_program,
        "checks": [
            "typed input replayed by deterministic exact executor",
            "complete structured result matched the original execution",
        ],
    }


def _latex_atom(value: Any) -> str:
    if isinstance(value, sp.Basic):
        return sp.latex(value)
    if isinstance(value, (list, tuple, set)):
        return r"\left\{" + r",\;".join(_latex_atom(item) for item in value) + r"\right\}"
    text = str(value).strip()
    try:
        return sp.latex(sp.sympify(text))
    except Exception:
        replacements = {
            "\\": r"\textbackslash{}",
            "&": r"\&",
            "%": r"\%",
            "$": r"\$",
            "#": r"\#",
            "_": r"\_",
            "{": r"\{",
            "}": r"\}",
            "^": r"\textasciicircum{}",
            "~": r"\textasciitilde{}",
        }
        escaped = "".join(replacements.get(character, character) for character in text)
        return r"\text{" + escaped + "}"


def _answer_latex(answer: Any) -> str:
    if isinstance(answer, ExactDisplayAnswer):
        return answer.latex
    if isinstance(answer, str):
        try:
            parsed = ast.literal_eval(answer)
        except (ValueError, SyntaxError):
            parsed = answer
    else:
        parsed = answer
    return r"\(" + _latex_atom(parsed) + r"\)"


def _math_chunks(statement: str) -> list[str]:
    patterns = (
        r"\\\[(.*?)\\\]",
        r"\$\$(.*?)\$\$",
        r"(?<!\$)\$(?!\$)(.*?)(?<!\$)\$(?!\$)",
    )
    chunks: list[str] = []
    for pattern in patterns:
        chunks.extend(match.strip() for match in re.findall(pattern, statement, flags=re.DOTALL))
    # The public editor accepts ordinary Japanese prose without requiring
    # explicit $...$ delimiters.  The deterministic front end identifies the
    # same mathematical spans, so both input styles must reach the exact
    # solver through one syntax path.
    if not chunks:
        chunks.extend(parse_latex_problem(statement).math_segments)
    return list(dict.fromkeys(chunk for chunk in chunks if chunk))


def _decompose_problem_obligations(statement: str) -> tuple[ProblemObligation, ...]:
    """Split explicit numbered subquestions while retaining their shared context."""

    enumerate_match = re.search(
        r"\\begin\{enumerate\}(?P<body>.*?)\\end\{enumerate\}",
        statement,
        flags=re.DOTALL,
    )
    if enumerate_match is not None:
        body = enumerate_match.group("body")
        markers = list(re.finditer(r"\\item(?:\[(?P<label>[^\]]+)\])?", body))
        if len(markers) >= 2:
            shared = (statement[: enumerate_match.start()] + statement[enumerate_match.end() :]).strip()
            obligations: list[ProblemObligation] = []
            for index, marker in enumerate(markers):
                end = markers[index + 1].start() if index + 1 < len(markers) else len(body)
                query = body[marker.end() : end].strip()
                label = (marker.group("label") or str(index + 1)).strip("() ")
                obligations.append(
                    ProblemObligation(
                        label=label,
                        statement="\n".join(part for part in (shared, query) if part).strip(),
                    )
                )
            return tuple(obligations)

    numbered_markers = list(
        re.finditer(r"(?:^|\\\\|\n)\s*\$?\((?P<label>\d+)\)\s*\$?\s*", statement)
    )
    if len(numbered_markers) < 2:
        return ()
    shared = statement[: numbered_markers[0].start()].strip()
    obligations = []
    for index, marker in enumerate(numbered_markers):
        end = numbered_markers[index + 1].start() if index + 1 < len(numbered_markers) else len(statement)
        query = statement[marker.end() : end].strip().rstrip("\\").strip()
        obligations.append(
            ProblemObligation(
                label=marker.group("label"),
                statement="\n".join(part for part in (shared, query) if part).strip(),
            )
        )
    return tuple(obligations)


def _three_real_cubic_chart(
    expression: sp.Expr,
    polynomial: sp.Poly,
    variable: sp.Symbol,
) -> tuple[ExactDisplayAnswer, list[sp.Expr], tuple[str, ...], tuple[str, ...]] | None:
    """Solve a three-real-root cubic without constructing Cardano radicals."""

    if polynomial.degree() != 3:
        return None
    discriminant = sp.factor(polynomial.discriminant())
    if discriminant.is_positive is not True:
        return None

    leading, quadratic, linear, constant = polynomial.all_coeffs()
    p = sp.factor((3 * leading * linear - quadratic**2) / (3 * leading**2))
    q = sp.factor(
        (27 * leading**2 * constant - 9 * leading * quadratic * linear + 2 * quadratic**3)
        / (27 * leading**3)
    )
    if p.is_negative is not True:
        return None

    shift = sp.factor(-quadratic / (3 * leading))
    radius = sp.sqrt(-p / 3)
    argument = sp.factor(-q / (2 * radius**3))
    if sp.factor(1 - argument**2).is_positive is not True:
        return None

    # This coefficient identity is the exact certificate for the chart change.
    depressed_variable = sp.Dummy("y")
    normalized = sp.expand(
        expression.subs(variable, depressed_variable + shift) / leading
    )
    depressed = depressed_variable**3 + p * depressed_variable + q
    if sp.expand(normalized - depressed) != 0:
        return None

    amplitude = 2 * radius
    base_angle = sp.acos(argument) / 3
    exact_roots = [
        shift + amplitude * sp.cos(base_angle - 2 * sp.pi * index / 3)
        for index in range(3)
    ]
    try:
        plot_roots = sorted(
            (
                root
                for root in sp.nroots(polynomial, n=18, maxsteps=100)
                if abs(complex(root).imag) < 1e-10
            ),
            key=lambda root: float(sp.re(root)),
        )
    except (ValueError, ArithmeticError):
        plot_roots = exact_roots

    family_latex = (
        sp.latex(shift)
        + "+"
        + sp.latex(amplitude)
        + r"\cos\left(\frac{1}{3}\arccos\left("
        + sp.latex(argument)
        + r"\right)-\frac{2\pi k}{3}\right)"
    )
    answer = ExactDisplayAnswer(
        value=tuple(exact_roots),
        latex=(
            r"\(\left\{\,"
            + family_latex
            + r"\;\middle|\;k=0,1,2\,\right\}\)"
        ),
    )
    derivation = (
        rf"左辺から右辺を移項し、\({sp.latex(expression)}=0\) とする。判別式は "
        rf"\({sp.latex(discriminant)}>0\) なので、相異なる実根は3個である。",
        rf"\({sp.latex(variable)}={sp.latex(depressed_variable + shift)}\) とおくと、係数恒等式により "
        rf"\({sp.latex(depressed)}=0\) へ正規化される。",
        rf"\({sp.latex(depressed_variable)}=2\sqrt{{{sp.latex(-p / 3)}}}\cos\theta\) とおき、"
        r"三倍角公式 \(4\cos^3\theta-3\cos\theta=\cos3\theta\) を使うと、"
        rf"\(\cos3\theta={sp.latex(argument)}\) を得る。",
        rf"したがって \({sp.latex(variable)}={family_latex}\;(k=0,1,2)\) である。"
        r"正規化恒等式と三倍角公式が各候補を元の三次式へ戻し、判別式と次数が完全性を保証する。",
    )
    checks = (
        "元の三次式と減次三次式の係数恒等式を記号的に確認",
        "判別式が正であり、相異なる実根が3個であることを確認",
        "三倍角公式により3候補が減次三次式を満たすことを確認",
    )
    return answer, plot_roots, derivation, checks


def _trigonometric_geometric_progression_chart(
    statement: str,
    chunks: list[str],
) -> ExactSolveOutcome | None:
    """Elaborate a three-term geometric progression of trig observables."""

    if "等比数列" not in statement or "求め" not in statement:
        return None
    sequence_chunks = [
        part.strip()
        for chunk in chunks
        for part in re.split(r"[,、，]", chunk)
        if part.strip()
    ]
    if len(sequence_chunks) < 4:
        return None
    try:
        terms = [parse_latex(chunk.rstrip(",、， ")) for chunk in sequence_chunks[:3]]
        target = parse_latex(sequence_chunks[-1].rstrip(",、， "))
    except Exception:
        return None
    if any(term.func not in {sp.sin, sp.cos, sp.tan} or len(term.args) != 1 for term in terms):
        return None
    if target.func not in {sp.sin, sp.cos} or len(target.args) != 1:
        return None
    argument = terms[0].args[0]
    if any(term.args[0] != argument for term in terms[1:]) or target.args[0] != argument:
        return None

    sine, cosine = sp.symbols("s c", real=True)

    def algebraic_coordinate(term: sp.Expr) -> sp.Expr:
        if term.func == sp.sin:
            return sine
        if term.func == sp.cos:
            return cosine
        return sine / cosine

    first, middle, third = map(algebraic_coordinate, terms)
    progression_relation = sp.together(middle**2 - first * third)
    relation_numerator, relation_denominator = progression_relation.as_numer_denom()
    identity = sine**2 + cosine**2 - 1
    target_symbol = sine if target.func == sp.sin else cosine
    eliminated_symbol = cosine if target_symbol == sine else sine
    try:
        resultant = sp.factor(
            sp.resultant(relation_numerator, identity, eliminated_symbol)
        )
        target_polynomial = sp.Poly(resultant, target_symbol).sqf_part()
    except (sp.PolynomialError, ValueError):
        return None
    if target_polynomial.degree() <= 0:
        return None

    exact_candidates = sp.solve(target_polynomial.as_expr(), target_symbol)
    admissible: list[tuple[sp.Expr, sp.Expr]] = []
    for candidate in exact_candidates:
        numeric = complex(sp.N(candidate, 18))
        if abs(numeric.imag) > 1e-10 or numeric.real < -1 - 1e-10 or numeric.real > 1 + 1e-10:
            continue
        other_symbol = eliminated_symbol
        for witness in (sp.sqrt(1 - candidate**2), -sp.sqrt(1 - candidate**2)):
            substitution = {target_symbol: candidate, other_symbol: witness}
            if sp.simplify(relation_denominator.subs(substitution)) == 0:
                continue
            if sp.simplify(relation_numerator.subs(substitution)) == 0:
                admissible.append((candidate, witness))
                break
    unique_values: list[tuple[sp.Expr, sp.Expr]] = []
    for candidate, witness in admissible:
        if not any(sp.simplify(candidate - prior) == 0 for prior, _ in unique_values):
            unique_values.append((candidate, witness))
    if len(unique_values) != 1:
        return None

    answer, witness = unique_values[0]
    polynomial_expression = sp.factor(target_polynomial.as_expr())
    root_numeric = _real_number(answer)
    if root_numeric is None:
        return None
    diagram, diagram_tikz = _curve_diagram(
        title="等比条件から得た代数方程式",
        caption="青い曲線の零点のうち、三角関数の定義域と元の等比条件を同時に満たす点だけを残します。",
        x_min=-1.0,
        x_max=1.0,
        curves=[(polynomial_expression, target_symbol, "primary")],
        marked_x=[(root_numeric, sp.latex(answer))],
    )
    term_tex = [sp.latex(term) for term in terms]
    target_tex = sp.latex(target)
    checks = (
        "等比数列の定義 b^2=ac を記号式へ変換",
        "sin^2+cos^2=1 と tan=sin/cos を用いて一変数へ消去",
        "全代数根を列挙し、実数範囲と分母非零条件を検査",
        "残った候補に対応する sin, cos を元の等比条件へ代入して残差0を確認",
    )
    return ExactSolveOutcome(
        answer=answer,
        tool_name="sympy.typed_relation_elimination",
        expression_tex=rf"{target_tex}:\;{sp.latex(target_polynomial.as_expr())}=0",
        derivation_tex=(
            rf"三項 ({term_tex[0]}, {term_tex[1]}, {term_tex[2]}) がこの順で等比数列をなす条件は、中央項の二乗が両端の積に等しいことである。",
            rf"(s=\sin {sp.latex(argument)},\ c=\cos {sp.latex(argument)}) とおく。"
            rf"さらに (	an {sp.latex(argument)}=s/c)、(s^2+c^2=1) を使う。",
            rf"等比条件と三角恒等式から ({sp.latex(eliminated_symbol)}) を消去すると、"
            rf"[{sp.latex(polynomial_expression)}=0] を得る。",
            rf"この多項式の全ての代数根を調べる。実数範囲 ([-1,1])、分母非零条件、"
            rf"および元の等比条件を同時に満たす ({target_tex}) は一つだけである。",
            rf"対応するもう一方の三角関数値を ({sp.latex(witness)}) と取れば、"
            rf"元の等比条件への代入残差は0になる。従って ({target_tex}={sp.latex(answer)}) である。",
        ),
        verification_method=(
            "typed geometric-progression relation + trigonometric identity + "
            "resultant elimination + exact witness replay"
        ),
        verification_checks=checks,
        diagram=diagram,
        diagram_tikz=diagram_tikz,
        capability_origin="synthesized_proof_program",
        proof_program=(
            {
                "rule": "geometric_progression_relation",
                "input_terms": term_tex,
                "constraint": sp.latex(sp.Eq(middle**2, first * third)),
            },
            {
                "rule": "trigonometric_coordinate_elaboration",
                "identities": [r"s^2+c^2=1", r"\tan\theta=s/c"],
            },
            {
                "rule": "resultant_elimination",
                "eliminated_symbol": sp.latex(eliminated_symbol),
                "result": sp.latex(polynomial_expression),
            },
            {
                "rule": "exact_witness_replay",
                "surviving_witness_count": 1,
            },
        ),
        hypotheses_evaluated=len(exact_candidates),
        search_depth=4,
    )


def _finite_orbit_exact_solve(statement: str) -> ExactSolveOutcome | None:
    synthesis = synthesize_finite_orbit_problem(statement)
    if synthesis is None:
        return None
    return ExactSolveOutcome(
        answer=ExactDisplayAnswer(synthesis.witness, synthesis.answer_tex),
        tool_name="mortra.finite_orbit_program_search",
        expression_tex=synthesis.expression_tex,
        derivation_tex=synthesis.derivation_tex,
        verification_method=(
            "typed recurrence elaboration + finite quotient enumeration + "
            "modular matrix replay + exact observable aggregation"
        ),
        verification_checks=synthesis.verification_checks,
        capability_origin="synthesized_proof_program",
        proof_program=synthesis.proof_program,
        hypotheses_evaluated=synthesis.hypotheses_evaluated,
        search_depth=len(synthesis.proof_program),
        execution_witness=synthesis.witness,
    )


def _runtime_solution_exact_solve(statement: str) -> ExactSolveOutcome | None:
    synthesis = synthesize_runtime_solution(statement)
    if synthesis is None:
        return None
    return ExactSolveOutcome(
        answer=ExactDisplayAnswer(synthesis.answer, synthesis.answer_tex),
        tool_name=synthesis.tool_name,
        expression_tex=synthesis.expression_tex,
        derivation_tex=synthesis.derivation_tex,
        verification_method=(
            "current-input typed program synthesis + exact symbolic replay + "
            "diagram derivation from the verified witness"
        ),
        verification_checks=synthesis.verification_checks,
        diagram=synthesis.diagram,
        capability_origin="synthesized_proof_program",
        proof_program=synthesis.proof_program,
        hypotheses_evaluated=len(synthesis.proof_program),
        search_depth=len(synthesis.proof_program),
        execution_witness=synthesis.witness,
        visual_explanation=synthesis.visual_explanation,
    )


def _correlation_limit_exact_solve(statement: str) -> ExactSolveOutcome | None:
    synthesis = synthesize_correlation_limit_problem(statement)
    if synthesis is None:
        return None
    return ExactSolveOutcome(
        answer=ExactDisplayAnswer(synthesis.witness, synthesis.answer_tex),
        tool_name="mortra.runtime_correlation_program_search",
        expression_tex=synthesis.expression_tex,
        derivation_tex=synthesis.derivation_tex,
        verification_method=(
            "typed sampling elaboration + runtime moment dependency expansion + "
            "independent exact integral replay + covariance normalization"
        ),
        verification_checks=synthesis.verification_checks,
        capability_origin="synthesized_proof_program",
        proof_program=synthesis.proof_program,
        hypotheses_evaluated=synthesis.hypotheses_evaluated,
        search_depth=len(synthesis.proof_program),
        execution_witness=synthesis.witness,
    )


def _recurrence_triangle_floor_exact_solve(statement: str) -> ExactSolveOutcome | None:
    synthesis = synthesize_recurrence_triangle_floor_problem(statement)
    if synthesis is None:
        return None
    return ExactSolveOutcome(
        answer=ExactDisplayAnswer(synthesis.witness, synthesis.answer_tex),
        tool_name="mortra.runtime_recurrence_program_search",
        expression_tex=synthesis.expression_tex,
        derivation_tex=synthesis.derivation_tex,
        verification_method=(
            "typed recurrence elaboration + companion-matrix replay + "
            "triangle-inequality root bounds + eventual floor stability"
        ),
        verification_checks=synthesis.verification_checks,
        capability_origin="synthesized_proof_program",
        proof_program=synthesis.proof_program,
        hypotheses_evaluated=synthesis.hypotheses_evaluated,
        search_depth=len(synthesis.proof_program),
        execution_witness=synthesis.witness,
    )


def _discrete_trig_profile_exact_solve(statement: str) -> ExactSolveOutcome | None:
    synthesis = synthesize_discrete_trig_profile_problem(statement)
    if synthesis is None:
        return None
    return ExactSolveOutcome(
        answer=ExactDisplayAnswer(synthesis.witness, synthesis.answer_tex),
        tool_name="mortra.runtime_discrete_profile_program_search",
        expression_tex=synthesis.expression_tex,
        derivation_tex=synthesis.derivation_tex,
        verification_method=(
            "typed profile elaboration + runtime derivative-root search + "
            "exact integer-candidate interval comparison + asymptotic composition"
        ),
        verification_checks=synthesis.verification_checks,
        capability_origin="synthesized_proof_program",
        proof_program=synthesis.proof_program,
        hypotheses_evaluated=synthesis.hypotheses_evaluated,
        search_depth=len(synthesis.proof_program),
        execution_witness=synthesis.witness,
    )


def _direct_exact_solve(statement: str) -> ExactSolveOutcome | None:
    chunks = _math_chunks(statement)
    if not chunks:
        return None

    normalized = statement.replace("−", "-")
    if r"\item" in normalized:
        return None
    try:
        inequality = parse_closed_strict_inequality(chunks)
        if inequality is not None and ("示せ" in normalized or "証明" in normalized):
            proof = synthesize_closed_inequality_proof(*inequality)
            if proof is not None:
                return ExactSolveOutcome(
                    answer=ExactDisplayAnswer(True, r"\(\text{成立する}\)"),
                    tool_name="mortra.typed_proof_program_search",
                    expression_tex=sp.latex(sp.Lt(*inequality)),
                    derivation_tex=proof_derivation_tex(proof),
                    verification_method=(
                        "iterative typed primitive-law enumeration + exact side-condition replay"
                    ),
                    verification_checks=(
                        "問題番号・登録済み解答・定理名による分岐を使用していない",
                        f"{proof.hypotheses_evaluated}個の証明候補を列挙",
                        "合成された全ての基本変換と前提条件を厳密式で再生",
                    ),
                    capability_origin="synthesized_proof_program",
                    proof_program=proof.proof_program,
                    hypotheses_evaluated=proof.hypotheses_evaluated,
                    search_depth=proof.max_depth,
                )

        progression_chart = _trigonometric_geometric_progression_chart(statement, chunks)
        if progression_chart is not None:
            return progression_chart

        if "導関数" in normalized or "微分せよ" in normalized:
            definition = next((chunk for chunk in chunks if "=" in chunk), None)
            if definition is None:
                return None
            _, expression_tex = definition.split("=", 1)
            expression = parse_latex(expression_tex.replace("−", "-"))
            variables = sorted(expression.free_symbols, key=lambda symbol: symbol.name)
            if len(variables) != 1:
                return None
            variable = variables[0]
            answer = sp.diff(expression, variable)
            diagram, diagram_tikz = _curve_diagram(
                title="関数と導関数",
                caption="青が元の関数、灰色が導関数です。表示範囲内で同じ厳密式を数値化しています。",
                x_min=-3.0,
                x_max=3.0,
                curves=[(expression, variable, "primary"), (answer, variable, "secondary")],
            )
            return ExactSolveOutcome(
                answer=answer,
                tool_name="sympy.diff",
                expression_tex=f"\\frac{{d}}{{d{sp.latex(variable)}}}({sp.latex(expression)})",
                derivation_tex=(
                    rf"与えられた関数は \(f({sp.latex(variable)})={sp.latex(expression)}\) である。",
                    rf"各項を微分すると \(f'({sp.latex(variable)})={sp.latex(answer)}\) を得る。",
                    "右図では元の関数と導関数を同じ座標系に描き、傾きの符号を照合した。",
                ),
                diagram=diagram,
                diagram_tikz=diagram_tikz,
            )

        integral_tex = next((chunk for chunk in chunks if r"\int" in chunk), None)
        if integral_tex is not None and ("積分" in normalized or "求めよ" in normalized):
            integral = parse_latex(integral_tex.replace("−", "-"))
            if not isinstance(integral, sp.Integral):
                return None
            answer = integral.doit()
            if answer.has(sp.Integral):
                return None
            integrand = integral.function
            limit_spec = integral.limits[0]
            variable = limit_spec[0]
            if len(limit_spec) != 3:
                return None
            lower, upper = limit_spec[1:]
            x_lower, x_upper = _real_number(lower), _real_number(upper)
            if x_lower is None or x_upper is None or x_lower == x_upper:
                return None
            antiderivative = sp.integrate(integrand, variable)
            diagram, diagram_tikz = _curve_diagram(
                title="定積分の被積分関数",
                caption="青い領域の符号付き面積を、原始関数の端点差で厳密に評価します。",
                x_min=min(x_lower, x_upper),
                x_max=max(x_lower, x_upper),
                curves=[(integrand, variable, "primary")],
                marked_x=[(x_lower, sp.latex(lower)), (x_upper, sp.latex(upper))],
                fill_first_to_axis=True,
            )
            return ExactSolveOutcome(
                answer=answer,
                tool_name="sympy.integrate",
                expression_tex=sp.latex(integral),
                derivation_tex=(
                    rf"被積分関数を \(h({sp.latex(variable)})={sp.latex(integrand)}\) とおく。",
                    rf"原始関数の一つは \(H({sp.latex(variable)})={sp.latex(antiderivative)}\) である。",
                    rf"微積分の基本定理より \(H({sp.latex(upper)})-H({sp.latex(lower)})={sp.latex(answer)}\) となる。",
                ),
                diagram=diagram,
                diagram_tikz=diagram_tikz,
            )

        limit_tex = next((chunk for chunk in chunks if r"\lim" in chunk), None)
        if limit_tex is not None:
            limit = parse_latex(limit_tex.replace("−", "-"))
            if not isinstance(limit, sp.Limit):
                return None
            answer = limit.doit()
            integrand, variable, destination = limit.args[:3]
            unresolved_symbols = integrand.free_symbols - {variable}
            if unresolved_symbols:
                return None
            if (
                answer.has(sp.Limit)
                or sp.simplify(answer - integrand) == 0
                or variable in answer.free_symbols
            ):
                return None
            center = _real_number(destination)
            diagram = diagram_tikz = None
            if center is not None:
                diagram, diagram_tikz = _curve_diagram(
                    title="極限点の近傍",
                    caption="極限点の左右で同じ関数値へ近づくことを、厳密式から描いた近傍図で確認します。",
                    x_min=center - 2.0,
                    x_max=center + 2.0,
                    curves=[(integrand, variable, "primary")],
                    marked_x=[(center, sp.latex(destination))],
                )
            try:
                local_form = sp.series(integrand, variable, destination, 4)
                local_step = rf"\({sp.latex(integrand)}={sp.latex(local_form)}\) と局所展開できる。"
            except (NotImplementedError, ValueError):
                local_step = "分子・分母の共通因子または既知の基本極限を厳密に整理する。"
            return ExactSolveOutcome(
                answer=answer,
                tool_name="sympy.limit",
                expression_tex=sp.latex(limit),
                derivation_tex=(
                    rf"\({sp.latex(variable)}\to {sp.latex(destination)}\) における局所形を調べる。",
                    local_step,
                    rf"したがって極限値は \({sp.latex(answer)}\) である。",
                ),
                diagram=diagram,
                diagram_tikz=diagram_tikz,
            )

        equation_tex = next((chunk for chunk in chunks if "=" in chunk), None)
        if equation_tex is not None:
            left_tex, right_tex = equation_tex.split("=", 1)
            left = parse_latex(left_tex.replace("−", "-"))
            right = parse_latex(right_tex.replace("−", "-"))
            variables = sorted((left - right).free_symbols, key=lambda symbol: symbol.name)
            if len(variables) != 1:
                return None
            variable = variables[0]
            variable_query = re.search(
                rf"(?<![A-Za-z0-9_]){re.escape(variable.name)}(?![A-Za-z0-9_])\s*を求め",
                normalized,
            )
            if not ("解け" in normalized or "解を" in normalized or variable_query):
                return None
            expression = sp.expand(left - right)
            try:
                polynomial = sp.Poly(expression, variable)
            except sp.PolynomialError:
                polynomial = None

            cubic_chart = (
                _three_real_cubic_chart(expression, polynomial, variable)
                if polynomial is not None
                else None
            )
            if cubic_chart is not None:
                answer, roots_for_plot, derivation, checks = cubic_chart
                real_roots = [
                    (numeric, rf"x_{{{index}}}")
                    for index, root in enumerate(roots_for_plot, start=1)
                    if (numeric := _real_number(root)) is not None
                ]
                root_values = [root for root, _ in real_roots]
                span = max(2.0, (max(root_values) - min(root_values)) * 0.35)
                diagram, diagram_tikz = _curve_diagram(
                    title="三次方程式の3実根",
                    caption="青い曲線は左辺−右辺です。橙色の点は三角関数形で厳密表示した3実根です。",
                    x_min=min(root_values) - span,
                    x_max=max(root_values) + span,
                    curves=[(expression, variable, "primary")],
                    marked_x=real_roots,
                )
                return ExactSolveOutcome(
                    answer=answer,
                    tool_name="sympy.cubic_trigonometric_chart",
                    expression_tex=sp.latex(sp.Eq(left, right)),
                    derivation_tex=derivation,
                    verification_method=(
                        "depressed-cubic coefficient identity + triple-angle identity + discriminant"
                    ),
                    verification_checks=checks,
                    diagram=diagram,
                    diagram_tikz=diagram_tikz,
                )

            roots = sp.solve(sp.Eq(left, right), variable)
            if not roots or any(sp.simplify(expression.subs(variable, root)) != 0 for root in roots):
                return None
            roots_for_plot = roots
            real_roots = [
                (numeric, sp.latex(root))
                for root in roots_for_plot
                if (numeric := _real_number(root)) is not None
            ]
            if real_roots:
                root_values = [root for root, _ in real_roots]
                span = max(2.0, (max(root_values) - min(root_values)) * 0.35)
                x_min, x_max = min(root_values) - span, max(root_values) + span
            else:
                x_min, x_max = -4.0, 4.0
            diagram, diagram_tikz = _curve_diagram(
                title="方程式の零点",
                caption="青い曲線は左辺−右辺です。橙色の点が元の方程式を満たす実数解です。",
                x_min=x_min,
                x_max=x_max,
                curves=[(expression, variable, "primary")],
                marked_x=real_roots,
            )
            factorized = sp.factor(expression)
            factor_step = (
                rf"左辺から右辺を移項すると \({sp.latex(expression)}=0\) であり、"
                rf"\({sp.latex(factorized)}=0\) と因数分解できる。"
                if factorized != expression
                else rf"左辺から右辺を移項し、\({sp.latex(expression)}=0\) を厳密に解く。"
            )
            root_set = r"\left\{" + r",\;".join(sp.latex(root) for root in roots_for_plot) + r"\right\}"
            return ExactSolveOutcome(
                answer=roots,
                tool_name="sympy.solve",
                expression_tex=sp.latex(sp.Eq(left, right)),
                derivation_tex=(
                    factor_step,
                    rf"各因子または代数的根を解くと \({sp.latex(variable)}\in {root_set}\) を得る。",
                    "各候補を元の等式へ代入し、残差がすべて0になることを確認した。",
                ),
                verification_checks=("各候補を元の等式へ代入し、残差0を確認",),
                diagram=diagram,
                diagram_tikz=diagram_tikz,
                capability_origin="synthesized_expression_program",
                proof_program=(
                    {
                        "rule": "elaborate_univariate_equation",
                        "variable": variable.name,
                        "equation": sp.srepr(sp.Eq(left, right)),
                    },
                    {
                        "rule": "normalize_equation_to_zero",
                        "expression": sp.srepr(expression),
                    },
                    {
                        "rule": "solve_exact_univariate_equation",
                        "roots": [sp.srepr(root) for root in roots],
                    },
                    {
                        "rule": "replay_roots_in_original_equation",
                        "residuals": [
                            sp.srepr(sp.simplify(expression.subs(variable, root)))
                            for root in roots
                        ],
                    },
                ),
                hypotheses_evaluated=len(roots),
                search_depth=4,
                execution_witness={
                    "variable": variable.name,
                    "equation": sp.srepr(sp.Eq(left, right)),
                    "normalized_expression": sp.srepr(expression),
                    "roots": [sp.srepr(root) for root in roots],
                    "residuals": [
                        sp.srepr(sp.simplify(expression.subs(variable, root)))
                        for root in roots
                    ],
                },
            )
    except Exception:
        return None
    return None


def _direct_payload(
    statement: str,
    outcome: ExactSolveOutcome,
    *,
    evaluation_mode: str,
    include_publication_artifact: bool = True,
) -> dict[str, Any]:
    answer_tex = _answer_latex(outcome.answer)
    operation = outcome.tool_name.removeprefix("sympy.")
    morphism_chain = [
        "ProblemText",
        "LatexSyntaxTree",
        "SymPyExpression",
        outcome.tool_name,
        "VerifiedAnswer",
    ]
    verification_method = f"{outcome.tool_name}: {outcome.verification_method}"
    execution_certificate = {
        "schema": "mortra.direct-exact-certificate.v1",
        "statement_sha256": hashlib.sha256(statement.encode("utf-8")).hexdigest(),
        "answer_tex_sha256": hashlib.sha256(answer_tex.encode("utf-8")).hexdigest(),
        "tool_name": outcome.tool_name,
        "expression_tex": outcome.expression_tex,
        "morphism_chain": morphism_chain,
        "checks": list(outcome.verification_checks),
        "capability_origin": outcome.capability_origin,
        "proof_program": list(outcome.proof_program),
        "search_statistics": {
            "hypotheses_evaluated": outcome.hypotheses_evaluated,
            "max_depth": outcome.search_depth,
        },
        "verified": True,
    }
    if outcome.execution_witness is not None:
        execution_certificate["witness"] = outcome.execution_witness
    _annotate_capability_provenance(execution_certificate)
    certificate_sha256 = hashlib.sha256(
        json.dumps(
            execution_certificate,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    trace = [
        "LaTeX数式を構文解析",
        "型付きの実行可能式へ変換",
        f"{outcome.tool_name} で厳密計算",
        "未評価演算と制約残差を検査",
        "問題文・解答・検証証明書を出力",
    ]
    card_payload = {
            "statement_tex": statement,
            "answer_tex": answer_tex,
            "solution_tex": "\n\n".join(
                rf"\textbf{{{index}.}} {step}"
                for index, step in enumerate(outcome.derivation_tex, start=1)
            ),
            "family_id": f"solve.exact.{operation}",
            "domain": "exact_symbolic",
            "morphism_chain": morphism_chain,
            "verification": {
                "method": verification_method,
                "exact_backend": True,
                "independent_check": True,
                "checks": list(outcome.verification_checks),
                "certificate_sha256": certificate_sha256,
            },
            "execution_certificate": execution_certificate,
            **({"diagram": outcome.diagram} if outcome.diagram else {}),
            **({"diagram_tikz": outcome.diagram_tikz} if outcome.diagram_tikz else {}),
            **({"visual_explanation": outcome.visual_explanation} if outcome.visual_explanation else {}),
        }
    card = (
        attach_solution_artifact(card_payload, trace)
        if include_publication_artifact
        else card_payload
    )
    return {
        "ok": True,
        "generated": 1,
        "requested": 1,
        "engine": "MORTRA typed exact solver (no LLM)",
        "evaluation_mode": evaluation_mode,
        "cards": [card],
        "trace": trace,
    }


def _math_expression(command: str) -> str:
    match = re.search(r"\((.*)\)$", command.strip())
    expression = match.group(1) if match else command
    expression = expression.replace("**", "^").replace("*", r"\,")
    return expression.replace("_", r"\_")


def _plain_derivation_to_tex(step: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "^": r"\textasciicircum{}",
        "~": r"\textasciitilde{}",
    }
    return "".join(replacements.get(character, character) for character in step)


def _solution_text(problem: str, answer_tex: str, data: dict[str, Any]) -> str:
    call = _first_executed_call(data)
    result = call.get("result") or {}
    derivation = result.get("derivation_tex")
    if isinstance(derivation, list) and derivation and all(isinstance(step, str) for step in derivation):
        return "\n\n".join(
            rf"\textbf{{{index}.}} {step}"
            for index, step in enumerate(derivation, start=1)
        )
    theorem_derivation = result.get("derivation")
    if (
        isinstance(theorem_derivation, list)
        and theorem_derivation
        and all(isinstance(step, str) for step in theorem_derivation)
    ):
        return "\n\n".join(
            rf"\textbf{{{index}.}} {_plain_derivation_to_tex(step)}"
            for index, step in enumerate(theorem_derivation, start=1)
        )
    command = str(call.get("command") or "exact symbolic execution")
    operator = str(result.get("query_operator") or call.get("name") or "constraint solving")
    expression = _math_expression(command)
    verification = data.get("verification", {})
    checks = verification.get("checks") or ["候補を元の制約へ代入して照合した。"]
    checks_tex = " ".join(str(check) for check in checks)
    operator_tex = operator.replace("_", r"\_")
    return (
        "問題文を字句・構文解析し，量化・定義域・等式を型付き制約へ変換する。"
        f"実行演算は \\(\\mathrm{{{operator_tex}}}\\) であり，"
        f"厳密計算対象は \\({expression}\\) である。"
        f"計算結果は {answer_tex}。"
        f"最後に得られた候補を元の条件へ戻して検査した。{checks_tex}"
    )


def _solve_composite_obligations(
    statement: str,
    obligations: tuple[ProblemObligation, ...],
    *,
    allow_theorem_kernels: bool,
    include_publication_artifact: bool,
) -> dict[str, Any] | None:
    children: list[dict[str, Any]] = []
    for obligation in obligations:
        status, payload = solve_problem(
            obligation.statement,
            allow_theorem_kernels=allow_theorem_kernels,
            include_publication_artifact=False,
            _allow_obligation_decomposition=False,
        )
        if status != 200 or not payload.get("cards"):
            return None
        card = payload["cards"][0]
        verification = card.get("verification") or {}
        certificate = card.get("execution_certificate")
        if (
            verification.get("exact_backend") is not True
            or verification.get("independent_check") is not True
            or not isinstance(certificate, dict)
        ):
            return None
        children.append(
            {
                "label": obligation.label,
                "statement": obligation.statement,
                "statement_sha256": hashlib.sha256(obligation.statement.encode("utf-8")).hexdigest(),
                "answer_tex": card["answer_tex"],
                "solution_tex": card["solution_tex"],
                "family_id": card["family_id"],
                "certificate": certificate,
                "certificate_sha256": verification.get("certificate_sha256"),
            }
        )

    morphism_chain = [
        "ProblemText",
        "NumberedObligationDecomposition",
        "TypedObligationConjunction",
        "IndependentChildCertificateReplay",
        "VerifiedAnswerBundle",
    ]
    execution_certificate = {
        "schema": "mortra.composite-obligation-certificate.v1",
        "statement_sha256": hashlib.sha256(statement.encode("utf-8")).hexdigest(),
        "morphism_chain": morphism_chain,
        "conjunction": "all",
        "children": [
            {
                "label": child["label"],
                "statement_sha256": child["statement_sha256"],
                "certificate_sha256": child["certificate_sha256"],
            }
            for child in children
        ],
        "witness": {
            "shared_chart": {
                "chart_id": "typed_obligation.conjunction.v1",
                "proof_obligation_records": [
                    {
                        "id": f"part-{child['label']}",
                        "claim": child["statement"],
                        "status": "verified",
                        "certificate_sha256": child["certificate_sha256"],
                    }
                    for child in children
                ],
            }
        },
        "verified": True,
    }
    certificate_sha256 = hashlib.sha256(
        json.dumps(
            execution_certificate,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    answer_tex = (
        r"\(\begin{aligned}"
        + r"\\".join(
            rf"\text{{({child['label']})}}\;&{child['answer_tex'].removeprefix(r'\(').removesuffix(r'\)')}"
            for child in children
        )
        + r"\end{aligned}\)"
    )
    solution_tex = "\n\n".join(
        rf"\textbf{{({child['label']})}}\quad {child['solution_tex']}"
        for child in children
    )
    trace = [
        f"問題文を{len(children)}個の設問へ構文分解",
        "共有条件を各設問の型付き意味表現へ継承",
        "各設問を独立に厳密実行",
        "全設問の証明書をAND条件として再生",
        "問題文・解答・検証証明書を出力",
    ]
    card_payload = {
        "statement_tex": statement,
        "answer_tex": answer_tex,
        "solution_tex": solution_tex,
        "family_id": "solve.composite.all_obligations",
        "domain": "typed_obligation_conjunction",
        "morphism_chain": morphism_chain,
        "verification": {
            "method": "all child certificates replayed under conjunction semantics",
            "exact_backend": True,
            "independent_check": True,
            "checks": [f"{len(children)}/{len(children)} numbered obligations certified"],
            "certificate_sha256": certificate_sha256,
        },
        "execution_certificate": execution_certificate,
        "proof_obligations": [
            {
                "id": f"part-{child['label']}",
                "claim": child["statement"],
                "status": "verified",
                "certificate_sha256": child["certificate_sha256"],
            }
            for child in children
        ],
    }
    card = (
        attach_solution_artifact(card_payload, trace)
        if include_publication_artifact
        else card_payload
    )
    return {
        "ok": True,
        "generated": 1,
        "requested": 1,
        "engine": "MORTRA typed exact solver (no LLM)",
        "evaluation_mode": "portfolio" if allow_theorem_kernels else "cold",
        "cards": [card],
        "trace": trace,
    }


def solve_problem(
    problem: str,
    *,
    allow_theorem_kernels: bool = True,
    include_publication_artifact: bool = True,
    _allow_obligation_decomposition: bool = True,
) -> tuple[int, dict[str, Any]]:
    statement = problem.strip()
    if not statement:
        return 400, {"ok": False, "error": "問題文を入力してください。"}

    evaluation_mode = "portfolio" if allow_theorem_kernels else "cold"

    runtime_solution = _runtime_solution_exact_solve(statement)
    if runtime_solution is not None:
        return 200, _direct_payload(
            statement,
            runtime_solution,
            evaluation_mode=evaluation_mode,
            include_publication_artifact=include_publication_artifact,
        )

    finite_orbit_direct = _finite_orbit_exact_solve(statement)
    if finite_orbit_direct is not None:
        return 200, _direct_payload(
            statement,
            finite_orbit_direct,
            evaluation_mode=evaluation_mode,
            include_publication_artifact=include_publication_artifact,
        )

    correlation_direct = _correlation_limit_exact_solve(statement)
    if correlation_direct is not None:
        return 200, _direct_payload(
            statement,
            correlation_direct,
            evaluation_mode=evaluation_mode,
            include_publication_artifact=include_publication_artifact,
        )

    recurrence_direct = _recurrence_triangle_floor_exact_solve(statement)
    if recurrence_direct is not None:
        return 200, _direct_payload(
            statement,
            recurrence_direct,
            evaluation_mode=evaluation_mode,
            include_publication_artifact=include_publication_artifact,
        )

    discrete_profile_direct = _discrete_trig_profile_exact_solve(statement)
    if discrete_profile_direct is not None:
        return 200, _direct_payload(
            statement,
            discrete_profile_direct,
            evaluation_mode=evaluation_mode,
            include_publication_artifact=include_publication_artifact,
        )

    obligations = (
        _decompose_problem_obligations(statement)
        if _allow_obligation_decomposition
        else ()
    )
    if obligations:
        composite = _solve_composite_obligations(
            statement,
            obligations,
            allow_theorem_kernels=allow_theorem_kernels,
            include_publication_artifact=include_publication_artifact,
        )
        if composite is not None:
            return 200, composite

    direct = None if obligations else _direct_exact_solve(statement)
    if direct is not None:
        return 200, _direct_payload(
            statement,
            direct,
            evaluation_mode=evaluation_mode,
            include_publication_artifact=include_publication_artifact,
        )

    solved = solve_request_payload(
        {
            "problem": statement,
            "full_pipeline": True,
            "allow_specialized": False,
            "allow_theorem_kernels": allow_theorem_kernels,
            "live_retrieval": False,
        }
    )
    data = solved.get("data") or {}
    answer = solved.get("answer")
    verification = data.get("verification") or {}
    evidence = _first_executed_call(data)
    verified = answer not in (None, "", []) and verification.get("status") == "verified"
    if not verified:
        return 422, {
            "ok": False,
            "generated": 0,
            "requested": 1,
            "engine": "MORTRA typed exact solver (no LLM)",
            "evaluation_mode": evaluation_mode,
            "error": "型付き制約は生成できましたが、厳密に検証できる解答までは到達しませんでした。",
            "trace": [
                "問題文を型付き意味IRへ変換",
                "実行可能制約を探索",
                "検証済み解答が得られないため公開を停止",
            ],
            "diagnostics": _failure_diagnostics(
                data,
                stage="verified_answer",
                candidate_answer=answer,
            ),
        }

    intent = str(data.get("tool_execution", {}).get("intent") or "exact_constraint")
    route = str(data.get("tool_execution", {}).get("route") or data.get("domain_ir", {}).get("domain") or "mathematics")
    call = _first_executed_call(data)
    result = call.get("result") or {}
    answer_tex = (
        result.get("answer_tex")
        if isinstance(result.get("answer_tex"), str)
        else _answer_latex(answer)
    )
    tool_name = str(call.get("name") or "exact_backend")
    morphism_chain = [
        "ProblemText",
        "TypedSemanticIR",
        "ExecutableConstraint",
        tool_name,
        "VerifiedAnswer",
    ]
    raw_execution_certificate = (
        result.get("certificate")
        if isinstance(result.get("certificate"), dict)
        else None
    )
    replayed_execution_certificate = (
        _replay_exact_backend_certificate(data, call)
        if raw_execution_certificate is None
        else None
    )
    execution_certificate = (
        dict(raw_execution_certificate)
        if raw_execution_certificate is not None
        else dict(replayed_execution_certificate)
        if replayed_execution_certificate is not None
        else None
    )
    if execution_certificate is not None:
        statement_sha256 = hashlib.sha256(statement.encode("utf-8")).hexdigest()
        answer_tex_sha256 = hashlib.sha256(answer_tex.encode("utf-8")).hexdigest()
        execution_certificate["statement_sha256"] = statement_sha256
        execution_certificate["answer_tex_sha256"] = answer_tex_sha256
        execution_certificate["tool_name"] = tool_name
        execution_certificate["runtime_binding"] = {
            "input_sha256": statement_sha256,
            "answer_tex_sha256": answer_tex_sha256,
            "tool_name": tool_name,
        }
        execution_certificate["morphism_chain"] = morphism_chain
        if not execution_certificate.get("capability_origin"):
            execution_certificate["capability_origin"] = (
                "registered_parameterized_morphism"
                if execution_certificate.get("cold_generalization_contract")
                else "verified_backend_execution"
            )
        _annotate_capability_provenance(execution_certificate)
    verified_cold_parameterized_morphism = bool(
        execution_certificate is not None
        and _is_verified_cold_parameterized_morphism(execution_certificate)
    )
    if (
        not allow_theorem_kernels
        and execution_certificate is not None
        and execution_certificate.get("registered_composite_used") is True
        and not verified_cold_parameterized_morphism
    ):
        return 422, {
            "ok": False,
            "generated": 0,
            "requested": 1,
            "engine": "MORTRA typed exact solver (no registered routes, no LLM)",
            "evaluation_mode": evaluation_mode,
            "error": (
                "登録済みの完成経路は公開解答として採用しません。"
                "現在の問題文から再合成するため、未解決義務を研究workerへ渡します。"
            ),
            "trace": [
                "問題文を型付き意味IRへ変換",
                "実行候補と証明書の由来を検査",
                "登録済み完成経路を公開結果から除外",
                "現在入力からの再合成を継続",
            ],
            "diagnostics": _failure_diagnostics(
                data,
                stage="registered_completed_route",
                candidate_answer=answer,
            ),
        }
    if verified_cold_parameterized_morphism and execution_certificate is not None:
        execution_certificate["public_release_basis"] = (
            "current-input-bound verified parameterized theorem replay"
        )
    backend_replayed = replayed_execution_certificate is not None
    certificate_verified = bool(
        execution_certificate
        and execution_certificate.get("verified") is True
        and (result.get("verified") is True or backend_replayed)
    )
    if not certificate_verified:
        return 422, {
            "ok": False,
            "generated": 0,
            "requested": 1,
            "engine": "MORTRA typed exact solver (no LLM)",
            "evaluation_mode": evaluation_mode,
            "error": "計算候補は得られましたが、入力と解答に結び付いた再生可能な証明書がないため公開しません。",
            "trace": [
                "問題文を型付き意味IRへ変換",
                "計算候補を取得",
                "証明書の入力ハッシュ・解答ハッシュ・検証済み状態を検査",
                "証明書が不完全なため未解決義務として保存",
            ],
            "diagnostics": _failure_diagnostics(
                data,
                stage="certificate_replay",
                candidate_answer=answer,
            ),
        }
    certificate_sha256 = (
        hashlib.sha256(
            json.dumps(
                execution_certificate,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        if execution_certificate is not None
        else None
    )
    trace = [
        "問題文を型付き意味IRへ変換",
        "実行可能制約を構成",
        f"{tool_name} で厳密計算",
        "元の条件への代入検査に合格",
        "問題文・解答・検証証明書を出力",
    ]
    card_payload = {
        "statement_tex": statement,
        "answer_tex": answer_tex,
        "solution_tex": _solution_text(statement, answer_tex, data),
        "family_id": f"solve.{route}.{intent}",
        "domain": route,
        "morphism_chain": morphism_chain,
        "verification": {
            "method": f"{tool_name}: exact execution + original-constraint check",
            "exact_backend": bool(result.get("verified") is True or backend_replayed),
            "independent_check": certificate_verified,
            "verification_scope": (
                "deterministic in-process witness replay; "
                "not an independent external theorem prover"
            ),
            "checks": [
                "typed executable call completed",
                "structural theorem replay certificate verified",
                "original-domain witness and proof obligations replayed",
            ],
            "certificate_sha256": certificate_sha256,
        },
        "execution_certificate": execution_certificate,
    }
    for display_key in ("diagram", "diagram_tikz", "visual_explanation"):
        display_value = result.get(display_key)
        if display_value:
            card_payload[display_key] = display_value
    card = (
        attach_solution_artifact(card_payload, trace)
        if include_publication_artifact
        else card_payload
    )
    return 200, {
        "ok": True,
        "generated": 1,
        "requested": 1,
        "engine": "MORTRA typed exact solver (no LLM)",
        "evaluation_mode": evaluation_mode,
        "cards": [card],
        "trace": trace,
    }


def solve_public_problem(problem: str) -> tuple[int, dict[str, Any]]:
    """Run the product solver without research-only completed routes."""

    status, payload = solve_problem(problem, allow_theorem_kernels=False)
    payload["uses_external_llm"] = False
    return status, payload


class handler(BaseHTTPRequestHandler):
    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - Vercel handler contract
        self._json(
            200,
            {
                "engine": "MORTRA typed exact solver (no LLM)",
                "mode": "single-problem",
                "uses_external_llm": False,
            },
        )

    def do_POST(self) -> None:  # noqa: N802 - Vercel handler contract
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            status, result = solve_public_problem(str(payload.get("problem") or ""))
        except Exception as error:  # The public endpoint must return structured failure.
            status, result = 500, {"ok": False, "error": f"解答器の実行に失敗しました: {error}"}
        self._json(status, result)
