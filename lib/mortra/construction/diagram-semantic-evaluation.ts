import {
  verifyCellComplex,
  type DiagramCell,
  type TypedCellComplex,
} from './diagrammatic-complex'

export type SemanticDiagramScore = {
  valid: boolean
  strictPass: boolean
  cellTypeF1: number
  incidenceF1: number
  labelF1: number
  topologyF1: number
  eulerMatch: boolean
  boundarySquaredResiduals: number
}

const f1 = (reference: Map<string, number>, candidate: Map<string, number>) => {
  let referenceTotal = 0
  let candidateTotal = 0
  let intersection = 0
  for (const count of reference.values()) referenceTotal += count
  for (const count of candidate.values()) candidateTotal += count
  for (const [key, count] of reference) {
    intersection += Math.min(count, candidate.get(key) ?? 0)
  }
  if (referenceTotal === 0 && candidateTotal === 0) return 1
  if (referenceTotal === 0 || candidateTotal === 0) return 0
  const precision = intersection / candidateTotal
  const recall = intersection / referenceTotal
  return precision + recall === 0 ? 0 : (2 * precision * recall) / (precision + recall)
}

function histogram(values: string[]) {
  const result = new Map<string, number>()
  for (const value of values) result.set(value, (result.get(value) ?? 0) + 1)
  return result
}

const cellType = (cell: DiagramCell) => `${cell.dimension}:${cell.kind}`

function incidenceType(cell: DiagramCell, byId: Map<string, DiagramCell>) {
  const boundary = cell.boundary
    .map(term => {
      const target = byId.get(term.cellId)
      return `${term.coefficient}:${target ? cellType(target) : 'missing'}`
    })
    .sort()
    .join('|')
  return `${cellType(cell)}->[${boundary}]`
}

function topologyHistogram(complex: TypedCellComplex) {
  const verification = verifyCellComplex(complex)
  return histogram(
    Object.entries(verification.bettiNumbers).map(([dimension, value]) =>
      `b${dimension}:${value}`),
  )
}

/**
 * Compare mathematical diagram semantics without depending on cell IDs,
 * coordinates, stroke widths, colors, or a particular renderer.
 */
export function evaluateDiagramSemantics(
  reference: TypedCellComplex,
  candidate: TypedCellComplex,
): SemanticDiagramScore {
  const referenceById = new Map(reference.cells.map(cell => [cell.id, cell]))
  const candidateById = new Map(candidate.cells.map(cell => [cell.id, cell]))
  const referenceVerification = verifyCellComplex(reference)
  const candidateVerification = verifyCellComplex(candidate)
  const cellTypeF1 = f1(
    histogram(reference.cells.map(cellType)),
    histogram(candidate.cells.map(cellType)),
  )
  const incidenceF1 = f1(
    histogram(reference.cells.map(cell => incidenceType(cell, referenceById))),
    histogram(candidate.cells.map(cell => incidenceType(cell, candidateById))),
  )
  const labelF1 = f1(
    histogram(reference.cells.flatMap(cell => cell.label ? [cell.label] : [])),
    histogram(candidate.cells.flatMap(cell => cell.label ? [cell.label] : [])),
  )
  const topologyF1 = f1(topologyHistogram(reference), topologyHistogram(candidate))
  const eulerMatch = referenceVerification.eulerCharacteristic
    === candidateVerification.eulerCharacteristic
  const strictPass = candidateVerification.passed
    && cellTypeF1 === 1
    && incidenceF1 === 1
    && labelF1 === 1
    && topologyF1 === 1
    && eulerMatch
  return {
    valid: candidateVerification.passed,
    strictPass,
    cellTypeF1,
    incidenceF1,
    labelF1,
    topologyF1,
    eulerMatch,
    boundarySquaredResiduals: candidateVerification.boundarySquaredResiduals,
  }
}
