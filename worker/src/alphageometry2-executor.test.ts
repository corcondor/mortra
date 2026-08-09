import assert from 'node:assert/strict'
import test from 'node:test'
import { spawnSync } from 'node:child_process'
import { resolve } from 'node:path'

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
