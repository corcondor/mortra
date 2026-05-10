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
const FAST_MAX    = 5000

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
          onProgress(`  ${reasoning && !full ? '推論' : '生成'}中... (${received} chars)`)
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

/**
 * 問題のフォーマット（DBのデータを全て活用）
 */
function fmt(p: ParentProblem, idx?: number): string {
  const h = idx != null ? `【親問題${idx}】（${p.topic_a}${p.topic_b ? ` × ${p.topic_b}` : ''}）` : '【問題】'
  const l = [h, `問題文: ${p.statement}`, `答え: ${p.answer ?? '（不明）'}`]
  if (p.solution)    l.push(`解法の骨格: ${p.solution}`)
  if (p.inspiration) l.push(`数学的洞察（作問時のメモ）: ${p.inspiration}`)
  return l.join('\n')
}

/**
 * 共通システム指示
 * 要点：A/B案比較・弱点探し・step-by-step計算・最小性確認
 */
const SYS = `あなたは数学オリンピアード・難関大学入試の専門作問者です。

◆ 作問前に必ずこの順序で実行すること：

【1】A案 vs B案  ── 互いに異なる2つのアプローチを考え、どちらが数学的に優れているか、理由を明示して選ぶ
【2】弱点探し    ── 自分の問題の矛盾・冗長な条件・崩れる特殊ケースを積極的に探す（反例を1つ挙げること）
【3】答えを計算  ── step-by-step で実際に解き、n=1, n=2 等の具体値で検算する（「たぶんこうなる」禁止）
【4】最小性確認  ── 条件を1つ削っても問題が成立するなら、その条件は冗長 → 削る

◆ JSON のみで出力（他の文章一切不要）：
\`\`\`json
{
  "inspiration": "このアプローチを選んだ数学的理由（3文以内）",
  "plan": {
    "approach_A": "アプローチAの概要（問題設定・使う道具）",
    "approach_B": "アプローチBの概要（問題設定・使う道具）",
    "chosen": "A または B",
    "reason": "選んだ理由（なぜもう一方より数学的に優れているか）"
  },
  "weakness_check": {
    "potential_issue": "問題が成立しないかもしれない点・冗長な条件",
    "counterexample_attempt": "反例を探した結果（「n=1のとき〜」等の具体的試み）",
    "fix": "修正した内容（問題なければ null）"
  },
  "verification": {
    "computation": "step-by-step 計算（省略なし）",
    "numerical_check": "具体値代入での検算（例: n=2 のとき両辺を計算）",
    "answer_check": "計算で確認した答え（LaTeX）",
    "problem_well_posed": true,
    "issues_found": null
  },
  "final_problem": {
    "statement": "問題文（LaTeX）",
    "answer": "答え（LaTeX）※ verification.answer_check と完全一致",
    "solution_outline": "解法の骨格（200字以内）",
    "difficulty": "A/B/C/D（A=最難）"
  },
  "beauty_analysis": {
    "surprise": 8,
    "minimality": 9,
    "connection_strength": 8,
    "inevitability": 9,
    "difficulty_calibration": 7,
    "total": 8.2,
    "comment": "この問題の美しさの核心（2文）"
  },
  "meta": "作問中に発見した数学的洞察（1文）"
}
\`\`\``

/**
 * 構造分析プロンプト（類題生成の前段として使用）
 * 弱点と改善方向を明示させる
 */
const makeAnalysis = (p: ParentProblem) =>
  `以下の数学問題の構造を深く分析してください。

${fmt(p)}

## 分析の手順

1. **核心一手の特定**: 解法から「これがなければ絶対に解けない操作」を1つ選び、なぜ代替不可能かを説明せよ
2. **弱点発見**: 問題として改善できる点を探せ（条件が冗長・答えが汚い・問題文が長い・解法が不自然）
3. **競合フレーミング**: この問題を全く異なる設定で書き直すとどうなるか（背後の構造を露わにする）
4. **改善の方向**: 弱点を克服した「より美しい類題」を作るための具体的な方針

\`\`\`json
{
  "core_structure": "核心的数学構造（定理・変換・対応）",
  "key_technique": "解法の核心一手（これなしでは解けない操作）",
  "why_inevitable": "答えがこの値である数学的必然性",
  "hidden_connection": "表面上見えない深い構造・背後にあるもの",
  "weakness": "問題として改善できる点（具体的に）",
  "improvement_direction": "弱点を克服するための方針（次の類題生成に使う）",
  "competing_framing": "同じ核心を別の設定で表現するとどうなるか"
}
\`\`\``

/**
 * 類題生成プロンプト
 * 弱点を克服し、A/B案比較を通じてより良い問題を作る
 */
const makeSimilar = (p: ParentProblem, a?: Record<string, string>) => {
  const analysisBlock = a ? `
【構造分析（事前計算済み）】
- 核心一手: ${a.key_technique ?? ''}
- 答えの必然性: ${a.why_inevitable ?? ''}
- 隠れた構造: ${a.hidden_connection ?? ''}
- 元問題の弱点: ${a.weakness ?? ''}
- 改善の方針: ${a.improvement_direction ?? ''}
- 競合フレーミング: ${a.competing_framing ?? ''}
` : ''

  return `${SYS}

# 元問題
${fmt(p)}
${analysisBlock}
---

# 類題生成の手順

## Step 1: 弱点を克服する
元問題の「弱点」を明確にし、その弱点を直接修正することを意識して類題を設計せよ。
弱点がなければ「競合フレーミング」を使って設定を刷新せよ。

## Step 2: A案 vs B案（plan フィールドに記入）
- A案: 弱点を克服しつつ、元の核心一手を保持した設定
- B案: 競合フレーミングから出発した全く異なる設定（しかし核心一手は同じ）
どちらが「必然性」と「美しさ」の観点で優れているか選べ。

## Step 3: 禁止事項の確認
- 単なる数値・記号の置き換え → 禁止
- 答えが元問題と同じ → 禁止
- 問題文が元より長い → 禁止

JSON形式のみで回答。`
}

/**
 * 融合生成プロンプト
 * 自己注意（Self-Attention）→ A/B案比較 → 弱点探し → 最小化
 */
const makeFusion = (ps: ParentProblem[]) => {
  const parentTexts = ps.map((p, i) => fmt(p, i + 1)).join('\n\n')

  return `${SYS}

# 親問題（これらを融合して新問題を作る）

${parentTexts}

---

# 構造的融合の手順

## Phase 0: 自己注意（Self-Attention）
各親問題について以下を実行せよ（inspiration と solution_outline を参考にすること）：
- 「解法からこれを取り除くと絶対に解けなくなる一手」を1つ選べ
- その一手を数学的操作として言語化せよ（例：「ガンマ関数と二項係数の積分表示の同一視」）
- なぜこの一手が他の方法で代替できないかを説明せよ

## Phase 1: 融合設計（A案 vs B案）
**A案（直列依存）**: 一手Aを実行したからこそ、一手Bが必要になる
**B案（並列依存）**: 共通の数学的対象に対して、一手A・一手B両方が自然に要求される

上記 plan フィールドに両案を具体的に書き、どちらを選ぶか理由とともに述べよ。

## Phase 2: 弱点探し（Devil's Advocate）
選んだ案について：
- この問題から片方の分野を排除しても解けるか？（→ 解ける = 融合が偽物）
- 問題文に冗長な条件はないか？
- 小さい値（n=1, n=2）で問題が崩壊しないか？

## Phase 3: 問題文の作成
- 1〜2文、(1)(2)分割禁止、誘導禁止、ヒント禁止
- 「問題文を見ただけでは融合がどこにあるか分からない」こと
- 解いていく過程で突然、別分野の道具が必要になること

## 答えの条件
整数・分数・π, e, √ 等のコンパクトな定数。実際に計算して確認した値のみ記載。

JSON形式のみで回答。`
}

/**
 * 高次元化プロンプト
 */
const makeExpand = (p: ParentProblem) =>
  `${SYS}

以下の問題を「より深い数学的構造へ一般化」してください。

${fmt(p)}

## 一般化の手順

## Step 1: 構造の露わ化
この問題の背後にある「より抽象的・一般的な構造」を言語化せよ。
（例：n=2 の特殊ケースである行列の話が実は作用素の話、等）

## Step 2: A案 vs B案の一般化
- A案: パラメータを増やす方向（n次元、一般のp等）
- B案: 構造を抽象化する方向（群・環・関数族・作用素等）
どちらが「元問題が特殊ケースであることが美しく見える」一般化か選べ。

## 答えの要件
- パラメータの美しい関数として表される
- 元の答えを特殊ケースとして含む

JSON形式のみで回答。`

/**
 * 検証プロンプト（高速モデル用）
 * 積極的に反例を探す・計算で確認する
 */
const makeVerify = (stmt: string, ans: string, sol: string) =>
  `以下の数学問題を厳密に検証してください。

【問題文】
${stmt}

【想定答え】
${ans}

【解法の骨格】
${sol}

## 検証手順

1. **反例探し**: まず問題が成立しない特殊ケース（n=0, n=1, 境界値等）を積極的に探せ
2. **step-by-step計算**: 解法の骨格に従い実際に計算せよ（省略なし）
3. **具体値検算**: 特定の数値を代入して両辺/答えを確認せよ
4. **答え照合**: 計算で得られた答えが想定答えと一致するか確認せよ
5. **一意性確認**: 答えが一意に定まるか確認せよ

\`\`\`json
{
  "counterexample_attempt": "反例を探した結果（見つかった場合は具体的に）",
  "step_by_step": "実際の計算過程（省略なし）",
  "numerical_check": "具体値を使った検算",
  "derived_answer": "計算で得られた答え（LaTeX）",
  "answer_matches": true,
  "problem_well_posed": true,
  "issues": null,
  "confidence": 8,
  "verdict": "PASS"
}
\`\`\``

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

    log(`🚀 [開始] ${resolved} 生成 × ${count}問 (model: ${MODEL})`)

    const generated: { id: string; statement: string }[] = []

    // ── 分析フェーズ（類題/高次元のみ） ───────────────────────────────────
    let analysis: Record<string, string> | undefined
    if (resolved !== 'fusion' && parents.length === 1) {
      log('🔍 [分析] 問題の核心構造・弱点を抽出中...')
      try {
        const raw = await callDeepSeek(makeAnalysis(parents[0]), FAST_MODEL, FAST_MAX)
        const a = extractJson(raw)
        if (a) {
          analysis = a as Record<string, string>
          log(`🔍 [分析] 完了: 核心=${analysis.key_technique?.slice(0, 40) ?? 'OK'} / 弱点=${analysis.weakness?.slice(0, 40) ?? 'なし'}`)
        }
      } catch(e) {
        log(`🔍 [分析] エラー（スキップ）: ${e}`, 'warn')
      }
    }

    // ── 生成ループ ──────────────────────────────────────────────────────────
    for (let i = 0; i < count; i++) {
      const nth = `${i+1}/${count}`
      log(`🎯 [生成 ${nth}] DeepSeek 呼び出し中...`)

      const prompt = resolved === 'fusion' ? makeFusion(parents)
        : resolved === 'expand'            ? makeExpand(parents[i % parents.length])
        : makeSimilar(parents[i % parents.length], analysis)

      let data: Record<string, unknown> | null = null
      let lastErr = ''

      for (let attempt = 1; attempt <= 3; attempt++) {
        if (attempt > 1) log(`🎯 [生成 ${nth}] リトライ ${attempt}/3...`)
        try {
          const raw = await callDeepSeek(prompt, MODEL, MAX_TOKENS,
            msg => log(`🎯 [生成 ${nth}]${msg}`))
          data = extractJson(raw)
          if (data) break
          lastErr = `JSON抽出失敗: ${raw.slice(0, 120)}`
          log(`⚠ [生成 ${nth}] ${lastErr}`, 'warn')
        } catch(e) {
          lastErr = String(e)
          log(`❌ [生成 ${nth}] DeepSeek エラー: ${lastErr}`, 'error')
          if (attempt < 3) await new Promise(r => setTimeout(r, 5000))
        }
      }

      if (!data) {
        log(`❌ [生成 ${nth}] 3回失敗 → スキップ: ${lastErr}`, 'error')
        continue
      }

      // 選んたA/B案を表示
      const plan = data.plan as Record<string, string> | undefined
      if (plan?.chosen) {
        log(`🎯 [生成 ${nth}] ${plan.chosen}案を選択: ${plan.reason?.slice(0, 60) ?? ''}`)
      }
      // 弱点チェック結果を表示
      const wc = data.weakness_check as Record<string, string> | undefined
      if (wc?.fix) {
        log(`🔧 [生成 ${nth}] 弱点修正: ${wc.fix.slice(0, 60)}`)
      }

      const fp  = (data.final_problem ?? {}) as Record<string, unknown>
      const ba  = (data.beauty_analysis ?? {}) as Record<string, unknown>
      const stmt = String(fp.statement ?? '')
      const ans  = String(fp.answer ?? '')
      const sol  = String(fp.solution_outline ?? '')

      if (!stmt || !ans) {
        log(`⚠ [生成 ${nth}] statement/answer が空 → スキップ`, 'warn')
        continue
      }

      // ── 検証フェーズ ────────────────────────────────────────────────────
      const emb = (data.verification ?? {}) as Record<string, unknown>
      let ok = true

      if (emb.problem_well_posed === false) {
        log(`⚠ [検証 ${nth}] 自己申告で不成立: ${emb.issues_found ?? ''}`, 'warn')
        ok = false
      } else {
        log(`🔍 [検証 ${nth}] step-by-step 計算で答えを確認中...`)
        try {
          const vRaw = await callDeepSeek(makeVerify(stmt, ans, sol), FAST_MODEL, FAST_MAX)
          const vr = extractJson(vRaw)
          if (vr) {
            const verdict = String(vr.verdict ?? '').toUpperCase()
            const conf    = Number(vr.confidence ?? 5)
            const issues  = vr.issues ? ` (${String(vr.issues).slice(0, 60)})` : ''

            const wellPosed   = vr.problem_well_posed !== false
            const ansMatches  = vr.answer_matches === true
            const hasDerived  = vr.derived_answer && String(vr.derived_answer).trim().length > 0

            if (!wellPosed || conf < 4) {
              // 問題自体が不成立 or 信頼度が低すぎる → 完全スキップ
              log(`⚠ [検証 ${nth}] 不成立 (conf=${conf}, well_posed=${wellPosed})${issues} → スキップ`, 'warn')
              ok = false
            } else if (ansMatches) {
              // 完全一致 → そのまま保存
              log(`✓ [検証 ${nth}] PASS (conf=${conf})`)
            } else if (hasDerived && conf >= 6) {
              // 答えは違うが問題は成立・検証モデルが正解を計算できている → 答えを上書き保存
              log(`🔧 [検証 ${nth}] 答えを検証値で修正 (conf=${conf}): ${String(vr.derived_answer).slice(0, 50)}`)
              fp.answer = vr.derived_answer
            } else {
              // 答えが間違いで代替答えも不明 → スキップ
              log(`⚠ [検証 ${nth}] 答え不一致・代替なし (conf=${conf})${issues} → スキップ`, 'warn')
              ok = false
            }
          }
        } catch(e) {
          log(`⚠ [検証 ${nth}] エラー（保存続行）: ${e}`, 'warn')
        }
      }

      if (!ok) continue

      // ── 保存 ────────────────────────────────────────────────────────────
      log(`💾 [保存 ${nth}] Supabase に書き込み中...`)
      const problem = {
        id: randomHex(6),
        topic_a: parents[0]?.topic_a ?? 'unknown',
        topic_b: resolved === 'fusion'
          ? (parents[parents.length-1]?.topic_a ?? null)
          : (parents[0]?.topic_b ?? null),
        variation: 0,
        statement: stmt,
        answer: fp.answer as string ?? null,
        difficulty: fp.difficulty as string ?? null,
        solution: sol,
        inspiration: data.inspiration as string ?? null,
        meta: data.meta as string ?? null,
        surprise:     Number(ba.surprise)             || 0,
        minimality:   Number(ba.minimality)           || 0,
        connection:   Number(ba.connection_strength)  || 0,
        inevitability:Number(ba.inevitability)        || 0,
        diff_cal:     Number(ba.difficulty_calibration)|| 0,
        total:        Number(ba.total)                || 0,
        generation: nextGen,
        parent_ids: parents.map(p => p.id),
        source_file: null,
      }

      const { error: pe } = await supabase.from('problems').upsert(problem)
      if (pe) {
        log(`❌ [保存 ${nth}] 保存エラー: ${pe.message}`, 'error')
        continue
      }

      await supabase.from('ratings').upsert(
        { user_id: userId ?? 'system', problem_id: problem.id, status: 'pending', x_posted: false },
        { onConflict: 'user_id,problem_id', ignoreDuplicates: true },
      )

      const score = Number(ba.total) || 0
      log(`✅ [完了 ${nth}] score=${score.toFixed(1)} 難=${fp.difficulty ?? '?'} → ${stmt.slice(0, 45)}...`)
      generated.push({ id: problem.id, statement: problem.statement })

      if (userId) {
        await supabase.from('usage').upsert(
          { user_id: userId, year_month: ym(), generations_count: 1 },
          { onConflict: 'user_id,year_month', ignoreDuplicates: false },
        )
      }
    }

    // ── 淘汰フェーズ ────────────────────────────────────────────────────────
    log('🗑️ [淘汰] 未選択問題を整理中...')
    const del = await purge(generated.map(p => p.id)).catch(() => 0)
    log(del > 0 ? `🗑️ [淘汰] ${del} 問削除` : '🗑️ [淘汰] 対象なし')

    const success = generated.length > 0
    log(success
      ? `🎉 [終了] ${generated.length}/${count} 問生成完了。表示を更新してください。`
      : `❌ [終了] 0/${count} 問 — 全て検証失敗またはエラー`)

    clearInterval(flushInterval)
    await flushLogs(jobId)
    await supabase.from('generation_jobs').update({
      status: success ? 'done' : 'failed',
      result: { ok: success, generated, total: count },
      updated_at: new Date().toISOString(),
    }).eq('id', jobId)

  } catch(e) {
    log(`❌ [致命的エラー] ${e}`, 'error')
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
