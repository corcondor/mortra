import { spawnSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { resolve } from 'node:path'

import type { ExecutableFusionCard } from './executable-fusion'
import {
  liftParent,
  type DiscoveryParent,
} from './parent-conditioned-discovery'
import { extractBoundMathExpression, isDirectBoundExpressionQuery } from './math-expression-ir'

type BridgeCard = {
  statement_tex?: unknown
  answer_tex?: unknown
  solution_tex?: unknown
  family_id?: unknown
  domain?: unknown
  morphism_chain?: unknown
  verification?: unknown
  execution_certificate?: unknown
  diagram?: unknown
  diagram_tikz?: unknown
  visual_explanation?: unknown
  proof_roadmap?: unknown
  proof_obligations?: unknown
}

type BridgeResponse = {
  ok?: unknown
  status?: unknown
  error?: unknown
  engine?: unknown
  evaluation_mode?: unknown
  registered_research_replay?: unknown
  trace?: unknown
  diagnostics?: unknown
  card?: BridgeCard
  results?: BridgeResponse[]
}

export type ExactCasSynthesis = {
  applicable: boolean
  reason: string
  cards: ExecutableFusionCard[]
  diagnostics?: Record<string, unknown>
}

const resultCache = new Map<string, ExactCasSynthesis>()

function sha256(value: string): string {
  return createHash('sha256').update(value).digest('hex')
}

function shortHash(value: unknown, length = 16): string {
  return createHash('sha256').update(JSON.stringify(value)).digest('hex').slice(0, length)
}

function stringArray(value: unknown): string[] | null {
  return Array.isArray(value) && value.every(item => typeof item === 'string')
    ? value
    : null
}

function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null
}

function repositoryRoot(): string {
  return resolve(__dirname, '..', '..')
}

function invokeBridgeRequest(request: Record<string, unknown>): BridgeResponse {
  const root = repositoryRoot()
  const python = process.env.MORTRA_PYTHON || process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3')
  const script = resolve(root, 'worker', 'backend', 'exact_problem_solver_bridge.py')
  const batchSize = Array.isArray(request.statements) ? request.statements.length : 1
  const run = spawnSync(python, ['-B', script], {
    cwd: root,
    input: JSON.stringify(request),
    encoding: 'utf8',
    timeout: Math.max(120_000, batchSize * 45_000),
    maxBuffer: 32 * 1024 * 1024,
    windowsHide: true,
  })
  if (run.error) throw run.error
  if (!run.stdout.trim()) {
    throw new Error(run.stderr.trim() || `exact solver bridge exited with code ${run.status ?? 'unknown'}`)
  }
  try {
    return JSON.parse(run.stdout) as BridgeResponse
  } catch {
    throw new Error(`exact solver bridge returned invalid JSON: ${run.stdout.slice(0, 240)}`)
  }
}

function invokeBridge(statement: string): BridgeResponse {
  const parsed = isDirectBoundExpressionQuery(statement)
    ? extractBoundMathExpression(statement)
    : null
  return invokeBridgeRequest({
    statement,
    ...(parsed ? { expression_ir: parsed.expression } : {}),
  })
}

function toExecutableCard(parent: DiscoveryParent, response: BridgeResponse): ExecutableFusionCard | null {
  const source = response.card
  if (!source) return null
  const statement = parent.statement?.trim() ?? ''
  const answer = typeof source.answer_tex === 'string' ? source.answer_tex : ''
  const solution = typeof source.solution_tex === 'string' ? source.solution_tex : ''
  const returnedStatement = typeof source.statement_tex === 'string' ? source.statement_tex : ''
  const chain = stringArray(source.morphism_chain)
  const verification = record(source.verification)
  const certificate = record(source.execution_certificate)
  if (!statement || !answer || !solution || returnedStatement !== statement || !chain?.length || !verification || !certificate) {
    return null
  }
  const registeredReplay = response.registered_research_replay === true &&
    response.evaluation_mode === 'portfolio' &&
    certificate?.registered_composite_used === true &&
    certificate?.capability_origin === 'registered_parameterized_morphism' &&
    record(certificate?.cold_generalization_contract) !== null
  if ((response.evaluation_mode !== 'cold' && !registeredReplay) ||
      typeof response.engine !== 'string' || !response.engine.includes('no LLM')) {
    return null
  }
  if (verification.exact_backend !== true || verification.independent_check !== true) return null
  if (certificate.statement_sha256 !== sha256(statement) || certificate.answer_tex_sha256 !== sha256(answer)) {
    return null
  }
  const certificateChain = stringArray(certificate.morphism_chain)
  if (!certificateChain || certificateChain.join('\u0000') !== chain.join('\u0000')) return null

  const parentId = String(parent.id || `single-${shortHash(statement, 10)}`)
  const graph = liftParent(parent)
  const anchors = [...new Set([...graph.semantic_roots, ...graph.constraints])]
  if (anchors.length === 0) anchors.push('ProblemText')
  const family = typeof source.family_id === 'string' ? source.family_id : 'solve.exact.symbolic'
  const domain = typeof source.domain === 'string' ? source.domain : 'exact_symbolic'
  const signature = shortHash({ statement, answer, certificate: certificate.answer_tex_sha256 })
  const requiredObligations = [
    'the solver input is byte-identical to the selected parent statement',
    'the exact backend returns no unevaluated target operation',
    'the answer replays against the original expression with zero residual',
    'the statement and answer hashes match across the Python and TypeScript runtimes',
  ]
  const proofCertificate = [
    { id: `${signature}.input`, claim: 'the executed statement matches the selected parent problem', verifier: 'cross-runtime-sha256' },
    { id: `${signature}.execution`, claim: 'the requested observable was evaluated exactly', verifier: String(certificate.tool_name || 'mortra-exact-backend') },
    { id: `${signature}.replay`, claim: 'the exact result satisfies the original executable obligation', verifier: 'original-obligation-replay' },
  ]

  const card: ExecutableFusionCard = {
    id: `mortra-single-exact-cas.${signature}`,
    family_id: family,
    statement_tex: statement,
    answer_tex: answer,
    solution_tex: solution,
    domain,
    morphism_chain: chain,
    parent_ids: [parentId],
    unresolved: false,
    discovery_status: 'verified',
    verification: {
      method: typeof verification.method === 'string'
        ? `${verification.method}; cross-runtime SHA-256 replay`
        : 'exact symbolic execution + original-obligation replay + cross-runtime SHA-256 replay',
      exact_backend: true,
      independent_check: true,
      samples: [],
    },
    difficulty: { band: 'certified', score: Math.max(1, chain.length - 2) },
    fusion_derivation: {
      passed: true,
      reason: registeredReplay
        ? 'the parameterized research schema was replayed against the current statement; the public product boundary still rejects it'
        : 'the answer was computed from the unregistered statement in cold mode and replayed against that same statement',
      ablationPassed: true,
      assignments: [{
        parentId,
        portId: 'input_1',
        role: 'typed_executable_problem',
        matchedAnchors: anchors,
        witnessSteps: chain,
        requiredObligations,
        consumedObligations: requiredObligations,
        coverage: 1,
      }],
      bridges: [{
        id: 'single_problem_exact_execution',
        witnessStep: chain.at(-2) ?? 'ExactBackend',
        consumes: ['input_1'],
        produces: 'VerifiedAnswer',
      }],
      intermediatePropositions: [{
        parentId,
        morphism: chain.at(-2) ?? 'ExactBackend',
        source: chain[0],
        target: chain.at(-1) ?? 'VerifiedAnswer',
        proposition: `the executable observable has the exact value ${answer}`,
        proved: true,
      }],
    },
    structure_blueprint: {
      id: `single-exact-cas.${signature}`,
      version: 1,
      kernel: 'typed_exact_symbolic_execution',
      observable: 'VerifiedAnswer',
      operators: chain,
      domain: registeredReplay ? 'registered_parameterized_research_replay' : 'unregistered_typed_problem',
      tags: anchors,
      morphismChain: chain,
      executable: true,
      proofCertificate,
    },
    search_evidence: {
      hypotheses_evaluated: 1,
      valid_hypotheses: 1,
      elapsed_ms: 0,
    },
  }

  card.execution_certificate = certificate
  if (source.diagram !== undefined) card.diagram = source.diagram
  if (typeof source.diagram_tikz === 'string') card.diagram_tikz = source.diagram_tikz
  if (source.visual_explanation !== undefined) card.visual_explanation = source.visual_explanation
  if (source.proof_roadmap !== undefined) card.proof_roadmap = source.proof_roadmap
  if (source.proof_obligations !== undefined) card.proof_obligations = source.proof_obligations
  return card
}

export function synthesizeExactCasSingleProblem(parents: readonly DiscoveryParent[]): ExactCasSynthesis {
  if (parents.length !== 1) {
    return { applicable: false, reason: 'exact symbolic execution requires exactly one input problem', cards: [] }
  }
  const parent = parents[0]
  const statement = parent.statement?.trim() ?? ''
  if (!statement) return { applicable: false, reason: 'the input problem has no statement', cards: [] }
  const cacheKey = sha256(statement)
  const cached = resultCache.get(cacheKey)
  if (cached) return cached

  let result: ExactCasSynthesis
  try {
    const response = invokeBridge(statement)
    const card = response.ok === true ? toExecutableCard(parent, response) : null
    result = card
      ? {
          applicable: true,
          reason: 'the unregistered statement compiled to an exact executable obligation with a replayable certificate',
          cards: [card],
        }
      : {
          applicable: false,
          reason: `exact symbolic execution remained open: ${String(response.error || `status ${response.status ?? 'unknown'}`)}`,
          cards: [],
          ...(record(response.diagnostics) ? { diagnostics: record(response.diagnostics)! } : {}),
        }
  } catch (error) {
    result = {
      applicable: false,
      reason: `exact symbolic execution bridge failed: ${error instanceof Error ? error.message : String(error)}`,
      cards: [],
    }
  }
  resultCache.set(cacheKey, result)
  return result
}

export function clearExactCasSynthesisCache(): void {
  resultCache.clear()
}

export function synthesizeExactCasSingleProblemBatch(
  parents: readonly DiscoveryParent[],
): ExactCasSynthesis[] {
  if (parents.length === 0) return []
  const batchSize = Math.max(1, Number(process.env.MORTRA_CAS_AUDIT_BATCH_SIZE || 10))
  const responses: BridgeResponse[] = []
  for (let start = 0; start < parents.length; start += batchSize) {
    const batch = parents.slice(start, start + batchSize)
    try {
      const statements = batch.map(parent => parent.statement?.trim() ?? '')
      const expressionIrs = statements.map(statement =>
        isDirectBoundExpressionQuery(statement)
          ? extractBoundMathExpression(statement)?.expression ?? null
          : null)
      const response = invokeBridgeRequest({ statements, expression_irs: expressionIrs })
      if (!Array.isArray(response.results) || response.results.length !== batch.length) {
        throw new Error('exact symbolic execution bridge returned an invalid batch response')
      }
      responses.push(...response.results)
    } catch (error) {
      const reason = `exact symbolic execution bridge failed: ${error instanceof Error ? error.message : String(error)}`
      responses.push(...batch.map(() => ({ ok: false, error: reason })))
    }
  }
  return responses.map((item, index) => {
    const parent = parents[index]
    const card = item.ok === true ? toExecutableCard(parent, item) : null
    const result: ExactCasSynthesis = card
      ? {
          applicable: true,
          reason: 'the unregistered statement compiled to an exact executable obligation with a replayable certificate',
          cards: [card],
        }
      : {
          applicable: false,
          reason: `exact symbolic execution remained open: ${String(item.error || `status ${item.status ?? 'unknown'}`)}`,
          cards: [],
          ...(record(item.diagnostics) ? { diagnostics: record(item.diagnostics)! } : {}),
        }
    const statement = parent.statement?.trim() ?? ''
    if (statement) resultCache.set(sha256(statement), result)
    return result
  })
}
