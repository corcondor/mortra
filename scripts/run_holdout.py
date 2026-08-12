# -*- coding: utf-8 -*-
"""固定した holdout で測る。dev とは分けて報告する。

    python scripts/run_holdout.py
"""
import glob
import io
import json
import os
import subprocess
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, 'worker', 'backend')
SEMANTICS = os.path.join(ROOT, 'worker', 'semantics')

BATCH = 10
BATCH_SECONDS = 75

WORKER = r'''
import json, sys
sys.path.insert(0, r"{backend}")
sys.path.insert(0, r"{semantics}")
import sympy as sp
from mathml_ast import parse_math
from solve_from_ast import solve_expressions, solve_full
from problem_ir import build_problem_ir, solve_with_routing

def run(p, mode):
    exprs = parse_math(" ".join(p["mathml"]))
    if not exprs:
        return {{"status": "parse_failed"}}
    if mode == "a3b":
        rel = [e for e in exprs if isinstance(e, (sp.Equality, sp.Rel))][:6]
        out = solve_full(rel, exprs, p.get("body", ""))
    elif mode == "a5":
        out = solve_with_routing(p.get("body", ""), exprs)
    else:
        ir = build_problem_ir(p.get("body", ""), exprs)
        if ir.goal is None:
            return {{"status": "no_goal", "stage": "goal"}}
        if ir.backend not in ("cas", "inequality"):
            return {{"status": "unsupported_backend", "detail": ir.backend,
                    "goal_operator": ir.goal.operator.value, "stage": "backend"}}
        if ir.goal_expression is None:
            return {{"status": "goal_not_expression",
                    "goal_operator": ir.goal.operator.value, "stage": "goal_expr"}}
        rel = list(ir.constraints)[:6] + list(ir.assumptions)[:4]
        out = solve_expressions(rel, ir.goal_expression)
        out["goal_operator"] = ir.goal.operator.value
        out["assumptions"] = len(ir.assumptions)
    out["parsed"] = True
    return out

payload = json.loads(sys.stdin.read())
mode = payload["mode"]
res = []
for p in payload["problems"]:
    try:
        r = run(p, mode)
    except Exception as exc:
        r = {{"status": "exception", "detail": repr(exc)[:80]}}
    res.append({{"id": p["id"], **{{k: v for k, v in r.items() if k != "answer"}}}})
sys.stdout.write(json.dumps(res, ensure_ascii=False, default=str))
'''.format(backend=BACKEND.replace(chr(92), chr(92) * 2),
           semantics=SEMANTICS.replace(chr(92), chr(92) * 2))


def run_batch(problems, mode):
    if not problems:
        return []
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    try:
        r = subprocess.run([sys.executable, '-c', WORKER],
                           input=json.dumps({'mode': mode, 'problems': problems}, ensure_ascii=False),
                           capture_output=True, text=True, encoding='utf-8',
                           timeout=BATCH_SECONDS, cwd=BACKEND, env=env)
        if r.returncode == 0 and r.stdout.strip():
            return json.loads(r.stdout)
    except Exception:
        pass
    if len(problems) == 1:
        return [{'id': problems[0]['id'], 'status': 'timeout'}]
    mid = len(problems) // 2
    return run_batch(problems[:mid], mode) + run_batch(problems[mid:], mode)


def bucket(r):
    st = r.get('status')
    if st == 'timeout':
        return 'timeout'
    if st in ('parse_failed', 'exception'):
        return 'parse_failed'
    if st == 'solver_error':
        return 'solver_failure'
    if st == 'unverified':
        return 'certified_wrong'
    if st == 'solved':
        return ('certified_correct' if r.get('verdict') in ('proved', 'verified_instance')
                else 'certified_wrong')
    return 'abstained'


def evaluate(problems, mode, label):
    stats, residual, ops = Counter(), Counter(), Counter()
    for i in range(0, len(problems), BATCH):
        sys.stderr.write(f'\r{label} {i}/{len(problems)}   ')
        sys.stderr.flush()
        for r in run_batch(problems[i:i + BATCH], mode):
            stats[bucket(r)] += 1
            if bucket(r) == 'abstained':
                residual[r.get('status', '?')] += 1
            if r.get('goal_operator'):
                ops[r['goal_operator']] += 1
    sys.stderr.write('\r' + ' ' * 60 + '\r')
    return stats, residual, ops


def main() -> int:
    manifest = json.load(open(os.path.join(ROOT, 'data', 'holdout-manifest.json'), encoding='utf-8'))
    hold_ids = set(manifest['holdout']['ids'])
    dev_ids = set(manifest['dev']['ids'])

    all_problems = {}
    for f in glob.glob(os.path.join(ROOT, 'data', 'mathexamtest', '*.json')):
        for p in json.load(open(f, encoding='utf-8'))['problems']:
            if p.get('mathml'):
                all_problems[p['id']] = {'id': p['id'], 'mathml': p['mathml'],
                                         'body': p.get('body', '')}
    dev = [all_problems[i] for i in sorted(dev_ids) if i in all_problems]
    hold = [all_problems[i] for i in sorted(hold_ids) if i in all_problems]

    out = {}
    for name, problems in (('dev/regression', dev), ('holdout', hold)):
        print(f'\n{"=" * 62}\n{name}  {len(problems)} 問\n')
        for mode, label in (('a3b', 'A3b 本文の指示と条件'),
                            ('a4', 'A4 Discourse IR（routing のみ）'),
                            ('a5', 'A5 routing + 後退')):
            stats, residual, ops = evaluate(problems, mode, f'{name[:3]}/{mode}')
            n = len(problems)
            correct = stats['certified_correct']
            print(f'  {label}')
            print(f'    certified correct  {correct:4d}/{n} = {100 * correct / n:5.1f}%')
            print(f'    certified wrong    {stats["certified_wrong"]:4d}')
            print(f'    abstained          {stats["abstained"]:4d}')
            print(f'    solver failure     {stats["solver_failure"]:4d}')
            print(f'    parse failure      {stats["parse_failed"]:4d}')
            print(f'    timeout            {stats["timeout"]:4d}')
            if residual:
                print(f'    残差: ' + ', '.join(f'{k} {v}' for k, v in residual.most_common(5)))
            if ops:
                print(f'    目標: ' + ', '.join(f'{k} {v}' for k, v in ops.most_common(6)))
            out[f'{name}:{mode}'] = dict(stats)
            print()

    with open(os.path.join(ROOT, 'data', 'holdout-results.json'), 'w', encoding='utf-8') as h:
        json.dump(out, h, ensure_ascii=False, indent=2)
    print('→ data/holdout-results.json')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
