import { writeFileSync } from 'node:fs'
import path from 'node:path'
import { performance } from 'node:perf_hooks'
import { synthesizeCertifiedPolynomialFusions } from '../lib/mortra/certified-fusion'

const polynomials = [
  'x^2-2',
  'x^2+x-3',
  'x^2-2x-5',
  'x^3-x-1',
  'x^3+x^2-2',
  'x^3-2x^2+x-4',
  'x^4-x-1',
  'x^4+x^2-3',
  'x^4-2x^2+x-2',
  'x^3+2x+5',
  'x^2+3x+1',
  'x^4+x^3-x+1',
]

const started = performance.now()
let endpointPairs = 0
let generated = 0
let verified = 0
let parentAblationPassed = 0
const structureIds = new Set<string>()
const failures: Array<{ left: string; right: string; generated: number }> = []

for (let leftIndex = 0; leftIndex < polynomials.length; leftIndex += 1) {
  for (let rightIndex = leftIndex + 1; rightIndex < polynomials.length; rightIndex += 1) {
    endpointPairs += 1
    const cards = synthesizeCertifiedPolynomialFusions([
      { id: `p${leftIndex}`, statement: `方程式 $${polynomials[leftIndex]}=0$ の根を考える。` },
      { id: `p${rightIndex}`, statement: `方程式 $${polynomials[rightIndex].replace(/x/g, 'y')}=0$ の根を考える。` },
    ], 3)
    generated += cards.length
    verified += cards.filter(card => card.verification.exact_backend && card.verification.independent_check).length
    parentAblationPassed += cards.filter(card =>
      card.fusion_derivation.ablationPassed &&
      card.fusion_derivation.assignments.length === 2 &&
      card.fusion_derivation.bridges.every(bridge => bridge.consumes.length === 2),
    ).length
    cards.forEach(card => structureIds.add(card.structure_blueprint.id))
    if (cards.length !== 3) failures.push({
      left: polynomials[leftIndex],
      right: polynomials[rightIndex],
      generated: cards.length,
    })
  }
}

const unsupportedInputs = [
  '三角形ABCの内心と外心の関係を証明せよ。',
  '自然数nについて最大公約数を求めよ。',
  '関数fの定積分を求めよ。',
  '確率変数Xの分散を求めよ。',
  '複素平面上の軌跡を求めよ。',
  '行列Aの固有値を求めよ。',
  '位相空間XのEuler標数を求めよ。',
  '数列a_nの極限を求めよ。',
  '円と接線の交点を求めよ。',
  '不等式を証明せよ。',
  '素数pについて合同式を示せ。',
  '立体の切断面積を求めよ。',
]
let falseAccepts = 0
for (const [index, statement] of unsupportedInputs.entries()) {
  const cards = synthesizeCertifiedPolynomialFusions([
    { id: `supported-${index}`, statement: '方程式 $x^2-2=0$ の根を考える。' },
    { id: `unsupported-${index}`, statement },
  ], 3)
  falseAccepts += cards.length
}

const report = {
  schema: 1,
  experiment: 'public-certified-polynomial-fusion-generalization',
  date: '2026-08-27',
  external_llm_used: false,
  problem_ids_used_for_branching: false,
  coefficient_templates: polynomials.length,
  endpoint_pairs: endpointPairs,
  requested_candidates: endpointPairs * 3,
  generated_candidates: generated,
  generation_rate: generated / (endpointPairs * 3),
  two_path_verified: verified,
  two_path_verification_rate: generated ? verified / generated : 0,
  all_parent_ablation_passed: parentAblationPassed,
  all_parent_ablation_rate: generated ? parentAblationPassed / generated : 0,
  structurally_unique_candidates: structureIds.size,
  unsupported_endpoint_pairs: unsupportedInputs.length,
  false_accepts: falseAccepts,
  failures,
  elapsed_ms: Number((performance.now() - started).toFixed(2)),
  verification_routes: [
    'exact BigInt Newton power sums',
    'independent BigInt Sylvester resultant',
  ],
}

const output = path.resolve(process.cwd(), 'data', 'product-certified-fusion-benchmark-2026-08-27.json')
writeFileSync(output, `${JSON.stringify(report, null, 2)}\n`, 'utf8')
process.stdout.write(`${JSON.stringify(report, null, 2)}\n`)
