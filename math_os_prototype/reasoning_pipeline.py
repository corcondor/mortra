"""Seven-layer reasoning pipeline for Math OS."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

try:
    from math_os_prototype.domain_registry import DomainIR, DomainRegistry
    from math_os_prototype.formal_language import compile_formal_ir
    from math_os_prototype.math_search import run_math_search
    from math_os_prototype.math_os import MathIR, ToolCall, ToolExecutor, run_pipeline
    from math_os_prototype.category_semantics import compile_typed_semantic_graph, run_verifier_gate
    from math_os_prototype.retriever import HybridRetriever
    from math_os_prototype.solution_graph import build_solution_graph
    from math_os_prototype.solution_step_parser import SolutionStepParser
    from math_os_prototype.step_verifier import StepVerifier
    from math_os_prototype.structural_parser import analyze_structure
    from math_os_prototype.typed_definition_kernel import compile_typed_definition_ir
    from math_os_prototype.web_solution_fetcher import WebSolutionFetcher
except ImportError:  # Allows local script use from the package directory.
    from domain_registry import DomainIR, DomainRegistry
    from formal_language import compile_formal_ir
    from math_search import run_math_search
    from math_os import MathIR, ToolCall, ToolExecutor, run_pipeline
    from category_semantics import compile_typed_semantic_graph, run_verifier_gate
    from retriever import HybridRetriever
    from solution_graph import build_solution_graph
    from solution_step_parser import SolutionStepParser
    from step_verifier import StepVerifier
    from structural_parser import analyze_structure
    from typed_definition_kernel import compile_typed_definition_ir
    from web_solution_fetcher import WebSolutionFetcher


@dataclass
class Strategy:
    name: str
    rationale: str
    tools: list[str]
    confidence: float


@dataclass
class SimulationReport:
    status: str
    observations: list[str]
    suggested_checks: list[str]


@dataclass
class VerificationReport:
    status: str
    checks: list[str]
    warnings: list[str] = field(default_factory=list)


@dataclass
class ReasoningPipelineResult:
    problem: str
    domain_ir: dict[str, Any]
    parser: dict[str, Any]
    structural_ir: dict[str, Any]
    typed_definition_ir: dict[str, Any]
    formal_ir: dict[str, Any]
    semantic_graph: dict[str, Any]
    constraint_ir: dict[str, Any]
    verifier_gate: dict[str, Any]
    memory_retrieval: dict[str, Any]
    web_solutions: dict[str, Any]
    strategies: list[dict[str, Any]]
    math_search: dict[str, Any]
    solution_graph: dict[str, Any]
    simulation: dict[str, Any]
    tool_execution: dict[str, Any]
    verification: dict[str, Any]
    explanation: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


class StrategyPlanner:
    def plan(self, ir: MathIR, retrieval: dict[str, Any], domain_ir: DomainIR | None = None) -> list[Strategy]:
        strategies: list[Strategy] = []
        intent = ir.intent
        base_intent = intent.removeprefix("latex_to_")
        route = ir.route
        domain_name = domain_ir.domain if domain_ir else "unknown"
        hit_hints = [hit.get("strategy_hint", "") for hit in retrieval.get("hits", [])]

        if "container_square_in_equilateral_triangle" in base_intent:
            strategies.append(
                Strategy(
                    name="support_function_sweep",
                    rationale="Containment of convex bodies can be converted to support-function inequalities.",
                    tools=["symbolic geometry", "line integral", "optional simulation"],
                    confidence=0.88,
                )
            )
            strategies.append(
                Strategy(
                    name="numerical_orientation_sweep",
                    rationale="Sample triangle orientations to detect symmetry and boundary candidates before proof.",
                    tools=["simulation", "Shapely", "SymPy"],
                    confidence=0.62,
                )
            )
        elif "equilateral_triangle_centroid_locus_area" in base_intent:
            strategies.append(
                Strategy(
                    name="geometry_constraint_compilation",
                    rationale="The parser should first build a constraint graph for points, curve membership, equilateral geometry, centroid, locus, and area instead of recalling a solved pattern.",
                    tools=["GeometryConstraintIR", "CAS elimination", "numeric continuation", "proof verifier"],
                    confidence=0.82,
                )
            )
        elif base_intent.startswith("number_theory_"):
            strategies.append(
                Strategy(
                    name="number_theory_adapter",
                    rationale="The parser produced a typed number-theory IR that can be checked by divisibility or small-case logic.",
                    tools=["NumberTheoryAdapter", "SymPy"],
                    confidence=0.82,
                )
            )
        elif base_intent.startswith("probability_"):
            strategies.append(
                Strategy(
                    name="probability_moment_adapter",
                    rationale="The parser produced a probability IR whose target reduces to exact moments or asymptotic moments.",
                    tools=["ProbabilityAdapter", "SymPy"],
                    confidence=0.80,
                )
            )
        elif base_intent.startswith("inequality_"):
            strategies.append(
                Strategy(
                    name="inequality_counterexample_adapter",
                    rationale="Before trying a proof, search small integer cases for a counterexample.",
                    tools=["InequalityAdapter", "SymPy"],
                    confidence=0.70,
                )
            )
        elif base_intent.startswith("geometry_circle_overlap"):
            strategies.append(
                Strategy(
                    name="coordinate_geometry_asymptotic_adapter",
                    rationale="The circle-overlap geometry can be represented by an exact area formula and asymptotic expansion.",
                    tools=["GeometryAdapter", "SymPy"],
                    confidence=0.78,
                )
            )
        elif route == "symbolic_algebra" and domain_name in {"unknown", "algebra"}:
            strategies.append(
                Strategy(
                    name="cas_solve_verify",
                    rationale="Algebraic equations can be delegated to a CAS, then verified by substitution.",
                    tools=["SymPy", "Wolfram"],
                    confidence=0.78,
                )
            )
        elif route == "calculus" and domain_name in {"unknown", "calculus"}:
            strategies.append(
                Strategy(
                    name="cas_calculus_verify",
                    rationale="Symbolic calculus tasks should be parsed into expression, variable, and operation.",
                    tools=["SymPy", "Wolfram"],
                    confidence=0.76,
                )
            )
        elif route == "convex_geometry" and domain_name in {"unknown", "convex_geometry"}:
            strategies.append(
                Strategy(
                    name="convex_model_then_check",
                    rationale="Convex objects can be represented by vertices, halfspaces, or support functions.",
                    tools=["Shapely", "SymPy", "Z3"],
                    confidence=0.72,
                )
            )
        elif route == "formal_proof" and domain_name in {"unknown", "formal_proof"}:
            strategies.append(
                Strategy(
                    name="formalize_then_kernel_check",
                    rationale="Formal tasks should be lowered to assumptions and a target proposition before Lean checks it.",
                    tools=["Lean", "Mathlib retrieval"],
                    confidence=0.66,
                )
            )
        elif "region" in intent:
            strategies.append(
                Strategy(
                    name="existential_quantifier_elimination",
                    rationale="A passing region is naturally expressed as an existential condition over parameters.",
                    tools=["SymPy", "Wolfram Reduce"],
                    confidence=0.84,
                )
            )
        elif "envelope" in intent:
            strategies.append(
                Strategy(
                    name="envelope_resultant",
                    rationale="Envelope conditions are F=0 and dF/dt=0.",
                    tools=["SymPy resultant", "Wolfram Eliminate"],
                    confidence=0.86,
                )
            )
        elif "locus" in intent:
            strategies.append(
                Strategy(
                    name="parametric_elimination",
                    rationale="Eliminate the parameter from x=f(t), y=g(t).",
                    tools=["SymPy resultant", "Wolfram Eliminate"],
                    confidence=0.82,
                )
            )

        if domain_ir and not strategies and domain_ir.domain != "unknown":
            strategies.append(
                Strategy(
                    name=f"{domain_ir.domain}_domain_plan",
                    rationale=(
                        f"DomainRegistry classified this as {domain_ir.label_ja}; "
                        f"use {', '.join(domain_ir.methods[:2])} and verify with {', '.join(domain_ir.verification[:2])}."
                    ),
                    tools=domain_ir.target_tools,
                    confidence=max(0.35, domain_ir.confidence - 0.05),
                )
            )

        for hint in hit_hints:
            if hint and all(hint != strategy.rationale for strategy in strategies):
                strategies.append(
                    Strategy(
                        name="retrieved_pattern",
                        rationale=hint,
                        tools=["retrieval", "CAS verification"],
                        confidence=0.50,
                    )
                )
        if not strategies:
            strategies.append(
                Strategy(
                    name="explore_then_verify",
                    rationale="No strong typed solver matched; use retrieval and simulation to propose a route.",
                    tools=["retrieval", "simulation", "CAS"],
                    confidence=0.35,
                )
            )
        return strategies[:5]


class SimulationEngine:
    def simulate(self, ir: MathIR, domain_ir: DomainIR | None = None) -> SimulationReport:
        intent = ir.intent
        if "container_square_in_equilateral_triangle" in intent:
            return SimulationReport(
                status="symbolic_simulation_available",
                observations=[
                    "The problem has D4 symmetry from the fixed square.",
                    "Orientation sweep suggests the boundary can be reduced to one 45-degree wedge.",
                    "The triangle side is tuned so its height equals the maximum support-function sum of the square.",
                ],
                suggested_checks=[
                    "Verify the support-function containment inequality.",
                    "Check the boundary parameterization endpoints.",
                    "Confirm the line-integral area times 8.",
                ],
            )
        if "geometry_dsl_region" in intent or "geometry_nl_to_dsl_region" in intent:
            return SimulationReport(
                status="not_needed",
                observations=["The region was represented exactly as an existential algebraic condition."],
                suggested_checks=["Compare SymPy inequality with Wolfram Reduce when available."],
            )
        if domain_ir and domain_ir.domain in {"number_theory", "combinatorics", "graph_theory", "inequalities"}:
            return SimulationReport(
                status="small_case_search_planned",
                observations=[
                    f"DomainRegistry suggests small-case exploration for {domain_ir.domain}.",
                    "Use this only to generate conjectures or find counterexamples before symbolic proof.",
                ],
                suggested_checks=domain_ir.verification[:3],
            )
        if domain_ir and domain_ir.domain in {"probability", "statistics", "optimization"}:
            return SimulationReport(
                status="numeric_sanity_check_planned",
                observations=[
                    f"DomainRegistry suggests numeric or sampling checks for {domain_ir.domain}.",
                ],
                suggested_checks=domain_ir.verification[:3],
            )
        return SimulationReport(
            status="planned",
            observations=["No dedicated simulator is wired for this intent yet."],
            suggested_checks=["Add sampling or counterexample search for this problem family."],
        )


class Verifier:
    def verify(self, ir: MathIR) -> VerificationReport:
        checks = []
        warnings = []
        if not ir.tool_calls:
            return VerificationReport("unverified", [], ["No tool calls were produced."])

        executable_calls = [call for call in ir.tool_calls if call.executable]
        all_executed = bool(executable_calls) and all(call.status == "executed" for call in executable_calls)
        if all_executed:
            checks.append("All executable tool calls completed.")
        elif not executable_calls:
            warnings.append("No executable solver was available for this parsed problem.")
        else:
            warnings.append("Some executable tool calls did not complete.")

        for call in ir.tool_calls:
            if call.error:
                warnings.append(f"{call.name} error: {call.error}")
            if call.result is None:
                continue
            if isinstance(call.result, dict) and "tool_results" in call.result:
                tool_statuses = [
                    f"{item.get('tool')}:{item.get('status')}"
                    for item in call.result.get("tool_results", [])
                ]
                checks.append(f"Tool adapter statuses: {', '.join(tool_statuses)}")
            if isinstance(call.result, dict) and call.result.get("status") == "solved":
                checks.append("Dedicated solver returned solved status.")
            if isinstance(call.result, dict) and call.result.get("status") == "formalized":
                checks.append("Executable constraint IR was emitted.")
            if isinstance(call.result, dict) and call.result.get("status") == "counterexample_found":
                checks.append("Small counterexample was found and checked.")
            if isinstance(call.result, dict) and call.result.get("status") == "no_small_counterexample":
                warnings.append("Small-case search found no counterexample, but this is not a proof.")
            if isinstance(call.result, dict) and call.result.get("status") in {"no_parse", "unavailable"}:
                warnings.append(f"{call.name} returned {call.result.get('status')}.")

        status = "verified" if checks and not warnings else "partial"
        return VerificationReport(status, checks, warnings)


class ExplanationBuilder:
    def build(
        self,
        ir: MathIR,
        strategies: list[Strategy],
        verification: VerificationReport,
        math_search: dict[str, Any] | None = None,
        web_solutions: dict[str, Any] | None = None,
        formal_ir: dict[str, Any] | None = None,
        semantic_graph: dict[str, Any] | None = None,
        verifier_gate: dict[str, Any] | None = None,
    ) -> str:
        lines = [
            f"Intent: {ir.intent}",
            f"Selected strategy: {strategies[0].name if strategies else 'none'}",
        ]
        direct_answer = extract_answer(ir)
        search_answer = (math_search or {}).get("answer")
        if direct_answer and has_executed_dedicated_answer(ir):
            answer = direct_answer
        else:
            answer = search_answer or direct_answer
        if answer:
            lines.append(f"Answer: {answer}")
        if math_search and math_search.get("status"):
            lines.append(f"MathSearch: {math_search['status']}")
        typed_definition_ir = formal_ir.get("typed_definition_ir") if isinstance(formal_ir, dict) else None
        if typed_definition_ir and typed_definition_ir.get("status"):
            lines.append(f"TypedKernel: {typed_definition_ir['status']}")
        if formal_ir and formal_ir.get("status"):
            lines.append(f"FormalIR: {formal_ir['status']}")
        if semantic_graph and semantic_graph.get("status"):
            lines.append(f"SemanticGraph: {semantic_graph['status']}")
        if verifier_gate and verifier_gate.get("status"):
            lines.append(f"VerifierGate: {verifier_gate['status']}")
        if web_solutions and web_solutions.get("enabled"):
            summary = web_solutions.get("summary", {})
            lines.append(
                "WebSolutions: "
                f"fetched={summary.get('fetched', 0)}, "
                f"parsed={summary.get('parsed_answers', 0)}, "
                f"checked={summary.get('verified_or_sanity_checked', 0)}"
            )
        if verification.checks:
            lines.append("Verification: " + " / ".join(verification.checks))
        warnings = list(verification.warnings)
        if math_search and math_search.get("status") == "solved_generic":
            warnings = [
                warning
                for warning in warnings
                if warning != "No executable solver was available for this parsed problem."
            ]
        if warnings:
            lines.append("Warnings: " + " / ".join(warnings))
        return "\n".join(lines)


def run_reasoning_pipeline(
    problem: str,
    *,
    external_tools: bool = False,
    live_retrieval: bool = False,
    allow_specialized: bool = False,
) -> ReasoningPipelineResult:
    registry = DomainRegistry()
    structure = analyze_structure(problem)
    typed_definition_ir = compile_typed_definition_ir(problem)
    formal_ir = compile_formal_ir(problem)
    search_result = run_math_search(structure, external_tools=external_tools)
    ir = run_pipeline(
        problem,
        execute=False,
        external_tools=external_tools,
        allow_specialized=allow_specialized,
    )
    parser_info = {
        "intent": ir.intent,
        "route": ir.route,
        "symbols": ir.symbols,
        "givens": ir.givens,
        "notes": ir.notes,
        "cold_mode": not allow_specialized,
    }
    domain_ir = registry.analyze(problem, parser_info)
    execute_safe_tool_calls(ir, domain_ir, problem, external_tools=external_tools)
    parser_info["domain"] = domain_ir.domain
    parser_info["domain_confidence"] = domain_ir.confidence
    parser_info["domain_ir"] = domain_ir.to_dict()
    retrieval = HybridRetriever(live_search=live_retrieval).retrieve(problem, parser_info)
    web_solutions = build_web_solution_report(
        retrieval,
        external_tools=external_tools,
        enabled=live_retrieval,
    )
    strategies = StrategyPlanner().plan(ir, retrieval, domain_ir)
    simulation = SimulationEngine().simulate(ir, domain_ir)
    verification = Verifier().verify(ir)
    search_dict = asdict(search_result)
    graph = build_solution_graph(problem, structure.to_dict(), retrieval, search_dict, web_solutions)
    formal_dict = formal_ir.to_dict()
    formal_dict["typed_definition_ir"] = typed_definition_ir.to_dict()
    semantic_graph = compile_typed_semantic_graph(
        problem,
        structural_ir=structure.to_dict(),
        typed_definition_ir=typed_definition_ir.to_dict(),
        formal_ir=formal_ir.to_dict(),
        arithmetic_problem=ir.givens.get("arithmetic_problem") if isinstance(ir.givens, dict) else None,
        symbolic_query_ir=ir.givens.get("symbolic_query") if isinstance(ir.givens, dict) else None,
        vector_query_ir=ir.givens.get("vector_query") if isinstance(ir.givens, dict) else None,
        matrix_query_ir=ir.givens.get("matrix_semantic_query") if isinstance(ir.givens, dict) else None,
        discrete_query_ir=ir.givens.get("discrete_constraint_query") if isinstance(ir.givens, dict) else None,
    )
    semantic_answer = extract_answer(ir) or search_dict.get("answer")
    verifier_gate = run_verifier_gate(semantic_graph, answer=str(semantic_answer) if semantic_answer is not None else None)
    constraint_ir = semantic_graph.constraint_ir()
    explanation = ExplanationBuilder().build(
        ir,
        strategies,
        verification,
        search_dict,
        web_solutions,
        formal_dict,
        semantic_graph.to_dict(),
        verifier_gate.to_dict(),
    )
    return ReasoningPipelineResult(
        problem=problem,
        domain_ir=domain_ir.to_dict(),
        parser=parser_info,
        structural_ir=structure.to_dict(),
        typed_definition_ir=typed_definition_ir.to_dict(),
        formal_ir=formal_ir.to_dict(),
        semantic_graph=semantic_graph.to_dict(),
        constraint_ir=constraint_ir.to_dict(),
        verifier_gate=verifier_gate.to_dict(),
        memory_retrieval=retrieval,
        web_solutions=web_solutions,
        strategies=[asdict(strategy) for strategy in strategies],
        math_search=search_dict,
        solution_graph=graph.to_dict(),
        simulation=asdict(simulation),
        tool_execution=ir_to_tool_execution_dict(ir),
        verification=asdict(verification),
        explanation=explanation,
    )


def build_web_solution_report(
    retrieval: dict[str, Any],
    *,
    external_tools: bool = False,
    enabled: bool = False,
) -> dict[str, Any]:
    if not enabled:
        return {
            "enabled": False,
            "fetched": [],
            "parsed": [],
            "verified": [],
            "summary": {"fetched": 0, "parsed_answers": 0, "verified_or_sanity_checked": 0},
        }
    fetcher = WebSolutionFetcher()
    fetched = fetcher.fetch_from_hits(retrieval.get("live_hits", []) or retrieval.get("hits", []), limit=3)
    parser = SolutionStepParser()
    verifier = StepVerifier(external_tools=external_tools)
    parsed_items = []
    verified_items = []
    for solution in fetched:
        for answer in solution.answers[:2]:
            parsed = parser.parse_answer(
                answer.body_text,
                source_url=solution.url,
                answer_id=answer.answer_id,
            )
            verified = verifier.verify_solution(parsed)
            parsed_items.append(parsed.to_dict())
            verified_items.append(verified.to_dict())
    verified_count = sum(
        1
        for item in verified_items
        if item.get("status") in {"verified_or_sanity_checked", "partially_verified"}
    )
    return {
        "enabled": True,
        "fetched": [item.to_dict() for item in fetched],
        "parsed": parsed_items,
        "verified": verified_items,
        "summary": {
            "fetched": len(fetched),
            "parsed_answers": len(parsed_items),
            "verified_or_sanity_checked": verified_count,
        },
    }


def execute_safe_tool_calls(
    ir: MathIR,
    domain_ir: DomainIR,
    problem: str,
    *,
    external_tools: bool = False,
) -> None:
    for call in ir.tool_calls:
        if call.executable and not is_safe_tool_call(call, ir, domain_ir, problem):
            call.executable = False
            ir.notes.append(f"Skipped unsafe generic execution for {call.name}.")
    ToolExecutor(external_tools=external_tools).execute(ir)


def is_safe_tool_call(call: ToolCall, ir: MathIR, domain_ir: DomainIR, problem: str) -> bool:
    name = call.name
    text = problem.lower()
    if name.startswith(("number_theory.", "inequality.", "probability.", "geometry.circle_overlap_limit")):
        return True
    if name == "arithmetic.nl":
        return True
    if name == "geometry.constraint_ir":
        return True
    if name == "geometry.asymptote_exact":
        return True
    if name == "sympy.vector_query":
        payload = ir.givens.get("vector_query") if isinstance(ir.givens, dict) else None
        return isinstance(payload, dict) and bool(payload.get("operator")) and bool(payload.get("lowering_certificate"))
    if name == "sympy.matrix_semantic_query":
        payload = ir.givens.get("matrix_semantic_query") if isinstance(ir.givens, dict) else None
        return (
            isinstance(payload, dict)
            and bool(payload.get("query_operator"))
            and bool(payload.get("target"))
            and bool(payload.get("lowering_certificate"))
        )
    if name == "sympy.linear_constraint_query":
        payload = ir.givens.get("linear_constraint_query") if isinstance(ir.givens, dict) else None
        certificate = payload.get("lowering_certificate") if isinstance(payload, dict) else None
        return (
            isinstance(payload, dict)
            and len(payload.get("constraints") or []) >= 2
            and bool(payload.get("query_coefficients"))
            and isinstance(certificate, dict)
            and certificate.get("kind") == "rational_linear_constraint_projection"
            and certificate.get("all_numeric_premises_consumed") is True
        )
    if name == "sympy.finite_relation_query":
        payload = ir.givens.get("finite_relation_query") if isinstance(ir.givens, dict) else None
        certificate = payload.get("lowering_certificate") if isinstance(payload, dict) else None
        return (
            isinstance(payload, dict)
            and bool(payload.get("equation"))
            and isinstance(certificate, dict)
            and certificate.get("kind") == "typed_finite_relation"
            and certificate.get("hole_count") == 1
            and certificate.get("all_numeric_premises_consumed") is True
        )
    if name == "sympy.discrete_constraint_query":
        payload = ir.givens.get("discrete_constraint_query") if isinstance(ir.givens, dict) else None
        return (
            isinstance(payload, dict)
            and bool(payload.get("operator"))
            and isinstance(payload.get("domain"), dict)
            and bool(payload.get("lowering_certificate"))
        )
    if name in {
        "container.square_in_equilateral_triangle",
        "geometry.dsl",
        "geometry.minkowski_sum",
        "sympy.polynomial_remainder",
    }:
        return True
    if name == "sympy.envelope":
        return "envelope" in ir.intent or "包絡線" in text
    if name == "sympy.diff":
        return domain_ir.domain == "calculus" and any(token in text for token in ("derivative", "differentiate", "微分"))
    if name == "sympy.solve":
        if "連立" in problem:
            return False
        return domain_ir.domain == "algebra" and (
            ("solve " in text and " for " in text)
            or ("解け" in text and "=" in text)
        )
    if name == "sympy.semantic_query":
        payload = ir.givens.get("symbolic_query") if isinstance(ir.givens, dict) else None
        return (
            domain_ir.domain in {"algebra", "inequalities", "prealgebra", "unknown"}
            and isinstance(payload, dict)
            and bool(payload.get("query_operator"))
            and bool(payload.get("target"))
        )
    return False


def should_execute_for_domain(domain_ir: DomainIR, problem: str) -> bool:
    text = problem.lower()
    if "余り" in text and "割" in text:
        return True
    if domain_ir.domain in {"geometry", "convex_geometry"}:
        return True
    if domain_ir.domain == "calculus":
        return any(token in text for token in ("derivative", "differentiate", "微分"))
    if domain_ir.domain == "algebra":
        return ("solve " in text and " for " in text) or ("解け" in text and "=" in text) or ("余り" in text and "割" in text)
    return False


def ir_to_tool_execution_dict(ir: MathIR) -> dict[str, Any]:
    return {
        "route": ir.route,
        "intent": ir.intent,
        "plan": ir.plan,
        "tool_calls": [asdict(call) for call in ir.tool_calls],
    }


def extract_answer(ir: MathIR) -> str | None:
    for call in ir.tool_calls:
        result = call.result
        if not isinstance(result, dict):
            continue
        if "answer_exact" in result:
            return str(result["answer_exact"])
        if "solutions" in result:
            return str(result["solutions"])
        if "derivative" in result:
            return str(result["derivative"])
        if "remainder" in result:
            return str(result["remainder"])
        if "vertices" in result:
            return str(result["vertices"])
        if "result" in result and isinstance(result["result"], dict):
            inner = result["result"]
            if "answer_exact" in inner:
                return str(inner["answer_exact"])
            if "solutions" in inner:
                return str(inner["solutions"])
            if "derivative" in inner:
                return str(inner["derivative"])
            if "remainder" in inner:
                return str(inner["remainder"])
            if "vertices" in inner:
                return str(inner["vertices"])
            if "closed_form" in inner and isinstance(inner["closed_form"], dict):
                return str(inner["closed_form"].get("inequality") or inner["closed_form"])
            for key in ("envelope_relation", "locus_relation", "readable"):
                if key in inner:
                    return str(inner[key])
    return None


def has_executed_dedicated_answer(ir: MathIR) -> bool:
    generic_names = {"sympy.solve", "sympy.algebra", "sympy.calculus"}
    return any(
        call.status == "executed"
        and call.name not in generic_names
        and isinstance(call.result, dict)
        for call in ir.tool_calls
    )
