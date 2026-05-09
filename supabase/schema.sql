-- ============================================================
-- math-corpus: Supabase schema
-- ============================================================

-- problems
CREATE TABLE IF NOT EXISTS problems (
  id            TEXT PRIMARY KEY,
  topic_a       TEXT NOT NULL,
  topic_b       TEXT,
  variation     INTEGER DEFAULT 0,
  statement     TEXT NOT NULL,
  answer        TEXT,
  difficulty    TEXT CHECK (difficulty IN ('A','B','C','D')),
  solution      TEXT,
  surprise      REAL DEFAULT 5.0,
  minimality    REAL DEFAULT 5.0,
  connection    REAL DEFAULT 5.0,
  inevitability REAL DEFAULT 5.0,
  diff_cal      REAL DEFAULT 5.0,
  total         REAL DEFAULT 5.0,
  inspiration   TEXT,
  meta          TEXT,
  generation    INTEGER DEFAULT 0,
  parent_ids    JSONB DEFAULT '[]',
  source_file   TEXT,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ratings
CREATE TABLE IF NOT EXISTS ratings (
  problem_id TEXT PRIMARY KEY REFERENCES problems(id) ON DELETE CASCADE,
  status     TEXT DEFAULT 'pending'
             CHECK (status IN ('pending','selected','rejected','posted')),
  x_posted   BOOLEAN DEFAULT FALSE,
  note       TEXT,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- indexes
CREATE INDEX IF NOT EXISTS idx_problems_topic_a    ON problems(topic_a);
CREATE INDEX IF NOT EXISTS idx_problems_difficulty ON problems(difficulty);
CREATE INDEX IF NOT EXISTS idx_problems_total      ON problems(total DESC);
CREATE INDEX IF NOT EXISTS idx_ratings_status      ON ratings(status);

-- generation_jobs: 非同期生成キュー
CREATE TABLE IF NOT EXISTS generation_jobs (
  id         TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  status     TEXT DEFAULT 'pending'
             CHECK (status IN ('pending','processing','done','failed')),
  user_id    TEXT,
  parents    JSONB NOT NULL,
  mode       TEXT NOT NULL DEFAULT 'auto',
  count      INTEGER NOT NULL DEFAULT 3,
  logs       JSONB DEFAULT '[]',   -- [{level, message, ts}]
  result     JSONB,                -- {ok, generated:[{id,statement}], total}
  error      TEXT,
  model      TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gen_jobs_status     ON generation_jobs(status);
CREATE INDEX IF NOT EXISTS idx_gen_jobs_user       ON generation_jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_gen_jobs_created    ON generation_jobs(created_at DESC);

-- Realtime 有効化（Supabase ダッシュボード > Database > Replication で generation_jobs を ON にすること）

-- Row Level Security (read-only public for MVP)
ALTER TABLE problems ENABLE ROW LEVEL SECURITY;
ALTER TABLE ratings  ENABLE ROW LEVEL SECURITY;

CREATE POLICY "public_read_problems" ON problems FOR SELECT USING (true);
CREATE POLICY "public_read_ratings"  ON ratings  FOR SELECT USING (true);

-- service_role can write (for migration and admin)
CREATE POLICY "service_write_problems" ON problems
  FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_write_ratings" ON ratings
  FOR ALL USING (auth.role() = 'service_role');
