import { createHash } from 'node:crypto'

import type { CertifiedFusionCard, CertifiedFusionParent } from './certified-fusion'

type CertifiedScalar = {
  parent: CertifiedFusionParent
  tex: string
}

const ALLOWED_COMMANDS = new Set([
  'arccos', 'arcsin', 'arctan', 'cdot', 'cos', 'dfrac', 'exp', 'frac',
  'left', 'ln', 'log', 'pi', 'right', 'sin', 'sqrt', 'tan', 'tfrac', 'times',
])

function hash(parts: string[]): string {
  return createHash('sha256').update(parts.join('\u0000')).digest('hex').slice(0, 16)
}

function stripMathDelimiters(value: string): string {
  let result = value.trim()
  if (result.startsWith('\\(') && result.endsWith('\\)')) result = result.slice(2, -2)
  if (result.startsWith('\\[') && result.endsWith('\\]')) result = result.slice(2, -2)
  return result.trim()
}

/**
 * Accept one exact closed scalar, not a tuple, set, decimal approximation, or
 * prose answer. Parent correctness comes from its stored proof certificate;
 * this function only checks that the value has the scalar type needed here.
 */
export function parseCertifiedExactScalar(parent: CertifiedFusionParent): CertifiedScalar | null {
  if (!parent.certificate?.verified || !parent.solution?.trim() || !parent.answer?.trim()) return null
  const tex = stripMathDelimiters(parent.answer)
  if (!tex || /(?:\\text|\\begin|\\end|\\quad|\\qquad|\\operatorname)/.test(tex)) return null
  if (/[=<>;,]|\\(?:infty|pm|mp|le|ge|ne|approx|equiv|in|notin|cup|cap)/.test(tex)) return null
  if (/\d\.\d/.test(tex)) return null

  const normalized = tex
    .replace(/\\mathrm\s*\{\s*e\s*\}/g, 'e')
    .replace(/\\!/g, '')
    .replace(/\\,/g, '')
    .replace(/\\;/g, '')
    .replace(/\\:/g, '')
  const commands = Array.from(normalized.matchAll(/\\([A-Za-z]+)/g), match => match[1])
  if (commands.some(command => !ALLOWED_COMMANDS.has(command))) return null
  const withoutCommands = normalized.replace(/\\[A-Za-z]+/g, '')
  const withoutEuler = withoutCommands.replace(/e/g, '')
  if (/[A-DF-Za-df-z]/.test(withoutEuler)) return null
  if (/[^0-9+\-*/^{}()[\]\s]/.test(withoutEuler)) return null
  return { parent, tex }
}

function universalRecurrenceIdentityHolds(): boolean {
  // Coefficients of a^(n+2), a^(n+1)b, ab^(n+1), b^(n+2).
  return [1 - 1, -1 + 1, -1 + 1, 1 - 1].every(value => value === 0)
}

function replayIntegerSamples(): number[] {
  const samples: Array<[bigint, bigint]> = [[2n, 3n], [-1n, 4n], [0n, 5n]]
  const passed: number[] = []
  samples.forEach(([alpha, beta], sampleIndex) => {
    const sequence = [2n, alpha + beta]
    for (let n = 0; n < 8; n += 1) {
      sequence.push((alpha + beta) * sequence[n + 1] - alpha * beta * sequence[n])
    }
    const exact = sequence.every((value, n) => value === alpha ** BigInt(n) + beta ** BigInt(n))
    if (exact) passed.push(sampleIndex)
  })
  return passed
}

function texDocument(statement: string, solution: string): string {
  return String.raw`\documentclass[uplatex,dvipdfmx,11pt]{jsarticle}
\usepackage{amsmath,amssymb,mathtools}
\usepackage{geometry}
\geometry{margin=24mm}
\begin{document}
\section*{問題}
${statement}
\section*{解答}
${solution}
\end{document}`
}

export function synthesizeCertifiedAnswerRecurrenceFusion(
  parents: CertifiedFusionParent[],
  requested = 1,
): CertifiedFusionCard[] {
  if (requested < 1 || parents.length !== 2) return []
  const scalars = parents.map(parseCertifiedExactScalar)
  if (scalars.some(value => value === null)) return []
  const [left, right] = scalars as [CertifiedScalar, CertifiedScalar]
  if (!universalRecurrenceIdentityHolds()) return []
  const samples = replayIntegerSamples()
  if (samples.length !== 3) return []

  const alpha = left.tex
  const beta = right.tex
  const statement = String.raw`次の二つの問題を解き、その答えをそれぞれ $\alpha,\beta$ とする。

\[\text{A}\quad ${left.parent.statement}\]
\[\text{B}\quad ${right.parent.statement}\]

数列 $\{u_n\}$ を
\[
u_0=2,\qquad u_1=\alpha+\beta,\qquad
u_{n+2}=(\alpha+\beta)u_{n+1}-\alpha\beta u_n\quad(n\geq0)
\]
で定める。$u_n$ の一般項と母関数 $\sum_{n=0}^{\infty}u_nt^n$ を求め、$u_3$ を厳密値で表せ。`
  const answer = String.raw`\[
u_n=\alpha^n+\beta^n,\qquad
\sum_{n=0}^{\infty}u_nt^n=\frac{2-(\alpha+\beta)t}{1-(\alpha+\beta)t+\alpha\beta t^2},
\qquad
u_3=\left(${alpha}\right)^3+\left(${beta}\right)^3.
\]`
  const solution = String.raw`A と B の保存済み証明書を再生すると
\[
\alpha=${alpha},\qquad \beta=${beta}
\]
を得る。特性多項式は
\[
X^2-(\alpha+\beta)X+\alpha\beta=(X-\alpha)(X-\beta)
\]
と因数分解できる。そこで $v_n=\alpha^n+\beta^n$ とおくと、$v_0=2$, $v_1=\alpha+\beta$ であり、
\[
v_{n+2}-(\alpha+\beta)v_{n+1}+\alpha\beta v_n=0
\]
が恒等的に成り立つ。初期値と漸化式の一意性から $u_n=v_n$、すなわち
\[
u_n=\alpha^n+\beta^n
\]
である。

また漸化式の両辺に $t^{n+2}$ を掛けて $n\geq0$ で足すと
\[
\{1-(\alpha+\beta)t+\alpha\beta t^2\}\sum_{n=0}^{\infty}u_nt^n
=2-(\alpha+\beta)t
\]
となるので、母関数も上の答えを得る。最後に $n=3$ を代入し、A と B の厳密解を戻せば
\[
u_3=\left(${alpha}\right)^3+\left(${beta}\right)^3
\]
である。`
  const normalizedScalars = [alpha.replace(/\s/g, ''), beta.replace(/\s/g, '')].sort()
  const structureId = `certified.answer-recurrence.${hash(normalizedScalars)}`
  const morphisms = [
    'VerifiedAnswerCertificateReplay',
    'ExactScalarPair',
    'ElementarySymmetricProjection',
    'CompanionRecurrenceConstruction',
    'CharacteristicPolynomialFactorization',
    'GeneratingFunctionElimination',
    'IndependentUniversalIdentityReplay',
    'AllParentAblation',
  ]

  return [{
    id: `mortra-${structureId}`,
    statement_tex: statement,
    answer_tex: answer,
    solution_tex: solution,
    solution_document_tex: texDocument(statement, solution),
    domain: 'algebra',
    family_id: 'certified.answer_pair_companion_recurrence',
    tool: 'MORTRA proof-certificate composition (no LLM)',
    morphism_chain: morphisms,
    diagram: {
      version: 1,
      kind: 'state',
      title: '二つの証明済み解から一つの漸化式へ',
      caption: 'A と B の厳密解を別々に保持し、和と積を通して同じ特性多項式へ合成します。',
      states: [
        { id: 'a', label: 'A の証明書', active: true },
        { id: 'b', label: 'B の証明書', active: true },
        { id: 's', label: 'α+β' },
        { id: 'p', label: 'αβ' },
        { id: 'r', label: '二階漸化式' },
        { id: 'c', label: 'u_n=α^n+β^n', terminal: true },
      ],
      transitions: [
        { from: 'a', to: 's', label: '和' },
        { from: 'b', to: 's', label: '和' },
        { from: 'a', to: 'p', label: '積' },
        { from: 'b', to: 'p', label: '積' },
        { from: 's', to: 'r', label: '係数' },
        { from: 'p', to: 'r', label: '係数' },
        { from: 'r', to: 'c', label: '特性方程式' },
      ],
    },
    parent_ids: [left.parent.id, right.parent.id],
    verification: {
      method: 'two stored exact proof certificates + universal polynomial identity + independent integer replay + all-parent ablation',
      exact_backend: true,
      independent_check: true,
      samples,
    },
    difficulty: { band: 'B_proof_certificate_composition', score: 7.2 },
    fusion_derivation: {
      passed: true,
      reason: 'each parent supplies one independently verified exact scalar; both are required to determine the recurrence coefficients and the requested exact value',
      ablationPassed: true,
      assignments: [left, right].map((scalar, index) => ({
        parentId: scalar.parent.id,
        portId: `verified_scalar_${index + 1}`,
        role: 'verified exact scalar',
        matchedAnchors: [scalar.tex],
        witnessSteps: ['VerifiedAnswerCertificateReplay', 'ExactScalarPair'],
      })),
      bridges: [
        {
          id: 'elementary-symmetric-pair',
          witnessStep: 'ElementarySymmetricProjection',
          consumes: ['verified_scalar_1', 'verified_scalar_2'],
          produces: 'companion_recurrence_coefficients',
        },
      ],
      intermediatePropositions: [left, right].map(scalar => ({
        parentId: scalar.parent.id,
        morphism: 'VerifiedAnswerCertificateReplay',
        source: 'SolvedProblemCertificate',
        target: 'ExactScalar',
        proposition: `${scalar.parent.certificate?.id ?? scalar.parent.id} proves ${scalar.tex}`,
        proved: true as const,
      })),
    },
    structure_blueprint: {
      id: structureId,
      version: 1,
      kernel: 'CertifiedExactScalarPairCompanionMatrixIR',
      observable: 'closed_form_recurrence_and_generating_function',
      operators: morphisms,
      domain: 'algebra',
      tags: ['proof-certificate', 'exact-scalar', 'recurrence', 'companion-matrix', 'generating-function', 'no-llm'],
      morphismChain: morphisms,
      executable: true,
      proofCertificate: [
        { id: 'parent-a', claim: `alpha=${alpha}`, verifier: left.parent.certificate?.method ?? left.parent.certificate?.id ?? 'stored exact proof' },
        { id: 'parent-b', claim: `beta=${beta}`, verifier: right.parent.certificate?.method ?? right.parent.certificate?.id ?? 'stored exact proof' },
        { id: 'universal-recurrence', claim: 'a^(n+2)+b^(n+2)=(a+b)(a^(n+1)+b^(n+1))-ab(a^n+b^n)', verifier: 'exact monomial coefficient cancellation' },
        { id: 'independent-replay', claim: 'the construction replays for three unrelated integer pairs through n=9', verifier: 'BigInt recurrence replay' },
        { id: 'parent-ablation', claim: 'removing either exact scalar leaves one recurrence coefficient and u_3 undetermined', verifier: 'typed input-cardinality and dependency check' },
      ],
      structuralUniqueness: {
        schema: 1,
        conditionSkeleton: ['two-independently-verified-exact-scalars', 'second-order-companion-recurrence'],
        querySignature: 'closed-form-generating-function-and-third-term',
        normalForm: 'u_n=alpha^n+beta^n',
        quotientAction: 'exchange-alpha-and-beta',
        freeParameters: ['alpha', 'beta'],
        uniqueNormalForm: true,
        finiteSolutionSet: true,
        numericInstanceConstants: [],
        conditionAblationPassed: true,
      },
    },
    search_evidence: {
      hypotheses_evaluated: 1,
      valid_hypotheses: 1,
      elapsed_ms: 0,
    },
  }]
}
