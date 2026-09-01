import { createHash } from 'node:crypto'

import type { DiscoveryParent } from './parent-conditioned-discovery'
import type { ExecutableFusionCard } from './executable-fusion'
import {
  executeLinearInvariant,
  verifyLinearInvariantCertificate,
  type LinearEquation,
  type LinearInvariantProgram,
  type RationalInput,
} from './exact-linear-invariant'
import { runtimeSynthesisCertificate } from './execution-certificate'
import { lowerLinearPredicateStatement } from './linear-predicate-lowerer'

type Q = { n: bigint; d: bigint }

type ParentBlock = {
  parentId: string
  sourceVariables: string[]
  generatedVariables: string[]
  equations: LinearEquation[]
  equationOffset: number
  translation: string[]
  shear: Array<{ source: string; target: string; coefficient: string }>
}

export type RuntimeLinearProblemGeneration = {
  applicable: boolean
  reason: string
  cards: ExecutableFusionCard[]
  hypothesesEvaluated: number
}

const ZERO: Q = { n: 0n, d: 1n }
const ONE: Q = { n: 1n, d: 1n }

function gcd(left: bigint, right: bigint): bigint {
  let a = left < 0n ? -left : left
  let b = right < 0n ? -right : right
  while (b !== 0n) [a, b] = [b, a % b]
  return a || 1n
}

function q(n: bigint, d = 1n): Q {
  if (d === 0n) throw new Error('zero rational denominator')
  if (d < 0n) return q(-n, -d)
  const divisor = gcd(n, d)
  return { n: n / divisor, d: d / divisor }
}

function parse(value: RationalInput): Q {
  if (typeof value === 'bigint') return q(value)
  if (typeof value === 'number') {
    if (!Number.isSafeInteger(value)) throw new Error('runtime linear generation requires exact rational coefficients')
    return q(BigInt(value))
  }
  const match = value.trim().match(/^([+-]?\d+)(?:\/([+-]?\d+))?$/)
  if (!match) throw new Error(`invalid rational coefficient: ${value}`)
  return q(BigInt(match[1]), BigInt(match[2] ?? '1'))
}

function add(left: Q, right: Q): Q { return q(left.n * right.d + right.n * left.d, left.d * right.d) }
function negate(value: Q): Q { return { n: -value.n, d: value.d } }
function subtract(left: Q, right: Q): Q { return add(left, negate(right)) }
function multiply(left: Q, right: Q): Q { return q(left.n * right.n, left.d * right.d) }
function equal(left: Q, right: Q): boolean { return left.n === right.n && left.d === right.d }
function isZero(value: Q): boolean { return value.n === 0n }
function format(value: Q): string { return value.d === 1n ? String(value.n) : `${value.n}/${value.d}` }

function tex(value: Q, absolute = false): string {
  const numerator = absolute && value.n < 0n ? -value.n : value.n
  return value.d === 1n ? String(numerator) : `\\frac{${numerator}}{${value.d}}`
}

function hash(value: unknown, length = 16): string {
  return createHash('sha256').update(JSON.stringify(value)).digest('hex').slice(0, length)
}

function addTerm(terms: Map<string, Q>, variable: string, coefficient: Q): void {
  const next = add(terms.get(variable) ?? ZERO, coefficient)
  if (isZero(next)) terms.delete(variable)
  else terms.set(variable, next)
}

function record(terms: Map<string, Q>): Record<string, string> {
  return Object.fromEntries([...terms].sort(([left], [right]) => left.localeCompare(right)).map(
    ([variable, coefficient]) => [variable, format(coefficient)],
  ))
}

function variableTex(variable: string): string {
  const match = variable.match(/^u_(\d+)_(\d+)$/)
  return match ? `u_{${match[1]},${match[2]}}` : variable.replace(/_/g, '\\_')
}

function linearTex(terms: Record<string, RationalInput>): string {
  const pieces: string[] = []
  for (const [variable, rawCoefficient] of Object.entries(terms).sort(([left], [right]) => left.localeCompare(right))) {
    const coefficient = parse(rawCoefficient)
    if (isZero(coefficient)) continue
    const negative = coefficient.n < 0n
    const absolute = q(negative ? -coefficient.n : coefficient.n, coefficient.d)
    const body = equal(absolute, ONE)
      ? variableTex(variable)
      : `${tex(absolute)}\\,${variableTex(variable)}`
    if (pieces.length === 0) pieces.push(negative ? `-${body}` : body)
    else pieces.push(negative ? `-${body}` : `+${body}`)
  }
  return pieces.join('') || '0'
}

function nonzeroVariables(terms: Record<string, RationalInput>): string[] {
  return Object.entries(terms)
    .filter(([, coefficient]) => !isZero(parse(coefficient)))
    .map(([variable]) => variable)
    .sort()
}

function signedProduct(coefficient: Q, body: string, first: boolean): string {
  const negative = coefficient.n < 0n
  const absolute = q(negative ? -coefficient.n : coefficient.n, coefficient.d)
  const product = equal(absolute, ONE) ? body : `${tex(absolute)}\\cdot ${body}`
  if (first) return negative ? `-${product}` : product
  return negative ? `-${product}` : `+${product}`
}

function transformedBlock(
  parent: DiscoveryParent,
  parentIndex: number,
  variant: number,
  equationOffset: number,
): ParentBlock | null {
  const lowered = lowerLinearPredicateStatement(parent.statement ?? '')
  if (lowered.status !== 'lowered' || lowered.program.coordinate !== 'additive') return null
  if ((lowered.program.sideConditions ?? []).some(condition => !condition.proved)) return null
  if (lowered.certificate.status === 'inconsistent') return null

  const sourceVariables = [...new Set(lowered.program.equations.flatMap(equation =>
    Object.entries(equation.terms)
      .filter(([, coefficient]) => !isZero(parse(coefficient)))
      .map(([variable]) => variable),
  ))].sort()
  if (sourceVariables.length === 0) return null

  const generatedVariables = sourceVariables.map((_, index) => `u_${parentIndex + 1}_${index + 1}`)
  const translation = sourceVariables.map((_, index) => {
    const magnitude = BigInt((variant + 1) * (parentIndex + 1) + index)
    return q((parentIndex + index + variant) % 2 === 0 ? magnitude : -magnitude)
  })
  const shear = sourceVariables.slice(0, -1).map((source, index) => {
    const magnitude = BigInt(1 + ((variant + parentIndex + index) % 3))
    return {
      source,
      target: sourceVariables[index + 1],
      coefficient: format(q((variant + parentIndex + index) % 2 === 0 ? magnitude : -magnitude)),
    }
  })

  const equations = lowered.program.equations
    .filter(equation => nonzeroVariables(equation.terms).length > 0)
    .map((equation, equationIndex): LinearEquation => {
      const terms = new Map<string, Q>()
      let translatedConstant = ZERO
      sourceVariables.forEach((sourceVariable, sourceIndex) => {
        const coefficient = parse(equation.terms[sourceVariable] ?? 0)
        if (isZero(coefficient)) return
        addTerm(terms, generatedVariables[sourceIndex], coefficient)
        if (sourceIndex + 1 < sourceVariables.length) {
          addTerm(terms, generatedVariables[sourceIndex + 1], multiply(coefficient, parse(shear[sourceIndex].coefficient)))
        }
        translatedConstant = add(translatedConstant, multiply(coefficient, translation[sourceIndex]))
      })
      return {
        terms: record(terms),
        rhs: format(subtract(parse(equation.rhs), translatedConstant)),
        provenance: [
          ...equation.provenance,
          `runtime-affine-chart:parent-${parentIndex + 1}:equation-${equationIndex + 1}`,
        ],
      }
    })
    .filter(equation => nonzeroVariables(equation.terms).length > 0)
  if (equations.length === 0) return null

  return {
    parentId: String(parent.id),
    sourceVariables,
    generatedVariables,
    equations,
    equationOffset,
    translation: translation.map(format),
    shear,
  }
}

function rowWeight(parentIndex: number, equationIndex: number, variant: number): Q {
  if (parentIndex === 0 && equationIndex === 0) return ONE
  const magnitude = BigInt((variant + 1) * (parentIndex + equationIndex + 1) + 1)
  return q((parentIndex + equationIndex + variant) % 2 === 0 ? magnitude : -magnitude)
}

function generatedCard(
  parents: readonly DiscoveryParent[],
  variant: number,
  hypothesesEvaluated: number,
): ExecutableFusionCard | null {
  let equationOffset = 0
  const blocks: ParentBlock[] = []
  for (let parentIndex = 0; parentIndex < parents.length; parentIndex++) {
    const block = transformedBlock(parents[parentIndex], parentIndex, variant, equationOffset)
    if (!block) return null
    blocks.push(block)
    equationOffset += block.equations.length
  }
  const equations = blocks.flatMap(block => block.equations)
  if (equations.length === 0) return null

  const target = new Map<string, Q>()
  let expected = ZERO
  const selectedWeights: string[] = []
  const parentTargets: Array<Record<string, string>> = []
  for (let parentIndex = 0; parentIndex < blocks.length; parentIndex++) {
    const parentTarget = new Map<string, Q>()
    blocks[parentIndex].equations.forEach((equation, equationIndex) => {
      const weight = rowWeight(parentIndex, equationIndex, variant)
      selectedWeights.push(format(weight))
      for (const [variable, coefficient] of Object.entries(equation.terms)) {
        const contribution = multiply(weight, parse(coefficient))
        addTerm(target, variable, contribution)
        addTerm(parentTarget, variable, contribution)
      }
      expected = add(expected, multiply(weight, parse(equation.rhs)))
    })
    if (parentTarget.size === 0) return null
    parentTargets.push(record(parentTarget))
  }

  const program: LinearInvariantProgram = {
    coordinate: 'additive',
    equations,
    goal: { terms: record(target), constant: '0', expected: format(expected) },
  }
  const certificate = executeLinearInvariant(program)
  if (certificate.status !== 'proved' || certificate.expectedMatches !== true ||
      !verifyLinearInvariantCertificate(program, certificate) || certificate.value === null ||
      certificate.proofCoefficients === null) return null

  for (const block of blocks) {
    const coefficients = certificate.proofCoefficients.slice(
      block.equationOffset,
      block.equationOffset + block.equations.length,
    )
    if (coefficients.every(coefficient => isZero(parse(coefficient)))) return null
  }

  const ablations = blocks.map(block => {
    const withoutParent: LinearInvariantProgram = {
      ...program,
      equations: equations.filter((_, index) =>
        index < block.equationOffset || index >= block.equationOffset + block.equations.length),
    }
    return { parent_id: block.parentId, status: executeLinearInvariant(withoutParent).status }
  })
  if (ablations.some(ablation => ablation.status === 'proved')) return null

  const counterfactuals = blocks.map((block, parentIndex) => {
    const variable = nonzeroVariables(parentTargets[parentIndex])[0]
    if (!variable) return null
    const shiftedEquations = equations.map((equation, equationIndex): LinearEquation => {
      if (equationIndex < block.equationOffset || equationIndex >= block.equationOffset + block.equations.length) {
        return equation
      }
      return {
        ...equation,
        rhs: format(add(parse(equation.rhs), parse(equation.terms[variable] ?? 0))),
      }
    })
    const shiftedProgram: LinearInvariantProgram = { ...program, equations: shiftedEquations }
    const shifted = executeLinearInvariant(shiftedProgram)
    if (shifted.status !== 'proved' || shifted.value === null ||
        !verifyLinearInvariantCertificate(shiftedProgram, shifted)) return null
    const predicted = add(parse(certificate.value!), parse(program.goal.terms[variable] ?? 0))
    if (!equal(parse(shifted.value), predicted) || equal(parse(shifted.value), parse(certificate.value!))) return null
    return {
      parent_id: block.parentId,
      shifted_variable: variable,
      value_before: certificate.value!,
      value_after: shifted.value,
      exact_delta: format(subtract(parse(shifted.value), parse(certificate.value!))),
    }
  })
  if (counterfactuals.some(value => value === null)) return null

  const signature = hash({
    parents: parents.map(parent => ({ id: parent.id, statement: parent.statement })),
    variant,
    program,
  })
  const parentIds = blocks.map(block => block.parentId)
  const chain = [
    'CurrentStatementElaboration',
    'ExactAffineConstraintIR',
    'VariableNamespace',
    'InvertibleAffineChart',
    'ConstraintRowComposition',
    'ProofCombinationReplay',
    'GeneratedProblem',
  ]
  const obligationIds = [
    'current-input-elaboration',
    'invertible-coordinate-change',
    'nonzero-parent-contribution',
    'exact-row-space-membership',
    'whole-parent-ablation',
    'structure-preserving-parent-perturbation',
  ]
  const equationRows = equations.map((equation, index) =>
    `E_{${index + 1}}:\\quad ${linearTex(equation.terms)}=${tex(parse(equation.rhs))}`,
  ).join('\\\\')
  const targetTex = linearTex(program.goal.terms)
  const proofTerms = certificate.proofCoefficients
    .map((coefficient, index) => ({ coefficient: parse(coefficient), index }))
    .filter(item => !isZero(item.coefficient))
  const proofRows = proofTerms
    .map((item, index) => signedProduct(item.coefficient, `E_{${item.index + 1}}`, index === 0))
    .join('')
  const proofRightHandSide = proofTerms
    .map((item, index) => signedProduct(
      item.coefficient,
      `\\left(${tex(parse(equations[item.index].rhs))}\\right)`,
      index === 0,
    ))
    .join('')
  const answerTex = tex(parse(certificate.value))
  const proofCertificate = [
    { id: `${signature}.parse`, claim: 'all constraints were elaborated from the current parent statements', verifier: 'typed-linear-lowerer' },
    { id: `${signature}.chart`, claim: 'each variable change is affine and has unit triangular linear part', verifier: 'unimodular-chart-check' },
    { id: `${signature}.rowspace`, claim: `the generated observable equals ${certificate.value}`, verifier: 'exact-rational-rref' },
    { id: `${signature}.replay`, claim: 'stored coefficients reconstruct the generated observable exactly', verifier: 'linear-combination-replay' },
    { id: `${signature}.ablation`, claim: 'removing any selected parent destroys the proof', verifier: 'whole-parent-ablation' },
    { id: `${signature}.perturb`, claim: 'a consistent unit shift in every parent changes the exact answer', verifier: 'counterfactual-linear-replay' },
  ]
  const generatedProgram = {
    schema: 'mortra.runtime-linear-problem-generation.v1',
    variant,
    parent_blocks: blocks.map((block, index) => ({
      parent_id: block.parentId,
      source_variables: block.sourceVariables,
      generated_variables: block.generatedVariables,
      translation: block.translation,
      shear: block.shear,
      selected_weights: selectedWeights.slice(block.equationOffset, block.equationOffset + block.equations.length),
      target_contribution: parentTargets[index],
    })),
    equations,
    goal: program.goal,
    exact_value: certificate.value,
    proof_coefficients: certificate.proofCoefficients,
    ablations,
    counterfactuals,
  }

  return {
    id: `mortra-runtime-linear-generation.${signature}`,
    family_id: 'runtime.linear_constraint_composition',
    statement_tex: `実数 ${blocks.flatMap(block => block.generatedVariables).map(variableTex).join(',')} が` +
      `\\[\\begin{aligned}${equationRows}\\end{aligned}\\]` +
      `を満たすとき、\\[${targetTex}\\] の値を求めよ。`,
    answer_tex: answerTex,
    solution_tex: `各等式を上から順に $E_1,E_2,\\ldots,E_{${equations.length}}$ とする。` +
      `入力された制約を変数の衝突がない座標へ移し、行基本変形で目標式を照合すると、` +
      `等式 ${proofRows} を作ればよいと分かる。その左辺と右辺をそれぞれ整理すると、` +
      `\\[${proofRows}\\quad\\Longrightarrow\\quad ${targetTex}=${proofRightHandSide}=${answerTex}.\\]` +
      `係数はすべて有理数として厳密に計算し、同じ線形結合を独立に再生して検算した。` +
      `さらに、どの親問題の制約を一組でも外すと目標式は決定不能になり、` +
      `各親の変数を整合性を保って1だけ動かすと答えも変わる。したがって、すべての親問題がこの結論に必要である。`,
    domain: 'runtime_exact_linear_composition',
    morphism_chain: chain,
    parent_ids: parentIds,
    unresolved: false,
    discovery_status: 'verified',
    verification: {
      method: 'runtime affine elaboration + exact row-space proof + whole-parent counterfactual replay',
      exact_backend: true,
      independent_check: true,
      samples: [equations.length, target.size, blocks.length, variant],
    },
    difficulty: {
      band: 'runtime_structural_linear',
      score: Math.max(2, equations.length + target.size / 2 + blocks.length + variant / 4),
    },
    fusion_derivation: {
      passed: true,
      reason: 'the generated observable was synthesized from the current constraint rows and needs every selected parent',
      ablationPassed: true,
      assignments: blocks.map((block, index) => ({
        parentId: block.parentId,
        portId: `input:${block.parentId}`,
        role: 'current_affine_constraint_block',
        matchedAnchors: block.sourceVariables,
        witnessSteps: chain,
        requiredObligations: obligationIds,
        consumedObligations: obligationIds,
        coverage: 1,
      })),
      bridges: [{
        id: `runtime-linear-composition:${signature}`,
        witnessStep: 'ProofCombinationReplay',
        consumes: parentIds.map(parentId => `input:${parentId}`),
        produces: 'VerifiedGeneratedProblem',
      }],
      intermediatePropositions: blocks.map((block, index) => ({
        parentId: block.parentId,
        morphism: 'ConstraintRowComposition',
        source: 'CurrentAffineConstraintIR',
        target: 'GeneratedAffineObservable',
        proposition: `parent ${index + 1} contributes a nonzero row-space component and passes exact ablation`,
        proved: true,
      })),
    },
    structure_blueprint: {
      id: `runtime-linear-generation.${signature}`,
      version: 1,
      kernel: 'runtime_exact_linear_constraint_composer',
      observable: 'VerifiedGeneratedProblem',
      operators: chain,
      domain: 'current_input_affine_constraint_ir',
      tags: ['runtime-synthesis', 'atlas-free', 'one-to-many', 'exact-linear-constraints'],
      morphismChain: chain,
      executable: true,
      proofCertificate,
    },
    search_evidence: {
      hypotheses_evaluated: hypothesesEvaluated,
      valid_hypotheses: 1,
      elapsed_ms: 0,
    },
    execution_certificate: runtimeSynthesisCertificate({
      origin: 'synthesized_linear_program',
      parents,
      generatedProgram,
      checks: proofCertificate.map(item => `${item.id}: ${item.verifier}`),
    }),
  }
}

export function synthesizeRuntimeLinearProblems(
  parents: readonly DiscoveryParent[],
  requested: number,
): RuntimeLinearProblemGeneration {
  if (parents.length === 0 || requested <= 0) {
    return { applicable: false, reason: 'at least one current parent is required', cards: [], hypothesesEvaluated: 0 }
  }
  if (parents.some(parent => parent.id === undefined) || new Set(parents.map(parent => String(parent.id))).size !== parents.length) {
    return { applicable: false, reason: 'current parents require distinct stable ids for proof ablation', cards: [], hypothesesEvaluated: 0 }
  }
  const lowered = parents.map(parent => lowerLinearPredicateStatement(parent.statement ?? ''))
  const invalidIndex = lowered.findIndex(result =>
    result.status !== 'lowered' || result.program.coordinate !== 'additive' ||
    result.certificate.status === 'inconsistent' ||
    (result.program.sideConditions ?? []).some(condition => !condition.proved),
  )
  if (invalidIndex >= 0) {
    const invalid = lowered[invalidIndex]
    const detail = invalid.status === 'lowered'
      ? `coordinate=${invalid.program.coordinate}, status=${invalid.certificate.status}`
      : `${invalid.status}: ${invalid.detail}`
    return {
      applicable: false,
      reason: `parent ${invalidIndex + 1} is not an executable additive constraint system (${detail})`,
      cards: [],
      hypothesesEvaluated: 0,
    }
  }

  const cards: ExecutableFusionCard[] = []
  const seen = new Set<string>()
  let hypothesesEvaluated = 0
  const budget = Math.max(requested * 12, 24)
  for (let variant = 0; variant < budget && cards.length < requested; variant++) {
    hypothesesEvaluated++
    const card = generatedCard(parents, variant, hypothesesEvaluated)
    if (!card) continue
    const normalForm = hash({ statement: card.statement_tex, answer: card.answer_tex }, 32)
    if (seen.has(normalForm)) continue
    seen.add(normalForm)
    cards.push(card)
  }
  return {
    applicable: cards.length > 0,
    reason: cards.length
      ? `${cards.length} fresh exact problems were composed from the current constraint rows without a registered route`
      : `${hypothesesEvaluated} runtime row-space constructions failed exact replay or whole-parent causality`,
    cards,
    hypothesesEvaluated,
  }
}
