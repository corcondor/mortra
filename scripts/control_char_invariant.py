# -*- coding: utf-8 -*-
"""ソース全体に制御文字が無いことを不変条件として課す。

Python の非raw文字列で `\b` と書くとバックスペース(0x08)になる。
これが正規表現に3回埋まった。
  収集器   <math\x08 になり MathML が一件も取れなかった
  CAS      関数判定が効かず I が虚数単位のままだった
どれも実行しても例外にならず、静かに間違った結果を出す。

以後は不変条件として検査する。個別に直すのをやめる。

    python scripts/control_char_invariant.py
"""
import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 改行・復帰・タブ以外の制御文字
CONTROL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')
NAMES = {0x08: 'BACKSPACE（\b を非raw文字列で書いた跡）', 0x07: 'BELL（\a）',
         0x0c: 'FORMFEED（\f）', 0x0b: 'VTAB（\v）', 0x1b: 'ESC'}

SKIP_DIRS = {'node_modules', '.next', '.git', 'export', 'data', 'dist', '__pycache__'}
EXTENSIONS = {'.py', '.ts', '.tsx', '.mts', '.mjs', '.js'}


def main() -> int:
    hits = []
    scanned = 0
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if os.path.splitext(name)[1] not in EXTENSIONS:
                continue
            path = os.path.join(base, name)
            try:
                text = open(path, encoding='utf-8').read()
            except (UnicodeDecodeError, OSError):
                continue
            scanned += 1
            for m in CONTROL.finditer(text):
                line = text.count('\n', 0, m.start()) + 1
                code = ord(m.group())
                hits.append((os.path.relpath(path, ROOT), line, code,
                             NAMES.get(code, f'0x{code:02x}')))

    print(f'走査 {scanned} ファイル')
    if not hits:
        print('制御文字なし')
        return 0
    print(f'\n制御文字 {len(hits)} 箇所:')
    for path, line, code, label in hits:
        print(f'  {path}:{line}  0x{code:02x}  {label}')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
