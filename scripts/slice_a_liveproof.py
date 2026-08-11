# -*- coding: utf-8 -*-
"""Slice A — MathML → 検証つき解答 → LiveProof の最小縦貫。

入口から出口まで一本で通す。途中で意味が切れていないことを、
provenance が全段で辿れることで示す。

  MathML → AST → scoped symbols → 制約グラフ → 検証つき解答
        → 依存グラフ → 同期した式・図・説明

LiveProof が作れない場合は、何が足りないかを分類する。
これが証明表現の品質要件になる。

    python scripts/slice_a_liveproof.py
"""
import glob
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'worker', 'backend'))

import sympy as sp  # noqa: E402
from mathml_ast import parse_math, Environment, build, scan_functions  # noqa: E402
from solve_from_ast import solve_expressions  # noqa: E402

# LiveProof が作れないときの分類（仕様 §7）
MISSING = {
    'missing_premise_dependency': '前提の依存が辿れない',
    'opaque_object': '対象が不透明で図に写せない',
    'missing_semantic_binding': '記号が何を指すか決まっていない',
    'missing_construction': '構成の手順が無い',
    'unexplained_algebraic_jump': '式の飛躍が説明できない',
    'unrenderable_relation': '関係が図にできない',
}

# 図にできる関係。これ以外は LiveProof の段にできない
RENDERABLE = {'Eq', 'Lt', 'Le', 'Gt', 'Ge'}


def build_scene(problem):
    """一問を LiveProof の段へ落とす。落とせない理由も返す"""
    exprs = parse_math(' '.join(problem['mathml']))
    if not exprs:
        return None, ['missing_semantic_binding']

    relations = [e for e in exprs if isinstance(e, (sp.Equality, sp.Rel))]
    plain = [e for e in exprs
             if not isinstance(e, (sp.Equality, sp.Rel)) and hasattr(e, 'free_symbols')]
    structured = [e for e in plain if e.has(sp.Integral, sp.Sum, sp.Limit)]
    goal = structured[-1] if structured else (plain[-1] if plain else None)
    if goal is None:
        return None, ['opaque_object']

    result = solve_expressions(relations[:6], goal)
    if result.get('status') != 'solved':
        reasons = []
        if result.get('status') in ('not_reduced', 'goal_not_expression'):
            reasons.append('unexplained_algebraic_jump')
        if not relations:
            reasons.append('missing_premise_dependency')
        return None, reasons or ['unexplained_algebraic_jump']

    # 段を組む。前提 → 目標 → 答え。各段が何を消費したかを持つ
    beats = []
    for i, r in enumerate(relations[:6]):
        renderable = type(r).__name__ in RENDERABLE
        beats.append({
            'index': i,
            'role': 'given',
            'claim': sp.latex(r),
            'consumes': sorted(str(s) for s in r.free_symbols),
            'focus': sorted(str(s) for s in r.free_symbols),
            'renderable': renderable,
            'certificate': None,
        })
    beats.append({
        'index': len(beats),
        'role': 'goal',
        'claim': f'{sp.latex(goal)} = {result.get("answer_latex")}',
        'consumes': sorted(str(s) for s in goal.free_symbols),
        'focus': sorted(str(s) for s in goal.free_symbols),
        'renderable': True,
        'certificate': {
            'method': result.get('method'),
            'verdict': result.get('verdict'),
            'symbolic': result.get('symbolic_check'),
            'numeric': result.get('numeric_check'),
        },
    })
    return {
        'id': problem['id'],
        'beats': beats,
        'answer': result.get('answer_latex'),
        'verdict': result.get('verdict'),
        'provenance': {
            'source': 'mathexamtest.jp MathML',
            'path': ['parse_math', 'scan_functions', 'resolve', 'solve_expressions'],
            'consumed': [sp.latex(r) for r in relations[:6]],
        },
    }, []


def main() -> int:
    problems = []
    for f in glob.glob(os.path.join(ROOT, 'data', 'mathexamtest', '*.json')):
        problems.extend(json.load(open(f, encoding='utf-8'))['problems'])
    problems = [p for p in problems if p.get('mathml')]

    scenes, reasons = [], {}
    for p in problems:
        try:
            scene, missing = build_scene(p)
        except Exception:
            scene, missing = None, ['opaque_object']
        if scene:
            scenes.append(scene)
        for m in missing:
            reasons[m] = reasons.get(m, 0) + 1

    n = len(problems)
    print(f'\nSlice A — MathML → 検証つき解答 → LiveProof（{n} 問）\n')
    print(f'  LiveProof が作れた   {len(scenes)}/{n} = {100 * len(scenes) / n:.1f}%')
    print('\n  作れなかった理由（証明表現の品質要件）:')
    for key, count in sorted(reasons.items(), key=lambda x: -x[1]):
        print(f'    {count:4d}  {MISSING.get(key, key)}')

    # 同期率。主張のある段が、注目対象を持ち、図にできるか
    total_beats = sum(len(s['beats']) for s in scenes)
    synced = sum(1 for s in scenes for b in s['beats'] if b['focus'] and b['renderable'])
    certified = sum(1 for s in scenes for b in s['beats'] if b['certificate'])
    print(f'\n  段の総数 {total_beats}')
    print(f'  proof-diagram 同期率  {synced}/{total_beats} = {100 * synced / max(1, total_beats):.1f}%')
    print(f'  証明書つきの段        {certified}/{total_beats}')

    if scenes:
        s = scenes[0]
        print(f'\n  例 [{s["id"]}]  verdict={s["verdict"]}')
        for b in s['beats']:
            tag = '与' if b['role'] == 'given' else '∴'
            cert = ''
            if b['certificate']:
                cert = f"  [{b['certificate']['method']} / {b['certificate']['verdict']}]"
            print(f"    {tag} {b['claim'][:66]}{cert}")
            print(f"       消費: {', '.join(b['consumes'][:6])}")
        print(f"    provenance: {' → '.join(s['provenance']['path'])}")

    out = os.path.join(ROOT, 'data', 'slice-a-liveproof.json')
    with open(out, 'w', encoding='utf-8') as h:
        json.dump({'total': n, 'scenes': scenes, 'missing': reasons}, h,
                  ensure_ascii=False, indent=2)
    print(f'\n→ {os.path.relpath(out, ROOT)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
