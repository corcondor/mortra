"""Typed symbolic-query IR and exact SymPy execution.

The legacy algebra route treated every relation as ``solve(..., x)``.  This
module keeps the mathematical constraints separate from the requested
observation, so one relation can be mapped to a solution set, a root
aggregate, an extremizer, or an inequality set without problem templates.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
import re
from typing import Any

import sympy as sp
from sympy.calculus.util import continuous_domain, function_range
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

try:
    from math_os_prototype.latex_frontend import parse_latex_problem
except ImportError:
    from latex_frontend import parse_latex_problem


@dataclass(frozen=True)
class SymbolicQueryIR:
    constraints: list[str]
    expressions: list[str]
    query_operator: str
    target: str
    variables: list[str]
    output_sort: str
    definitions: dict[str, dict[str, str]] = field(default_factory=dict)
    substitutions: dict[str, str] = field(default_factory=dict)
    parameters: dict[str, Any] = field(default_factory=dict)
    lowering_certificate: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compile_symbolic_query(text: str) -> SymbolicQueryIR | None:
    parsed = parse_latex_problem(text)
    segments = [clean_math_segment(part) for item in parsed.math_segments for part in split_math_statements(item)]
    segments = [item for item in segments if item]
    lower = parsed.normalized_text.lower()
    definitions = extract_function_definitions(segments)
    definitions.update(extract_piecewise_function_definitions(parsed.math_segments))
    constraints = [
        relation
        for item in segments
        for clause in split_logical_relations(item)
        if relation_operator(clause)
        for relation in expand_chained_relation(clause)
    ]
    constraints = expand_tuple_equalities(constraints)
    expressions = [item for item in segments if not relation_operator(item)]
    variables = sorted(extract_symbols(segments) - set(definitions))

    function_observation = requested_function_set(lower, definitions)
    if function_observation is not None:
        operator, function_name = function_observation
        definition = definitions[function_name]
        if "expression" in definition:
            compiled = build_ir(
                constraints,
                expressions,
                operator,
                definition["expression"],
                [definition["variable"]],
                "Scalar" if operator in {"function_domain_minimum", "function_domain_maximum"} else "Set",
                definitions,
            )
            if compiled is not None:
                return replace(
                    compiled,
                    parameters={"function": function_name},
                    lowering_certificate={
                        "kind": "real_function_set_observation",
                        "observation": operator,
                        "definition": function_name,
                    },
                )

    inverse_proportion = extract_inverse_proportion_observation(lower)
    if inverse_proportion is not None:
        return replace(
            build_ir(constraints, expressions, "inverse_proportion", inverse_proportion["query"], variables, "Scalar", definitions),
            parameters=inverse_proportion,
            lowering_certificate={"kind": "multiplicative_invariant", "observation": inverse_proportion["query"]},
        )

    binary_operator = extract_binary_operator_definition(segments)
    binary_target = next((item for item in reversed(expressions) if "astop" in item), "")
    if binary_operator and binary_target and query_requests_value(lower):
        return replace(
            build_ir(constraints, expressions, "evaluate_binary_operator", binary_target, variables, "Scalar", definitions),
            parameters=binary_operator,
            lowering_certificate={"kind": "binary_operator_application", "observation": binary_target},
        )

    inverse_target = requested_inverse_function(lower, definitions)
    if inverse_target:
        return replace(
            build_ir(constraints, expressions, "invert_defined_function", inverse_target, variables, "Function", definitions),
            lowering_certificate={"kind": "function_inverse", "observation": inverse_target},
        )

    finite_inverse_target = next((item for item in reversed(expressions) if "**(-1)" in item), "")
    finite_graph = extract_finite_function_graph(constraints)
    if finite_inverse_target and finite_graph and query_requests_value(lower):
        return replace(
            build_ir(constraints, expressions, "evaluate_finite_function_expression", finite_inverse_target, [], "Scalar", definitions),
            parameters={"finite_function_graph": finite_graph},
            lowering_certificate={"kind": "finite_function_graph", "observation": finite_inverse_target},
        )

    if contains_word(lower, "expand") or "展開" in lower:
        target = last_expression(expressions)
        return build_ir(constraints, expressions, "expand", target, variables, "Expression", definitions)
    factor_request = bool(re.search(r"(?:^|[.!?]\s*)factor(?:\s+the)?\s+(?:following\s+)?(?:expression|polynomial)?", lower))
    japanese_factor_request = bool(
        re.search(r"因数分解\s*(?:せよ|しなさい|してください|すること)", lower)
    ) and not bool(re.search(r"因数分解\s*できることを\s*(?:示せ|証明)", lower))
    if factor_request or japanese_factor_request:
        target = last_expression(expressions)
        return build_ir(constraints, expressions, "factor", target, variables, "Expression", definitions)
    if contains_word(lower, "simplify") or "簡単" in lower:
        target = last_expression(expressions)
        return build_ir(constraints, expressions, "simplify", target, variables, "Expression", definitions)

    function_target = next(
        (item for item in reversed(expressions) if any(function_call_present(item, name) for name in definitions)),
        "",
    )
    unsupported_function_query = any(
        marker in lower
        for marker in ("remainder", "divided by", "inverse", "^{-1}", "polynomial of degree", "roots of", "余り", "割")
    )
    if definitions and function_target and query_requests_value(lower) and not unsupported_function_query:
        return build_ir(
            constraints,
            expressions,
            "evaluate_defined_expression",
            function_target,
            variables,
            "Expression",
            definitions,
        )

    equation = next((item for item in constraints if equation_operator(item)), "")
    inequalities = [item for item in constraints if inequality_operator(item)]
    inequality = inequalities[0] if inequalities else ""
    equations = [item for item in constraints if equation_operator(item)]
    constraints, equations = instantiate_coordinate_constraints(lower, constraints, equations)
    equation = next((item for item in equations if equation_operator(item)), "")
    common_root_target = expression_requested_by_query(lower, expressions)
    if len(equations) >= 2 and "root in common" in lower and common_root_target:
        shared_symbols = set.intersection(*(extract_symbols([item]) for item in equations))
        root_candidates = shared_symbols - extract_symbols([common_root_target])
        if len(root_candidates) == 1:
            root_variable = next(iter(root_candidates))
            parameter_variables = sorted(set().union(*(extract_symbols([item]) for item in equations)) - {root_variable})
            compiled = build_ir(
                constraints,
                expressions,
                "common_polynomial_root_projection",
                common_root_target,
                [root_variable, *parameter_variables],
                "Set",
                definitions,
            )
            if compiled is not None:
                return replace(
                    compiled,
                    parameters={
                        "root_variable": root_variable,
                        "parameter_variables": parameter_variables,
                    },
                    lowering_certificate={
                        "kind": "resultant_projection",
                        "constraint_count": len(equations),
                        "observation": common_root_target,
                    },
                )
    if len(equations) > 1:
        target = expression_requested_by_query(lower, expressions)
        if target and query_requests_value(lower):
            compiled = build_ir(
                constraints,
                expressions,
                "solve_system_evaluate",
                target,
                sorted(extract_symbols(equations)),
                "Scalar",
                definitions,
            )
            if compiled is not None:
                return replace(
                    compiled,
                    lowering_certificate={
                        "kind": "constraint_system_observation",
                        "constraint_count": len(equations),
                        "observation": "evaluate target under the unique satisfying assignment",
                    },
                )
        return None

    observed_target = expression_requested_by_query(lower, expressions)
    if (
        equation
        and "complex number" in lower
        and observed_target
        and re.fullmatch(r"\|\s*[A-Za-z]\s*\|", observed_target)
    ):
        complex_variable = re.search(r"[A-Za-z]", observed_target).group(0)
        compiled = build_ir(
            constraints,
            expressions,
            "complex_root_moduli",
            equation,
            [complex_variable],
            "Set",
            definitions,
        )
        if compiled is not None:
            return replace(
                compiled,
                parameters={"complex_variable": complex_variable},
                lowering_certificate={
                    "kind": "complex_root_observation",
                    "observation": f"Abs({complex_variable})",
                },
            )
    if (
        equation
        and observed_target
        and query_requests_value(lower)
        and root_aggregate_query(lower) is None
        and not re.fullmatch(r"[A-Za-z]", observed_target)
    ):
        equation_symbols = extract_symbols([equation])
        target_symbols = extract_symbols([observed_target])
        if target_symbols and target_symbols <= equation_symbols and not query_requests_solution_set(lower):
            compiled = build_ir(
                constraints,
                expressions,
                "solve_constraints_evaluate",
                observed_target,
                sorted(equation_symbols),
                "Scalar",
                definitions,
            )
            if compiled is not None:
                return replace(
                    compiled,
                    lowering_certificate={
                        "kind": "constraint_observation",
                        "constraint_count": len(equations),
                        "observation": observed_target,
                    },
                )

    rounding_operator = None
    if "greatest integer less than or equal" in lower or "floor" in lower or "床関数" in lower:
        rounding_operator = "floor_value"
    elif "least integer greater than or equal" in lower or "ceiling" in lower or "天井関数" in lower:
        rounding_operator = "ceiling_value"
    if not constraints and rounding_operator and expressions:
        target = expressions[-1]
        if is_closed_scalar_term(target):
            compiled = build_ir(constraints, expressions, rounding_operator, target, [], "Integer", definitions)
            if compiled is not None:
                return replace(
                    compiled,
                    lowering_certificate={
                        "kind": "ordered_integer_projection",
                        "constraint_count": 0,
                        "observation": rounding_operator,
                    },
                )

    closed_projection: tuple[str, str] | None = None
    if "nearest integer" in lower or "最も近い整数" in lower:
        closed_projection = ("nearest_integer_value", "Integer")
    elif "positive square root" in lower or "正の平方根" in lower:
        closed_projection = ("positive_square_root", "Real")
    elif "units digit" in lower or "ones digit" in lower or "一の位" in lower:
        closed_projection = ("units_digit", "Integer")
    if not constraints and closed_projection and expressions:
        target = expressions[-1]
        if is_closed_scalar_term(target):
            operator, output_sort = closed_projection
            compiled = build_ir(constraints, expressions, operator, target, [], output_sort, definitions)
            if compiled is not None:
                return replace(
                    compiled,
                    lowering_certificate={
                        "kind": "closed_term_projection",
                        "constraint_count": 0,
                        "observation": operator,
                    },
                )
    query_variable = infer_query_variable(lower, variables, equation or inequality)

    named_roots = extract_named_roots(lower)
    symmetric_target = next(
        (
            item
            for item in reversed(expressions)
            if named_roots and all(re.search(rf"\b{re.escape(name)}\b", item) for name in named_roots)
        ),
        "",
    )
    if equation and named_roots and symmetric_target:
        compiled = build_ir(
            constraints,
            expressions,
            "symmetric_root_expression",
            symmetric_target,
            [infer_symbol(equation) or "x"],
            "Scalar",
            definitions,
        )
        if compiled is not None:
            return replace(compiled, parameters={"equation": equation, "root_symbols": named_roots})

    root_ratio = extract_root_ratio(lower)
    if equation and root_ratio is not None:
        query_parameter = infer_query_variable(lower, variables, equation)
        polynomial_variables = sorted(extract_symbols([equation]) - {query_parameter})
        if polynomial_variables:
            compiled = build_ir(
                constraints,
                expressions,
                "root_ratio_parameter_extreme",
                query_parameter,
                polynomial_variables,
                "Scalar",
                definitions,
            )
            if compiled is not None:
                return replace(
                    compiled,
                    parameters={
                        "equation": equation,
                        "ratio": str(root_ratio),
                        "query_parameter": query_parameter,
                        "selection": "maximum" if any(marker in lower for marker in ("largest", "greatest", "maximum")) else "minimum",
                    },
                    lowering_certificate={"kind": "vieta_root_ratio", "observation": query_parameter},
                )

    qualified_root_subset = any(
        marker in lower for marker in ("positive real", "negative real", "real part", "imaginary part", "inside", "outside")
    )
    asks_for_root_count = bool(
        re.search(r"how many\s+(?:different\s+|distinct\s+|real\s+)?(?:values|solutions|roots)", lower)
        or re.search(r"number of\s+(?:different\s+|distinct\s+|real\s+)?(?:values|solutions|roots)", lower)
    )
    if equation and asks_for_root_count:
        return build_ir(constraints, expressions, "count_solutions", equation, [query_variable], "Integer", definitions)
    if equation and root_aggregate_query(lower) and not qualified_root_subset:
        operator, output_sort = root_aggregate_query(lower)
        if inequalities and re.search(r"\b(?:sin|cos|tan)\b", equation):
            operator = f"{operator}_on_domain"
        return build_ir(constraints, expressions, operator, equation, [query_variable], output_sort, definitions)

    extremum_expression = expression_for_extremum(lower, expressions)
    if extremum_expression:
        operator = "argmin" if asks_for_extremizer(lower) else "minimum_value"
        if any(word in lower for word in ("maximum", "maximal")) or "最大" in lower:
            operator = "argmax" if asks_for_extremizer(lower) else "maximum_value"
        return build_ir(
            constraints,
            expressions,
            operator,
            extremum_expression,
            [query_variable],
            "Scalar",
            definitions,
        )

    if inequalities and requests_integer_solution_aggregate(lower):
        compiled = build_ir(
            constraints,
            expressions,
            "integer_solution_sum",
            " and ".join(inequalities),
            [query_variable],
            "Integer",
            definitions,
        )
        if compiled is not None:
            return replace(
                compiled,
                lowering_certificate={
                    "kind": "finite_integer_set_aggregate",
                    "constraint_count": len(inequalities),
                    "observation": "sum",
                },
            )

    if inequality and query_requests_solution_set(lower):
        return build_ir(
            constraints,
            expressions,
            "solve_inequality",
            " and ".join(inequalities),
            [query_variable],
            "Set",
            definitions,
        )

    excluded_solve_observation = any(
        marker in lower for marker in ("asymptote", "radius", "area", "volume", "distance", "remainder", "|z|", "modulus")
    )
    if equation and query_requests_solution(lower) and not excluded_solve_observation:
        solve_operator = "solve"
        if any(marker in lower for marker in ("smallest value", "least value", "minimum solution")):
            solve_operator = "solve_minimum"
        elif any(marker in lower for marker in ("largest value", "greatest value", "maximum solution")):
            solve_operator = "solve_maximum"
        compiled = build_ir(constraints, expressions, solve_operator, equation, [query_variable], "Set", definitions)
        if compiled is None:
            return None
        return replace(
            compiled,
            substitutions=extract_known_solution_substitution(lower, expressions, equation, query_variable),
        )
    non_scalar_observations = (
        "area", "volume", "radius", "locus", "envelope", "limit", "integral",
        "remainder", "probability", "correlation", "prove", "show that",
        "面積", "体積", "半径", "軌跡", "包絡線", "極限", "積分", "余り", "確率", "相関", "証明", "示せ",
    )
    if (
        not constraints
        and expressions
        and directly_requests_closed_term(lower, expression_requested_by_query(lower, expressions))
        and not any(marker in lower for marker in non_scalar_observations)
    ):
        target = expression_requested_by_query(lower, expressions)
        if target and is_closed_scalar_term(target):
            return replace(
                build_ir(constraints, expressions, "evaluate_expression", target, [], "Scalar", definitions),
                lowering_certificate={
                    "kind": "closed_term_evaluation",
                    "constraint_count": 0,
                    "observation": "normalize and evaluate a closed mathematical term",
                },
            )
    return None


def directly_requests_closed_term(text: str, target: str) -> bool:
    """Require a syntactic dependency from the query operator to its term.

    A closed number appearing in a word problem is data, not automatically the
    requested observation. This elaboration gate prevents a generic CAS
    evaluator from answering an unrelated number found in the statement.
    """
    if not target:
        return False
    escaped = re.escape(target)
    boundary = r"(?=\s|[.!?]|$)"
    english = rf"(?:evaluate|compute|calculate)(?:\s+the)?(?:\s+value\s+of)?\s+{escaped}{boundary}"
    value_question = rf"what\s+is\s+the\s+value\s+of\s+{escaped}{boundary}"
    japanese = rf"{escaped}\s*(?:を)?\s*計算"
    return bool(re.search(english, text) or re.search(value_question, text) or re.search(japanese, text))


def execute_symbolic_query(payload: dict[str, Any]) -> dict[str, Any]:
    ir = SymbolicQueryIR(**payload)
    locals_map = sympy_locals(ir)
    variable_name = ir.variables[0] if ir.variables else "x"
    variable = locals_map.setdefault(variable_name, sp.Symbol(variable_name, real=True))
    operator = ir.query_operator

    if operator in {"expand", "factor", "simplify"}:
        expression = parse_expression(ir.target, locals_map)
        result = {
            "expand": sp.expand,
            "factor": sp.factor,
            "simplify": sp.simplify,
        }[operator](expression)
    elif operator == "evaluate_expression":
        expression = parse_expression(ir.target, locals_map)
        if expression.free_symbols:
            raise ValueError("closed-term evaluation contains unbound symbols")
        result = sp.simplify(expression)
    elif operator in {"function_domain", "function_domain_minimum", "function_domain_maximum", "function_range"}:
        expression = parse_expression(ir.target, locals_map)
        if operator == "function_range":
            result = function_range(expression, variable, sp.S.Reals)
        else:
            domain = continuous_domain(expression, variable, sp.S.Reals)
            if operator == "function_domain":
                result = domain
            elif operator == "function_domain_minimum":
                result = domain.inf
                if result not in domain:
                    raise ValueError("function domain has an infimum but no minimum")
            else:
                result = domain.sup
                if result not in domain:
                    raise ValueError("function domain has a supremum but no maximum")
    elif operator in {"floor_value", "ceiling_value", "nearest_integer_value", "positive_square_root", "units_digit"}:
        expression = parse_expression(ir.target, locals_map)
        if expression.free_symbols:
            raise ValueError("integer projection contains unbound symbols")
        if operator == "floor_value":
            result = sp.floor(expression)
        elif operator == "ceiling_value":
            result = sp.ceiling(expression)
        elif operator == "nearest_integer_value":
            result = sp.floor(expression + sp.Rational(1, 2))
        elif operator == "positive_square_root":
            result = sp.sqrt(expression)
        else:
            if expression.is_integer is not True:
                raise ValueError("units-digit projection requires an integer term")
            result = sp.Mod(expression, 10)
    elif operator in {"solve_system_evaluate", "solve_constraints_evaluate"}:
        equations = [parse_relation(item, locals_map) for item in ir.constraints if equation_operator(item)]
        variables = sorted(
            set().union(*(equation.free_symbols for equation in equations)),
            key=lambda item: item.name,
        )
        target = parse_expression(ir.target, locals_map)
        if not target.free_symbols <= set(variables):
            raise ValueError("target contains symbols not declared by the constraint system")
        solutions = sp.solve(equations, variables, dict=True)
        if not solutions:
            raise ValueError("constraint system has no finite symbolic solutions")
        observed: list[sp.Expr] = []
        for assignment in solutions:
            if not all(sp.simplify(equation.lhs.subs(assignment) - equation.rhs.subs(assignment)) == 0 for equation in equations):
                raise ValueError("backend assignment failed constraint re-verification")
            value = sp.simplify(target.subs(assignment))
            if value.free_symbols:
                raise ValueError("observed value still contains unbound symbols")
            observed.append(value)
        result = observed[0]
        if any(sp.simplify(value - result) != 0 for value in observed[1:]):
            raise ValueError("constraint system does not determine a unique observation")
    elif operator == "evaluate_defined_expression":
        result = evaluate_defined_expression(ir.target, ir.definitions, locals_map)
        result = sp.expand(result)
        if result.free_symbols:
            raise ValueError("defined-expression observation contains unbound symbols")
    elif operator == "invert_defined_function":
        definition = ir.definitions.get(ir.target)
        if not definition or "expression" not in definition:
            raise ValueError("inverse query has no executable function definition")
        input_symbol = locals_map.setdefault(definition["variable"], sp.Symbol(definition["variable"], real=True))
        output_symbol = sp.Symbol("__output", real=True)
        body = expand_defined_body(ir.target, ir.definitions, locals_map)
        solutions = sp.solve(sp.Eq(output_symbol, body), input_symbol)
        if len(solutions) != 1:
            raise ValueError("function definition does not have a unique symbolic inverse")
        result = sp.simplify(solutions[0].subs(output_symbol, input_symbol))
        if not verify_function_inverse(body, result, input_symbol):
            raise ValueError("inverse failed composition verification")
    elif operator == "evaluate_finite_function_expression":
        result = evaluate_finite_function_expression(
            ir.target,
            {str(name): {str(key): str(value) for key, value in mapping.items()} for name, mapping in ir.parameters["finite_function_graph"].items()},
        )
    elif operator == "evaluate_binary_operator":
        result = evaluate_binary_operator(ir.target, ir.parameters, locals_map)
    elif operator == "inverse_proportion":
        first_left = sp.Rational(ir.parameters["first_left"])
        first_right = sp.Rational(ir.parameters["first_right"])
        second_known = sp.Rational(ir.parameters["second_known"])
        result = sp.simplify(first_left * first_right / second_known)
        if sp.simplify(result * second_known - first_left * first_right) != 0:
            raise ValueError("multiplicative invariant failed re-verification")
    elif operator == "root_ratio_parameter_extreme":
        result = solve_root_ratio_parameter(ir, locals_map)
    elif operator == "common_polynomial_root_projection":
        result = solve_common_polynomial_root_projection(ir, locals_map)
    elif operator == "complex_root_moduli":
        result = solve_complex_root_moduli(ir, locals_map)
    elif operator in {"root_sum_on_domain", "root_product_on_domain", "root_square_product_on_domain"}:
        relation = parse_relation(ir.target, locals_map)
        domain = sp.S.Reals
        for constraint in ir.constraints:
            if inequality_operator(constraint) and variable.name in extract_symbols([constraint]):
                domain = sp.Intersection(
                    domain,
                    sp.solve_univariate_inequality(
                        parse_relation(constraint, locals_map),
                        variable,
                        relational=False,
                    ),
                )
        solutions = sp.solveset(relation, variable, domain=domain)
        if not isinstance(solutions, sp.FiniteSet):
            raise ValueError("domain-restricted aggregate has no certified finite solution set")
        if not solutions:
            raise ValueError("domain-restricted aggregate has no solutions")
        values = list(solutions)
        if operator == "root_sum_on_domain":
            result = sp.simplify(sum(values))
        else:
            product = sp.prod(values)
            result = sp.simplify(product if operator == "root_product_on_domain" else product**2)
    elif operator in {"root_sum", "root_product", "root_square_product"}:
        try:
            polynomial = polynomial_from_equation(ir.target, variable, locals_map)
            degree = polynomial.degree()
            if operator == "root_sum":
                result = -polynomial.all_coeffs()[1] / polynomial.all_coeffs()[0]
            else:
                root_product = (-1) ** degree * polynomial.all_coeffs()[-1] / polynomial.all_coeffs()[0]
                result = root_product if operator == "root_product" else sp.expand(root_product**2)
        except (sp.PolynomialError, TypeError, ValueError):
            relation = parse_relation(ir.target, locals_map)
            solutions = sp.solve(relation, variable)
            if not solutions or any(solution.free_symbols for solution in solutions):
                raise ValueError("root aggregate has no finite closed solution set")
            if operator == "root_sum":
                result = sp.simplify(sum(solutions))
            else:
                product = sp.prod(solutions)
                result = sp.simplify(product if operator == "root_product" else product**2)
    elif operator == "symmetric_root_expression":
        equation = str(ir.parameters.get("equation") or "")
        root_names = [str(item) for item in ir.parameters.get("root_symbols", [])]
        polynomial = polynomial_from_equation(equation, variable, locals_map)
        if polynomial.degree() != len(root_names) or not root_names:
            raise ValueError("named roots do not match the polynomial degree")
        roots = [sp.Symbol(name) for name in root_names]
        target_locals = {**locals_map, **dict(zip(root_names, roots))}
        target = parse_expression(ir.target, target_locals)
        symmetric, remainder, mapping = sp.symmetrize(target, roots, formal=True)
        if remainder != 0:
            raise ValueError("requested root expression is not symmetric")
        coefficients = polynomial.all_coeffs()
        substitutions = {
            generator: (-1) ** index * coefficients[index] / coefficients[0]
            for index, (generator, _) in enumerate(mapping, start=1)
        }
        result = sp.simplify(symmetric.subs(substitutions))
    elif operator in {"solve", "solve_minimum", "solve_maximum"}:
        relation = parse_relation(ir.target, locals_map)
        if isinstance(relation, sp.Equality) and relation.has(sp.factorial):
            reduced = sp.combsimp(relation.lhs - relation.rhs)
            quotient = sp.simplify(reduced / sp.factorial(variable))
            relation = sp.Eq(quotient if quotient.has(variable) else reduced, 0)
        for name, value in ir.substitutions.items():
            symbol = locals_map.setdefault(name, sp.Symbol(name, real=True))
            relation = relation.subs(symbol, parse_expression(value, locals_map))
        solutions = sp.solve(relation, variable)
        if not solutions:
            raise ValueError("equation solver returned an uncertified empty solution set")
        if any(getattr(solution, "free_symbols", set()) for solution in solutions):
            raise ValueError("solution still contains an unbound symbol")
        if operator in {"solve_minimum", "solve_maximum"}:
            real_solutions = [solution for solution in solutions if solution.is_real is not False]
            if not real_solutions:
                raise ValueError("ordered solution query has no real solutions")
            ordered = sorted(real_solutions, key=lambda item: float(sp.N(item, 30)))
            return result_payload(ir, ordered[0] if operator == "solve_minimum" else ordered[-1], expression=ir.target)
        if len(solutions) == 1:
            return result_payload(ir, solutions[0], expression=ir.target)
        return result_payload(ir, solutions, expression=ir.target)
    elif operator == "count_solutions":
        relation = parse_relation(ir.target, locals_map)
        solutions = sp.solveset(relation, variable, domain=sp.S.Reals)
        if not isinstance(solutions, sp.FiniteSet):
            raise ValueError("solution-count query has no certified finite real solution set")
        for solution in solutions:
            if sp.simplify(relation.lhs.subs(variable, solution) - relation.rhs.subs(variable, solution)) != 0:
                raise ValueError("counted solution failed substitution verification")
        result = sp.Integer(len(solutions))
    elif operator == "solve_inequality":
        relation_sources = [item for item in ir.constraints if inequality_operator(item)]
        if not relation_sources:
            raise ValueError("inequality query has no order constraints")
        solution_sets = [
            sp.solve_univariate_inequality(parse_relation(item, locals_map), variable, relational=False)
            for item in relation_sources
        ]
        result = sp.Intersection(*solution_sets)
    elif operator == "integer_solution_sum":
        relation_sources = [item for item in ir.constraints if inequality_operator(item)]
        if not relation_sources:
            raise ValueError("integer aggregate has no order constraints")
        solution_sets = [
            sp.solve_univariate_inequality(
                parse_relation(item, locals_map),
                variable,
                relational=False,
            )
            for item in relation_sources
        ]
        solution_set = sp.Intersection(*solution_sets, sp.S.Integers)
        if solution_set.is_finite_set is not True:
            raise ValueError("integer aggregate is not a certified finite set")
        result = sp.simplify(sum(list(solution_set)))
    elif operator in {"argmin", "minimum_value", "argmax", "maximum_value"}:
        expression = parse_expression(ir.target, locals_map)
        result = solve_polynomial_extremum(expression, variable, operator)
    else:
        raise ValueError(f"unsupported symbolic query operator: {operator}")
    return result_payload(ir, result, expression=ir.target)


def build_ir(
    constraints: list[str],
    expressions: list[str],
    operator: str,
    target: str,
    variables: list[str],
    output_sort: str,
    definitions: dict[str, dict[str, str]],
) -> SymbolicQueryIR | None:
    if not target:
        return None
    return SymbolicQueryIR(
        constraints=constraints,
        expressions=expressions,
        query_operator=operator,
        target=target,
        variables=variables or [infer_symbol(target) or "x"],
        output_sort=output_sort,
        definitions=definitions,
    )


def result_payload(ir: SymbolicQueryIR, result: Any, *, expression: str) -> dict[str, Any]:
    if isinstance(result, (list, tuple, set)):
        answer = [sp.sstr(item) for item in result]
    else:
        answer = sp.sstr(result)
    return {
        "answer_exact": answer,
        "query_operator": ir.query_operator,
        "output_sort": ir.output_sort,
        "expression": expression,
        "constraint_count": len(ir.constraints),
        "verified": True,
    }


def solve_polynomial_extremum(expression: sp.Expr, variable: sp.Symbol, operator: str) -> sp.Expr:
    polynomial = sp.Poly(expression, variable)
    if polynomial.degree() != 2:
        raise ValueError("the exact extremum backend currently requires a univariate quadratic")
    a, b, _ = polynomial.all_coeffs()
    extremizer = sp.cancel(-b / (2 * a))
    is_minimum = sp.ask(sp.Q.positive(a)) is True
    if operator in {"argmin", "minimum_value"} and not is_minimum:
        raise ValueError("quadratic has no global minimum")
    if operator in {"argmax", "maximum_value"} and is_minimum:
        raise ValueError("quadratic has no global maximum")
    return extremizer if operator.startswith("arg") else sp.simplify(expression.subs(variable, extremizer))


def polynomial_from_equation(source: str, variable: sp.Symbol, locals_map: dict[str, Any]) -> sp.Poly:
    relation = parse_relation(source, locals_map)
    expression = sp.together(relation.lhs - relation.rhs)
    numerator, _ = expression.as_numer_denom()
    return sp.Poly(sp.expand(numerator), variable)


def parse_relation(source: str, locals_map: dict[str, Any]) -> Any:
    for token, constructor in (("<=", sp.Le), (">=", sp.Ge), ("!=", sp.Ne), ("=", sp.Eq), ("<", sp.Lt), (">", sp.Gt)):
        if token in source:
            left, right = source.split(token, 1)
            return constructor(parse_expression(left, locals_map), parse_expression(right, locals_map))
    raise ValueError("no relation operator")


def parse_expression(source: str, locals_map: dict[str, Any]) -> sp.Expr:
    cleaned = re.sub(r"\b(?:If|Let|Find|Solve|What|For)\b.*?(?=[A-Za-z0-9_(])", "", source).strip(" .,?:~")
    cleaned = normalize_absolute_values(cleaned)
    cleaned = normalize_factorials(cleaned)
    cleaned = cleaned.replace("[", "(").replace("]", ")")
    return parse_expr(
        cleaned,
        local_dict=locals_map,
        transformations=standard_transformations + (convert_xor, implicit_multiplication_application),
        evaluate=True,
    )


def evaluate_defined_expression(
    source: str,
    definitions: dict[str, dict[str, str]],
    locals_map: dict[str, Any],
) -> sp.Expr:
    expanded = source
    for name, definition in definitions.items():
        if "branches" in definition and function_call_present(expanded, name):
            return evaluate_piecewise_call(expanded, name, definition, locals_map)
    for _ in range(len(definitions) + 2):
        changed = False
        for name, definition in definitions.items():
            if "expression" not in definition:
                continue
            pattern = rf"\b{re.escape(name)}\*?\(([^()]*)\)"
            while re.search(pattern, expanded):
                match = re.search(pattern, expanded)
                assert match is not None
                argument = parse_expression(match.group(1), locals_map)
                formal = locals_map.setdefault(definition["variable"], sp.Symbol(definition["variable"]))
                body = parse_expression(definition["expression"], locals_map).subs(formal, argument)
                expanded = expanded[: match.start()] + f"({sp.sstr(body)})" + expanded[match.end() :]
                expanded = re.sub(r"\(\(([^()]*)\)\)", r"(\1)", expanded)
                changed = True
        if not changed:
            break
    return parse_expression(expanded, locals_map)


def expand_defined_body(name: str, definitions: dict[str, dict[str, Any]], locals_map: dict[str, Any]) -> sp.Expr:
    definition = definitions[name]
    body = definition["expression"]
    for nested_name in definitions:
        if nested_name != name and function_call_present(body, nested_name):
            body = sp.sstr(evaluate_defined_expression(body, definitions, locals_map))
    return parse_expression(body, locals_map)


def verify_function_inverse(body: sp.Expr, inverse: sp.Expr, variable: sp.Symbol) -> bool:
    return sp.simplify(body.subs(variable, inverse) - variable) == 0


def extract_function_definitions(segments: list[str]) -> dict[str, dict[str, Any]]:
    definitions: dict[str, dict[str, Any]] = {}
    for segment in segments:
        match = re.fullmatch(r"\s*([A-Za-z])\*?\(([A-Za-z])\)\s*=\s*(.+)", segment)
        if match:
            definitions[match.group(1)] = {"variable": match.group(2), "expression": match.group(3)}
    return definitions


def extract_piecewise_function_definitions(math_segments: list[str]) -> dict[str, dict[str, Any]]:
    definitions: dict[str, dict[str, Any]] = {}
    for segment in math_segments:
        parts = split_math_statements(segment)
        if len(parts) < 2:
            continue
        head = re.fullmatch(r"\s*([A-Za-z])\*?\(([A-Za-z])\)\s*=\s*(.+?)\s+if\s+(.+)", parts[0])
        if not head:
            continue
        branches: list[dict[str, str]] = [{"expression": head.group(3), "condition": head.group(4)}]
        for part in parts[1:]:
            branch = re.fullmatch(r"\s*(.+?)\s+if\s+(.+)", part)
            if branch:
                branches.append({"expression": branch.group(1), "condition": branch.group(2)})
        if len(branches) == len(parts):
            definitions[head.group(1)] = {"variable": head.group(2), "branches": branches}
    return definitions


def extract_binary_operator_definition(segments: list[str]) -> dict[str, Any] | None:
    for segment in segments:
        match = re.fullmatch(r"\s*([A-Za-z])\s+astop\s+([A-Za-z])\s*=\s*(.+)", segment)
        if match:
            return {
                "operator": "astop",
                "left_variable": match.group(1),
                "right_variable": match.group(2),
                "expression": match.group(3),
            }
    return None


def expand_tuple_equalities(constraints: list[str]) -> list[str]:
    expanded: list[str] = []
    for constraint in constraints:
        match = re.fullmatch(r"\s*\(([^()]*)\)\s*=\s*\(([^()]*)\)\s*", constraint)
        if not match:
            expanded.append(constraint)
            continue
        left = [item.strip() for item in match.group(1).split(",")]
        right = [item.strip() for item in match.group(2).split(",")]
        if len(left) == len(right) and len(left) > 1:
            expanded.extend(f"{a}={b}" for a, b in zip(left, right))
        else:
            expanded.append(constraint)
    return expanded


def extract_inverse_proportion_observation(text: str) -> dict[str, str] | None:
    relation = re.search(r"\b([a-z])\s+and\s+([a-z])\s+are\s+inversely\s+proportional", text)
    if not relation:
        return None
    left_name, right_name = relation.groups()
    first = re.search(
        rf"\b{left_name}\s*=\s*(-?\d+(?:/\d+)?)\s+when\s+{right_name}\s*=\s*(-?\d+(?:/\d+)?)",
        text,
    )
    query = re.search(
        rf"(?:value\s+of\s+|find\s+)({left_name}|{right_name})\s+when\s+({left_name}|{right_name})\s*=\s*(-?\d+(?:/\d+)?)",
        text,
    )
    if not first or not query or query.group(1) == query.group(2):
        return None
    return {
        "left": left_name,
        "right": right_name,
        "first_left": first.group(1),
        "first_right": first.group(2),
        "query": query.group(1),
        "second_known_name": query.group(2),
        "second_known": query.group(3),
    }


def extract_root_ratio(text: str) -> sp.Rational | None:
    match = re.search(
        r"(?:solutions|roots).*?ratio\s+(?:of\s+)?(\d+(?:/\d+)?)\s+to\s+(\d+(?:/\d+)?)",
        text,
    )
    if not match:
        return None
    right = sp.Rational(match.group(2))
    if right == 0:
        return None
    return sp.Rational(match.group(1)) / right


def solve_root_ratio_parameter(ir: SymbolicQueryIR, locals_map: dict[str, Any]) -> sp.Expr:
    root_variable = locals_map.setdefault(ir.variables[0], sp.Symbol(ir.variables[0], real=True))
    query_name = str(ir.parameters["query_parameter"])
    query_parameter = locals_map.setdefault(query_name, sp.Symbol(query_name, real=True))
    polynomial = polynomial_from_equation(str(ir.parameters["equation"]), root_variable, locals_map)
    if polynomial.degree() != 2:
        raise ValueError("root-ratio observation currently requires a quadratic relation")
    leading, linear, constant = polynomial.all_coeffs()
    ratio = sp.Rational(ir.parameters["ratio"])
    scale = sp.Symbol("__root_scale", real=True)
    scale_values = sp.solve(sp.Eq(ratio * scale**2, constant / leading), scale)
    candidates: list[sp.Expr] = []
    for scale_value in scale_values:
        parameter_values = sp.solve(
            sp.Eq(-(linear / leading), (ratio + 1) * scale_value),
            query_parameter,
        )
        candidates.extend(sp.simplify(value) for value in parameter_values if not value.free_symbols)
    if not candidates:
        raise ValueError("root ratio does not determine a finite parameter set")
    ordered = sorted(candidates, key=lambda item: float(sp.N(item, 30)))
    result = ordered[-1] if ir.parameters.get("selection") == "maximum" else ordered[0]
    return result


def solve_common_polynomial_root_projection(
    ir: SymbolicQueryIR,
    locals_map: dict[str, Any],
) -> list[sp.Expr]:
    root_name = str(ir.parameters["root_variable"])
    root = locals_map.setdefault(root_name, sp.Symbol(root_name))
    parameter_names = [str(item) for item in ir.parameters["parameter_variables"]]
    parameters = [locals_map.setdefault(name, sp.Symbol(name, real=True)) for name in parameter_names]
    equations = [parse_relation(item, locals_map) for item in ir.constraints if equation_operator(item)]
    if len(equations) < 2 or not parameters:
        raise ValueError("common-root projection requires two polynomial constraints and parameters")
    first = sp.Poly(sp.together(equations[0].lhs - equations[0].rhs), root)
    second = sp.Poly(sp.together(equations[1].lhs - equations[1].rhs), root)
    resultant = sp.factor(sp.resultant(first.as_expr(), second.as_expr(), root))
    if resultant == 0:
        raise ValueError("common-root constraints are algebraically dependent")
    target = parse_expression(ir.target, locals_map)
    factors = [factor for factor, _ in sp.factor_list(resultant)[1]]
    observed: set[sp.Expr] = set()
    for factor in factors:
        factor = sp.expand(factor)
        for parameter in parameters:
            for substitution in sp.solve(sp.Eq(factor, 0), parameter):
                value = sp.simplify(target.subs(parameter, substitution))
                if not value.free_symbols:
                    observed.add(value)
        polynomial = sp.Poly(factor, *parameters)
        if polynomial.total_degree() == 2:
            stationary = sp.solve(
                [sp.diff(factor, parameter) for parameter in parameters],
                parameters,
                dict=True,
            )
            hessian = sp.hessian(factor, parameters)
            if hessian.is_positive_definite is True:
                for assignment in stationary:
                    if set(assignment) == set(parameters) and sp.simplify(factor.subs(assignment)) == 0:
                        value = sp.simplify(target.subs(assignment))
                        if not value.free_symbols:
                            observed.add(value)
    if not observed:
        raise ValueError("resultant factors do not determine a finite target projection")
    return sorted(observed, key=sp.default_sort_key)


def solve_complex_root_moduli(ir: SymbolicQueryIR, locals_map: dict[str, Any]) -> list[sp.Expr]:
    name = str(ir.parameters["complex_variable"])
    variable = sp.Symbol(name)
    complex_locals = {**locals_map, name: variable}
    relation = parse_relation(ir.target, complex_locals)
    roots = sp.solve(relation, variable)
    if not roots or any(root.free_symbols for root in roots):
        raise ValueError("complex polynomial has no certified finite root set")
    for root in roots:
        if sp.simplify(relation.lhs.subs(variable, root) - relation.rhs.subs(variable, root)) != 0:
            raise ValueError("complex root failed substitution verification")
    moduli = {sp.simplify(sp.Abs(root)) for root in roots}
    if any(value.free_symbols for value in moduli):
        raise ValueError("complex modulus projection is not closed")
    return sorted(moduli, key=sp.default_sort_key)


def requested_inverse_function(text: str, definitions: dict[str, dict[str, Any]]) -> str | None:
    match = re.search(r"inverse\s+of\s+([a-z])(?:\s*\(|\b)", text)
    if match and match.group(1) in definitions:
        return match.group(1)
    return None


def extract_finite_function_graph(constraints: list[str]) -> dict[str, dict[str, str]]:
    graphs: dict[str, dict[str, str]] = {}
    for constraint in constraints:
        match = re.fullmatch(
            r"\s*([A-Za-z])\*?\(([+-]?\d+(?:/\d+)?)\)\s*=\s*([+-]?\d+(?:/\d+)?)\s*",
            constraint,
        )
        if match:
            graphs.setdefault(match.group(1), {})[match.group(2)] = match.group(3)
    return graphs


def instantiate_coordinate_constraints(
    text: str,
    constraints: list[str],
    equations: list[str],
) -> tuple[list[str], list[str]]:
    point = re.search(r"point\s*\(\s*([a-z])\s*,\s*([a-z])\s*\)\s+lies\s+on\s+the\s+line", text)
    if not point:
        return constraints, equations
    coordinate_equation = next(
        (item for item in equations if {"x", "y"} <= extract_symbols([item])),
        None,
    )
    if coordinate_equation is None:
        return constraints, equations
    x_name, y_name = point.groups()
    instantiated = re.sub(r"\bx\b", x_name, coordinate_equation)
    instantiated = re.sub(r"\by\b", y_name, instantiated)
    updated = [instantiated if item == coordinate_equation else item for item in constraints]
    return updated, [item for item in updated if equation_operator(item)]


def normalize_absolute_values(source: str) -> str:
    previous = None
    while previous != source:
        previous = source
        source = re.sub(r"\|([^|]+)\|", r"Abs(\1)", source)
    return source


def normalize_factorials(source: str) -> str:
    previous = None
    while source != previous:
        previous = source
        source = re.sub(r"(\([^()]+\)|[A-Za-z]|\d+)\s*!(?!\s*=)", r"factorial(\1)", source)
    return source


def evaluate_piecewise_call(
    source: str,
    name: str,
    definition: dict[str, Any],
    locals_map: dict[str, Any],
) -> sp.Expr:
    match = re.fullmatch(rf"\s*{re.escape(name)}\*?\((.+)\)\s*", source)
    if not match:
        raise ValueError("piecewise function query is not a direct application")
    argument = parse_expression(match.group(1), locals_map)
    variable = locals_map.setdefault(definition["variable"], sp.Symbol(definition["variable"], real=True))
    for branch in definition["branches"]:
        condition = parse_relation(branch["condition"], locals_map)
        truth = sp.simplify(condition.subs(variable, argument))
        if truth is sp.true or truth is True:
            return parse_expression(branch["expression"], locals_map).subs(variable, argument)
    raise ValueError("piecewise function argument satisfies no branch")


def evaluate_finite_function_expression(source: str, graphs: dict[str, dict[str, str]]) -> sp.Expr:
    compact = re.sub(r"\s+", "", source)

    def evaluate(term: str) -> str:
        direct = re.fullmatch(r"([A-Za-z])\*?\((.+)\)", term)
        inverse = re.fullmatch(r"([A-Za-z])\*\*\(-1\)\*\((.+)\)", term)
        match = inverse or direct
        if not match:
            return sp.sstr(sp.sympify(term))
        name, argument_source = match.groups()
        argument = evaluate(argument_source)
        graph = graphs.get(name)
        if not graph:
            raise ValueError(f"finite function {name} has no graph")
        if inverse:
            preimages = [key for key, value in graph.items() if sp.simplify(sp.sympify(value) - sp.sympify(argument)) == 0]
            if len(preimages) != 1:
                raise ValueError("finite inverse is not uniquely defined at the requested value")
            return preimages[0]
        if argument not in graph:
            raise ValueError("finite function is undefined at the requested value")
        return graph[argument]

    return sp.sympify(evaluate(compact))


def evaluate_binary_operator(source: str, parameters: dict[str, Any], locals_map: dict[str, Any]) -> sp.Expr:
    match = re.fullmatch(r"\s*(.+?)\s+astop\s+(.+?)\s*", source)
    if not match:
        raise ValueError("binary operator query has no application")
    left = parse_expression(match.group(1), locals_map)
    right = parse_expression(match.group(2), locals_map)
    left_symbol = locals_map.setdefault(parameters["left_variable"], sp.Symbol(parameters["left_variable"]))
    right_symbol = locals_map.setdefault(parameters["right_variable"], sp.Symbol(parameters["right_variable"]))
    body = parse_expression(parameters["expression"], locals_map)
    result = sp.simplify(body.subs({left_symbol: left, right_symbol: right}))
    if result.free_symbols:
        raise ValueError("binary operator application contains unbound symbols")
    return result


def sympy_locals(ir: SymbolicQueryIR) -> dict[str, Any]:
    names = extract_symbols([*ir.constraints, *ir.expressions, ir.target]) | set(ir.variables)
    locals_map: dict[str, Any] = {name: sp.Symbol(name, real=True) for name in names if name not in ir.definitions}
    locals_map.update({"sqrt": sp.sqrt, "sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "log": sp.log, "exp": sp.exp, "factorial": sp.factorial, "I": sp.I, "i": sp.I, "pi": sp.pi})
    return locals_map


def clean_math_segment(source: str) -> str:
    return source.strip().strip(".,;:?")


def split_math_statements(source: str) -> list[str]:
    return [part.strip() for part in re.split(r"\s*;\s*", source) if part.strip()]


def split_logical_relations(source: str) -> list[str]:
    parts = [part.strip() for part in re.split(r"\s+and\s+|\s+かつ\s+", source) if part.strip()]
    if len(parts) > 1 and all(relation_operator(part) for part in parts):
        return parts
    return [source]


def expression_requested_by_query(lower: str, expressions: list[str]) -> str:
    if not expressions:
        return ""
    # Display order is significant: in ``Determine T if C1,...,Cn`` the
    # observation precedes the constraints, while in ``compute T`` it is the
    # last (and usually only) non-relational span.
    if any(marker in lower for marker in ("determine", "求め", "値")):
        return expressions[0]
    return expressions[-1]


def is_closed_scalar_term(source: str) -> bool:
    names = extract_symbols([source])
    if names - {"i"}:
        return False
    try:
        expression = parse_expression(source, {"i": sp.I, "I": sp.I, "pi": sp.pi})
    except Exception:
        return False
    return not expression.free_symbols and not isinstance(expression, (sp.MatrixBase, sp.Set))


def extract_symbols(sources: list[str]) -> set[str]:
    ignored = {"sqrt", "sin", "cos", "tan", "log", "exp", "infinity"}
    return {name for source in sources for name in re.findall(r"\b[A-Za-z]\b", source) if name not in ignored}


def infer_symbol(source: str) -> str | None:
    names = extract_symbols([source])
    return sorted(names)[0] if names else None


def infer_query_variable(text: str, variables: list[str], source: str) -> str:
    match = re.search(r"(?:value|values)\s+of\s+([a-z])|solve\s+for\s+([a-z])", text)
    if match:
        return next(group for group in match.groups() if group)
    names = sorted(extract_symbols([source]))
    return names[0] if names else (variables[0] if variables else "x")


def last_expression(expressions: list[str]) -> str:
    return expressions[-1] if expressions else ""


def relation_operator(source: str) -> str | None:
    match = re.search(r"<=|>=|!=|=|<|>", source)
    return match.group(0) if match else None


def expand_chained_relation(source: str) -> list[str]:
    match = re.fullmatch(r"\s*(.+?)\s*(<=|>=|<|>)\s*(.+?)\s*(<=|>=|<|>)\s*(.+?)\s*", source)
    if not match:
        return [source]
    left, first_operator, middle, second_operator, right = match.groups()
    return [
        f"{left.strip()}{first_operator}{middle.strip()}",
        f"{middle.strip()}{second_operator}{right.strip()}",
    ]


def equation_operator(source: str) -> bool:
    return relation_operator(source) == "="


def inequality_operator(source: str) -> bool:
    return relation_operator(source) in {"<", ">", "<=", ">="}


def contains_word(text: str, word: str) -> bool:
    return bool(re.search(rf"\b{re.escape(word)}\b", text))


def query_requests_value(text: str) -> bool:
    return any(
        phrase in text
        for phrase in ("find", "what is", "evaluate", "compute", "calculate", "determine", "value", "求め", "計算")
    )


def query_requests_solution(text: str) -> bool:
    return any(phrase in text for phrase in ("solve", "possible values", "solutions", "value of", "values of", "解け")) or bool(
        re.search(r"\bfind\s+[a-z]\b", text)
    ) or (
        "方程式" in text and "求め" in text
    )


def query_requests_solution_set(text: str) -> bool:
    return any(
        phrase in text
        for phrase in ("what values", "for what", "interval notation", "all possible", "all real", "範囲", "すべて")
    )


def requested_function_set(
    text: str,
    definitions: dict[str, dict[str, Any]],
) -> tuple[str, str] | None:
    """Return a typed set observation over an explicitly defined function."""
    if not definitions:
        return None
    if "domain" in text or "定義域" in text:
        if any(marker in text for marker in ("smallest", "least", "minimum", "最小")):
            operator = "function_domain_minimum"
        elif any(marker in text for marker in ("largest", "greatest", "maximum", "最大")):
            operator = "function_domain_maximum"
        else:
            operator = "function_domain"
    elif "range" in text or "値域" in text:
        operator = "function_range"
    else:
        return None
    mentioned = [
        name
        for name in definitions
        if re.search(rf"\b{re.escape(name)}\b", text)
    ]
    if len(mentioned) != 1:
        return None
    return operator, mentioned[0]


def requests_integer_solution_aggregate(text: str) -> bool:
    return bool(
        re.search(
            r"\bsum\s+of\s+(?:all\s+)?integers?\b|"
            r"\bintegers?\b[^.?!]{0,80}\b(?:sum|total)\b",
            text,
        )
        or re.search(r"(?:すべての)?整数[^。]{0,60}(?:和|合計)", text)
    )


def root_aggregate_query(text: str) -> tuple[str, str] | None:
    if re.search(r"product of (?:the )?squares of (?:the )?(?:solutions|roots)", text):
        return "root_square_product", "Scalar"
    if re.search(
        r"sum of (?:all )?(?:the )?(?:(?:real|complex|distinct|possible)\s+)*(?:solutions|roots|values)",
        text,
    ):
        return "root_sum", "Scalar"
    if re.search(r"product of (?:all )?(?:the )?(?:solutions|roots)", text):
        return "root_product", "Scalar"
    return None


def expression_for_extremum(text: str, expressions: list[str]) -> str:
    if not any(word in text for word in ("minimum", "maximum", "minimize", "maximize", "最小", "最大")):
        return ""
    candidates = [item for item in expressions if re.search(r"[A-Za-z]", item) and any(op in item for op in ("+", "-", "*", "**", "/"))]
    return candidates[-1] if candidates else ""


def asks_for_extremizer(text: str) -> bool:
    return bool(re.search(r"what\s+(?:value|number)\s+of\s+[a-z]|which\s+[a-z]|[a-z]\s*の値", text))


def function_call_present(source: str, name: str) -> bool:
    return bool(re.search(rf"\b{re.escape(name)}\*?\(", source))


def extract_named_roots(text: str) -> list[str]:
    match = re.search(
        r"\b([a-z])\s*(?:,|and)\s*([a-z])\s+(?:are|be)\s+(?:the\s+)?(?:solutions|roots)",
        text,
    )
    return [match.group(1), match.group(2)] if match else []


def extract_known_solution_substitution(
    text: str,
    expressions: list[str],
    equation: str,
    query_variable: str,
) -> dict[str, str]:
    if not any(phrase in text for phrase in ("is a solution", "is a root", "を解にもつ", "が解")):
        return {}
    equation_variables = sorted(extract_symbols([equation]) - {query_variable})
    constants = [item for item in expressions if re.fullmatch(r"[+-]?\d+(?:/\d+)?", item)]
    if len(equation_variables) != 1 or not constants:
        return {}
    return {equation_variables[0]: constants[0]}
