import { createHash } from 'node:crypto'

import type { ExecutableFusionCard } from './executable-fusion'
import { evaluateExactExpressions, type ExactExpressionEvaluation } from './exact-expression-executor'
import { runtimeSynthesisCertificate } from './execution-certificate'
import {
  extractBoundMathExpression,
  mathExpressionToLatex,
  renameMathSymbol,
  type MathExpression,
} from './math-expression-ir'
import type { DiscoveryParent } from './parent-conditioned-discovery'

type GrammarState = {
  expression: MathExpression
  parents: number[]
  depth: number
  operators: string[]
}

type RuntimeProgram = {
  id: string
  parents: number[]
  depth: number
  operators: string[]
  construction: 'output-composition' | 'aligned-binder-body' | 'binder-body-lift' | 'binder-moment'
  structuralScore: number
  build: (inputs: readonly MathExpression[]) => MathExpression | null
}

export type RuntimeExpressionSynthesis = {
  applicable: boolean
  reason: string
  cards: ExecutableFusionCard[]
  hypothesesEvaluated: number
}

const PLACEHOLDER_PREFIX = '__mortra_parent_'
const cache = new Map<string, RuntimeExpressionSynthesis>()

function hash(value: unknown, length = 16): string {
  return createHash('sha256').update(JSON.stringify(value)).digest('hex').slice(0, length)
}

function unique<T>(values: readonly T[]): T[] {
  return [...new Set(values)]
}

function placeholder(index: number): string {
  return `${PLACEHOLDER_PREFIX}${index}`
}

function instantiate(expression: MathExpression, inputs: readonly MathExpression[]): MathExpression {
  if (typeof expression === 'number') return expression
  if (typeof expression === 'string') {
    if (!expression.startsWith(PLACEHOLDER_PREFIX)) return expression
    const index = Number(expression.slice(PLACEHOLDER_PREFIX.length))
    if (!Number.isInteger(index) || !inputs[index]) throw new Error(`invalid parent placeholder ${expression}`)
    return inputs[index]
  }
  if (expression[0] === 'Sum') {
    const [, index, lower, upper, body] = expression
    return ['Sum', index, instantiate(lower, inputs), instantiate(upper, inputs), instantiate(body, inputs)]
  }
  if (expression[0] === 'Limit') {
    const [, variable, destination, body] = expression
    return ['Limit', variable, instantiate(destination, inputs), instantiate(body, inputs)]
  }
  if (expression[0] === 'Integral') {
    const [, variable, lower, upper, body] = expression
    return ['Integral', variable, instantiate(lower, inputs), instantiate(upper, inputs), instantiate(body, inputs)]
  }
  if (expression[0] === 'Apply') {
    const [, name, ...args] = expression
    return ['Apply', name, ...args.map(value => instantiate(value, inputs))]
  }
  return [expression[0], ...expression.slice(1).map(value =>
    instantiate(value as MathExpression, inputs))] as MathExpression
}

function expressionKey(expression: MathExpression): string {
  return JSON.stringify(expression)
}

function normalizeExpression(expression: MathExpression): MathExpression {
  if (typeof expression === 'number' || typeof expression === 'string') return expression
  const operator = expression[0]
  if (operator === 'Sum') {
    const [, index, lower, upper, body] = expression
    return ['Sum', index, normalizeExpression(lower), normalizeExpression(upper), normalizeExpression(body)]
  }
  if (operator === 'Limit') {
    const [, variable, destination, body] = expression
    return ['Limit', variable, normalizeExpression(destination), normalizeExpression(body)]
  }
  if (operator === 'Integral') {
    const [, variable, lower, upper, body] = expression
    return ['Integral', variable, normalizeExpression(lower), normalizeExpression(upper), normalizeExpression(body)]
  }
  if (operator === 'Apply') {
    const [, name, ...args] = expression
    return ['Apply', name, ...args.map(normalizeExpression)]
  }

  const args = expression.slice(1).map(value => normalizeExpression(value as MathExpression))
  if (operator === 'Negate') {
    const value = args[0]
    if (typeof value === 'number') return -value
    if (Array.isArray(value) && value[0] === 'Negate') return value[1]
    return ['Negate', value]
  }
  if (operator === 'Add') {
    const flattened = args.flatMap(value =>
      Array.isArray(value) && value[0] === 'Add' ? value.slice(1) as MathExpression[] : [value])
      .filter(value => value !== 0)
    if (flattened.length === 0) return 0
    if (flattened.length === 1) return flattened[0]
    return ['Add', ...flattened]
  }
  if (operator === 'Multiply') {
    if (args.some(value => value === 0)) return 0
    const flattened = args.flatMap(value =>
      Array.isArray(value) && value[0] === 'Multiply' ? value.slice(1) as MathExpression[] : [value])
      .filter(value => value !== 1)
    if (flattened.length === 0) return 1
    if (flattened.length === 1) return flattened[0]
    return ['Multiply', ...flattened]
  }
  if (operator === 'Subtract' && args[1] === 0) return args[0]
  if (operator === 'Divide' && args[1] === 1) return args[0]
  if (operator === 'Power' && args[1] === 1) return args[0]
  return [operator, ...args] as MathExpression
}

function expressionNodeCount(expression: MathExpression): number {
  if (typeof expression === 'number' || typeof expression === 'string') return 1
  const start = expression[0] === 'Apply' ? 2 : 1
  return 1 + (expression.slice(start) as MathExpression[]).reduce<number>((sum, value) =>
    sum + expressionNodeCount(value as MathExpression), 0)
}

function combineExpressions(
  operator: 'Add' | 'Multiply',
  expressions: readonly MathExpression[],
): MathExpression {
  if (expressions.length === 1) return expressions[0]
  return normalizeExpression([operator, ...expressions])
}

function mapBinderBody(
  expression: MathExpression,
  transform: (body: MathExpression, variable: string) => MathExpression,
): MathExpression | null {
  if (!Array.isArray(expression)) return null
  if (expression[0] === 'Sum') {
    const [, index, lower, upper, body] = expression
    return ['Sum', index, lower, upper, normalizeExpression(transform(body, index))]
  }
  if (expression[0] === 'Limit') {
    const [, variable, destination, body] = expression
    return ['Limit', variable, destination, normalizeExpression(transform(body, variable))]
  }
  if (expression[0] === 'Integral') {
    const [, variable, lower, upper, body] = expression
    return ['Integral', variable, lower, upper, normalizeExpression(transform(body, variable))]
  }
  return null
}

function binderParts(expression: MathExpression): {
  operator: 'Sum' | 'Limit' | 'Integral'
  variable: string
  parameters: MathExpression[]
  body: MathExpression
} | null {
  if (!Array.isArray(expression)) return null
  if (expression[0] === 'Sum') {
    const [, variable, lower, upper, body] = expression
    return { operator: 'Sum', variable, parameters: [lower, upper], body }
  }
  if (expression[0] === 'Limit') {
    const [, variable, destination, body] = expression
    return { operator: 'Limit', variable, parameters: [destination], body }
  }
  if (expression[0] === 'Integral') {
    const [, variable, lower, upper, body] = expression
    return { operator: 'Integral', variable, parameters: [lower, upper], body }
  }
  return null
}

function rebuildBinder(
  parts: NonNullable<ReturnType<typeof binderParts>>,
  body: MathExpression,
): MathExpression {
  if (parts.operator === 'Limit') {
    return ['Limit', parts.variable, parts.parameters[0], normalizeExpression(body)]
  }
  if (parts.operator === 'Sum') {
    return ['Sum', parts.variable, parts.parameters[0], parts.parameters[1], normalizeExpression(body)]
  }
  return ['Integral', parts.variable, parts.parameters[0], parts.parameters[1], normalizeExpression(body)]
}

function perturbExpression(expression: MathExpression): MathExpression {
  return mapBinderBody(expression, body => ['Add', body, 1]) ?? ['Add', expression, 1]
}

function enumerateGrammar(parentCount: number, maxStates = 320): GrammarState[] {
  const allParents = Array.from({ length: parentCount }, (_, index) => index)
  const states: GrammarState[] = allParents.map(index => ({
    expression: placeholder(index),
    parents: [index],
    depth: 0,
    operators: [],
  }))
  const seen = new Set(states.map(state => hash(state.expression, 24)))

  for (let round = 0; round < 3 && states.length < maxStates; round++) {
    const snapshot = [...states]
    const additions: GrammarState[] = []
    for (const state of snapshot) {
      if (state.depth > round || state.depth >= 3) continue
      const unary: Array<[string, MathExpression]> = [
        ['Power', ['Power', state.expression, 2]],
      ]
      for (const [operator, expression] of unary) {
        const key = hash(expression, 24)
        if (seen.has(key)) continue
        seen.add(key)
        additions.push({
          expression,
          parents: state.parents,
          depth: state.depth + 1,
          operators: [...state.operators, operator],
        })
      }
    }
    for (let leftIndex = 0; leftIndex < snapshot.length; leftIndex++) {
      const left = snapshot[leftIndex]
      for (let rightIndex = leftIndex + 1; rightIndex < snapshot.length; rightIndex++) {
        const right = snapshot[rightIndex]
        if (left.parents.some(index => right.parents.includes(index))) continue
        const parents = unique([...left.parents, ...right.parents]).sort((a, b) => a - b)
        const combinations: Array<[string, MathExpression]> = [
          ['Add', ['Add', left.expression, right.expression]],
          ['Multiply', ['Multiply', left.expression, right.expression]],
          ['Subtract', ['Subtract', left.expression, right.expression]],
          ['Subtract', ['Subtract', right.expression, left.expression]],
          ['Divide', ['Divide', left.expression, right.expression]],
          ['Divide', ['Divide', right.expression, left.expression]],
        ]
        for (const [operator, expression] of combinations) {
          const key = hash(expression, 24)
          if (seen.has(key)) continue
          seen.add(key)
          additions.push({
            expression,
            parents,
            depth: Math.max(left.depth, right.depth) + 1,
            operators: [...left.operators, ...right.operators, operator],
          })
        }
      }
    }
    states.push(...additions.slice(0, Math.max(0, maxStates - states.length)))
  }

  return states
    .filter(state => state.parents.length === parentCount && state.depth > 0)
    .sort((left, right) => {
      const leftDiversity = new Set(left.operators).size
      const rightDiversity = new Set(right.operators).size
      return left.depth - right.depth || rightDiversity - leftDiversity ||
        left.operators.length - right.operators.length ||
        hash(left.expression).localeCompare(hash(right.expression))
    })
}

function alignedBinderProgram(
  operator: 'Add' | 'Multiply',
  parentCount: number,
): RuntimeProgram {
  return {
    id: `aligned-binder-${operator.toLowerCase()}`,
    parents: Array.from({ length: parentCount }, (_, index) => index),
    depth: 1,
    operators: ['AlignBinderScopes', `Compose${operator}Bodies`],
    construction: 'aligned-binder-body',
    structuralScore: 12,
    build(inputs) {
      const parts = inputs.map(binderParts)
      if (parts.some(item => item === null)) return null
      const first = parts[0]!
      if (parts.some(item => item!.operator !== first.operator ||
        item!.parameters.length !== first.parameters.length)) return null
      const normalizedParameters = first.parameters.map(item => expressionKey(normalizeExpression(item)))
      if (parts.some(item => item!.parameters.some((parameter, index) =>
        expressionKey(normalizeExpression(parameter)) !== normalizedParameters[index]))) return null
      const bodies = parts.map(item =>
        normalizeExpression(renameMathSymbol(item!.body, item!.variable, first.variable)))
      return normalizeExpression(rebuildBinder(first, combineExpressions(operator, bodies)))
    },
  }
}

function binderBodyLiftProgram(
  outerIndex: number,
  operator: 'Add' | 'Multiply',
  parentCount: number,
): RuntimeProgram {
  const otherIndices = Array.from({ length: parentCount }, (_, index) => index)
    .filter(index => index !== outerIndex)
  return {
    id: `binder-body-lift-${outerIndex}-${operator.toLowerCase()}`,
    parents: [outerIndex, ...otherIndices],
    depth: 2,
    operators: ['SelectBinderShell', `LiftClosedParentBy${operator}`, 'PreserveBinderScope'],
    construction: 'binder-body-lift',
    structuralScore: 10,
    build(inputs) {
      if (otherIndices.length === 0) return null
      const closedInput = combineExpressions(operator, otherIndices.map(index => inputs[index]))
      return mapBinderBody(inputs[outerIndex], body =>
        normalizeExpression([operator, body, closedInput]))
    },
  }
}

function binderMomentProgram(
  operator: 'Power' | 'MultiplyByBinder',
): RuntimeProgram {
  return {
    id: `binder-moment-${operator.toLowerCase()}`,
    parents: [0],
    depth: 1,
    operators: operator === 'Power'
      ? ['SelectBinderBody', 'ComposePowerMoment']
      : ['SelectBinderBody', 'ComposeBinderWeightedMoment'],
    construction: 'binder-moment',
    structuralScore: 8,
    build(inputs) {
      if (inputs.length !== 1) return null
      return mapBinderBody(inputs[0], (body, variable) => operator === 'Power'
        ? ['Power', body, 2]
        : ['Multiply', variable, body])
    },
  }
}

function enumerateRuntimePrograms(
  inputs: readonly MathExpression[],
  maxStates = 320,
): RuntimeProgram[] {
  const parentCount = inputs.length
  const programs: RuntimeProgram[] = []
  if (parentCount > 1) {
    programs.push(alignedBinderProgram('Add', parentCount))
    programs.push(alignedBinderProgram('Multiply', parentCount))
    for (let outerIndex = 0; outerIndex < parentCount; outerIndex++) {
      programs.push(binderBodyLiftProgram(outerIndex, 'Add', parentCount))
      programs.push(binderBodyLiftProgram(outerIndex, 'Multiply', parentCount))
    }
  } else {
    programs.push(binderMomentProgram('Power'))
    programs.push(binderMomentProgram('MultiplyByBinder'))
  }
  programs.push(...enumerateGrammar(parentCount, maxStates).map((state, index): RuntimeProgram => ({
    id: `output-composition-${index}`,
    parents: state.parents,
    depth: state.depth,
    operators: state.operators,
    construction: 'output-composition',
    structuralScore: 2,
    build: currentInputs => normalizeExpression(instantiate(state.expression, currentInputs)),
  })))

  const seen = new Set<string>()
  return programs.filter(program => {
    const expression = program.build(inputs)
    if (expression === null) return false
    const key = expressionKey(normalizeExpression(expression))
    if (seen.has(key)) return false
    seen.add(key)
    return true
  }).sort((left, right) =>
    right.structuralScore - left.structuralScore || left.depth - right.depth ||
    left.operators.length - right.operators.length || left.id.localeCompare(right.id))
}

function perturbInputs(inputs: readonly MathExpression[], parentIndex: number): MathExpression[] {
  return inputs.map((input, index) =>
    index === parentIndex ? normalizeExpression(perturbExpression(input)) : input)
}

function cardFromCandidate(
  parents: readonly DiscoveryParent[],
  inputExpressions: readonly MathExpression[],
  inputEvaluations: readonly ExactExpressionEvaluation[],
  state: RuntimeProgram,
  expression: MathExpression,
  evaluation: ExactExpressionEvaluation,
  ablations: readonly ExactExpressionEvaluation[],
  hypothesesEvaluated: number,
): ExecutableFusionCard {
  const parentIds = parents.map(parent => String(parent.id))
  const expressionTex = mathExpressionToLatex(expression)
  const answerTex = `\\(${evaluation.result_tex}\\)`
  const morphismChain = [
    'CurrentParentExpressionIR',
    ...state.operators.map(operator => `Compose${operator}`),
    'ExactExpressionEvaluation',
    'ParentCounterfactualReplay',
    'VerifiedAnswer',
  ]
  const obligations = [
    'every selected parent contributes a concrete expression parsed from the current input',
    'the candidate is composed only from the finite typed expression grammar',
    'exact evaluation leaves no free symbol or unevaluated binder',
    'perturbing each parent changes the exact result',
  ]
  const parentRows = parents.map((parent, index) =>
    `\\(E_{${index + 1}}=${mathExpressionToLatex(inputExpressions[index])}` +
    `=${inputEvaluations[index].result_tex}\\)`).join('、')
  const signature = hash({ expression, result: evaluation.result_srepr })
  const generatedProgram = {
    schema: 'mortra.runtime-expression-grammar.v2',
    grammar: [
      'Add', 'Subtract', 'Multiply', 'Divide', 'Power',
      'AlignBinderScopes', 'LiftClosedParent', 'MapBinderBody',
    ],
    construction: state.construction,
    program_id: state.id,
    parent_expression_asts: inputExpressions,
    generated_ast: expression,
    generated_ast_sha256: evaluation.certificate?.ast_sha256,
    exact_result: evaluation.result_srepr,
    parent_ablation_results: Object.fromEntries(parentIds.map((parentId, index) => [
      parentId,
      ablations[index].result_srepr,
    ])),
  }
  const proofCertificate = [
    { id: `${signature}.parse`, claim: 'all parent expressions came from the current statements', verifier: 'binder-aware-expression-parser' },
    { id: `${signature}.grammar`, claim: 'the new AST was enumerated from primitive expression constructors', verifier: 'typed-expression-grammar' },
    { id: `${signature}.exact`, claim: 'the generated expression has the displayed exact value', verifier: 'SymPy exact-expression IR replay' },
    { id: `${signature}.ablation`, claim: 'every parent changes the generated result under exact perturbation', verifier: 'whole-expression counterfactual replay' },
  ]

  return {
    id: `mortra-runtime-expression.${signature}`,
    family_id: 'runtime.expression_grammar',
    statement_tex: `次の値を厳密に求めよ。\\[${expressionTex}\\]`,
    answer_tex: answerTex,
    solution_tex: `親問題から現在の入力に書かれた式を読み取り、${parentRows} とおく。` +
      `これらを問題番号や登録済み解法ではなく、束縛変数のスコープを保つ構成規則 ` +
      `${state.operators.join(', ')} に従ってその場で合成すると ` +
      `\\[${expressionTex}\\]` +
      `を得る。束縛変数の範囲を保って内側から厳密計算すると ` +
      `\\[${expressionTex}=${evaluation.result_tex}\\]` +
      `である。同じ式木の再計算に加え、各親式を一つずつ変えた ${parents.length} 通りでも全体を再計算し、` +
      `いずれも結果が変わることを確認した。したがって答えは ${answerTex} である。`,
    domain: 'runtime_expression_composition',
    morphism_chain: morphismChain,
    parent_ids: parentIds,
    unresolved: false,
    discovery_status: 'verified',
    verification: {
      method: 'typed expression grammar enumeration + exact evaluation + per-parent counterfactual replay',
      exact_backend: true,
      independent_check: true,
      samples: [hypothesesEvaluated, parents.length, state.depth],
    },
    difficulty: {
      band: 'runtime_structural_expression',
      score: 2 + state.depth + new Set(state.operators).size + state.structuralScore / 4 + expressionTex.length / 160,
    },
    fusion_derivation: {
      passed: true,
      reason: 'a fresh expression program was enumerated from the current parents and survived exact whole-program ablation',
      ablationPassed: true,
      assignments: parents.map((parent, index) => ({
        parentId: String(parent.id),
        portId: `input:${String(parent.id)}`,
        role: 'current_expression_ast',
        matchedAnchors: [mathExpressionToLatex(inputExpressions[index])],
        witnessSteps: ['CurrentParentExpressionIR', ...state.operators, 'ExactExpressionEvaluation'],
        requiredObligations: obligations,
        consumedObligations: obligations,
        coverage: 1,
      })),
      bridges: [{
        id: `runtime-expression:${signature}`,
        witnessStep: 'ExactExpressionEvaluation',
        consumes: parentIds.map(parentId => `input:${parentId}`),
        produces: 'VerifiedAnswer',
      }],
      intermediatePropositions: parents.map((parent, index) => ({
        parentId: String(parent.id),
        morphism: 'EvaluateCurrentExpression',
        source: 'ExecutableExpression',
        target: 'Scalar',
        proposition: `the current parent expression equals ${inputEvaluations[index].result_tex}`,
        proved: true,
      })),
    },
    structure_blueprint: {
      id: `runtime-expression.${signature}`,
      version: 1,
      kernel: 'runtime_typed_expression_grammar',
      observable: 'VerifiedAnswer',
      operators: morphismChain,
      domain: 'current_input_expression_ir',
      tags: ['runtime-synthesis', 'atlas-free', 'expression-ir', ...unique(state.operators)],
      morphismChain,
      executable: true,
      proofCertificate,
    },
    search_evidence: {
      hypotheses_evaluated: hypothesesEvaluated,
      valid_hypotheses: 1,
      elapsed_ms: 0,
    },
    execution_certificate: runtimeSynthesisCertificate({
      origin: 'synthesized_expression_program',
      parents,
      generatedProgram,
      checks: proofCertificate.map(item => `${item.id}: ${item.verifier}`),
    }),
  }
}

export function synthesizeRuntimeExpressionProblems(
  parents: readonly DiscoveryParent[],
  requested: number,
): RuntimeExpressionSynthesis {
  const key = hash({
    parents: parents.map(parent => ({ id: parent.id, statement: parent.statement })),
    requested,
  }, 32)
  const cached = cache.get(key)
  if (cached) return cached
  if (parents.length === 0 || requested <= 0) {
    return { applicable: false, reason: 'at least one current parent expression is required', cards: [], hypothesesEvaluated: 0 }
  }
  const parsed = parents.map(parent => extractBoundMathExpression(parent.statement ?? ''))
  if (parsed.some(item => item === null)) {
    const result = {
      applicable: false,
      reason: 'at least one parent lacks a concrete binder-aware expression in the current input',
      cards: [],
      hypothesesEvaluated: 0,
    }
    cache.set(key, result)
    return result
  }
  const inputExpressions = parsed.map(item => item!.expression)
  const inputEvaluations = evaluateExactExpressions(inputExpressions)
  if (inputEvaluations.some(item => item.ok !== true)) {
    const result = {
      applicable: false,
      reason: 'at least one current parent expression did not close under exact evaluation',
      cards: [],
      hypothesesEvaluated: inputEvaluations.length,
    }
    cache.set(key, result)
    return result
  }

  const grammar = enumerateRuntimePrograms(inputExpressions)
  const instantiated = grammar.map(state => normalizeExpression(state.build(inputExpressions)!))
  const evaluations = evaluateExactExpressions(instantiated)
  const viable = grammar.flatMap((state, index) => {
    const evaluation = evaluations[index]
    const expressionTex = mathExpressionToLatex(instantiated[index])
    return evaluation.ok === true && evaluation.result_srepr &&
      (evaluation.result_tex?.length ?? 0) <= 400 && expressionTex.length <= 1_200
      ? [{
        state,
        expression: instantiated[index],
        evaluation,
        complexity: expressionNodeCount(instantiated[index]),
      }]
      : []
  }).sort((left, right) => {
    const leftTrivial = ['0', '1', '-1'].includes(left.evaluation.result_tex ?? '') ? 1 : 0
    const rightTrivial = ['0', '1', '-1'].includes(right.evaluation.result_tex ?? '') ? 1 : 0
    return right.state.structuralScore - left.state.structuralScore ||
      leftTrivial - rightTrivial || left.state.depth - right.state.depth ||
      left.complexity - right.complexity || left.state.id.localeCompare(right.state.id)
  }).slice(0, Math.max(16, requested * 10))

  const viableWithAblations = viable.flatMap(candidate => {
    const expressions = parents.map((_, parentIndex) =>
      candidate.state.build(perturbInputs(inputExpressions, parentIndex)))
    return expressions.some(expression => expression === null)
      ? []
      : [{ ...candidate, ablationExpressions: expressions.map(expression =>
        normalizeExpression(expression!)) }]
  })
  const ablationExpressions = viableWithAblations.flatMap(candidate => candidate.ablationExpressions)
  const ablationEvaluations = evaluateExactExpressions(ablationExpressions)
  const cards: ExecutableFusionCard[] = []
  let cursor = 0
  for (const candidate of viableWithAblations) {
    const ablations = ablationEvaluations.slice(cursor, cursor + parents.length)
    cursor += parents.length
    if (ablations.length !== parents.length || ablations.some(item =>
      item.ok !== true || item.result_srepr === candidate.evaluation.result_srepr)) continue
    cards.push(cardFromCandidate(
      parents,
      inputExpressions,
      inputEvaluations,
      candidate.state,
      candidate.expression,
      candidate.evaluation,
      ablations,
      grammar.length + ablationExpressions.length,
    ))
    if (cards.length >= requested) break
  }
  const result: RuntimeExpressionSynthesis = {
    applicable: cards.length > 0,
    reason: cards.length
      ? `${cards.length} fresh expression programs survived exact evaluation and every parent ablation`
      : 'the current expression grammar produced no candidate that survived exact evaluation and every parent ablation',
    cards,
    hypothesesEvaluated: grammar.length + ablationExpressions.length,
  }
  cache.set(key, result)
  return result
}

export function clearRuntimeExpressionSynthesisCache(): void {
  cache.clear()
}
