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


# 数学定数。変数として解かない。e = 0 < t < ∞ のような答えが実際に出た
MATH_CONSTANTS = {'e', 'i', 'pi', 'oo', 'E', 'I'}


def restates_premise(goal, answer, relations) -> bool:
    """答えが前提の言い換えでしかないか。

    Eq(a_1, α) を α について解くと a_1 が返る。正しいが、問題の答えではない。
    導いた Eq(goal, answer) が入力の関係式そのものなら、何も進んでいない。

    p_n = p_n 型は is_trivial が弾くが、別名への言い換え（α = a_1）は弾けなかった。
    """
    try:
        derived = sp.simplify(goal - answer)
        for r in relations:
            if not isinstance(r, sp.Equality):
                continue
            diff = sp.simplify(r.lhs - r.rhs)
            if diff == 0:
                continue
            # 定数倍を許して比べる。2x = 2y と x = y は同じ主張
            ratio = sp.simplify(derived / diff) if diff != 0 else None
            if ratio is not None and ratio.is_number and ratio != 0:
                return True
            if sp.simplify(derived + diff) == 0 or derived == diff:
                return True
    except Exception:
        return False
    return False


def usable_goal(goal) -> bool:
    """目標として意味があるか。数学定数や単独の数は目標にならない"""
    if goal is None or not hasattr(goal, 'free_symbols'):
        return False
    if goal.is_Number:
        return False
    names = {str(sym) for sym in goal.free_symbols}
    if goal.is_Symbol and names & MATH_CONSTANTS:
        return False
    return True


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
    if not usable_goal(goal):
        return {'status': 'goal_not_meaningful'}

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
        values = [v for v in values
                  if not is_trivial(goal, v) and not restates_premise(goal, v, flat)]
        if values:
            return {'status': 'solved', 'verdict': 'proved', 'method': 'solve',
                    'answer_latex': [sp.latex(v) for v in values],
                    'symbolic_check': True, 'numeric_check': True}

    # 2) 関係式で消去する
    if equalities:
        try:
            for sol in sp.solve(equalities, dict=True)[:6]:
                value = sp.simplify(goal.subs(sol))
                if is_trivial(goal, value) or restates_premise(goal, value, flat):
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

    # 3) 不等式の解集合。
    #    目標そのものが未知数のときだけ。log(r) を目標にして r の範囲を返すのは、
    #    別の量の答えを目標の答えとして出していることになる。実際にそうなっていた。
    if inequalities and goal.is_Symbol:
        relevant = [q for q in inequalities if goal in q.free_symbols]
        # 前提が一本だけなら、解いても前提を言い直すだけ。
        # α > 1 から α の範囲を出して「1 < α < ∞」と答えるのは答えではない。実際そうなっていた。
        if len(relevant) >= 2:
            try:
                region = sp.reduce_inequalities(relevant, goal)
                plain = sp.And(*relevant)
                if sp.simplify(region) == sp.simplify(plain):
                    return {'status': 'not_reduced', 'detail': '前提の連言をそのまま返しただけ'}
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


# ---------------------------------------------------------------------------
# 目標候補を一つに決め打ちしない
# ---------------------------------------------------------------------------

def goal_candidates(expressions, limit: int = 14):
    """目標になりうる式を、有望な順に並べる。

    これまで「最後の非関係式」だけを試していた。外したらその問題は落ちる。
    入試の問題文には10〜15個の式が印字されていて、そのどれかが問われている。
    全部試して、検証を通ったものを採る。

    順序は「求められていそうな度合い」。未評価の演算を含むもの、
    複合的なもの、記号が少ないものを先に見る。
    """
    plain = [e for e in expressions
             if not isinstance(e, (sp.Equality, sp.Rel)) and hasattr(e, 'free_symbols')]
    scored = []
    for e in plain:
        score = 0
        if e.has(*UNEVALUATED):
            score += 100          # 積分・総和・極限は明らかに「求めよ」の対象
        ops = sp.count_ops(e)
        score += min(ops, 20) * 2  # 複合的な式ほど問われやすい
        if e.is_Symbol:
            score -= 5             # 単独の記号は答えそのものではないことが多い
        if e.is_Number:
            score -= 50            # 定数は目標にならない
        if e.is_Symbol and str(e) in MATH_CONSTANTS:
            score -= 100           # e や i は変数ではない
        scored.append((score, ops, e))
    scored.sort(key=lambda t: (-t[0], -t[1]))
    return [e for _, _, e in scored[:limit]]


def solve_best(relations, expressions, limit: int = 14) -> dict:
    """候補を順に試し、最も強い検証を通ったものを返す。

    強さの順は proved > verified_instance > numerically_supported。
    一つも通らなければ、最後に見た状態を返す（棄権の理由が残るように）。
    """
    rank = {'proved': 3, 'verified_instance': 2, 'numerically_supported': 1}
    best = {'status': 'not_reduced'}
    best_rank = -1
    tried = 0
    for goal in goal_candidates(expressions, limit):
        tried += 1
        try:
            r = solve_expressions(relations, goal)
        except Exception as exc:
            best = {'status': 'solver_error', 'detail': repr(exc)[:100]}
            continue
        if r.get('status') != 'solved':
            if best_rank < 0:
                best = r
            continue
        score = rank.get(r.get('verdict', ''), 0)
        if score > best_rank:
            best_rank = score
            best = {**r, 'goal_latex': sp.latex(goal), 'tried': tried}
            if score == 3:
                break     # proved が出たらそれ以上探さない
    best['candidates_tried'] = tried
    return best


# ---------------------------------------------------------------------------
# 問題文が「何を求めよ」と言っている場所から目標を決める
# ---------------------------------------------------------------------------

import re as _re

# 何を問うているか。語ごとに、直前の式が目標になりやすい
ASK_MARKERS = [
    (r'の?範囲を求めよ', 'range'),
    (r'を求めよ|を求めなさい|求めよ', 'value'),
    (r'を用いて表せ|で表せ|表しなさい', 'express'),
    (r'の値は', 'value'),
    (r'を計算せよ', 'value'),
    (r'を示せ|を証明せよ', 'prove'),
]

PLACEHOLDER = '⟦式⟧'


def goals_from_text(
        body: str, expressions: list, window: int = 4,
        expression_slots: list | None = None):
    """本文の「求めよ」の直前にある式を、目標の候補として順に返す。

    収集器が <math> を ⟦式⟧ に置き換えているので、
    本文中の ⟦式⟧ の個数と expressions の添字が一対一に対応する。

    式だけを見て「最後の非関係式」を目標にしていたのが、点を落としていた最大の原因。
    どれが問われているかは本文が言っている。
    """
    if not body or PLACEHOLDER not in body:
        return []
    slots = expressions if expression_slots is None else expression_slots
    picks: list[int] = []
    for pattern, _kind in ASK_MARKERS:
        for m in _re.finditer(pattern, body):
            before = body[:m.start()]
            index = before.count(PLACEHOLDER) - 1
            # 「求めよ」の直前から遡って数個を候補にする
            for k in range(index, max(-1, index - window), -1):
                if 0 <= k < len(slots) and slots[k] is not None and k not in picks:
                    picks.append(k)
    return [slots[i] for i in picks]


def solve_with_text(
        relations, expressions, body: str, limit: int = 14,
        expression_slots: list | None = None) -> dict:
    """本文の指示を先に使い、駄目なら式の形だけで選ぶ。

    本文が言っていることを無視して式の形だけで当てにいくのは、
    情報を捨てている。まず本文の指示を使う。
    """
    rank = {'proved': 3, 'verified_instance': 2, 'numerically_supported': 1}
    best = {'status': 'not_reduced'}
    best_rank = -1
    tried = 0
    seen: set[str] = set()

    text_goals = goals_from_text(
        body, expressions, expression_slots=expression_slots)
    ordered = text_goals + goal_candidates(expressions, limit)
    for goal in ordered:
        key = sp.srepr(goal) if hasattr(goal, 'free_symbols') else str(goal)
        if key in seen:
            continue
        seen.add(key)
        tried += 1
        if tried > limit + 6:
            break
        try:
            r = solve_expressions(relations, goal)
        except Exception as exc:
            if best_rank < 0:
                best = {'status': 'solver_error', 'detail': repr(exc)[:100]}
            continue
        if r.get('status') != 'solved':
            if best_rank < 0:
                best = r
            continue
        score = rank.get(r.get('verdict', ''), 0)
        if score > best_rank:
            best_rank = score
            best = {**r, 'goal_latex': sp.latex(goal), 'from_text': goal in text_goals}
            if score == 3:
                break
    best['candidates_tried'] = tried
    return best


# ---------------------------------------------------------------------------
# 本文の日本語から条件を取る
# ---------------------------------------------------------------------------

def constraints_from_text(
        body: str, expressions: list, expression_slots: list | None = None) -> list:
    """本文に日本語で書かれた条件を、sympy の仮定へ落とす。

    167問中78問には印字された等式が一本も無い。条件は日本語で書かれている。
      「nを自然数とする」「0<t<1を満たす実数」「三角形ABCにおいて」
    式だけを見ていると、これらを全部捨てていた。

    ここで拾うのは、solve が使える形の条件だけ。
    拾えないものは黙って捨てる（誤読するより棄権する）。
    """
    if not body:
        return []
    slots = expressions if expression_slots is None else expression_slots
    out = []
    # 変数名は本文には出ない。⟦式⟧ の中にある。
    # 「⟦式⟧ を自然数とする」の ⟦式⟧ が何番目かを数えて、その式を見る。
    for m in _re.finditer(
            r'⟦式⟧\s*(?:を|は|が)\s*[^。⟦]{0,12}?(自然数|正の整数|整数|正の実数|正の数|実数)',
            body):
        index = body[:m.start()].count(PLACEHOLDER)
        if not (0 <= index < len(slots)):
            continue
        target = slots[index]
        if not (hasattr(target, 'is_Symbol') and target.is_Symbol):
            continue
        kind = m.group(1)
        if kind in ('自然数', '正の整数', '正の実数', '正の数'):
            out.append(sp.Gt(target, 0))

    # 「0 < ⟦式⟧ < 1」のように式として印字されている条件は
    # すでに relations に入っているので、ここでは拾わない（二重に入れない）
    return out


def solve_full(
        relations, expressions, body: str, limit: int = 14,
        expression_slots: list | None = None) -> dict:
    """本文の条件と指示を両方使って解く。現在の入口"""
    extra = constraints_from_text(body, expressions, expression_slots)
    merged = list(relations) + [c for c in extra if c not in relations]
    r = solve_with_text(
        merged[:8], expressions, body, limit,
        expression_slots=expression_slots)
    r['text_constraints'] = len(extra)
    return r
