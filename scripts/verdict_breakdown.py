# -*- coding: utf-8 -*-
"""A5 の中身を verdict まで割って数える。

run_holdout.py の bucket() は verdict が proved / verified_instance 以外を
全部 certified_wrong に落とす。proof backend は disproved と
numerically_supported を返すので、この二つが「誤答」に化ける。

化けているのか、本当に誤答なのかを、ここで分けて数える。

    python scripts/verdict_breakdown.py [dev|holdout]
"""
import glob
import io
import json
import os
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, 'worker', 'backend')
SEMANTICS = os.path.join(ROOT, 'worker', 'semantics')

BATCH = 1
BATCH_SECONDS = int(os.environ.get('MORTRA_PROBLEM_TIMEOUT', '12'))
MAX_WORKERS = max(1, int(os.environ.get('MORTRA_BENCH_WORKERS', '4')))

WORKER = r'''
import json, os, sys
sys.path.insert(0, r"{backend}")
sys.path.insert(0, r"{semantics}")
from mathml_ast import parse_math, parse_math_document
from problem_ir import solve_with_routing

payload = json.loads(sys.stdin.read())
res = []
for p in payload["problems"]:
    try:
        if os.environ.get("MORTRA_LEGACY_FLAT_PARSE") == "1":
            exprs = parse_math(" ".join(p["mathml"]))
            slots = None
        else:
            parsed = parse_math_document(p["mathml"])
            exprs = parsed.expressions
            slots = parsed.slots
        if not exprs:
            r = {{"status": "parse_failed"}}
        else:
            r = solve_with_routing(p.get("body", ""), exprs, slots)
    except Exception as exc:
        r = {{"status": "exception", "detail": repr(exc)[:80]}}
    res.append({{"id": p["id"],
                "status": r.get("status"), "verdict": r.get("verdict"),
                "method": r.get("method"), "route": r.get("route"),
                "backend": r.get("backend"), "goal_operator": r.get("goal_operator"),
                "answer": str(r.get("answer_latex"))[:70]}})
sys.stdout.write(json.dumps(res, ensure_ascii=False, default=str))
'''.format(backend=BACKEND.replace(chr(92), chr(92) * 2),
           semantics=SEMANTICS.replace(chr(92), chr(92) * 2))


def run_batch(problems):
    if not problems:
        return []
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    try:
        r = subprocess.run([sys.executable, '-c', WORKER],
                           input=json.dumps({'problems': problems}, ensure_ascii=False),
                           capture_output=True, text=True, encoding='utf-8',
                           timeout=BATCH_SECONDS, cwd=BACKEND, env=env)
        if r.returncode == 0 and r.stdout.strip():
            return json.loads(r.stdout)
    except Exception:
        pass
    if len(problems) == 1:
        return [{'id': problems[0]['id'], 'status': 'timeout'}]
    mid = len(problems) // 2
    return run_batch(problems[:mid]) + run_batch(problems[mid:])


def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else 'dev'
    manifest = json.load(open(os.path.join(ROOT, 'data', 'holdout-manifest.json'), encoding='utf-8'))
    ids = set(manifest['dev' if which == 'dev' else 'holdout']['ids'])

    allp = {}
    for f in glob.glob(os.path.join(ROOT, 'data', 'mathexamtest', '*.json')):
        for p in json.load(open(f, encoding='utf-8'))['problems']:
            if p.get('mathml'):
                allp[p['id']] = {'id': p['id'], 'mathml': p['mathml'], 'body': p.get('body', '')}
    problems = [allp[i] for i in sorted(ids) if i in allp]
    n = len(problems)
    print(f'\n{which}  {n} 問。A5 の verdict を割って数える\n')

    rows = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        jobs = {pool.submit(run_batch, [problem]): problem['id'] for problem in problems}
        for done, future in enumerate(as_completed(jobs), 1):
            try:
                rows.extend(future.result())
            except Exception as exc:
                rows.append({'id': jobs[future], 'status': 'exception',
                             'detail': repr(exc)[:80]})
            sys.stderr.write(f'\r{done}/{n}   ')
            sys.stderr.flush()
    sys.stderr.write('\r' + ' ' * 40 + '\r')
    rows.sort(key=lambda row: row['id'])

    verdicts = Counter()
    for r in rows:
        if r.get('status') == 'solved':
            verdicts[r.get('verdict') or '?'] += 1
        else:
            verdicts[f"[{r.get('status')}]"] += 1

    print('  verdict の内訳')
    for k, v in verdicts.most_common():
        print(f'    {k:26s} {v:4d}')

    proved = verdicts['proved'] + verdicts['verified_instance']
    disproved = verdicts['disproved']
    numsup = verdicts['numerically_supported'] + verdicts['[numerically_supported]']
    print(f'\n  現行 bucket()   certified_correct {proved}   certified_wrong '
          f'{disproved + verdicts["unverified"]}')
    print(f'  内訳            disproved {disproved} / numerically_supported {numsup} '
          f'/ unverified {verdicts["unverified"]}')

    statuses = Counter(r.get('status') or '?' for r in rows)
    certified_wrong = disproved + verdicts['unverified']
    certified_total = proved + certified_wrong
    print('\n  必須集計')
    print(f'    total                   {n:4d}')
    print(f'    certified_correct       {proved:4d}')
    print(f'    certified_wrong         {certified_wrong:4d}')
    print(f'    proved                  {verdicts["proved"]:4d}')
    print(f'    verified_instance       {verdicts["verified_instance"]:4d}')
    print(f'    numerically_supported   {numsup:4d}')
    print(f'    abstained               '
          f'{n - certified_total - numsup - statuses["solver_error"] - statuses["timeout"]:4d}')
    for key in ('unsupported_backend', 'not_reduced', 'goal_not_meaningful',
                'goal_is_relation', 'solver_error', 'timeout', 'parse_failed', 'exception'):
        print(f'    {key:23s} {statuses[key]:4d}')

    print('\n  proof backend が触った問題（route=discourse, backend=proof）')
    pb = [r for r in rows if r.get('backend') == 'proof' and r.get('route') == 'discourse']
    by = Counter(r.get('verdict') for r in pb)
    for k, v in by.most_common():
        print(f'    {str(k):26s} {v:4d}')
    for r in pb[:6]:
        print(f"      [{r['id']}] {r.get('verdict')} / {r.get('method')} → {r.get('answer')}")

    suffix = '-legacy-flat' if os.environ.get('MORTRA_LEGACY_FLAT_PARSE') == '1' else ''
    out = os.path.join(ROOT, 'data', f'verdict-breakdown-{which}{suffix}.json')
    with open(out, 'w', encoding='utf-8') as h:
        json.dump({'total': n, 'rows': rows}, h, ensure_ascii=False, indent=2)
    print(f'\n→ {os.path.relpath(out, ROOT)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
