import type { Metadata } from 'next'
import { MortraProductPage } from '@/components/mortra/MortraProductPage'
import { getCopy } from '@/lib/mortra/i18n'

const t = getCopy('ja')

export const metadata: Metadata = {
  title: t.meta.title,
  description: t.meta.description,
  alternates: {
    canonical: '/ja',
    languages: { en: '/', ja: '/ja', 'x-default': '/' },
  },
  openGraph: { title: t.meta.title, description: t.meta.description, url: 'https://mortra.ai/ja', locale: 'ja_JP' },
  twitter: { card: 'summary_large_image', title: t.meta.title, description: t.meta.description },
}

export default function JaPage() {
  return <MortraProductPage lang="ja" />
}
