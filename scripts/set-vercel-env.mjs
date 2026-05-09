#!/usr/bin/env node
/**
 * Vercel 環境変数を REST API で一括登録するスクリプト
 * 使い方:
 *   node scripts/set-vercel-env.mjs <VERCEL_TOKEN>
 *
 * トークン取得: https://vercel.com/account/tokens
 */

const TOKEN      = process.argv[2]
const PROJECT    = 'sakumon-web'
const TEAM_SLUG  = 'imtceed-3946s-projects'

if (!TOKEN) {
  console.error('Usage: node scripts/set-vercel-env.mjs <VERCEL_TOKEN>')
  console.error('Token: https://vercel.com/account/tokens')
  process.exit(1)
}

// ── 追加する環境変数 ──────────────────────────────────────────────────────
const ENVS = [
  { key: 'NEXT_PUBLIC_SUPABASE_URL',      value: 'https://dvzzsxczqatotgzlestu.supabase.co' },
  { key: 'NEXT_PUBLIC_SUPABASE_ANON_KEY', value: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImR2enpzeGN6cWF0b3Rnemxlc3R1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc5NzIwNjIsImV4cCI6MjA5MzU0ODA2Mn0.BCn9R7BWTrgKNH4p_DtLvIpLMboyt6NFYRFcGFjA0zM' },
  { key: 'SUPABASE_SERVICE_KEY',           value: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImR2enpzeGN6cWF0b3Rnemxlc3R1Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3Nzk3MjA2MiwiZXhwIjoyMDkzNTQ4MDYyfQ.TowYOtOLChN-py_4GArGPNgwLkSGhMIvgb_7iAGf_nQ' },
  { key: 'DEEPSEEK_API_KEY',               value: 'sk-799e1763cb3f4e0684756714bcdf1d51' },
  { key: 'DEEPSEEK_MODEL',                 value: 'deepseek-v4-pro' },
  { key: 'DEEPSEEK_HEALTH_MODEL',          value: 'deepseek-v4-flash' },
  { key: 'DEEPSEEK_MAX_TOKENS',            value: '4000' },
  { key: 'X_API_KEY',                      value: 'azmULTwrcUtTJfGXu5WErwsRv' },
  { key: 'X_API_SECRET',                   value: 'OLiwmlMfzLxhQKtOPhil9FUcSN2CWsU6Ekv4fHvjukNk7rs30W' },
  { key: 'X_ACCESS_TOKEN',                 value: '1570419317388484608-5kqzrfbZNWNpn8EZIyGudrO0IOUj5M' },
  { key: 'X_ACCESS_TOKEN_SECRET',          value: 'r5okzK3Vec8NED8KpKEiB5D3wKtSktcIqCssj4wDLRB3T' },
]

const TARGETS = ['production', 'preview', 'development']

// ── プロジェクト ID 取得 ───────────────────────────────────────────────────
async function getProjectId() {
  // まずチームスラグで試す
  for (const teamParam of [`?teamId=${TEAM_SLUG}`, '']) {
    const res = await fetch(`https://api.vercel.com/v9/projects/${PROJECT}${teamParam}`, {
      headers: { Authorization: `Bearer ${TOKEN}` },
    })
    if (res.ok) {
      const data = await res.json()
      console.log(`✅ Project found: ${data.id} (team: ${data.accountId ?? 'personal'})`)
      return { projectId: data.id, teamId: data.accountId }
    }
  }
  throw new Error('Project not found. Check PROJECT name and TOKEN permissions.')
}

// ── 環境変数を upsert ──────────────────────────────────────────────────────
async function upsertEnv(projectId, teamId, key, value) {
  const teamParam = teamId ? `?teamId=${teamId}` : ''
  const body = { key, value, type: 'encrypted', target: TARGETS }

  // 既存の一覧を取得して同名があれば PATCH, なければ POST
  const listRes = await fetch(
    `https://api.vercel.com/v10/projects/${projectId}/env${teamParam}`,
    { headers: { Authorization: `Bearer ${TOKEN}` } },
  )
  const list = listRes.ok ? (await listRes.json()).envs ?? [] : []
  const existing = list.filter(e => e.key === key)

  if (existing.length > 0) {
    // 既存を全削除してから再作成（target が違う場合があるため）
    for (const e of existing) {
      await fetch(`https://api.vercel.com/v10/projects/${projectId}/env/${e.id}${teamParam}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${TOKEN}` },
      })
    }
  }

  const res = await fetch(
    `https://api.vercel.com/v10/projects/${projectId}/env${teamParam}`,
    {
      method:  'POST',
      headers: { Authorization: `Bearer ${TOKEN}`, 'Content-Type': 'application/json' },
      body:    JSON.stringify(body),
    },
  )

  if (res.ok) {
    console.log(`  ✅ ${key}`)
  } else {
    const err = await res.text()
    console.log(`  ❌ ${key}: ${err.slice(0, 120)}`)
  }
}

// ── メイン ────────────────────────────────────────────────────────────────
;(async () => {
  console.log(`\n🚀 Vercel env vars → ${PROJECT}\n`)

  let projectId, teamId
  try {
    ;({ projectId, teamId } = await getProjectId())
  } catch (e) {
    console.error('❌', e.message)
    process.exit(1)
  }

  for (const { key, value } of ENVS) {
    await upsertEnv(projectId, teamId, key, value)
  }

  console.log('\n✨ 完了！Vercel Dashboard で Redeploy してください。')
  console.log(`   https://vercel.com/${TEAM_SLUG}/${PROJECT}/deployments`)
})()
