/**
 * LaTeX ドキュメント生成 + リモートコンパイル (texlive.net)
 *
 * ローカル検証済み: scripts/test-tetsuryoku.tex
 *  - lualatex (MiKTeX 25.12) ✓
 *  - texlive.net latexcgi (lualatex) ✓ ~3.5s
 */

const LATEXCGI_URL = 'https://texlive.net/cgi-bin/latexcgi'

// ── 鉄緑会風プリアンブル ──────────────────────────────────────────────────

const TETSURYOKU_PREAMBLE = String.raw`\documentclass[a4paper,11pt]{ltjsarticle}
\usepackage{amsmath,amssymb}
\usepackage{tikz}
\usetikzlibrary{calc,arrows.meta,intersections,patterns,decorations.markings}
\usepackage[margin=20mm]{geometry}
\usepackage[most]{tcolorbox}
\pagestyle{empty}

\newtcolorbox{mondaibox}[1][]{
  enhanced, sharp corners,
  colback=white, colframe=black, boxrule=0.6pt,
  attach boxed title to top left={yshift=-2.5mm, xshift=4mm},
  boxed title style={colback=white, colframe=white, boxrule=0pt},
  title={\textbf{【#1】}}, coltitle=black,
  top=3mm, bottom=2.5mm, left=3mm, right=3mm,
  overlay={
    \draw[line width=1pt] ([xshift=1.2mm,yshift=-1.2mm]frame.north west) -- ++(3mm,0)
                          ([xshift=1.2mm,yshift=-1.2mm]frame.north west) -- ++(0,-3mm);
    \draw[line width=1pt] ([xshift=-1.2mm,yshift=-1.2mm]frame.north east) -- ++(-3mm,0)
                          ([xshift=-1.2mm,yshift=-1.2mm]frame.north east) -- ++(0,-3mm);
    \draw[line width=1pt] ([xshift=1.2mm,yshift=1.2mm]frame.south west) -- ++(3mm,0)
                          ([xshift=1.2mm,yshift=1.2mm]frame.south west) -- ++(0,3mm);
    \draw[line width=1pt] ([xshift=-1.2mm,yshift=1.2mm]frame.south east) -- ++(-3mm,0)
                          ([xshift=-1.2mm,yshift=1.2mm]frame.south east) -- ++(0,3mm);
  },
}

\newcommand{\sectionhead}[1]{\vspace{4mm}\noindent\tikz[baseline=-0.6ex]\fill[black] (0,0) -- (0.28,0.11) -- (0,0.22) -- cycle;\ \textbf{#1}\par\vspace{1mm}\hrule height 0.3pt\vspace{2mm}}
`

export interface TetsuryokuDoc {
  title: string
  statement: string
  solution?: string | null
  tikz?: string | null
  features?: string | null
  tags?: string[]
  difficulty?: number | null
  points?: number | null
}

/** 鉄緑会風 解説プリント1枚の LaTeX ソースを組む */
export function buildTetsuryokuTex(doc: TetsuryokuDoc): string {
  const metaParts: string[] = []
  if (doc.difficulty) metaParts.push(`難易度 ${'★'.repeat(Math.min(5, Math.ceil(doc.difficulty / 2)))}`)
  if (doc.points) metaParts.push(`${doc.points}点`)
  if (doc.tags?.length) metaParts.push(doc.tags.slice(0, 5).join('・'))
  const metaLine = metaParts.length
    ? String.raw`\begin{flushright}\small ${escapeTexText(metaParts.join('　／　'))}\end{flushright}`
    : ''

  const tikzBlock = doc.tikz
    ? String.raw`
\begin{center}
${doc.tikz}
\end{center}
`
    : ''

  const shishin = doc.features
    ? String.raw`
\sectionhead{指針}
${doc.features}
`
    : ''

  const kaito = doc.solution
    ? String.raw`
\sectionhead{解答}
${doc.solution}
`
    : ''

  return `${TETSURYOKU_PREAMBLE}
\\begin{document}
\\begin{center}{\\large \\textbf{数学 解説プリント}}\\end{center}
${metaLine}
\\vspace{1mm}

\\begin{mondaibox}[${escapeTexText(doc.title).slice(0, 40)}]
${doc.statement}
\\end{mondaibox}
${shishin}${tikzBlock}${kaito}
\\end{document}
`
}

/** TikZ 単体プレビュー用 standalone ドキュメント */
export function buildTikzStandalone(tikz: string): string {
  return String.raw`\documentclass[tikz,border=10pt]{standalone}
\usetikzlibrary{calc,arrows.meta,intersections,patterns,decorations.markings}
\begin{document}
${tikz}
\end{document}
`
}

/** タイトル等のプレーンテキストに含まれる TeX 特殊文字をエスケープ */
function escapeTexText(s: string): string {
  return s.replace(/([#%&_{}])/g, '\\$1').replace(/\\\\/g, '')
}

export interface CompileResult {
  ok: boolean
  pdf?: ArrayBuffer
  log?: string
}

/**
 * texlive.net でコンパイル。
 * 成功: 301 → PDF URL へリダイレクト（fetch が自動追跡）→ %PDF バイト列
 * 失敗: text/html のログが返る
 */
export async function compileTex(
  tex: string,
  engine: 'lualatex' | 'pdflatex' = 'lualatex',
): Promise<CompileResult> {
  const form = new FormData()
  form.append('filecontents[]', tex)
  form.append('filename[]', 'document.tex')
  form.append('engine', engine)
  form.append('return', 'pdf')

  const res = await fetch(LATEXCGI_URL, {
    method: 'POST',
    body: form,
    signal: AbortSignal.timeout(120_000),
  })

  const buf = await res.arrayBuffer()
  const head = new TextDecoder().decode(buf.slice(0, 5))

  if (head.startsWith('%PDF')) {
    return { ok: true, pdf: buf }
  }
  // 失敗時はログテキスト。エラー行を抽出
  const logText = new TextDecoder().decode(buf)
  const errLines = logText
    .split('\n')
    .filter(l => l.startsWith('!') || /^l\.\d+/.test(l))
    .slice(0, 12)
    .join('\n')
  return { ok: false, log: errLines || logText.slice(-1500) }
}
