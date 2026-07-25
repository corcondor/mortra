// 作問ステーションの高スコア(難しい)問題を MathOS の新規性コーパス用に書き出す。
// 使い方: node --env-file=.env.local scripts/export-hard-problems.mjs [最低スコア]
import { createClient } from '@supabase/supabase-js'
import { writeFileSync, mkdirSync } from 'node:fs'
import { dirname } from 'node:path'

// --env-file が値の引用符を残すことがあるので剥がす。
const strip = (v) => (v ?? '').trim().replace(/^["']|["']$/g, '')
const url = strip(process.env.NEXT_PUBLIC_SUPABASE_URL)
const key = strip(process.env.SUPABASE_SERVICE_KEY)
if (!url || !key) {
  console.error('NEXT_PUBLIC_SUPABASE_URL / SUPABASE_SERVICE_KEY が未設定です (.env.local)')
  process.exit(1)
}
try {
  const u = new URL(url)
  console.log(`接続先ホスト: ${u.host}`) // URLは公開情報。鍵は表示しない。
} catch {
  console.error(`URL が不正です（引用符混入など）: ${JSON.stringify(url).slice(0, 40)}…`)
  process.exit(1)
}
// 接続確認: REST ルートへ直接 fetch し、失敗の真因(cause)を表示。
try {
  const r = await fetch(`${url}/rest/v1/`, { headers: { apikey: key } })
  console.log(`疎通OK: HTTP ${r.status}`)
} catch (e) {
  console.error('疎通NG: fetch failed')
  console.error('  真因:', e?.cause?.code || e?.cause?.message || e?.message)
  console.error('  → プロキシ/VPN(Tailscale等)経由、IPv6、またはSupabaseプロジェクト一時停止が疑わしい。')
  console.error('  → Supabaseダッシュボードでプロジェクトが Active か確認してください。')
  process.exit(1)
}

const minTotal = Number(process.argv[2] ?? 7)
const out =
  'C:/Users/81808/.openclaw/workspace/math_os_prototype/problem_synthesis/sakumon_hard.json'

const supabase = createClient(url, key, {
  auth: { persistSession: false, autoRefreshToken: false },
})

const { data, error } = await supabase
  .from('problems')
  .select('id, statement, answer, total, difficulty')
  .gte('total', minTotal)
  .order('total', { ascending: false })

if (error) {
  console.error('Supabase エラー:', error.message)
  process.exit(1)
}

const rows = (data ?? []).filter((r) => r.statement)
mkdirSync(dirname(out), { recursive: true })
writeFileSync(out, JSON.stringify(rows, null, 2), 'utf8')
console.log(`書き出し完了: ${rows.length} 問 (total>=${minTotal}) → ${out}`)
