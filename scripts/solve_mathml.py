# -*- coding: utf-8 -*-
"""MathML 経路で解き、タグを剥いた平文経路と直接比べる。

束ごとに別プロセスで走らせる。Windows でプールを作り直すと壊れるため。
束が時間切れになったら、その束だけ半分に割って再試行する。
一問ずつ諦めるのではなく、まず束で試す。

    python scripts/solve_mathml.py
"""
import glob
import io
import json
import os
import re
import subprocess
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, 'worker', 'backend')
sys.path.insert(0, BACKEND)

from mathml_to_sympy import parse_math_elements  # noqa: E402

REL = re.compile(r'(?<![<>!=])=(?!=)|<=|>=|!=|<|>')
BATCH = 12
BATCH_SECONDS = 90


def solve_batch(items):
    """束を別プロセスで解く。時間切れなら半分に割る。割れなくなったら諦める"""
    if not items:
        return []
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    try:
        res = subprocess.run(
            [sys.executable, os.path.join(BACKEND, 'solve_batch.py')],
            input=json.dumps(items, ensure_ascii=False), capture_output=True,
            text=True, encoding='utf-8', timeout=BATCH_SECONDS, cwd=BACKEND, env=env)
        if res.returncode == 0 and res.stdout.strip():
            return json.loads(res.stdout)
    except subprocess.TimeoutExpired:
        pass
    except Exception:
        pass
    if len(items) == 1:
        return [{'id': items[0].get('id'), 'status': '打ち切り'}]
    mid = len(items) // 2
    return solve_batch(items[:mid]) + solve_batch(items[mid:])


def extract_mathml(p):
    exprs = parse_math_elements(' '.join(p['mathml']))
    relations = [e for e in exprs if REL.search(e)]
    candidates = [e for e in exprs if not REL.search(e) and len(e) > 1]
    structured = [e for e in candidates if any(k in e for k in ('Integral', 'Sum', 'Limit'))]
    goal = structured[-1] if structured else (candidates[-1] if candidates else None)
    return relations[:6], goal


def extract_plain(p):
    """タグを剥いた平文。以前やっていたこと"""
    text = ' '.join(re.sub(r'<[^>]*>', ' ', m) for m in p['mathml'])
    text = re.sub(r'&[a-zA-Z]+;', ' ', text)
    segs = [s.strip() for s in re.split(r'[，、。\s]{2,}', text) if s.strip()]
    rel = [s for s in segs if REL.search(s)]
    cand = [s for s in segs if not REL.search(s) and len(s) > 1]
    return rel[:6], (cand[-1] if cand else None)


def run(problems, extract, label):
    stats = Counter()
    items = []
    for p in problems:
        relations, goal = extract(p)
        if not goal or len(goal) > 240:
            stats['結論の式が取れない'] += 1
            continue
        items.append({'id': p['id'], 'relations': relations, 'goal': goal})

    solved = []
    for i in range(0, len(items), BATCH):
        chunk = items[i:i + BATCH]
        sys.stderr.write(f'\r{label} {i}/{len(items)}  solved {stats["solved"]}   ')
        sys.stderr.flush()
        for r in solve_batch(chunk):
            st = r.get('status', '?')
            stats[st] += 1
            if st == 'solved':
                stats[f"  └ {r.get('verdict', '-')}"] += 1
                src = next((c for c in chunk if c['id'] == r.get('id')), {})
                solved.append({**r, 'goal': src.get('goal'), 'relations': src.get('relations')})
    sys.stderr.write('\r' + ' ' * 70 + '\r')
    return stats, solved


def main() -> int:
    problems = []
    for f in glob.glob(os.path.join(ROOT, 'data', 'mathexamtest', '*.json')):
        problems.extend(json.load(open(f, encoding='utf-8'))['problems'])
    problems = [p for p in problems if p.get('mathml')]
    print(f'MathML つきの問題 {len(problems)} 問\n')

    old_stats, _ = run(problems, extract_plain, '平文')
    new_stats, new_solved = run(problems, extract_mathml, 'MathML')

    n = len(problems)
    print(f"{'':26s} {'タグを剥いた平文':>14s} {'MathML':>10s}")
    for k in sorted(set(old_stats) | set(new_stats), key=lambda k: -(new_stats[k] + old_stats[k])):
        print(f'  {k:24s} {old_stats[k]:>14d} {new_stats[k]:>10d}')
    print(f'\n  解けた                   {old_stats["solved"]:>14d} {new_stats["solved"]:>10d}'
          f'   ({100*old_stats["solved"]/n:.1f}% → {100*new_stats["solved"]/n:.1f}%)')

    with open(os.path.join(ROOT, 'data', 'mathml-solved.json'), 'w', encoding='utf-8') as h:
        json.dump(new_solved, h, ensure_ascii=False, indent=2)

    print('\n解けた例:')
    for s in new_solved[:14]:
        print(f"  [{str(s.get('verdict')):20s}] {str(s.get('goal'))[:40]:40s} = {str(s.get('answer_latex'))[:32]}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
