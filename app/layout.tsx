import type { Metadata } from 'next'
import './globals.css'
import { SpeedInsights } from '@vercel/speed-insights/next'
import { Analytics } from '@vercel/analytics/next'

// 既定は英語。日本語は /ja が自前の metadata で上書きする。
// 数字はここに書かない。正本は lib/mortra/i18n.ts の FIGURES。
const TITLE = 'MORTRA — Finite primitives. Infinite mathematics.'
const DESCRIPTION =
  'MORTRA researches how mathematics can be represented, transformed and verified through a compact system of typed objects, morphisms and invariants. No neural components in the reasoning path.'

export const metadata: Metadata = {
  metadataBase: new URL('https://mortra.ai'),
  title: TITLE,
  description: DESCRIPTION,
  applicationName: 'MORTRA',
  icons: {
    icon: '/favicon.svg',
    shortcut: '/favicon.svg',
    apple: '/apple-icon.svg',
  },
  alternates: { canonical: '/' },
  keywords: [
    'MORTRA', 'symbolic reasoning', 'automated theorem proving', 'geometry proof',
    'mathematical structure', 'proof certificate', 'IMO geometry', 'non-LLM reasoning',
    '数学AI', '記号推論', '幾何証明', '自動作問',
  ],
  authors: [{ name: 'MORTRA' }],
  creator: 'MORTRA',
  publisher: 'MORTRA',
  robots: { index: true, follow: true },
  openGraph: {
    title: TITLE,
    description: DESCRIPTION,
    url: 'https://mortra.ai/',
    siteName: 'MORTRA',
    locale: 'en_US',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: TITLE,
    description: DESCRIPTION,
  },
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
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
