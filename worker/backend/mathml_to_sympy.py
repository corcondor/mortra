# -*- coding: utf-8 -*-
"""MathML → sympy。

mathexamtest.jp の問題文はネイティブ MathML で書かれている。
タグを剥いで平文にすると `\\log x \\leqq x-1` が `log x x - 1` になり、
不等号も積分区間も消える。意味を運んでいるのはタグの方だった。

MathML は木なので、LaTeX の正規表現より確実に読める。
分数・冪・根号・積分区間・総和・極限が構造として入っている。

    from mathml_to_sympy import parse_math_elements
    parse_math_elements(html)  → ['x > 0', 'log(x) <= x - 1', ...]
"""
from __future__ import annotations

import html as html_mod
import re
from xml.etree import ElementTree as ET

# 見えない演算子と、記号の対応
INVISIBLE = {'⁡', '⁢', '⁣', '⁤'}   # af, it, ic, plus
OPERATORS = {
    '≤': '<=', '≦': '<=', '≥': '>=', '≧': '>=',
    '≠': '!=', '×': '*', '⋅': '*', '÷': '/',
    '−': '-', '′': "'", '∞': 'oo',
    '→': '->', '⇒': '=>',
}
IDENTIFIERS = {
    'π': 'pi', '∞': 'oo', 'Γ': 'Gamma',
    'α': 'alpha', 'β': 'beta', 'γ': 'gamma', 'δ': 'delta',
    'θ': 'theta', 'λ': 'lamda', 'μ': 'mu', 'σ': 'sigma',
    'φ': 'phi', 'ω': 'omega', 'ρ': 'rho', 'τ': 'tau',
    'ε': 'epsilon', 'ζ': 'zeta', 'η': 'eta', 'κ': 'kappa',
    'ν': 'nu', 'ξ': 'xi', 'ψ': 'psi', 'χ': 'chi',
}
FUNCTIONS = {'sin', 'cos', 'tan', 'log', 'ln', 'exp', 'sinh', 'cosh', 'tanh'}

BIG = {'∫': 'Integral', '∑': 'Sum', '∏': 'Product'}


def _text(node) -> str:
    return ''.join(node.itertext()).strip()


def convert(node) -> str:
    """MathML の要素を sympy が読める文字列にする"""
    tag = node.tag.split('}')[-1]

    if tag in ('mspace', 'mtext', 'none', 'mpadded'):
        return ' '
    if tag == 'mn':
        return _text(node)
    if tag == 'mi':
        t = _text(node)
        if t in IDENTIFIERS:
            return IDENTIFIERS[t]
        if t in FUNCTIONS:
            return t
        return t
    if tag == 'mo':
        t = _text(node)
        if t in INVISIBLE:
            return '*' if t == '⁢' else ' '
        if t in BIG:
            return BIG[t]
        return OPERATORS.get(t, t)
    if tag in ('mrow', 'mstyle', 'math', 'mphantom', 'semantics'):
        return _join(node)
    if tag == 'mfrac':
        parts = [convert(c) for c in node]
        return f'(({parts[0]})/({parts[1]}))' if len(parts) == 2 else _join(node)
    if tag == 'msqrt':
        return f'sqrt({_join(node)})'
    if tag == 'mroot':
        parts = [convert(c) for c in node]
        return f'(({parts[0]})**(1/({parts[1]})))' if len(parts) == 2 else _join(node)
    if tag == 'msup':
        parts = [convert(c) for c in node]
        return f'(({parts[0]})**({parts[1]}))' if len(parts) == 2 else _join(node)
    if tag == 'msub':
        parts = [convert(c) for c in node]
        # 添字は名前の一部として扱う。a_1 と a_2 は別の量
        if len(parts) == 2:
            sub = re.sub(r'\W', '', parts[1])
            return f'{parts[0]}_{sub}' if sub else parts[0]
        return _join(node)
    if tag in ('munderover', 'msubsup'):
        parts = [convert(c) for c in node]
        if len(parts) == 3:
            head, lo, hi = parts
            if head in BIG.values():
                # 積分・総和の区間。中身は呼び出し側で足す
                return f'{head}@({lo})@({hi})'
            return f'{head}'
        return _join(node)
    if tag in ('munder', 'mover'):
        parts = [convert(c) for c in node]
        if len(parts) == 2 and parts[0].strip() == 'lim':
            m = re.match(r'\s*(\w+)\s*->\s*(.+)', parts[1])
            if m:
                return f'Limit@({m.group(1)})@({m.group(2)})'
        return parts[0] if parts else _join(node)
    if tag == 'mfenced':
        return f'({_join(node)})'
    return _join(node)


def _join(node) -> str:
    return ''.join(convert(c) for c in node)


def finish(expr: str) -> str:
    """Integral@(a)@(b) f dx のような中間形を sympy の呼び出しに直す"""
    s = expr

    # 積分：Integral@(lo)@(hi) body d x
    def integral(m):
        lo, hi, body, var = m.group(1), m.group(2), m.group(3), m.group(4)
        return f'Integral({body}, ({var}, {lo}, {hi}))'
    s = re.sub(r'Integral@\(([^()]*)\)@\(([^()]*)\)\s*(.+?)\s*d\s*([a-zA-Z]\w*)', integral, s)

    # 総和：Sum@(k=lo)@(hi) body
    def summation(m):
        lo, hi, body = m.group(1), m.group(2), m.group(3)
        v = lo.split('=')[0].strip() if '=' in lo else 'k'
        start = lo.split('=')[1].strip() if '=' in lo else lo
        return f'Sum({body}, ({v}, {start}, {hi}))'
    s = re.sub(r'Sum@\(([^()]*)\)@\(([^()]*)\)\s*(.+)', summation, s)

    # 極限：Limit@(x)@(a) body
    s = re.sub(r'Limit@\(([^()]*)\)@\(([^()]*)\)\s*(.+)', r'Limit(\3, \1, \2)', s)

    # 見えない乗算（&it;）が式の末尾や括弧の前後に残ると構文が壊れる。
    # sin(n*x)* のような形で実際に落ちていた。
    s = re.sub(r'\*\s*(?=[),\]]|$)', '', s)
    s = re.sub(r'(?<=[(,\[])\s*\*', '', s)
    s = re.sub(r'\*{3,}', '**', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def parse_math_elements(raw_html: str) -> list[str]:
    """HTML 中の <math> をすべて sympy 文字列にする。読めないものは飛ばす"""
    out: list[str] = []
    for chunk in re.findall(r'<math\b.*?</math>', raw_html, re.S):
        # 実体参照を文字に戻してから XML として読む
        text = html_mod.unescape(chunk)
        text = re.sub(r'<(\w+)([^>]*?)\s*/>', r'<\1\2></\1>', text)
        try:
            node = ET.fromstring(text)
        except ET.ParseError:
            continue
        try:
            expr = finish(convert(node))
        except Exception:
            continue
        if expr and not expr.isspace():
            out.append(expr)
    return out
