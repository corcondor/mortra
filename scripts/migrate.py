"""
SQLite (curation.db) → Supabase 移行スクリプト
使い方:
  pip install supabase python-dotenv
  SUPABASE_URL=https://xxx.supabase.co SUPABASE_SERVICE_KEY=xxx python scripts/migrate.py
"""
import os, sys, json, sqlite3
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from supabase import create_client, Client

SQLITE_PATH = r"C:\Users\81808\.openclaw\workspace\math-dataset\curation.db"

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_KEY")   # service_role key (bypasses RLS)

if not url or not key:
    print("ERROR: set SUPABASE_URL and SUPABASE_SERVICE_KEY env vars")
    sys.exit(1)

sb: Client = create_client(url, key)

# ── read SQLite ─────────────────────────────────────────────
con = sqlite3.connect(SQLITE_PATH)
con.row_factory = sqlite3.Row

problems = con.execute("SELECT * FROM problems").fetchall()
ratings  = con.execute("SELECT * FROM ratings").fetchall()
con.close()
print(f"SQLite: {len(problems)} problems, {len(ratings)} ratings")

# ── helper ──────────────────────────────────────────────────
def normalize_problem(r: sqlite3.Row) -> dict:
    d = dict(r)
    # parent_ids: JSON string → python list
    try:
        d['parent_ids'] = json.loads(d.get('parent_ids') or '[]')
    except Exception:
        d['parent_ids'] = []
    # remove fields that don't exist in Supabase schema (none expected, but be safe)
    return d

def normalize_rating(r: sqlite3.Row) -> dict:
    d = dict(r)
    d['x_posted'] = bool(d.get('x_posted', 0))
    return d

# ── upsert problems (batched) ────────────────────────────────
BATCH = 50
problem_rows = [normalize_problem(p) for p in problems]

ok = 0
for i in range(0, len(problem_rows), BATCH):
    batch = problem_rows[i:i+BATCH]
    res = sb.table('problems').upsert(batch, on_conflict='id').execute()
    ok += len(batch)
    print(f"  problems upserted: {ok}/{len(problem_rows)}")

# ── upsert ratings ────────────────────────────────────────────
rating_rows = [normalize_rating(r) for r in ratings]
ok = 0
for i in range(0, len(rating_rows), BATCH):
    batch = rating_rows[i:i+BATCH]
    res = sb.table('ratings').upsert(batch, on_conflict='problem_id').execute()
    ok += len(batch)
    print(f"  ratings upserted: {ok}/{len(rating_rows)}")

# ── verify ────────────────────────────────────────────────────
total_p = sb.table('problems').select('id', count='exact').execute()
total_r = sb.table('ratings').select('problem_id', count='exact').execute()
print(f"\nSupabase: {total_p.count} problems, {total_r.count} ratings")
print("移行完了！")
