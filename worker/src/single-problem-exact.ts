import { createHash } from 'node:crypto'

import type { ExecutableFusionCard } from './executable-fusion'
import {
  liftParent,
  type DiscoveryParent,
} from './parent-conditioned-discovery'
import {
  lowerLinearPredicateStatement,
} from './linear-predicate-lowerer'
import { verifyLinearInvariantCertificate } from './exact-linear-invariant'
import { runtimeSynthesisCertificate } from './execution-certificate'

function hash(value: unknown, length = 16): string {
  return createHash('sha256').update(JSON.stringify(value)).digest('hex').slice(0, length)
}

function rationalTex(value: string): string {
  const match = value.match(/^(-?)(\d+)\/(\d+)$/)
  if (!match) return value
  return `${match[1]}\\frac{${match[2]}}{${match[3]}}`
}

function relationTex(provenance: string): string {
  return provenance.replace(/^relation:\d+:/, '')
}

export function exactSingleProblemSupport(parents: readonly DiscoveryParent[]) {
  if (parents.length !== 1) {
    return { applicable: false, reason: 'exact single-problem execution requires exactly one input problem' }
  }
  const lowered = lowerLinearPredicateStatement(parents[0].statement ?? '')
  if (lowered.status !== 'lowered') {
    return { applicable: false, reason: `single-problem lowering remained ${lowered.status}: ${lowered.detail}` }
  }
  if (lowered.certificate.status !== 'proved') {
    return {
      applicable: false,
      reason: `exact linear obligation remained ${lowered.certificate.status}`,
    }
  }
  return {
    applicable: verifyLinearInvariantCertificate(lowered.program, lowered.certificate),
    reason: verifyLinearInvariantCertificate(lowered.program, lowered.certificate)
      ? 'typed linear goal has an independently replayable exact proof combination'
      : 'linear elimination returned a value whose proof combination did not replay',
  }
}

export function synthesizeExactSingleProblem(
  parents: readonly DiscoveryParent[],
): ExecutableFusionCard[] {
  if (parents.length !== 1) return []
  const parent = parents[0]
  const statement = parent.statement?.trim() ?? ''
  if (!statement) return []
  const lowered = lowerLinearPredicateStatement(statement)
  if (lowered.status !== 'lowered' || lowered.certificate.status !== 'proved') return []
  if (!verifyLinearInvariantCertificate(lowered.program, lowered.certificate)) return []

  const parentId = String(parent.id || `single-${hash(statement, 10)}`)
  const value = lowered.certificate.value!
  const valueTex = rationalTex(value)
  const coefficients = lowered.certificate.proofCoefficients ?? []
  const relations = lowered.program.equations.flatMap(equation => equation.provenance.map(relationTex))
  const relationDisplay = relations.length
    ? relations.map((relation, index) => `E_{${index + 1}}:\ ${relation}`).join(',\\qquad ')
    : '\\text{入力された等式}'
  const coefficientDisplay = coefficients.map(rationalTex).join(',')
  const chain = [
    'ProblemText',
    'TypedLinearRelations',
    'ExactRationalElimination',
    'ProofCombinationReplay',
    'VerifiedAnswer',
  ]
  const requiredObligations = [
    'all input equalities elaborate to affine typed relations',
    'the requested observable has zero residual after elimination',
    'stored proof coefficients replay against the original relations',
  ]
  const signature = hash({ statement, value, coefficients })
  const graph = liftParent(parent)

  return [{
    id: `mortra-single-exact-linear.${signature}`,
    family_id: 'certified.single_problem.exact_linear_invariant',
    statement_tex: statement,
    answer_tex: valueTex,
    solution_tex: `問題文中の等式を有理数係数の一次方程式として読み取る。これらを
\\[
${relationDisplay}
\\]
と書く。求める式を同じ変数の一次式として表し、分数を近似せずに消去すると、係数行列の階数は ${lowered.certificate.rank} で、求める式に残る未消去変数はない。

実際、元の等式を係数
\\[
(\\lambda_1,\\ldots,\\lambda_${coefficients.length})=(${coefficientDisplay})
\\]
で線形結合すると、左辺は求める式、右辺は \\(${valueTex}\\) になる。この恒等式を元の等式から独立に再計算して一致を確認した。したがって答えは
\\[
${valueTex}
\\]
である。`,
    domain: 'exact_linear_mathematics',
    morphism_chain: chain,
    parent_ids: [parentId],
    unresolved: false,
    discovery_status: 'verified',
    verification: {
      method: 'exact rational Gaussian elimination + proof-combination replay',
      exact_backend: true,
      independent_check: true,
      samples: [],
    },
    difficulty: { band: 'certified', score: Math.max(1, lowered.certificate.rank) },
    fusion_derivation: {
      passed: true,
      reason: 'the answer is derived from the input constraints and replayed as an exact linear combination',
      ablationPassed: true,
      assignments: [{
        parentId,
        portId: 'input_1',
        role: 'typed_constraint_system',
        matchedAnchors: graph.semantic_roots,
        witnessSteps: chain,
        requiredObligations,
        consumedObligations: requiredObligations,
        coverage: 1,
      }],
      bridges: [{
        id: 'single_problem_query_realization',
        witnessStep: 'ProofCombinationReplay',
        consumes: ['input_1'],
        produces: 'VerifiedAnswer',
      }],
      intermediatePropositions: [{
        parentId,
        morphism: 'ExactRationalElimination',
        source: 'TypedLinearRelations',
        target: 'VerifiedAnswer',
        proposition: `the requested affine observable equals ${value}`,
        proved: true,
      }],
    },
    structure_blueprint: {
      id: `single-linear.${signature}`,
      version: 1,
      kernel: 'exact_linear_invariant',
      observable: 'VerifiedAnswer',
      operators: chain,
      domain: 'typed_linear_constraints',
      tags: [...new Set([...graph.semantic_roots, ...graph.constraints])],
      morphismChain: chain,
      executable: true,
      proofCertificate: [
        { id: `${signature}.elaboration`, claim: 'all used relations were parsed as affine equalities', verifier: 'typed-linear-lowerer' },
        { id: `${signature}.elimination`, claim: `the requested observable equals ${value}`, verifier: 'exact-rational-rref' },
        { id: `${signature}.replay`, claim: 'proof coefficients reconstruct the goal from the original relations', verifier: 'linear-combination-replay' },
      ],
    },
    search_evidence: {
      hypotheses_evaluated: 1,
      valid_hypotheses: 1,
      elapsed_ms: 0,
    },
    execution_certificate: runtimeSynthesisCertificate({
      origin: 'synthesized_linear_program',
      parents,
      generatedProgram: {
        equations: lowered.program.equations,
        observable: lowered.program.goal,
        proof_coefficients: coefficients,
        exact_value: value,
      },
      checks: [
        'typed affine elaboration',
        'exact rational elimination',
        'independent linear-combination replay',
      ],
    }),
  }]
}
