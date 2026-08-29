# -*- coding: utf-8 -*-
"""matplotlib が書き出した証明図から、点・ラベル・円・直線の実座標を取り出す。

図を作り直すのではなく、MORTRAが実際に出力した図の座標をそのまま読む。
出力した JSON を使って、証明の1手ごとに図を1段ずつ出す。

    python scripts/extract_proof_figure.py <svg> <out.json>
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# DejaVuSans のグリフ ID は Unicode コードポイントの16進
GLYPH = re.compile(r'xlink:href="#DejaVuSans-([0-9a-f]+)"\s+x="([\-\d.]+)"\s+y="([\-\d.]+)"')
USE = re.compile(r'<use[^>]*?x="([\-\d.]+)"\s+y="([\-\d.]+)"[^>]*?/>')
GROUP = re.compile(r'<g id="([^"]+)"[^>]*>(.*?)</g>\s*(?=<g id="|</g>)', re.S)
TRANSLATE = re.compile(r'translate\(([\-\d.]+)\s+([\-\d.]+)\)')
PATH_D = re.compile(r'<path[^>]*\sd="([^"]+)"', re.S)


def groups(svg: str) -> dict[str, str]:
    """トップレベル付近の <g id="..."> を素朴に切り出す"""
    out: dict[str, str] = {}
    for m in re.finditer(r'<g id="([^"]+)"', svg):
        name = m.group(1)
        start = m.end()
        depth = 1
        i = start
        while depth > 0 and i < len(svg):
            nxt_open = svg.find('<g', i)
            nxt_close = svg.find('</g>', i)
            if nxt_close == -1:
                break
            if nxt_open != -1 and nxt_open < nxt_close:
                depth += 1
                i = nxt_open + 2
            else:
                depth -= 1
                i = nxt_close + 4
        out[name] = svg[start:i]
    return out


COMMENT = re.compile(r'<!--\s*(.*?)\s*-->', re.S)


def label_of(chunk: str) -> tuple[str, float, float] | None:
    """text_N グループから、文字列と描画位置を復元する。

    matplotlib は各 text グループの先頭に `<!-- A -->` の形で元の文字列を
    そのまま残す。グリフを組み直すより確実なので、まずコメントを読む。
    位置は `transform="translate(x y) scale(0.1 -0.1)"` から取る。
    """
    tr = TRANSLATE.search(chunk)
    if not tr:
        return None
    ox, oy = float(tr.group(1)), float(tr.group(2))

    c = COMMENT.search(chunk)
    if c and c.group(1):
        return c.group(1), ox, oy

    # コメントが無い場合だけ、グリフの並びから復元する
    chars: list[tuple[float, str]] = []
    for g in GLYPH.finditer(chunk):
        chars.append((float(g.group(2)), chr(int(g.group(1), 16))))
    if not chars:
        return None
    chars.sort(key=lambda t: t[0])
    return ''.join(t[1] for t in chars), ox, oy


def points_of(chunk: str) -> list[tuple[float, float]]:
    """PathCollection の <use x= y=> をそのまま点として拾う"""
    return [(float(x), float(y)) for x, y in USE.findall(chunk)]


def main() -> int:
    svg_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])
    svg = svg_path.read_text(encoding='utf-8')

    gs = groups(svg)

    labels = []
    for name, chunk in gs.items():
        if not name.startswith('text_'):
            continue
        got = label_of(chunk)
        if got:
            labels.append({'text': got[0], 'x': got[1], 'y': got[2]})

    scatter = []
    for name, chunk in gs.items():
        if not name.startswith('PathCollection_'):
            continue
        pts = points_of(chunk)
        if pts:
            scatter.append({'group': name, 'points': [{'x': p[0], 'y': p[1]} for p in pts]})

    # 円・直線は path の d をそのまま持ち回る（描き直さない）
    paths = []
    for name, chunk in gs.items():
        if not (name.startswith('patch_') or name.startswith('line2d_')):
            continue
        for d in PATH_D.findall(chunk):
            if len(d) > 24:                      # 枠線のような短い矩形は捨てる
                paths.append({'group': name, 'd': d})

    vb = re.search(r'viewBox="([\d.\- ]+)"', svg)
    out = {
        'source_svg': str(svg_path).replace('\\', '/'),
        'viewBox': vb.group(1) if vb else None,
        'labels': labels,
        'scatter': scatter,
        'paths': paths,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')

    print(f'  ラベル {len(labels)} 個: ' + ', '.join(l['text'] for l in labels))
    print(f'  点群   {len(scatter)} 群 / 合計 {sum(len(s["points"]) for s in scatter)} 点')
    print(f'  パス   {len(paths)} 本')
    print(f'  -> {out_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
