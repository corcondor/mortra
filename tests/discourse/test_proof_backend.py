# -*- coding: utf-8 -*-
"""証明 backend の検査。

「反例が無かった」を「証明した」と呼ばないことを固定する。
certified に数えてよいのは proved と disproved だけ。

    python tests/discourse/test_proof_backend.py
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'worker', 'semantics'))
sys.path.insert(0, os.path.join(ROOT, 'worker', 'backend'))

import sympy as sp  # noqa: E402
from proof_backend import prove_relation, find_counterexample  # noqa: E402

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


a, b, u = sp.symbols('a b u')
x, y = sp.symbols('x y', positive=True)

print('\n■ 真の命題を proved と判定する')
for name, goal, prem in [
    ('(a+b)² = a²+2ab+b²', sp.Eq((a + b) ** 2, a ** 2 + 2 * a * b + b ** 2), []),
    ('前提 u=2 のもとで u²=4', sp.Eq(u ** 2, 4), [sp.Eq(u, 2)]),
    ('2 < 3', sp.Lt(sp.Integer(2), sp.Integer(3)), []),
]:
    r = prove_relation(goal, prem)
    check(name, r.get('verdict') == 'proved', str(r.get('verdict')))

print('\n■ 偽の命題を disproved と判定する')
for name, goal, prem in [
    ('(a+b)² = a²+b²', sp.Eq((a + b) ** 2, a ** 2 + b ** 2), []),
    ('u>0 のもとで u<0', sp.Lt(u, 0), [sp.Gt(u, 0)]),
    ('3 < 2', sp.Lt(sp.Integer(3), sp.Integer(2)), []),
]:
    r = prove_relation(goal, prem)
    check(name, r.get('verdict') == 'disproved', str(r.get('verdict')))

print('\n■ 証明できないものを proved と呼ばない')
for name, goal, prem in [
    ('log x ≦ x−1', sp.Le(sp.log(x), x - 1), [sp.Gt(x, 0)]),
    ('相加相乗 x+y ≧ 2√(xy)', sp.Ge(x + y, 2 * sp.sqrt(x * y)), []),
]:
    r = prove_relation(goal, prem)
    check(f'{name} は numerically_supported',
          r.get('verdict') == 'numerically_supported', str(r.get('verdict')))
    check(f'{name} を proved と言わない', r.get('verdict') != 'proved')

print('\n■ 反例探索が前提を守る')
{
    # x>0 の前提のもとで x<0 の反例を探すと、x>0 を満たす点だけを試すこと
}
c = find_counterexample(sp.Lt(u, 5), [sp.Gt(u, 10)])
check('前提 u>10 のもとで u<5 の反例が見つかる', c is not None, str(c))
c2 = find_counterexample(sp.Gt(u, 0), [sp.Gt(u, 10)])
check('前提 u>10 のもとで u>0 の反例は無い', c2 is None, str(c2))

print('\n■ 既に評価済みの関係を扱える')
check('sp.true を proved',
      prove_relation(sp.true, []).get('verdict') == 'proved')
check('sp.false を disproved',
      prove_relation(sp.false, []).get('verdict') == 'disproved')

print('\n■ 関係式でないものは扱わない')
check('式を渡したら goal_not_relation',
      prove_relation(a + b, []).get('status') == 'goal_not_relation')

print('\n■ 保留を「答えを出した」と数えさせない')
# dev A5 で「誤答 4」と出たものは全部これだった。
# status が 'solved' だと採点側が答えとして読み、verdict が proved でないので
# 誤答に落ちる。保留は誤答ではない。status を分ける。
r = prove_relation(sp.Le(sp.log(x), x - 1), [sp.Gt(x, 0)])
check('反例なしの status は solved ではない',
      r.get('status') != 'solved', str(r.get('status')))
check('反例なしの status は numerically_supported',
      r.get('status') == 'numerically_supported', str(r.get('status')))
check('proved の status は solved のまま',
      prove_relation(sp.Eq(a + b, b + a), []).get('status') == 'solved')
check('disproved の status は solved のまま',
      prove_relation(sp.false, []).get('status') == 'solved')

print(f"\n{'─' * 60}")
print(f'証明backend {passed}/{passed + failed}' + (f'   失敗 {failed}' if failed else ''))
for n in notes:
    print(f'  {n}')
sys.exit(1 if failed else 0)
