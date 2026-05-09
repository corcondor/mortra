/**
 * process-job.ts
 * GitHub Actions / Render Worker 兼用。
 * 環境変数 JOB_ID があれば単一ジョブを処理して終了。
 * なければポーリングループ（常駐サーバー用）。
 */

import { createClient } from '@supabase/supabase-js'

// ── 環境変数 ─────────────────────────────────────────────────────────────────
const SUPABASE_URL              = process.env.SUPABASE_URL!
const SUPABASE_SERVICE_ROLE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY!
const DEEPSEEK_API_KEY          = process.env.DEEPSEEK_API_KEY!
const MODEL       = process.env.DEEPSEEK_MODEL      ?? 'deepseek-chat'
const FAST_MODEL  = process.env.DEEPSEEK_FAST_MODEL ?? 'deepseek-chat'
const MAX_TOKENS  = Number(process.env.DEEPSEEK_MAX_TOKENS ?? (MODEL.includes('reasoner') ? '32000' : '8000'))
const FAST_MAX    = 6000

if (!SUPABASE_URL || !SUPABASE_SERVICE_ROLE_KEY || !DEEPSEEK_API_KEY) {
  console.error('必須環境変数が未設定: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, DEEPSEEK_API_KEY')
  process.exit(1)
}

const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

// ── 型 ───────────────────────────────────────────────────────────────────────
interface ParentProblem {
  id: string; statement: string; answer?: string | null
  solution?: string | null; inspiration?: string | null
  topic_a: string; topic_b?: string | null
}
interface LogEntry { level: string; message: string; ts: string }

// ── ログ ─────────────────────────────────────────────────────────────────────
let logBuf: LogEntry[] = []

function pushLog(message: string, level = 'info') {
  logBuf.push({ level, message, ts: new Date().toISOString() })
  console.log(`[${level.toUpperCase()}] ${message}`)
}

async function flushLogs(jobId: string) {
  if (!logBuf.length) return
  const batch = logBuf.splice(0)
  const { error } = await supabase.rpc('append_job_logs', { p_job_id: jobId, p_logs: batch })
  if (error) console.error('flushLogs:', error.message)
}

// ── DeepSeek ─────────────────────────────────────────────────────────────────
async function callDeepSeek(
  prompt: string, model = MODEL, maxTokens = MAX_TOKENS,
  onProgress?: (msg: string) => void,
): Promise<string> {
  const res = await fetch('https://api.deepseek.com/chat/completions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${DEEPSEEK_API_KEY}` },
    body: JSON.stringify({
      model, messages: [{ role: 'user', content: prompt }],
      stream: true, max_tokens: maxTokens,
      ...(model.includes('reasoner') ? { temperature: 1 } : {}),
    }),
  })
  if (!res.ok) throw new Error(`DeepSeek ${res.status}: ${(await res.text()).slice(0, 200)}`)
  if (!res.body) throw new Error('no body')

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const reader = (res.body as any).getReader() as ReadableStreamDefaultReader<Uint8Array>
  const dec = new TextDecoder()
  let full = '', reasoning = '', streamDone = false, finishReason = ''
  let lineBuf = '', received = 0, lastProg = Date.now()

  while (!streamDone) {
    const { done, value } = await reader.read()
    if (done) break
    lineBuf += dec.decode(value)
    const lines = lineBuf.split('\n'); lineBuf = lines.pop() ?? ''
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      const data = line.slice(6).trim()
      if (data === '[DONE]') { streamDone = true; break }
      try {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const p: any = JSON.parse(data)
        const delta = p.choices?.[0]?.delta
        const fr    = p.choices?.[0]?.finish_reason
        if (fr) finishReason = fr
        if (delta?.reasoning_content) { reasoning += delta.reasoning_content; received += delta.reasoning_content.length }
        if (delta?.content)           { full      += delta.content;           received += delta.content.length }
        if (onProgress && Date.now() - lastProg > 3500) {
          lastProg = Date.now()
          onProgress(`${reasoning && !full ? '推論' : '生成'}中... (${received} chars)`)
        }
      } catch { /* skip */ }
    }
  }
  if (!streamDone) {
    if (finishReason === 'length') throw new Error(`トークン上限(${maxTokens})`)
    if (!full && reasoning) throw new Error('推論が途中で切断されました')
    if (!full) throw new Error('応答なしで終了')
  }
  return full || reasoning
}

// ── JSON 抽出 ────────────────────────────────────────────────────────────────
function extractJson(text: string): Record<string, unknown> | null {
  const m = text.match(/```(?:json)?\s*([\s\S]*?)```/)
  const s = m ? m[1] : text
  const i = s.indexOf('{'), j = s.lastIndexOf('}')
  if (i < 0 || j < 0) return null
  try { return JSON.parse(s.slice(i, j + 1)) } catch { return null }
}

// ── プロンプト ────────────────────────────────────────────────────────────────
function fmt(p: ParentProblem, idx?: number): string {
  const h = idx != null ? `【問題${idx}】` : '【問題】'
  const l = [h, p.statement, `答え: ${p.answer ?? ''}`]
  if (p.solution)    l.push(`解法の骨格: ${p.solution}`)
  if (p.inspiration) l.push(`数学的洞察: ${p.inspiration}`)
  return l.join('\n')
}

const SYS = `あなたは数学オリンピアード・難関大学入試問題の作問専門家です。
美しい数学問題とは：驚き（非自明な結論）、最小性（余分な条件なし）、強い接続（複数分野の深い融合）、必然性（その答えしかありえない感覚）、難易度較正を備えています。

【最重要：数学的厳密性】
1. 問題の条件に矛盾・循環がないか確認する
2. 答えを実際に step-by-step で計算して確認する
3. 整数・有理数・既知定数（π,e,√n等）として表せるか確認する
4. 計算で確かめた答えのみを final_problem.answer に記載する

以下のJSON形式のみで出力（他の文章一切不要）:
\`\`\`json
{"inspiration":"...","exploration":[{"approach":"...","why_discard":"..."}],"drafts":[{"version":1,"problem_statement":"...","intended_answer":"...","self_critique":"..."},{"version":2,"problem_statement":"...","intended_answer":"...","self_critique":"..."},{"version":3,"problem_statement":"...","intended_answer":"...","self_critique":"..."}],"verification":{"computation":"step-by-step計算","answer_check":"LaTeX","problem_well_posed":true,"issues_found":null},"final_problem":{"statement":"LaTeX","answer":"LaTeX","solution_outline":"200字以内","difficulty":"A/B/C/D"},"beauty_analysis":{"surprise":8,"minimality":9,"connection_strength":8,"inevitability":9,"difficulty_calibration":7,"total":8.2,"comment":"..."},"meta":"..."}
\`\`\``

const makeAnalysis = (p: ParentProblem) =>
  `以下の数学問題を深く分析してください。\n\n${fmt(p)}\n\nJSON形式で返してください：\`\`\`json\n{"core_structure":"...","proof_skeleton":"...","beauty_source":"...","key_technique":"...","hidden_connection":"...","generalization":"...","weakness":"..."}\n\`\`\``

const makeSimilar = (p: ParentProblem, a?: Record<string,string>) => {
  const b = a ? `\n【構造分析】\n- 核心: ${a.core_structure??''}\n- 骨格: ${a.proof_skeleton??''}\n- 必然性: ${a.beauty_source??''}\n- 核心一手: ${a.key_technique??''}\n` : ''
  return `${SYS}\n\n以下の問題の類題を生成してください。${b}\n${fmt(p)}\n\n【指示】設定・数値は変える、解法の核心は保つ、答えは元と異なること。JSON形式のみで回答。`
}

const makeFusion = (ps: ParentProblem[]) =>
  `${SYS}\n\n# 親問題\n\n${ps.map((p,i)=>fmt(p,i+1)).join('\n\n')}\n\n---\n\n# タスク：「構造的融合」による新問題の作問\n\n## 目標：「京大の問い・東工大の手数」\n- 問題文は1つの問い（(1)(2)分割は絶対禁止）\n- 誘導なし・1-2文で「〜を求めよ」で終わる\n- 解法の中に融合がある（解く過程で別分野の道具が必要になる）\n- 答えはコンパクト（整数・分数・π,e,√等）\n\n## 手順\nStep1: 各親問題から「不可欠な一手」を言語化\nStep2: 核心が依存し合う状況を設計\nStep3: 最小の問題文を書く\nStep4: 解法と答えを検証\n\n## 禁止：(1)(2)分割、誘導・ヒント\n\nJSON形式のみで回答。`

const makeExpand = (p: ParentProblem) =>
  `${SYS}\n\n以下の問題を「より深い階層へ一般化」した問題を作ってください。\n\n${fmt(p)}\n\n【指示】背後の構造が鮮明になる一般化、元の問題が特殊ケースになる形。JSON形式のみで回答。`

const makeVerify = (stmt: string, ans: string, sol: string) =>
  `以下の数学問題の妥当性を検証してください。\n\n【問題文】${stmt}\n【答え】${ans}\n【解法】${sol}\n\n実際にstep-by-stepで計算し、以下JSONのみで回答：\n\`\`\`json\n{"step_by_step":"...","derived_answer":"LaTeX","answer_matches":true,"problem_well_posed":true,"issues":null,"confidence":8,"verdict":"PASS"}\n\`\`\``

// ── ユーティリティ ────────────────────────────────────────────────────────────
function randomHex(n = 6) {
  return Array.from({ length: n }, () => Math.floor(Math.random() * 16).toString(16)).join('')
}

function ym() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`
}

// ── 淘汰 ─────────────────────────────────────────────────────────────────────
async function purge(excludeIds: string[]) {
  const ex = new Set(excludeIds)
  type R = { id: string; rating?: { status?: string|null; x_posted?: boolean|null }[] }
  const { data } = await supabase.from('problems').select('id, rating:ratings(status,x_posted)')
  if (!data) return 0
  const ids = (data as R[]).filter(c => {
    if (ex.has(c.id)) return false
    const rs = Array.isArray(c.rating) ? c.rating : c.rating ? [c.rating] : []
    return rs.length === 0 || !rs.some(r => r.x_posted || r.status === 'selected' || r.status === 'posted')
  }).map(c => c.id)
  if (!ids.length) return 0
  await supabase.from('ratings').delete().in('problem_id', ids)
  const { count } = await supabase.from('problems').delete({ count: 'exact' }).in('id', ids)
  return count ?? ids.length
}

// ── メイン処理 ───────────────────────────────────────────────────────────────
async function processJob(jobId: string) {
  console.log(`Processing job: ${jobId}`)
  logBuf = []

  // まず processing に変更
  await supabase.from('generation_jobs').update({
    status: 'processing', model: MODEL, updated_at: new Date().toISOString(),
  }).eq('id', jobId)

  // ログを定期フラッシュ
  const flushInterval = setInterval(() => flushLogs(jobId), 3000)

  const log = (msg: string, level = 'info') => pushLog(msg, level)

  try {
    // ジョブ情報取得
    const { data: job, error } = await supabase
      .from('generation_jobs').select('*').eq('id', jobId).single()
    if (error || !job) throw new Error(`ジョブが見つかりません: ${error?.message}`)

    const parents   = job.parents as ParentProblem[]
    const mode      = String(job.mode ?? 'auto')
    const count     = Number(job.count) || 3
    const userId    = job.user_id as string | null
    const resolved  = mode === 'auto' ? (parents.length >= 2 ? 'fusion' : 'similar') : mode

    const { data: gd } = await supabase.from('problems')
      .select('generation').order('generation', { ascending: false }).limit(1).single()
    const nextGen = ((gd?.generation as number|null) ?? 0) + 1

    log(`[Worker] DeepSeek (${MODEL}) で ${resolved} 生成開始（${count}問）`)

    const generated: { id: string; statement: string }[] = []

    // 分析
    let analysis: Record<string,string> | undefined
    if (resolved !== 'fusion' && parents.length === 1) {
      log('問題を分析中...')
      const raw = await callDeepSeek(makeAnalysis(parents[0]), FAST_MODEL, FAST_MAX)
      const a = extractJson(raw)
      if (a) analysis = a as Record<string,string>
      log(`分析完了: ${analysis?.core_structure?.slice(0, 60) ?? 'OK'}`)
    }

    for (let i = 0; i < count; i++) {
      log(`生成中... (${i+1}/${count})`)
      const prompt = resolved === 'fusion' ? makeFusion(parents)
        : resolved === 'expand'            ? makeExpand(parents[i % parents.length])
        : makeSimilar(parents[i % parents.length], analysis)

      let data: Record<string,unknown> | null = null
      let lastErr = ''

      for (let attempt = 1; attempt <= 3; attempt++) {
        log(`DeepSeek 呼び出し (試行 ${attempt}/3)`)
        try {
          const raw = await callDeepSeek(prompt, MODEL, MAX_TOKENS, msg => log(msg))
          data = extractJson(raw)
          if (data) break
          lastErr = `JSON抽出失敗: ${raw.slice(0, 120)}`
          log(lastErr, 'warn')
        } catch(e) {
          lastErr = String(e)
          log(`DeepSeek エラー: ${lastErr}`, 'error')
          if (attempt < 3) { log('5秒後にリトライ...'); await new Promise(r=>setTimeout(r,5000)) }
        }
      }

      if (!data) { log(`生成失敗 (${i+1}問目): ${lastErr}`, 'error'); continue }

      data.id = randomHex(6)
      const fp  = (data.final_problem ?? {}) as Record<string,unknown>
      const ba  = (data.beauty_analysis ?? {}) as Record<string,unknown>
      const stmt = String(fp.statement ?? '')
      const ans  = String(fp.answer ?? '')
      const sol  = String(fp.solution_outline ?? '')

      // 検証
      const emb = (data.verification ?? {}) as Record<string,unknown>
      let ok = true
      if (emb.problem_well_posed === false) {
        log(`⚠ 問題不成立: ${emb.issues_found ?? ''}`, 'warn'); ok = false
      } else {
        log(`数学的妥当性を検証中... (${i+1}/${count})`)
        try {
          const vr = extractJson(await callDeepSeek(makeVerify(stmt, ans, sol), FAST_MODEL, FAST_MAX))
          if (vr) {
            const verdict = String(vr.verdict ?? '').toUpperCase()
            const conf    = Number(vr.confidence ?? 5)
            if (verdict === 'FAIL' || vr.problem_well_posed === false || conf < 5 || vr.answer_matches === false) {
              log(`⚠ 検証失敗 (verdict=${verdict}, conf=${conf})`, 'warn'); ok = false
            } else {
              log(`✓ 検証OK (verdict=${verdict}, conf=${conf})`)
              if (vr.derived_answer && vr.answer_matches === true) fp.answer = vr.derived_answer
            }
          }
        } catch(e) { log(`検証エラー（保存続行）: ${e}`, 'warn') }
      }
      if (!ok) continue

      // 保存
      log('Supabase に保存中...')
      const problem = {
        id: data.id as string,
        topic_a: parents[0]?.topic_a ?? 'unknown',
        topic_b: resolved === 'fusion' ? (parents[parents.length-1]?.topic_a ?? null) : (parents[0]?.topic_b ?? null),
        variation: 0, statement: stmt,
        answer: fp.answer as string ?? null,
        difficulty: fp.difficulty as string ?? null,
        solution: sol, inspiration: data.inspiration as string ?? null,
        meta: data.meta as string ?? null,
        surprise: Number(ba.surprise)||0, minimality: Number(ba.minimality)||0,
        connection: Number(ba.connection_strength)||0, inevitability: Number(ba.inevitability)||0,
        diff_cal: Number(ba.difficulty_calibration)||0, total: Number(ba.total)||0,
        generation: nextGen, parent_ids: parents.map(p=>p.id), source_file: null,
      }
      const { error: pe } = await supabase.from('problems').upsert(problem)
      if (pe) { log(`保存エラー: ${pe.message}`, 'error'); continue }

      await supabase.from('ratings').upsert(
        { user_id: userId ?? 'system', problem_id: problem.id, status: 'pending', x_posted: false },
        { onConflict: 'user_id,problem_id', ignoreDuplicates: true },
      )
      log(`保存完了 score=${ba.total ?? '?'} → ${stmt.slice(0, 50)}...`)
      generated.push({ id: problem.id, statement: problem.statement })

      if (userId) {
        await supabase.from('usage').upsert(
          { user_id: userId, year_month: ym(), generations_count: 1 },
          { onConflict: 'user_id,year_month', ignoreDuplicates: false },
        )
      }
    }

    // 淘汰
    log('未選択問題を淘汰中...')
    const del = await purge(generated.map(p=>p.id)).catch(()=>0)
    log(del > 0 ? `淘汰完了: ${del} 問削除` : '淘汰対象なし')

    const success = generated.length > 0
    log(success ? `完了: ${generated.length}/${count} 問生成` : `失敗: 0/${count} 問生成`)

    clearInterval(flushInterval)
    await flushLogs(jobId)
    await supabase.from('generation_jobs').update({
      status: success ? 'done' : 'failed',
      result: { ok: success, generated, total: count },
      updated_at: new Date().toISOString(),
    }).eq('id', jobId)

  } catch(e) {
    log(`予期しないエラー: ${e}`, 'error')
    clearInterval(flushInterval)
    await flushLogs(jobId)
    await supabase.from('generation_jobs').update({
      status: 'failed', error: String(e), updated_at: new Date().toISOString(),
    }).eq('id', jobId)
    process.exit(1)
  }
}

// ── エントリポイント ──────────────────────────────────────────────────────────
const targetJobId = process.env.JOB_ID

if (targetJobId) {
  // GitHub Actions モード: 1ジョブ処理して終了
  processJob(targetJobId).then(() => {
    console.log('Done.'); process.exit(0)
  }).catch(e => {
    console.error('Fatal:', e); process.exit(1)
  })
} else {
  // 常駐モード（Render.com など）: ポーリングループ
  const POLL_MS = Number(process.env.POLL_INTERVAL_MS ?? '3000')
  let busy = false

  async function poll() {
    if (busy) return
    busy = true
    try {
      const { data: job } = await supabase
        .from('generation_jobs').select('id').eq('status', 'pending')
        .order('created_at', { ascending: true }).limit(1).single()
      if (job) await processJob((job as {id:string}).id)
    } catch(e: unknown) {
      // PGRST116 = no rows（正常）
      if ((e as {code?:string}).code !== 'PGRST116') console.error('[poll]', e)
    } finally { busy = false }
  }

  console.log(`Worker 起動 (常駐モード): model=${MODEL}, poll=${POLL_MS}ms`)
  poll()
  setInterval(poll, POLL_MS)
  process.on('SIGTERM', () => process.exit(0))
  process.on('SIGINT',  () => process.exit(0))
}
