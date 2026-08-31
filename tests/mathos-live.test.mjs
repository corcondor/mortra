import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import test from 'node:test'
import { fileURLToPath, pathToFileURL } from 'node:url'

const repoRoot = dirname(dirname(fileURLToPath(import.meta.url)))
const scratchDir = mkdtempSync(join(tmpdir(), 'mathos-live-'))
const sourceDir = join(scratchDir, 'lib')
const mortraDir = join(sourceDir, 'mortra')
const compiledDir = join(scratchDir, 'out', 'lib')
mkdirSync(mortraDir, { recursive: true })
const entry = join(sourceDir, 'mathos-live.ts')
writeFileSync(entry, readFileSync(join(repoRoot, 'lib', 'mathos-live.ts'), 'utf8'), 'utf8')
writeFileSync(
  join(mortraDir, 'calculus-analysis.ts'),
  readFileSync(join(repoRoot, 'lib', 'mortra', 'calculus-analysis.ts'), 'utf8'),
  'utf8',
)
execFileSync(
  process.execPath,
  [
    join(repoRoot, 'node_modules', 'typescript', 'bin', 'tsc'),
    entry, join(mortraDir, 'calculus-analysis.ts'),
    '--target', 'es2022', '--module', 'commonjs',
    '--moduleResolution', 'node', '--skipLibCheck',
    '--outDir', join(scratchDir, 'out'), '--rootDir', scratchDir,
  ],
  { cwd: repoRoot, stdio: 'pipe' },
)
const mathos = await import(pathToFileURL(join(compiledDir, 'mathos-live.js')).href)

test('解析タグを指定すると積分状態列と不等式制約を接続する', () => {
  const problem = mathos.generateLiveProblem({
    domain: 'analysis',
    focusTags: ['integral', 'recurrence', 'inequality', 'limit', 'asymptotic'],
    preferDepth: true,
  })

  assert.ok(problem)
  assert.equal(problem.familyId, 'runtime.integral_state.endpoint_squeeze')
  assert.match(problem.statementTex, /\\int_0\^1/)
  assert.match(problem.statementTex, /\\lim_\{n\\to\\infty\}/)

  const contract = problem.structureBlueprint?.fusionContract
  assert.ok(contract)
  assert.deepEqual(
    contract.ports.map(port => port.id),
    ['integral_state_dynamics', 'order_control'],
  )
  assert.deepEqual(
    contract.bridges[0].consumes,
    ['integral_state_dynamics', 'order_control'],
  )
  for (const port of contract.ports) {
    for (const witness of port.witnessSteps) {
      assert.ok(problem.morphismChain.includes(witness), `${witness} が証明射列にない`)
    }
  }
  assert.ok(problem.morphismChain.includes(contract.bridges[0].witnessStep))
})

test('積分状態列の漸化式と剰余上界が数値積分でも成立する', () => {
  const problem = mathos.generateLiveProblem({
    domain: 'analysis',
    focusTags: ['integral', 'recurrence', 'inequality', 'limit', 'asymptotic'],
  })
  const lambda = problem.parameters.lambda
  const integrate = (n) => {
    const divisions = 200000
    let sum = 0
    for (let index = 0; index < divisions; index++) {
      const x = (index + 0.5) / divisions
      sum += x ** n / (1 + lambda * x)
    }
    return sum / divisions
  }

  const n = 9
  const current = integrate(n)
  const previous = integrate(n - 1)
  assert.ok(Math.abs(lambda * current + previous - 1 / n) < 1e-9)

  const endpoint = 1 / ((lambda + 1) * (n + 1))
  const upperRemainder = lambda / ((lambda + 1) * (n + 1) * (n + 2))
  assert.ok(current >= endpoint - 1e-12)
  assert.ok(current - endpoint <= upperRemainder + 1e-12)
})
