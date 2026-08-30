import { MortraResearchPage } from '@/components/mortra/MortraResearchPage'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Research | MORTRA',
  description: 'Explore MORTRA through certified proof replay, typed morphism maps, reproducible benchmarks and a live public research stream.',
  alternates: {
    canonical: 'https://mortra.ai/research',
    languages: { en: 'https://mortra.ai/research', ja: 'https://mortra.ai/ja/research' },
  },
}

export default function ResearchPage() {
  return <MortraResearchPage lang="en" />
}
