# -*- coding: utf-8 -*-
"""ANSI つきのフレームを、実際の端末フォントで画像にする。

Cascadia Mono は Windows Terminal の既定フォントで、Braille 256 字を全て持つ。
つまりここで描いた絵は、同じ文字列を端末へ流したときの表示と同じである。

    python scripts/terminal/frames_to_png.py build/terminal/frames-2009G6 \
        --output build/terminal/png-2009G6 --cell-height 28
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SGR = re.compile(r"\x1b\[([0-9;]*)m")
FONT = Path("C:/Windows/Fonts/CascadiaMono.ttf")
GROUND = (5, 7, 10)          # MORTRA の地色
DEFAULT_FG = (232, 238, 242)


def parse(frame: str) -> list[list[tuple[str, tuple[int, int, int]]]]:
    """ANSI を剥がしつつ、文字ごとの色を持つ格子にする。"""
    rows = []
    for line in frame.split("\n"):
        cur = DEFAULT_FG
        out: list[tuple[str, tuple[int, int, int]]] = []
        i = 0
        while i < len(line):
            m = SGR.match(line, i)
            if m:
                p = m.group(1)
                if p in ("", "0"):
                    cur = DEFAULT_FG
                else:
                    f = p.split(";")
                    if len(f) == 5 and f[0] == "38" and f[1] == "2":
                        cur = (int(f[2]), int(f[3]), int(f[4]))
                i = m.end()
                continue
            out.append((line[i], cur))
            i += 1
        rows.append(out)
    return rows


def measure(font: ImageFont.FreeTypeFont) -> tuple[int, int]:
    """等幅の1セル。Braille の全点灯で高さを見る。"""
    a = font.getlength("M")
    b = font.getlength("\u28ff")
    if abs(a - b) > 0.51:
        raise SystemExit(f"等幅でない: M={a} braille={b}")
    asc, desc = font.getmetrics()
    return int(round(a)), asc + desc


def render(rows, font, cw, ch, pad) -> Image.Image:
    w = max(len(r) for r in rows) * cw + pad * 2
    h = len(rows) * ch + pad * 2
    img = Image.new("RGB", (w, h), GROUND)
    d = ImageDraw.Draw(img)
    for ri, row in enumerate(rows):
        y = pad + ri * ch
        # 同じ色が続く区間をまとめて描く
        i = 0
        while i < len(row):
            col = row[i][1]
            j = i
            while j < len(row) and row[j][1] == col:
                j += 1
            text = "".join(c for c, _ in row[i:j])
            d.text((pad + i * cw, y), text, font=font, fill=col)
            i = j
    return img


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("frames", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--cell-height", type=int, default=28,
                    help="1文字の高さ（px）。フォントサイズはここから決める")
    ap.add_argument("--pad", type=int, default=24)
    a = ap.parse_args()

    if not FONT.exists():
        raise SystemExit(f"フォントがありません: {FONT}")

    # 目標の行高に合うフォントサイズを探す
    size = a.cell_height
    while size > 4:
        f = ImageFont.truetype(str(FONT), size)
        asc, desc = f.getmetrics()
        if asc + desc <= a.cell_height:
            break
        size -= 1
    font = ImageFont.truetype(str(FONT), size)
    cw, ch = measure(font)
    ch = a.cell_height

    a.output.mkdir(parents=True, exist_ok=True)
    files = sorted(a.frames.glob("f*.txt"))
    if not files:
        raise SystemExit(f"フレームがありません: {a.frames}")

    size_wh = None
    for k, p in enumerate(files):
        rows = parse(p.read_text(encoding="utf-8"))
        img = render(rows, font, cw, ch, a.pad)
        if size_wh is None:
            size_wh = img.size
        elif img.size != size_wh:
            img = img.resize(size_wh)
        img.save(a.output / f"{k:05d}.png")

    print(f"  font      Cascadia Mono {size}px")
    print(f"  cell      {cw} x {ch} px")
    print(f"  frames    {len(files)}")
    print(f"  size      {size_wh[0]} x {size_wh[1]}")
    print(f"  -> {a.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
