# -*- coding: utf-8 -*-
"""過去問を全件、CAS 実行層に通して答えを出す。

条件は固定。LLM なし、外部 API なし。
出すのは段階ごとの通過数と、答えが出た問題の一覧。

    python scripts/solve_pastexam.py [--limit N]
"""
import json
import os
import re
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, TimeoutError as FuturesTimeout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'worker', 'backend'))

import cas_solver as C  # noqa: E402

# 問題ごとに打ち切る。CAS は入力次第でいくらでも時間を使うので、
# 1問に上限を置かないと全件が終わらない。終わらない実行は結果ではない。
PER_PROBLEM_SECONDS = 6.0
MAX_UNKNOWNS = 5
MAX_RELATIONS = 6
MAX_CHARS = 240


def worth_trying(relations, goal) -> str | None:
    """明らかに手に負えないものは投げる前に落とす。理由を返す"""
    if len(relations) > MAX_RELATIONS:
        return '関係式が多すぎる'
    if len(goal) > MAX_CHARS or any(len(r) > MAX_CHARS for r in relations):
        return '式が長すぎる'
    blob = goal + ' '.join(relations)
    if len(set(re.findall(r'[a-zA-Z]', blob))) > MAX_UNKNOWNS * 3:
        return '記号が多すぎる'
    return None


def solve_one(payload):
    relations, goal = payload
    return C.solve_request({'relations': relations, 'goal': goal})

# 問題文から数式を取り出す。$...$ と \[...\]
SEG = re.compile(r'\$\$(.+?)\$\$|\$([^$]+)\$|\\\[(.+?)\\\]', re.S)
REL = re.compile(r'(?<![<>!])=(?!=)|\\le|\\ge|\\neq|≦|≧|<|>')
# 「〜を求めよ」の直前にある数式が目標になっていることが多い
ASK = re.compile(r'(?:を)?(?:求めよ|求めなさい|答えよ|示せ|証明せよ)')


def segments(text: str):
    for m in SEG.finditer(text):
        s = (m.group(1) or m.group(2) or m.group(3) or '').strip()
        if s:
            yield s, m.start()


def split_problem(text: str):
    """関係式と目標を分ける。

    目標は「求めよ」の直前の数式。無ければ最後の非関係式。
    関係式は目標以外で = や不等号を含むもの。
    """
    segs = list(segments(text))
    if not segs:
        return [], None

    goal = None
    ask = ASK.search(text)
    if ask:
        before = [(s, p) for s, p in segs if p < ask.start()]
        for s, _ in reversed(before):
            if not REL.search(s):
                goal = s
                break
    if goal is None:
        for s, _ in reversed(segs):
            if not REL.search(s):
                goal = s
                break

    relations = [s for s, _ in segs if REL.search(s) and s != goal]
    return relations, goal


def main() -> int:
    limit = int(sys.argv[sys.argv.index('--limit') + 1]) if '--limit' in sys.argv else None
    src = os.path.join(ROOT, 'worker', 'artifacts', 'pastexam-5369.jsonl')
    rows = [json.loads(line) for line in open(src, encoding='utf-8')]
    if limit:
        rows = rows[:limit]

    stats = Counter()
    solved = []
    pool = ProcessPoolExecutor(max_workers=1)
    for i, row in enumerate(rows, 1):
        if i % 100 == 0:
            sys.stderr.write(f'\r{i}/{len(rows)}  解けた {stats["solved"]}')
            sys.stderr.flush()
        relations, goal = split_problem(row['statement'])
        if not goal:
            stats['数式の目標が取れない'] += 1
            continue
        skip = worth_trying(relations, goal)
        if skip:
            stats[skip] += 1
            continue
        future = pool.submit(solve_one, (relations, goal))
        try:
            r = future.result(timeout=PER_PROBLEM_SECONDS)
        except FuturesTimeout:
            stats['打ち切り'] += 1
            pool.shutdown(wait=False, cancel_futures=True)
            pool = ProcessPoolExecutor(max_workers=1)
            continue
        except Exception:
            stats['例外'] += 1
            continue
        stats[r.get('status', '?')] += 1
        if r.get('status') == 'solved':
            solved.append({
                'id': row['id'], 'univ': row.get('benchmark'),
                'goal': goal, 'relations': relations[:3],
                'answer': r.get('answer_latex'), 'method': r.get('method'),
            })
    sys.stderr.write('\r')

    n = len(rows)
    print(f'\n過去問 {n} 問を CAS 実行層に通した（LLM なし・外部 API なし）\n')
    for k, v in stats.most_common():
        print(f'  {k:22s} {v:5d}  {100 * v / n:5.1f}%')
    print(f'\n★ 答えが出て検証も通った: {stats["solved"]}/{n} = {100 * stats["solved"] / n:.1f}%')

    with open(os.path.join(ROOT, 'data', 'pastexam-solved.json'), 'w', encoding='utf-8') as h:
        json.dump(solved, h, ensure_ascii=False, indent=2)

    by_univ = Counter(s['univ'] for s in solved)
    print('\n大学別に答えが出た数:')
    for k, v in sorted(by_univ.items()):
        print(f'  {k:14s} {v}')

    print('\n答えが出た問題の例:')
    for s in solved[:10]:
        print(f"  [{s['univ']}] {s['method']:10s} {s['goal'][:40]} = {str(s['answer'])[:45]}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
