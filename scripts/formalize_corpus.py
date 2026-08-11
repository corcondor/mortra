# -*- coding: utf-8 -*-
"""日本語の問題文 → 型付き述語 + 座標 → data/formalized-geometry.json

形式化器は数値作図までやるので、出てくる座標はその問題の制約を実際に満たしている。
図は後付けの挿絵ではなく、問題そのものから出ている。

    python scripts/formalize_corpus.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'worker', 'backend'))

from geometry_natural_formalizer import formalize_geometry_text  # noqa: E402

# 手を入れていない、入試の言い回しそのままの問題文
CORPUS = [
    dict(id='orthocenter-foot', title='垂心から下ろした足',
         text='三角形ABCの垂心をHとする。AHとBCの交点をDとするとき、ADとBCは垂直であることを示せ。'),
    dict(id='circumcenter-midpoint', title='外心と辺の中点',
         text='三角形ABCの外心をOとする。BCの中点をMとするとき、OMとBCは垂直であることを示せ。'),
    dict(id='midline', title='中点連結',
         text='三角形ABCにおいて、ABの中点をM、ACの中点をNとする。MNとBCは平行であることを示せ。'),
    dict(id='midline-triple', title='中点三角形',
         text='三角形ABCにおいて、ABの中点をM、ACの中点をN、BCの中点をLとする。MNとBCは平行であることを示せ。'),
    dict(id='centroid-median', title='重心は中線上',
         text='三角形ABCの重心をGとし、BCの中点をMとする。A、G、Mは同一直線上にあることを示せ。'),

    # ここから下は、規則が一本では届かない問題。
    # 別々の規則が合成して初めて結論に着く。射の語彙で解くとはこういうこと。
    dict(id='midline-perp-circumcenter', title='中点連結と外心',
         text='三角形ABCの外心をOとする。ABの中点をM、ACの中点をN、BCの中点をLとするとき、'
              'MNとOLは垂直であることを示せ。'),
    dict(id='midline-perp-orthocenter', title='中点連結と垂心',
         text='三角形ABCの垂心をHとする。ABの中点をM、ACの中点をNとする。'
              'AHとBCの交点をDとするとき、MNとADは垂直であることを示せ。'),
]


def main() -> int:
    out = []
    for item in CORPUS:
        sys.stderr.write(f"{item['id']:24s} ")
        sys.stderr.flush()
        try:
            # 制約を満たす図は複数ある。多めに集めてから読みやすい物を採る。
            # 書き出しは事前に一度やるだけなので、時間より見た目を優先する。
            r = formalize_geometry_text(item['text'], max_restarts=80)
            out.append({
                **item,
                'status': r.status,
                'points': r.points,
                'predicates': [
                    {'name': p.name, 'args': list(p.points), 'constants': list(p.constants)}
                    for p in r.predicates
                ],
                'goal': ({'name': r.goal.name, 'args': list(r.goal.points)} if r.goal else None),
                'coordinates': {k: [v[0], v[1]] for k, v in r.coordinates.items()},
                'residual': r.diagram_residual,
                'unresolved': r.unresolved_relations,
            })
            sys.stderr.write(f"{r.status}\n")
        except Exception as exc:  # 形式化の失敗は結果の一部。落とさず記録する
            out.append({**item, 'status': 'error', 'error': repr(exc)})
            sys.stderr.write(f"ERROR {exc!r}\n")
        sys.stderr.flush()

    os.makedirs(os.path.join(ROOT, 'data'), exist_ok=True)
    target = os.path.join(ROOT, 'data', 'formalized-geometry.json')
    with open(target, 'w', encoding='utf-8') as handle:
        json.dump(out, handle, ensure_ascii=False, indent=2)

    ok = sum(1 for r in out if r['status'] == 'formalized')
    sys.stderr.write(f"\n{ok}/{len(out)} formalized -> data/formalized-geometry.json\n")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
