# -*- coding: utf-8 -*-
"""Discourse IR → Typed Problem IR → backend。

日本語本文を直接 CAS へ渡さない。必ずこの経路を通す。

  Japanese text → Discourse IR → Typed Problem IR → Backend-specific IR

backend は目標の演算子と制約の型で選ぶ。全部を sympy へ押し込まない。
未実装の backend は unsupported_backend として正しく棄却する。
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))

import sympy as sp  # noqa: E402

from discourse_ir import (  # noqa: E402
    DiscourseIR, GoalNode, GoalOperator, Sort, parse_discourse,
)

# 型 → sympy の仮定
SORT_ASSUMPTION = {
    Sort.NATURAL: lambda s: [sp.Gt(s, 0)],
    Sort.PRIME: lambda s: [sp.Gt(s, 1)],
    Sort.POSITIVE_REAL: lambda s: [sp.Gt(s, 0)],
    Sort.INTEGER: lambda s: [],
    Sort.REAL: lambda s: [],
    Sort.RATIONAL: lambda s: [],
    Sort.COMPLEX: lambda s: [],
}

# 目標の演算子 → backend
BACKEND_FOR_GOAL = {
    GoalOperator.COMPUTE_VALUE: 'cas',
    GoalOperator.SOLVE_EQUATION: 'cas',
    GoalOperator.EXPRESS_IN_TERMS: 'cas',
    GoalOperator.EVALUATE_LIMIT: 'cas',
    GoalOperator.EVALUATE_INTEGRAL: 'cas',
    GoalOperator.FIND_RANGE: 'inequality',
    GoalOperator.FIND_ALL: 'solution_set',
    GoalOperator.FIND_MAXIMUM: 'optimization',
    GoalOperator.FIND_MINIMUM: 'optimization',
    GoalOperator.COUNT: 'counting',
    GoalOperator.PROVE: 'proof',
    GoalOperator.SHOW_INEQUALITY: 'proof',
    GoalOperator.FIND_LOCUS: 'geometry_region',
    GoalOperator.FIND_AREA: 'geometry_region',
    GoalOperator.FIND_VOLUME: 'geometry_region',
    GoalOperator.FIND_PROBABILITY: 'probability',
    GoalOperator.CONSTRUCT: 'construction',
    GoalOperator.UNKNOWN: 'unsupported',
}

IMPLEMENTED_BACKENDS = {'cas', 'inequality', 'proof'}


@dataclass
class TypedProblemIR:
    expressions: list
    assumptions: list = field(default_factory=list)
    constraints: list = field(default_factory=list)
    goal: GoalNode | None = None
    goal_expression: object | None = None
    backend: str = 'unsupported'
    discourse: DiscourseIR | None = None
    notes: list[str] = field(default_factory=list)


def build_problem_ir(body: str, expressions: list) -> TypedProblemIR:
    """談話 IR と式の列から、実行できる形を作る"""
    ir = parse_discourse(body)
    notes: list[str] = list(ir.unresolved)

    # 前提。印字された関係式
    constraints = [e for e in expressions if isinstance(e, (sp.Equality, sp.Rel))]

    # 本文が言っている型を仮定にする
    assumptions = []
    for d in ir.domains:
        if d.formula_index is None or not (0 <= d.formula_index < len(expressions)):
            continue
        target = expressions[d.formula_index]
        if not getattr(target, 'is_Symbol', False):
            continue
        for a in SORT_ASSUMPTION.get(d.sort, lambda s: [])(target):
            assumptions.append(a)

    # 本文が言っている範囲を制約にする
    for iv in ir.intervals:
        if iv.formula_index is None or not (0 <= iv.formula_index < len(expressions)):
            continue
        target = expressions[iv.formula_index]
        if not getattr(target, 'free_symbols', None):
            continue
        try:
            if iv.lower is not None:
                bound = _bound_value(iv.lower, expressions)
                if bound is not None:
                    assumptions.append(sp.Gt(target, bound) if iv.lower_open
                                       else sp.Ge(target, bound))
            if iv.upper is not None:
                bound = _bound_value(iv.upper, expressions)
                if bound is not None:
                    assumptions.append(sp.Lt(target, bound) if iv.upper_open
                                       else sp.Le(target, bound))
        except Exception:
            notes.append('interval_conversion_failed')

    # 目標。信頼度の高い順
    goal = None
    goal_expr = None
    for candidate in sorted(ir.goals, key=lambda g: -g.confidence):
        if candidate.formula_index is not None and 0 <= candidate.formula_index < len(expressions):
            expr = expressions[candidate.formula_index]
            wants_relation = candidate.operator in (
                GoalOperator.PROVE, GoalOperator.SHOW_INEQUALITY)
            is_relation = isinstance(expr, (sp.Equality, sp.Rel))
            # 「示せ」の目標は関係式そのもの。式を探しに行くのが誤りだった
            if wants_relation != is_relation:
                continue
            goal, goal_expr = candidate, expr
            break
        if candidate.symbolic_target:
            goal = candidate
            break
    if goal is None and ir.goals:
        goal = ir.goals[0]

    backend = BACKEND_FOR_GOAL.get(goal.operator, 'unsupported') if goal else 'unsupported'
    if backend not in IMPLEMENTED_BACKENDS:
        notes.append(f'unsupported_backend:{backend}')

    return TypedProblemIR(
        expressions=expressions, assumptions=assumptions, constraints=constraints,
        goal=goal, goal_expression=goal_expr, backend=backend,
        discourse=ir, notes=notes)


def _bound_value(token: str, expressions: list):
    """境界の値。数字ならそのまま、⟦式⟧ ならその式"""
    from discourse_ir import PLACEHOLDER
    if token == PLACEHOLDER:
        return None
    try:
        return sp.Rational(token)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# A5 — routing で決まらないときに候補探索へ落とす
# ---------------------------------------------------------------------------

def solve_with_routing(body: str, expressions: list) -> dict:
    """Discourse IR で目標と backend を決め、決まらなければ候補探索へ後退する。

    A4（routing だけ）は A3b（候補探索だけ）より悪かった。
    routing が「この目標は Prove だから proof backend が要る」と正しく棄却すると、
    候補探索なら偶然当たっていた問題まで落ちる。

    棄却の質は上がったが点は下がる。両方を使う。
      1. Discourse が目標を決め、backend が実装済みならそれで解く
      2. 決まらない・未実装なら、候補探索に落とす（ただし本文の条件は使う）
    """
    from solve_from_ast import solve_with_text, solve_expressions

    ir = build_problem_ir(body, expressions)
    relations = list(ir.constraints)[:6] + list(ir.assumptions)[:4]

    # 1. routing で決まった場合
    if ir.goal is not None and ir.backend in IMPLEMENTED_BACKENDS             and ir.goal_expression is not None:
        try:
            if ir.backend == 'proof':
                from proof_backend import prove_relation
                out = prove_relation(ir.goal_expression, relations)
            else:
                out = solve_expressions(relations, ir.goal_expression)
        except Exception as exc:
            out = {'status': 'solver_error', 'detail': repr(exc)[:100]}
        if out.get('status') == 'solved':
            out['route'] = 'discourse'
            out['goal_operator'] = ir.goal.operator.value
            out['backend'] = ir.backend
            return out

    # 2. 後退。本文から得た仮定は捨てずに渡す
    try:
        out = solve_with_text(relations, expressions, body)
    except Exception as exc:
        out = {'status': 'solver_error', 'detail': repr(exc)[:100]}
    out['route'] = 'fallback'
    if ir.goal is not None:
        out['goal_operator'] = ir.goal.operator.value
        out['backend'] = ir.backend
        # routing が未実装 backend と言っていて、後退も解けなかったなら、
        # 「解けない」ではなく「その backend が無い」と記録する
        if out.get('status') != 'solved' and ir.backend not in IMPLEMENTED_BACKENDS:
            out['status'] = 'unsupported_backend'
            out['detail'] = ir.backend
    return out
