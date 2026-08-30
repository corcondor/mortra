import type { Metadata } from 'next'
import { EngineeringGeometryResearchPage } from '@/components/mortra/EngineeringGeometryResearchPage'

export const metadata: Metadata = {
  title: 'Engineering Geometry | MORTRA',
  description: 'Eight dimension-independent morphisms generate exact 3D solids, third-angle drawings, sections, dimensions and exchange artifacts from one construction DAG.',
  alternates: {
    canonical: 'https://mortra.ai/research/engineering-geometry',
    languages: {
      en: 'https://mortra.ai/research/engineering-geometry',
      ja: 'https://mortra.ai/ja/research/engineering-geometry',
    },
  },
}

export default function EngineeringGeometryPage() {
  return <EngineeringGeometryResearchPage lang="en" />
}
