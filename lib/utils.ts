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

// Runtime synthesis also returns compact answers such as
// `P(z)=z^{6}-9z^{5}+...` without delimiters or a backslash command.  Those
// are valid TeX, but BARE_LATEX_RE alone cannot distinguish them from prose.
// Require a clearly mathematical base together with a sub/superscript so
// ordinary text containing braces is not sent to KaTeX.
const BARE_SCRIPTED_MATH_RE = /(?:\p{L}[\p{L}\p{N}]*\s*(?:\([^\n)]*\))?|[\p{L}\p{N})\]])\s*[_^]\s*(?:\{[^{}\n]+\}|[\p{L}\p{N}])/u
const NATURAL_LANGUAGE_RE = /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}]/u
const BARE_RELATION_OPERATOR_RE = /\\(?:leq?|geq?|equiv)|[=<>≤≥≡]/u

function hasBareMathRelation(value: string): boolean {
  const relation = BARE_RELATION_OPERATOR_RE.exec(value)
  if (!relation || relation.index === undefined) return false

  const left = value.slice(0, relation.index).trim()
  const right = value.slice(relation.index + relation[0].length).trim()
  return (
    /(?:[\p{L}\p{N})\]}]|\\[A-Za-z]+)$/u.test(left)
    && /^(?:[\p{L}\p{N}(\[{+\-]|\\[A-Za-z]+)/u.test(right)
  )
}

function isBareMathLine(line: string): boolean {
  const trimmed = line.trim()
  if (!trimmed || NATURAL_LANGUAGE_RE.test(trimmed)) return false
  return (
    BARE_LATEX_RE.test(trimmed)
    || BARE_SCRIPTED_MATH_RE.test(trimmed)
    || hasBareMathRelation(trimmed)
  )
}

function isMixedBareMath(value: string): boolean {
  const trimmed = value.trim()
  if (!trimmed || NATURAL_LANGUAGE_RE.test(trimmed)) return false

  // A subscript alone in Japanese prose (for example "答えは z^{6} である")
  // is ambiguous. Mixed prose is split only when a TeX command or a relation
  // gives an explicit mathematical boundary.
  return BARE_LATEX_RE.test(trimmed) || hasBareMathRelation(trimmed)
}

function splitMixedBareMathLine(line: string): { found: boolean; segments: MathSegment[] } {
  const segments: MathSegment[] = []
  let cursor = 0
  let found = false

  for (const match of line.matchAll(/[^\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}]+/gu)) {
    const run = match[0]
    const runStart = match.index ?? 0
    const leadingLength = run.match(/^[\s。、，；：！？「」『』【】]+/u)?.[0].length ?? 0
    const trailingLength = run.match(/[\s。、，；：！？「」『』【】]+$/u)?.[0].length ?? 0
    const candidateStart = runStart + leadingLength
    const candidateEnd = runStart + run.length - trailingLength
    if (candidateStart >= candidateEnd) continue

    const candidate = line.slice(candidateStart, candidateEnd)
    if (!isMixedBareMath(candidate)) continue

    if (candidateStart > cursor) {
      segments.push({ type: 'text', content: line.slice(cursor, candidateStart) })
    }
    segments.push({ type: 'inline', content: candidate })
    cursor = candidateEnd
    found = true
  }

  if (found && cursor < line.length) {
    segments.push({ type: 'text', content: line.slice(cursor) })
  }
  return { found, segments }
}

/** テキストセグメントに生 LaTeX が含まれていれば inline math として返す */
function splitBareLatex(raw: string): MathSegment[] {
  const lines = raw.split('\n')
  const parsedLines: MathSegment[][] = []
  let foundMath = false

  for (const line of lines) {
    if (isBareMathLine(line)) {
      parsedLines.push([{ type: 'inline', content: line.trim() }])
      foundMath = true
      continue
    }

    const mixed = splitMixedBareMathLine(line)
    if (mixed.found) {
      parsedLines.push(mixed.segments)
      foundMath = true
    } else {
      parsedLines.push(line.trim() ? [{ type: 'text', content: line }] : [])
    }
  }

  if (!foundMath) return [{ type: 'text', content: raw }]

  // Keep the historical line boundary after every parsed line. MathText uses
  // it to preserve the layout of generated derivations.
  const result: MathSegment[] = []
  for (const segments of parsedLines) {
    result.push(...segments)
    result.push({ type: 'text', content: '\n' })
  }
  return result
}

/**
 * 過去問の .tex から取り込んだ問題文には、数式ではない LaTeX の版面指示が
 * 混ざっている。小問を `\begin{description}\item[(1)]` で書いてあるのが典型で、
 * これは数式の外にあるため KaTeX に渡らず `\item` のまま画面に残ってしまう。
 * 一覧の上位600問のうち381問がこれで崩れていた（\item だけで1081回）。
 *
 * ここで版面指示だけを日本語の見た目に直す。数式の中身には触れない
 * （description / enumerate / itemize は数式中に現れないので安全）。
 */
export function normalizeStatement(text: string): string {
  if (!text) return ''
  let out = text

  // 文書クラス・プリアンブル（.tex 全文が入っている行がある）
  out = out.replace(/\\documentclass(\[[^\]]*\])?\{[^}]*\}/g, '')
  out = out.replace(/\\usepackage(\[[^\]]*\])?\{[^}]*\}/g, '')
  out = out.replace(/\\geometry\{[^}]*\}/g, '')
  out = out.replace(/\\(?:begin|end)\{document\}/g, '')

  // 箇条書き環境そのものは表示に不要
  out = out.replace(/\\(?:begin|end)\{(?:description|enumerate|itemize)\}/g, '')

  // \item[(1)] → 改行して (1)、ラベルなしの \item → 中黒
  out = out.replace(/\\item\s*\[([^\]]*)\]/g, '\n$1 ')
  out = out.replace(/\\item\b/g, '\n・')

  // \ding{172} / \ding{"AC} は丸数字。TeX では先頭の " が16進を意味する。
  // pifont の 172-181 が ①-⑩、182-191 が ❶-❿。
  out = out.replace(/\\ding\{"?([0-9A-Fa-f]+)\}/g, (_, digits: string) => {
    const raw = String(digits)
    const hex = /[A-Fa-f]/.test(raw) || _.includes('"')
    const code = parseInt(raw, hex ? 16 : 10)
    if (code >= 172 && code <= 181) return '①②③④⑤⑥⑦⑧⑨⑩'[code - 172]
    if (code >= 182 && code <= 191) return '❶❷❸❹❺❻❼❽❾❿'[code - 182]
    return ''
  })

  // ルビは親文字だけ残す
  out = out.replace(/\\ruby\{([^}]*)\}\{[^}]*\}/g, '$1')

  // 図版は本文に出せないので落とす
  out = out.replace(/\\includegraphics(\[[^\]]*\])?\{[^}]*\}/g, '')

  // 余白・字下げの指示は空白へ
  out = out.replace(/\\[hv]space\*?\{[^}]*\}/g, ' ')
  out = out.replace(/\\(?:medskip|bigskip|smallskip|noindent|par|newpage|clearpage)\b/g, '')

  // 見出しは中身だけ残す
  out = out.replace(/\\(?:sub)*section\*?\{([^}]*)\}/g, '\n$1\n')
  out = out.replace(/\\paragraph\*?\{([^}]*)\}/g, '\n$1 ')

  // 数式外の強調・書体指定は、Webでは親文字だけを表示する。
  // 残すと splitBareLatex が日本語を含む行全体を数式と誤認する。
  out = out.replace(/\\(?:textbf|textit|texttt|textrm|emph)\{([^{}]*)\}/g, '$1')

  // 取り込み時にエスケープが解けず文字列 "\n" のまま残っているものを改行へ。
  // \newline も同じ扱い。\noindent 等は上で処理済みなので後置で安全。
  out = out.replace(/\\newline\b/g, '\n')
  out = out.replace(/\\n(?![A-Za-z])/g, '\n')

  // 3行以上の空行は詰める
  out = out.replace(/\n{3,}/g, '\n\n')
  return out.trim()
}

export function parseMath(text: string): MathSegment[] {
  if (!text) return []
  text = normalizeStatement(text)
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
