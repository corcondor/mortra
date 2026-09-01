import assert from 'node:assert/strict'
import test from 'node:test'
import { evaluateBenchmarkRequest } from './benchmark-bridge'

test('benchmark bridge separates type reachability from exact execution', () => {
  const result = evaluateBenchmarkRequest({
    id: 'unseen-linear-case',
    statement: '実数 $x,y$ は $x+y=19$, $y=4$ を満たす。$x$ を求めよ。',
    compact: true,
  })
  assert.ok(['goal_reached', 'goal_unreached'].includes(result.status))
  assert.equal(result.execution.status, 'lowered')
  assert.equal(result.execution_proof_status, 'certified')
  if (result.execution.status !== 'lowered') return
  assert.equal(result.execution.certificate.status, 'proved')
  assert.equal(result.execution.certificate.value, '15')
})

test('benchmark bridge never calls mere type reach an executed solution', () => {
  const result = evaluateBenchmarkRequest({
    id: 'nonlinear-case',
    statement: '実数 $x,y$ は $x\\cdot y=6$ を満たす。$x$ を求めよ。',
    compact: true,
  })
  assert.notEqual(result.execution.status, 'lowered')
  assert.equal(result.execution_proof_status, 'unproved')
})

test('benchmark bridge does not mistake a standalone number for the requested answer', () => {
  const result = evaluateBenchmarkRequest({
    id: 'combinatorics-prose',
    statement: 'A board has $36$ cells. Determine the number of valid colourings.',
    compact: true,
  })
  assert.notEqual(result.execution.status, 'lowered')
  assert.equal(result.execution_proof_status, 'unproved')
})
