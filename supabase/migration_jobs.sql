-- ============================================================
-- 1. generation_jobs テーブル
-- ============================================================
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

CREATE INDEX IF NOT EXISTS idx_gen_jobs_status  ON generation_jobs(status);
CREATE INDEX IF NOT EXISTS idx_gen_jobs_user    ON generation_jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_gen_jobs_created ON generation_jobs(created_at DESC);

-- RLS
ALTER TABLE generation_jobs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "users_own_jobs" ON generation_jobs
  FOR ALL USING (
    user_id = auth.uid()::text
    OR auth.role() = 'service_role'
    OR user_id IS NULL
  );

-- ============================================================
-- 2. ログ追記 RPC（Worker が呼ぶ）
--    Worker が logs を append するたびに Realtime UPDATE が走る
-- ============================================================
CREATE OR REPLACE FUNCTION append_job_logs(
  p_job_id TEXT,
  p_logs   JSONB
) RETURNS void LANGUAGE sql AS $$
  UPDATE generation_jobs
  SET
    logs       = logs || p_logs,
    updated_at = NOW()
  WHERE id = p_job_id;
$$;

-- ============================================================
-- 3. Supabase Realtime 有効化
--    ダッシュボード > Database > Replication > generation_jobs をONにすること
--    または以下のコマンドを実行:
-- ============================================================
-- ALTER PUBLICATION supabase_realtime ADD TABLE generation_jobs;
