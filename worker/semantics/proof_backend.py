# -*- coding: utf-8 -*-
"""証明 backend。示すべき関係式が前提から従うかを判定する。

holdout 522問のうち Prove 目標が 100問ある。backend が無いだけで落ちていた。

判定は三段階に分ける。強い言葉を安売りしない。

  disproved              反例が見つかった。これは確実
  proved                 記号的に確かめられた
  numerically_supported  反例が見つからないが記号的な確認が無い

「反例が無かった」を「証明した」と呼ばない。
certified solve に数えるのは proved と disproved だけ。
"""
from __future__ import annotations

import itertools
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))

import sympy as sp  # noqa: E402

SAMPLES = 40
DOMAIN_POINTS = [
    sp.Rational(1, 3), sp.Rational(1, 2), sp.Integer(1), sp.Rational(3, 2),
    sp.Integer(2), sp.Integer(3), sp.Integer(5), sp.Rational(1, 10),
    sp.Rational(7, 2), sp.Integer(10),
]


def _satisfies(constraints, assignment) -> bool:
    """その割り当てが前提を満たすか"""
    for c in constraints:
        try:
            value = c.subs(assignment)
            if value is sp.false:
                return False
            if isinstance(value, sp.Rel) and value.free_symbols:
                return False   # まだ決まらない。使えない割り当て
        except Exception:
            return False
    return True


def find_counterexample(goal, constraints, seed: int = 20260812):
    """前提を満たし、目標を破る割り当てを探す。

    見つかれば反例。これは確実に「成り立たない」と言える。
    """
    symbols = sorted(goal.free_symbols, key=str)
    if not symbols or len(symbols) > 3:
        return None
    rng = random.Random(seed)
    pool = DOMAIN_POINTS + [sp.Rational(rng.randint(1, 30), rng.randint(1, 6))
                            for _ in range(SAMPLES)]
    for values in itertools.islice(itertools.product(pool, repeat=len(symbols)), 3000):
        assignment = dict(zip(symbols, values))
        if not _satisfies(constraints, assignment):
            continue
        try:
            value = goal.subs(assignment)
            if value is sp.false:
                return assignment
        except Exception:
            continue
    return None


def prove_relation(goal, constraints) -> dict:
    """関係式 goal が constraints のもとで成り立つか。

    等式は差が恒等的に 0 か。不等式は差の符号が決まるか。
    決まらなければ反例を探し、無ければ numerically_supported に留める。
    """
    # sympy は構築時に評価してしまうことがある。
    # x を positive と宣言していると Lt(x,0) はその場で False になる。
    # 「関係式でない」ではなく「既に真偽が決まった」として扱う。
    if goal is sp.true or goal is True:
        return {'status': 'solved', 'verdict': 'proved', 'method': 'evaluated',
                'answer_latex': '真', 'symbolic_check': True, 'numeric_check': True}
    if goal is sp.false or goal is False:
        return {'status': 'solved', 'verdict': 'disproved', 'method': 'evaluated',
                'answer_latex': '偽', 'symbolic_check': True, 'numeric_check': True}
    if not isinstance(goal, (sp.Equality, sp.Rel)):
        return {'status': 'goal_not_relation'}

    equalities = [c for c in constraints if isinstance(c, sp.Equality)]
    others = [c for c in constraints if not isinstance(c, sp.Equality)]

    # まず反例。見つかれば確実に否定できる
    counter = find_counterexample(goal, constraints)
    if counter is not None:
        return {'status': 'solved', 'verdict': 'disproved', 'method': 'counterexample',
                'answer_latex': '偽',
                'detail': ', '.join(f'{k}={v}' for k, v in list(counter.items())[:3]),
                'symbolic_check': True, 'numeric_check': True}

    # 等式なら、前提で消去して差が 0 になるか
    if isinstance(goal, sp.Equality):
        try:
            diff = sp.simplify(goal.lhs - goal.rhs)
            if diff == 0:
                return {'status': 'solved', 'verdict': 'proved', 'method': 'identity',
                        'answer_latex': '真', 'symbolic_check': True, 'numeric_check': True}
            if equalities:
                for sol in sp.solve(equalities, dict=True)[:4]:
                    if sp.simplify(diff.subs(sol)) == 0:
                        return {'status': 'solved', 'verdict': 'proved',
                                'method': 'substitution', 'answer_latex': '真',
                                'symbolic_check': True, 'numeric_check': True}
        except Exception as exc:
            return {'status': 'solver_error', 'detail': repr(exc)[:100]}

    # 不等式。前提のもとで否定が矛盾するか
    else:
        try:
            negation = goal.reversed if hasattr(goal, 'reversed') else None
            diff = sp.simplify(goal.lhs - goal.rhs)
            # 差が定数なら符号で決まる
            if not diff.free_symbols:
                holds = bool(goal.func(diff, 0))
                return {'status': 'solved',
                        'verdict': 'proved' if holds else 'disproved',
                        'method': 'constant_sign', 'answer_latex': '真' if holds else '偽',
                        'symbolic_check': True, 'numeric_check': True}
            # 一変数なら解集合を出して、前提の範囲を覆うか見る
            symbols = sorted(goal.free_symbols, key=str)
            if len(symbols) == 1 and others:
                try:
                    region = sp.reduce_inequalities([goal], symbols[0])
                    premise = sp.And(*others)
                    if sp.simplify(sp.Implies(premise, region)) is sp.true:
                        return {'status': 'solved', 'verdict': 'proved',
                                'method': 'region_inclusion', 'answer_latex': '真',
                                'symbolic_check': True, 'numeric_check': True}
                except (NotImplementedError, Exception):
                    # 解集合が出せない不等式は珍しくない（log x ≦ x−1 など）。
                    # 落ちずに、反例なしの段へ落とす
                    pass
            void(negation)
        except Exception as exc:
            return {'status': 'solver_error', 'detail': repr(exc)[:100]}

    # 反例が無く、記号的にも決まらない。証明したとは呼ばない。
    #
    # status を 'solved' にしない。二つ理由がある。
    #   1. 採点側が status=='solved' を「答えを出した」と読む。
    #      「反例が無い」を答えとして数えさせない。
    #   2. routing が status=='solved' で打ち切る。
    #      未証明で打ち切ると、候補探索が解けたかもしれない問題を潰す。
    return {'status': 'numerically_supported', 'verdict': 'numerically_supported',
            'method': 'no_counterexample',
            'answer_latex': '反例なし（未証明）',
            'symbolic_check': False, 'numeric_check': True}


def void(_):
    return None
