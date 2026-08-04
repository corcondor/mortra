"""CEGIS-style induction of executable laws between two algebraic parents.

The candidate language contains typed polynomial expressions, not finished
problem templates.  Candidates are deduplicated semantically, eliminated
exactly, checked numerically, and tested by perturbing either parent.
"""

import json
import sys
from itertools import product

import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)


TRANSFORMS = standard_transformations + (convert_xor, implicit_multiplication_application)


def parse_polynomial(source: str, name: str):
    expression = parse_expr(source, transformations=TRANSFORMS, evaluate=True)
    symbols = sorted(expression.free_symbols, key=lambda symbol: symbol.name)
    if len(symbols) != 1:
        raise ValueError(f"{name} must contain exactly one variable")
    polynomial = sp.Poly(sp.together(expression), symbols[0], domain=sp.QQ)
    if polynomial.degree() < 1:
        raise ValueError(f"{name} must have positive degree")
    return polynomial


def quickspec_candidate_expressions(variables, max_depth: int, max_candidates: int):
    levels = [set(variables)]
    accepted = []
    seen = {sp.srepr(variable) for variable in variables}
    numeric_points = [
        tuple((sample + 2) * (-1 if (sample + index) % 3 == 0 else 1) for index in range(len(variables)))
        for sample in range(1, 6)
    ]
    signatures = set()
    for depth in range(1, max(2, max_depth + 1)):
        prior = set().union(*levels)
        generated = set()
        for left in prior:
            for right in prior:
                for expression in (left + right, left - right, left * right):
                    expression = sp.expand(expression)
                    if not all(expression.has(variable) for variable in variables):
                        continue
                    if sp.Poly(expression, *variables).total_degree() > max_depth + 1:
                        continue
                    key = sp.srepr(expression)
                    if key in seen:
                        continue
                    seen.add(key)
                    signature = tuple(
                        sp.expand(expression).subs(dict(zip(variables, point)))
                        for point in numeric_points
                    )
                    if signature in signatures:
                        continue
                    signatures.add(signature)
                    generated.add(expression)
        if not generated:
            break
        ordered = sorted(generated, key=lambda item: (sp.count_ops(item), len(str(item)), str(item)))
        levels.append(set(ordered[: max_candidates * 4]))
        accepted.extend(ordered)
        if len(accepted) >= max_candidates * 8:
            break
    return accepted


def cvc5_term_to_sympy(term, variables):
    import cvc5

    if term.isIntegerValue():
        return sp.Integer(term.getIntegerValue())
    if term.getNumChildren() == 0:
        if str(term) in variables:
            return variables[str(term)]
        raise ValueError(f"unsupported SyGuS atom: {term}")
    children = [cvc5_term_to_sympy(child, variables) for child in term]
    if term.getKind() == cvc5.Kind.ADD:
        return sp.Add(*children)
    if term.getKind() == cvc5.Kind.SUB:
        return children[0] - children[1]
    if term.getKind() == cvc5.Kind.MULT:
        return sp.Mul(*children)
    if term.getKind() == cvc5.Kind.NEG:
        return -children[0]
    raise ValueError(f"unsupported SyGuS operator: {term.getKind()}")


def sygus_candidate_expressions(variable_names, max_depth: int, max_candidates: int):
    """Enumerate typed terms with cvc5 SyGuS, falling back to QuickSpec-style enumeration."""
    try:
        import cvc5
        from cvc5 import FindSynthTarget, Kind

        manager = cvc5.TermManager()
        solver = cvc5.Solver(manager)
        solver.setOption("sygus", "true")
        solver.setOption("incremental", "true")
        solver.setLogic("LIA")
        integer = manager.getIntegerSort()
        input_variables = [manager.mkVar(integer, name) for name in variable_names]
        start = manager.mkVar(integer, "Start")
        grammar = solver.mkGrammar(input_variables, [start])
        grammar.addRules(start, [
            *input_variables,
            manager.mkInteger(-1),
            manager.mkInteger(0),
            manager.mkInteger(1),
            manager.mkTerm(Kind.ADD, start, start),
            manager.mkTerm(Kind.SUB, start, start),
            manager.mkTerm(Kind.MULT, start, start),
        ])
        symbolic_variables = {name: sp.Symbol(name) for name in variable_names}
        accepted = []
        examined = 0
        limit = max(256, max_candidates * 96)
        term = solver.findSynth(FindSynthTarget.ENUM, grammar)
        while not term.isNull() and examined < limit and len(accepted) < max_candidates * 12:
            examined += 1
            try:
                expression = sp.expand(cvc5_term_to_sympy(term, symbolic_variables))
                if all(expression.has(variable) for variable in symbolic_variables.values()):
                    polynomial = sp.Poly(expression, *symbolic_variables.values())
                    if polynomial.total_degree() <= max_depth + 1 and sp.count_ops(expression) <= max_depth * 3 + 2:
                        accepted.append(expression)
            except Exception:
                pass
            term = solver.findSynthNext()
        if accepted:
            return accepted, "cvc5-sygus-enum", examined
    except Exception:
        pass
    accepted = quickspec_candidate_expressions(
        [sp.Symbol(name) for name in variable_names], max_depth, max_candidates
    )
    return accepted, "quickspec-semantic-enumeration", len(accepted)


def egglog_equivalence_keys(expressions):
    """Collapse ring-equivalent candidate programs with an actual egglog e-graph."""
    try:
        from egglog import EGraph, Expr, StringLike, i64, i64Like, rewrite, ruleset, vars_

        class RingExpr(Expr):
            def __init__(self, value: i64Like) -> None: ...

            @classmethod
            def var(cls, name: StringLike) -> "RingExpr": ...

            def __add__(self, other: "RingExpr") -> "RingExpr": ...

            def __mul__(self, other: "RingExpr") -> "RingExpr": ...

        def convert(expression):
            if expression.is_Integer:
                return RingExpr(int(expression))
            if expression.is_Symbol:
                return RingExpr.var(str(expression))
            if expression.is_Add:
                values = [convert(argument) for argument in expression.args]
                return values[0] if len(values) == 1 else sum(values[1:], values[0])
            if expression.is_Mul:
                values = [convert(argument) for argument in expression.args]
                result = values[0]
                for value in values[1:]:
                    result = result * value
                return result
            if expression.is_Pow and expression.exp.is_Integer and int(expression.exp) >= 0:
                exponent = int(expression.exp)
                if exponent == 0:
                    return RingExpr(1)
                base = convert(expression.base)
                result = base
                for _ in range(exponent - 1):
                    result = result * base
                return result
            raise ValueError(f"unsupported e-graph expression: {expression}")

        runtime_expressions = [convert(sp.expand(expression)) for expression in expressions]
        a, b, c = vars_("a b c", RingExpr)
        i, j = vars_("i j", i64)
        egraph = EGraph()
        egraph.register(*runtime_expressions)
        egraph.run(ruleset(
            rewrite(a + b).to(b + a),
            rewrite(a * b).to(b * a),
            rewrite((a + b) + c).to(a + (b + c)),
            rewrite((a * b) * c).to(a * (b * c)),
            rewrite(RingExpr(i) + RingExpr(j)).to(RingExpr(i + j)),
            rewrite(RingExpr(i) * RingExpr(j)).to(RingExpr(i * j)),
        ) * 4)
        return [str(egraph.extract(expression)) for expression in runtime_expressions], True
    except Exception:
        return [sp.srepr(sp.expand(expression)) for expression in expressions], False


def sympy_to_cvc5(expression, manager, variables):
    import cvc5

    if expression.is_Integer:
        return manager.mkInteger(int(expression))
    if expression.is_Symbol:
        return variables[str(expression)]
    if expression.is_Add:
        return manager.mkTerm(cvc5.Kind.ADD, *[
            sympy_to_cvc5(argument, manager, variables) for argument in expression.args
        ])
    if expression.is_Mul:
        return manager.mkTerm(cvc5.Kind.MULT, *[
            sympy_to_cvc5(argument, manager, variables) for argument in expression.args
        ])
    if expression.is_Pow and expression.exp.is_Integer and int(expression.exp) >= 0:
        exponent = int(expression.exp)
        if exponent == 0:
            return manager.mkInteger(1)
        base = sympy_to_cvc5(expression.base, manager, variables)
        return base if exponent == 1 else manager.mkTerm(cvc5.Kind.MULT, *([base] * exponent))
    raise ValueError(f"unsupported cvc5 expression: {expression}")


def cvc5_all_parent_dependency(expression, variable_names):
    """Require machine-found witnesses that independently changing every parent can change the term."""
    try:
        import cvc5

        manager = cvc5.TermManager()
        integer = manager.getIntegerSort()
        variables = {name: manager.mkConst(integer, name) for name in variable_names}
        changed_variables = {name: manager.mkConst(integer, f"{name}_changed") for name in variable_names}

        def check(left_variables, right_variables):
            solver = cvc5.Solver(manager)
            solver.setLogic("QF_NIA")
            left = sympy_to_cvc5(expression, manager, left_variables)
            right = sympy_to_cvc5(expression, manager, right_variables)
            solver.assertFormula(manager.mkTerm(cvc5.Kind.DISTINCT, left, right))
            return solver.checkSat().isSat()

        dependencies = []
        for changed_name in variable_names:
            right = dict(variables)
            right[changed_name] = changed_variables[changed_name]
            dependencies.append(check(variables, right))
        return all(dependencies), True
    except Exception:
        return bool(all(sp.diff(expression, sp.Symbol(name)) != 0 for name in variable_names)), False


def monic_squarefree(expression, variable):
    polynomial = sp.Poly(sp.expand(expression), variable, domain=sp.QQ)
    if polynomial.is_zero or polynomial.degree() < 1:
        raise ValueError("elimination produced no finite nonconstant observable")
    return polynomial.sqf_part().monic()


def eliminate(polynomials, variables, observable):
    z = sp.Symbol("z")
    relation = z - observable
    for polynomial, variable in reversed(list(zip(polynomials, variables))):
        constraint = polynomial.as_expr().subs(polynomial.gens[0], variable)
        relation = sp.resultant(constraint, relation, variable)
    return monic_squarefree(relation, z)


def numeric_check(polynomials, variables, result, observable):
    z = sp.Symbol("z")
    root_sets = [
        [complex(value) for value in sp.nroots(polynomial.as_expr(), maxsteps=200)]
        for polynomial in polynomials
    ]
    result_expression = result.as_expr().subs(result.gens[0], z)
    tolerance = 1e-6
    for roots in product(*root_sets):
        value = complex(observable.subs(dict(zip(variables, roots))))
        residual = abs(complex(result_expression.subs(z, value)))
        if residual > tolerance * max(1.0, abs(value)) ** max(1, result.degree()):
            return False
    return True


def perturb(polynomial, amount):
    return sp.Poly(polynomial.as_expr() + amount, polynomial.gens[0], domain=sp.QQ)


def main():
    request = json.load(sys.stdin)
    polynomial_sources = request.get("polynomials") or [request["left"], request["right"]]
    if len(polynomial_sources) < 2:
        raise ValueError("at least two parent polynomial constraints are required")
    polynomials = [
        parse_polynomial(source, f"parent[{index}]")
        for index, source in enumerate(polynomial_sources)
    ]
    variable_names = [f"x{index}" for index in range(len(polynomials))]
    variables = [sp.Symbol(name) for name in variable_names]
    max_depth = max(1, min(int(request.get("max_depth", 3)), 4))
    max_candidates = max(1, min(int(request.get("max_candidates", 4)), 12))
    offset = max(0, int(request.get("offset", 0)))
    expressions, synthesis_engine, synthesis_terms_examined = sygus_candidate_expressions(
        variable_names, max_depth, max_candidates + offset + 8
    )
    registered_seed_laws = set()
    if len(variables) == 2:
        x, y = variables
        registered_seed_laws = {
            sp.srepr(sp.expand(expression))
            for expression in (x + y, x - y, y - x, x * y)
        }
    for registered_expression in request.get("registered_expressions", []):
        try:
            parsed = parse_expr(
                registered_expression,
                local_dict={name: variable for name, variable in zip(variable_names, variables)},
                transformations=TRANSFORMS,
                evaluate=True,
            )
            registered_seed_laws.add(sp.srepr(sp.expand(parsed)))
        except Exception:
            continue
    expressions = [
        expression for expression in expressions
        if sp.srepr(sp.expand(expression)) not in registered_seed_laws
    ]
    equivalence_keys, egglog_available = egglog_equivalence_keys(expressions)
    unique_expressions = []
    seen_equivalence_classes = set()
    for expression, equivalence_key in zip(expressions, equivalence_keys):
        if equivalence_key in seen_equivalence_classes:
            continue
        seen_equivalence_classes.add(equivalence_key)
        unique_expressions.append(expression)
    expressions = unique_expressions
    tested = rejected_elimination = rejected_numeric = rejected_ablation = rejected_duplicate = 0
    cvc5_checked = cvc5_rejected = 0
    cvc5_available = synthesis_engine == "cvc5-sygus-enum"
    results = []
    result_normal_forms = set()
    for observable in expressions[offset:]:
        if len(results) >= max_candidates:
            break
        tested += 1
        dependency_ok, dependency_used_cvc5 = cvc5_all_parent_dependency(observable, variable_names)
        cvc5_available = cvc5_available or dependency_used_cvc5
        cvc5_checked += 1
        if not dependency_ok:
            cvc5_rejected += 1
            continue
        try:
            result = eliminate(polynomials, variables, observable)
        except Exception:
            rejected_elimination += 1
            continue
        if not numeric_check(polynomials, variables, result, observable):
            rejected_numeric += 1
            continue
        result_key = sp.srepr(result.as_expr())
        if result_key in result_normal_forms:
            rejected_duplicate += 1
            continue
        try:
            changed_results = []
            for changed_index in range(len(polynomials)):
                changed_polynomials = list(polynomials)
                changed_polynomials[changed_index] = perturb(changed_polynomials[changed_index], 1)
                changed_results.append(eliminate(changed_polynomials, variables, observable))
        except Exception:
            rejected_ablation += 1
            continue
        if any(changed == result for changed in changed_results):
            rejected_ablation += 1
            continue
        result_normal_forms.add(result_key)
        results.append({
            "expression": sp.sstr(observable),
            "expression_tex": sp.latex(observable),
            "result": sp.latex(result.as_expr(), order="lex"),
            "degree_result": result.degree(),
            "operations": int(sp.count_ops(observable)),
            "exact": True,
            "numeric_check": True,
            "left_ablation": True,
            "right_ablation": True,
            "all_parent_ablation": True,
            "parent_arity": len(polynomials),
            "synthesis_engine": synthesis_engine,
            "equivalence_engine": "egglog" if egglog_available else "sympy-normal-form",
            "dependency_verifier": "cvc5-qf-nia" if dependency_used_cvc5 else "sympy-derivative-fallback",
        })
    json.dump({
        "left": sp.latex(polynomials[0].monic().as_expr(), order="lex"),
        "right": sp.latex(polynomials[1].monic().as_expr(), order="lex"),
        "polynomials": [sp.latex(polynomial.monic().as_expr(), order="lex") for polynomial in polynomials],
        "candidates": results,
        "telemetry": {
            "enumerated": len(expressions),
            "tested": tested,
            "rejected_elimination": rejected_elimination,
            "rejected_numeric": rejected_numeric,
            "rejected_ablation": rejected_ablation,
            "rejected_duplicate": rejected_duplicate,
            "cvc5_checked": cvc5_checked,
            "cvc5_rejected": cvc5_rejected,
            "cvc5_available": cvc5_available,
            "egglog_available": egglog_available,
            "equivalence_classes": len(seen_equivalence_classes),
            "synthesis_terms_examined": synthesis_terms_examined,
            "synthesis_engine": synthesis_engine,
            "parent_arity": len(polynomials),
            "certified": len(results),
        },
    }, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        json.dump({"error": f"{type(error).__name__}: {error}"}, sys.stdout, ensure_ascii=False)
        sys.exit(2)
