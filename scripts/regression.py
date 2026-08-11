# -*- coding: utf-8 -*-
"""解けたと呼んでよいものと、呼んではいけないものを固定する。

偽陽性を一度でも数えたら、その数字は全部信用できなくなる。
p_n = p_n を「証明済み」と数えていたことが実際にあった。
以後は必ずこの表を通してから測る。

    python scripts/regression.py
"""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'worker', 'backend'))

import cas_solver as C  # noqa: E402

# 解けたと呼んではいけないもの。何も計算していない
MUST_REJECT = [
    ('恒等な関数値', [], 'f (x)'),
    ('恒等な数列項', [], 'a_n'),
    ('恒等な冪', [], '((w)**(n))'),
    ('定数の極限', [], 'Limit(d_n , n, oo)'),
    ('数列の和（和が取れていない）', [], 'Sum(a_k , (k, 1, n))'),
    ('積分できていない', [], 'Integral(f_x , (x, 0, 1))'),
    ('単独の記号', [], 'beta'),
    ('添字つき記号', [], 'p_n'),
]

# 解けたと呼んでよいもの
MUST_SOLVE = [
    ('2次方程式', [r'x^2-5x+6=0'], 'x', ['2', '3']),
    ('3次方程式', [r'x^3-6x^2+11x-6=0'], 'x', ['1', '2', '3']),
    ('連立', ['x+y=10', 'x-y=4'], 'x*y', '21'),
    ('対称式の消去', ['a+b=s', 'a*b=p'], 'a**2+b**2', None),
    ('定積分', [], r'\int_0^1 x^2 dx', r'\frac{1}{3}'),
    ('総和', [], r'\sum_{k=1}^{n} k', None),
    ('総和 k^2', [], r'\sum_{k=1}^{n} k^2', None),
    ('極限', [], 'Limit(sin(x)/x, x, 0)', '1'),
    ('不等式', [r'x^2-5x+6<=0'], 'x', None),
    ('連鎖不等式', ['0<=t<=1'], 't', None),
    ('角度記号', [r'∠ABC=pi/6'], r'∠ABC', None),
]


def main() -> int:
    bad, missed = [], []
    print('■ 解けたと呼んではいけないもの')
    for name, rel, goal in MUST_REJECT:
        st = C.solve_request({'relations': rel, 'goal': goal}).get('status')
        ok = st != 'solved'
        if not ok:
            bad.append(name)
        print(f"  {'ok  ' if ok else 'NG  '} {name:28s} {st}")

    print('\n■ 解けたと呼んでよいもの')
    for name, rel, goal, expect in MUST_SOLVE:
        r = C.solve_request({'relations': rel, 'goal': goal})
        st, ans = r.get('status'), r.get('answer_latex')
        ok = st == 'solved'
        if ok and expect is not None:
            ok = (ans == expect) if isinstance(expect, list) else (str(expect) in str(ans))
        if not ok:
            missed.append(name)
        print(f"  {'ok  ' if ok else 'NG  '} {name:28s} {st:14s} {str(ans)[:34]}")

    total = len(MUST_REJECT) + len(MUST_SOLVE)
    fails = len(bad) + len(missed)
    print(f"\n{'─' * 60}")
    print(f'退行テスト {total - fails}/{total}'
          f'   偽陽性 {len(bad)}   取りこぼし {len(missed)}')
    if bad:
        print(f'  偽陽性: {bad}')
    if missed:
        print(f'  取りこぼし: {missed}')
    return 1 if fails else 0


if __name__ == '__main__':
    raise SystemExit(main())
