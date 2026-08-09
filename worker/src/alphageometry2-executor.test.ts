import assert from 'node:assert/strict'
import test from 'node:test'
import { spawnSync } from 'node:child_process'
import { resolve } from 'node:path'
import { executeAlphaGeometry2 } from './alphageometry2-executor'

test('official AlphaGeometry2 DDAR checkout proves formalized problems without answer leakage', {
  skip: !process.env.MATHOS_AG2_DIR,
}, () => {
  const adapter = resolve(__dirname, '..', 'backend', 'alphageometry2_adapter.py')
  const result = spawnSync(process.platform === 'win32' ? 'python' : 'python3', [
    adapter,
    '--engine-dir', process.env.MATHOS_AG2_DIR!,
    '--official-suite',
    '--limit', '2',
  ], { encoding: 'utf8', timeout: 120_000 })
  assert.equal(result.status, 0, result.stderr)
  const report = JSON.parse(result.stdout)
  assert.equal(report.total, 2)
  assert.equal(report.proved, 2)
})

test('finite typed search discovers an auxiliary intersection without an LLM', {
  skip: !process.env.MATHOS_AG2_DIR,
}, () => {
  const problem = [
    'a@0_0 = ',
    'b@4_0 = ',
    'c@1_3 = ',
    'd@1_1 = perp b d a c, perp c d a b ? perp a d b c',
  ].join('; ')
  const result = executeAlphaGeometry2(problem, {
    searchAuxiliary: true,
    maxDepth: 1,
    beamWidth: 8,
    maxAttempts: 32,
  })
  assert.equal(result.proved, true, result.error)
  assert.equal(result.baseline_proved, false)
  assert.equal(result.uses_language_model, false)
  assert.equal(result.proposal_engine, 'finite_typed_construction_grammar')
  assert.ok(result.constructions?.some(item => item.kind === 'line_intersection'))
})

test('auxiliary search is invariant under a similarity coordinate change', {
  skip: !process.env.MATHOS_AG2_DIR,
}, () => {
  const configurations = [
    ['2_-1', '10_-1', '4_5', '4_1'],
    ['3_4', '3_8', '0_5', '2_5'],
    ['-2_7', '-14_7', '-5_-2', '-5_4'],
    ['1_1', '3_1', '1.5_2.5', '1.5_1.5'],
  ]
  for (const [a, b, c, d] of configurations) {
    const problem = [
      `a@${a} = `,
      `b@${b} = `,
      `c@${c} = `,
      `d@${d} = perp b d a c, perp c d a b ? perp a d b c`,
    ].join('; ')
    const result = executeAlphaGeometry2(problem, {
      searchAuxiliary: true,
      maxDepth: 1,
      beamWidth: 8,
      maxAttempts: 32,
    })
    assert.equal(result.proved, true, result.error)
    assert.equal(result.baseline_proved, false)
    assert.ok(result.constructions?.some(item => item.kind === 'line_intersection'))
    assert.equal(result.attempt_trace?.at(-1)?.status, 'proved')
  }
})

test('auxiliary search does not turn a false goal into a proof', {
  skip: !process.env.MATHOS_AG2_DIR,
}, () => {
  const problem = [
    'a@0_0 = ',
    'b@4_0 = ',
    'c@1_3 = ',
    'd@1_1 = perp b d a c, perp c d a b ? para a d b c',
  ].join('; ')
  const result = executeAlphaGeometry2(problem, {
    searchAuxiliary: true,
    maxDepth: 1,
    beamWidth: 8,
    maxAttempts: 32,
  })
  assert.equal(result.proved, false)
  assert.equal(result.status, 'unproved')
  assert.equal(result.baseline_proved, false)
})
