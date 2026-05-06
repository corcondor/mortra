import type { Metadata } from 'next'
import './globals.css'
import { SpeedInsights } from '@vercel/speed-insights/next'
import { Analytics }     from '@vercel/analytics/next'

export const metadata: Metadata = {
  title: 'Sakumon Station',
  description: '難関大学・数学オリンピアード 問題生成・キュレーションプラットフォーム',
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
      <body className="min-h-screen overflow-hidden text-white">
        {children}
        <SpeedInsights />
        <Analytics />
      </body>
    </html>
  )
}
