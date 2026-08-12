# -*- coding: utf-8 -*-
"""談話 IR のテスト。

positive / equivalent（意味を保つ）/ counterfactual（意味を変える）/ ambiguous
を各項目に付ける。単語検出だけの脆い実装をここで落とす。

    python tests/discourse/test_discourse.py
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'worker', 'semantics'))

from discourse_ir import parse_discourse, GoalOperator, Sort  # noqa: E402

P = '⟦式⟧'
passed = failed = 0
notes = []


def check(name, ok, detail=''):
    global passed, failed
    if ok:
        passed += 1
    else:
        failed += 1
        notes.append(f'{name}  {detail}')
    print(f"{'  ok  ' if ok else '  NG  '} {name}{'' if ok or not detail else '   ' + detail}")


def goal_of(body):
    ir = parse_discourse(body)
    return ir.goals[0] if ir.goals else None


def sig(body):
    """点名や数値に依らない構造の署名"""
    ir = parse_discourse(body)
    g = ir.goals[0] if ir.goals else None
    return (g.operator if g else None,
            g.formula_index if g else None,
            tuple(sorted(d.sort for d in ir.domains)),
            tuple(sorted((i.lower, i.lower_open, i.upper, i.upper_open) for i in ir.intervals)),
            tuple(sorted(o.sort for o in ir.objects)))


print('\n■ positive — 基本の解析')
check('自然数の宣言', parse_discourse(f'{P} を自然数とする。').domains[0].sort is Sort.NATURAL)
check('実数の宣言', parse_discourse(f'{P} は実数である。').domains[0].sort is Sort.REAL)
check('素数の宣言', parse_discourse(f'{P} を素数とする。').domains[0].sort is Sort.PRIME)
check('三角形の宣言',
      parse_discourse(f'三角形 {P} において').objects[0].sort is Sort.TRIANGLE)
check('数列の宣言',
      parse_discourse(f'数列 {P} を考える。').objects[0].sort is Sort.SEQUENCE)
check('3以上', parse_discourse(f'{P} は3以上とする。').intervals[0].lower == '3')
check('3以上は閉区間', parse_discourse(f'{P} は3以上とする。').intervals[0].lower_open is False)
check('0より大きく1より小さい',
      parse_discourse(f'{P} は0より大きく1より小さい。').intervals[0].upper == '1')
check('0より大きいは開区間',
      parse_discourse(f'{P} は0より大きく1より小さい。').intervals[0].lower_open is True)

print('\n■ positive — 目標の演算子')
for body, want in [
    (f'{P} の値を求めよ。', GoalOperator.COMPUTE_VALUE),
    (f'{P} の範囲を求めよ。', GoalOperator.FIND_RANGE),
    (f'{P} の最大値を求めよ。', GoalOperator.FIND_MAXIMUM),
    (f'{P} の最小値を求めよ。', GoalOperator.FIND_MINIMUM),
    (f'三角形 {P} の面積を求めよ。', GoalOperator.FIND_AREA),
    (f'{P} の体積を求めよ。', GoalOperator.FIND_VOLUME),
    (f'点 {P} の軌跡を求めよ。', GoalOperator.FIND_LOCUS),
    (f'{P} をすべて求めよ。', GoalOperator.FIND_ALL),
    (f'{P} の個数を求めよ。', GoalOperator.COUNT),
    (f'{P} を示せ。', GoalOperator.PROVE),
    (f'{P} の極限を求めよ。', GoalOperator.EVALUATE_LIMIT),
    (f'{P} を {P} を用いて表せ。', GoalOperator.EXPRESS_IN_TERMS),
]:
    g = goal_of(body)
    check(f'{want.value}', g is not None and g.operator is want,
          g.operator.value if g else 'なし')

print('\n■ metamorphic — 意味を保つ変更で同じ IR')
base = f'{P} は3以上の自然数とする。{P} の範囲を求めよ。'
check('語順を変えても同じ', sig(base) == sig(f'自然数 {P} は3以上であるとする。{P} の範囲を求めよ。'),
      '「自然数nは3以上」と「nは3以上の自然数」')
check('「とする」→「とおく」で同じ',
      sig(base) == sig(f'{P} は3以上の自然数とおく。{P} の範囲を求めよ。'))
check('「求めよ」→「求めなさい」で同じ',
      sig(f'{P} を求めよ。') == sig(f'{P} を求めなさい。'))
check('「示せ」→「証明せよ」で同じ',
      sig(f'{P} を示せ。') == sig(f'{P} を証明せよ。'))
check('句読点の違いで同じ',
      sig(f'{P} を自然数とする。') == sig(f'{P} を自然数とする．'))

print('\n■ counterfactual — 意味を変える変更で IR が変わる')
check('自然数 → 実数',
      parse_discourse(f'{P} を自然数とする。').domains[0].sort
      is not parse_discourse(f'{P} を実数とする。').domains[0].sort)
check('3以上 → 4以上',
      parse_discourse(f'{P} は3以上。').intervals[0].lower
      != parse_discourse(f'{P} は4以上。').intervals[0].lower)
check('以上 → より大きい（開閉が変わる）',
      parse_discourse(f'{P} は3以上。').intervals[0].lower_open
      != parse_discourse(f'{P} は3より大きい。').intervals[0].lower_open)
check('最大値 → 最小値',
      goal_of(f'{P} の最大値を求めよ。').operator
      is not goal_of(f'{P} の最小値を求めよ。').operator)
check('面積 → 体積',
      goal_of(f'{P} の面積を求めよ。').operator
      is not goal_of(f'{P} の体積を求めよ。').operator)
check('求めよ → 示せ',
      goal_of(f'{P} を求めよ。').operator is not goal_of(f'{P} を示せ。').operator)
check('三角形 → 四面体',
      parse_discourse(f'三角形 {P} において').objects[0].sort
      is not parse_discourse(f'四面体 {P} において').objects[0].sort)

print('\n■ negative — 壊れた入力では棄権する')
check('目標の語が無ければ no_goal_detected',
      'no_goal_detected' in parse_discourse(f'{P} は自然数である。').unresolved)
check('目標が多すぎれば ambiguous_goal',
      'ambiguous_goal' in parse_discourse(
          f'{P} を求めよ。{P} を求めよ。{P} を求めよ。{P} を求めよ。').unresolved)
check('空文字で落ちない', parse_discourse('').formula_count() == 0)
check('式が無くても落ちない', parse_discourse('求めよ。').formula_count() == 0)

print('\n■ 長い表現が短い表現に食われない')
check('「範囲を求めよ」が「求めよ」にならない',
      goal_of(f'{P} の範囲を求めよ。').operator is GoalOperator.FIND_RANGE)
check('「最大値を求めよ」が「求めよ」にならない',
      goal_of(f'{P} の最大値を求めよ。').operator is GoalOperator.FIND_MAXIMUM)
check('「面積を求めよ」が「求めよ」にならない',
      goal_of(f'三角形 {P} の面積を求めよ。').operator is GoalOperator.FIND_AREA)

print('\n■ 式の位置が保たれる')
ir = parse_discourse(f'{P} と {P} について {P} を求めよ。')
check('式が3つ', ir.formula_count() == 3)
check('目標は3番目の式', goal_of(f'{P} と {P} について {P} を求めよ。').formula_index == 2)

print(f"\n{'─' * 60}")
print(f'談話テスト {passed}/{passed + failed}' + (f'   失敗 {failed}' if failed else ''))
for n in notes:
    print(f'  {n}')
sys.exit(1 if failed else 0)
