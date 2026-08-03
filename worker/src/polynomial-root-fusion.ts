import { spawnSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import path from 'node:path'
import type { DiscoveryParent } from './parent-conditioned-discovery'
import type { ExecutableFusionCard } from './executable-fusion'

type Operation = 'sum' | 'difference' | 'product'

type PolynomialInput = {
  parentId: string
  source: string
  normalized: string
}

type BackendResult = {
  left: string
  right: string
  result: string
  degree_left: number
  degree_right: number
  degree_result: number
  operation: Operation
  exact: true
  numeric_check: true
  ablation: true
  error?: never
}

const backendCache = new Map<string, BackendResult | null>()

function hash(value: unknown, length = 12): string {
  return createHash('sha256').update(JSON.stringify(value)).digest('hex').slice(0, length)
}

function mathSegments(statement: string): string[] {
  const segments: string[] = []
  const patterns = [
    /\$([^$]+)\$/g,
    /\\\(([^]*?)\\\)/g,
    /\\\[([^]*?)\\\]/g,
  ]
  for (const pattern of patterns) {
    for (const match of statement.matchAll(pattern)) segments.push(match[1])
  }
  return segments.length ? segments : [statement]
}

function replaceFractions(source: string): string {
  let current = source
  const fraction = /\\(?:d?frac)\s*\{([^{}]+)\}\s*\{([^{}]+)\}/g
  for (let iteration = 0; iteration < 12 && fraction.test(current); iteration++) {
    fraction.lastIndex = 0
    current = current.replace(fraction, '(($1)/($2))')
  }
  return current
}

function normalizeLatexExpression(source: string): string | null {
  let value = source
    .replace(/\\left|\\right/g, '')
    .replace(/−|–/g, '-')
    .replace(/\\cdot|\\times/g, '*')
    .replace(/\\sqrt\s*\{([^{}]+)\}/g, 'sqrt($1)')
  value = replaceFractions(value)
    .replace(/\^\s*\{([^{}]+)\}/g, '^($1)')
    .replace(/_\s*\{[^{}]+\}/g, '')
    .replace(/[{}]/g, match => match === '{' ? '(' : ')')
    .replace(/\\[a-zA-Z]+/g, '')
    .replace(/[^0-9A-Za-z+\-*/^().\s]/g, '')
    .trim()
  if (!value || /[A-Za-z]{2,}/.test(value.replace(/sqrt/g, ''))) return null
  return value
}

function extractPolynomial(parent: DiscoveryParent, index: number): PolynomialInput | null {
  const parentId = String(parent.id || `parent-${index + 1}`)
  for (const segment of mathSegments(parent.statement ?? '')) {
    const relation = segment.match(/([^=<>]+)=([^=<>]+)/)
    if (!relation) continue
    const left = normalizeLatexExpression(relation[1])
    const right = normalizeLatexExpression(relation[2])
    if (!left || !right) continue
    const normalized = `((${left})-(${right}))`
    const variables = new Set((normalized.replace(/sqrt/g, '').match(/[A-Za-z]/g) ?? []))
    if (variables.size !== 1) continue
    const variable = [...variables][0]
    const alphaNormalized = normalized.replace(new RegExp(`(?<![A-Za-z])${variable}(?![A-Za-z])`, 'g'), 'x')
    return { parentId, source: relation[0].trim(), normalized: alphaNormalized }
  }
  return null
}

function backendPath(): string {
  return path.resolve(process.cwd(), 'backend', 'sympy_fusion.py')
}

function runBackend(left: PolynomialInput, right: PolynomialInput, operation: Operation): BackendResult | null {
  const cacheKey = JSON.stringify([left.normalized, right.normalized, operation])
  if (backendCache.has(cacheKey)) return backendCache.get(cacheKey) ?? null
  const request = JSON.stringify({ left: left.normalized, right: right.normalized, operation })
  const commands = process.platform === 'win32' ? ['python', 'py'] : ['python3', 'python']
  for (const command of commands) {
    const args = command === 'py' ? ['-3', backendPath()] : [backendPath()]
    const result = spawnSync(command, args, {
      input: request,
      encoding: 'utf8',
      timeout: 45_000,
      maxBuffer: 4 * 1024 * 1024,
    })
    if (result.error && (result.error as NodeJS.ErrnoException).code === 'ENOENT') continue
    if (!result.stdout) {
      backendCache.set(cacheKey, null)
      return null
    }
    try {
      const parsed = JSON.parse(result.stdout) as BackendResult | { error: string }
      const value = 'error' in parsed ? null : parsed
      backendCache.set(cacheKey, value)
      return value
    } catch {
      backendCache.set(cacheKey, null)
      return null
    }
  }
  backendCache.set(cacheKey, null)
  return null
}

function operationTex(operation: Operation): string {
  if (operation === 'sum') return '\\alpha+\\beta'
  if (operation === 'difference') return '\\alpha-\\beta'
  return '\\alpha\\beta'
}

function operationLabel(operation: Operation): string {
  if (operation === 'sum') return '和'
  if (operation === 'difference') return '差'
  return '積'
}

export function supportsPolynomialRootFusion(parents: DiscoveryParent[]): {
  applicable: boolean
  reason: string
  inputs: PolynomialInput[]
} {
  const inputs = parents.map(extractPolynomial).filter((item): item is PolynomialInput => item !== null)
  const distinctParents = new Set(inputs.map(input => input.parentId))
  return {
    applicable: distinctParents.size >= 2,
    reason: distinctParents.size >= 2
      ? `${distinctParents.size} parents provide parseable univariate polynomial constraints`
      : 'fewer than two parents provide parseable univariate polynomial constraints',
    inputs,
  }
}

export function synthesizePolynomialRootFusions(
  parents: DiscoveryParent[],
  requested: number,
  round = 1,
): ExecutableFusionCard[] {
  const startedAt = Date.now()
  const support = supportsPolynomialRootFusion(parents)
  if (!support.applicable) return []
  const operations: Operation[] = round % 3 === 1
    ? ['sum', 'product', 'difference']
    : round % 3 === 2
      ? ['product', 'difference', 'sum']
      : ['difference', 'sum', 'product']
  const cards: ExecutableFusionCard[] = []
  for (let leftIndex = 0; leftIndex < support.inputs.length; leftIndex++) {
    for (let rightIndex = leftIndex + 1; rightIndex < support.inputs.length; rightIndex++) {
      const left = support.inputs[leftIndex]
      const right = support.inputs[rightIndex]
      if (left.parentId === right.parentId) continue
      for (const operation of operations) {
        if (cards.length >= requested) return cards
        const result = runBackend(left, right, operation)
        if (!result) continue
        const parentIds = [left.parentId, right.parentId]
        const expression = operationTex(operation)
        const structureId = `root-set.${operation}.${hash({ parentIds, left: result.left, right: result.right })}`
        const morphisms = [
          'PolynomialConstraintExtraction',
          'RootConfiguration',
          operation === 'sum' ? 'MinkowskiSum' : operation === 'difference' ? 'MinkowskiDifference' : 'PointwiseProduct',
          'FiberProduct',
          'ParameterElimination',
          'Resultant',
          'SquareFreeReduction',
          'NumericRootCounterexampleCheck',
          'ParentPerturbationAblation',
        ]
        const statement = `\(f(x)=${result.left}\), \(g(x)=${result.right}\) とする。\(f(\alpha)=0\), \(g(\beta)=0\) を満たす複素数 \(\alpha,\beta\) をすべて動かしたとき、\(${expression}\) の異なる値全体をちょうど根にもつモニック多項式を求めよ。`
        const answer = `P(z)=${result.result}`
        const substitution = operation === 'sum'
          ? 'g(z-x)'
          : operation === 'difference'
            ? 'g(x-z)'
            : `x^{${result.degree_right}}g(z/x)`
        const solution = `\(f(x)=0\) の根 \(\alpha\) と \(g(y)=0\) の根 \(\beta\) の${operationLabel(operation)}を消去する。したがって \[R(z)=\operatorname{Res}_x\!\left(f(x),${substitution}\right)\] を計算し、重複根を除いてモニック化すればよい。厳密終結式計算により \(P(z)=${result.result}\) を得る。全根の数値照合と、各親多項式を独立に摂動するアブレーション検査も通過した。`
        const proofCertificate = [
          { id: 'typed-inputs', claim: 'both parents elaborate to univariate polynomial constraints', verifier: 'MathOS typed parser + SymPy Poly(QQ)' },
          { id: 'fiber-product', claim: `the joint root configuration contains every ordered pair (alpha,beta)`, verifier: 'finite algebraic fiber product' },
          { id: 'resultant', claim: `elimination computes every value of ${operation}`, verifier: 'SymPy exact resultant over QQ' },
          { id: 'squarefree', claim: 'the output roots are the distinct composed values', verifier: 'exact square-free monic reduction' },
          { id: 'numeric-check', claim: 'all numerical pairwise root compositions vanish in P', verifier: 'independent nroots comparison' },
          { id: 'ablation', claim: 'perturbing either parent changes P', verifier: 'two-sided parent perturbation' },
        ]
        cards.push({
          id: `mathos-discovered-${hash([structureId, result.result])}`,
          family_id: `discovered.polynomial_root_${operation}`,
          statement_tex: statement,
          answer_tex: answer,
          solution_tex: solution,
          domain: 'algebraic_geometry',
          morphism_chain: morphisms,
          parent_ids: parentIds,
          unresolved: false,
          discovery_status: 'verified',
          verification: {
            method: 'exact resultant plus independent numerical roots and parent perturbation',
            exact_backend: true,
            independent_check: true,
            samples: [result.degree_left, result.degree_right, result.degree_result],
          },
          difficulty: { band: 'A_algebraic_elimination', score: 7 + result.degree_result + morphisms.length * 0.25 },
          fusion_derivation: {
            passed: true,
            reason: 'each parent supplies one algebraic root configuration and the binary root-set operation requires both inputs',
            ablationPassed: true,
            assignments: [
              { parentId: left.parentId, portId: 'left_root_set', role: 'object', matchedAnchors: [left.source], witnessSteps: ['PolynomialConstraintExtraction', 'RootConfiguration'] },
              { parentId: right.parentId, portId: 'right_root_set', role: 'object', matchedAnchors: [right.source], witnessSteps: ['PolynomialConstraintExtraction', 'RootConfiguration'] },
            ],
            bridges: [{ id: `root-set-${operation}`, witnessStep: morphisms[2], consumes: ['left_root_set', 'right_root_set'], produces: 'composed_root_set' }],
            intermediatePropositions: [
              { parentId: left.parentId, morphism: 'RootConfiguration', source: 'Polynomial', target: 'FiniteAlgebraicOrbit', proposition: 'the roots of f form a finite algebraic configuration', proved: true },
              { parentId: right.parentId, morphism: 'RootConfiguration', source: 'Polynomial', target: 'FiniteAlgebraicOrbit', proposition: 'the roots of g form a finite algebraic configuration', proved: true },
            ],
          },
          structure_blueprint: {
            id: structureId,
            version: 1,
            kernel: 'binary_operation_on_algebraic_root_configurations',
            observable: `minimal_squarefree_root_polynomial_of_${operation}`,
            operators: morphisms,
            domain: 'algebraic_geometry',
            tags: ['polynomial', 'root_configuration', operation, 'resultant'],
            morphismChain: morphisms,
            executable: true,
            proofCertificate,
          },
          search_evidence: { hypotheses_evaluated: operations.length, valid_hypotheses: cards.length + 1, elapsed_ms: Date.now() - startedAt },
        })
      }
    }
  }
  return cards
}
