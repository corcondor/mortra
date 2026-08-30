import type { Metadata } from 'next'
import { MortraResearchPage } from '@/components/mortra/MortraResearchPage'

export const metadata: Metadata = {
  title: '研究 | MORTRA',
  description: '証明の再生、型付き射の地図、再現可能な評価結果、公開リポジトリの更新からMORTRAの研究過程をたどれます。',
  alternates: {
    canonical: 'https://mortra.ai/ja/research',
    languages: { en: 'https://mortra.ai/research', ja: 'https://mortra.ai/ja/research' },
  },
}

export default function JapaneseResearchPage() {
  return <MortraResearchPage lang="ja" />
}
