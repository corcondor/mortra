'use client'

import { Eye, FileCode2 } from 'lucide-react'
import { BlockMath, InlineMath } from 'react-katex'
import type { Lang } from '@/lib/mortra/i18n'
import styles from '@/app/mortra/mortra.module.css'

type LiveTexPreviewProps = {
  lang: Lang
  sourceA: string
  sourceB?: string
  mode: 'solve' | 'fusion' | 'draw'
}

const MATH_PATTERN = /(\$\$[\s\S]*?\$\$|\\\[[\s\S]*?\\\]|\$[^$\n]+\$|\\\([\s\S]*?\\\))/g

function MathSource({ source }: { source: string }) {
  const normalized = source.trim()
  if (!normalized) return <span className={styles.texEmpty}>∅</span>

  const parts = normalized.split(MATH_PATTERN).filter(Boolean)
  const hasDelimitedMath = parts.some(part => (
    (part.startsWith('$$') && part.endsWith('$$'))
    || (part.startsWith('\\[') && part.endsWith('\\]'))
    || (part.startsWith('$') && part.endsWith('$'))
    || (part.startsWith('\\(') && part.endsWith('\\)'))
  ))

  if (!hasDelimitedMath && /\\[A-Za-z]+|[_^{}]/.test(normalized) && !/[ぁ-んァ-ン一-龯]/.test(normalized)) {
    return <BlockMath math={normalized} renderError={() => <code>{normalized}</code>} />
  }

  return (
    <div className={styles.texDocument}>
      {parts.map((part, index) => {
        if (part.startsWith('$$') && part.endsWith('$$')) {
          return <BlockMath key={`${index}-${part}`} math={part.slice(2, -2)} renderError={() => <code>{part}</code>} />
        }
        if (part.startsWith('\\[') && part.endsWith('\\]')) {
          return <BlockMath key={`${index}-${part}`} math={part.slice(2, -2)} renderError={() => <code>{part}</code>} />
        }
        if (part.startsWith('$') && part.endsWith('$')) {
          return <InlineMath key={`${index}-${part}`} math={part.slice(1, -1)} renderError={() => <code>{part}</code>} />
        }
        if (part.startsWith('\\(') && part.endsWith('\\)')) {
          return <InlineMath key={`${index}-${part}`} math={part.slice(2, -2)} renderError={() => <code>{part}</code>} />
        }
        return <span key={`${index}-${part}`} className={styles.texText}>{part}</span>
      })}
    </div>
  )
}

export function LiveTexPreview({ lang, sourceA, sourceB, mode }: LiveTexPreviewProps) {
  const ja = lang === 'ja'
  return (
    <section className={styles.texPreviewPane} aria-label={ja ? 'TeX組版プレビュー' : 'TeX typeset preview'}>
      <header className={styles.workspacePaneHeader}>
        <span><Eye size={14} aria-hidden="true" />TEX PREVIEW</span>
        <span className={styles.previewStatus}><i />{ja ? '即時組版' : 'Live typeset'}</span>
      </header>

      <div className={styles.texPreviewBody}>
        <article className={styles.texPreviewProblem}>
          <header><span>A</span><small>{ja ? '入力問題' : 'Input problem'}</small></header>
          <MathSource source={sourceA} />
        </article>

        {mode === 'fusion' && (
          <article className={styles.texPreviewProblem}>
            <header><span>B</span><small>{ja ? '融合する問題' : 'Fusion parent'}</small></header>
            <MathSource source={sourceB ?? ''} />
          </article>
        )}

        <footer className={styles.texPreviewFooter}>
          <FileCode2 size={13} aria-hidden="true" />
          <span>{mode === 'draw'
            ? (ja ? '解答と図を同じ数学状態から生成' : 'Generate solution and figure from one mathematical state')
            : mode === 'fusion'
              ? (ja ? 'A・Bを別々の端点として保持' : 'Keep A and B as separate endpoints')
              : (ja ? '問題文・解答・証明書を一つの実行で返す' : 'Return statement, solution and certificate in one run')}</span>
        </footer>
      </div>
    </section>
  )
}
