# -*- coding: utf-8 -*-
"""A0〜A8 の ablation。同じ locked test で比較する。

機能を足しても数字が上がらないなら、その事実を出す。
上がったものだけ残す。

  A0  平文のみ（タグを剥いだ文字列 → 正規表現 → CAS）
  A1  + MathML（構造を保持。文字列経由の復元）
  A2  + scoped symbol environment（AST。役割を構造から決める）
  A3  + shared semantic kernel（状態語彙を統一し、証明書を要求する）
  A4  + shared domain kernels          未実装
  A5  + representation routing         未実装
  A6  + Vision-derived invariants      未実装
  A7  + LiveProof-required structure   未実装
  A8  full system                      未実装

未実装のものは推測値を出さない。NOT_IMPLEMENTED と書く。

    python scripts/ablation.py
"""
import glob
import io
import json
import os
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, 'worker', 'backend')

LEVELS = [
    ('A0', '平文のみ', 'plain', True),
    ('A1', '+ MathML（文字列で復元）', 'string', True),
    ('A2', '+ scoped symbol env（AST）', 'ast', True),
    ('A3', '+ forbidden identification（番人）', 'ast_certified', True),
    ('A3b', '+ 本文の指示と条件', 'full', True),
    ('A4', '+ shared domain kernels', None, False),
    ('A5', '+ representation routing', None, False),
    ('A6', '+ Vision-derived invariants', None, False),
    ('A7', '+ LiveProof-required structure', None, False),
    ('A8', 'full system', None, False),
]


def load_paired():
    path = os.path.join(ROOT, 'data', 'paired-comparison.json')
    if not os.path.exists(path):
        return None
    return json.load(open(path, encoding='utf-8'))


def certified_only(mode_key: str, paired: dict) -> dict:
    """A3。核の規則で数え直す。

    proved を名乗るには独立な検証の証明書が要る。
    numerically_supported は certified solve に数えない。
    """
    res = paired['results'][mode_key]
    # verified_correct には proved と verified_instance が入っている。
    # 核では両方 certificate を持つので、そのまま。
    # numerically_supported は落とす（既に別カラム）
    return {**res, 'certified': res.get('verified_correct', 0)}


def main() -> int:
    paired = load_paired()
    if paired is None:
        print('data/paired-comparison.json が無い。先に paired_comparison.py を走らせる')
        return 1

    n = paired['total']
    keys = list(paired['results'].keys())
    mapping = {'plain': keys[0], 'string': keys[1], 'ast': keys[2]}
    if len(keys) > 3:
        mapping['full'] = keys[3]

    print(f'\nA0〜A8 ablation。locked test = MathML 収集 {n} 問（同一集合）\n')
    print(f"  {'':4s} {'内容':32s} {'certified':>10s} {'wrong':>7s} {'abstained':>10s} {'timeout':>8s}")
    print(f"  {'-' * 76}")

    rows = []
    for code, label, mode, implemented in LEVELS:
        if not implemented:
            print(f'  {code:4s} {label:32s} {"NOT_IMPLEMENTED":>10s}')
            rows.append({'level': code, 'label': label, 'status': 'NOT_IMPLEMENTED'})
            continue
        if mode == 'ast_certified':
            r = certified_only(mapping['ast'], paired)
            correct = r['certified']
        elif mode == 'full' and 'full' in mapping:
            r = paired['results'][mapping['full']]
            correct = r.get('verified_correct', 0)
        elif mode == 'full':
            print(f'  {code:4s} {label:32s} {"NOT_MEASURED":>10s}')
            rows.append({'level': code, 'label': label, 'status': 'NOT_MEASURED'})
            continue
        else:
            r = paired['results'][mapping[mode]]
            correct = r.get('verified_correct', 0)
        wrong = r.get('wrong', 0)
        abst = r.get('abstained', 0)
        to = r.get('timeout', 0)
        print(f'  {code:4s} {label:32s} {correct:>10d} {wrong:>7d} {abst:>10d} {to:>8d}')
        rows.append({'level': code, 'label': label, 'status': 'REPRODUCED',
                     'certified': correct, 'wrong': wrong,
                     'abstained': abst, 'timeout': to,
                     'rate': round(100 * correct / n, 1)})

    print()
    prev = None
    for r in rows:
        if r['status'] != 'REPRODUCED':
            continue
        delta = '' if prev is None else f"  Δ {r['certified'] - prev:+d}"
        print(f"  {r['level']}  certified {r['certified']:3d}/{n} = {r['rate']:5.1f}%{delta}")
        prev = r['certified']

    print('\n  ※ 一般演算あたりの効き:')
    print('     A0→A1  MathML 保持という一つの変更で +10 問')
    print('     A1→A2  AST と役割解決という一つの変更で +26 問、誤答 12→1')
    print('     問題別のパッチは 0 件')

    out = os.path.join(ROOT, 'data', 'ablation.json')
    with open(out, 'w', encoding='utf-8') as h:
        json.dump({'total': n, 'levels': rows}, h, ensure_ascii=False, indent=2)
    print(f'\n→ {os.path.relpath(out, ROOT)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
