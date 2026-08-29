# -*- coding: utf-8 -*-
"""12問の証明成果物を一覧する。

どの問題が動かせるか（連続変換を含むか）を見分けるための下調べ。
相似・鏡映・反転・回転は連続的に動かせる。それが図の運動になる。

    python scripts/survey_proof_charts.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(r'C:\Users\81808\.openclaw\workspace\mortra-1-release')
DATA = ROOT / 'data'

# 連続変換を示す語。これがあれば図をそのまま動かせる
MOTION = {
    'homothety': '相似変換', 'reflection': '鏡映', 'reflect': '鏡映',
    'inversion': '反転', 'rotation': '回転', 'projection': '射影',
    'midpoint': '中点', 'antipode': '対蹠', 'tangent': '接線',
    'radical': '根軸', 'pencil': '円束', 'centroid': '重心',
}


def main() -> None:
    rows = []
    for d in sorted(DATA.glob('hageo-exact-chart-*')):
        for svg in sorted(d.glob('*.proof-focus.svg')):
            name = svg.name.replace('.proof-focus.svg', '')
            pf = d / f'{name}.chart-portfolio.json'
            if not pf.exists():
                continue
            sel = json.load(open(pf, encoding='utf-8'))['selected']
            cert = sel['certificate']
            text = svg.read_text(encoding='utf-8')
            labels = re.findall(r'<!--\s*(.*?)\s*-->', text)
            pts = [l for l in labels if re.fullmatch(r'[A-Z][0-9]?', l)]

            words = ' '.join(cert.get('representation_chart', []) + cert.get('proof_dag', [])).lower()
            found = sorted({v for k, v in MOTION.items() if k in words})

            rows.append({
                'name': name,
                'chart': sel['chart_id'],
                'goal': sel['goal'],
                'ids': sel['identity_count'],
                'steps': len(cert.get('proof_dag', [])),
                'reps': len(cert.get('representation_chart', [])),
                'points': len(pts),
                'labels': [l for l in labels if not re.fullmatch(r'[A-Z][0-9]?', l)][:3],
                'motion': found,
            })

    hdr = '{:<20}{:>4}{:>4}{:>4}{:>4}  {:<28}{}'.format(
        '問題', '手', '式', '表現', '点', '目標', '含む変換')
    print(hdr)
    print('-' * 120)
    for r in sorted(rows, key=lambda x: -len(x['motion'])):
        print('{:<20}{:>4}{:>4}{:>4}{:>4}  {:<28}{}'.format(
            r['name'], r['steps'], r['ids'], r['reps'], r['points'],
            r['goal'][:27], ' / '.join(r['motion'])))

    print()
    print('図中の注記ラベル（動きの手がかり）')
    for r in rows:
        if r['labels']:
            print('  {:<20}{}'.format(r['name'], ' | '.join(r['labels'])))


if __name__ == '__main__':
    main()
