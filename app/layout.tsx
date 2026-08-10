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
const TITLE = 'Sakumon by MORTRA'
const DESCRIPTION =
  '数学問題を作る人のためのワークスペース。生成・検証・比較・作図・書き出しまでを一つの流れで扱います。'

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  applicationName: 'Sakumon',
  openGraph: {
    title: TITLE,
    description: DESCRIPTION,
    url: 'https://sakumon-web.vercel.app/',
    siteName: 'Sakumon by MORTRA',
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
      </head>
      <body className="min-h-screen overflow-hidden bg-[#09090b] text-zinc-100">
        {children}
        <SpeedInsights />
        <Analytics />
      </body>
    </html>
  )
}
