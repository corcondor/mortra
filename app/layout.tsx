import type { Metadata } from 'next'
import './globals.css'
import { SpeedInsights } from '@vercel/speed-insights/next'
import { Analytics }     from '@vercel/analytics/next'

export const metadata: Metadata = {
  title: 'Sakumon Station',
  description: 'AIが東大・京大レベルの数学問題を自動生成。良問を選び抜いてXで発信したい人のための、作問・管理ツールです。',
  openGraph: {
    title: 'Sakumon Station',
    description: 'AIが東大・京大レベルの数学問題を自動生成。良問を選び抜いてXで発信したい人のための、作問・管理ツールです。',
    url: 'https://sakumon-web.vercel.app/',
    siteName: 'Sakumon Station',
    locale: 'ja_JP',
    type: 'website',
  },
  twitter: {
    card: 'summary',
    title: 'Sakumon Station',
    description: 'AIが東大・京大レベルの数学問題を自動生成。良問を選び抜いてXで発信したい人のための、作問・管理ツールです。',
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
      <body className="min-h-screen overflow-hidden text-white">
        {children}
        <SpeedInsights />
        <Analytics />
      </body>
    </html>
  )
}
