# -*- coding: utf-8 -*-
"""日本語の問題文 → 型付き述語 + 座標 → data/formalized-geometry.json

形式化器は数値作図までやるので、出てくる座標はその問題の制約を実際に満たしている。
図は後付けの挿絵ではなく、問題そのものから出ている。

    python scripts/formalize_corpus.py            全部
    python scripts/formalize_corpus.py --only 円  一部だけ（語彙を足したときの確認用）
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'worker', 'backend'))

from geometry_natural_formalizer import formalize_geometry_text  # noqa: E402

# 入試の言い回しをそのまま入れる。こちらの都合で書き換えない。
# 書き換えた瞬間に「解けた」は意味を失う。
CORPUS = [
    # ── 中点・中線 ────────────────────────────────────────────
    dict(id='midline', title='中点連結', tag='中点',
         text='三角形ABCにおいて、ABの中点をM、ACの中点をNとする。MNとBCは平行であることを示せ。'),
    dict(id='midline-triple', title='中点三角形', tag='中点',
         text='三角形ABCにおいて、ABの中点をM、ACの中点をN、BCの中点をLとする。MNとBCは平行であることを示せ。'),
    dict(id='centroid-median', title='重心は中線上', tag='重心',
         text='三角形ABCの重心をGとし、BCの中点をMとする。A、G、Mは同一直線上にあることを示せ。'),

    # ── 垂心・外心 ────────────────────────────────────────────
    dict(id='orthocenter-foot', title='垂心から下ろした足', tag='垂心',
         text='三角形ABCの垂心をHとする。AHとBCの交点をDとするとき、ADとBCは垂直であることを示せ。'),
    dict(id='circumcenter-midpoint', title='外心と辺の中点', tag='外心',
         text='三角形ABCの外心をOとする。BCの中点をMとするとき、OMとBCは垂直であることを示せ。'),
    dict(id='midline-perp-circumcenter', title='中点連結と外心', tag='合成',
         text='三角形ABCの外心をOとする。ABの中点をM、ACの中点をN、BCの中点をLとするとき、'
              'MNとOLは垂直であることを示せ。'),
    dict(id='midline-perp-orthocenter', title='中点連結と垂心', tag='合成',
         text='三角形ABCの垂心をHとする。ABの中点をM、ACの中点をNとする。'
              'AHとBCの交点をDとするとき、MNとADは垂直であることを示せ。'),

    # ── 垂線の足 ──────────────────────────────────────────────
    dict(id='foot-of-perp', title='垂線の足', tag='垂線',
         text='三角形ABCにおいて、AからBCに下ろした垂線の足をDとする。ADとBCは垂直であることを示せ。'),
    dict(id='foot-midline', title='垂線の足と中点連結', tag='合成',
         text='三角形ABCにおいて、AからBCに下ろした垂線の足をDとする。'
              'ABの中点をM、ACの中点をNとするとき、MNとADは垂直であることを示せ。'),
    dict(id='two-feet-parallel', title='二つの垂線の足', tag='垂線',
         text='三角形ABCにおいて、AからBCに下ろした垂線の足をD、ABの中点をM、ACの中点をNとする。'
              'ADとMNは垂直であることを示せ。'),

    # ── 内心・角の二等分線 ────────────────────────────────────
    dict(id='incenter-bisect', title='内心は角を二等分する', tag='内心',
         text='三角形ABCの内心をIとする。角BAIと角IACは等しいことを示せ。'),
    dict(id='bisector-foot', title='角の二等分線と対辺', tag='二等分線',
         text='三角形ABCにおいて、角BACの二等分線とBCの交点をDとする。'
              '角BADと角DACは等しいことを示せ。'),

    # ── 円・接線 ──────────────────────────────────────────────
    dict(id='tangent-radius', title='接線は半径に直交する', tag='接線',
         text='三角形ABCの外接円の中心をOとする。Aにおける円の接線上の点をTとするとき、'
              'OAとATは垂直であることを示せ。'),
    dict(id='thales', title='直径に立つ角は直角', tag='円',
         text='ABを直径とする円周上の点をPとする。APとBPは垂直であることを示せ。'),
    dict(id='tangent-named-center', title='中心が名指しされた接線', tag='接線',
         text='直線PQは中心Oの円に点Tで接する。PQとOTは垂直であることを示せ。'),

    # ── 四角形 ────────────────────────────────────────────────
    dict(id='parallelogram', title='平行四辺形の対辺', tag='四角形',
         text='平行四辺形ABCDにおいて、ABとDCは平行であることを示せ。'),
    dict(id='rectangle-perp', title='長方形の隣り合う辺', tag='四角形',
         text='長方形ABCDにおいて、ABとBCは垂直であることを示せ。'),
    dict(id='square-side', title='正方形の辺', tag='四角形',
         text='正方形ABCDにおいて、ABとBCは等しいことを示せ。'),
    dict(id='rhombus-parallel', title='ひし形の対辺', tag='四角形',
         text='ひし形ABCDにおいて、ABとDCは平行であることを示せ。'),

    # ── 二等辺・正三角形 ──────────────────────────────────────
    dict(id='isosceles-apex', title='二等辺三角形の頂点と底辺の中点', tag='二等辺',
         text='二等辺三角形ABCにおいて、BCの中点をMとする。AMとBCは垂直であることを示せ。'),
    dict(id='equilateral-median', title='正三角形の中線', tag='正三角形',
         text='正三角形ABCにおいて、BCの中点をMとする。AMとBCは垂直であることを示せ。'),

    # ── 内分・延長・線分上 ────────────────────────────────────
    dict(id='internal-division', title='内分点', tag='比',
         text='三角形ABCにおいて、ABを2:1に内分する点をPとする。A、P、Bは同一直線上にあることを示せ。'),
    dict(id='on-segment', title='線分上の点', tag='共線',
         text='三角形ABCにおいて、線分BC上の点をPとする。B、P、Cは同一直線上にあることを示せ。'),
]


def main() -> int:
    only = None
    if '--only' in sys.argv:
        only = sys.argv[sys.argv.index('--only') + 1]

    items = [c for c in CORPUS if not only or only in c['tag'] or only in c['id']]
    out = []
    for item in items:
        sys.stderr.write(f"{item['id']:26s} ")
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
                'goals': [{'name': g.name, 'args': list(g.points)} for g in r.goals],
                'coordinates': {k: [v[0], v[1]] for k, v in r.coordinates.items()},
                'residual': r.diagram_residual,
                'unresolved': r.unresolved_relations,
            })
            note = '' if r.status == 'formalized' else '  ' + '; '.join(r.unresolved_relations[:3])
            sys.stderr.write(f"{r.status}{note}\n")
        except Exception as exc:  # 形式化の失敗は結果の一部。落とさず記録する
            out.append({**item, 'status': 'error', 'error': repr(exc)})
            sys.stderr.write(f"ERROR {exc!r}\n")
        sys.stderr.flush()

    if only:
        sys.stderr.write(f"\n(--only {only}: 書き出しは省略)\n")
        return 0

    os.makedirs(os.path.join(ROOT, 'data'), exist_ok=True)
    target = os.path.join(ROOT, 'data', 'formalized-geometry.json')
    with open(target, 'w', encoding='utf-8') as handle:
        json.dump(out, handle, ensure_ascii=False, indent=2)

    ok = sum(1 for r in out if r['status'] == 'formalized')
    sys.stderr.write(f"\n形式化 {ok}/{len(out)} -> data/formalized-geometry.json\n")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
