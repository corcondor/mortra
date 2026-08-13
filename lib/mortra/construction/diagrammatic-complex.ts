/**
 * Sparse typed cellular complexes for diagrams whose semantics are not
 * reducible to Euclidean circles and straight lines.
 *
 * Geometry is deliberately separate from incidence. A diagram can therefore
 * be checked combinatorially before any 2D/3D embedding is chosen.
 */

export type CellDimension = 0 | 1 | 2 | 3

export type BoundaryTerm = {
  cellId: string
  coefficient: -1 | 1
}

export type DiagramCell = {
  id: string
  dimension: CellDimension
  kind: string
  boundary: BoundaryTerm[]
  label?: string
}

export type AmbientSpace =
  | { kind: 'abstract' }
  | { kind: 'euclidean'; dimension: 2 | 3 }
  | { kind: 'configuration'; degreesOfFreedom: number }

export type TypedCellComplex = {
  id: string
  ambient: AmbientSpace
  cells: DiagramCell[]
}

export type ComplexVerification = {
  passed: boolean
  errors: string[]
  counts: Record<CellDimension, number>
  eulerCharacteristic: number
  boundarySquaredResiduals: number
}

const dimensions: CellDimension[] = [0, 1, 2, 3]

export function verifyCellComplex(complex: TypedCellComplex): ComplexVerification {
  const errors: string[] = []
  const byId = new Map<string, DiagramCell>()
  const counts: Record<CellDimension, number> = { 0: 0, 1: 0, 2: 0, 3: 0 }

  for (const cell of complex.cells) {
    if (byId.has(cell.id)) errors.push(`duplicate cell id: ${cell.id}`)
    byId.set(cell.id, cell)
    counts[cell.dimension] += 1
    if (cell.dimension === 0 && cell.boundary.length > 0) {
      errors.push(`0-cell ${cell.id} must have empty boundary`)
    }
  }

  for (const cell of complex.cells) {
    for (const term of cell.boundary) {
      const boundaryCell = byId.get(term.cellId)
      if (!boundaryCell) {
        errors.push(`${cell.id} references missing boundary cell ${term.cellId}`)
        continue
      }
      if (boundaryCell.dimension !== cell.dimension - 1) {
        errors.push(
          `${cell.id} has ${boundaryCell.dimension}-cell ${term.cellId} in its boundary`,
        )
      }
    }
  }

  let boundarySquaredResiduals = 0
  for (const cell of complex.cells) {
    if (cell.dimension < 2) continue
    const coefficients = new Map<string, number>()
    for (const outer of cell.boundary) {
      const boundaryCell = byId.get(outer.cellId)
      if (!boundaryCell || boundaryCell.dimension !== cell.dimension - 1) continue
      for (const inner of boundaryCell.boundary) {
        coefficients.set(
          inner.cellId,
          (coefficients.get(inner.cellId) ?? 0) + outer.coefficient * inner.coefficient,
        )
      }
    }
    for (const [lowerCellId, coefficient] of coefficients) {
      if (coefficient === 0) continue
      boundarySquaredResiduals += 1
      errors.push(`boundary^2(${cell.id}) contains ${coefficient} * ${lowerCellId}`)
    }
  }

  const eulerCharacteristic = dimensions.reduce<number>(
    (sum, dimension) => sum + (dimension % 2 === 0 ? 1 : -1) * counts[dimension],
    0,
  )
  return {
    passed: errors.length === 0,
    errors,
    counts,
    eulerCharacteristic,
    boundarySquaredResiduals,
  }
}

export function buildDynkinA(rank: number): TypedCellComplex {
  const safeRank = Math.max(1, Math.floor(rank))
  const vertices: DiagramCell[] = Array.from({ length: safeRank }, (_, index) => ({
    id: `alpha_${index + 1}`,
    dimension: 0,
    kind: 'simple-root',
    label: `alpha_${index + 1}`,
    boundary: [],
  }))
  const bonds: DiagramCell[] = Array.from({ length: Math.max(0, safeRank - 1) }, (_, index) => ({
    id: `bond_${index + 1}_${index + 2}`,
    dimension: 1,
    kind: 'dynkin-bond',
    boundary: [
      { cellId: `alpha_${index + 1}`, coefficient: -1 },
      { cellId: `alpha_${index + 2}`, coefficient: 1 },
    ],
  }))
  return {
    id: `dynkin-A${safeRank}`,
    ambient: { kind: 'abstract' },
    cells: [...vertices, ...bonds],
  }
}

/** Build an oriented rectangular cellulation of a torus by periodic gluing. */
export function buildTorusCellulation(columns: number, rows: number): TypedCellComplex {
  const width = Math.max(2, Math.floor(columns))
  const height = Math.max(2, Math.floor(rows))
  const cells: DiagramCell[] = []
  const vertex = (x: number, y: number) => `v_${(x + width) % width}_${(y + height) % height}`
  const horizontal = (x: number, y: number) => `h_${(x + width) % width}_${(y + height) % height}`
  const vertical = (x: number, y: number) => `e_${(x + width) % width}_${(y + height) % height}`

  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      cells.push({ id: vertex(x, y), dimension: 0, kind: 'vertex', boundary: [] })
      cells.push({
        id: horizontal(x, y),
        dimension: 1,
        kind: 'periodic-edge-u',
        boundary: [
          { cellId: vertex(x, y), coefficient: -1 },
          { cellId: vertex(x + 1, y), coefficient: 1 },
        ],
      })
      cells.push({
        id: vertical(x, y),
        dimension: 1,
        kind: 'periodic-edge-v',
        boundary: [
          { cellId: vertex(x, y), coefficient: -1 },
          { cellId: vertex(x, y + 1), coefficient: 1 },
        ],
      })
      cells.push({
        id: `face_${x}_${y}`,
        dimension: 2,
        kind: 'oriented-face',
        boundary: [
          { cellId: horizontal(x, y), coefficient: 1 },
          { cellId: vertical(x + 1, y), coefficient: 1 },
          { cellId: horizontal(x, y + 1), coefficient: -1 },
          { cellId: vertical(x, y), coefficient: -1 },
        ],
      })
    }
  }

  return {
    id: `torus-cellulation-${width}x${height}`,
    ambient: { kind: 'euclidean', dimension: 3 },
    cells,
  }
}
