import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Math Corpus',
  description: '難関大学数学 問題データベース',
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
      </body>
    </html>
  )
}
