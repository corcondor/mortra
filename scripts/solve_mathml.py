# -*- coding: utf-8 -*-
"""MathML 経路で解く。平文経路との差を直接測る。

前の経路はタグを剥いた平文を CAS に食わせていた。
不等号も積分区間も消えた文字列を解いても、出るのはゴミだった。

ここでは MathML の木から式を取り、前提と結論を分けて CAS に渡す。
同じ問題集合で両方を走らせ、数字がどれだけ動いたかを出す。

    python scripts/solve_mathml.py
"""
import glob
import io
import json
import os
import re
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, TimeoutError as FuturesTimeout
from concurrent.futures.process import BrokenProcessPool

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'worker', 'backend'))

import cas_solver as C  # noqa: E402
from mathml_to_sympy import parse_math_elements  # noqa: E402

PER_PROBLEM_SECONDS = 8.0
REL = re.compile(r'(?<![<>!=])=(?!=)|<=|>=|!=|<|>')
ASK = re.compile(r'求めよ|求めなさい|答えよ|示せ|証明せよ')


def split_problem(exprs, body):
    """式の列を、前提と結論に分ける。

    「求めよ」の直前にある関係でない式が結論。
    関係（等号・不等号を含むもの）は前提。
    """
    relations = [e for e in exprs if REL.search(e)]
    candidates = [e for e in exprs if not REL.search(e) and len(e) > 1]
    goal = None
    # 構造を持つもの（積分・総和・極限）は結論になりやすい
    structured = [e for e in candidates if any(k in e for k in ('Integral', 'Sum', 'Limit'))]
    if structured:
        goal = structured[-1]
    elif candidates:
        goal = candidates[-1]
    return relations, goal


def solve_one(payload):
    relations, goal = payload
    return C.solve_request({'relations': relations, 'goal': goal})


def run(problems, extract, label):
    stats = Counter()
    solved = []
    pool = ProcessPoolExecutor(max_workers=1)
    for i, p in enumerate(problems, 1):
        if i % 25 == 0:
            sys.stderr.write(f'\r{label} {i}/{len(problems)}  solved {stats["solved"]}')
            sys.stderr.flush()
        relations, goal = extract(p)
        if not goal:
            stats['結論の式が取れない'] += 1
            continue
        if len(relations) > 8 or len(goal) > 300:
            stats['大きすぎる'] += 1
            continue
        try:
            future = pool.submit(solve_one, (relations[:8], goal))
            r = future.result(timeout=PER_PROBLEM_SECONDS)
        except FuturesTimeout:
            stats['打ち切り'] += 1
            pool.shutdown(wait=False, cancel_futures=True)
            pool = ProcessPoolExecutor(max_workers=1)
            continue
        except BrokenProcessPool:
            # 子プロセスが落ちた（再帰の深さ・メモリ）。壊れたプールは使えないので作り直す
            stats['子プロセス異常終了'] += 1
            pool = ProcessPoolExecutor(max_workers=1)
            continue
        except Exception:
            stats['例外'] += 1
            continue
        stats[r.get('status', '?')] += 1
        if r.get('status') == 'solved':
            stats[f"  └ {r.get('verdict', 'unknown')}"] += 1
            solved.append({'id': p['id'], 'goal': goal, 'relations': relations[:3],
                           'answer': r.get('answer_latex'), 'verdict': r.get('verdict'),
                           'method': r.get('method')})
    pool.shutdown(wait=False, cancel_futures=True)
    sys.stderr.write('\r' + ' ' * 60 + '\r')
    return stats, solved


def main() -> int:
    problems = []
    for f in glob.glob(os.path.join(ROOT, 'data', 'mathexamtest', '*.json')):
        problems.extend(json.load(open(f, encoding='utf-8'))['problems'])
    problems = [p for p in problems if p.get('mathml')]
    print(f'MathML つきの問題 {len(problems)} 問\n')

    # 旧経路：MathML のタグを剥いた平文から $ 区切りを探す（区切りが無いので何も取れない）
    def old_extract(p):
        text = ' '.join(re.sub(r'<[^>]*>', ' ', m) for m in p['mathml'])
        text = re.sub(r'&[a-zA-Z]+;', ' ', text)
        segs = [s.strip() for s in re.split(r'[，、。]', text) if s.strip()]
        rel = [s for s in segs if REL.search(s)]
        cand = [s for s in segs if not REL.search(s)]
        return rel, (cand[-1] if cand else None)

    # 新経路：MathML の木から式を取る
    def new_extract(p):
        return split_problem(parse_math_elements(' '.join(p['mathml'])), p.get('body', ''))

    old_stats, _ = run(problems, old_extract, '旧')
    new_stats, new_solved = run(problems, new_extract, '新')

    n = len(problems)
    print(f"{'':26s} {'タグを剥いた平文':>16s} {'MathML':>10s}")
    keys = sorted(set(old_stats) | set(new_stats), key=lambda k: -(new_stats[k] + old_stats[k]))
    for k in keys:
        print(f'  {k:24s} {old_stats[k]:>16d} {new_stats[k]:>10d}')
    print()
    print(f'  解けた                   {old_stats["solved"]:>16d} {new_stats["solved"]:>10d}'
          f'   ({100*old_stats["solved"]/n:.1f}% → {100*new_stats["solved"]/n:.1f}%)')

    with open(os.path.join(ROOT, 'data', 'mathml-solved.json'), 'w', encoding='utf-8') as h:
        json.dump(new_solved, h, ensure_ascii=False, indent=2)

    print('\n解けた例:')
    for s in new_solved[:12]:
        print(f"  [{s['verdict']:20s}] {s['goal'][:44]:44s} = {str(s['answer'])[:34]}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
