# -*- coding: utf-8 -*-
"""Position-preserving MathML/discourse alignment tests.

These are structural tests: no benchmark IDs, source names, or expected-answer
lookup.  They exercise parse failure, equivalent insertions, changed targets,
and a negative case where guessing a later formula would be unsound.
"""
import io
import os
import sys

import sympy as sp

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'worker', 'backend'))
sys.path.insert(0, os.path.join(ROOT, 'worker', 'semantics'))

from mathml_ast import parse_math_document  # noqa: E402
from problem_ir import build_problem_ir, solve_with_routing  # noqa: E402

P = '⟦式⟧'
BAD = '<math><mrow></math>'


def ident(name: str) -> str:
    return f'<math><mi>{name}</mi></math>'


def equation(name: str, value: int) -> str:
    return (
        f'<math><mrow><mi>{name}</mi><mo>=</mo>'
        f'<mn>{value}</mn></mrow></math>'
    )


def sum_equation(left: str, right: str, value: int) -> str:
    return (
        f'<math><mrow><mi>{left}</mi><mo>+</mo><mi>{right}</mi>'
        f'<mo>=</mo><mn>{value}</mn></mrow></math>'
    )


passed = failed = 0


def check(name: str, ok: bool) -> None:
    global passed, failed
    if ok:
        passed += 1
    else:
        failed += 1
    print(f"{'  ok  ' if ok else '  NG  '} {name}")


print('\n■ source positions survive parse failure')
doc = parse_math_document([
    sum_equation('x', 'y', 5), equation('y', 3), BAD, ident('x')])
check('one slot per source formula', len(doc.slots) == 4)
check('failed formula remains an empty slot', doc.slots[2] is None)
check('executable expressions stay compact', len(doc.expressions) == 3)
check('unresolved slot is reported', doc.unresolved_slots == [2])

body = f'{P} と {P} を満たす。注記 {P}。{P} の値を求めよ。'
ir = build_problem_ir(body, doc.expressions, doc.slots)
check('goal keeps the fourth source position', ir.goal is not None and ir.goal.formula_index == 3)
check('goal binds to x, not the preceding failed formula', ir.goal_expression == sp.Symbol('x'))

print('\n■ execution and metamorphic invariance')
base = parse_math_document([
    sum_equation('x', 'y', 5), equation('y', 3), ident('x')])
base_body = f'{P} と {P} を満たす。{P} の値を求めよ。'
base_result = solve_with_routing(base_body, base.expressions, base.slots)
shifted_result = solve_with_routing(body, doc.expressions, doc.slots)
check('base problem is certified', base_result.get('verdict') == 'proved')
check('inserting an unparsed display does not change the answer',
      shifted_result.get('answer_latex') == base_result.get('answer_latex'))

print('\n■ counterfactual and negative cases')
changed = parse_math_document([
    sum_equation('x', 'y', 5), equation('y', 3), BAD, ident('y')])
changed_result = solve_with_routing(body, changed.expressions, changed.slots)
check('changing the mathematical target changes the answer',
      changed_result.get('answer_latex') != base_result.get('answer_latex'))

unsafe = parse_math_document([
    sum_equation('x', 'y', 5), equation('y', 3), BAD, ident('x')])
unsafe_body = f'{P} と {P} を満たす。{P} の値を求めよ。参考として {P} とする。'
unsafe_ir = build_problem_ir(unsafe_body, unsafe.expressions, unsafe.slots)
check('an unresolved goal is not rebound to a later expression',
      unsafe_ir.goal_expression is None and 'unparsed_goal_slot:2' in unsafe_ir.notes)

domain = parse_math_document([BAD, ident('n')])
domain_ir = build_problem_ir(f'注記 {P}。{P} を自然数とする。{P} を求めよ。',
                             domain.expressions, domain.slots)
check('type declarations remain attached after an earlier failure',
      sp.Gt(sp.Symbol('n'), 0) in domain_ir.assumptions)

print(f"\n{'─' * 60}")
print(f'MathML alignment {passed}/{passed + failed}')
raise SystemExit(1 if failed else 0)
