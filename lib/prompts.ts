/**
 * 作問プロンプト集（mutate_problems.py からの移植）
 */

export const SYSTEM_INSTRUCTION = `あなたは数学オリンピアード・難関大学入試問題の作問専門家です。
美しい数学問題とは：驚き（非自明な結論）、最小性（余分な条件なし）、
強い接続（複数分野の深い融合）、必然性（その答えしかありえない感覚）、
難易度較正（解法の糸口は掴めるが完答は困難）を備えています。

以下の厳密なJSON形式のみで出力してください（他の文章は一切不要）:
\`\`\`json
{
  "inspiration": "なぜこの2分野を組み合わせるか（3-5文）",
  "exploration": [
    {"approach": "アプローチ案1", "why_discard": "棄却または採用理由"},
    {"approach": "アプローチ案2", "why_discard": "棄却または採用理由"},
    {"approach": "アプローチ案3", "why_discard": "採用 - 美的基準を最も満たす"}
  ],
  "drafts": [
    {"version": 1, "problem_statement": "初稿（LaTeX）", "intended_answer": "答え", "self_critique": "改善点"},
    {"version": 2, "problem_statement": "改訂版（LaTeX）", "intended_answer": "答え", "self_critique": "改善点"},
    {"version": 3, "problem_statement": "最終版（LaTeX）", "intended_answer": "答え", "self_critique": "採用理由"}
  ],
  "final_problem": {
    "statement": "最終問題文（LaTeX完全版）",
    "answer": "答え（LaTeX）",
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
    "comment": "美的分析（2-3文）"
  },
  "meta": "作問過程で発見した数学的洞察（1-2文）"
}
\`\`\``

export interface ParentProblem {
  id: string
  statement: string
  answer?: string | null
  solution?: string | null
  inspiration?: string | null
  topic_a: string
  topic_b?: string | null
}

function formatProblem(p: ParentProblem, idx?: number): string {
  const header = idx != null ? `【問題${idx}】` : '【問題】'
  const lines = [header, p.statement, `答え: ${p.answer ?? ''}`]
  if (p.solution)     lines.push(`解法の骨格: ${p.solution}`)
  if (p.inspiration)  lines.push(`数学的洞察: ${p.inspiration}`)
  return lines.join('\n')
}

export function makeAnalysisPrompt(p: ParentProblem): string {
  return `以下の数学問題の「数学的構造と美しさの本質」を深く分析してください。

${formatProblem(p)}

以下の観点で分析し、JSONで返してください：
\`\`\`json
{
  "core_structure": "この問題の核心的な数学的構造（どの定理・変換・対応関係が本質か）",
  "proof_skeleton": "解法の骨格（どの順序で何を経由して答えに至るか）",
  "beauty_source": "なぜこの答えが必然なのか（偶然ではない理由）",
  "key_technique": "解法の最も重要な一手（この視点転換がなければ解けない）",
  "hidden_connection": "表面上は見えない深い数学的つながり（背後にある構造）",
  "generalization": "この問題を一般化・拡張するとどうなるか",
  "weakness": "問題として改善できる点・美しさを損なっている部分"
}
\`\`\``
}

export function makeSimilarPrompt(p: ParentProblem, analysis?: Record<string, string>): string {
  const analysisBlock = analysis ? `
【構造分析】
- 核心的数学構造: ${analysis.core_structure ?? ''}
- 証明の骨格: ${analysis.proof_skeleton ?? ''}
- 必然性の源泉: ${analysis.beauty_source ?? ''}
- 解法の核心一手: ${analysis.key_technique ?? ''}
- 隠れた深い接続: ${analysis.hidden_connection ?? ''}
- 改善点: ${analysis.weakness ?? ''}
` : ''

  return `${SYSTEM_INSTRUCTION}

以下の問題の「数学的構造・解法の骨格・必然性」を正確に引き継いだ類題を生成してください。
${analysisBlock}
${formatProblem(p)}

【類題生成の指示】
1. 問題文は元の問題と同等かより短く・シンプルに（設定を増やさない）
2. 表面的な数値・関数・設定は変える（新鮮さのため）
3. しかし以下は必ず保つ：
   - 核心となる数学的構造（定理・変換・対応関係）
   - 解法の「鍵となる一手」の性質
   - 答えが必然的に導かれる論理の骨格
4. 単なる数値置き換えや表現の言い換えは禁止
5. 元の問題よりさらに「必然性」が高い問題を目指す
6. 答えは元と異なること

JSON形式のみで回答してください。`
}

export function makeFusionPrompt(problems: ParentProblem[]): string {
  const probTexts = problems.map((p, i) => formatProblem(p, i + 1)).join('\n\n')

  return `${SYSTEM_INSTRUCTION}

# 参考にする親問題（解法の核心を抽出すること）

${probTexts}

---

# あなたのタスク：「構造的融合」による新問題の作問

## ゴールのイメージ：「京大の問い・東工大の手数」

- **問題文は1つの問い**（絶対禁止：(1)(2)への分割）
  - 誘導なし・ヒントなし・1文か2文で「〜を求めよ」で終わる
  - 京大入試のように、問いはシンプルだが何から手をつければいいか一瞬わからない

- **解法の中に融合がある**（計算量・手数は東工大レベル）
  - 問題文を見ただけでは「どこが融合しているか」わからない
  - 解いていく過程で突然、全く別の分野の道具が必要になる
  - 完答までに複数の変換・操作・評価が必要で、計算の手数が多い

- **答えはコンパクト**：整数・分数・既知の定数（π, e, √など）が望ましい

## ✅ 構造的融合の例
$\\sum_{k=0}^{n}\\binom{n}{k}\\frac{(-1)^k}{k+x}$ を求めよ。
→ シンプルな問い。しかし解くにはベータ関数・部分分数・二項定理・積分交換が必要。

## 作問手順（必ずこの順番で考えること）

**Step 1** 親問題それぞれから「解くときに不可欠な一手」を1つ言語化する
**Step 2** 核心同士が「依存しあう」状況を設計する（AをやったからこそBが必要になる）
**Step 3** その依存関係を自然に誘導する最小の問題文を書く（2文以内・(1)(2)禁止）
**Step 4** 解法と答えを検証する（両方の核心が必要か、答えが美しいか）

## 禁止事項（厳守）
- **(1)(2)への分割** ── 最大の禁止事項
- 誘導・ヒント・小問を問題文に入れること
- 問題文に両親の設定を両方書くこと（足し算になる）
- 問題文が長くなること（2文以内を目標に）

JSON形式のみで回答してください。`
}

export function makeExpandPrompt(p: ParentProblem): string {
  return `${SYSTEM_INSTRUCTION}

以下の問題を「より深い階層へ一般化」した問題を作ってください。

${formatProblem(p)}

【高次元化・一般化の指示】
1. 単なるnへのパラメータ置き換えではなく：
   - 背後にある数学的構造がより鮮明に見える一般化を目指す
   - 元の問題が「n=2（または特定値）の特殊ケース」になる形が理想

2. 一般化の方向性（どれか1つ以上）：
   - より抽象的な代数構造へ（群・環・加群など）
   - より高次元の幾何学的対象へ
   - より一般的な関数族・作用素へ
   - 有限から無限次元へ、または離散から連続へ

3. 答えの要件：
   - パラメータnや一般的な構造の美しい関数として表される
   - 元の答えを特殊ケースとして内包する

JSON形式のみで回答してください。`
}

/** AIの応答から JSON を抽出 */
export function extractJson(text: string): Record<string, unknown> | null {
  // コードブロック内の JSON を優先
  const codeMatch = text.match(/```(?:json)?\s*([\s\S]*?)```/)
  const candidate = codeMatch ? codeMatch[1] : text

  // { ... } の最外殻を探す
  const start = candidate.indexOf('{')
  const end   = candidate.lastIndexOf('}')
  if (start === -1 || end === -1) return null

  try {
    return JSON.parse(candidate.slice(start, end + 1))
  } catch {
    return null
  }
}
