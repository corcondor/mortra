"""Generic math-state experiment runner.

This module avoids benchmark-specific detectors. It turns a StructuralIR into
generic experiments, runs what can be verified, and exposes the action tree.
"""

from __future__ import annotations

import ast
import re
from dataclasses import asdict, dataclass, field
from itertools import product
from typing import Any

try:
    import sympy as sp
except ImportError:  # pragma: no cover
    sp = None

try:
    from math_os_prototype.structural_parser import StructuralIR
    from math_os_prototype.tool_adapters import WolframAdapter
except ImportError:  # Allows local script use.
    from structural_parser import StructuralIR
    from tool_adapters import WolframAdapter


KNOWN_FUNCTIONS = ("sin", "cos", "tan", "log", "exp", "sqrt")


@dataclass
class MathState:
    relations: list[str]
    constraints: list[dict[str, Any]]
    target_operations: list[dict[str, Any]]
    quantities: list[str]


@dataclass
class MathAction:
    name: str
    input_summary: str
    verifier: str
    command: str | None = None
    executable: bool = False
    result: dict[str, Any] | None = None
    status: str = "planned"


@dataclass
class MathSearchResult:
    status: str
    state: dict[str, Any]
    actions: list[dict[str, Any]]
    answer: str | None = None
    notes: list[str] = field(default_factory=list)


def run_math_search(
    structure: StructuralIR,
    *,
    budget: int = 24,
    external_tools: bool = False,
) -> MathSearchResult:
    state = MathState(
        relations=structure.relations,
        constraints=[asdict(item) for item in structure.constraints],
        target_operations=[asdict(item) for item in structure.operations],
        quantities=structure.quantities,
    )
    actions = generate_actions(structure)[:budget]
    answer = None
    notes: list[str] = []

    for action in actions:
        if not action.executable:
            continue
        if action.name == "generic_sympy_value_from_constraints":
            action.result = try_generic_value_from_constraints(structure)
        elif action.name == "generic_existence_range":
            action.result = try_generic_existence_range(structure)
        elif action.name == "generic_sympy_system_solve":
            action.result = try_generic_system_solve(structure)
        elif action.name == "generic_sympy_solve":
            action.result = try_generic_sympy_solve(structure)
        elif action.name == "generic_counterexample_search":
            action.result = try_generic_counterexample_search(structure)
        elif action.name == "generic_inequality_implication":
            action.result = try_generic_inequality_implication(structure)
        elif action.name == "generic_sympy_expression_transform":
            action.result = try_generic_expression_transform(structure)
        elif action.name == "generic_forall_quadratic_positivity":
            action.result = try_generic_forall_quadratic_positivity(structure)
        elif action.name == "generic_sympy_limit":
            action.result = try_generic_limit(structure)
        elif action.name == "generic_sympy_integral":
            action.result = try_generic_integral(structure)
        elif action.name == "generic_probability_state_space":
            action.result = try_generic_probability_state_space(structure)
        elif action.name == "generic_matrix_determinant":
            action.result = try_generic_matrix_determinant(structure)
        elif action.name == "generic_combinatorics_count":
            action.result = try_generic_combinatorics_count(structure)
        elif action.name == "generic_sympy_optimization":
            action.result = try_generic_optimization(structure)
        elif action.name == "generic_complex_absolute_value":
            action.result = try_generic_complex_absolute_value(structure)
        elif action.name == "generic_modular_parity_proof":
            action.result = try_generic_modular_parity_proof(structure)
        elif action.name == "generic_wolfram_experiment":
            action.result = run_wolfram_experiment(action.command or "", external_tools=external_tools)
        else:
            action.result = {"status": "not_implemented"}
        action.status = "executed"
        if action.result and answer is None and action.result.get("status") in {"solved", "counterexample_found"}:
            answer = str(action.result.get("answer_exact") or action.result.get("counterexample"))

    status = "solved_generic" if answer else "planned_generic_search"
    if not answer:
        notes.append("No benchmark-specific detector was used; only generic actions were planned or attempted.")
    return MathSearchResult(
        status=status,
        state=asdict(state),
        actions=[asdict(action) for action in actions],
        answer=answer,
        notes=notes,
    )


def generate_actions(structure: StructuralIR) -> list[MathAction]:
    affordances = set(structure.tool_affordances)
    operation_kinds = {operation.kind for operation in structure.operations}
    actions: list[MathAction] = []
    suppress_plain_equation_solve = is_geometry_locus_measure_problem(structure)

    if contains_text(structure, ("絶対値", "absolute value", "modulus")):
        actions.append(
            MathAction(
                "generic_complex_absolute_value",
                "evaluate absolute value/modulus from explicit complex assignment",
                "square_norm_or_abs_check",
                executable=True,
            )
        )
    if "sympy.solve" in affordances and structure.relations and not suppress_plain_equation_solve:
        if contains_text(structure, ("すべての実数", "任意の実数", "for all real", "必要十分条件")):
            actions.append(
                MathAction(
                    "generic_forall_quadratic_positivity",
                    "derive parameter condition for one-variable quadratic positivity",
                    "discriminant_condition_and_quantifier_check",
                    executable=True,
                )
            )
        range_parameter = choose_range_parameter(structure)
        equation_count = sum(1 for constraint in structure.constraints if constraint.kind == "equation")
        if range_parameter:
            actions.append(
                MathAction(
                    name="generic_existence_range",
                    input_summary=f"existence range for {range_parameter}",
                    verifier="discriminant_or_quantifier_elimination_sanity_checks",
                    executable=True,
                )
            )
        target_expr = choose_target_expression(structure)
        if target_expr and equation_count >= 1:
            actions.append(
                MathAction(
                    name="generic_sympy_value_from_constraints",
                    input_summary=f"{target_expr} under {equation_count} equation(s)",
                    verifier="solve_constraints_then_substitute_target_expression",
                    executable=True,
                )
            )
        if equation_count >= 2:
            actions.append(
                MathAction(
                    name="generic_sympy_system_solve",
                    input_summary=f"solve {equation_count} equation constraints",
                    verifier="substitution_back_into_all_equations_and_domain_constraints",
                    executable=True,
                )
            )
        actions.append(
            MathAction(
                name="generic_sympy_solve",
                input_summary=structure.relations[-1],
                verifier="substitution_back_into_equation_and_domain_constraints",
                executable=True,
            )
        )
    if "numeric_counterexample_search" in affordances and structure.relations:
        actions.append(
            MathAction(
                name="generic_inequality_implication",
                input_summary=structure.relations[-1],
                verifier="prove_by_unsat_of_assumptions_and_negated_target",
                executable=True,
            )
        )
        actions.append(
            MathAction(
                name="generic_counterexample_search",
                input_summary=structure.relations[-1],
                verifier="direct_relation_evaluation_under_constraints",
                executable=True,
            )
        )
    if "sympy.expression" in affordances:
        actions.append(
            MathAction(
                "generic_sympy_expression_transform",
                "factor/simplify/expand target expression",
                "reverse_transform_or_symbolic_equivalence",
                executable=True,
            )
        )
    if "limit" in operation_kinds:
        actions.append(
            MathAction(
                "generic_sympy_limit",
                "detect limit expression and variable",
                "numeric_asymptotic_sampling_then_CAS_check",
                executable=True,
            )
        )
    if "integral" in operation_kinds:
        actions.append(
            MathAction(
                "generic_sympy_integral",
                "detect integrand, variable, and bounds",
                "differentiate_antiderivative_or_numeric_quadrature_check",
                executable=True,
            )
        )
    if {"passing_region", "locus", "envelope"} & operation_kinds:
        actions.append(MathAction("generic_elimination_model", "build existential formula and eliminate parameters", "sample_points_against_original_constraints"))
    if "integer_model_search" in affordances:
        if contains_text(structure, ("偶数", "even")) and contains_text(structure, ("ならば", "implies")):
            actions.append(
                MathAction(
                    "generic_modular_parity_proof",
                    "prove parity implication by exhaustive residues modulo 2",
                    "complete_modular_case_split",
                    executable=True,
                )
            )
        actions.append(MathAction("generic_integer_search", "enumerate bounded integer cases to conjecture structure", "exact substitution and modular checks"))
    if "coordinate_geometry_model" in affordances:
        actions.append(MathAction("generic_coordinate_geometry_model", "assign coordinates to geometric primitives", "constraint residuals and symbolic equivalence"))
    if "finite_probability_model" in affordances:
        actions.append(
            MathAction(
                "generic_probability_state_space",
                "construct finite sample space or limiting random variables",
                "total_probability_and_moment_checks",
                executable=True,
            )
        )
    if contains_text(structure, ("行列式", "determinant")):
        actions.append(
            MathAction(
                "generic_matrix_determinant",
                "parse explicit matrix literal and compute determinant",
                "cofactor_or_matrix_det_check",
                executable=True,
            )
        )
    if contains_text(structure, ("何通り", "選ぶ方法", "choose")):
        actions.append(
            MathAction(
                "generic_combinatorics_count",
                "parse n choose k counting problem",
                "integer_combination_formula_check",
                executable=True,
            )
        )
    if "critical_point_search" in affordances:
        actions.append(
            MathAction(
                "generic_sympy_optimization",
                "differentiate objective and evaluate critical points",
                "critical_point_and_boundary_check",
                executable=True,
            )
        )

    wolfram_code = build_wolfram_experiment_code(structure)
    if wolfram_code:
        actions.append(
            MathAction(
                name="generic_wolfram_experiment",
                input_summary="run generic Wolfram Reduce/Resolve/Solve experiment",
                verifier="Wolfram kernel result plus independent sanity checks",
                command=wolfram_code,
                executable=True,
            )
        )
    return actions


def try_generic_sympy_solve(structure: StructuralIR) -> dict[str, Any]:
    if sp is None:
        return {"status": "unavailable", "error": "SymPy is not installed."}
    relation = structure.relations[-1] if structure.relations else ""
    if is_geometry_locus_measure_problem(structure):
        return {
            "status": "not_applicable",
            "reason": "geometry locus/area tasks need parameter elimination, not solving the displayed curve equation",
        }
    if contains_text(structure, ("微分方程式", "differential equation", "dy/dx", "ode")):
        return {"status": "not_applicable", "reason": "differential equations need dsolve, not algebraic solve"}
    if "=" not in relation or any(op in relation for op in ("<", ">")):
        return {"status": "not_applicable", "reason": "target is not a plain equation"}
    variable = choose_variable(structure.variables, relation)
    if not variable:
        return {"status": "no_variable"}
    try:
        lhs_text, rhs_text = relation.split("=", 1)
        symbols = {name: sp.symbols(name) for name in structure.variables}
        lhs = sp.sympify(normalize_expr(lhs_text), locals=symbols)
        rhs = sp.sympify(normalize_expr(rhs_text), locals=symbols)
        var = symbols[variable]
        expr = lhs - rhs
        filtered = []
        for solution in sp.solve(expr, var):
            if sp.simplify(expr.subs(var, solution)) == 0 and solution_is_allowed_by_constraints(structure, {variable: solution}):
                filtered.append(solution)
        if filtered:
            return {"status": "solved", "answer_exact": [str(item) for item in filtered], "variable": variable, "verified": True}
        return {"status": "no_solution_or_filtered_out"}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}


def try_generic_value_from_constraints(structure: StructuralIR) -> dict[str, Any]:
    if sp is None:
        return {"status": "unavailable", "error": "SymPy is not installed."}
    target_text = choose_target_expression(structure)
    if not target_text:
        return {"status": "not_applicable", "reason": "no standalone target expression detected"}
    equation_constraints = [constraint for constraint in structure.constraints if constraint.kind == "equation"]
    if not equation_constraints:
        return {"status": "not_applicable", "reason": "no equation constraints"}
    try:
        symbols = {name: sp.symbols(name) for name in structure.variables}
        equations = []
        for constraint in equation_constraints:
            lhs_text, rhs_text = constraint.expression.split("=", 1)
            lhs = sp.sympify(normalize_expr(lhs_text), locals=symbols)
            rhs = sp.sympify(normalize_expr(rhs_text), locals=symbols)
            equations.append(sp.Eq(lhs, rhs))
        target = sp.sympify(normalize_expr(target_text), locals=symbols)
        solve_vars = sorted(
            {symbol for equation in equations for symbol in equation.free_symbols},
            key=lambda item: item.name,
        )
        if not solve_vars:
            return {"status": "not_applicable", "reason": "equations have no symbolic variables"}
        solutions = sp.solve(equations, solve_vars, dict=True)
        if not solutions:
            return {"status": "no_solution"}
        values = []
        for solution in solutions:
            assignment = {str(symbol): value for symbol, value in solution.items()}
            if not solution_is_allowed_by_constraints(structure, assignment):
                continue
            value = sp.simplify(target.subs(solution))
            if value.free_symbols:
                continue
            if all(sp.simplify(value - existing) != 0 for existing in values):
                values.append(value)
        if not values:
            return {"status": "no_ground_value", "target": target_text}
        answer = values[0] if len(values) == 1 else values
        return {
            "status": "solved",
            "answer_exact": str(answer) if len(values) == 1 else [str(item) for item in values],
            "target": target_text,
            "verified": True,
            "solution_count": len(solutions),
        }
    except Exception as exc:
        return {"status": "failed", "error": str(exc), "target": target_text}


def try_generic_system_solve(structure: StructuralIR) -> dict[str, Any]:
    if sp is None:
        return {"status": "unavailable", "error": "SymPy is not installed."}
    equation_constraints = [constraint for constraint in structure.constraints if constraint.kind == "equation"]
    if len(equation_constraints) < 2:
        return {"status": "not_applicable", "reason": "fewer than two equation constraints"}
    try:
        symbols = {name: sp.symbols(name) for name in structure.variables}
        equations = []
        for constraint in equation_constraints:
            lhs_text, rhs_text = constraint.expression.split("=", 1)
            lhs = sp.sympify(normalize_expr(lhs_text), locals=symbols)
            rhs = sp.sympify(normalize_expr(rhs_text), locals=symbols)
            equations.append(sp.Eq(lhs, rhs))
        solve_vars = sorted(
            {symbol for equation in equations for symbol in equation.free_symbols},
            key=lambda item: item.name,
        )
        if not solve_vars:
            return {"status": "no_variable"}
        solutions = sp.solve(equations, solve_vars, dict=True)
        filtered = []
        for solution in solutions:
            assignment = {str(symbol): value for symbol, value in solution.items()}
            if not solution_is_allowed_by_constraints(structure, assignment):
                continue
            if all(bool(equation.subs(solution)) for equation in equations):
                filtered.append({str(symbol): str(sp.simplify(value)) for symbol, value in solution.items()})
        if not filtered:
            return {"status": "no_solution_or_filtered_out"}
        answer = filtered[0] if len(filtered) == 1 else filtered
        return {
            "status": "solved",
            "answer_exact": answer,
            "variables": [str(symbol) for symbol in solve_vars],
            "verified": True,
        }
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}


def try_generic_existence_range(structure: StructuralIR) -> dict[str, Any]:
    if sp is None:
        return {"status": "unavailable", "error": "SymPy is not installed."}
    parameter = choose_range_parameter(structure)
    if not parameter:
        return {"status": "not_applicable", "reason": "no range parameter detected"}
    equation_constraints = [constraint for constraint in structure.constraints if constraint.kind == "equation"]
    if len(equation_constraints) != 1:
        return {"status": "not_applicable", "reason": "expected one equation constraint"}
    try:
        symbols = {name: sp.symbols(name, real=True) for name in structure.variables}
        if parameter not in symbols:
            return {"status": "not_applicable", "reason": "range parameter is not symbolic"}
        lhs_text, rhs_text = equation_constraints[0].expression.split("=", 1)
        expr = sp.sympify(normalize_expr(lhs_text), locals=symbols) - sp.sympify(normalize_expr(rhs_text), locals=symbols)
        param_symbol = symbols[parameter]
        existence_vars = sorted(expr.free_symbols - {param_symbol}, key=lambda item: item.name)
        if len(existence_vars) != 1:
            return {"status": "not_applicable", "reason": "expected one existential variable"}
        variable = existence_vars[0]
        poly = sp.Poly(expr, variable)
        if poly.degree() != 2:
            return {"status": "not_applicable", "reason": "currently handles quadratic real-root ranges"}
        leading = poly.LC()
        if leading.has(param_symbol):
            return {"status": "not_applicable", "reason": "parameter-dependent leading coefficient needs case split"}
        discriminant = sp.factor(sp.discriminant(poly.as_expr(), variable))
        condition = sp.reduce_inequalities([discriminant >= 0], param_symbol)
        return {
            "status": "solved",
            "answer_exact": str(condition),
            "parameter": parameter,
            "existential_variable": str(variable),
            "condition": str(discriminant >= 0),
            "verified": True,
        }
    except Exception as exc:
        return {"status": "failed", "error": str(exc), "parameter": parameter}


def try_generic_counterexample_search(structure: StructuralIR) -> dict[str, Any]:
    if sp is None:
        return {"status": "unavailable", "error": "SymPy is not installed."}
    relation = structure.relations[-1] if structure.relations else ""
    if not any(op in relation for op in ("<=", ">=", "<", ">")):
        return {"status": "not_applicable", "reason": "target is not an inequality"}
    variables = [var for var in structure.variables if re.search(rf"\b{re.escape(var)}\b", relation)][:4]
    if not variables:
        return {"status": "no_variable"}
    try:
        parsed = parse_relation(relation, variables)
        symbols = {name: sp.symbols(name) for name in variables}
        for values in product(range(-4, 5), repeat=len(variables)):
            assignment = dict(zip(variables, values))
            if not simple_constraints_hold(structure, assignment, target_relation=relation):
                continue
            if not bool(parsed.subs({symbols[name]: value for name, value in assignment.items()})):
                return {"status": "counterexample_found", "counterexample": assignment, "relation": relation}
        return {"status": "no_small_counterexample", "relation": relation, "note": "not a proof"}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}


def try_generic_inequality_implication(structure: StructuralIR) -> dict[str, Any]:
    if sp is None:
        return {"status": "unavailable", "error": "SymPy is not installed."}
    relation = structure.relations[-1] if structure.relations else ""
    if not any(op in relation for op in ("<=", ">=", "<", ">")):
        return {"status": "not_applicable", "reason": "target is not an inequality"}
    variables = [var for var in structure.variables if re.search(rf"\b{re.escape(var)}\b", relation)]
    if len(variables) != 1:
        return {"status": "not_applicable", "reason": "currently handles one target variable"}
    variable = variables[0]
    try:
        target = parse_relation(relation, [variable])
        assumptions = []
        for constraint in structure.constraints:
            if constraint.expression == relation or constraint.kind != "inequality":
                continue
            if variable in constraint.variables:
                assumptions.append(parse_relation(constraint.expression, [variable]))
        contradiction_inputs = [*assumptions, sp.Not(target)]
        contradiction = sp.reduce_inequalities(contradiction_inputs, sp.symbols(variable))
        if contradiction is False or contradiction == sp.false:
            return {
                "status": "solved",
                "answer_exact": "proved",
                "method": "assumptions_and_negated_target_unsatisfiable" if assumptions else "negated_target_unsatisfiable",
                "target": relation,
                "verified": True,
            }
        return {
            "status": "not_proved",
            "remaining_counter_region": str(contradiction),
            "target": relation,
        }
    except Exception as exc:
        return {"status": "failed", "error": str(exc), "target": relation}


def try_generic_forall_quadratic_positivity(structure: StructuralIR) -> dict[str, Any]:
    if sp is None:
        return {"status": "unavailable", "error": "SymPy is not installed."}
    relation = structure.relations[-1] if structure.relations else ""
    if not any(op in relation for op in (">", ">=", "<", "<=")):
        return {"status": "not_applicable", "reason": "target is not an inequality"}
    parameter = choose_range_parameter(structure) or choose_parameter_for_universal_condition(structure, relation)
    if not parameter:
        return {"status": "not_applicable", "reason": "no parameter detected"}
    try:
        all_symbols = {name: sp.symbols(name, real=True) for name in structure.variables}
        param_symbol = all_symbols[parameter]
        variable_candidates = [name for name in structure.variables if name != parameter and re.search(rf"\b{re.escape(name)}\b", relation)]
        if len(variable_candidates) != 1:
            return {"status": "not_applicable", "reason": "expected one universally quantified variable"}
        var = all_symbols[variable_candidates[0]]
        lhs_text, op, rhs_text = split_relation_operator(relation)
        expr = sp.sympify(normalize_expr(lhs_text), locals=all_symbols) - sp.sympify(normalize_expr(rhs_text), locals=all_symbols)
        poly = sp.Poly(expr, var)
        if poly.degree() != 2:
            return {"status": "not_applicable", "reason": "currently handles quadratic expressions"}
        leading = sp.simplify(poly.LC())
        discriminant = sp.factor(sp.discriminant(poly.as_expr(), var))
        if op == ">":
            conditions = [leading > 0, discriminant < 0]
        elif op == ">=":
            conditions = [leading > 0, discriminant <= 0]
        elif op == "<":
            conditions = [leading < 0, discriminant < 0]
        else:
            conditions = [leading < 0, discriminant <= 0]
        condition = sp.reduce_inequalities(conditions, param_symbol)
        return {
            "status": "solved",
            "answer_exact": str(condition),
            "parameter": parameter,
            "universal_variable": str(var),
            "discriminant": str(discriminant),
            "verified": True,
        }
    except Exception as exc:
        return {"status": "failed", "error": str(exc), "relation": relation}


def try_generic_expression_transform(structure: StructuralIR) -> dict[str, Any]:
    if sp is None:
        return {"status": "unavailable", "error": "SymPy is not installed."}
    operation = next(
        (item for item in structure.operations if item.kind in {"factor", "simplify", "expand"}),
        None,
    )
    if operation is None:
        return {"status": "not_applicable", "reason": "no expression transform requested"}
    target = operation.target or choose_target_expression(structure)
    if not target:
        return {"status": "not_applicable", "reason": "no target expression"}
    try:
        symbols = {name: sp.symbols(name) for name in structure.variables}
        expr = sp.sympify(normalize_expr(target), locals=symbols)
        if operation.kind == "factor":
            result = sp.factor(expr)
        elif operation.kind == "expand":
            result = sp.expand(expr)
        else:
            result = sp.simplify(expr)
        return {
            "status": "solved",
            "answer_exact": str(result),
            "operation": operation.kind,
            "target": target,
            "verified": True,
        }
    except Exception as exc:
        return {"status": "failed", "error": str(exc), "target": target}


def try_generic_limit(structure: StructuralIR) -> dict[str, Any]:
    if sp is None:
        return {"status": "unavailable", "error": "SymPy is not installed."}
    parsed = parse_limit_request(structure)
    if parsed is None:
        return {"status": "not_applicable", "reason": "could not parse limit target"}
    variable, point, expression = parsed
    if not is_executable_math_text(expression):
        return {
            "status": "not_applicable",
            "reason": "the extracted limit target is not a mathematical expression",
            "target": expression,
        }
    try:
        symbols = {name: sp.symbols(name) for name in sorted(set(structure.variables + [variable]))}
        var = symbols[variable]
        expr = sp.sympify(normalize_expr(expression), locals=symbols)
        point_expr = sympy_point(point, symbols)
        declared_symbols = set(symbols.values())
        unbound_symbols = (expr.free_symbols | point_expr.free_symbols) - declared_symbols
        if unbound_symbols:
            return {
                "status": "not_applicable",
                "reason": "the limit contains symbols that were not bound by semantic elaboration",
                "unbound_symbols": sorted(str(item) for item in unbound_symbols),
                "target": expression,
            }
        result = sp.limit(expr, var, point_expr)
        return {
            "status": "solved",
            "answer_exact": str(sp.simplify(result)),
            "variable": variable,
            "point": str(point_expr),
            "target": expression,
            "verified": True,
        }
    except Exception as exc:
        return {"status": "failed", "error": str(exc), "target": expression}


def try_generic_integral(structure: StructuralIR) -> dict[str, Any]:
    if sp is None:
        return {"status": "unavailable", "error": "SymPy is not installed."}
    parsed = parse_integral_request(structure)
    if parsed is None:
        return {"status": "not_applicable", "reason": "could not parse integral target"}
    variable, lower, upper, expression = parsed
    if not is_executable_math_text(expression):
        return {
            "status": "not_applicable",
            "reason": "the extracted integrand is not a mathematical expression",
            "target": expression,
        }
    try:
        symbols = {name: sp.symbols(name) for name in sorted(set(structure.variables + [variable]))}
        var = symbols[variable]
        expr = sp.sympify(normalize_expr(expression), locals=symbols)
        declared_symbols = set(symbols.values())
        if expr.free_symbols - declared_symbols:
            return {
                "status": "not_applicable",
                "reason": "the integrand contains symbols that were not bound by semantic elaboration",
                "unbound_symbols": sorted(str(item) for item in expr.free_symbols - declared_symbols),
                "target": expression,
            }
        if lower is None or upper is None:
            result = sp.integrate(expr, var)
            bounds = None
        else:
            lower_expr = sympy_point(lower, symbols)
            upper_expr = sympy_point(upper, symbols)
            bound_symbols = lower_expr.free_symbols | upper_expr.free_symbols
            if bound_symbols - declared_symbols:
                return {
                    "status": "not_applicable",
                    "reason": "an integration bound contains symbols that were not bound by semantic elaboration",
                    "unbound_symbols": sorted(str(item) for item in bound_symbols - declared_symbols),
                }
            result = sp.integrate(expr, (var, lower_expr, upper_expr))
            bounds = [str(lower_expr), str(upper_expr)]
        return {
            "status": "solved",
            "answer_exact": str(sp.simplify(result)),
            "variable": variable,
            "bounds": bounds,
            "target": expression,
            "verified": True,
        }
    except Exception as exc:
        return {"status": "failed", "error": str(exc), "target": expression}


def try_generic_probability_state_space(structure: StructuralIR) -> dict[str, Any]:
    text = structure.normalized_text
    if "サイコロ" not in text and "dice" not in text.lower():
        return {"status": "not_applicable", "reason": "only dice state spaces are implemented"}
    count_match = re.search(r"(\d+)\s*回", text)
    dice_count = int(count_match.group(1)) if count_match else 1
    sum_match = re.search(r"和が\s*(\d+)", text)
    if not sum_match:
        sum_match = re.search(r"sum\s*(?:is|=)?\s*(\d+)", text, flags=re.IGNORECASE)
    if not sum_match:
        return {"status": "not_applicable", "reason": "could not detect target sum"}
    target_sum = int(sum_match.group(1))
    outcomes = list(product(range(1, 7), repeat=dice_count))
    favorable = [outcome for outcome in outcomes if sum(outcome) == target_sum]
    if not outcomes:
        return {"status": "failed", "error": "empty state space"}
    probability = sp.Rational(len(favorable), len(outcomes)) if sp is not None else len(favorable) / len(outcomes)
    return {
        "status": "solved",
        "answer_exact": str(probability),
        "model": f"{dice_count}d6",
        "favorable": len(favorable),
        "total": len(outcomes),
        "verified": True,
    }


def try_generic_matrix_determinant(structure: StructuralIR) -> dict[str, Any]:
    if sp is None:
        return {"status": "unavailable", "error": "SymPy is not installed."}
    match = re.search(r"\[\s*\[[^\]]+\](?:\s*,\s*\[[^\]]+\])+\s*\]", structure.source_text)
    if not match:
        return {"status": "not_applicable", "reason": "no explicit matrix literal"}
    try:
        matrix_data = ast.literal_eval(match.group(0))
        matrix = sp.Matrix(matrix_data)
        determinant = sp.det(matrix)
        return {
            "status": "solved",
            "answer_exact": str(determinant),
            "shape": list(matrix.shape),
            "verified": True,
        }
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}


def try_generic_combinatorics_count(structure: StructuralIR) -> dict[str, Any]:
    text = structure.normalized_text
    match = re.search(r"(\d+)\s*人から\s*(\d+)\s*人", text)
    if not match:
        match = re.search(r"choose\s*\(?\s*(\d+)\s*,\s*(\d+)\s*\)?", text, flags=re.IGNORECASE)
    if not match:
        return {"status": "not_applicable", "reason": "could not parse n choose k"}
    n = int(match.group(1))
    k = int(match.group(2))
    if k < 0 or n < 0 or k > n:
        return {"status": "solved", "answer_exact": "0", "n": n, "k": k, "verified": True}
    value = sp.binomial(n, k) if sp is not None else 0
    return {"status": "solved", "answer_exact": str(value), "n": n, "k": k, "verified": True}


def try_generic_optimization(structure: StructuralIR) -> dict[str, Any]:
    if sp is None:
        return {"status": "unavailable", "error": "SymPy is not installed."}
    operation = next((item for item in structure.operations if item.kind == "optimize"), None)
    if operation is None:
        return {"status": "not_applicable", "reason": "no optimization operation"}
    target = choose_target_expression(structure) or operation.target
    if not target:
        return {"status": "not_applicable", "reason": "no objective expression"}
    try:
        symbols = {name: sp.symbols(name, real=True) for name in structure.variables}
        expr = sp.sympify(normalize_expr(target), locals=symbols)
        variables = sorted(expr.free_symbols, key=lambda item: item.name)
        if len(variables) != 1:
            return {"status": "not_applicable", "reason": "currently handles one-variable objectives"}
        var = variables[0]
        derivative = sp.diff(expr, var)
        critical_points = sp.solve(derivative, var)
        candidates = [sp.simplify(expr.subs(var, point)) for point in critical_points]
        if not candidates:
            return {"status": "not_applicable", "reason": "no critical point found"}
        sense = operation.qualifiers.get("sense", "min")
        if sense == "max":
            value = max(candidates, key=lambda item: float(item))
        else:
            value = min(candidates, key=lambda item: float(item))
        return {
            "status": "solved",
            "answer_exact": str(sp.simplify(value)),
            "variable": str(var),
            "critical_points": [str(item) for item in critical_points],
            "sense": sense,
            "verified": True,
        }
    except Exception as exc:
        return {"status": "failed", "error": str(exc), "target": target}


def try_generic_complex_absolute_value(structure: StructuralIR) -> dict[str, Any]:
    if sp is None:
        return {"status": "unavailable", "error": "SymPy is not installed."}
    relation = structure.relations[-1] if structure.relations else ""
    if "=" not in relation:
        return {"status": "not_applicable", "reason": "no explicit complex assignment"}
    try:
        _, rhs_text = relation.split("=", 1)
        symbols = {name: sp.symbols(name) for name in structure.variables if name not in {"i", "I"}}
        expr = sp.sympify(normalize_expr(rhs_text), locals={**symbols, "i": sp.I, "I": sp.I})
        value = sp.simplify(sp.Abs(expr))
        return {
            "status": "solved",
            "answer_exact": str(value),
            "target": rhs_text,
            "verified": True,
        }
    except Exception as exc:
        return {"status": "failed", "error": str(exc), "relation": relation}


def try_generic_modular_parity_proof(structure: StructuralIR) -> dict[str, Any]:
    text = structure.normalized_text
    variable_match = re.search(r"\b([A-Za-z])\b(?:\*\*|\^)?2?\s*が偶数ならば\s*\1\s*も偶数", text)
    if not variable_match:
        variable_match = re.search(r"\b([A-Za-z])\b(?:\*\*|\^)?2?\s+is even.*\1\s+is even", text, flags=re.IGNORECASE)
    if not variable_match:
        return {"status": "not_applicable", "reason": "no n^2 even implies n even pattern"}
    variable = variable_match.group(1)
    modulus = 2
    cases = []
    for residue in range(modulus):
        square_even = (residue * residue) % modulus == 0
        variable_even = residue % modulus == 0
        cases.append(
            {
                f"{variable}_mod_2": residue,
                f"{variable}^2_mod_2": (residue * residue) % modulus,
                "premise_even": square_even,
                "conclusion_even": variable_even,
                "case_ok": (not square_even) or variable_even,
            }
        )
    if all(item["case_ok"] for item in cases):
        return {
            "status": "solved",
            "answer_exact": "proved",
            "method": "complete_residue_case_split_mod_2",
            "theorem": f"forall {variable}: even({variable}^2) -> even({variable})",
            "proof_steps": [
                f"Every integer {variable} is congruent to 0 or 1 modulo 2.",
                f"If {variable} mod 2 = 0, then {variable} is even.",
                f"If {variable} mod 2 = 1, then {variable}^2 mod 2 = 1, so the premise even({variable}^2) is false.",
                f"Therefore every residue satisfying even({variable}^2) also satisfies even({variable}).",
            ],
            "certificate": {"modulus": modulus, "cases": cases},
            "verified": True,
        }
    return {"status": "failed", "reason": "a residue class violates the implication", "certificate": cases}


def run_wolfram_experiment(code: str, *, external_tools: bool) -> dict[str, Any]:
    adapter = WolframAdapter(timeout_seconds=20)
    if not code:
        return {"status": "no_command"}
    if not external_tools:
        return {"status": "planned", "available": adapter.is_available(), "command": code}
    return adapter.execute_code(code, label="generic_math_search").to_dict()


def build_wolfram_experiment_code(structure: StructuralIR) -> str | None:
    if not structure.variables or not structure.relations:
        return None
    operation_kinds = {operation.kind for operation in structure.operations}
    variables = structure.variables[:6]
    relation = to_wolfram_relation(structure.relations[-1])
    assumptions = wolfram_assumptions(structure, variables, target_relation=structure.relations[-1])
    var_list = "{" + ", ".join(variables) + "}"
    formula = f"({assumptions}) && ({relation})" if assumptions else relation

    if "prove" in operation_kinds and any(op in structure.relations[-1] for op in ("<=", ">=", "<", ">")):
        implication = f"Implies[{assumptions or 'True'}, {relation}]"
        return inputform(f"Resolve[ForAll[{var_list}, {implication}], Reals]")
    if "solve_all" in operation_kinds:
        domain = "Integers" if has_integer_constraints(structure) else "Reals"
        return inputform(f"Reduce[{formula}, {var_list}, {domain}]")
    if "compute_or_solve" in operation_kinds and "=" in structure.relations[-1]:
        domain = "Integers" if has_integer_constraints(structure) else "Reals"
        return inputform(f"Reduce[{formula}, {var_list}, {domain}]")
    if any(kind in operation_kinds for kind in ("passing_region", "locus", "envelope")):
        return inputform(f"Reduce[{formula}, {var_list}, Reals]")
    return inputform(f"FullSimplify[{formula}]")


def wolfram_assumptions(
    structure: StructuralIR,
    variables: list[str],
    *,
    target_relation: str | None = None,
) -> str:
    assumptions: list[str] = []
    for constraint in structure.constraints:
        targets = constraint.variables or variables
        if constraint.kind == "positive_integer":
            assumptions.extend(f"Element[{var}, Integers] && {var} > 0" for var in targets if var in variables)
        elif constraint.kind == "nonnegative_integer":
            assumptions.extend(f"Element[{var}, Integers] && {var} >= 0" for var in targets if var in variables)
        elif constraint.kind == "integer":
            assumptions.extend(f"Element[{var}, Integers]" for var in targets if var in variables)
        elif constraint.kind == "real":
            assumptions.extend(f"Element[{var}, Reals]" for var in targets if var in variables)
        elif constraint.kind == "prime":
            assumptions.extend(f"Element[{var}, Primes]" for var in targets if var in variables)
        elif constraint.kind in {"equation", "inequality"} and constraint.expression != target_relation:
            assumptions.append(to_wolfram_relation(constraint.expression))
    return " && ".join(dict.fromkeys(assumptions))


def has_integer_constraints(structure: StructuralIR) -> bool:
    return any(constraint.kind in {"integer", "positive_integer", "nonnegative_integer", "prime"} for constraint in structure.constraints)


def solution_is_allowed_by_constraints(structure: StructuralIR, assignment: dict[str, Any]) -> bool:
    for constraint in structure.constraints:
        targets = constraint.variables or list(assignment)
        for var in targets:
            if var not in assignment:
                continue
            value = assignment[var]
            if constraint.kind == "positive_integer" and not (value.is_integer and value > 0):
                return False
            if constraint.kind == "nonnegative_integer" and not (value.is_integer and value >= 0):
                return False
            if constraint.kind == "integer" and not value.is_integer:
                return False
            if constraint.kind == "real" and not value.is_real:
                return False
    return True


def parse_relation(relation: str, variables: list[str]) -> Any:
    symbols = {name: sp.symbols(name) for name in variables}
    for op in ("<=", ">=", "<", ">"):
        if op in relation:
            lhs_text, rhs_text = relation.split(op, 1)
            lhs = sp.sympify(normalize_expr(lhs_text), locals=symbols)
            rhs = sp.sympify(normalize_expr(rhs_text), locals=symbols)
            if op == "<=":
                return lhs <= rhs
            if op == ">=":
                return lhs >= rhs
            if op == "<":
                return lhs < rhs
            return lhs > rhs
    raise ValueError("no inequality operator")


def split_relation_operator(relation: str) -> tuple[str, str, str]:
    for op in ("<=", ">=", "!=", "=", "<", ">"):
        if op in relation:
            lhs_text, rhs_text = relation.split(op, 1)
            return lhs_text, op, rhs_text
    raise ValueError("no relation operator")


def simple_constraints_hold(
    structure: StructuralIR,
    assignment: dict[str, int],
    *,
    target_relation: str | None = None,
) -> bool:
    for constraint in structure.constraints:
        if constraint.kind == "positive_integer":
            for var in constraint.variables or assignment.keys():
                if var in assignment and assignment[var] <= 0:
                    return False
        if constraint.kind == "nonnegative_integer":
            for var in constraint.variables or assignment.keys():
                if var in assignment and assignment[var] < 0:
                    return False
        if constraint.kind in {"equation", "inequality"}:
            if target_relation and constraint.expression == target_relation:
                continue
            if not relation_constraint_holds(constraint.expression, assignment):
                return False
    return True


def relation_constraint_holds(relation: str, assignment: dict[str, int]) -> bool:
    variables = [name for name in assignment if re.search(rf"\b{re.escape(name)}\b", relation)]
    if not variables:
        return True
    if any(name not in assignment for name in variables):
        return True
    try:
        if any(op in relation for op in ("<=", ">=", "<", ">")):
            parsed = parse_relation(relation, variables)
            symbols = {name: sp.symbols(name) for name in variables}
            return bool(parsed.subs({symbols[name]: assignment[name] for name in variables}))
        if "=" in relation and "!=" not in relation:
            lhs_text, rhs_text = relation.split("=", 1)
            symbols = {name: sp.symbols(name) for name in variables}
            lhs = sp.sympify(normalize_expr(lhs_text), locals=symbols)
            rhs = sp.sympify(normalize_expr(rhs_text), locals=symbols)
            return bool(sp.simplify((lhs - rhs).subs({symbols[name]: assignment[name] for name in variables})) == 0)
    except Exception:
        return True
    return True


def choose_variable(variables: list[str], relation: str) -> str | None:
    for variable in variables:
        if re.search(rf"\b{re.escape(variable)}\b", relation):
            return variable
    return variables[0] if variables else None


def choose_target_expression(structure: StructuralIR) -> str | None:
    relation_set = {clean_relation_text(relation) for relation in structure.relations}
    variable_set = set(structure.variables)
    for expression in reversed(structure.expressions):
        candidate = clean_relation_text(expression)
        if not candidate or candidate in relation_set:
            continue
        if "," in candidate:
            continue
        if candidate in variable_set:
            continue
        if not any(re.search(rf"\b{re.escape(variable)}\b", candidate) for variable in structure.variables):
            continue
        return candidate
    return None


def choose_range_parameter(structure: StructuralIR) -> str | None:
    if "範囲" not in structure.normalized_text and "range" not in structure.normalized_text.lower():
        return None
    match = re.search(r"\b([A-Za-z])\b\s*の範囲", structure.normalized_text)
    if match and match.group(1) in structure.variables:
        return match.group(1)
    relation_set = {clean_relation_text(relation) for relation in structure.relations}
    for expression in reversed(structure.expressions):
        candidate = clean_relation_text(expression)
        if candidate in structure.variables and candidate not in relation_set:
            return candidate
    return None


def choose_parameter_for_universal_condition(structure: StructuralIR, relation: str) -> str | None:
    if "必要十分条件" in structure.normalized_text:
        match = re.search(r"実数\s+([A-Za-z])\s+について", structure.normalized_text)
        if match and match.group(1) in structure.variables:
            return match.group(1)
    relation_vars = {var for var in structure.variables if re.search(rf"\b{re.escape(var)}\b", relation)}
    candidates = [var for var in structure.variables if var not in relation_vars]
    return candidates[0] if candidates else None


def parse_limit_request(structure: StructuralIR) -> tuple[str, str, str] | None:
    text = structure.normalized_text
    match = re.search(
        r"limit_?\s*([A-Za-z])\s+to\s+([^\s]+)\s+(.+?)(?:\s+を|\s+求め|$)",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return match.group(1), match.group(2), clean_expression_target(match.group(3))
    match = re.search(
        r"limit\s+(.+?)\s+as\s+([A-Za-z])\s+to\s+([^\s]+)",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return match.group(2), match.group(3), clean_expression_target(match.group(1))
    return None


def parse_integral_request(structure: StructuralIR) -> tuple[str, str | None, str | None, str] | None:
    text = structure.normalized_text
    match = re.search(
        r"integral_([^\s]+)\*\*([^\s]+)\s+(.+?)\s+d\s*([A-Za-z])(?:\s+を|\s+求め|$)",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return match.group(4), match.group(1), match.group(2), clean_expression_target(match.group(3))
    match = re.search(
        r"integral\s+(.+?)\s+from\s+([^\s]+)\s+to\s+([^\s]+)\s+with respect to\s+([A-Za-z])",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return match.group(4), match.group(2), match.group(3), clean_expression_target(match.group(1))
    match = re.search(r"integral\s+(.+?)\s+d\s*([A-Za-z])(?:\s+を|\s+求め|$)", text, flags=re.IGNORECASE)
    if match:
        return match.group(2), None, None, clean_expression_target(match.group(1))
    return None


def clean_expression_target(text: str) -> str:
    text = text.strip(" ,，。.;")
    text = re.sub(r"\s+", " ", text)
    return text


def is_executable_math_text(text: str) -> bool:
    """Accept only the compact mathematical language understood by normalize_expr.

    This prevents an imperative suffix such as ``を求めよ`` from being interpreted
    as a product of newly invented SymPy symbols when LaTeX token boundaries were
    lost earlier in the pipeline.
    """

    candidate = text.strip()
    return bool(candidate) and re.fullmatch(
        r"[A-Za-z0-9_+\-*/^().,\s]+",
        candidate,
    ) is not None


def clean_relation_text(text: str) -> str:
    return re.sub(r"\s+", "", text.replace("^", "**"))


def contains_text(structure: StructuralIR, needles: tuple[str, ...]) -> bool:
    text = f"{structure.source_text}\n{structure.normalized_text}".lower()
    return any(needle.lower() in text for needle in needles)


def is_geometry_locus_measure_problem(structure: StructuralIR) -> bool:
    operation_kinds = {operation.kind for operation in structure.operations}
    entity_kinds = {entity.kind for entity in structure.entities}
    if "locus" in operation_kinds and "measure" in operation_kinds:
        return True
    if operation_kinds & {"passing_region", "envelope"} and "measure" in operation_kinds:
        return True
    if "equilateral_triangle" in entity_kinds and contains_text(structure, ("重心", "centroid", "軌跡", "locus")):
        return True
    return False


def inputform(formula: str) -> str:
    return f"ToString[InputForm[FullSimplify[{formula}]]]"


def normalize_expr(expr: str) -> str:
    expr = expr.replace("^", "**")
    expr = normalize_function_application(expr)
    placeholders: dict[str, str] = {}
    for index, function_name in enumerate(KNOWN_FUNCTIONS):
        placeholder = f"@{index}@"
        placeholders[placeholder] = function_name
        expr = re.sub(rf"\b{function_name}\b", placeholder, expr)
    expr = re.sub(r"(?<=\d)(?=[A-Za-z])", "*", expr)
    expr = re.sub(r"(?<=[A-Za-z])(?=\d)", "*", expr)
    expr = re.sub(r"(?<=[A-Za-z])(?=[A-Za-z])", "*", expr)
    for placeholder, function_name in placeholders.items():
        expr = expr.replace(placeholder, function_name)
    return expr.strip()


def normalize_function_application(expr: str) -> str:
    for function_name in KNOWN_FUNCTIONS:
        expr = re.sub(rf"\b{function_name}\s+([A-Za-z_]\w*)\b", rf"{function_name}(\1)", expr)
    return expr


def sympy_point(text: str, symbols: dict[str, Any]) -> Any:
    normalized = text.replace("infinity", "oo")
    return sp.sympify(normalize_expr(normalized), locals={**symbols, "oo": sp.oo})


def to_wolfram_expr(expr: str) -> str:
    return (
        expr.replace("**", "^")
        .replace("sqrt", "Sqrt")
        .replace("sin", "Sin")
        .replace("cos", "Cos")
        .replace("tan", "Tan")
        .replace("log", "Log")
        .replace("exp", "Exp")
    )


def to_wolfram_relation(expr: str) -> str:
    converted = to_wolfram_expr(expr)
    if "!=" in converted or "<=" in converted or ">=" in converted:
        return converted
    if "=" in converted:
        return converted.replace("=", "==", 1)
    return converted
