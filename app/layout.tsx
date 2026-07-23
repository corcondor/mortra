import type { Metadata } from 'next'
import './globals.css'
import { SpeedInsights } from '@vercel/speed-insights/next'
import { Analytics }     from '@vercel/analytics/next'

export const metadata: Metadata = {
  title: '作問ステーション | Sakumon Station',
  description: 'MathOSで数学問題を生成・検証・比較し、作問過程を管理するワークスペースです。',
  openGraph: {
    title: '作問ステーション | Sakumon Station',
    description: 'MathOSで数学問題を生成・検証・比較し、作問過程を管理するワークスペースです。',
    url: 'https://sakumon-web.vercel.app/',
    siteName: 'Sakumon Station',
    locale: 'ja_JP',
    type: 'website',
  },
  twitter: {
    card: 'summary',
    title: '作問ステーション | Sakumon Station',
    description: 'MathOSで数学問題を生成・検証・比較し、作問過程を管理するワークスペースです。',
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
      <body className="min-h-screen overflow-hidden text-[#14213d]">
        {children}
        <SpeedInsights />
        <Analytics />
      </body>
    </html>
  )
}
