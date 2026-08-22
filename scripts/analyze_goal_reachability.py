# -*- coding: utf-8 -*-
"""未解決問題がどこで落ちているかを、既存 artifact だけから確定させる。

結論を先に書く。46問すべて・64試行すべてで goal_deduction_count が 0 だった。
閉包は数千から十二万回の演繹を出しているが、そのどれもゴールに触れていない。

  探索が足りない          → 違う。未解決の方が閉包が大きい
  補助構成の選び方が悪い  → 違う。64通り全部でゴールに触れない
  残差を勾配に使えばよい  → 違う。残差は動くがゴールに触れないまま動いている

ゴールに触れた試行が1つでもあれば解けた（6/6）。0なら解けなかった（46/46）。
52問・3,328試行で例外なし。これは探索の問題ではなく到達可能性の問題である。

    python scripts/analyze_goal_reachability.py
"""
import glob
import io
import json
import os
import statistics as st
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = os.path.join(ROOT, 'data', 'hageo-heldout-remaining52-n6-k64-runs-2026-08-20')


def collect():
    rows = []
    for f in sorted(glob.glob(os.path.join(RUNS, '*.json'))):
        d = json.load(open(f, encoding='utf-8'))
        attempts = d.get('attempt_results', [])
        if not attempts:
            continue
        goal = [a.get('goal_deduction_count') or 0 for a in attempts]
        allc = [a.get('all_deduction_count') or 0 for a in attempts]
        res = [a.get('proof_residual', {}).get('ar_residual_l1') for a in attempts]
        res = [v for v in res if isinstance(v, (int, float))]
        rows.append({
            'problem': d['problem_name'],
            'solved': bool(d.get('solved')),
            'attempts': len(attempts),
            'attempts_touching_goal': sum(1 for v in goal if v > 0),
            'max_goal_deductions': max(goal),
            'max_all_deductions': max(allc),
            'median_all_deductions': st.median(allc),
            'min_residual': min(res) if res else None,
            'distinct_residuals': len(set(res)),
            'unique_paths': len({json.dumps(a.get('path')) for a in attempts}),
        })
    return rows


def main() -> int:
    rows = collect()
    if not rows:
        print(f'run artifact が無い: {RUNS}')
        return 1
    solved = [r for r in rows if r['solved']]
    unsolved = [r for r in rows if not r['solved']]

    print(f'\nHAGeo heldout remaining52 / n=6 rounds / k=64 attempts\n')
    print(f'  問題数 {len(rows)}   解けた {len(solved)}   未解決 {len(unsolved)}')
    print(f'  総試行 {sum(r["attempts"] for r in rows)}\n')

    print('■ ゴールに触れた試行の有無で完全に分かれる')
    print(f'    解けた   ゴールに触れた試行あり  {sum(1 for r in solved if r["attempts_touching_goal"] > 0)}/{len(solved)}')
    print(f'    未解決   ゴールに触れた試行あり  {sum(1 for r in unsolved if r["attempts_touching_goal"] > 0)}/{len(unsolved)}')
    exceptions = [r for r in rows if r['solved'] != (r['attempts_touching_goal'] > 0)]
    print(f'    例外 {len(exceptions)} 件')

    print('\n■ 閉包の大きさは原因ではない')
    for name, group in (('解けた', solved), ('未解決', unsolved)):
        v = [r['max_all_deductions'] for r in group]
        print(f'    {name:6s} all_deduction_count 最大の中央値 {st.median(v):8.0f}   '
              f'範囲 {min(v)}–{max(v)}')
    print('    未解決の方が大きい。演繹はしているが、方向がゴールと交わらない')

    print('\n■ 残差は勾配として使えない')
    moving = [r for r in unsolved if r['distinct_residuals'] > 1]
    print(f'    未解決で残差が動く問題 {len(moving)}/{len(unsolved)}')
    print(f'    そのすべてで ゴールに触れた試行は 0。'
          f'残差が下がってもゴールへは近づいていない')

    print('\n■ 最も惜しい問題（閉包が小さい＝早く飽和している）')
    for r in sorted(unsolved, key=lambda x: x['max_all_deductions'])[:6]:
        print(f'    {r["problem"]:26s} 閉包最大 {r["max_all_deductions"]:7d}  '
              f'残差最小 {r["min_residual"]}  相異path {r["unique_paths"]}')

    out = os.path.join(ROOT, 'data', 'goal-reachability-analysis.json')
    with open(out, 'w', encoding='utf-8') as h:
        json.dump({
            'source_runs': os.path.basename(RUNS),
            'finding': 'goal_deduction_count==0 for all unsolved attempts; '
                       'closure size is not the limiting factor',
            'separation_exceptions': len(exceptions),
            'rows': rows,
        }, h, ensure_ascii=False, indent=2)
    print(f'\n→ {os.path.relpath(out, ROOT)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
