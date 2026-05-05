/** LaTeX デリミタを parse して { type, content }[] に分解
 *
 * 対応形式（優先順）:
 *   $$...$$   → block  (display math)
 *   \[...\]   → block
 *   \(...\)   → inline
 *   $...$     → inline
 */
export type MathSegment =
  | { type: 'text';   content: string }
  | { type: 'inline'; content: string }
  | { type: 'block';  content: string }

// 優先度: $$ > \[..\] > \(..\) > $
// ※ $$ を先に試すことで $$ が単独 $ × 2 と誤認識されない
const MATH_RE = /\$\$([\s\S]*?)\$\$|\\\[([\s\S]*?)\\\]|\\\(([\s\S]*?)\\\)|\$((?:[^$\\]|\\.)*?)\$/g

// デリミタなしの生 LaTeX を検出する正規表現
// \dfrac, \sqrt, \frac, \int, \sum 等のコマンドが含まれていれば数式とみなす
const BARE_LATEX_RE = /\\(?:d?frac|sqrt|int|oint|iint|sum|prod|lim|inf[ty]+|pmod|equiv|[lg]eq|binom|quad|qquad|cdot|mathbb|mathbf|mathrm|text|overline|underline|vec|hat|bar|tilde|widehat|widetilde|begin|end|left|right|[Pp]i|alpha|beta|gamma|[Dd]elta|epsilon|zeta|eta|theta|lambda|mu|nu|xi|rho|sigma|tau|phi|chi|psi|omega|partial|nabla|forall|exists|in|subset|cup|cap|to|iff|implies|land|lor|neg|pm|mp|times|div|otimes|oplus)\b/

/** テキストセグメントに生 LaTeX が含まれていれば inline math として返す */
function splitBareLatex(raw: string): MathSegment[] {
  if (!BARE_LATEX_RE.test(raw)) return [{ type: 'text', content: raw }]
  // 行単位で「LaTeX が多い行」と「普通のテキスト行」を分ける
  const lines = raw.split('\n')
  const result: MathSegment[] = []
  for (const line of lines) {
    if (BARE_LATEX_RE.test(line)) {
      // この行は数式扱い
      result.push({ type: 'inline', content: line.trim() })
    } else if (line.trim()) {
      result.push({ type: 'text', content: line })
    }
    result.push({ type: 'text', content: '\n' })
  }
  return result
}

export function parseMath(text: string): MathSegment[] {
  if (!text) return []
  const segs: MathSegment[] = []
  let lastIndex = 0
  let m: RegExpExecArray | null

  MATH_RE.lastIndex = 0
  while ((m = MATH_RE.exec(text)) !== null) {
    if (m.index > lastIndex) {
      // デリミタなし LaTeX を検出してセグメント化
      const raw = text.slice(lastIndex, m.index)
      segs.push(...splitBareLatex(raw))
    }
    if (m[1] !== undefined) {
      segs.push({ type: 'block',  content: m[1] })   // $$...$$
    } else if (m[2] !== undefined) {
      segs.push({ type: 'block',  content: m[2] })   // \[...\]
    } else if (m[3] !== undefined) {
      segs.push({ type: 'inline', content: m[3] })   // \(...\)
    } else if (m[4] !== undefined) {
      segs.push({ type: 'inline', content: m[4] })   // $...$
    }
    lastIndex = MATH_RE.lastIndex
  }

  if (lastIndex < text.length) {
    segs.push(...splitBareLatex(text.slice(lastIndex)))
  }
  return segs
}

/** 問題文から最初のテキストを抜き出してスニペットとして使う */
export function extractSnippet(statement: string, maxLen = 60): string {
  const segs = parseMath(statement)
  const text = segs
    .filter(s => s.type === 'text')
    .map(s => s.content.replace(/\s+/g, ' ').trim())
    .join(' ')
  return text.length > maxLen ? text.slice(0, maxLen) + '…' : text
}

/** query で statement / topic を OR 検索 */
export function filterProblems<T extends { statement: string; topic_a: string; topic_b?: string | null }>(
  problems: T[],
  query: string,
): T[] {
  const q = query.toLowerCase().trim()
  if (!q) return problems
  return problems.filter(p =>
    p.statement.toLowerCase().includes(q) ||
    p.topic_a.toLowerCase().includes(q) ||
    (p.topic_b ?? '').toLowerCase().includes(q),
  )
}

export function cn(...classes: (string | undefined | false | null)[]) {
  return classes.filter(Boolean).join(' ')
}
