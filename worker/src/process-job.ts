/**
 * process-job.ts — GitHub Actions / Render Worker 兼用
 * 環境変数 JOB_ID があれば単一ジョブを処理して終了。
 * なければポーリングループ（常駐サーバー用）。
 */

import { createClient } from '@supabase/supabase-js'

// ── 環境変数 ─────────────────────────────────────────────────────────────────
const SUPABASE_URL              = process.env.SUPABASE_URL!
const SUPABASE_SERVICE_ROLE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY!
const DEEPSEEK_API_KEY          = process.env.DEEPSEEK_API_KEY!
const MODEL      = process.env.DEEPSEEK_MODEL      ?? 'deepseek-chat'
const FAST_MODEL = process.env.DEEPSEEK_FAST_MODEL ?? 'deepseek-chat'
const MAX_TOKENS = Number(process.env.DEEPSEEK_MAX_TOKENS ?? '8000')
const FAST_MAX   = 5000

if (!SUPABASE_URL || !SUPABASE_SERVICE_ROLE_KEY || !DEEPSEEK_API_KEY) {
  console.error('必須環境変数が未設定')
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
    if (!full && reasoning) throw new Error('推論が切断されました')
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
  const h = idx != null
    ? `【親問題${idx}】（${p.topic_a}${p.topic_b ? ` × ${p.topic_b}` : ''}）`
    : '【問題】'
  const l = [h, `問題文: ${p.statement}`, `答え: ${p.answer ?? '（不明）'}`]
  if (p.solution)    l.push(`解法の骨格: ${p.solution}`)
  if (p.inspiration) l.push(`数学的洞察: ${p.inspiration}`)
  return l.join('\n')
}

const SYS = `あなたは数学オリンピアード・難関大学入試の専門作問者です。

◆ 必須手順（この順番で実行）：
【1】A案 vs B案  ── 2つの競合アプローチを考え、数学的に優れている方を選ぶ
【2】弱点探し    ── 反例・矛盾・冗長条件を積極的に探す（具体値n=1,2で確認）
【3】答えを計算  ── step-by-step で実際に解き、数値を代入して検算（「たぶん」禁止）
【4】最小化      ── 条件を削れるなら削る

◆ JSON のみで出力：
\`\`\`json
{
  "inspiration": "アプローチ選択の数学的理由（3文以内）",
  "plan": {
    "approach_A": "A案の概要",
    "approach_B": "B案の概要",
    "chosen": "A または B",
    "reason": "選択理由（数学的必然性）"
  },
  "weakness_check": {
    "potential_issue": "問題が成立しないかもしれない点",
    "counterexample_attempt": "反例を探した結果（具体的に）",
    "fix": "修正内容（問題なければ null）"
  },
  "verification": {
    "computation": "step-by-step計算（省略なし）",
    "numerical_check": "具体値での検算（例: n=2で両辺計算）",
    "answer_check": "計算で確認した答え（LaTeX）",
    "problem_well_posed": true,
    "issues_found": null
  },
  "final_problem": {
    "statement": "問題文（LaTeX）",
    "answer": "答え（LaTeX）※ verification.answer_check と一致",
    "solution_outline": "解法の骨格（200字以内）",
    "difficulty": "A/B/C/D"
  },
  "beauty_analysis": {
    "surprise": 8, "minimality": 9, "connection_strength": 8,
    "inevitability": 9, "difficulty_calibration": 7, "total": 8.2,
    "comment": "美的分析（2文）"
  },
  "meta": "作問中に発見した洞察（1文）"
}
\`\`\``

/** 親問題の構造分析（類題生成前の事前分析） */
const makeAnalysis = (p: ParentProblem) =>
  `以下の数学問題の構造を深く分析してください。

${fmt(p)}

## 分析手順
1. 「解法からこれを除くと絶対に解けない一手」を1つ特定し、代替不可能な理由を説明
2. 問題として改善できる弱点を探す（条件冗長・答えが汚い・問題文が長い等）
3. 弱点を克服した類題を作るための具体的方針を示す

\`\`\`json
{
  "core_structure": "核心的数学構造",
  "key_technique": "解法の核心一手",
  "why_inevitable": "答えの必然性",
  "hidden_connection": "背後にある深い構造",
  "weakness": "改善できる点（具体的に）",
  "improvement_direction": "弱点を克服する方針",
  "competing_framing": "同じ核心を別設定で表現するとどうなるか"
}
\`\`\``

/** 類題生成 */
const makeSimilar = (p: ParentProblem, a?: Record<string, string>, attempt = 1, prevStatements: string[] = []) => {
  const analysisBlock = a ? `
【構造分析】
- 核心一手: ${a.key_technique ?? ''}
- 必然性: ${a.why_inevitable ?? ''}
- 隠れた構造: ${a.hidden_connection ?? ''}
- 弱点: ${a.weakness ?? ''}
- 改善方針: ${a.improvement_direction ?? ''}
- 別フレーミング: ${a.competing_framing ?? ''}
` : ''

  const prevBlock = prevStatements.length > 0 ? `
【既に生成した問題（これらと全く異なること）】
${prevStatements.map((s, i) => `- 試み${i+1}: ${s.slice(0, 80)}...`).join('\n')}
` : ''

  return `${SYS}

# 元問題
${fmt(p)}
${analysisBlock}${prevBlock}
---
# 類題生成の手順（試み${attempt}回目）

## Step 1: 弱点を克服する
元問題の「弱点」を直接修正した類題を設計。または「別フレーミング」から出発。

## Step 2: A案 vs B案
- A案: 弱点克服型（元の核心一手を保持しつつ設定を変える）
- B案: 別フレーミング型（同じ核心を全く異なる設定で表現）

## 禁止
- 単なる数値・記号の置き換え
- 元と同じ答え
- 既に生成した問題と同じパターン

JSON形式のみで回答。`
}

/** 融合生成 */
const makeFusion = (ps: ParentProblem[], attempt = 1, prevStatements: string[] = []) => {
  const parentTexts = ps.map((p, i) => fmt(p, i + 1)).join('\n\n')

  const prevBlock = prevStatements.length > 0 ? `
## ⚠ 過去の試みとの差別化（必須）
以下のパターンは既に試みられ却下されました。全く異なるアプローチを取ること：
${prevStatements.map((s, i) => `- 試み${i+1}: ${s.slice(0, 100)}...`).join('\n')}
` : ''

  return `${SYS}

# 親問題
${parentTexts}

---
# 構造的融合（試み${attempt}回目）
${prevBlock}

## Phase 0: 自己注意（inspiration と solution を必ず参照）
各親問題について：
- 「これを除いたら絶対に解けない一手」を1つ特定
- その一手が代替不可能な理由を説明

## Phase 1: 融合設計（A案 vs B案）
**A案（直列）**: 一手Aを実行したからこそ一手Bが必要になる
**B案（並列）**: 共通の対象に一手A・B両方が自然に要求される
plan フィールドに両案を書き、選択理由を示す。

## Phase 2: 弱点探し
- 片方の分野を除いても解けるか？ → 解ける = 融合が偽物
- 小さい値（n=1,2）で崩壊しないか？
- 答えが整数・分数・π,e,√ 等のコンパクトな形か？

## Phase 3: 問題文
- 1〜2文、(1)(2)分割禁止、誘導禁止
- 問題文を見ただけでは融合箇所が分からないこと

JSON形式のみで回答。`
}

/** 高次元化 */
const makeExpand = (p: ParentProblem, attempt = 1) =>
  `${SYS}

以下の問題を「より深い数学的構造へ一般化」してください（試み${attempt}回目）。

${fmt(p)}

## 一般化の方向（A案 vs B案）
- A案: パラメータ化（n次元・一般のpなど、元が特殊ケースになる）
- B案: 構造の抽象化（群・環・関数族・作用素など）

JSON形式のみで回答。`

/** 問題修正プロンプト（検証失敗後に呼ぶ） */
const makeRepair = (stmt: string, ans: string, sol: string, issues: string, derivedAnswer: string | null) => {
  // 「すべて求めよ」系かどうかを検出
  const isFindAll = /すべて求め|すべて見つけ|全ての.*求め|すべての.*求め|find all|enumerate all/i.test(stmt)
  const isNoSolution = /解が存在しない|解なし|条件を満たす.*存在しない|no solution|empty/i.test(issues)

  const findAllInstruction = isFindAll && isNoSolution
    ? `⚠ 重要: この問題は「すべて求めよ」型ですが、解が存在しないことが確認されました。
以下のいずれかの方針で修正してください（どちらでもよい）：
- 【方針A】条件を緩めて解が1つ以上存在するよう変更する（例: $n \\geq 2$ → $n \\geq 1$、係数を変える、等）
- 【方針B】問題の聞き方を変える（例: 「すべて求めよ」→「最小値を求めよ」「〜が成立する条件を求めよ」）
方針Aを優先し、数学的に自然な変更にすること。`
    : isFindAll
    ? `注意: この問題は「すべて求めよ」型です。答えが空集合にならないよう確認し、解が存在することを step-by-step で確認してください。`
    : ''

  return `以下の数学問題に問題が見つかりました。修正してください。

【元の問題文】
${stmt}

【想定答え（誤りの可能性あり）】
${ans}

【解法の骨格】
${sol}

【確認された問題点】
${issues}

${derivedAnswer ? `【検証モデルが計算した正しい答え（これを使うこと）】\n${derivedAnswer}\n` : ''}
${findAllInstruction ? `\n${findAllInstruction}\n` : ''}
## 修正の指示
1. 問題の条件の矛盾・曖昧さを解消する
2. 解が必ず1つ以上存在するよう条件を整理・追加する（「すべて求めよ」型なら解が空にならないこと）
3. ${derivedAnswer ? `答えを「${derivedAnswer}」と整合するよう問題文を修正` : '問題が成立するよう条件を修正'}
4. 問題文は最小限に（冗長な条件は削る）
5. 修正後も step-by-step で答えを確認すること

\`\`\`json
{
  "statement": "修正後の問題文（LaTeX）",
  "answer": "修正後の答え（LaTeX）",
  "solution_outline": "解法の骨格（150字以内）",
  "fix_explanation": "何をどう修正したか（具体的に）",
  "verification": "修正後の答えの確認計算（step-by-step）"
}
\`\`\``
}

/** 親問題の修正プロンプト */
const makeParentRepair = (p: ParentProblem, issues: string) =>
  `以下の数学問題は不成立が確認されました。修正してください。

${fmt(p)}

【確認された問題点】
${issues}

## 修正の指示
- 数学的核心（分野・解法の核心一手）は保持する
- 条件の矛盾を解消し、解が一意に存在するよう修正する
- 問題文は簡潔に（不要な条件は削る）

\`\`\`json
{
  "statement": "修正後の問題文（LaTeX）",
  "answer": "修正後の答え（LaTeX）",
  "solution_outline": "解法の骨格",
  "fix_explanation": "何をどう修正したか"
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

  await supabase.from('generation_jobs').update({
    status: 'processing', model: MODEL, updated_at: new Date().toISOString(),
  }).eq('id', jobId)

  const flushInterval = setInterval(() => flushLogs(jobId), 3000)
  const log = (msg: string, level = 'info') => pushLog(msg, level)

  try {
    const { data: job, error } = await supabase
      .from('generation_jobs').select('*').eq('id', jobId).single()
    if (error || !job) throw new Error(`ジョブが見つかりません: ${error?.message}`)

    let parents   = job.parents as ParentProblem[]
    const mode    = String(job.mode ?? 'auto')
    const count   = Number(job.count) || 3
    const userId  = job.user_id as string | null
    const resolved = mode === 'auto' ? (parents.length >= 2 ? 'fusion' : 'similar') : mode

    const { data: gd } = await supabase.from('problems')
      .select('generation').order('generation', { ascending: false }).limit(1).single()
    const nextGen = ((gd?.generation as number|null) ?? 0) + 1

    log(`🚀 [開始] ${resolved} 生成 × ${count}問 (model: ${MODEL})`)

    // ────────────────────────────────────────────────────────────────────────
    // Phase 0: 親問題の修正
    // ────────────────────────────────────────────────────────────────────────
    log('🔍 [親問題チェック] 妥当性を確認中...')
    for (let pi = 0; pi < parents.length; pi++) {
      const p = parents[pi]
      if (!p.statement || !p.answer) continue
      try {
        const checkRaw = await callDeepSeek(
          `以下の数学問題が数学的に成立しているか確認してください。\n\n${fmt(p)}\n\n` +
          `step-by-step で答えを確認し、JSONのみで返してください：\n` +
          `\`\`\`json\n{"well_posed":true,"issues":null,"confidence":8}\n\`\`\``,
          FAST_MODEL, 3000,
        )
        const check = extractJson(checkRaw)
        if (check && check.well_posed === false && Number(check.confidence ?? 0) >= 6) {
          log(`⚠ [親問題${pi+1}] 不成立 → 修正中... (issues: ${String(check.issues ?? '').slice(0, 60)})`, 'warn')
          const repairRaw = await callDeepSeek(makeParentRepair(p, String(check.issues ?? '')), MODEL, MAX_TOKENS)
          const repaired = extractJson(repairRaw)
          if (repaired?.statement) {
            const newStmt = String(repaired.statement)
            const newAns  = String(repaired.answer ?? p.answer ?? '')
            const newSol  = String(repaired.solution_outline ?? p.solution ?? '')
            // DB更新
            await supabase.from('problems').update({
              statement: newStmt, answer: newAns, solution: newSol,
              updated_at: new Date().toISOString(),
            }).eq('id', p.id)
            // ローカル参照も更新
            parents[pi] = { ...p, statement: newStmt, answer: newAns, solution: newSol }
            log(`✓ [親問題${pi+1}] 修正完了: ${String(repaired.fix_explanation ?? '').slice(0, 60)}`)
          } else {
            log(`⚠ [親問題${pi+1}] 修正失敗 → そのまま使用`, 'warn')
          }
        } else {
          log(`✓ [親問題${pi+1}] 成立確認OK`)
        }
      } catch(e) {
        log(`⚠ [親問題${pi+1}] チェックエラー（スキップ）: ${e}`, 'warn')
      }
    }

    // ────────────────────────────────────────────────────────────────────────
    // Phase 1: 構造分析（類題のみ）
    // ────────────────────────────────────────────────────────────────────────
    let analysis: Record<string, string> | undefined
    if (resolved === 'similar' && parents.length === 1) {
      log('🔍 [分析] 問題の核心構造・弱点を抽出中...')
      try {
        const raw = await callDeepSeek(makeAnalysis(parents[0]), FAST_MODEL, FAST_MAX)
        const a = extractJson(raw)
        if (a) {
          analysis = a as Record<string, string>
          log(`🔍 [分析] 完了: 核心=${analysis.key_technique?.slice(0, 40) ?? 'OK'}`)
        }
      } catch(e) {
        log(`⚠ [分析] エラー（スキップ）: ${e}`, 'warn')
      }
    }

    // ────────────────────────────────────────────────────────────────────────
    // Phase 2: 生成ループ（count問になるまでリトライ）
    // ────────────────────────────────────────────────────────────────────────
    const generated: { id: string; statement: string }[] = []
    const prevStatements: string[] = []  // 多様性確保：過去の試みを記録
    const maxAttempts = count * 4        // 最大 count×4 回試みる
    let totalAttempts = 0

    while (generated.length < count && totalAttempts < maxAttempts) {
      totalAttempts++
      const nth = `${generated.length + 1}/${count}`
      log(`🎯 [生成 ${nth}] 試み${totalAttempts} (残${maxAttempts - totalAttempts}回)`)

      // プロンプト生成（試み番号・過去の問題を渡す）
      const prompt = resolved === 'fusion'
        ? makeFusion(parents, totalAttempts, prevStatements)
        : resolved === 'expand'
          ? makeExpand(parents[totalAttempts % parents.length], totalAttempts)
          : makeSimilar(parents[totalAttempts % parents.length], analysis, totalAttempts, prevStatements)

      // DeepSeek呼び出し（2回まで）
      let rawData: Record<string, unknown> | null = null
      for (let attempt = 1; attempt <= 2; attempt++) {
        try {
          const raw = await callDeepSeek(prompt, MODEL, MAX_TOKENS,
            msg => log(`🎯 [生成 ${nth}]${msg}`))
          rawData = extractJson(raw)
          if (rawData) break
          log(`⚠ [生成 ${nth}] JSON抽出失敗 (${attempt}/2)`, 'warn')
        } catch(e) {
          log(`❌ [生成 ${nth}] エラー: ${e}`, 'error')
          if (attempt < 2) await new Promise(r => setTimeout(r, 3000))
        }
      }
      if (!rawData) continue

      // プラン情報を表示
      const plan = rawData.plan as Record<string, string> | undefined
      if (plan?.chosen) {
        log(`💡 [生成 ${nth}] ${plan.chosen}案: ${plan.reason?.slice(0, 60) ?? ''}`)
      }
      const wc = rawData.weakness_check as Record<string, string> | undefined
      if (wc?.fix) {
        log(`🔧 [生成 ${nth}] 弱点修正: ${wc.fix.slice(0, 60)}`)
      }

      // 問題文・答え・解法を取り出す
      const fp   = (rawData.final_problem ?? {}) as Record<string, unknown>
      const ba   = (rawData.beauty_analysis ?? {}) as Record<string, unknown>
      let stmt   = String(fp.statement ?? '')
      let ans    = String(fp.answer ?? '')
      let sol    = String(fp.solution_outline ?? '')

      if (!stmt) { log(`⚠ [生成 ${nth}] statement が空 → スキップ`, 'warn'); continue }

      // 多様性記録（生成できた問題文を追加）
      prevStatements.push(stmt)

      // 生成モデル自身が不成立と言っている場合は修正を試みる
      const emb = (rawData.verification ?? {}) as Record<string, unknown>
      if (emb.problem_well_posed === false) {
        const embIssues = String(emb.issues_found ?? '')
        const isFindAll = /すべて求め|すべて見つけ|全ての.*求め|すべての.*求め/i.test(stmt)
        if (isFindAll) {
          log(`⚠ [生成 ${nth}] 自己申告: 「すべて求めよ」型で不成立 → 条件を修正します...`, 'warn')
        } else {
          log(`⚠ [生成 ${nth}] 自己申告: 不成立 → 修正を試みます...`, 'warn')
        }
        const repairRaw = await callDeepSeek(
          makeRepair(stmt, ans, sol, embIssues, null),
          FAST_MODEL, FAST_MAX,
        ).catch(() => null)
        if (repairRaw) {
          const repaired = extractJson(repairRaw)
          if (repaired?.statement) {
            stmt = String(repaired.statement)
            ans  = String(repaired.answer ?? ans)
            sol  = String(repaired.solution_outline ?? sol)
            log(`🔧 [生成 ${nth}] 自己修正: ${String(repaired.fix_explanation ?? '').slice(0, 60)}`)
          }
        }
      }

      // ── 独立検証 ────────────────────────────────────────────────────────
      log(`🔍 [検証 ${nth}] step-by-step で確認中...`)
      let verifyOk = true
      try {
        const vRaw = await callDeepSeek(
          makeVerify(stmt, ans, sol), FAST_MODEL, FAST_MAX)
        const vr = extractJson(vRaw)
        if (vr) {
          const verdict    = String(vr.verdict ?? '').toUpperCase()
          const conf       = Number(vr.confidence ?? 5)
          const wellPosed  = vr.problem_well_posed !== false
          const ansMatches = vr.answer_matches === true
          const derived    = vr.derived_answer ? String(vr.derived_answer) : null
          const issues     = vr.issues ? String(vr.issues) : ''

          if (!wellPosed && conf >= 6) {
            // 問題自体が成立しない → 修正を試みる
            const noSol = vr.no_solution_exists === true
            const isFindAll = vr.is_find_all_type === true
            if (noSol && isFindAll) {
              log(`⚠ [検証 ${nth}] 「すべて求めよ」型で解が存在しない (conf=${conf}) → 問題文を修正します...`, 'warn')
            } else {
              log(`⚠ [検証 ${nth}] 不成立 (conf=${conf}) → 修正します...`, 'warn')
            }
            const repairRaw = await callDeepSeek(
              makeRepair(stmt, ans, sol, issues, derived), FAST_MODEL, FAST_MAX,
            ).catch(() => null)
            const repaired = repairRaw ? extractJson(repairRaw) : null
            if (repaired?.statement) {
              stmt = String(repaired.statement)
              ans  = String(repaired.answer ?? ans)
              sol  = String(repaired.solution_outline ?? sol)
              log(`🔧 [検証 ${nth}] 修正完了: ${String(repaired.fix_explanation ?? '').slice(0, 60)}`)
              // 修正後に再度検証（簡易）
              const v2Raw = await callDeepSeek(makeVerify(stmt, ans, sol), FAST_MODEL, FAST_MAX).catch(() => '')
              const v2 = extractJson(v2Raw)
              if (v2 && v2.problem_well_posed === false) {
                log(`⚠ [検証 ${nth}] 再検証でも不成立 → スキップ`, 'warn')
                verifyOk = false
              } else {
                log(`✓ [検証 ${nth}] 修正後の再検証OK`)
                if (v2?.derived_answer) ans = String(v2.derived_answer)
              }
            } else {
              log(`⚠ [検証 ${nth}] 修正失敗 → スキップ`, 'warn')
              verifyOk = false
            }
          } else if (!ansMatches && derived && conf >= 6) {
            // 問題は成立するが答えが違う → 検証モデルの答えで上書き
            log(`🔧 [検証 ${nth}] 答えを修正 (conf=${conf}): ${derived.slice(0, 50)}`)
            ans = derived
          } else if (!wellPosed && conf < 6) {
            // 信頼度が低い → とりあえず通す（人間がレビュー）
            log(`⚠ [検証 ${nth}] 低信頼度(conf=${conf}) → 一応保存（要確認）`, 'warn')
          } else {
            log(`✓ [検証 ${nth}] PASS (verdict=${verdict}, conf=${conf})`)
            if (derived && ansMatches) ans = derived
          }
        }
      } catch(e) {
        log(`⚠ [検証 ${nth}] エラー（保存続行）: ${e}`, 'warn')
      }

      if (!verifyOk) continue

      // ── 保存 ────────────────────────────────────────────────────────────
      log(`💾 [保存 ${nth}] Supabase に書き込み中...`)
      const problem = {
        id: randomHex(6),
        topic_a:      parents[0]?.topic_a ?? 'unknown',
        topic_b:      resolved === 'fusion'
          ? (parents[parents.length-1]?.topic_a ?? null)
          : (parents[0]?.topic_b ?? null),
        variation:    0,
        statement:    stmt,
        answer:       ans || null,
        difficulty:   fp.difficulty as string ?? null,
        solution:     sol,
        inspiration:  rawData.inspiration as string ?? null,
        meta:         rawData.meta as string ?? null,
        surprise:     Number(ba.surprise)              || 0,
        minimality:   Number(ba.minimality)            || 0,
        connection:   Number(ba.connection_strength)   || 0,
        inevitability:Number(ba.inevitability)         || 0,
        diff_cal:     Number(ba.difficulty_calibration)|| 0,
        total:        Number(ba.total)                 || 0,
        generation:   nextGen,
        parent_ids:   parents.map(p => p.id),
        source_file:  null,
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
      log(`✅ [完了 ${nth}] score=${score.toFixed(1)} 難=${fp.difficulty ?? '?'} → ${stmt.slice(0, 50)}...`)
      generated.push({ id: problem.id, statement: problem.statement })

      if (userId) {
        await supabase.from('usage').upsert(
          { user_id: userId, year_month: ym(), generations_count: 1 },
          { onConflict: 'user_id,year_month', ignoreDuplicates: false },
        )
      }
    }

    // ── 淘汰 ────────────────────────────────────────────────────────────────
    log('🗑️ [淘汰] 未選択問題を整理中...')
    const del = await purge(generated.map(p => p.id)).catch(() => 0)
    log(del > 0 ? `🗑️ [淘汰] ${del} 問削除` : '🗑️ [淘汰] 対象なし')

    const success = generated.length > 0
    if (success) {
      log(`🎉 [終了] ${generated.length}/${count} 問生成完了（試み${totalAttempts}回）。表示を更新してください。`)
    } else {
      log(`❌ [終了] 0/${count} 問 — ${totalAttempts}回試みたが全て修正不能でスキップ`)
    }

    clearInterval(flushInterval)
    await flushLogs(jobId)
    await supabase.from('generation_jobs').update({
      status: success ? 'done' : 'failed',
      result: { ok: success, generated, total: count, attempts: totalAttempts },
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

// ── 検証プロンプト ────────────────────────────────────────────────────────────
const makeVerify = (stmt: string, ans: string, sol: string) =>
  `以下の数学問題を厳密に検証してください。

【問題文】
${stmt}

【想定答え】
${ans}

【解法の骨格】
${sol}

## 検証手順
1. 「すべて求めよ」「全て見つけよ」型の問題か確認する
2. 反例を探す（n=0,1,境界値で問題が崩壊しないか）
3. step-by-step で実際に計算（省略なし）
4. 具体値を代入して検算
5. 「すべて求めよ」型なら：条件を満たす解が1つ以上実際に存在するか確認（空集合は問題として不成立）

\`\`\`json
{
  "is_find_all_type": false,
  "counterexample_attempt": "反例を探した結果",
  "step_by_step": "実際の計算（省略なし）",
  "numerical_check": "具体値での検算",
  "derived_answer": "計算で得られた答え（LaTeX）",
  "answer_matches": true,
  "problem_well_posed": true,
  "no_solution_exists": false,
  "issues": null,
  "confidence": 8,
  "verdict": "PASS"
}
\`\`\`

注意: "no_solution_exists": true は「すべて求めよ」系で解が1つも存在しない場合のみ true にする。
この場合は必ず "problem_well_posed": false とし、issues に「解が存在しない」と明記してください。`

// ── エントリポイント ──────────────────────────────────────────────────────────
const targetJobId = process.env.JOB_ID

if (targetJobId) {
  processJob(targetJobId).then(() => {
    console.log('Done.'); process.exit(0)
  }).catch(e => {
    console.error('Fatal:', e); process.exit(1)
  })
} else {
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
      if ((e as {code?:string}).code !== 'PGRST116') console.error('[poll]', e)
    } finally { busy = false }
  }

  console.log(`Worker 起動 (常駐モード): model=${MODEL}, poll=${POLL_MS}ms`)
  poll()
  setInterval(poll, POLL_MS)
  process.on('SIGTERM', () => process.exit(0))
  process.on('SIGINT',  () => process.exit(0))
}
