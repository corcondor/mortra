import assert from 'node:assert/strict'
import { resolve } from 'node:path'
import test from 'node:test'

import { locateRepositoryRoot, pythonBackendEnvironment } from './python-backend-runtime'

const repositoryRoot = resolve(__dirname, '..', '..')

test('locates a Python backend from both repository and worker working directories', () => {
  const requiredPath = 'worker/backend/exact_expression_ir.py'
  assert.equal(
    locateRepositoryRoot(requiredPath, { cwd: repositoryRoot, moduleDir: __dirname }),
    repositoryRoot,
  )
  assert.equal(
    locateRepositoryRoot(requiredPath, {
      cwd: resolve(repositoryRoot, 'worker'),
      moduleDir: resolve(repositoryRoot, 'worker'),
    }),
    repositoryRoot,
  )
})

test('passes the repository package path and UTF-8 settings to Python', () => {
  const environment = pythonBackendEnvironment(repositoryRoot)
  assert.equal(environment.PYTHONUTF8, '1')
  assert.equal(environment.PYTHONIOENCODING, 'utf-8')
  assert.ok(environment.PYTHONPATH?.split(process.platform === 'win32' ? ';' : ':').includes(repositoryRoot))
})
