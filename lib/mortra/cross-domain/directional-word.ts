import {
  addCertificate,
  addMorphism,
  addObject,
  addRelation,
  auditKernel,
  createKernel,
  sid,
  type SemanticId,
  type SemanticKernel,
} from '../kernel/semantic-kernel'

export type Direction = 'N' | 'E' | 'S' | 'W'
export type GridPoint = { x: number; y: number }
export type Matrix3 = [[number, number, number], [number, number, number], [number, number, number]]

export type OrderedGridEdge = {
  index: number
  direction: Direction
  from: GridPoint
  to: GridPoint
  supportKey: string
}

export type DirectionalWordGeometry = {
  vertices: GridPoint[]
  edges: OrderedGridEdge[]
  endpoint: GridPoint
  boundingBox: { minX: number; maxX: number; minY: number; maxY: number }
}

export type DirectionalWordStabilizer = {
  orderedSupport: string[]
  support: string[]
  parityRow: number[]
  weight: number
  repeatedEdges: string[]
  codeAdmissibility: {
    simpleEdgeSupport: boolean
    mutualPrimalDualCommutation: 'not_checked'
    displacementParityCondition: 'not_checked'
  }
}

export type DirectionalScheduleLayer = {
  index: number
  direction: Direction
  from: GridPoint
  to: GridPoint
  operation: 'CXSWAP_OR_SWAP'
}

export type DirectionalWordSchedule = {
  layers: DirectionalScheduleLayer[]
  interactionDepth: number
  roundDepthWithPreparationAndMeasurement: number
  inverseWord: Direction[]
  forwardInverseRestoresOrigin: boolean
}

export type EndpointNormalFormCertificate = {
  quotient: 'translation-action-only'
  originalWord: Direction[]
  normalWord: Direction[]
  originalMatrix: Matrix3
  normalMatrix: Matrix3
  endpoint: GridPoint
  preserved: ['endpoint', 'translation-action']
  notPreserved: ['ordered-support', 'stabilizer-support', 'measurement-schedule']
}

export type DirectionalWordCompilation = {
  id: string
  steps: Direction[]
  geometry: DirectionalWordGeometry
  stabilizer: DirectionalWordStabilizer
  schedule: DirectionalWordSchedule
  translationMatrix: Matrix3
  endpointNormalForm: EndpointNormalFormCertificate
  kernel: SemanticKernel
  semanticIds: {
    word: SemanticId
    geometry: SemanticId
    stabilizer: SemanticId
    schedule: SemanticId
    matrix: SemanticId
  }
}

const VECTOR: Record<Direction, GridPoint> = {
  N: { x: 0, y: 1 },
  E: { x: 1, y: 0 },
  S: { x: 0, y: -1 },
  W: { x: -1, y: 0 },
}

const OPPOSITE: Record<Direction, Direction> = { N: 'S', E: 'W', S: 'N', W: 'E' }

const IDENTITY: Matrix3 = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]

function clonePoint(point: GridPoint): GridPoint {
  return { x: point.x, y: point.y }
}

function addPoint(left: GridPoint, right: GridPoint): GridPoint {
  return { x: left.x + right.x, y: left.y + right.y }
}

function pointKey(point: GridPoint): string {
  return `${point.x},${point.y}`
}

function edgeKey(left: GridPoint, right: GridPoint): string {
  const first = pointKey(left)
  const second = pointKey(right)
  return first < second ? `${first}|${second}` : `${second}|${first}`
}

function multiply(left: Matrix3, right: Matrix3): Matrix3 {
  const output = Array.from({ length: 3 }, () => Array<number>(3).fill(0))
  for (let row = 0; row < 3; row += 1) {
    for (let column = 0; column < 3; column += 1) {
      for (let inner = 0; inner < 3; inner += 1) {
        output[row][column] += left[row][inner] * right[inner][column]
      }
    }
  }
  return output as Matrix3
}

function directionMatrix(direction: Direction): Matrix3 {
  const delta = VECTOR[direction]
  return [[1, 0, delta.x], [0, 1, delta.y], [0, 0, 1]]
}

export function composeDirectionMatrices(steps: Direction[]): Matrix3 {
  let result: Matrix3 = IDENTITY
  for (const step of steps) result = multiply(directionMatrix(step), result)
  return result
}

function matricesEqual(left: Matrix3, right: Matrix3): boolean {
  return left.every((row, rowIndex) => row.every((value, column) => value === right[rowIndex][column]))
}

function endpointNormalWord(endpoint: GridPoint): Direction[] {
  const result: Direction[] = []
  result.push(...Array<Direction>(Math.abs(endpoint.x)).fill(endpoint.x >= 0 ? 'E' : 'W'))
  result.push(...Array<Direction>(Math.abs(endpoint.y)).fill(endpoint.y >= 0 ? 'N' : 'S'))
  return result
}

export function parseDirectionalWord(input: string): { steps?: Direction[]; errors: string[] } {
  let source = input
    .toUpperCase()
    .replace(/\\TEXTTT\{([NESW])\}/g, '$1')
    .replace(/\\MATHFRAK\s*\{?D\}?\s*=/g, '')
    .replace(/[\s,$·]/g, '')
    .replace(/\\CDOT/g, '')
  if (!source) return { errors: ['directional word is empty'] }

  const steps: Direction[] = []
  let cursor = 0
  while (cursor < source.length) {
    const direction = source[cursor] as Direction
    if (!Object.hasOwn(VECTOR, direction)) {
      return { errors: [`invalid directional token at offset ${cursor}: ${source[cursor]}`] }
    }
    cursor += 1
    let count = 1
    if (source[cursor] === '^') {
      cursor += 1
      let digits = ''
      if (source[cursor] === '{') {
        cursor += 1
        while (cursor < source.length && source[cursor] !== '}') digits += source[cursor++]
        if (source[cursor] !== '}') return { errors: ['unterminated exponent'] }
        cursor += 1
      } else {
        while (cursor < source.length && /[0-9]/.test(source[cursor])) digits += source[cursor++]
      }
      if (!digits || !/^[0-9]+$/.test(digits)) return { errors: ['direction exponent must be an integer'] }
      count = Number(digits)
      if (!Number.isSafeInteger(count) || count < 1 || count > 10_000) {
        return { errors: ['direction exponent must be in [1, 10000]'] }
      }
    }
    if (steps.length + count > 100_000) return { errors: ['directional word exceeds 100000 steps'] }
    steps.push(...Array<Direction>(count).fill(direction))
  }
  return { steps, errors: [] }
}

function deriveGeometry(steps: Direction[]): DirectionalWordGeometry {
  const vertices: GridPoint[] = [{ x: 0, y: 0 }]
  const edges: OrderedGridEdge[] = []
  let current = vertices[0]
  for (let index = 0; index < steps.length; index += 1) {
    const direction = steps[index]
    const next = addPoint(current, VECTOR[direction])
    edges.push({
      index,
      direction,
      from: clonePoint(current),
      to: clonePoint(next),
      supportKey: edgeKey(current, next),
    })
    vertices.push(clonePoint(next))
    current = next
  }
  const xs = vertices.map(vertex => vertex.x)
  const ys = vertices.map(vertex => vertex.y)
  return {
    vertices,
    edges,
    endpoint: clonePoint(current),
    boundingBox: {
      minX: Math.min(...xs),
      maxX: Math.max(...xs),
      minY: Math.min(...ys),
      maxY: Math.max(...ys),
    },
  }
}

function deriveStabilizer(geometry: DirectionalWordGeometry): DirectionalWordStabilizer {
  const counts = new Map<string, number>()
  for (const edge of geometry.edges) counts.set(edge.supportKey, (counts.get(edge.supportKey) ?? 0) + 1)
  const support = [...counts.keys()].sort()
  return {
    orderedSupport: geometry.edges.map(edge => edge.supportKey),
    support,
    parityRow: support.map(() => 1),
    weight: support.length,
    repeatedEdges: [...counts.entries()].filter(([, count]) => count > 1).map(([key]) => key).sort(),
    codeAdmissibility: {
      simpleEdgeSupport: [...counts.values()].every(count => count === 1),
      mutualPrimalDualCommutation: 'not_checked',
      displacementParityCondition: 'not_checked',
    },
  }
}

function deriveSchedule(steps: Direction[], geometry: DirectionalWordGeometry): DirectionalWordSchedule {
  const inverseWord = [...steps].reverse().map(step => OPPOSITE[step])
  const roundTrip = [...steps, ...inverseWord]
  const roundTripMatrix = composeDirectionMatrices(roundTrip)
  return {
    layers: geometry.edges.map(edge => ({
      index: edge.index,
      direction: edge.direction,
      from: clonePoint(edge.from),
      to: clonePoint(edge.to),
      operation: 'CXSWAP_OR_SWAP',
    })),
    interactionDepth: steps.length,
    roundDepthWithPreparationAndMeasurement: steps.length + 2,
    inverseWord,
    forwardInverseRestoresOrigin: matricesEqual(roundTripMatrix, IDENTITY),
  }
}

function buildSemanticKernel(
  id: string,
  steps: Direction[],
  geometry: DirectionalWordGeometry,
  stabilizer: DirectionalWordStabilizer,
  schedule: DirectionalWordSchedule,
  matrix: Matrix3,
): { kernel: SemanticKernel; ids: DirectionalWordCompilation['semanticIds'] } {
  const kernel = createKernel()
  const ids = {
    word: sid(`${id}:directional-word`),
    geometry: sid(`${id}:geometric-path`),
    stabilizer: sid(`${id}:stabilizer-support`),
    schedule: sid(`${id}:measurement-schedule`),
    matrix: sid(`${id}:translation-matrix`),
  }
  addObject(kernel, {
    id: ids.word,
    sort: 'Sequence',
    label: steps.join(''),
    definition: 'ordered word in the four square-lattice translation generators',
    assumptions: [],
    conventions: [{ kind: 'orientation', value: 'N=(0,1),E=(1,0),S=(0,-1),W=(-1,0)' }],
    provenance: { source: 'directional-word input', path: [], consumed: [] },
    payload: { steps },
  })

  const targets = [
    { id: ids.geometry, sort: 'VisualElement' as const, label: 'square-lattice path', payload: geometry },
    { id: ids.stabilizer, sort: 'Stabilizer' as const, label: 'candidate ordered local support', payload: stabilizer },
    { id: ids.schedule, sort: 'Sequence' as const, label: 'nearest-neighbour layer schedule', payload: schedule },
    { id: ids.matrix, sort: 'Matrix' as const, label: 'homogeneous translation action', payload: matrix },
  ]
  for (const target of targets) {
    addObject(kernel, {
      ...target,
      definition: target.id === ids.stabilizer
        ? 'a candidate support derived from the same word; CSS code admissibility is not certified here'
        : 'a certified representation of the same directional word',
      assumptions: [ids.word],
      conventions: [{ kind: 'orientation', value: 'N=(0,1),E=(1,0),S=(0,-1),W=(-1,0)' }],
      provenance: { source: 'DirectionalWord multi-view compiler', path: [], consumed: [ids.word] },
    })
  }

  const definitions = [
    {
      target: ids.geometry,
      name: 'DirectionalWordToGeometricPath',
      sort: 'VisualElement' as const,
      preserved: ['step order', 'adjacency', 'endpoint'],
      detail: `${steps.length} nearest-neighbour edges replayed`,
    },
    {
      target: ids.stabilizer,
      name: 'DirectionalWordToStabilizerSupport',
      sort: 'Stabilizer' as const,
      preserved: ['ordered edge support', 'set support', 'support weight', 'explicit code-admissibility boundary'],
      detail: `${stabilizer.weight} distinct support edges`,
    },
    {
      target: ids.schedule,
      name: 'DirectionalWordToMeasurementSchedule',
      sort: 'Sequence' as const,
      preserved: ['step order', 'nearest-neighbour locality', 'forward/inverse restoration'],
      detail: `${schedule.interactionDepth} directional layers plus preparation and measurement`,
    },
    {
      target: ids.matrix,
      name: 'DirectionalWordToTranslationMatrix',
      sort: 'Matrix' as const,
      preserved: ['endpoint', 'composition order', 'affine action'],
      detail: `translation (${geometry.endpoint.x},${geometry.endpoint.y})`,
    },
  ]

  for (const definition of definitions) {
    const certificate = sid(`${id}:certificate:${definition.name}`)
    const morphism = sid(`${id}:morphism:${definition.name}`)
    addCertificate(kernel, {
      id: certificate,
      method: 'exact_substitution',
      consumedPremises: [ids.word],
      detail: definition.detail,
      artifact: 'lib/mortra/cross-domain/directional-word.ts',
    })
    addMorphism(kernel, {
      id: morphism,
      name: definition.name,
      source: [ids.word],
      target: [definition.target],
      sourceSorts: ['Sequence'],
      targetSorts: [definition.sort],
      preconditions: ['all symbols are N, E, S, or W'],
      transported: [ids.word],
      preserved: definition.preserved,
      proofObligations: [],
      certificate,
    })
    kernel.objects.get(definition.target)!.provenance.path = [morphism]
  }
  const coherence = sid(`${id}:certificate:multi-view-coherence`)
  addCertificate(kernel, {
    id: coherence,
    method: 'symbolic_identity',
    consumedPremises: [ids.word, ids.geometry, ids.stabilizer, ids.schedule, ids.matrix],
    detail: 'all four views replay the same ordered generator word',
    artifact: 'tests/directional-word-cross-domain.test.ts',
  })
  addRelation(kernel, {
    id: sid(`${id}:relation:one-structure-many-representations`),
    predicate: 'represent_same_directional_word',
    arguments: [ids.word, ids.geometry, ids.stabilizer, ids.schedule, ids.matrix],
    status: 'proved',
    certificate: coherence,
    provenance: {
      source: 'multi-view coherence replay',
      path: [],
      consumed: [ids.word, ids.geometry, ids.stabilizer, ids.schedule, ids.matrix],
    },
  })
  return { kernel, ids }
}

export function compileDirectionalWord(
  id: string,
  input: string | Direction[],
): { compilation?: DirectionalWordCompilation; errors: string[] } {
  if (!id.trim()) return { errors: ['id is required'] }
  const parsed = typeof input === 'string' ? parseDirectionalWord(input) : { steps: [...input], errors: [] }
  if (!parsed.steps || parsed.errors.length) return { errors: parsed.errors }
  if (!parsed.steps.length) return { errors: ['directional word is empty'] }
  if (parsed.steps.some(step => !Object.hasOwn(VECTOR, step))) return { errors: ['directional word contains an invalid generator'] }

  const steps = parsed.steps
  const geometry = deriveGeometry(steps)
  const stabilizer = deriveStabilizer(geometry)
  const schedule = deriveSchedule(steps, geometry)
  const translationMatrix = composeDirectionMatrices(steps)
  const normalWord = endpointNormalWord(geometry.endpoint)
  const endpointNormalForm: EndpointNormalFormCertificate = {
    quotient: 'translation-action-only',
    originalWord: [...steps],
    normalWord,
    originalMatrix: translationMatrix,
    normalMatrix: composeDirectionMatrices(normalWord),
    endpoint: clonePoint(geometry.endpoint),
    preserved: ['endpoint', 'translation-action'],
    notPreserved: ['ordered-support', 'stabilizer-support', 'measurement-schedule'],
  }
  const semantic = buildSemanticKernel(id, steps, geometry, stabilizer, schedule, translationMatrix)
  return {
    compilation: {
      id,
      steps,
      geometry,
      stabilizer,
      schedule,
      translationMatrix,
      endpointNormalForm,
      kernel: semantic.kernel,
      semanticIds: semantic.ids,
    },
    errors: [],
  }
}

export function verifyEndpointNormalFormCertificate(
  certificate: EndpointNormalFormCertificate,
  input: Direction[] = certificate.originalWord,
): string[] {
  const errors: string[] = []
  const originalMatrix = composeDirectionMatrices(input)
  const normalMatrix = composeDirectionMatrices(certificate.normalWord)
  if (input.join('') !== certificate.originalWord.join('')) errors.push('certificate was replayed against a different word')
  if (!matricesEqual(originalMatrix, certificate.originalMatrix)) errors.push('original matrix is stale')
  if (!matricesEqual(normalMatrix, certificate.normalMatrix)) errors.push('normal matrix is stale')
  if (!matricesEqual(originalMatrix, normalMatrix)) errors.push('normal form changed the translation action')
  if (normalMatrix[0][2] !== certificate.endpoint.x || normalMatrix[1][2] !== certificate.endpoint.y) {
    errors.push('normal form endpoint mismatch')
  }
  if (certificate.quotient !== 'translation-action-only') errors.push('unsupported normal-form quotient')
  if (certificate.normalWord.join('') !== endpointNormalWord(certificate.endpoint).join('')) {
    errors.push('normal word is not the canonical shortest translation representative')
  }
  if (certificate.preserved.join('|') !== ['endpoint', 'translation-action'].join('|')) {
    errors.push('certificate preserved-invariant declaration is incomplete')
  }
  if (certificate.notPreserved.join('|') !== [
    'ordered-support',
    'stabilizer-support',
    'measurement-schedule',
  ].join('|')) {
    errors.push('certificate hides a lost invariant')
  }
  return errors
}

export function verifyDirectionalWordCompilation(compilation: DirectionalWordCompilation): string[] {
  const errors: string[] = []
  const geometry = deriveGeometry(compilation.steps)
  const stabilizer = deriveStabilizer(geometry)
  const schedule = deriveSchedule(compilation.steps, geometry)
  const matrix = composeDirectionMatrices(compilation.steps)
  if (JSON.stringify(geometry) !== JSON.stringify(compilation.geometry)) errors.push('geometric path replay mismatch')
  if (JSON.stringify(stabilizer) !== JSON.stringify(compilation.stabilizer)) errors.push('stabilizer support replay mismatch')
  if (JSON.stringify(schedule) !== JSON.stringify(compilation.schedule)) errors.push('schedule replay mismatch')
  if (!matricesEqual(matrix, compilation.translationMatrix)) errors.push('translation matrix replay mismatch')
  errors.push(...verifyEndpointNormalFormCertificate(compilation.endpointNormalForm, compilation.steps))
  errors.push(...auditKernel(compilation.kernel).map(violation => `${violation.kind}: ${violation.detail}`))
  return [...new Set(errors)]
}

export function endpointNormalFormLosesSupport(compilation: DirectionalWordCompilation): boolean {
  const normalGeometry = deriveGeometry(compilation.endpointNormalForm.normalWord)
  const normalSupport = deriveStabilizer(normalGeometry)
  return normalSupport.orderedSupport.join('|') !== compilation.stabilizer.orderedSupport.join('|')
}
