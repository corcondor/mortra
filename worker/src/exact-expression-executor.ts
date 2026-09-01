import { spawnSync } from 'node:child_process'
import { resolve } from 'node:path'

import type { MathExpression } from './math-expression-ir'

export type ExactExpressionEvaluation = {
  ok: boolean
  error?: string
  free_symbols?: string[]
  expression_tex?: string
  result_tex?: string
  result_srepr?: string
  operators?: string[]
  certificate?: Record<string, unknown>
}

type ExactExpressionBatchResponse = {
  ok?: unknown
  results?: ExactExpressionEvaluation[]
  error?: unknown
}

function repositoryRoot(): string {
  return resolve(__dirname, '..', '..')
}

export function evaluateExactExpression(expression: MathExpression): ExactExpressionEvaluation {
  return evaluateExactExpressions([expression])[0] ?? { ok: false, error: 'empty exact-expression response' }
}

export function evaluateExactExpressions(expressions: readonly MathExpression[]): ExactExpressionEvaluation[] {
  if (expressions.length === 0) return []
  const root = repositoryRoot()
  const python = process.env.MORTRA_PYTHON || process.env.PYTHON ||
    (process.platform === 'win32' ? 'python' : 'python3')
  const script = resolve(root, 'worker', 'backend', 'exact_expression_ir.py')
  const run = spawnSync(python, ['-B', script], {
    cwd: root,
    input: JSON.stringify({ expression_irs: expressions }),
    encoding: 'utf8',
    timeout: 120_000,
    maxBuffer: 8 * 1024 * 1024,
    windowsHide: true,
  })
  if (run.error) return expressions.map(() => ({ ok: false, error: run.error!.message }))
  if (!run.stdout.trim()) {
    const error = run.stderr.trim() || `exact expression executor exited with ${run.status}`
    return expressions.map(() => ({ ok: false, error }))
  }
  try {
    const response = JSON.parse(run.stdout) as ExactExpressionBatchResponse
    if (!Array.isArray(response.results) || response.results.length !== expressions.length) {
      const error = String(response.error || 'exact expression executor returned an invalid batch')
      return expressions.map(() => ({ ok: false, error }))
    }
    return response.results
  } catch {
    const error = `exact expression executor returned invalid JSON: ${run.stdout.slice(0, 240)}`
    return expressions.map(() => ({ ok: false, error }))
  }
}
