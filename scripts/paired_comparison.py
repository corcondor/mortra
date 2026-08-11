# -*- coding: utf-8 -*-
"""三経路を同一問題集合で比べ、対にした表で出す。

  平文        MathML のタグを剥いた文字列（以前やっていたこと）
  文字列AST   MathML を文字列に落としてから正規表現で直す（前回の経路）
  AST         MathML の木から直接 sympy を作る（今回）

段階を分けて数える。混ぜると「解けた率」が何を指すか分からなくなる。

  parsed            式として読めた
  executed          求解を試みた
  verified correct  独立な検証を通った
  wrong             検証に落ちた
  abstained         棄権した（読めない・範囲外・自明）
  timeout           時間切れ

中間値を最終結果として扱わない。全件を通す。

    python scripts/paired_comparison.py
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

BATCH = 10
BATCH_SECONDS = 75

WORKER = r'''
import json, sys, re
sys.path.insert(0, r"{backend}")
import sympy as sp
from mathml_ast import parse_math
from solve_from_ast import solve_expressions
import cas_solver as C

REL = re.compile(r"(?<![<>!=])=(?!=)|<=|>=|!=|<|>")

def run_ast(p):
    exprs = parse_math(" ".join(p["mathml"]))
    if not exprs:
        return {{"status": "parse_failed"}}
    relations = [e for e in exprs if isinstance(e, (sp.Equality, sp.Rel))]
    plain = [e for e in exprs
             if not isinstance(e, (sp.Equality, sp.Rel)) and getattr(e, "free_symbols", None) is not None]
    structured = [e for e in plain if e.has(sp.Integral, sp.Sum, sp.Limit)]
    goal = structured[-1] if structured else (plain[-1] if plain else None)
    if goal is None:
        return {{"status": "no_goal"}}
    out = solve_expressions(relations[:6], goal)
    out["parsed"] = True
    return out

def run_string(p, strip_tags):
    if strip_tags:
        text = " ".join(re.sub(r"<[^>]*>", " ", m) for m in p["mathml"])
        text = re.sub(r"&[a-zA-Z]+;", " ", text)
        segs = [s.strip() for s in re.split(r"[，、。\s]{{2,}}", text) if s.strip()]
    else:
        from mathml_to_sympy import parse_math_elements
        segs = parse_math_elements(" ".join(p["mathml"]))
    if not segs:
        return {{"status": "parse_failed"}}
    rel = [s for s in segs if REL.search(s)][:6]
    cand = [s for s in segs if not REL.search(s) and len(s) > 1]
    struct = [s for s in cand if any(k in s for k in ("Integral", "Sum", "Limit"))]
    goal = struct[-1] if struct else (cand[-1] if cand else None)
    if not goal or len(goal) > 240:
        return {{"status": "no_goal"}}
    out = C.solve_request({{"relations": rel, "goal": goal}})
    out["parsed"] = True
    return out

payload = json.loads(sys.stdin.read())
mode = payload["mode"]
out = []
for p in payload["problems"]:
    try:
        if mode == "ast":
            r = run_ast(p)
        elif mode == "string":
            r = run_string(p, strip_tags=False)
        else:
            r = run_string(p, strip_tags=True)
    except Exception as exc:
        r = {{"status": "exception", "detail": repr(exc)[:90]}}
    out.append({{"id": p["id"], **{{k: v for k, v in r.items() if k != "answer"}}}})
sys.stdout.write(json.dumps(out, ensure_ascii=False, default=str))
'''.format(backend=BACKEND.replace('\\', '\\\\'))


def run_batch(problems, mode):
    if not problems:
        return []
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    try:
        res = subprocess.run(
            [sys.executable, '-c', WORKER],
            input=json.dumps({'mode': mode, 'problems': problems}, ensure_ascii=False),
            capture_output=True, text=True, encoding='utf-8',
            timeout=BATCH_SECONDS, cwd=BACKEND, env=env)
        if res.returncode == 0 and res.stdout.strip():
            return json.loads(res.stdout)
    except subprocess.TimeoutExpired:
        pass
    except Exception:
        pass
    if len(problems) == 1:
        return [{'id': problems[0]['id'], 'status': 'timeout'}]
    mid = len(problems) // 2
    return run_batch(problems[:mid], mode) + run_batch(problems[mid:], mode)


def bucket(r) -> str:
    """段階に落とす。曖昧なものを correct に混ぜない"""
    st = r.get('status')
    if st == 'timeout':
        return 'timeout'
    if st in ('parse_failed', 'exception'):
        return 'parse_failed'
    if st in ('no_goal', 'goal_not_expression', 'goal_is_relation',
              'goal_unparsed', 'missing_goal', 'not_reduced'):
        return 'abstained'
    if st == 'solver_error':
        return 'executed_failed'
    if st == 'unverified':
        return 'wrong'
    if st == 'solved':
        verdict = r.get('verdict')
        if verdict in ('proved', 'verified_instance'):
            return 'verified_correct'
        if verdict == 'numerically_supported':
            return 'numerically_supported'
        return 'wrong'
    return 'abstained'


ORDER = ['parsed', 'executed', 'verified_correct', 'numerically_supported',
         'wrong', 'abstained', 'executed_failed', 'parse_failed', 'timeout']


def evaluate(problems, mode, label):
    stats = Counter()
    for i in range(0, len(problems), BATCH):
        sys.stderr.write(f'\r{label} {i}/{len(problems)}   ')
        sys.stderr.flush()
        for r in run_batch(problems[i:i + BATCH], mode):
            if r.get('parsed'):
                stats['parsed'] += 1
            b = bucket(r)
            stats[b] += 1
            if b in ('verified_correct', 'numerically_supported', 'wrong', 'executed_failed'):
                stats['executed'] += 1
    sys.stderr.write('\r' + ' ' * 60 + '\r')
    return stats


def main() -> int:
    problems = []
    for f in glob.glob(os.path.join(ROOT, 'data', 'mathexamtest', '*.json')):
        problems.extend(json.load(open(f, encoding='utf-8'))['problems'])
    problems = [{'id': p['id'], 'mathml': p['mathml']} for p in problems if p.get('mathml')]
    n = len(problems)
    print(f'同一問題集合 {n} 問。三経路を全件で比べる\n')

    results = {
        '平文（タグを剥ぐ）': evaluate(problems, 'plain', '平文'),
        '文字列AST（正規表現）': evaluate(problems, 'string', '文字列'),
        'AST（木から直接）': evaluate(problems, 'ast', 'AST'),
    }

    width = max(len(k) for k in results)
    print(f"{'':22s}" + ''.join(f'{k:>{width + 2}s}' for k in results))
    for key in ORDER:
        row = ''.join(f'{results[k][key]:>{width + 2}d}' for k in results)
        print(f'  {key:20s}{row}')
    print()
    for k, s in results.items():
        rate = 100 * s['verified_correct'] / n
        print(f'  {k:22s} verified correct {s["verified_correct"]:4d}/{n}  = {rate:5.1f}%')

    out = os.path.join(ROOT, 'data', 'paired-comparison.json')
    with open(out, 'w', encoding='utf-8') as h:
        json.dump({'total': n, 'results': {k: dict(v) for k, v in results.items()}},
                  h, ensure_ascii=False, indent=2)
    print(f'\n→ {os.path.relpath(out, ROOT)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
