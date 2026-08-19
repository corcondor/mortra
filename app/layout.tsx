import type { Metadata } from 'next'
import './globals.css'
import { SpeedInsights } from '@vercel/speed-insights/next'
import { Analytics }     from '@vercel/analytics/next'

/*
 * ブランド構造。
 *
 *   MORTRA   会社・研究・基盤。公開。ログイン不要。「One structure. Many representations.」
 *   Sakumon  その最初の応用。作問者のための業務ワークスペース。ログインの内側。
 *
 * 公開名だけを先に変える。リポジトリ名・モジュール名・API は動かさない。
 * 内部 rename は作業量の割に価値が薄く、先に確立すべきは
 *   MORTRA  = なぜ / 研究 / 技術
 *   Sakumon = 今日から使えて金を払える物
 * という関係の方だから。
 *
 * MathOS は内部名として残す（= MORTRA Core）。
 */
const TITLE = 'MORTRA-1 — Mathematics, in motion.'
const DESCRIPTION =
  '型付き構造、記号推論、検証可能な問題生成を公開するMORTRA-1 β。'

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  applicationName: 'MORTRA-1',
  openGraph: {
    title: TITLE,
    description: DESCRIPTION,
    url: 'https://sakumon-web.vercel.app/',
    siteName: 'MORTRA-1',
    locale: 'ja_JP',
    type: 'website',
  },
  twitter: {
    card: 'summary',
    title: TITLE,
    description: DESCRIPTION,
  },
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja">
      <head>
        {/* KaTeX CSS + fonts via CDN — ローカルだとフォントパスが狂うため CDN を使用 */}
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css"
          crossOrigin="anonymous"
        />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Zen+Old+Mincho:wght@500;700;900&family=Noto+Sans+JP:wght@400;500;700&family=JetBrains+Mono:wght@400;500;600&display=swap"
          rel="stylesheet"
        />
      </head>
      {/*
        overflow-hidden を body に直接付けていたため、公開ページ（/mortra 以下）が
        スクロールできなかった。業務画面だけ止めたいので、globals.css の
        body:has([data-app-shell]) に任せ、ここでは止めない。
      */}
      <body className="min-h-[100dvh] bg-[#09090b] text-zinc-100">
        {children}
        <SpeedInsights />
        <Analytics />
      </body>
    </html>
  )
}
