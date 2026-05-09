/**
 * Sakumon Generation Worker
 * ─────────────────────────────────────────────────────────────────────────────
 * Railway 上で常駐する Node.js プロセス。タイムアウトなし。
 * generation_jobs テーブルを 3 秒おきにポーリングし、
 * pending なジョブを拾って DeepSeek に投げ、結果を Supabase に書き戻す。
 * Supabase Realtime 経由でブラウザにライブログが届く。
 */

import { createClient, SupabaseClient } from '@supabase/supabase-js'

// ── 型定義 ──────────────────────────────────────────────────────────────────
interface ParentProblem {
  id: string
  statement: string
  answer?: string | null
  solution?: string | null
  inspiration?: string | null
  topic_a: string
  topic_b?: string | null
}

interface LogEntry { level: string; message: string; ts: string }

// ── 環境変数 ─────────────────────────────────────────────────────────────────
const SUPABASE_URL             = process.env.SUPABASE_URL!
const SUPABASE_SERVICE_ROLE_KEY= process.env.SUPABASE_SERVICE_ROLE_KEY!
const DEEPSEEK_API_KEY         = process.env.DEEPSEEK_API_KEY!
const MODEL      = process.env.DEEPSEEK_MODEL      ?? 'deepseek-chat'
const FAST_MODEL = process.env.DEEPSEEK_FAST_MODEL ?? 'deepseek-chat'
const MAX_TOKENS      = Number(process.env.DEEPSEEK_MAX_TOKENS      ?? (MODEL.includes('reasoner') ? '32000' : '8000'))
const FAST_MAX_TOKENS = 6000
const POLL_MS         = Number(process.env.POLL_INTERVAL_MS ?? '3000')

// ── Supabase クライアント ────────────────────────────────────────────────────
const supabase: SupabaseClient = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

// ── ログユーティリティ ───────────────────────────────────────────────────────
// ジョブごとに pending logs をバッファし、まとめて DB に書く（Realtime 通知される）
let pendingLogs: LogEntry[] = []

async function flushLogs(jobId: string): Promise<void> {
  if (pendingLogs.length === 0) return
  const batch = pendingLogs.splice(0)   // atomic swap

  // logs 列を JSONB concatenate で追記
  await supabase.rpc('append_job_logs', { p_job_id: jobId, p_logs: batch })
    .catch(err => console.error('[flushLogs]', err))
}

function pushLog(jobId: string, message: string, level = 'info'): void {
  const entry: LogEntry = { level, message, ts: new Date().toISOString() }
  pendingLogs.push(entry)
  console.log(`[${jobId.slice(0,8)}] ${message}`)
}

// 定期フラッシュ（3秒ごと）
let flushTimer: ReturnType<typeof setInterval> | null = null
function startFlush(jobId: string) {
  flushTimer = setInterval(() => flushLogs(jobId), 3000)
}
function stopFlush(jobId: string) {
  if (flushTimer) { clearInterval(flushTimer); flushTimer = null }
  return flushLogs(jobId)   // 残りを全部書く
}

// ── DeepSeek API ─────────────────────────────────────────────────────────────
async function callDeepSeek(
  prompt: string,
  model    = MODEL,
  maxTokens= MAX_TOKENS,
  onProgress?: (msg: string) => void,
): Promise<string> {
  const isReasoner = model.includes('reasoner')
  const res = await fetch('https://api.deepseek.com/chat/completions', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${DEEPSEEK_API_KEY}` },
    body: JSON.stringify({
      model,
      messages:   [{ role: 'user', content: prompt }],
      stream:     true,
      max_tokens: maxTokens,
      ...(isReasoner ? { temperature: 1 } : {}),
    }),
  })

  if (!res.ok) {
    const body = await res.text()
    throw new Error(`DeepSeek HTTP ${res.status}: ${body.slice(0, 300)}`)
  }
  if (!res.body) throw new Error('no response body')

  const reader = (res.body as unknown as AsyncIterable<Uint8Array>)[Symbol.asyncIterator]
    ? res.body as unknown as AsyncIterable<Uint8Array>
    : null

  // Node 18+ の fetch は ReadableStream を返す
  // getReader() で読む
  // deno-lint-ignore no-explicit-any
  const getReader = (res.body as any).getReader?.bind(res.body)
  if (!getReader) throw new Error('getReader not available')

  const rawReader = getReader() as ReadableStreamDefaultReader<Uint8Array>
  const dec = new TextDecoder()
  let full = '', reasoning = '', streamDone = false, finishReason = ''
  let lineBuf = '', received = 0, lastProgress = Date.now()
  void reader   // silence unused warning

  while (!streamDone) {
    const { done, value } = await rawReader.read()
    if (done) break
    lineBuf += dec.decode(value)
    const lines = lineBuf.split('\n')
    lineBuf = lines.pop() ?? ''

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      const data = line.slice(6).trim()
      if (data === '[DONE]') { streamDone = true; break }
      try {
        // deno-lint-ignore no-explicit-any
        const parsed: any = JSON.parse(data)
        const delta = parsed.choices?.[0]?.delta
        const fr    = parsed.choices?.[0]?.finish_reason
        if (fr) finishReason = fr
        if (delta?.reasoning_content) { reasoning += delta.reasoning_content; received += delta.reasoning_content.length }
        if (delta?.content)           { full      += delta.content;           received += delta.content.length }
        if (onProgress && Date.now() - lastProgress > 3500) {
          lastProgress = Date.now()
          const kind = reasoning && !full ? '推論' : '生成'
          onProgress(`${kind}中... (${received} chars)`)
        }
      } catch { /* ignore parse errors */ }
    }
  }

  if (!streamDone) {
    if (finishReason === 'length') throw new Error(`トークン上限(${maxTokens})に達しました`)
    if (!full && reasoning) throw new Error(`推論が途中で切断されました (${reasoning.length} chars)`)
    if (!full) throw new Error('応答なしでストリーム終了')
  }
  if (!full && reasoning) full = reasoning
  return full
}

// ── JSON 抽出 ────────────────────────────────────────────────────────────────
function extractJson(text: string): Record<string, unknown> | null {
  const codeMatch = text.match(/```(?:json)?\s*([\s\S]*?)```/)
  const candidate = codeMatch ? codeMatch[1] : text
  const start = candidate.indexOf('{')
  const end   = candidate.lastIndexOf('}')
  if (start === -1 || end === -1) return null
  try { return JSON.parse(candidate.slice(start, end + 1)) } catch { return null }
}

// ── プロンプト（lib/prompts.ts と同内容・import不可のためインライン） ────────
function formatProblem(p: ParentProblem, idx?: number): string {
  const header = idx != null ? `【問題${idx}】` : '【問題】'
  const lines  = [header, p.statement, `答え: ${p.answer ?? ''}`]
  if (p.solution)    lines.push(`解法の骨格: ${p.solution}`)
  if (p.inspiration) lines.push(`数学的洞察: ${p.inspiration}`)
  return lines.join('\n')
}

const SYSTEM_INSTRUCTION = `あなたは数学オリンピアード・難関大学入試問題の作問専門家です。
美しい数学問題とは：驚き（非自明な結論）、最小性（余分な条件なし）、
強い接続（複数分野の深い融合）、必然性（その答えしかありえない感覚）、
難易度較正（解法の糸口は掴めるが完答は困難）を備えています。

【最重要：数学的厳密性】
問題を作成する前に以下を必ず守ること：
1. **問題の条件を確認**: 条件に矛盾・循環がないか、一意の解が存在するかを確認する
2. **答えを実際に計算する**: 解法の骨格に従い、紙に書くように step-by-step で計算し、答えを数値/式として確認する
3. **答えの妥当性チェック**: 整数・有理数・既知定数（π, e, √n等）として綺麗に表せるか確認する
4. **問題が成立することを保証**: 「なんとなくこうなりそう」ではなく、計算で確かめた答えのみを final_problem.answer に記載する

以下の厳密なJSON形式のみで出力してください（他の文章は一切不要）:
\`\`\`json
{
  "inspiration": "なぜこの2分野を組み合わせるか（3-5文）",
  "exploration": [{"approach":"...","why_discard":"..."}],
  "drafts": [
    {"version":1,"problem_statement":"初稿（LaTeX）","intended_answer":"答え","self_critique":"改善点"},
    {"version":2,"problem_statement":"改訂版（LaTeX）","intended_answer":"答え","self_critique":"改善点"},
    {"version":3,"problem_statement":"最終版（LaTeX）","intended_answer":"答え","self_critique":"採用理由"}
  ],
  "verification": {
    "computation": "答えを導く実際の計算過程（step-by-step、省略なし）",
    "answer_check": "計算で得られた答えの値（LaTeX）",
    "problem_well_posed": true,
    "issues_found": null
  },
  "final_problem": {
    "statement": "最終問題文（LaTeX完全版）",
    "answer": "答え（LaTeX）",
    "solution_outline": "解法の骨格（200字以内）",
    "difficulty": "A/B/C/D（A=最難）"
  },
  "beauty_analysis": {
    "surprise":8,"minimality":9,"connection_strength":8,
    "inevitability":9,"difficulty_calibration":7,"total":8.2,
    "comment":"美的分析（2-3文）"
  },
  "meta": "作問過程で発見した数学的洞察（1-2文）"
}
\`\`\``

function makeAnalysisPrompt(p: ParentProblem): string {
  return `以下の数学問題の「数学的構造と美しさの本質」を深く分析してください。\n\n${formatProblem(p)}\n\n以下の観点で分析し、JSONで返してください：\n\`\`\`json\n{"core_structure":"...","proof_skeleton":"...","beauty_source":"...","key_technique":"...","hidden_connection":"...","generalization":"...","weakness":"..."}\n\`\`\``
}

function makeSimilarPrompt(p: ParentProblem, analysis?: Record<string,string>): string {
  const block = analysis ? `\n【構造分析】\n- 核心的数学構造: ${analysis.core_structure??''}\n- 証明の骨格: ${analysis.proof_skeleton??''}\n- 必然性の源泉: ${analysis.beauty_source??''}\n- 解法の核心一手: ${analysis.key_technique??''}\n- 隠れた深い接続: ${analysis.hidden_connection??''}\n- 改善点: ${analysis.weakness??''}\n` : ''
  return `${SYSTEM_INSTRUCTION}\n\n以下の問題の「数学的構造・解法の骨格・必然性」を正確に引き継いだ類題を生成してください。${block}\n${formatProblem(p)}\n\n【類題生成の指示】\n1. 問題文は元の問題と同等かより短く・シンプルに\n2. 表面的な数値・関数・設定は変える\n3. 核心となる数学的構造・解法の鍵となる一手・答えが必然的に導かれる論理は保つ\n4. 単なる数値置き換えや言い換えは禁止\n5. 答えは元と異なること\n\nJSON形式のみで回答してください。`
}

function makeFusionPrompt(problems: ParentProblem[]): string {
  const probTexts = problems.map((p,i) => formatProblem(p, i+1)).join('\n\n')
  return `${SYSTEM_INSTRUCTION}\n\n# 参考にする親問題（解法の核心を抽出すること）\n\n${probTexts}\n\n---\n\n# あなたのタスク：「構造的融合」による新問題の作問\n\n## ゴールのイメージ：「京大の問い・東工大の手数」\n\n- **問題文は1つの問い**（絶対禁止：(1)(2)への分割）\n  - 誘導なし・ヒントなし・1文か2文で「〜を求めよ」で終わる\n- **解法の中に融合がある**\n  - 解いていく過程で突然、全く別の分野の道具が必要になる\n- **答えはコンパクト**：整数・分数・既知の定数（π, e, √など）\n\n## 作問手順\n**Step 1** 親問題それぞれから「解くときに不可欠な一手」を1つ言語化する\n**Step 2** 核心同士が「依存しあう」状況を設計する\n**Step 3** その依存関係を自然に誘導する最小の問題文を書く\n**Step 4** 解法と答えを検証する\n\n## 禁止事項（厳守）\n- **(1)(2)への分割** ── 最大の禁止事項\n- 誘導・ヒント・小問を問題文に入れること\n\nJSON形式のみで回答してください。`
}

function makeExpandPrompt(p: ParentProblem): string {
  return `${SYSTEM_INSTRUCTION}\n\n以下の問題を「より深い階層へ一般化」した問題を作ってください。\n\n${formatProblem(p)}\n\n【高次元化・一般化の指示】\n1. 背後にある数学的構造がより鮮明に見える一般化\n2. 元の問題が特殊ケースになる形が理想\n3. 答えのパラメータnや一般的な構造の美しい関数として表される\n\nJSON形式のみで回答してください。`
}

function makeVerificationPrompt(statement: string, answer: string, solution: string): string {
  return `以下の数学問題が数学的に正しく成立しているかを厳密に検証してください。\n\n【問題文】\n${statement}\n\n【想定される答え】\n${answer}\n\n【解法の骨格】\n${solution}\n\n検証手順：\n1. 問題文の条件が矛盾していないか確認する\n2. 解法の骨格に従い、step-by-step で実際に計算を行い、答えを導出する\n3. 導出した答えが「想定される答え」と一致するか確認する\n4. 問題の解が一意に定まるか確認する\n\n以下のJSON形式のみで回答してください（他の文章は一切不要）：\n\`\`\`json\n{"step_by_step":"実際の計算過程","derived_answer":"計算で得られた答え（LaTeX）","answer_matches":true,"problem_well_posed":true,"issues":null,"confidence":8,"verdict":"PASS"}\n\`\`\``
}

// ── ユーティリティ ───────────────────────────────────────────────────────────
function randomHex(bytes = 6): string {
  return [...Buffer.from(crypto.randomUUID().replace(/-/g,'')).slice(0, bytes)]
    .map(b => b.toString(16).padStart(2,'0')).join('').slice(0, bytes * 2)
}

function currentYearMonth(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`
}

// ── 淘汰 ─────────────────────────────────────────────────────────────────────
async function purgeUnselected(excludeIds: string[]): Promise<number> {
  const excluded = new Set(excludeIds)
  type Row = { id: string; rating?: {status?:string|null;x_posted?:boolean|null}[] | null }

  const { data } = await supabase.from('problems').select('id, rating:ratings(status,x_posted)')
  if (!data) return 0

  const ids = (data as Row[])
    .filter(c => {
      if (excluded.has(c.id)) return false
      const rs = Array.isArray(c.rating) ? c.rating : c.rating ? [c.rating] : []
      if (rs.length === 0) return true
      return !rs.some(r => r.x_posted === true || r.status === 'selected' || r.status === 'posted')
    })
    .map(c => c.id)

  if (!ids.length) return 0
  await supabase.from('ratings').delete().in('problem_id', ids)
  const { count } = await supabase.from('problems').delete({ count: 'exact' }).in('id', ids)
  return count ?? ids.length
}

// ── ジョブ処理 ───────────────────────────────────────────────────────────────
async function processJob(job: Record<string, unknown>): Promise<void> {
  const jobId   = job.id as string
  pendingLogs   = []

  const log = (message: string, level = 'info') => {
    pushLog(jobId, message, level)
  }

  // processing に変更
  await supabase.from('generation_jobs').update({
    status:     'processing',
    model:      MODEL,
    updated_at: new Date().toISOString(),
  }).eq('id', jobId)

  startFlush(jobId)

  const parents   = job.parents as ParentProblem[]
  const mode      = String(job.mode ?? 'auto')
  const count     = Number(job.count) || 3
  const userId    = job.user_id as string | null

  const resolvedMode = mode === 'auto' ? (parents.length >= 2 ? 'fusion' : 'similar') : mode

  const { data: genData } = await supabase.from('problems')
    .select('generation').order('generation', { ascending: false }).limit(1).single()
  const nextGen = ((genData?.generation as number|null) ?? 0) + 1

  const generated: { id: string; statement: string }[] = []

  try {
    log(`[Worker] DeepSeek (${MODEL}) で ${resolvedMode} 生成開始（${count}問）`)

    // 分析フェーズ
    let analysis: Record<string,string> | undefined
    if (resolvedMode !== 'fusion' && parents.length === 1) {
      log('問題を分析中...')
      const raw = await callDeepSeek(makeAnalysisPrompt(parents[0]), FAST_MODEL, FAST_MAX_TOKENS)
      const a = extractJson(raw)
      if (a) analysis = a as Record<string,string>
      log(`分析完了: ${analysis?.core_structure?.slice(0, 60) ?? 'OK'}`)
    }

    for (let i = 0; i < count; i++) {
      log(`生成中... (${i+1}/${count})`)

      const prompt = resolvedMode === 'fusion'  ? makeFusionPrompt(parents)
        : resolvedMode === 'expand'             ? makeExpandPrompt(parents[i % parents.length])
        : makeSimilarPrompt(parents[i % parents.length], analysis)

      let data: Record<string,unknown> | null = null
      let lastFailure = ''

      for (let attempt = 1; attempt <= 3; attempt++) {
        log(`DeepSeek 呼び出し中... (試行 ${attempt}/3)`)
        try {
          const raw = await callDeepSeek(
            prompt, MODEL, MAX_TOKENS,
            (msg) => { log(msg) },
          )
          data = extractJson(raw)
          if (data) break
          lastFailure = `JSON抽出失敗: ${raw.slice(0, 120)}`
          log(lastFailure, 'warn')
        } catch (e) {
          lastFailure = String(e)
          log(`DeepSeek エラー: ${lastFailure}`, 'error')
          if (attempt < 3) {
            log('5秒後にリトライ...')
            await new Promise(r => setTimeout(r, 5000))
          }
        }
      }

      if (!data) { log(`生成失敗 (${i+1}問目): ${lastFailure}`, 'error'); continue }

      data.id = randomHex(6)
      const fp  = (data.final_problem ?? {}) as Record<string,unknown>
      const ba  = (data.beauty_analysis ?? {}) as Record<string,unknown>
      const statement = String(fp.statement ?? '')
      const answer    = String(fp.answer    ?? '')
      const solution  = String(fp.solution_outline ?? '')
      const score     = ba.total ?? '?'

      // 検証
      const embedded = (data.verification ?? {}) as Record<string,unknown>
      let passed = true

      if (embedded.problem_well_posed === false) {
        log(`⚠ 問題不成立: ${embedded.issues_found ?? '詳細不明'}`, 'warn')
        passed = false
      } else {
        log(`数学的妥当性を検証中... (${i+1}/${count})`)
        try {
          const vRaw    = await callDeepSeek(makeVerificationPrompt(statement, answer, solution), FAST_MODEL, FAST_MAX_TOKENS)
          const vResult = extractJson(vRaw) as Record<string,unknown> | null
          if (vResult) {
            const verdict    = String(vResult.verdict ?? 'UNKNOWN').toUpperCase()
            const confidence = Number(vResult.confidence ?? 5)
            if (verdict === 'FAIL' || vResult.problem_well_posed === false || confidence < 5 || vResult.answer_matches === false) {
              log(`⚠ 検証失敗 (verdict=${verdict}, conf=${confidence}): ${vResult.issues ?? ''}`, 'warn')
              passed = false
            } else {
              log(`✓ 検証OK (verdict=${verdict}, conf=${confidence})`)
              if (vResult.derived_answer && vResult.answer_matches === true) fp.answer = vResult.derived_answer
            }
          }
        } catch(e) { log(`検証エラー（保存続行）: ${e}`, 'warn') }
      }

      if (!passed) continue

      // 保存
      log('Supabase に保存中...')
      const problem = {
        id:           data.id as string,
        topic_a:      parents[0]?.topic_a ?? 'unknown',
        topic_b:      resolvedMode === 'fusion' ? (parents[parents.length-1]?.topic_a ?? null) : (parents[0]?.topic_b ?? null),
        variation:    0,
        statement,
        answer:       fp.answer as string ?? null,
        difficulty:   fp.difficulty as string ?? null,
        solution,
        inspiration:  data.inspiration as string ?? null,
        meta:         data.meta as string ?? null,
        surprise:     Number(ba.surprise)               || 0,
        minimality:   Number(ba.minimality)             || 0,
        connection:   Number(ba.connection_strength)    || 0,
        inevitability:Number(ba.inevitability)          || 0,
        diff_cal:     Number(ba.difficulty_calibration) || 0,
        total:        Number(ba.total)                  || 0,
        generation:   nextGen,
        parent_ids:   parents.map(p => p.id),
        source_file:  null,
      }

      const { error: pErr } = await supabase.from('problems').upsert(problem)
      if (pErr) { log(`保存エラー: ${pErr.message}`, 'error'); continue }

      await supabase.from('ratings').upsert(
        { user_id: userId ?? 'system', problem_id: problem.id, status: 'pending', x_posted: false },
        { onConflict: 'user_id,problem_id', ignoreDuplicates: true },
      )

      log(`保存完了 score=${score} → ${statement.slice(0, 50)}...`)
      generated.push({ id: problem.id, statement: problem.statement })

      // 使用量カウント
      if (userId) {
        const ym = currentYearMonth()
        await supabase.from('usage').upsert(
          { user_id: userId, year_month: ym, generations_count: 1 },
          { onConflict: 'user_id,year_month', ignoreDuplicates: false },
        ).catch(() => {})
      }
    }

    // 淘汰
    log('未選択問題を淘汰中...')
    const deleted = await purgeUnselected(generated.map(p => p.id)).catch(() => 0)
    log(deleted > 0 ? `淘汰完了: ${deleted} 問削除` : '淘汰対象なし')

    const ok = generated.length > 0
    log(ok ? `完了: ${generated.length}/${count} 問生成` : `失敗: 0/${count} 問生成`)

    await stopFlush(jobId)
    await supabase.from('generation_jobs').update({
      status:     ok ? 'done' : 'failed',
      result:     { ok, generated, total: count },
      updated_at: new Date().toISOString(),
    }).eq('id', jobId)

  } catch (e) {
    log(`予期しないエラー: ${e}`, 'error')
    await stopFlush(jobId)
    await supabase.from('generation_jobs').update({
      status:     'failed',
      error:      String(e),
      updated_at: new Date().toISOString(),
    }).eq('id', jobId)
  }
}

// ── メインポーリングループ ────────────────────────────────────────────────────
let processing = false

async function poll(): Promise<void> {
  if (processing) return
  processing = true
  try {
    const { data: job } = await supabase
      .from('generation_jobs')
      .select('*')
      .eq('status', 'pending')
      .order('created_at', { ascending: true })
      .limit(1)
      .single()

    if (job) await processJob(job as Record<string,unknown>)
  } catch (e) {
    // single() は結果0件でもエラーを返す（PGRST116）、無視
    if ((e as {code?: string}).code !== 'PGRST116') {
      console.error('[poll error]', e)
    }
  } finally {
    processing = false
  }
}

// ── 起動 ─────────────────────────────────────────────────────────────────────
if (!SUPABASE_URL || !SUPABASE_SERVICE_ROLE_KEY || !DEEPSEEK_API_KEY) {
  console.error('必須の環境変数が設定されていません: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, DEEPSEEK_API_KEY')
  process.exit(1)
}

console.log(`Worker 起動: model=${MODEL}, poll=${POLL_MS}ms`)
poll()  // 起動直後に即実行
setInterval(poll, POLL_MS)

// グレースフルシャットダウン
process.on('SIGTERM', () => { console.log('SIGTERM received, shutting down...'); process.exit(0) })
process.on('SIGINT',  () => { console.log('SIGINT received, shutting down...');  process.exit(0) })
