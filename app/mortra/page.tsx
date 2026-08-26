import type { Metadata } from 'next'
import { MortraProductPage } from '@/components/mortra/MortraProductPage'
import { getCopy } from '@/lib/mortra/i18n'

const t = getCopy('en')

export const metadata: Metadata = {
  title: t.meta.title,
  description: t.meta.description,
  alternates: { canonical: '/', languages: { en: '/', ja: '/ja', 'x-default': '/' } },
}

export default function MortraPage() {
  return <MortraProductPage lang="en" />
}
