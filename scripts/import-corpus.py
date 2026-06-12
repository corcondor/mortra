"""
corpus/ の .tex ファイルと Google Drive の作問サークル PDF を
Supabase の problems テーブルに一括インポートする。

使い方:
  python scripts/import-corpus.py --dry-run    # 確認のみ
  python scripts/import-corpus.py              # 実際にインポート
  python scripts/import-corpus.py --source gdrive   # Google Drive PDFのみ
  python scripts/import-corpus.py --source corpus   # corpus/のみ
"""

import re
import json
import sys
import uuid
import argparse
from pathlib import Path

# Windows コンソール文字化け回避
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

try:
    from supabase import create_client
    from dotenv import load_dotenv
    import os
    load_dotenv(Path(__file__).parent.parent / '.env.local')
    SUPABASE_URL  = os.environ['NEXT_PUBLIC_SUPABASE_URL']
    SUPABASE_KEY  = os.environ['SUPABASE_SERVICE_KEY']
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    HAS_SUPABASE = True
except Exception as e:
    print(f"[WARN] Supabase未接続: {e}")
    HAS_SUPABASE = False

CORPUS_DIR  = Path(__file__).parent.parent.parent / '.openclaw' / 'workspace' / 'corpus'
GDRIVE_DIR  = Path('G:/マイドライブ/math-dataset')

# ── LaTeX → プレーンテキスト（最低限） ──────────────────────────────────

def strip_tex_cmds(text: str) -> str:
    """数式コマンドを残しつつ、レイアウト系コマンドだけ除去する軽量変換"""
    text = re.sub(r'\\(?:medskip|bigskip|smallskip|noindent|centering|hfill|vfill|newpage)\b', ' ', text)
    text = re.sub(r'\\(?:textbf|emph|textit)\{([^}]*)\}', r'\1', text)
    text = re.sub(r'%.*', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

# ── TeX ファイルのパース ──────────────────────────────────────────────────

def parse_tex_file(path: Path) -> list[dict]:
    """1ファイルから複数の問題を抽出する"""
    try:
        text = path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        text = path.read_text(encoding='cp932')

    problems = []

    # --- new_entries 形式: \subsection*{タイトル} + \begin{itembox}...\end{itembox} ---
    # subsection が itembox より前に現れる場合だけ多問題フォーマットとみなす
    _sub_m = re.search(r'\\subsection\*\{', text)
    _box_m = re.search(r'\\begin\{itembox\}', text)
    _is_multi = _sub_m and _box_m and _sub_m.start() < _box_m.start()
    if _is_multi:
        blocks = re.split(r'\\subsection\*\{([^}]+)\}', text)
        for i in range(1, len(blocks) - 1, 2):
            title = blocks[i].strip()
            body  = blocks[i + 1]

            # 問題文
            m = re.search(r'\\begin\{itembox\}[^}]*\}(.*?)\\end\{itembox\}', body, re.DOTALL)
            if not m:
                continue
            problem_raw = re.sub(r'\\begin\{flushright\}.*?\\end\{flushright\}', '', m.group(1), flags=re.DOTALL).strip()

            # 解答
            sol_raw = body[m.end():].strip()
            sol_m = re.search(r'\\textbf\{解答[^}]*\}[.．]?\s*\\?', sol_raw)
            if sol_m:
                sol_raw = sol_raw[sol_m.end():]

            problems.append({
                'title':    title,
                'statement': strip_tex_cmds(problem_raw),
                'solution':  strip_tex_cmds(sol_raw),
                'source':   path.name,
            })

    # --- 1問1ファイル形式: \begin{itembox}...\end{itembox} ---
    else:
        # itembox の引数は [l]{問題} / [c]{問題} / {問題} など様々
        m = re.search(r'\\begin\{itembox\}(?:\[[^\]]*\])?\{[^}]*\}(.*?)\\end\{itembox\}', text, re.DOTALL)
        if m:
            problem_raw = m.group(1).strip()
            problem_raw = re.sub(r'\\begin\{flushright\}.*?\\end\{flushright\}', '', problem_raw, flags=re.DOTALL).strip()

            # 解答セクションを広くマッチ: 模範解答, 解答, Answer, Solution
            sm = re.search(
                r'(?:\\section\*?\{(?:模範解答|解答|Answer|Solution)[^}]*\}'
                r'|\\noindent\\textbf\{(?:模範解答|解答)[^}]*\}(?:\\\\)?'
                r'|\\textbf\{解答[^}]*\}[.．]?\s*\\?)',
                text, re.DOTALL
            )
            sol_raw = text[sm.end():].strip() if sm else ''
            # \end{document} より前だけ取る
            sol_raw = re.split(r'\\end\{document\}', sol_raw)[0].strip()

            if problem_raw:
                problems.append({
                    'title':    path.stem,
                    'statement': strip_tex_cmds(problem_raw),
                    'solution':  strip_tex_cmds(sol_raw),
                    'source':   path.name,
                })

    return problems

# ── PDF パース（テキスト抽出） ────────────────────────────────────────────

def parse_pdf_file(path: Path) -> list[dict]:
    """PDF から問題を抽出（テキストベース）"""
    try:
        import pdfplumber
    except ImportError:
        print(f"  [SKIP] pdfplumber 未インストール: pip install pdfplumber")
        return []

    problems = []
    try:
        pdf_obj = pdfplumber.open(str(path))
    except Exception as e:
        print(f"  [SKIP] PDF開けず ({e.__class__.__name__}): {path.name}")
        return []
    with pdf_obj as pdf:
        full_text = '\n'.join(p.extract_text() or '' for p in pdf.pages)

    # 問題番号パターン: [1], (1), 問1, 第1問 などで分割
    blocks = re.split(r'\n(?=(?:\[?\d+\]?[\.\s]|問\s*\d+|第\s*\d+\s*問))', full_text)

    for block in blocks:
        block = block.strip()
        if len(block) < 30:
            continue
        # 解答部分を分離
        sol_m = re.search(r'(?:【解答】|解答[．.]\s*|Answer\s*:)', block)
        if sol_m:
            statement = block[:sol_m.start()].strip()
            solution  = block[sol_m.end():].strip()
        else:
            statement = block
            solution  = ''

        # タイトル（最初の1行）
        first_line = statement.split('\n')[0][:60]

        if len(statement) > 20:
            problems.append({
                'title':    first_line,
                'statement': statement,
                'solution':  solution,
                'source':   path.name,
            })

    return problems

# ── Supabase への挿入 ─────────────────────────────────────────────────────

def to_supabase_row(p: dict) -> dict:
    """problems テーブルのスキーマに合わせて変換"""
    # topic をタイトルから推定
    title = p['title']
    topic = 'geometry'
    for kw, t in [('確率','probability'),('整数','number_theory'),('積分','integral'),
                  ('漸化式','recurrence'),('複素','complex'),('多項式','polynomial'),
                  ('三角','trigonometry'),('不等式','inequality'),('代数','algebra'),
                  ('組み合わせ','combinatorics'),('幾何','geometry'),('通過領域','geometry')]:
        if kw in title:
            topic = t
            break

    return {
        'id':         str(uuid.uuid4()),
        'topic_a':    topic,
        'topic_b':    None,
        'variation':  0,
        'statement':  p['statement'],
        'answer':     None,
        'difficulty': None,
        'solution':   p['solution'] if p['solution'] else None,
        'surprise':   0, 'minimality': 0, 'connection': 0,
        'inevitability': 0, 'diff_cal': 0, 'total': 0,
        'generation':  -1,   # -1 = 手作りコーパス
        'parent_ids':  [],
        'source_file': p['source'],
        'meta':        json.dumps({'title': p['title']}, ensure_ascii=False),
    }

# ── メイン ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--source', choices=['corpus','gdrive','all'], default='all')
    args = parser.parse_args()

    all_problems = []

    # corpus/ の .tex ファイル
    if args.source in ('corpus', 'all') and CORPUS_DIR.exists():
        tex_files = list(CORPUS_DIR.glob('*.tex'))
        print(f"\n[corpus] {len(tex_files)} .tex ファイルを解析中...")
        for f in sorted(tex_files):
            probs = parse_tex_file(f)
            print(f"  {f.name}: {len(probs)} 問")
            all_problems.extend(probs)

    # Google Drive の作問サークルPDF
    if args.source in ('gdrive', 'all') and GDRIVE_DIR.exists():
        pdf_files = [f for f in GDRIVE_DIR.glob('*.pdf')
                     if re.search(r'作問|模試|総集|東工大', f.name)]
        print(f"\n[gdrive] {len(pdf_files)} PDFを解析中...")
        for f in sorted(pdf_files):
            probs = parse_pdf_file(f)
            print(f"  {f.name}: {len(probs)} 問")
            all_problems.extend(probs)

    print(f"\n合計: {len(all_problems)} 問")

    if args.dry_run:
        print("\n[DRY RUN] 最初の3問:")
        for p in all_problems[:3]:
            print(f"  [{p['source']}] {p['title'][:50]}")
            print(f"    問題: {p['statement'][:80]}...")
        return

    if not HAS_SUPABASE:
        print("[ERROR] Supabase に接続できません。.env.local を確認してください。")
        return

    # バッチ挿入（重複は source_file+title でスキップ）
    rows = [to_supabase_row(p) for p in all_problems]
    ok = err = 0
    for row in rows:
        try:
            supabase.table('problems').insert(row).execute()
            ok += 1
        except Exception as e:
            if 'duplicate' in str(e).lower():
                print(f"  [SKIP] 重複: {row['meta']}")
            else:
                print(f"  [ERR] {e}")
            err += 1

    print(f"\n完了: 成功 {ok} 問 / スキップ/エラー {err} 問")


if __name__ == '__main__':
    main()
