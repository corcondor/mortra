import type { Metadata } from 'next'
import { EngineeringGeometryResearchPage } from '@/components/mortra/EngineeringGeometryResearchPage'

export const metadata: Metadata = {
  title: '3D設計と機械製図 | MORTRA',
  description: '次元に依存しない8つの射から、厳密な3D形状、第三角法、断面、寸法、STEP・DXFを同じ構成DAGで生成した実験です。',
  alternates: {
    canonical: 'https://mortra.ai/ja/research/engineering-geometry',
    languages: {
      en: 'https://mortra.ai/research/engineering-geometry',
      ja: 'https://mortra.ai/ja/research/engineering-geometry',
    },
  },
}

export default function JapaneseEngineeringGeometryPage() {
  return <EngineeringGeometryResearchPage lang="ja" />
}
