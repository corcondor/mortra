export type CalculusColumnRole = 'interval' | 'endpoint' | 'critical' | 'singularity'

export type CalculusTableColumn = {
  role: CalculusColumnRole
  label: string
  x?: number
  derivative: '+' | '-' | '0' | 'undefined' | ''
  behavior: 'increase' | 'decrease' | 'maximum' | 'minimum' | 'value' | 'discontinuous'
  functionLabel: string
}

export type CalculusPlotPoint = { x: number; y: number }

export type CertifiedCalculusAnalysis = {
  version: 1
  variable: string
  functionTex: string
  derivativeTex: string
  domainTex: string
  columns: CalculusTableColumn[]
  plot: {
    viewport: { xMin: number; xMax: number; yMin: number; yMax: number }
    segments: CalculusPlotPoint[][]
    keyPoints: Array<{
      x: number
      y: number
      label: string
      role: 'endpoint' | 'critical' | 'singularity'
    }>
  }
  certificate: {
    method: string
    checks: Array<{
      id: string
      claim: string
      status: 'verified'
    }>
  }
}

/**
 * The renderer must not infer missing calculus facts. This validator enforces
 * the executable contract produced by the symbolic backend before publication.
 */
export function validateCalculusAnalysis(analysis: CertifiedCalculusAnalysis): string[] {
  const errors: string[] = []
  if (!analysis.functionTex.trim()) errors.push('function expression is missing')
  if (!analysis.derivativeTex.trim()) errors.push('derivative expression is missing')
  if (!analysis.domainTex.trim()) errors.push('domain is missing')
  if (analysis.columns.length < 3) errors.push('variation partition is too small')
  if (!analysis.columns.some(column => column.role === 'interval')) errors.push('no sign interval')
  if (!analysis.plot.segments.some(segment => segment.length >= 2)) errors.push('plot has no executable segment')
  if (!analysis.certificate.method.trim()) errors.push('verification method is missing')
  if (!analysis.certificate.checks.length) errors.push('verification checks are missing')

  let previousX = Number.NEGATIVE_INFINITY
  for (const column of analysis.columns) {
    if (column.role === 'interval') continue
    if (!Number.isFinite(column.x)) {
      errors.push(`non-finite partition point: ${column.label}`)
      continue
    }
    if ((column.x as number) <= previousX) errors.push('partition points are not strictly ordered')
    previousX = column.x as number
  }

  for (const segment of analysis.plot.segments) {
    for (let index = 1; index < segment.length; index += 1) {
      if (segment[index].x <= segment[index - 1].x) {
        errors.push('plot samples are not ordered')
        break
      }
    }
  }
  return [...new Set(errors)]
}
