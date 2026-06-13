"""
コーパス問題 (generation=-1) を DeepSeek で一括エンリッチする。

各問題に対して:
  - 問題文・解答を KaTeX 互換 LaTeX に清書（PDF抽出の壊れた数式を修復）
  - タグ (3-6個) / topic / 難易度 (1-10) / 想定配点 / 特徴 を生成
  - problems.statement, solution, difficulty, topic_a, meta を更新

使い方:
  python scripts/enrich-problems.py --limit 5 --dry-run   # 確認
  python scripts/enrich-problems.py                       # 全件実行
"""

import os
import re
import sys
import json
import time
import argparse
import urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from supabase import create_client
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / '.env.local')

SUPABASE_URL = os.environ['NEXT_PUBLIC_SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_KEY']
DEEPSEEK_KEY = os.environ['DEEPSEEK_API_KEY']
MODEL = os.environ.get('DEEPSEEK_MODEL', 'deepseek-chat')

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

LOG_FILE = ROOT / 'scripts' / 'enrich-progress.log'

VALID_TOPICS = {
    'calculus', 'algebra', 'geometry', 'number_theory', 'probability',
    'combinatorics', 'inequality', 'sequence', 'complex', 'polynomial',
    'trigonometry', 'integral', 'recurrence', 'other',
}

PROMPT = """以下はPDFやTeXファイルから機械抽出した大学入試レベルの数学問題です。
抽出過程で数式が壊れている可能性があります（例: 上付き添字の消失 x2→x^2、√記号の位置ズレ、
分数の崩れ、和記号Σの引数分離、行の混入・分断など）。数学的に意味が通るように復元してください。

# 問題文（原文）
{statement}

# 解答（原文・空または断片の場合あり）
{solution}

次のJSONオブジェクトのみを返してください:
{{
  "statement": "問題文をKaTeX互換のLaTeXで清書。インライン数式は$...$、別行立ては$$...$$。問題番号・配点表記・『(下書き用紙)』『— 2 —』等の紙面ノイズは除去。数学的内容は一切変えない。",
  "solution": "解答を同様に清書。原文が空・断片すぎて復元不能なら空文字列",
  "tags": ["接線", "極限", "はさみうち"],
  "topic": "calculus|algebra|geometry|number_theory|probability|combinatorics|inequality|sequence|complex|polynomial|trigonometry|integral|recurrence|other から1つ",
  "difficulty": 7,
  "points": 40,
  "features": "問題の特徴・狙い・解法の核心を1〜2文で"
}}

difficulty基準: 教科書例題=2, 共通テスト=4, 標準国立二次=5, 東大京大標準=7, 最難関・数オリ系=9
points: 入試での想定配点 20〜60 の整数
tags: 分野・解法テクニックを3〜6個"""


def log(msg: str):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def call_deepseek(statement: str, solution: str) -> dict | None:
    body = json.dumps({
        'model': MODEL,
        'max_tokens': 4096,
        'response_format': {'type': 'json_object'},
        'messages': [{
            'role': 'user',
            'content': PROMPT.format(statement=statement[:4000], solution=(solution or '')[:4000]),
        }],
    }).encode('utf-8')

    req = urllib.request.Request(
        'https://api.deepseek.com/chat/completions',
        data=body,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {DEEPSEEK_KEY}',
        },
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=180) as res:
                data = json.loads(res.read().decode('utf-8'))
            content = data['choices'][0]['message']['content']
            return json.loads(content)
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))
    return None


def enrich_one(row: dict, dry_run: bool) -> tuple[str, bool, str]:
    pid = row['id']
    try:
        result = call_deepseek(row['statement'], row.get('solution') or '')

        statement = (result.get('statement') or '').strip()
        if len(statement) < 20:
            return pid, False, 'statement too short after rewrite'

        tags = result.get('tags') or []
        topic = result.get('topic') or 'other'
        if topic not in VALID_TOPICS:
            topic = 'other'
        difficulty = result.get('difficulty')
        d10 = max(1, min(10, int(difficulty))) if difficulty else None
        # DBの difficulty 列は A-D の文字グレード
        letter = ('A' if d10 >= 9 else 'B' if d10 >= 7 else 'C' if d10 >= 4 else 'D') if d10 else None
        points = result.get('points')
        points = max(10, min(80, int(points))) if points else None
        features = (result.get('features') or '').strip()
        solution = (result.get('solution') or '').strip() or None

        meta = {}
        if row.get('meta'):
            try:
                meta = json.loads(row['meta'])
            except Exception:
                meta = {}
        meta.update({
            'tags': tags,
            'points': points,
            'features': features,
            'difficulty10': d10,
            'enriched_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'raw_statement': row['statement'][:2000],  # 原文保持（巻き戻し用）
        })

        if dry_run:
            return pid, True, f"[DRY] {topic} {letter}(d{d10}) {points}pt tags={tags} | {statement[:60]}"

        supabase.table('problems').update({
            'statement': statement,
            'solution': solution,
            'difficulty': letter,
            'topic_a': topic,
            'meta': json.dumps(meta, ensure_ascii=False),
        }).eq('id', pid).execute()

        return pid, True, f"{topic} {letter}(d{d10}) {points}pt | {statement[:50]}"
    except Exception as e:
        return pid, False, f"{e.__class__.__name__}: {e}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=0, help='0 = all')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--workers', type=int, default=6)
    args = parser.parse_args()

    # 未エンリッチの gen=-1 問題を取得
    q = supabase.table('problems').select('id, statement, solution, meta') \
        .eq('generation', -1).order('id')
    rows = q.execute().data

    # meta.enriched_at が無いものだけ
    pending = []
    for r in rows:
        meta = {}
        if r.get('meta'):
            try:
                meta = json.loads(r['meta'])
            except Exception:
                pass
        if not meta.get('enriched_at'):
            pending.append(r)

    if args.limit:
        pending = pending[:args.limit]

    log(f"対象: {len(pending)} 問 (全 gen=-1: {len(rows)} 問) workers={args.workers} dry_run={args.dry_run}")

    ok = err = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(enrich_one, r, args.dry_run): r['id'] for r in pending}
        for i, fut in enumerate(as_completed(futures), 1):
            pid, success, msg = fut.result()
            if success:
                ok += 1
                log(f"({i}/{len(pending)}) OK {pid[:8]} {msg}")
            else:
                err += 1
                log(f"({i}/{len(pending)}) ERR {pid[:8]} {msg}")

    log(f"完了: 成功 {ok} / 失敗 {err}")


if __name__ == '__main__':
    main()
