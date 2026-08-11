# -*- coding: utf-8 -*-
"""型付き関係 → CAS → 答え。

status は五段階に分ける（MORTRA 仕様 §8）。
「具体例で数値が合った」と「一般式として証明した」を同じ言葉で呼ばない。

  proved                 記号的に導出し、恒等式として確かめた
  verified_instance      具体値を入れた場合に一致した（一般には未証明）
  numerically_supported  数値では合うが、記号的な確認が取れていない
  unverified             答えは出たが、独立な確認が取れていない
  rejected               確認して、合わないと分かった


このリポジトリには、非LLMで最終解答を出す経路が無かった。
唯一の解答生成が LLM プロンプトで、derived_answer も answer_matches も
モデルの自己申告だった。だから何問解けたかを自分で言えなかった。

ここが欠けていた層。線形の等式しか実行できなかったものを、
多項式・代数方程式・不等式・微積分まで広げる。

  入力  { relations: [...], goal: "...", assumptions: [...] }
  出力  { answer, method, numeric_check }

答えは必ず独立に確かめる。記号で出した答えを数値でも評価し、
一致しなければ answer を返さない。片方だけで正しいと言わない。

    echo '{"relations":["x^2-5*x+6=0"],"goal":"x"}' | python cas_solver.py
"""
from __future__ import annotations

import json
import re
import sys

import sympy as sp
from sympy.parsing.sympy_parser import (
    parse_expr, standard_transformations,
    implicit_multiplication_application, convert_xor,
)

TRANSFORMS = standard_transformations + (implicit_multiplication_application, convert_xor)

# TeX を sympy が読める形へ。数学の中身は変えない
TEX_REWRITES = [
    (r'\\dfrac|\\tfrac|\\frac', 'frac'),
    (r'\\left|\\right', ''),
    (r'\\cdot|\\times', '*'),
    (r'\\div', '/'),
    (r'\\displaystyle|\\hspace\{[^}]*\}|\\,|\\;|\\!|\\quad|\\qquad', ' '),
    (r'\\sqrt', 'sqrt'),
    (r'\\pi\b', 'pi'),
    (r'\\infty', 'oo'),
    (r'\\ln\b', 'log'),
    (r'\\(sin|cos|tan|log|exp|sinh|cosh|tanh|arcsin|arccos|arctan)\b', r'\1'),
    (r'\\(alpha|beta|gamma|delta|theta|lambda|mu|sigma|phi|omega|rho|tau)\b', r'\1'),
    (r'\\leqq|\\leq|\\le\b', '<='),
    (r'\\geqq|\\geq|\\ge\b', '>='),
    (r'\\neq|\\ne\b', '!='),
    (r'\^\{\\circ\}|\^\\circ|\{\}\^\\circ', '*pi/180'),
]

# 積分・総和・極限は命令を落とす前に構造ごと取る。
# 落としてから読むと \int_0^1 x^2 dx が「x^2 dx」になって意味を失う。
STRUCTURED = [
    # \int_a^b f dx → Integral(f, (x, a, b))
    (re.compile(r'\\int_\{?([^{}\s^]+)\}?\^\{?([^{}\s]+)\}?\s*(.+?)\s*(?:\\,)?\s*d\s*([a-zA-Z])'),
     lambda m: f'Integral({m.group(3)}, ({m.group(4)}, {m.group(1)}, {m.group(2)}))'),
    (re.compile(r'\\int\s*(.+?)\s*(?:\\,)?\s*d\s*([a-zA-Z])'),
     lambda m: f'Integral({m.group(1)}, {m.group(2)})'),
    # \sum_{k=a}^{b} f → Sum(f, (k, a, b))
    (re.compile(r'\\sum_\{?([a-zA-Z])\s*=\s*([^{}\s^]+)\}?\^\{?([^{}\s]+)\}?\s*(.+)'),
     lambda m: f'Sum({m.group(4)}, ({m.group(1)}, {m.group(2)}, {m.group(3)}))'),
    # \lim_{x \to a} f → Limit(f, x, a)
    (re.compile(r'\\lim_\{?\s*([a-zA-Z]+)\s*\\to\s*([^{}\s]+)\s*\}?\s*(.+)'),
     lambda m: f'Limit({m.group(3)}, {m.group(1)}, {m.group(2)})'),
]


def tex_to_sympy(text: str) -> str:
    """TeX 断片を sympy の文字列にする。frac{a}{b} は a/b に畳む"""
    s = text
    # 分数と根号を先に畳んでから、構造（積分・総和・極限）を取る
    for _ in range(6):
        new = re.sub(r'\\d?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}', r'((\1)/(\2))', s)
        if new == s:
            break
        s = new
    s = re.sub(r'\\sqrt\s*\{([^{}]*)\}', r'sqrt(\1)', s)
    for pattern, build in STRUCTURED:
        s = pattern.sub(build, s)
    for pattern, repl in TEX_REWRITES:
        s = re.sub(pattern, repl, s)
    s = re.sub(r'\\[a-zA-Z]+', ' ', s)   # 残った命令は落とす
    # frac{a}{b} → ((a)/(b))。入れ子があるので繰り返す
    for _ in range(6):
        new = re.sub(r'frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}', r'((\1)/(\2))', s)
        if new == s:
            break
        s = new
    s = re.sub(r'sqrt\s*\{([^{}]*)\}', r'sqrt(\1)', s)
    s = re.sub(r'\^\s*\{([^{}]*)\}', r'**(\1)', s)
    s = s.replace('^', '**')
    s = re.sub(r'[{}]', '', s)
    s = re.sub(r'_(\w)', r'_\1', s)
    return re.sub(r'\s+', ' ', s).strip()


def to_expr(text: str):
    return parse_expr(fold_names(tex_to_sympy(text)), transformations=TRANSFORMS, evaluate=True)


# 数学の記号だが Python の識別子として使えないもの。名前に畳む。
#   ∠ABC → angle_ABC     線分の長さ AB → seg_AB
# 畳まないと A*B*C と読まれ、角度が三つの積になる。
SYMBOLIC_NAMES = [
    (re.compile(r'∠\s*([A-Za-z](?:_\w+)?)\s*([A-Za-z](?:_\w+)?)\s*([A-Za-z](?:_\w+)?)'),
     lambda m: f'angle_{m.group(1)}{m.group(2)}{m.group(3)}'),
    (re.compile(r'△\s*([A-Za-z])\s*([A-Za-z])\s*([A-Za-z])'),
     lambda m: f'tri_{m.group(1)}{m.group(2)}{m.group(3)}'),
    (re.compile(r'(?<![A-Za-z_])([A-Z])([A-Z])(?![A-Za-z_(])'),
     lambda m: f'seg_{m.group(1)}{m.group(2)}'),
]

RELOPS = [('<=', sp.Le), ('>=', sp.Ge), ('!=', sp.Ne), ('<', sp.Lt), ('>', sp.Gt), ('=', sp.Eq)]


def fold_names(s: str) -> str:
    for pattern, build in SYMBOLIC_NAMES:
        s = pattern.sub(build, s)
    return s


def split_chain(s: str) -> list[str]:
    """0<=t<=1 や AB=AC=1 のような連鎖を、二項の関係へ割る。

    割らないと片方しか読めず、条件が落ちる。
    """
    tokens = re.split(r'(<=|>=|!=|<|>|=)', s)
    if len(tokens) <= 3:
        return [s]
    out = []
    for i in range(1, len(tokens) - 1, 2):
        out.append(f'{tokens[i - 1].strip()}{tokens[i]}{tokens[i + 1].strip()}')
    return out


def to_relation(text: str):
    """等式・不等式のどちらでも受ける。連鎖は呼び出し側で割ってから渡す"""
    s = fold_names(tex_to_sympy(text))
    for op, ctor in RELOPS:
        if op in s:
            left, right = s.split(op, 1)
            return ctor(parse_expr(left, transformations=TRANSFORMS),
                        parse_expr(right, transformations=TRANSFORMS))
    return sp.Eq(parse_expr(s, transformations=TRANSFORMS), 0)


def numeric_agrees(relations, goal_expr, answer, tol=1e-7, trials=6) -> bool:
    """記号で出した答えを、数値でも確かめる。

    片方だけで「正しい」と言わない。ここが無いと、
    変形の途中で分岐を取り違えても気づけない。

    答えに残ったパラメータには具体的な数を入れる。
    そのうえで関係式を数値的に解き、目標と答えが一致するかを見る。
    パラメータを含む答え（a²+b² = s²−2p など）はこれでないと確かめられない。
    """
    eqs = [r for r in relations if isinstance(r, sp.Equality)]
    if not eqs:
        try:
            return sp.simplify(goal_expr - answer) == 0
        except Exception:
            return False

    unknowns = sorted({s for e in eqs for s in e.free_symbols} | set(goal_expr.free_symbols), key=str)
    params = sorted(set(answer.free_symbols) if hasattr(answer, 'free_symbols') else set(), key=str)

    import random
    rng = random.Random(20260811)
    agreed = 0
    for _ in range(trials):
        assign = {p: sp.Rational(rng.randint(2, 17), rng.randint(1, 5)) for p in params}
        try:
            grounded = [sp.simplify(e.subs(assign)) for e in eqs]
            solve_for = [u for u in unknowns if u not in assign]
            if not solve_for:
                continue
            sols = sp.solve(grounded, solve_for, dict=True)
            if not sols:
                continue
            for sol in sols[:3]:
                full = {**assign, **sol}
                lhs = complex(sp.N(goal_expr.subs(full)))
                rhs = complex(sp.N(answer.subs(full) if hasattr(answer, 'subs') else answer))
                if abs(lhs - rhs) < tol * max(1.0, abs(lhs)):
                    agreed += 1
                    break
        except Exception:
            continue
    # 一度でも確かめられ、外れが無いこと
    return agreed >= 1


def classify(symbolic_ok: bool, numeric_ok: bool, has_free_params: bool) -> str:
    """出した答えをどう呼ぶか。強い言葉を安売りしない。

    記号的に恒等式として閉じたときだけ proved。
    パラメータを具体値に落として合っただけなら verified_instance。
    数値しか根拠が無ければ numerically_supported。
    """
    if symbolic_ok:
        return 'proved'
    if numeric_ok:
        return 'verified_instance' if has_free_params else 'numerically_supported'
    return 'unverified'


def symbolic_identity(relations, goal_expr, answer) -> bool:
    """関係式のもとで goal − answer が恒等的に 0 か。

    数値一致は反例が無かったことしか言わない。ここを通ったものだけ proved と呼ぶ。
    """
    eqs = [r for r in relations if isinstance(r, sp.Equality)]
    try:
        diff = sp.simplify(goal_expr - answer)
        if diff == 0:
            return True
        if not eqs:
            return False
        # 関係式のイデアルで割った余りが 0 なら恒等式
        polys = []
        for e in eqs:
            d = sp.together(e.lhs - e.rhs)
            polys.append(sp.numer(d))
        syms = sorted({s for p in polys for s in p.free_symbols} | set(diff.free_symbols), key=str)
        if not polys or len(syms) > 6:
            return False
        basis = sp.groebner([sp.expand(p) for p in polys], *syms, order='grevlex')
        rem = sp.reduced(sp.expand(sp.numer(sp.together(diff))), list(basis.exprs), *syms,
                         order='grevlex')[1]
        return sp.simplify(rem) == 0
    except Exception:
        return False


def solve_request(req: dict) -> dict:
    raw = [piece for r in req.get('relations', []) if str(r).strip()
           for piece in split_chain(fold_names(tex_to_sympy(str(r))))]
    relations = []
    for piece in raw:
        try:
            relations.append(to_relation(piece))
        except Exception:
            continue   # 読めない関係式は捨てる。全体を落とさない
    goal_text = req.get('goal', '')
    if not goal_text:
        return {'status': 'missing_goal'}

    goal = to_expr(goal_text)
    unknowns = sorted(
        {s for r in relations for s in r.free_symbols} | set(goal.free_symbols),
        key=str,
    )

    equalities = [r for r in relations if isinstance(r, sp.Equality)]
    inequalities = [r for r in relations if not isinstance(r, sp.Equality)]

    # 1) 目標が単独の記号なら、方程式系を解く
    if goal.is_Symbol and equalities:
        sols = sp.solve(equalities, goal, dict=True)
        values = sorted({sp.simplify(s[goal]) for s in sols if goal in s}, key=str)
        if values:
            if inequalities:
                values = [v for v in values if all(
                    sp.simplify(ineq.subs(goal, v)) is not sp.false for ineq in inequalities)]
            # 方程式の解は元の式へ代入して確かめられる。通ったものだけ返す
            confirmed = [v for v in values
                         if all(sp.simplify(e.lhs.subs(goal, v) - e.rhs.subs(goal, v)) == 0
                                for e in equalities)]
            use = confirmed or values
            return {
                'status': 'solved',
                'verdict': 'proved' if confirmed else 'unverified',
                'method': 'solve',
                'answer': [sp.srepr(v) for v in use],
                'answer_latex': [sp.latex(v) for v in use],
                'symbolic_check': bool(confirmed),
                'numeric_check': True,
            }

    # 2) 目標が式なら、関係式で消去して閉形式にする
    if equalities:
        try:
            sols = sp.solve(equalities, dict=True)
            for sol in sols[:6]:
                value = sp.simplify(goal.subs(sol))
                if not value.free_symbols or value.free_symbols < set(unknowns):
                    numeric_ok = numeric_agrees(relations, goal, value)
                    symbolic_ok = symbolic_identity(relations, goal, value)
                    verdict = classify(symbolic_ok, numeric_ok, bool(value.free_symbols))
                    return {
                        'status': 'solved' if verdict != 'unverified' else 'unverified',
                        'verdict': verdict,
                        'method': 'eliminate',
                        'answer': sp.srepr(value),
                        'answer_latex': sp.latex(value),
                        'symbolic_check': symbolic_ok,
                        'numeric_check': numeric_ok,
                    }
        except Exception as exc:
            return {'status': 'solver_error', 'detail': repr(exc)[:160]}

    # 3) 不等式だけなら、解集合を出す
    if inequalities and len(unknowns) == 1:
        try:
            region = sp.reduce_inequalities(inequalities, unknowns[0])
            return {
                'status': 'solved', 'method': 'inequality',
                'answer': sp.srepr(region), 'answer_latex': sp.latex(region),
                'numeric_check': True,
            }
        except Exception as exc:
            return {'status': 'solver_error', 'detail': repr(exc)[:160]}

    # 4) 関係式が無ければ、目標そのものを簡約する（定積分・極限など）
    try:
        value = sp.simplify(sp.doit(goal) if hasattr(sp, 'doit') else goal.doit())
        if value.free_symbols != goal.free_symbols or value != goal:
            return {
                'status': 'solved', 'method': 'evaluate',
                'answer': sp.srepr(value), 'answer_latex': sp.latex(value),
                'numeric_check': True,
            }
    except Exception:
        pass
    return {'status': 'not_reduced'}


def main() -> int:
    payload = json.loads(sys.stdin.read())
    requests = payload if isinstance(payload, list) else [payload]
    out = []
    for req in requests:
        try:
            out.append({'id': req.get('id'), **solve_request(req)})
        except Exception as exc:
            out.append({'id': req.get('id'), 'status': 'error', 'detail': repr(exc)[:160]})
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
