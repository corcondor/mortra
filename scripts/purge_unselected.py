#!/usr/bin/env python3
"""
selected / posted 以外の問題を SQLite + Supabase から削除する
使い方: python purge_unselected.py
"""
import sys, os, json, sqlite3
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import urllib.request

DB_PATH      = "C:/Users/81808/.openclaw/workspace/math-dataset/curation.db"
SUPABASE_URL = os.environ.get("NEXT_PUBLIC_SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

KEEP_STATUSES = ('selected', 'posted')

def sb_delete_batch(ids: list):
    if not ids:
        return
    ids_str = ','.join(ids)
    url = f"{SUPABASE_URL}/rest/v1/problems?id=in.({ids_str})"
    req = urllib.request.Request(url, method='DELETE')
    req.add_header('apikey',        SUPABASE_KEY)
    req.add_header('Authorization', f'Bearer {SUPABASE_KEY}')
    try:
        with urllib.request.urlopen(req) as r:
            pass
    except Exception as e:
        print(f"  ⚠️ Supabase 削除エラー: {e}", flush=True)

def purge():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row

    # 削除対象を取得
    rows = con.execute("""
        SELECT p.id FROM problems p
        LEFT JOIN ratings r ON p.id = r.problem_id
        WHERE r.problem_id IS NULL
           OR r.status NOT IN ('selected','posted')
    """).fetchall()
    to_delete = [r['id'] for r in rows]

    total_before = con.execute("SELECT COUNT(*) FROM problems").fetchone()[0]
    print(f"📊 削除前: {total_before} 問題", flush=True)
    print(f"🗑️  削除対象: {len(to_delete)} 件", flush=True)

    if not to_delete:
        print("✅ 削除対象なし", flush=True)
        con.close()
        print(json.dumps({"deleted": 0}), flush=True)
        return

    # SQLite から削除
    placeholders = ','.join('?' * len(to_delete))
    con.execute(f"DELETE FROM ratings  WHERE problem_id IN ({placeholders})", to_delete)
    con.execute(f"DELETE FROM problems WHERE id          IN ({placeholders})", to_delete)
    con.commit()

    total_after = con.execute("SELECT COUNT(*) FROM problems").fetchone()[0]
    con.close()
    print(f"   SQLite 削除完了: {total_after} 問題 残存", flush=True)

    # Supabase から削除（バッチ 50件）
    print("☁️  Supabase から削除中...", flush=True)
    BATCH = 50
    for i in range(0, len(to_delete), BATCH):
        sb_delete_batch(to_delete[i:i+BATCH])
        print(f"   {min(i+BATCH, len(to_delete))}/{len(to_delete)}", flush=True)

    print(f"✅ 淘汰完了: {len(to_delete)} 件削除", flush=True)
    print(json.dumps({"deleted": len(to_delete), "remaining": total_after}), flush=True)

if __name__ == '__main__':
    purge()
