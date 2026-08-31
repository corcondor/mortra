import { NextResponse } from 'next/server'

import fullProblemCatalog from '@/data/mortra/full-problem-catalog.json'

export const dynamic = 'force-static'

type CatalogEntry = {
  id: string
  ordinal: number
  label: string
  statement: string
  status: 'verified' | 'unresolved'
  familyId: string | null
}

export function GET() {
  const catalog = fullProblemCatalog as {
    schema: number
    sourceLabel: string
    entries: CatalogEntry[]
  }
  return NextResponse.json({
    schema: catalog.schema,
    sourceLabel: catalog.sourceLabel,
    entries: catalog.entries.map(entry => ({
      id: entry.id,
      ordinal: entry.ordinal,
      label: entry.label,
      statement: entry.statement,
      status: entry.status,
      familyId: entry.familyId,
    })),
  })
}
