'use client'
import katex from 'katex'
import { parseMath } from '@/lib/utils'

interface Props {
  text: string
  className?: string
  /** true にすると block math を中央揃えで大きく表示 */
  large?: boolean
}

function safeKatex(latex: string, display: boolean): string {
  try {
    return katex.renderToString(latex.trim(), {
      displayMode: display,
      throwOnError: false,
      strict:       false,
      trust:        false,
      macros: {
        '\\R':   '\\mathbb{R}',
        '\\C':   '\\mathbb{C}',
        '\\Z':   '\\mathbb{Z}',
        '\\N':   '\\mathbb{N}',
        '\\Q':   '\\mathbb{Q}',
      },
    })
  } catch {
    // フォールバック: 生テキストをそのまま表示
    return `<code class="text-red-400 text-xs px-1 bg-red-950/30 rounded">${latex.slice(0, 60)}</code>`
  }
}

export function MathText({ text, className = '', large = false }: Props) {
  if (!text) return null
  const segs = parseMath(text)

  return (
    <span className={className}>
      {segs.map((seg, i) => {
        if (seg.type === 'text') {
          return (
            <span key={i} style={{ whiteSpace: 'pre-wrap' }}>
              {seg.content}
            </span>
          )
        }

        const html = safeKatex(seg.content, seg.type === 'block')

        if (seg.type === 'block') {
          return (
            <span
              key={i}
              className={`block w-full overflow-x-auto py-1 text-center ${large ? 'my-3' : 'my-1.5'}`}
              dangerouslySetInnerHTML={{ __html: html }}
            />
          )
        }

        // inline
        return (
          <span
            key={i}
            className="inline align-baseline"
            dangerouslySetInnerHTML={{ __html: html }}
          />
        )
      })}
    </span>
  )
}
