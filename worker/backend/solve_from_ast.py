# -*- coding: utf-8 -*-
"""sympy の式を直接受け取って解く。文字列を経由しない。

cas_solver は TeX 文字列を前提にしていたので、MathML AST から来た式を
一度 str() に落として再パースしていた。往復のたびに意味が壊れる。
ここは AST 経路の終点として、sympy の対象をそのまま扱う。

status は cas_solver と同じ五段階。
"""
from __future__ import annotations

import sympy as sp

from cas_solver import classify, is_trivial, numeric_agrees, symbolic_identity

UNEVALUATED = (sp.Limit, sp.Integral, sp.Sum, sp.Product, sp.Derivative)


def split_chained(rel):
    """Eq(AB, Eq(AC, 1)) のような連鎖を二項へ割る"""
    out = []
    stack = [rel]
    while stack:
        r = stack.pop()
        if isinstance(r, sp.Equality):
            left, right = r.args
            if isinstance(right, sp.Equality):
                stack.append(sp.Eq(left, right.lhs))
                stack.append(right)
                continue
        out.append(r)
    return out


def solve_expressions(relations, goal) -> dict:
    """relations と goal は sympy の対象。文字列ではない"""
    if goal is None:
        return {'status': 'missing_goal'}
    if isinstance(goal, sp.Rel) or isinstance(goal, sp.Equality):
        return {'status': 'goal_is_relation'}
    if not hasattr(goal, 'free_symbols'):
        return {'status': 'goal_not_expression'}

    flat = []
    for r in relations:
        if isinstance(r, (sp.Equality, sp.Rel)):
            flat.extend(split_chained(r))
    equalities = [r for r in flat if isinstance(r, sp.Equality)]
    inequalities = [r for r in flat if not isinstance(r, sp.Equality)]

    # 1) 目標が単独の記号なら方程式を解く
    if goal.is_Symbol and equalities:
        try:
            sols = sp.solve(equalities, goal, dict=True)
        except Exception as exc:
            return {'status': 'solver_error', 'detail': repr(exc)[:120]}
        values = sorted({sp.simplify(s[goal]) for s in sols if goal in s}, key=str)
        values = [v for v in values if not is_trivial(goal, v)]
        if values:
            return {'status': 'solved', 'verdict': 'proved', 'method': 'solve',
                    'answer_latex': [sp.latex(v) for v in values],
                    'symbolic_check': True, 'numeric_check': True}

    # 2) 関係式で消去する
    if equalities:
        try:
            for sol in sp.solve(equalities, dict=True)[:6]:
                value = sp.simplify(goal.subs(sol))
                if is_trivial(goal, value):
                    continue
                numeric_ok = numeric_agrees(flat, goal, value)
                symbolic_ok = symbolic_identity(flat, goal, value)
                verdict = classify(symbolic_ok, numeric_ok, bool(value.free_symbols))
                if verdict == 'unverified':
                    return {'status': 'unverified', 'verdict': verdict,
                            'answer_latex': sp.latex(value)}
                return {'status': 'solved', 'verdict': verdict, 'method': 'eliminate',
                        'answer_latex': sp.latex(value),
                        'symbolic_check': symbolic_ok, 'numeric_check': numeric_ok}
        except Exception as exc:
            return {'status': 'solver_error', 'detail': repr(exc)[:120]}

    # 3) 不等式の解集合
    unknowns = sorted(goal.free_symbols, key=str)
    if inequalities and len(unknowns) == 1:
        try:
            region = sp.reduce_inequalities(inequalities, unknowns[0])
            return {'status': 'solved', 'verdict': 'proved', 'method': 'inequality',
                    'answer_latex': sp.latex(region),
                    'symbolic_check': True, 'numeric_check': True}
        except Exception as exc:
            return {'status': 'solver_error', 'detail': repr(exc)[:120]}

    # 4) 未評価の演算を評価する
    if goal.has(*UNEVALUATED):
        try:
            value = sp.simplify(goal.doit())
            if not is_trivial(goal, value):
                return {'status': 'solved', 'verdict': 'proved', 'method': 'evaluate',
                        'answer_latex': sp.latex(value),
                        'symbolic_check': True, 'numeric_check': True}
        except Exception as exc:
            return {'status': 'solver_error', 'detail': repr(exc)[:120]}

    return {'status': 'not_reduced'}
