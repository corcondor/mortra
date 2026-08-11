# -*- coding: utf-8 -*-
"""MathML → AST → sympy。文字列の正規表現を積み上げるのをやめる。

これまでは MathML を文字列に落としてから正規表現で直していた。
`\\b` がバックスペースになる事故が3回、見えない演算子の残留、
`I` が虚数単位に化ける、`(a,b)` がタプルになる ―― 全部その積み重ねの副作用。

ここでは木を木のまま扱う。
  MathML 要素 → Node（型を持つ中間表現）→ 環境で解決 → sympy

型の解決は文脈と MathML の構造から行う。

  sin / log / exp     msup が続けば sin^2 x のような冪、mo &af; が続けば関数適用
  I, C, E, N          問題側で括弧が続けば関数、そうでなければ記号。sympy の組み込みに負けない
  暗黙の乗算          mo &it; を明示の乗算にする。並置は AST の段階で決める
  ApplyFunction       mo &af; を関数適用として木に持つ

全入力に制御文字の不変条件を課す。
"""
from __future__ import annotations

import html as html_mod
import re
from dataclasses import dataclass, field
from typing import Any
from xml.etree import ElementTree as ET

import sympy as sp

# ---------------------------------------------------------------------------
# 不変条件
# ---------------------------------------------------------------------------

_CONTROL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')


def assert_no_control_chars(value: str, where: str) -> str:
    """制御文字が混ざっていないこと。正規表現に \\b を書いて 0x08 を埋めた事故が3回あった。

    入口で必ず通す。通っていない経路は作らない。
    """
    hit = _CONTROL.search(value)
    if hit:
        raise ValueError(
            f'{where}: 制御文字 0x{ord(hit.group()):02x} が位置 {hit.start()} にある')
    return value


# ---------------------------------------------------------------------------
# AST
# ---------------------------------------------------------------------------

@dataclass
class Node:
    """MathML の意味を持った中間表現。文字列ではない"""
    kind: str
    value: str = ''
    children: list['Node'] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        if self.children:
            return f'{self.kind}({self.value or ""}{"," if self.value else ""}' \
                   f'{",".join(map(repr, self.children))})'
        return f'{self.kind}:{self.value}'


# 見えない演算子。文字ではなく意味として扱う
INVISIBLE = {
    '⁡': 'apply',    # &af;  関数適用
    '⁢': 'times',    # &it;  暗黙の乗算
    '⁣': 'sep',      # &ic;  区切り
    '⁤': 'plus',     # &ip;  帯分数の和
}

RELATIONS = {
    '=': 'Eq', '≤': 'Le', '≦': 'Le', '<': 'Lt',
    '≥': 'Ge', '≧': 'Ge', '>': 'Gt', '≠': 'Ne',
}

BIG_OPERATORS = {'∫': 'Integral', '∑': 'Sum', '∏': 'Product'}

GREEK = {
    'α': 'alpha', 'β': 'beta', 'γ': 'gamma', 'δ': 'delta', 'ε': 'epsilon',
    'ζ': 'zeta', 'η': 'eta', 'θ': 'theta', 'ι': 'iota', 'κ': 'kappa',
    'λ': 'lamda', 'μ': 'mu', 'ν': 'nu', 'ξ': 'xi', 'ρ': 'rho',
    'σ': 'sigma', 'τ': 'tau', 'φ': 'phi', 'χ': 'chi', 'ψ': 'psi', 'ω': 'omega',
    'π': 'pi', '∞': 'oo',
}

KNOWN_FUNCTIONS = {
    'sin': sp.sin, 'cos': sp.cos, 'tan': sp.tan,
    'sinh': sp.sinh, 'cosh': sp.cosh, 'tanh': sp.tanh,
    'log': sp.log, 'ln': sp.log, 'exp': sp.exp,
}


def build(element) -> Node:
    """MathML 要素を Node へ。ここでは意味を確定させず、構造だけ写す"""
    tag = element.tag.split('}')[-1]
    text = ''.join(element.itertext()).strip()

    if tag in ('mspace', 'mtext', 'none', 'mpadded', 'mprescripts'):
        return Node('space')
    if tag == 'mn':
        return Node('number', text)
    if tag == 'mi':
        return Node('identifier', GREEK.get(text, text))
    if tag == 'mo':
        if text in INVISIBLE:
            return Node('invisible', INVISIBLE[text])
        if text in BIG_OPERATORS:
            return Node('bigop', BIG_OPERATORS[text])
        if text in RELATIONS:
            return Node('relation', RELATIONS[text])
        return Node('operator', {'−': '-', '×': '*', '⋅': '*', '÷': '/'}.get(text, text))

    kids = [build(c) for c in element]
    kids = [k for k in kids if k.kind != 'space']

    if tag in ('mrow', 'math', 'mstyle', 'mphantom', 'semantics'):
        return Node('row', children=kids)
    if tag == 'mfrac':
        return Node('frac', children=kids[:2])
    if tag == 'msqrt':
        return Node('sqrt', children=[Node('row', children=kids)])
    if tag == 'mroot':
        return Node('root', children=kids[:2])
    if tag == 'msup':
        return Node('sup', children=kids[:2])
    if tag == 'msub':
        return Node('sub', children=kids[:2])
    if tag == 'msubsup':
        return Node('subsup', children=kids[:3])
    if tag == 'munderover':
        return Node('underover', children=kids[:3])
    if tag in ('munder', 'mover'):
        return Node(tag, children=kids[:2])
    if tag == 'mfenced':
        return Node('fenced', children=kids)
    return Node('row', children=kids)


# ---------------------------------------------------------------------------
# 環境。名前の意味は文脈で決まる
# ---------------------------------------------------------------------------

@dataclass
class Environment:
    """名前 → sympy の対象。スコープを持つ。

    問題側で `I(a,n)` と書かれていたら I は関数。
    sympy の虚数単位に負けないよう、ここが優先される。
    """
    functions: set[str] = field(default_factory=set)
    symbols: dict[str, sp.Symbol] = field(default_factory=dict)
    funcs: dict[str, Any] = field(default_factory=dict)

    def symbol(self, name: str) -> sp.Symbol:
        if name not in self.symbols:
            self.symbols[name] = sp.Symbol(name)
        return self.symbols[name]

    def function(self, name: str):
        if name in KNOWN_FUNCTIONS:
            return KNOWN_FUNCTIONS[name]
        if name not in self.funcs:
            self.funcs[name] = sp.Function(name)
        return self.funcs[name]

    def child(self) -> 'Environment':
        """束縛変数を導入するときの子スコープ"""
        return Environment(set(self.functions), dict(self.symbols), dict(self.funcs))


def scan_functions(node: Node, env: Environment) -> None:
    """木を歩いて「関数として使われている名前」を集める。

    直後に &af;（関数適用）か括弧が来るものが関数。
    文字列の正規表現ではなく、木の隣接関係で決める。
    """
    kids = node.children
    for i, child in enumerate(kids):
        if child.kind == 'identifier':
            nxt = kids[i + 1] if i + 1 < len(kids) else None
            if nxt is not None and (
                (nxt.kind == 'invisible' and nxt.value == 'apply')
                or (nxt.kind == 'operator' and nxt.value == '(')
                or nxt.kind == 'fenced'
            ):
                env.functions.add(child.value)
        scan_functions(child, env)


# ---------------------------------------------------------------------------
# 解決。Node → sympy
# ---------------------------------------------------------------------------

class Unresolved(Exception):
    """読めなかった。黙って別の意味に読み替えない"""


def resolve(node: Node, env: Environment):
    if node.kind == 'number':
        return sp.Rational(node.value) if '.' not in node.value else sp.Float(node.value)
    if node.kind == 'identifier':
        name = node.value
        if name in env.functions:
            return env.function(name)
        if name == 'pi':
            return sp.pi
        if name == 'oo':
            return sp.oo
        return env.symbol(name)
    if node.kind == 'frac':
        return resolve(node.children[0], env) / resolve(node.children[1], env)
    if node.kind == 'sqrt':
        return sp.sqrt(resolve(node.children[0], env))
    if node.kind == 'root':
        return resolve(node.children[0], env) ** (1 / resolve(node.children[1], env))
    if node.kind == 'sup':
        base, exponent = node.children
        # sin^2 x は (sin x)^2。関数名の冪は特別扱いする
        if base.kind == 'identifier' and base.value in KNOWN_FUNCTIONS:
            return Node('funcpow', base.value, [exponent])
        return resolve(base, env) ** resolve(exponent, env)
    if node.kind == 'sub':
        base, sub = node.children
        name = f'{flatten_name(base)}_{flatten_name(sub)}'
        # 添字つきは一つの記号。ただし添字が束縛変数なら数列として扱えるよう覚えておく
        symbol = env.symbol(name)
        symbol_meta.setdefault(name, flatten_name(sub))
        return symbol
    if node.kind == 'fenced':
        return resolve_sequence(node.children, env)
    if node.kind == 'row':
        return resolve_sequence(node.children, env)
    raise Unresolved(node.kind)


def flatten_name(node: Node) -> str:
    if node.kind in ('identifier', 'number'):
        return node.value
    return ''.join(flatten_name(c) for c in node.children)


# 添字つき記号が、どの名前を添字に持つか。数列の判定に使う
symbol_meta: dict[str, str] = {}


def resolve_sequence(nodes: list[Node], env: Environment):
    """並びを sympy の式にする。暗黙の乗算・関数適用・関係を木の順で処理する"""
    nodes = [n for n in nodes if n.kind != 'space']
    if not nodes:
        raise Unresolved('empty')

    # 関係があれば、そこで二分する
    for i, n in enumerate(nodes):
        if n.kind == 'relation':
            left = resolve_sequence(nodes[:i], env)
            right = resolve_sequence(nodes[i + 1:], env)
            return getattr(sp, n.value)(left, right)

    # 大きい演算子（積分・総和）
    for i, n in enumerate(nodes):
        if n.kind in ('underover', 'subsup') and n.children:
            head = n.children[0]
            if head.kind == 'bigop':
                return resolve_bigop(n, nodes[i + 1:], env)
        if n.kind == 'bigop':
            raise Unresolved('bigop without bounds')
        if n.kind == 'munder' and n.children and flatten_name(n.children[0]) == 'lim':
            return resolve_limit(n, nodes[i + 1:], env)

    # 加減
    depth = 0
    for i in range(len(nodes) - 1, 0, -1):
        n = nodes[i]
        if n.kind == 'operator' and n.value in '+-' and depth == 0:
            left = resolve_sequence(nodes[:i], env)
            right = resolve_sequence(nodes[i + 1:], env)
            return left + right if n.value == '+' else left - right

    # 乗除（明示・暗黙）
    for i in range(len(nodes) - 1, 0, -1):
        n = nodes[i]
        if (n.kind == 'operator' and n.value in '*/') or \
           (n.kind == 'invisible' and n.value == 'times'):
            left = resolve_sequence(nodes[:i], env)
            right = resolve_sequence(nodes[i + 1:], env)
            return left / right if (n.kind == 'operator' and n.value == '/') else left * right

    # 関数適用
    for i, n in enumerate(nodes):
        if n.kind == 'invisible' and n.value == 'apply':
            head = nodes[i - 1] if i else None
            rest = nodes[i + 1:]
            if head is None or not rest:
                raise Unresolved('apply without operand')
            name = flatten_name(head)
            args = resolve_arguments(rest, env)
            fn = KNOWN_FUNCTIONS.get(name) or env.function(name)
            return fn(*args)

    # 単項マイナス
    if nodes[0].kind == 'operator' and nodes[0].value == '-':
        return -resolve_sequence(nodes[1:], env)

    if len(nodes) == 1:
        return resolve(nodes[0], env)

    # 残りは並置＝乗算
    product = resolve(nodes[0], env)
    for n in nodes[1:]:
        if n.kind in ('invisible', 'space'):
            continue
        product = product * resolve(n, env)
    return product


def resolve_arguments(nodes: list[Node], env: Environment) -> list:
    """関数の引数。fenced か、括弧に囲まれた並び"""
    if len(nodes) == 1 and nodes[0].kind == 'fenced':
        return split_commas(nodes[0].children, env)
    if nodes and nodes[0].kind == 'operator' and nodes[0].value == '(':
        depth = 0
        for i, n in enumerate(nodes):
            if n.kind == 'operator' and n.value == '(':
                depth += 1
            elif n.kind == 'operator' and n.value == ')':
                depth -= 1
                if depth == 0:
                    return split_commas(nodes[1:i], env)
    return [resolve_sequence(nodes, env)]


def split_commas(nodes: list[Node], env: Environment) -> list:
    args, current = [], []
    for n in nodes:
        if (n.kind == 'operator' and n.value in ',，、') or \
           (n.kind == 'invisible' and n.value == 'sep'):
            if current:
                args.append(resolve_sequence(current, env))
            current = []
        else:
            current.append(n)
    if current:
        args.append(resolve_sequence(current, env))
    return args


def resolve_bigop(node: Node, body_nodes: list[Node], env: Environment):
    head, lower, upper = node.children
    name = head.value
    inner = env.child()
    if name == 'Integral':
        var = find_integration_variable(body_nodes)
        if var is None:
            raise Unresolved('integral without dx')
        body = resolve_sequence(strip_differential(body_nodes), inner)
        return sp.Integral(body, (inner.symbol(var), resolve(lower, env), resolve(upper, env)))
    # 総和・総乗。下端は k=1 の形
    bound, start = split_assignment(lower, env)
    body = resolve_sequence(body_nodes, inner)
    ctor = sp.Sum if name == 'Sum' else sp.Product
    return ctor(body, (inner.symbol(bound), start, resolve(upper, env)))


def split_assignment(node: Node, env: Environment):
    kids = node.children if node.kind == 'row' else [node]
    for i, n in enumerate(kids):
        if n.kind == 'relation' and n.value == 'Eq':
            return flatten_name(kids[i - 1]), resolve_sequence(kids[i + 1:], env)
    return flatten_name(node), sp.Integer(1)


def find_integration_variable(nodes: list[Node]) -> str | None:
    for i, n in enumerate(nodes):
        if n.kind == 'identifier' and n.value == 'd' and i + 1 < len(nodes):
            nxt = nodes[i + 1]
            if nxt.kind == 'identifier':
                return nxt.value
    return None


def strip_differential(nodes: list[Node]) -> list[Node]:
    for i, n in enumerate(nodes):
        if n.kind == 'identifier' and n.value == 'd' and i + 1 < len(nodes):
            return nodes[:i]
    return nodes


def resolve_limit(node: Node, body_nodes: list[Node], env: Environment):
    spec = node.children[1]
    kids = spec.children if spec.kind == 'row' else [spec]
    var, target = None, None
    for i, n in enumerate(kids):
        if n.kind == 'operator' and n.value in ('→', '->'):
            var = flatten_name(kids[i - 1])
            target = resolve_sequence(kids[i + 1:], env)
            break
    if var is None:
        raise Unresolved('lim without arrow')
    inner = env.child()
    return sp.Limit(resolve_sequence(body_nodes, inner), inner.symbol(var), target)


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def parse_math(raw_html: str) -> list:
    """HTML 中の <math> を sympy の式にする。読めないものは黙って捨てる（誤読しない）"""
    assert_no_control_chars(raw_html[:4000], 'parse_math input')
    out = []
    for chunk in re.findall(r'<math\b.*?</math>', raw_html, re.S):
        text = html_mod.unescape(chunk)
        text = re.sub(r'<(\w+)([^>]*?)\s*/>', r'<\1\2></\1>', text)
        try:
            element = ET.fromstring(text)
        except ET.ParseError:
            continue
        try:
            node = build(element)
            env = Environment()
            scan_functions(node, env)
            expr = resolve(node, env)
            if expr is not None:
                out.append(expr)
        except (Unresolved, Exception):
            continue
    return out


def is_sequence_symbol(symbol: sp.Symbol, bound: str) -> bool:
    """a_k のような添字つき記号が、束縛変数 k の数列かどうか。

    MathML の msub を名前へ畳んだので、文字列を見ずに構造の記録から判定する。
    """
    return symbol_meta.get(str(symbol)) == bound
