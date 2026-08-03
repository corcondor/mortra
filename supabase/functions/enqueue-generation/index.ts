// Supabase Edge Function: enqueue-generation
// 仕事: 認証・制限チェックして generation_jobs に INSERT し job_id を即返す
// 重い処理は Railway Worker が担当（タイムアウトなし）

import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const corsHeaders = {
  'Access-Control-Allow-Origin':  '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
}

const FREE_GENERATIONS_PER_MONTH = 10
const ADMIN_EMAIL = Deno.env.get('ADMIN_EMAIL') ?? 'imtceed@gmail.com'

function currentYearMonth(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' },
  })
}

Deno.serve(async (req: Request) => {
  if (req.method === 'OPTIONS') return new Response('ok', { headers: corsHeaders })

  const supabase = createClient(
    Deno.env.get('SUPABASE_URL')!,
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!,
  )

  // ── 認証 ──────────────────────────────────────────────────────────────────
  const token = req.headers.get('Authorization')?.replace(/^Bearer /, '') ?? null
  let userId: string | null = null, userEmail: string | null = null, isAdmin = false

  if (token) {
    const { data } = await supabase.auth.getUser(token)
    userId    = data.user?.id    ?? null
    userEmail = data.user?.email ?? null
    isAdmin   = userEmail === ADMIN_EMAIL
  }

  // ── 利用制限チェック ──────────────────────────────────────────────────────
  if (userId && !isAdmin) {
    const ym = currentYearMonth()
    const { data: usageData } = await supabase.from('usage')
      .select('generations_count').eq('user_id', userId).eq('year_month', ym).single()
    const used = (usageData?.generations_count as number) ?? 0

    const { data: subData } = await supabase.from('subscriptions')
      .select('status').eq('user_id', userId).single()
    const isPaid = subData?.status === 'active'

    if (!isPaid && used >= FREE_GENERATIONS_PER_MONTH) {
      return json({
        error: `無料枠（月${FREE_GENERATIONS_PER_MONTH}回）を使い切りました。`,
        code: 'USAGE_LIMIT_EXCEEDED', used, limit: FREE_GENERATIONS_PER_MONTH,
      }, 402)
    }
  }

  // ── リクエスト解析 ─────────────────────────────────────────────────────────
  let body: { parents?: unknown[]; mode?: string; count?: number; resume_job_id?: string }
  try { body = await req.json() }
  catch { return json({ error: 'invalid json' }, 400) }

  const githubToken = Deno.env.get('GITHUB_TOKEN')
  const githubRepo = Deno.env.get('GITHUB_REPO')
  const dispatch = async (jobId: string, mode: string) => {
    if (!githubToken || !githubRepo) return { dispatched: false, reason: 'github dispatch env missing' }
    const ghRes = await fetch(`https://api.github.com/repos/${githubRepo}/dispatches`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${githubToken}`,
        'Content-Type': 'application/json',
        Accept: 'application/vnd.github.v3+json',
      },
      body: JSON.stringify({
        event_type: 'generate-problem',
        client_payload: { job_id: jobId, mode },
      }),
    })
    if (!ghRes.ok) return { dispatched: false, reason: `${ghRes.status} ${await ghRes.text()}` }
    return { dispatched: true, reason: null }
  }

  if (body.resume_job_id) {
    const { data: existing, error: findError } = await supabase
      .from('generation_jobs')
      .select('id,status,mode,result,updated_at')
      .eq('id', body.resume_job_id)
      .single()
    if (findError || !existing) return json({ error: 'job not found' }, 404)
    if (existing.status !== 'processing' || existing.mode !== 'mathos_discovery') {
      return json({ resumed: false, reason: 'job is not an active research job' })
    }
    const state = (existing.result as { searchState?: { continuing?: boolean; next_attempt_at?: string | null } } | null)?.searchState
    const due = state?.continuing === true && (!state.next_attempt_at || Date.parse(state.next_attempt_at) <= Date.now())
    if (!due) return json({ resumed: false, reason: 'job is not due' })
    const updatedAt = Date.parse(existing.updated_at ?? '')
    if (Number.isFinite(updatedAt) && Date.now() - updatedAt < 90_000) {
      return json({ resumed: false, reason: 'resume request already sent recently' })
    }
    await supabase.from('generation_jobs').update({ updated_at: new Date().toISOString() }).eq('id', existing.id)
    const dispatched = await dispatch(existing.id, existing.mode)
    if (!dispatched.dispatched) return json({ resumed: false, reason: dispatched.reason }, 503)
    return json({ resumed: true, job_id: existing.id })
  }

  const { parents, mode = 'auto', count = 3 } = body

  if (!parents?.length) return json({ error: 'parents required' }, 400)

  // ── ジョブをキューに積む ──────────────────────────────────────────────────
  const { data: job, error: insertErr } = await supabase
    .from('generation_jobs')
    .insert({
      user_id: userId,
      parents,
      mode,
      count: Math.max(1, Math.min(Number(count) || 1, 10)),
      status: 'pending',
    })
    .select('id')
    .single()

  if (insertErr || !job) {
    return json({ error: `ジョブ作成失敗: ${insertErr?.message}` }, 500)
  }

  // ── GitHub Actions を起動（GITHUB_TOKEN が設定されている場合） ──────────
  const dispatched = await dispatch(job.id, mode)
  if (!dispatched.dispatched) console.error(`GitHub dispatch failed: ${dispatched.reason}`)
  // GITHUB_TOKEN 未設定 → 常駐 Worker（Render.com など）が自動ピックアップ

  // ── 即座に job_id を返す ──────────────────────────────────────────────────
  return json({ job_id: job.id, status: 'pending', dispatched: dispatched.dispatched })
})
