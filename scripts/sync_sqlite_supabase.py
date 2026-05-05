#!/usr/bin/env python3
"""
SQLite (curation.db) → Supabase 全量 upsert
新規生成問題を Supabase に反映する
使い方: python sync_sqlite_supabase.py
"""
import sys, os, json, sqlite3
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

try:
    import urllib.request
except ImportError:
    pass

DB_PATH      = "C:/Users/81808/.openclaw/workspace/math-dataset/curation.db"
SUPABASE_URL = os.environ.get("NEXT_PUBLIC_SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

STATUS_MAP = {'unseen': 'pending', 'seen': 'pending'}

def sb_request(method: str, path: str, body=None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('apikey',        SUPABASE_KEY)
    req.add_header('Authorization', f'Bearer {SUPABASE_KEY}')
    req.add_header('Content-Type',  'application/json')
    req.add_header('Prefer',        'resolution=merge-duplicates')
    with urllib.request.urlopen(req) as r:
        return r.status

def upsert_batch(table: str, rows: list, on_conflict='id'):
    if not rows:
        return
    path = f"{table}?on_conflict={on_conflict}"
    sb_request('POST', path, rows)

def sync():
    print("📂 SQLite を読み込み中...", flush=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row

    problems_raw = [dict(r) for r in con.execute("SELECT * FROM problems").fetchall()]
    ratings_raw  = [dict(r) for r in con.execute("SELECT * FROM ratings").fetchall()]
    con.close()

    print(f"   → 問題 {len(problems_raw)} 件 / 評価 {len(ratings_raw)} 件", flush=True)

    # problems → Supabase 形式
    problems = []
    for p in problems_raw:
        problems.append({
            'id':           p['id'],
            'topic_a':      p.get('topic_a', ''),
            'topic_b':      p.get('topic_b'),
            'variation':    p.get('variation', 0),
            'statement':    p.get('statement', ''),
            'answer':       p.get('answer', ''),
            'difficulty':   p.get('difficulty', 'C'),
            'solution':     p.get('solution'),
            'inspiration':  p.get('inspiration'),
            'surprise':     p.get('surprise'),
            'minimality':   p.get('minimality'),
            'connection':   p.get('connection'),
            'inevitability':p.get('inevitability'),
            'diff_cal':     p.get('diff_cal'),
            'total':        p.get('total'),
            'generation':   p.get('generation', 0),
            'parent_ids':   p.get('parent_ids'),
            'source_file':  p.get('source_file'),
        })

    # ratings → Supabase 形式
    ratings = []
    for r in ratings_raw:
        status = STATUS_MAP.get(r.get('status', 'pending'), r.get('status', 'pending'))
        ratings.append({
            'problem_id': r['problem_id'],
            'status':     status,
            'x_posted':   bool(r.get('x_posted', 0)),
            'note':       r.get('note'),
        })

    # バッチ upsert
    BATCH = 100
    print("☁️  Supabase に upsert 中...", flush=True)
    for i in range(0, len(problems), BATCH):
        upsert_batch('problems', problems[i:i+BATCH])
        print(f"   問題 {min(i+BATCH, len(problems))}/{len(problems)}", flush=True)

    for i in range(0, len(ratings), BATCH):
        upsert_batch('ratings', ratings[i:i+BATCH], on_conflict='problem_id')
        print(f"   評価 {min(i+BATCH, len(ratings))}/{len(ratings)}", flush=True)

    print(f"✅ 同期完了: {len(problems)} 問題, {len(ratings)} 評価", flush=True)

if __name__ == '__main__':
    sync()
