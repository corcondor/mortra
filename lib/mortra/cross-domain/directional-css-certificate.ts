import type { DirectionalWordGeometry, OrderedGridEdge } from './directional-word'

export type TileEdgeOrientation = 'horizontal' | 'vertical'

export type DirectionalTileEdge = {
  orientation: TileEdgeOrientation
  x: number
  y: number
  sourceIndices: number[]
}

export type OddVerticalDisplacementWitness = {
  dx2: number
  dy2: number
  multiplicity: number
  orderedPairs: Array<[number, number]>
}

export type CssCommutationWitness = {
  relativeTranslation: { x: number; y: number }
  overlap: number
  xEdges: string[]
  zEdges: string[]
}

export type DirectionalCssCertificate = {
  theorem: 'directional-tiles-mutual-and-displacement-parity'
  coordinateConvention: {
    tileEdge: 'lower-left endpoint of the unoriented unit edge'
    displacement: 'twice the physical edge-centre coordinate'
    relativeTranslation: 'X anchor minus Z anchor'
  }
  gridSize: number
  xTile: DirectionalTileEdge[]
  zTile: DirectionalTileEdge[]
  mutualCondition: {
    valid: boolean
    checkedEdges: number
    violations: string[]
  }
  staticCssCommutation: {
    valid: boolean
    proofDomain: 'all relative translations with nonzero overlap'
    checkedRelativeTranslations: number
    nonzeroRelativeTranslations: number
    maximumOverlap: number
    witnesses: CssCommutationWitness[]
    oddOverlapViolations: CssCommutationWitness[]
  }
  displacementParity: {
    valid: boolean
    checkedOrderedPairs: number
    oddVerticalVectors: OddVerticalDisplacementWitness[]
    oddMultiplicityViolations: OddVerticalDisplacementWitness[]
  }
}

function orientation(edge: OrderedGridEdge): TileEdgeOrientation {
  return edge.from.y === edge.to.y ? 'horizontal' : 'vertical'
}

function rawTileEdge(edge: OrderedGridEdge): DirectionalTileEdge {
  return {
    orientation: orientation(edge),
    x: Math.min(edge.from.x, edge.to.x),
    y: Math.min(edge.from.y, edge.to.y),
    sourceIndices: [edge.index],
  }
}

function tileEdgeKey(edge: Pick<DirectionalTileEdge, 'orientation' | 'x' | 'y'>): string {
  return `${edge.orientation}:${edge.x},${edge.y}`
}

function normalizeTile(edges: OrderedGridEdge[]): DirectionalTileEdge[] {
  const raw = edges.map(rawTileEdge)
  const minX = Math.min(...raw.map(edge => edge.x))
  const minY = Math.min(...raw.map(edge => edge.y))
  const unique = new Map<string, DirectionalTileEdge>()
  for (const edge of raw) {
    const normalized = { ...edge, x: edge.x - minX, y: edge.y - minY }
    const key = tileEdgeKey(normalized)
    const existing = unique.get(key)
    if (existing) existing.sourceIndices.push(...normalized.sourceIndices)
    else unique.set(key, normalized)
  }
  return [...unique.values()].sort((left, right) => tileEdgeKey(left).localeCompare(tileEdgeKey(right)))
}

function dualEdge(edge: DirectionalTileEdge, gridSize: number): DirectionalTileEdge {
  return {
    orientation: edge.orientation === 'horizontal' ? 'vertical' : 'horizontal',
    x: gridSize - 1 - edge.x,
    y: gridSize - 1 - edge.y,
    sourceIndices: [...edge.sourceIndices],
  }
}

function doubledEdgeCentre(edge: DirectionalTileEdge): { x: number; y: number } {
  return edge.orientation === 'horizontal'
    ? { x: 2 * edge.x + 1, y: 2 * edge.y }
    : { x: 2 * edge.x, y: 2 * edge.y + 1 }
}

function orderedNormalizedEdges(edges: OrderedGridEdge[]): DirectionalTileEdge[] {
  const raw = edges.map(rawTileEdge)
  const minX = Math.min(...raw.map(edge => edge.x))
  const minY = Math.min(...raw.map(edge => edge.y))
  return raw.map(edge => ({ ...edge, x: edge.x - minX, y: edge.y - minY }))
}

function deriveDisplacementParity(geometry: DirectionalWordGeometry): DirectionalCssCertificate['displacementParity'] {
  const orderedEdges = orderedNormalizedEdges(geometry.edges)
  const counts = new Map<string, OddVerticalDisplacementWitness>()
  let checkedOrderedPairs = 0
  for (let earlier = 0; earlier < orderedEdges.length; earlier += 1) {
    const from = doubledEdgeCentre(orderedEdges[earlier])
    for (let later = earlier + 1; later < orderedEdges.length; later += 1) {
      checkedOrderedPairs += 1
      const to = doubledEdgeCentre(orderedEdges[later])
      const dx2 = to.x - from.x
      const dy2 = to.y - from.y
      if (Math.abs(dy2) % 2 !== 1) continue
      const key = `${dx2},${dy2}`
      const witness = counts.get(key) ?? { dx2, dy2, multiplicity: 0, orderedPairs: [] }
      witness.multiplicity += 1
      witness.orderedPairs.push([earlier, later])
      counts.set(key, witness)
    }
  }
  const oddVerticalVectors = [...counts.values()].sort((left, right) =>
    left.dx2 - right.dx2 || left.dy2 - right.dy2)
  const oddMultiplicityViolations = oddVerticalVectors.filter(witness => witness.multiplicity % 2 === 1)
  return {
    valid: oddMultiplicityViolations.length === 0,
    checkedOrderedPairs,
    oddVerticalVectors,
    oddMultiplicityViolations,
  }
}

function deriveStaticCommutation(
  xTile: DirectionalTileEdge[],
  zTile: DirectionalTileEdge[],
): DirectionalCssCertificate['staticCssCommutation'] {
  const correlations = new Map<string, CssCommutationWitness>()
  for (const xEdge of xTile) {
    for (const zEdge of zTile) {
      if (xEdge.orientation !== zEdge.orientation) continue
      const dx = xEdge.x - zEdge.x
      const dy = xEdge.y - zEdge.y
      const key = `${dx},${dy}`
      const witness = correlations.get(key) ?? {
        relativeTranslation: { x: dx, y: dy },
        overlap: 0,
        xEdges: [],
        zEdges: [],
      }
      witness.overlap += 1
      witness.xEdges.push(tileEdgeKey(xEdge))
      witness.zEdges.push(tileEdgeKey(zEdge))
      correlations.set(key, witness)
    }
  }
  const witnesses = [...correlations.values()].sort((left, right) =>
    left.relativeTranslation.x - right.relativeTranslation.x
      || left.relativeTranslation.y - right.relativeTranslation.y)
  const oddOverlapViolations = witnesses.filter(witness => witness.overlap % 2 === 1)
  return {
    valid: oddOverlapViolations.length === 0,
    proofDomain: 'all relative translations with nonzero overlap',
    checkedRelativeTranslations: witnesses.length,
    nonzeroRelativeTranslations: witnesses.length,
    maximumOverlap: Math.max(0, ...witnesses.map(witness => witness.overlap)),
    witnesses,
    oddOverlapViolations,
  }
}

export function deriveDirectionalCssCertificate(geometry: DirectionalWordGeometry): DirectionalCssCertificate {
  const xTile = normalizeTile(geometry.edges)
  const gridSize = Math.max(...xTile.flatMap(edge => [edge.x, edge.y])) + 2
  const zTile = xTile.map(edge => dualEdge(edge, gridSize))
    .sort((left, right) => tileEdgeKey(left).localeCompare(tileEdgeKey(right)))
  const zKeys = new Set(zTile.map(tileEdgeKey))
  const mutualViolations = xTile.flatMap(edge => {
    const expected = dualEdge(edge, gridSize)
    return zKeys.has(tileEdgeKey(expected)) ? [] : [`missing ${tileEdgeKey(expected)} for ${tileEdgeKey(edge)}`]
  })
  return {
    theorem: 'directional-tiles-mutual-and-displacement-parity',
    coordinateConvention: {
      tileEdge: 'lower-left endpoint of the unoriented unit edge',
      displacement: 'twice the physical edge-centre coordinate',
      relativeTranslation: 'X anchor minus Z anchor',
    },
    gridSize,
    xTile,
    zTile,
    mutualCondition: {
      valid: mutualViolations.length === 0,
      checkedEdges: xTile.length,
      violations: mutualViolations,
    },
    staticCssCommutation: deriveStaticCommutation(xTile, zTile),
    displacementParity: deriveDisplacementParity(geometry),
  }
}

export function verifyDirectionalCssCertificate(
  geometry: DirectionalWordGeometry,
  certificate: DirectionalCssCertificate,
): string[] {
  const replayed = deriveDirectionalCssCertificate(geometry)
  const errors: string[] = []
  if (JSON.stringify(replayed) !== JSON.stringify(certificate)) errors.push('directional CSS certificate replay mismatch')
  return errors
}

export function directionalCssConditionFailures(certificate: DirectionalCssCertificate): string[] {
  const errors: string[] = []
  if (!certificate.mutualCondition.valid) errors.push('directional-tile mutual condition failed')
  if (!certificate.staticCssCommutation.valid) errors.push('translated CSS stabilizer supports have an odd overlap')
  if (!certificate.displacementParity.valid) errors.push('odd-vertical displacement vector has odd multiplicity')
  return errors
}
