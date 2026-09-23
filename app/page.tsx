import type { Metadata } from 'next'
import { MortraProductPage } from '@/components/mortra/MortraProductPage'
import { getWorldCopy } from '@/lib/mortra/i18n'

const t = getWorldCopy('en')

export const metadata: Metadata = {
  title: t.meta.title,
  description: t.meta.description,
  alternates: {
    canonical: '/',
    languages: { en: '/', ja: '/ja', 'x-default': '/' },
  },
  openGraph: { title: t.meta.title, description: t.meta.description, url: 'https://mortra.ai/', locale: 'en_US' },
  twitter: { card: 'summary_large_image', title: t.meta.title, description: t.meta.description },
}

export default function Home() {
  return <MortraProductPage lang="en" />
}
