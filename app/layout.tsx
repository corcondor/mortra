import type { Metadata } from 'next'
import './globals.css'
import { SpeedInsights } from '@vercel/speed-insights/next'
import { Analytics } from '@vercel/analytics/next'

const TITLE = 'MORTRA-1 — 数学を、動かす。'
const DESCRIPTION =
  '外部LLMを使わずIMO幾何25/30。複数の記号推論器を協調させ、数学を解き、作る研究システム。'

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
      <body className="min-h-[100dvh] bg-[#09090b] text-zinc-100">
        {children}
        <SpeedInsights />
        <Analytics />
      </body>
    </html>
  )
}
