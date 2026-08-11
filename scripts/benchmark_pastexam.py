# -*- coding: utf-8 -*-
"""過去問DBの幾何証明問題を、未見データとして形式化器に通す。

条件は固定する。
    LLM        使わない
    外部API    使わない
    問題文     書き換えない（LaTeX の版面指示を落とすだけ）

出すのは「解けた率」ではなく、次を分けた数字。
    形式化率   問題文を型付き述語と座標に落とせたか
    証明率     そこから結論に到達したか
    誤証明率   到達したが、図の上で結論が成り立っていないもの（あってはならない）
落ちたものは理由で分類する。何が足りないかが次の作業指示になる。

    python scripts/benchmark_pastexam.py
    python scripts/benchmark_pastexam.py --univ 01_tokyo
"""
import json
import os
import re
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'worker', 'backend'))

from geometry_natural_formalizer import formalize_geometry_text  # noqa: E402


def strip_latex(text: str) -> str:
    """版面の指示だけ落とす。数学の中身には触らない。

    図の埋め込み（\\includegraphics{...jpg}）を消し損ねると、
    残った `jpg}` が結論の文頭に入って読めなくなる。実際に落ちていた。
    """
    t = text
    t = re.sub(r'\\includegraphics(?:\[[^\]]*\])?\{[^{}]*\}', ' ', t)
    t = re.sub(r'\\begin\{[^}]*\}|\\end\{[^}]*\}', ' ', t)
    t = re.sub(r'\\item\[[^\]]*\]|\\item', '。', t)
    t = re.sub(r'\\ding\{[^{}]*\}|\\hspace\{[^{}]*\}|\\vspace\{[^{}]*\}', ' ', t)
    t = re.sub(r'\\(?:displaystyle|quad|qquad|cdots|dots|hfill|noindent|par)\b', ' ', t)
    t = t.replace('\\\\', '。')
    t = t.replace('\\triangle', '△').replace('\\angle', '∠')
    t = t.replace('\\perp', '⊥').replace('\\parallel', '∥')
    t = re.sub(r'\\mathrm\{([^{}]*)\}|\\text\{([^{}]*)\}|\\mbox\{([^{}]*)\}', r'\1\2\3', t)
    # {90}° のような余分な波括弧を外す（数式の中身は触らない）
    t = re.sub(r'\{(\d+)\}', r'\1', t)
    t = re.sub(r'\$+', '', t)
    t = t.replace('，', '、').replace('．', '。')
    return re.sub(r'[ \t]+', ' ', t).strip()


def failure_reason(unresolved) -> str:
    """なぜ落ちたかを一語で。次に何を足すかの指示になるように分ける。"""
    joined = ' '.join(unresolved)
    if 'goal predicate' in joined:
        return '結論の関係が読めない'
    if 'nondegenerate numerical diagram' in joined:
        return '数値作図が退化'
    if 'unsupported typed predicate' in joined:
        return '未対応の述語'
    if 'ill-typed' in joined:
        return '型が合わない'
    if 'fewer than two' in joined:
        return '点が取れない'
    words = [w for w in unresolved if len(w) <= 6]
    return f"未対応の語: {', '.join(sorted(set(words))[:4])}" if words else 'その他'


def main() -> int:
    univ = None
    if '--univ' in sys.argv:
        univ = sys.argv[sys.argv.index('--univ') + 1]

    with open(os.path.join(ROOT, 'data', 'pastexam-geometry.json'), encoding='utf-8') as h:
        items = json.load(h)
    if univ:
        items = [p for p in items if str(p['source']).startswith(univ)]

    results = []
    for i, p in enumerate(items, 1):
        text = strip_latex(p['statement'])
        sys.stderr.write(f'\r{i}/{len(items)}')
        sys.stderr.flush()
        try:
            r = formalize_geometry_text(text, max_restarts=12)
            results.append({
                'id': p['id'], 'source': p['source'], 'text': text,
                'status': r.status,
                'reason': None if r.status == 'formalized' else failure_reason(r.unresolved_relations),
                'points': r.points,
                'predicates': [
                    {'name': q.name, 'args': list(q.points), 'constants': list(q.constants)}
                    for q in r.predicates
                ],
                'goal': ({'name': r.goal.name, 'args': list(r.goal.points)} if r.goal else None),
                'goals': [{'name': g.name, 'args': list(g.points)} for g in r.goals],
                'coordinates': {k: [v[0], v[1]] for k, v in r.coordinates.items()},
            })
        except Exception as exc:
            results.append({'id': p['id'], 'source': p['source'], 'text': text,
                            'status': 'error', 'reason': repr(exc)[:80]})
    sys.stderr.write('\r')

    out = os.path.join(ROOT, 'data', 'pastexam-formalized.json')
    with open(out, 'w', encoding='utf-8') as h:
        json.dump(results, h, ensure_ascii=False, indent=2)

    n = len(results)
    ok = [r for r in results if r['status'] == 'formalized']
    print(f'\n対象 {n} 問' + (f'（{univ}）' if univ else '（8大学）'))
    print(f'形式化 {len(ok)}/{n} = {100 * len(ok) / n:.1f}%\n')

    print('落ちた理由:')
    for reason, c in Counter(r['reason'] for r in results if r['status'] != 'formalized').most_common(12):
        print(f'  {c:4d}  {reason}')

    print('\n大学別の形式化:')
    for u in sorted({str(r['source']).split('/')[0] for r in results}):
        sub = [r for r in results if str(r['source']).startswith(u)]
        good = sum(1 for r in sub if r['status'] == 'formalized')
        print(f'  {u:14s} {good:3d}/{len(sub):3d}')

    if ok:
        print('\n形式化できた問題:')
        for r in ok:
            g = r['goal']
            print(f"  [{r['source']}] {g['name']}({','.join(g['args'])})" if g else f"  [{r['source']}]")
            print(f"      {r['text'][:110]}")

    print(f'\n→ data/pastexam-formalized.json')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
