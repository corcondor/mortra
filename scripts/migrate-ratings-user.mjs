#!/usr/bin/env node
/**
 * ratings テーブルを per-user 対応に移行するスクリプト
 *
 * 変更内容:
 *  1. ratings に user_id UUID カラムを追加
 *  2. 既存レコードに管理者の user_id をバックフィル
 *  3. PK を (user_id, problem_id) の複合キーに変更
 *  4. RLS を有効化 (ユーザーは自分の ratings のみ見える)
 *  5. usage テーブルを作成 (月間生成数追跡)
 *  6. subscriptions テーブルを作成 (Stripe 課金)
 *
 * 実行前に確認: Supabase ダッシュボード → Authentication → Users で
 * imtceed@gmail.com の UUID を確認してください
 *
 * 実行:
 *   node scripts/migrate-ratings-user.mjs
 */

const SUPABASE_URL = 'https://dvzzsxczqatotgzlestu.supabase.co'
const SERVICE_KEY  = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImR2enpzeGN6cWF0b3Rnemxlc3R1Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3Nzk3MjA2MiwiZXhwIjoyMDkzNTQ4MDYyfQ.TowYOtOLChN-py_4GArGPNgwLkSGhMIvgb_7iAGf_nQ'
const ADMIN_EMAIL  = 'imtceed@gmail.com'

const headers = {
  apikey:        SERVICE_KEY,
  Authorization: `Bearer ${SERVICE_KEY}`,
  'Content-Type': 'application/json',
}

async function sql(query) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/rpc/exec_sql`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ query }),
  })
  if (!res.ok) {
    const txt = await res.text()
    throw new Error(`SQL 失敗: ${txt}`)
  }
  return res.json()
}

async function getAdminUserId() {
  // auth.users は REST API から直接取得できないので admin API を使う
  const res = await fetch(`${SUPABASE_URL}/auth/v1/admin/users?email=${encodeURIComponent(ADMIN_EMAIL)}`, {
    headers,
  })
  if (!res.ok) throw new Error(`admin users fetch failed: ${await res.text()}`)
  const data = await res.json()
  const user = (data.users ?? []).find(u => u.email === ADMIN_EMAIL)
  if (!user) throw new Error(`${ADMIN_EMAIL} のユーザーが見つかりません。まずログインしてください。`)
  return user.id
}

;(async () => {
  console.log('\n🔧 ratings テーブル per-user 移行開始...\n')

  // 1. 管理者 UUID 取得
  console.log('  📧 管理者 UUID 取得中...')
  const adminId = await getAdminUserId()
  console.log(`  ✅ 管理者 UUID: ${adminId}\n`)

  // Supabase SQL Editor から直接 SQL を実行する必要があります
  // このスクリプトでは実行する SQL を表示します
  const migrationSQL = `
-- =====================================================
-- Step 1: ratings テーブルに user_id を追加
-- =====================================================
ALTER TABLE ratings
  ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE;

-- =====================================================
-- Step 2: 既存レコードに管理者の UUID をバックフィル
-- =====================================================
UPDATE ratings
  SET user_id = '${adminId}'
  WHERE user_id IS NULL;

-- =====================================================
-- Step 3: user_id を NOT NULL に変更
-- =====================================================
ALTER TABLE ratings
  ALTER COLUMN user_id SET NOT NULL;

-- =====================================================
-- Step 4: 既存の PK 制約を削除して複合 PK に変更
-- =====================================================
-- 既存の PK 名を確認してから実行してください
-- ALTER TABLE ratings DROP CONSTRAINT ratings_pkey;
-- ALTER TABLE ratings ADD PRIMARY KEY (user_id, problem_id);

-- または UNIQUE 制約として追加する場合:
ALTER TABLE ratings
  DROP CONSTRAINT IF EXISTS ratings_pkey,
  ADD PRIMARY KEY (user_id, problem_id);

-- =====================================================
-- Step 5: RLS を有効化
-- =====================================================
ALTER TABLE ratings ENABLE ROW LEVEL SECURITY;

-- ユーザーは自分の ratings のみ CRUD 可能
DROP POLICY IF EXISTS "users_own_ratings" ON ratings;
CREATE POLICY "users_own_ratings" ON ratings
  FOR ALL
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

-- service_role は RLS をバイパスするので API Route は引き続き全レコードにアクセス可能

-- =====================================================
-- Step 6: usage テーブル作成 (月間生成数)
-- =====================================================
CREATE TABLE IF NOT EXISTS usage (
  user_id        UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  year_month     TEXT NOT NULL,  -- 例: '2026-05'
  generations_count INTEGER NOT NULL DEFAULT 0,
  updated_at     TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (user_id, year_month)
);

ALTER TABLE usage ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "users_own_usage" ON usage;
CREATE POLICY "users_own_usage" ON usage
  FOR SELECT
  USING (auth.uid() = user_id);

-- =====================================================
-- Step 7: subscriptions テーブル作成 (Stripe 課金)
-- =====================================================
CREATE TABLE IF NOT EXISTS subscriptions (
  user_id                 UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  stripe_customer_id      TEXT,
  stripe_subscription_id  TEXT,
  status                  TEXT NOT NULL DEFAULT 'free',  -- 'free' | 'active' | 'canceled'
  current_period_end      TIMESTAMPTZ,
  created_at              TIMESTAMPTZ DEFAULT NOW(),
  updated_at              TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "users_own_subscription" ON subscriptions;
CREATE POLICY "users_own_subscription" ON subscriptions
  FOR SELECT
  USING (auth.uid() = user_id);

-- =====================================================
-- Step 8: increment_usage RPC 関数を作成
-- =====================================================
CREATE OR REPLACE FUNCTION increment_usage(p_user_id UUID, p_year_month TEXT)
RETURNS void AS $$
BEGIN
  INSERT INTO usage (user_id, year_month, generations_count)
  VALUES (p_user_id, p_year_month, 1)
  ON CONFLICT (user_id, year_month)
  DO UPDATE SET
    generations_count = usage.generations_count + 1,
    updated_at = NOW();
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
`

  console.log('📋 以下の SQL を Supabase SQL Editor で実行してください:')
  console.log('   https://supabase.com/dashboard/project/dvzzsxczqatotgzlestu/sql/new')
  console.log('')
  console.log('━'.repeat(60))
  console.log(migrationSQL)
  console.log('━'.repeat(60))
  console.log('')
  console.log('✅ SQL を上記 URL で実行した後、アプリが per-user ratings に対応します。')
  console.log('')
  console.log('📌 次のステップ:')
  console.log('   1. 上記 SQL を Supabase SQL Editor でコピー & 実行')
  console.log('   2. Stripe ダッシュボードで月額プランを作成')
  console.log('      https://dashboard.stripe.com/products/create')
  console.log('   3. 以下の環境変数を Vercel に追加:')
  console.log('      STRIPE_SECRET_KEY=sk_live_...')
  console.log('      STRIPE_WEBHOOK_SECRET=whsec_...')
  console.log('      STRIPE_PRICE_ID=price_...')
  console.log('   4. Stripe Webhook エンドポイントを登録:')
  console.log('      URL: https://sakumon-web.vercel.app/api/billing/webhook')
  console.log('      イベント: checkout.session.completed, customer.subscription.updated, customer.subscription.deleted')
})()
