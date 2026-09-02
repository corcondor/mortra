import { createHash } from 'node:crypto'

export const PROBLEM_TASK_PRIMITIVES = [
  'transport',
  'pair',
  'map',
  'fold',
  'equalizer',
  'preimage',
  'period',
  'extremum',
  'boundary',
  'eliminate',
  'normalize',
  'contract',
] as const

export type ProblemTaskPrimitive = typeof PROBLEM_TASK_PRIMITIVES[number]

export type ProblemTaskValueSort =
  | 'typed-object'
  | 'finite-orbit'
  | 'indexed-orbit'
  | 'algebraic-configuration'
  | 'random-vector'
  | 'lattice-region'
  | 'sequence'
  | 'configuration'
  | 'index-set'
  | 'period-data'
  | 'histogram'
  | 'scalar'
  | 'equation'
  | 'polynomial'

export type ProblemTaskOperation = {
  operator: ProblemTaskPrimitive
  output: ProblemTaskValueSort
}

export type ProblemTaskAlgebra = {
  schema: 1
  input: ProblemTaskValueSort
  operations: ProblemTaskOperation[]
  output: ProblemTaskValueSort
  complete: boolean
  /** Prevents unsafe merging when a task has not yet been elaborated. */
  opaqueSignature?: string
}

export type ProblemTaskAlgebraInput = {
  kernel?: string
  observable?: string
  querySignature?: string
}

const VALUE_SORTS = new Set<ProblemTaskValueSort>([
  'typed-object',
  'finite-orbit',
  'indexed-orbit',
  'algebraic-configuration',
  'random-vector',
  'lattice-region',
  'sequence',
  'configuration',
  'index-set',
  'period-data',
  'histogram',
  'scalar',
  'equation',
  'polynomial',
])

const PRIMITIVES = new Set<ProblemTaskPrimitive>(PROBLEM_TASK_PRIMITIVES)

function clean(value: unknown): string {
  return String(value ?? '')
    .normalize('NFKC')
    .trim()
    .replace(/\s+/g, ' ')
    .toLowerCase()
}

function compact(value: unknown): string {
  return clean(value).replace(/[^a-z0-9]+/g, '')
}

function digest(value: unknown): string {
  return createHash('sha256').update(JSON.stringify(value)).digest('hex')
}

function inputSort(kernel: unknown): ProblemTaskValueSort {
  const token = compact(kernel)
  if (/finitegeneratedaction|finitestate|finiteorbit/.test(token)) return 'finite-orbit'
  if (/generatedindex|indexed|recurrence/.test(token)) return 'indexed-orbit'
  if (/reversible|polynomial|root|mobius/.test(token)) return 'algebraic-configuration'
  if (/expectation|random|probability|quadratic/.test(token)) return 'random-vector'
  if (/lattice|pick|polygon/.test(token)) return 'lattice-region'
  return 'typed-object'
}

function makeProgram(
  input: ProblemTaskValueSort,
  operations: ProblemTaskOperation[],
): ProblemTaskAlgebra {
  return {
    schema: 1,
    input,
    operations,
    output: operations.at(-1)?.output ?? input,
    complete: true,
  }
}

/**
 * Validate a task program emitted by a generation engine. This keeps the
 * normalization layer independent of problem names and rejects malformed
 * programs instead of assigning them a misleading structural fingerprint.
 */
export function normalizeExplicitProblemTaskAlgebra(value: unknown): ProblemTaskAlgebra | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  const source = value as Partial<ProblemTaskAlgebra>
  if (source.schema !== 1 || !VALUE_SORTS.has(source.input as ProblemTaskValueSort)) return null
  if (!Array.isArray(source.operations) || !VALUE_SORTS.has(source.output as ProblemTaskValueSort)) return null
  const operations: ProblemTaskOperation[] = []
  for (const operation of source.operations) {
    if (!operation || typeof operation !== 'object' || Array.isArray(operation)) return null
    const candidate = operation as Partial<ProblemTaskOperation>
    if (!PRIMITIVES.has(candidate.operator as ProblemTaskPrimitive)) return null
    if (!VALUE_SORTS.has(candidate.output as ProblemTaskValueSort)) return null
    operations.push({
      operator: candidate.operator as ProblemTaskPrimitive,
      output: candidate.output as ProblemTaskValueSort,
    })
  }
  if (source.complete !== true || operations.length === 0) return null
  if (operations.at(-1)?.output !== source.output) return null
  return {
    schema: 1,
    input: source.input as ProblemTaskValueSort,
    operations,
    output: source.output as ProblemTaskValueSort,
    complete: true,
  }
}

/**
 * Elaborate named observables into a small typed algebra. The resulting
 * program records how a question is read from a mathematical structure, not
 * which function, constants, symbols, parent ids, or answer happened to occur.
 */
export function compileProblemTaskAlgebra(input: ProblemTaskAlgebraInput): ProblemTaskAlgebra {
  const source = inputSort(input.kernel)
  const observable = compact(input.observable)
  const query = compact(input.querySignature)
  const task = `${observable}${query}`

  if (/transportedrootfixedpoint|recoverfixedmap/.test(task)) {
    return makeProgram(source, [
      { operator: 'transport', output: 'configuration' },
      { operator: 'equalizer', output: 'equation' },
      { operator: 'eliminate', output: 'polynomial' },
      { operator: 'normalize', output: 'polynomial' },
    ])
  }

  if (/transportedrootpowersum|powersumsofthetransportedroot/.test(task)) {
    return makeProgram(source, [
      { operator: 'transport', output: 'configuration' },
      { operator: 'map', output: 'sequence' },
      { operator: 'fold', output: 'sequence' },
    ])
  }

  if (/rootmultiset.*polynomial|minimalsquarefreerootpolynomial|expandproductoverroot/.test(task)) {
    return makeProgram(source, [
      { operator: 'pair', output: 'configuration' },
      { operator: 'map', output: 'configuration' },
      { operator: 'eliminate', output: 'polynomial' },
      { operator: 'normalize', output: 'polynomial' },
    ])
  }

  if (/differencevector.*period/.test(task)) {
    return makeProgram(source, [
      { operator: 'pair', output: 'sequence' },
      { operator: 'map', output: 'sequence' },
      { operator: 'period', output: 'period-data' },
    ])
  }

  if (/crossdeterminant.*solutionset|zerodeterminant/.test(task)) {
    return makeProgram(source, [
      { operator: 'pair', output: 'sequence' },
      { operator: 'map', output: 'sequence' },
      { operator: 'preimage', output: 'index-set' },
    ])
  }

  if (/periodiccongruence.*solutionset|equalitystatesinproductorbit/.test(task)) {
    return makeProgram(source, [
      { operator: 'pair', output: 'sequence' },
      { operator: 'map', output: 'sequence' },
      { operator: 'preimage', output: 'index-set' },
    ])
  }

  if (/powersum/.test(task)) {
    const prefix: ProblemTaskOperation[] = [
      { operator: 'map', output: 'sequence' },
      { operator: 'fold', output: 'sequence' },
    ]
    if (/lastthreshold|finalstrictthreshold|minimalindexafter/.test(task)) {
      return makeProgram(source, [
        ...prefix,
        { operator: 'preimage', output: 'index-set' },
        { operator: 'boundary', output: 'scalar' },
      ])
    }
    if (/globalmax|globalmin|extrem/.test(task)) {
      return makeProgram(source, [
        ...prefix,
        { operator: 'extremum', output: 'scalar' },
        { operator: 'preimage', output: 'index-set' },
      ])
    }
    if (/inequality|above|below|threshold/.test(task)) {
      return makeProgram(source, [
        ...prefix,
        { operator: 'preimage', output: 'index-set' },
      ])
    }
    if (/equality|attaining|solutionset|classify/.test(task)) {
      return makeProgram(source, [
        ...prefix,
        { operator: 'preimage', output: 'index-set' },
      ])
    }
  }

  if (/signprofile|signperiod|signmultiplicit/.test(task)) {
    return makeProgram(source, [
      { operator: 'map', output: 'sequence' },
      { operator: 'period', output: 'period-data' },
      { operator: 'fold', output: 'histogram' },
    ])
  }

  if (/unitcirclepoint.*period|exactorbit/.test(task)) {
    return makeProgram(source, [
      { operator: 'map', output: 'sequence' },
      { operator: 'period', output: 'period-data' },
    ])
  }

  if (/minimal.*period|eventualperiod|exactcycle/.test(task)) {
    return makeProgram(source, [
      { operator: 'map', output: 'sequence' },
      { operator: 'period', output: 'period-data' },
    ])
  }

  if (/unitcirclepoint.*return|returntimetotheinitial/.test(task)) {
    return makeProgram(source, [
      { operator: 'map', output: 'sequence' },
      { operator: 'preimage', output: 'index-set' },
    ])
  }

  if (/zeroindex|vanish|zeroset/.test(task)) {
    return makeProgram(source, [
      { operator: 'map', output: 'sequence' },
      { operator: 'preimage', output: 'index-set' },
    ])
  }

  if (/expectation|expectedquadratic|moment/.test(task)) {
    return makeProgram(source, [
      { operator: 'contract', output: 'scalar' },
    ])
  }

  if (/lattice.*count|interiorcount|classifyandcount|floorsum/.test(task)) {
    return makeProgram(source, [
      { operator: 'preimage', output: 'lattice-region' },
      { operator: 'fold', output: 'scalar' },
    ])
  }

  if (/classify|solutionset|indexset/.test(task)) {
    return makeProgram(source, [
      { operator: 'map', output: 'sequence' },
      { operator: 'preimage', output: 'index-set' },
    ])
  }

  if (/verifiedanswer|verifiedgeneratedproblem|exactvalue|solve|equation/.test(task)) {
    return makeProgram(source, [
      { operator: 'eliminate', output: 'scalar' },
      { operator: 'normalize', output: 'scalar' },
    ])
  }

  return {
    schema: 1,
    input: source,
    operations: [],
    output: source,
    complete: false,
    opaqueSignature: digest({ observable: clean(input.observable), query: clean(input.querySignature) }),
  }
}

export function problemTaskPrimitiveSet(programs: readonly ProblemTaskAlgebra[]): ProblemTaskPrimitive[] {
  return PROBLEM_TASK_PRIMITIVES.filter(primitive =>
    programs.some(program => program.operations.some(operation => operation.operator === primitive)),
  )
}
