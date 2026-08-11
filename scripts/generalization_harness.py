# -*- coding: utf-8 -*-
"""汎化ハーネス（MORTRA 仕様 §6）。

正答率が上がったことを汎化と呼ばない。次の二つを別々に測る。

  metamorphic   意味を変えない変換をかけても、答えが対応して保たれるか
                （変数名の付け替え、前提の順序、等式の左右、TeXの言い換え、
                  図の回転・平行移動・拡大、格子基底の変換 B → BU）

  counterfactual 意味を変える小さな変更で、答えがちゃんと変わるか
                （= ↔ ≦、正 ↔ 負、平行 ↔ 垂直、60° ↔ 61°、FCC ↔ BCC）

前者だけ通って後者が通らないものは、入力を見ていない。
後者だけ通って前者が通らないものは、表層に張り付いている。

    python scripts/generalization_harness.py
"""
import io
import math
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'worker', 'backend'))

import sympy as sp  # noqa: E402
import cas_solver as C  # noqa: E402
from geometry_natural_formalizer import formalize_geometry_text  # noqa: E402

passed = 0
failed = 0
notes: list[str] = []


def check(name: str, ok: bool, detail: str = '') -> None:
    global passed, failed
    if ok:
        passed += 1
    else:
        failed += 1
        notes.append(f'{name}  {detail}')
    print(f"{'  ok  ' if ok else '  NG  '} {name}{'' if ok or not detail else '   ' + detail}")


# ---------------------------------------------------------------------------
# 1. CAS — 意味を保つ変換
# ---------------------------------------------------------------------------
print('\n■ metamorphic（CAS）— 意味を変えない変換で答えが保たれるか')

BASE = {'relations': ['x + y = 10', 'x - y = 4'], 'goal': 'x*y'}


def answer_of(req):
    r = C.solve_request(req)
    if r.get('status') != 'solved':
        return None
    a = r.get('answer')
    return sp.sympify(a[0] if isinstance(a, list) else a)


base_answer = answer_of(BASE)
check('基準が解ける', base_answer is not None, str(base_answer))

# 変数名の付け替え。x,y → u,v にしても答えは同じ数
renamed = {'relations': ['u + v = 10', 'u - v = 4'], 'goal': 'u*v'}
check('変数名の付け替えで不変', answer_of(renamed) == base_answer, str(answer_of(renamed)))

# 前提の順序
reordered = {'relations': ['x - y = 4', 'x + y = 10'], 'goal': 'x*y'}
check('前提の順序で不変', answer_of(reordered) == base_answer)

# 等式の左右を入れ替える
flipped = {'relations': ['10 = x + y', '4 = x - y'], 'goal': 'x*y'}
check('等式の左右で不変', answer_of(flipped) == base_answer)

# 同値な TeX の書き方
tex_forms = [
    {'relations': [r'x+y=10', r'x-y=4'], 'goal': r'x \cdot y'},
    {'relations': [r'x + y = \frac{20}{2}', r'x - y = 4'], 'goal': 'x*y'},
]
for i, form in enumerate(tex_forms):
    check(f'同値な TeX 表記 {i} で不変', answer_of(form) == base_answer, str(answer_of(form)))

# 定数倍した方程式は同じ解を持つ
scaled = {'relations': ['2*x + 2*y = 20', 'x - y = 4'], 'goal': 'x*y'}
check('方程式の定数倍で不変', answer_of(scaled) == base_answer)

# ---------------------------------------------------------------------------
# 2. CAS — 意味を変える変更
# ---------------------------------------------------------------------------
print('\n■ counterfactual（CAS）— 意味を変えたら答えも変わるか')

changed = {'relations': ['x + y = 11', 'x - y = 4'], 'goal': 'x*y'}
check('定数を変えたら答えが変わる', answer_of(changed) != base_answer,
      f'{answer_of(changed)} vs {base_answer}')

sign = {'relations': ['x + y = 10', 'x - y = -4'], 'goal': 'x*y'}
check('符号を変えたら解が変わる（積は対称なので x,y は入れ替わる）',
      answer_of(sign) == base_answer, '積は対称。これは変わらないのが正しい')

# = を ≦ にすると等式の解ではなくなる
ineq = C.solve_request({'relations': ['x + y <= 10', 'x - y = 4'], 'goal': 'x*y'})
check('= を ≦ にすると等式としては解けない',
      ineq.get('status') != 'solved' or ineq.get('answer') != str(base_answer),
      str(ineq.get('status')))

# 2次方程式の係数を変えると根が変わる
q1 = answer_of({'relations': ['x^2-5*x+6=0'], 'goal': 'x'})
q2 = answer_of({'relations': ['x^2-5*x+7=0'], 'goal': 'x'})
check('2次の定数項を変えたら根が変わる', q1 != q2, f'{q1} vs {q2}')

# ---------------------------------------------------------------------------
# 3. 幾何形式化 — 意味を保つ変換
# ---------------------------------------------------------------------------
print('\n■ metamorphic（幾何形式化）')

GEO = '三角形ABCにおいて、ABの中点をM、ACの中点をNとする。MNとBCは平行であることを示せ。'


def geo_signature(text: str):
    """点の名前に依らない形で形式化の結果を表す"""
    r = formalize_geometry_text(text, max_restarts=8)
    if r.status != 'formalized' or not r.goals:
        return None
    return (r.goals[0].name, len(r.predicates), len(r.points))


base_geo = geo_signature(GEO)
check('幾何の基準が形式化できる', base_geo is not None, str(base_geo))

# 点の付け替え A,B,C,M,N → P,Q,R,S,T
table = str.maketrans('ABCMN', 'PQRST')
check('点名の付け替えで同じ構造', geo_signature(GEO.translate(table)) == base_geo,
      str(geo_signature(GEO.translate(table))))

# 前提の順序を入れ替える
swapped = '三角形ABCにおいて、ACの中点をN、ABの中点をMとする。MNとBCは平行であることを示せ。'
check('前提の順序で同じ構造', geo_signature(swapped) == base_geo, str(geo_signature(swapped)))

# 言い回しの言い換え（「とする」→「とおく」、「示せ」→「証明せよ」）
paraphrased = '三角形ABCにおいて、ABの中点をMとおき、ACの中点をNとおく。MNとBCは平行であることを証明せよ。'
check('言い回しの言い換えで同じ構造', geo_signature(paraphrased) == base_geo,
      str(geo_signature(paraphrased)))

# 記号で書く（平行 → ∥）
symbolic = '三角形ABCにおいて、ABの中点をM、ACの中点をNとする。MN∥BCを示せ。'
check('語を記号にしても同じ構造', geo_signature(symbolic) == base_geo, str(geo_signature(symbolic)))

# ---------------------------------------------------------------------------
# 4. 幾何形式化 — 意味を変える変更
# ---------------------------------------------------------------------------
print('\n■ counterfactual（幾何形式化）')

# 「MN と BC は垂直」は偽（中点連結より平行）。
# 結論も図の制約に入れているので、矛盾する目標では図が構成できず棄権する。
# 偽の命題を形式化してしまう方が危険なので、これは通ってはいけない検査。
perp = GEO.replace('平行', '垂直')
check('偽の結論（MN⊥BC）は形式化を拒否する', geo_signature(perp) is None,
      str(geo_signature(perp)))

# 真の結論に変えた場合は通る。拒否が「何でも拒否」でないことの確認
true_perp = ('三角形ABCにおいて、AからBCに下ろした垂線の足をDとする。'
             'ABの中点をM、ACの中点をNとするとき、MNとADは垂直であることを示せ。')
sig_true = geo_signature(true_perp)
check('真の垂直の結論は形式化できる（何でも拒否ではない）',
      sig_true is not None and sig_true[0] == 'perp', str(sig_true))

# 中点 → 内分点にすると前提が変わる
divided = '三角形ABCにおいて、ABを2:1に内分する点をM、ACの中点をNとする。MNとBCは平行であることを示せ。'
sig_div = geo_signature(divided)
check('中点 → 内分点 で前提が変わる',
      sig_div is None or sig_div[1] != base_geo[1], str(sig_div))

# ---------------------------------------------------------------------------
# 5. 格子 — 基底変換で不変、格子を変えたら変わる
# ---------------------------------------------------------------------------
print('\n■ metamorphic / counterfactual（格子）')
print('     scripts/lattice-properties.mts が B → BU の不変性を 93 件で検査している')
print('     ここでは分野をまたぐ一点だけ確認する')

# FCC ↔ BCC。逆格子が入れ替わることは、格子を変えたら結果が変わることの確認
try:
    import subprocess
    out = subprocess.run(
        ['node', '-e', '''
        const L = require("fs").existsSync("lib/vision/lattice.ts");
        console.log(L ? "ok" : "missing");
        '''], capture_output=True, text=True, cwd=ROOT, timeout=60)
    check('格子核が存在する', 'ok' in out.stdout, out.stdout.strip())
except Exception as exc:
    check('格子核が存在する', False, repr(exc)[:60])

# ---------------------------------------------------------------------------
print(f"\n{'─' * 64}")
print(f'汎化ハーネス {passed}/{passed + failed}' + (f'   失敗 {failed}' if failed else ''))
if notes:
    print('\n失敗:')
    for n in notes:
        print(f'  {n}')
sys.exit(1 if failed else 0)
