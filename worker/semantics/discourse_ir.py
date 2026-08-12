# -*- coding: utf-8 -*-
"""日本語数学談話 IR。

本文と、順序を保った MathML を、談話構造として表す。

  本文 + 順序付きMathML → Mathematical Discourse IR → Typed Problem IR → backend

これまでの実装は、式の並びだけを見て「最後の非関係式」を目標にしていた。
本文が何を宣言し、何を仮定し、何を求めているかを読んでいなかった。
167問中78問（47%）には印字された等式が一本も無い。条件は日本語の側にある。

語ごとの if 文を並べない。共通のノードへ解析する。
読めなかったものは黙って捨てる（誤読するより棄権する）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

PLACEHOLDER = '⟦式⟧'
_CONTROL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')


def assert_no_control(value: str, where: str) -> str:
    hit = _CONTROL.search(value)
    if hit:
        raise ValueError(f'{where}: 制御文字 0x{ord(hit.group()):02x} が位置 {hit.start()}')
    return value


# ---------------------------------------------------------------------------
# 文書の並び。本文と式の順序を失わない
# ---------------------------------------------------------------------------

class BlockKind(str, Enum):
    TEXT = 'text'
    FORMULA = 'formula'
    SUBPROBLEM = 'subproblem'


@dataclass
class DocumentBlock:
    kind: BlockKind
    text: str = ''
    """FORMULA のとき、その式が expressions の何番目か"""
    formula_index: int | None = None
    span: tuple[int, int] = (0, 0)


SUBPROBLEM = re.compile(r'[（(]\s*([0-9０-９]{1,2}|[ｉiIｖv]{1,3})\s*[）)]')


def split_blocks(body: str) -> list[DocumentBlock]:
    """本文を、文と式と小問境界に割る。式の位置は添字で保持する"""
    assert_no_control(body[:4000], 'split_blocks')
    blocks: list[DocumentBlock] = []
    index = 0
    cursor = 0
    for m in re.finditer(re.escape(PLACEHOLDER), body):
        text = body[cursor:m.start()]
        if text.strip():
            for piece in _split_text(text, cursor):
                blocks.append(piece)
        blocks.append(DocumentBlock(BlockKind.FORMULA, PLACEHOLDER, index, m.span()))
        index += 1
        cursor = m.end()
    tail = body[cursor:]
    if tail.strip():
        blocks.extend(_split_text(tail, cursor))
    return blocks


def _split_text(text: str, offset: int) -> list[DocumentBlock]:
    out: list[DocumentBlock] = []
    pos = 0
    for m in SUBPROBLEM.finditer(text):
        before = text[pos:m.start()]
        if before.strip():
            out.append(DocumentBlock(BlockKind.TEXT, before, None, (offset + pos, offset + m.start())))
        out.append(DocumentBlock(BlockKind.SUBPROBLEM, m.group(0), None,
                                 (offset + m.start(), offset + m.end())))
        pos = m.end()
    rest = text[pos:]
    if rest.strip():
        out.append(DocumentBlock(BlockKind.TEXT, rest, None, (offset + pos, offset + len(text))))
    return out


# ---------------------------------------------------------------------------
# 談話ノード
# ---------------------------------------------------------------------------

class Sort(str, Enum):
    NATURAL = 'Natural'
    INTEGER = 'Integer'
    REAL = 'Real'
    POSITIVE_REAL = 'PositiveReal'
    COMPLEX = 'Complex'
    PRIME = 'Prime'
    RATIONAL = 'Rational'
    TRIANGLE = 'Triangle'
    CIRCLE = 'Circle'
    LINE = 'Line'
    POINT = 'Point'
    QUADRILATERAL = 'Quadrilateral'
    TETRAHEDRON = 'Tetrahedron'
    SEQUENCE = 'Sequence'
    FUNCTION = 'Function'
    POLYNOMIAL = 'Polynomial'
    SET = 'Set'
    REGION = 'Region'
    UNKNOWN = 'Unknown'


class GoalOperator(str, Enum):
    COMPUTE_VALUE = 'ComputeValue'
    SOLVE_EQUATION = 'SolveEquation'
    FIND_ALL = 'FindAll'
    FIND_RANGE = 'FindRange'
    FIND_MAXIMUM = 'FindMaximum'
    FIND_MINIMUM = 'FindMinimum'
    COUNT = 'Count'
    PROVE = 'Prove'
    SHOW_INEQUALITY = 'ShowInequality'
    FIND_LOCUS = 'FindLocus'
    FIND_AREA = 'FindArea'
    FIND_VOLUME = 'FindVolume'
    FIND_PROBABILITY = 'FindProbability'
    EVALUATE_LIMIT = 'EvaluateLimit'
    EVALUATE_INTEGRAL = 'EvaluateIntegral'
    EXPRESS_IN_TERMS = 'ExpressInTerms'
    CONSTRUCT = 'Construct'
    UNKNOWN = 'Unknown'


@dataclass
class ObjectDeclaration:
    """「三角形ABCにおいて」「数列 a_n を」。対象を型付きで登録する"""
    name: str
    sort: Sort
    components: list[str] = field(default_factory=list)
    formula_index: int | None = None
    span: tuple[int, int] = (0, 0)
    source_text: str = ''


@dataclass
class DomainDeclaration:
    """「n を自然数とする」。変数の住む集合"""
    formula_index: int | None
    sort: Sort
    span: tuple[int, int] = (0, 0)
    source_text: str = ''


@dataclass
class IntervalConstraint:
    """0 < t < 1、n ≧ 3。連鎖を分解しすぎず一つの制約として持つ"""
    formula_index: int | None
    lower: str | None = None
    lower_open: bool = True
    upper: str | None = None
    upper_open: bool = True
    span: tuple[int, int] = (0, 0)
    source_text: str = ''


@dataclass
class StructuralCondition:
    """AB=AC、∠A=60°、点Pは円O上。CAS では扱えないので幾何側へ送る"""
    predicate: str
    arguments: list[str]
    span: tuple[int, int] = (0, 0)
    source_text: str = ''


@dataclass
class GoalNode:
    """目標。第一級。最後の式でも未知変数でもない"""
    operator: GoalOperator
    """式が目標のとき、その添字"""
    formula_index: int | None = None
    """式でない目標。Area(Triangle(A,B,C)) など"""
    symbolic_target: str | None = None
    qualifiers: list[str] = field(default_factory=list)
    span: tuple[int, int] = (0, 0)
    confidence: float = 0.0
    source_text: str = ''


@dataclass
class DiscourseIR:
    blocks: list[DocumentBlock]
    objects: list[ObjectDeclaration] = field(default_factory=list)
    domains: list[DomainDeclaration] = field(default_factory=list)
    intervals: list[IntervalConstraint] = field(default_factory=list)
    structural: list[StructuralCondition] = field(default_factory=list)
    goals: list[GoalNode] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)

    def formula_count(self) -> int:
        return sum(1 for b in self.blocks if b.kind is BlockKind.FORMULA)


# ---------------------------------------------------------------------------
# 対象の宣言
# ---------------------------------------------------------------------------

GEOMETRIC_SORTS = [
    (r'三角形|△', Sort.TRIANGLE, 3),
    (r'四角形|四辺形', Sort.QUADRILATERAL, 4),
    (r'四面体', Sort.TETRAHEDRON, 4),
    (r'円', Sort.CIRCLE, 1),
    (r'直線', Sort.LINE, 2),
]

DOMAIN_WORDS = [
    (r'自然数|正の整数', Sort.NATURAL),
    (r'整数', Sort.INTEGER),
    (r'素数', Sort.PRIME),
    (r'正の実数|正の数', Sort.POSITIVE_REAL),
    (r'実数', Sort.REAL),
    (r'有理数', Sort.RATIONAL),
    (r'複素数', Sort.COMPLEX),
]


def extract_objects(body: str, blocks: list[DocumentBlock]) -> list[ObjectDeclaration]:
    """幾何対象と数列・関数の宣言を拾う。

    語ごとの if 文ではなく、(語 → 型 → 成分数) の表から作る。
    """
    out: list[ObjectDeclaration] = []
    for pattern, sort, arity in GEOMETRIC_SORTS:
        # 「三角形 ⟦式⟧」または「三角形ABC」
        for m in re.finditer(rf'({pattern})\s*({PLACEHOLDER}|[A-Z]{{{arity}}})', body):
            token = m.group(2)
            index = body[:m.start(2)].count(PLACEHOLDER) if token == PLACEHOLDER else None
            comps = [] if token == PLACEHOLDER else list(token)
            out.append(ObjectDeclaration(
                name=token, sort=sort, components=comps,
                formula_index=index, span=m.span(), source_text=m.group(0)))
    # 数列。「数列 ⟦式⟧」「⟦式⟧ で定める数列」
    for m in re.finditer(rf'数列\s*[（(]?\s*({PLACEHOLDER})', body):
        index = body[:m.start(1)].count(PLACEHOLDER)
        out.append(ObjectDeclaration(name=f'formula_{index}', sort=Sort.SEQUENCE,
                                     formula_index=index, span=m.span(), source_text=m.group(0)))
    for m in re.finditer(rf'関数\s*({PLACEHOLDER})', body):
        index = body[:m.start(1)].count(PLACEHOLDER)
        out.append(ObjectDeclaration(name=f'formula_{index}', sort=Sort.FUNCTION,
                                     formula_index=index, span=m.span(), source_text=m.group(0)))
    return out


def extract_domains(body: str) -> list[DomainDeclaration]:
    """「⟦式⟧ を自然数とする」「⟦式⟧ は実数」

    変数名は本文には出ない。式の中にある。⟦式⟧ の位置で対応づける。
    """
    out: list[DomainDeclaration] = []
    for words, sort in DOMAIN_WORDS:
        pattern = (rf'{PLACEHOLDER}\s*(?:を|は|が)\s*[^。⟦]{{0,14}}?({words})')
        for m in re.finditer(pattern, body):
            index = body[:m.start()].count(PLACEHOLDER)
            out.append(DomainDeclaration(formula_index=index, sort=sort,
                                         span=m.span(), source_text=m.group(0)))
        # 「自然数 ⟦式⟧ は」の語順
        pattern2 = rf'({words})\s*{PLACEHOLDER}'
        for m in re.finditer(pattern2, body):
            index = body[:m.end(1)].count(PLACEHOLDER)
            out.append(DomainDeclaration(formula_index=index, sort=sort,
                                         span=m.span(), source_text=m.group(0)))
    # 同じ式に複数の型が付いたら、狭い方を残す
    best: dict[int | None, DomainDeclaration] = {}
    order = {s: i for i, (_, s) in enumerate(DOMAIN_WORDS)}
    for d in out:
        prev = best.get(d.formula_index)
        if prev is None or order.get(d.sort, 99) < order.get(prev.sort, 99):
            best[d.formula_index] = d
    return list(best.values())


# ---------------------------------------------------------------------------
# 範囲の条件
# ---------------------------------------------------------------------------

NUM = r'(-?\d+(?:/\d+)?|' + re.escape(PLACEHOLDER) + r')'
COMPARE_WORDS = [
    (r'以上', 'ge'), (r'以下', 'le'),
    (r'より大き(?:い|く)', 'gt'), (r'より小さ(?:い|く)', 'lt'),
    (r'を超え(?:る|ない)', 'gt'), (r'未満', 'lt'),
]


def extract_intervals(body: str) -> list[IntervalConstraint]:
    """「⟦式⟧ は3以上」「⟦式⟧ は0より大きく1より小さい」

    印字された 0<t<1 は MathML 側に不等式として入っているので、ここでは拾わない。
    日本語で書かれたものだけを取る。二重に入れない。
    """
    out: list[IntervalConstraint] = []

    # 「⟦式⟧ は a 以上 b 以下」
    for m in re.finditer(
            rf'{PLACEHOLDER}\s*(?:は|が|を)\s*{NUM}\s*以上\s*(?:で\s*)?{NUM}\s*以下', body):
        index = body[:m.start()].count(PLACEHOLDER)
        out.append(IntervalConstraint(index, lower=m.group(1), lower_open=False,
                                      upper=m.group(2), upper_open=False,
                                      span=m.span(), source_text=m.group(0)))

    # 「⟦式⟧ は a より大きく b より小さい」
    for m in re.finditer(
            rf'{PLACEHOLDER}\s*(?:は|が|を)\s*{NUM}\s*より大き(?:い|く)\s*'
            rf'{NUM}\s*より小さ(?:い|く)', body):
        index = body[:m.start()].count(PLACEHOLDER)
        out.append(IntervalConstraint(index, lower=m.group(1), lower_open=True,
                                      upper=m.group(2), upper_open=True,
                                      span=m.span(), source_text=m.group(0)))

    # 片側だけ。「⟦式⟧ は 3 以上」「⟦式⟧ は 0 より大きい」
    for words, op in COMPARE_WORDS:
        for m in re.finditer(rf'{PLACEHOLDER}\s*(?:は|が|を)\s*{NUM}\s*(?:{words})', body):
            index = body[:m.start()].count(PLACEHOLDER)
            value = m.group(1)
            if any(c.formula_index == index and c.lower and c.upper for c in out):
                continue    # 両側の条件が既にある
            if op in ('ge', 'gt'):
                out.append(IntervalConstraint(index, lower=value, lower_open=(op == 'gt'),
                                              span=m.span(), source_text=m.group(0)))
            else:
                out.append(IntervalConstraint(index, upper=value, upper_open=(op == 'lt'),
                                              span=m.span(), source_text=m.group(0)))
    return out


# ---------------------------------------------------------------------------
# 目標
# ---------------------------------------------------------------------------

# 目標の演算子。長い表現を先に見る（「範囲を求めよ」が「求めよ」に食われないように）
GOAL_PATTERNS: list[tuple[str, GoalOperator, str | None]] = [
    (r'の?軌跡を求め', GoalOperator.FIND_LOCUS, 'Locus'),
    (r'の?面積を求め', GoalOperator.FIND_AREA, 'Area'),
    (r'の?体積を求め', GoalOperator.FIND_VOLUME, 'Volume'),
    (r'の?確率を求め', GoalOperator.FIND_PROBABILITY, 'Probability'),
    (r'の?最大値を求め', GoalOperator.FIND_MAXIMUM, 'Maximum'),
    (r'の?最小値を求め', GoalOperator.FIND_MINIMUM, 'Minimum'),
    (r'の?範囲を求め', GoalOperator.FIND_RANGE, None),
    (r'の?個数を求め|は何個|何通り', GoalOperator.COUNT, 'Count'),
    (r'の?極限を求め', GoalOperator.EVALUATE_LIMIT, None),
    (r'すべて求め|全て求め', GoalOperator.FIND_ALL, None),
    (r'を用いて表せ|で表せ|を表せ', GoalOperator.EXPRESS_IN_TERMS, None),
    (r'を示せ|を証明せよ|証明せよ|示せ', GoalOperator.PROVE, None),
    (r'の?値を求め|を求め|求めよ|求めなさい', GoalOperator.COMPUTE_VALUE, None),
]

# 目標が式でない場合、直前にある対象を探す
OBJECT_BEFORE_GOAL = re.compile(
    rf'(三角形|△|四角形|四辺形|四面体|円|領域|曲線)\s*({PLACEHOLDER}|[A-Z]{{1,4}})')


def extract_goals(body: str, objects: list[ObjectDeclaration]) -> list[GoalNode]:
    """「何を求めよ」と言っている場所から目標を作る。

    目標は常に「最後の式」でも「未知変数」でもない。
    面積を求めよ、なら印字式ではなく Area(...) を目標として構築する。
    無理に sympy の式へ押し込まない。
    """
    out: list[GoalNode] = []
    claimed: set[tuple[int, int]] = set()

    for pattern, operator, symbolic in GOAL_PATTERNS:
        for m in re.finditer(pattern, body):
            # 既に長い表現が取った位置は飛ばす
            if any(s <= m.start() < e for s, e in claimed):
                continue
            claimed.add(m.span())
            before = body[:m.start()]
            index = before.count(PLACEHOLDER) - 1

            target = None
            confidence = 0.5
            if symbolic:
                # 面積・体積・軌跡は、直前の対象を引数にする
                obj = None
                for om in OBJECT_BEFORE_GOAL.finditer(before[-60:]):
                    obj = om
                if obj:
                    name = obj.group(2)
                    if name == PLACEHOLDER:
                        name = f'formula_{before.count(PLACEHOLDER) - 1}'
                    target = f'{symbolic}({obj.group(1)}:{name})'
                    confidence = 0.8
                else:
                    target = f'{symbolic}(?)'
                    confidence = 0.3
                out.append(GoalNode(operator, formula_index=None, symbolic_target=target,
                                    span=m.span(), confidence=confidence,
                                    source_text=body[max(0, m.start() - 30):m.end()]))
                continue

            if index >= 0:
                confidence = 0.7 if operator is not GoalOperator.COMPUTE_VALUE else 0.6
                out.append(GoalNode(operator, formula_index=index, span=m.span(),
                                    confidence=confidence,
                                    source_text=body[max(0, m.start() - 30):m.end()]))
    # 出現順に
    out.sort(key=lambda g: g.span[0])
    return out


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def parse_discourse(body: str) -> DiscourseIR:
    """本文を談話 IR にする。読めないものは unresolved に残す"""
    if not body:
        return DiscourseIR(blocks=[])
    blocks = split_blocks(body)
    objects = extract_objects(body, blocks)
    ir = DiscourseIR(
        blocks=blocks,
        objects=objects,
        domains=extract_domains(body),
        intervals=extract_intervals(body),
        structural=[],
        goals=extract_goals(body, objects),
    )
    if not ir.goals:
        ir.unresolved.append('no_goal_detected')
    if len(ir.goals) > 3:
        ir.unresolved.append('ambiguous_goal')
    return ir
