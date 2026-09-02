import assert from 'node:assert/strict'
import test from 'node:test'

import { auditPublicationContent } from './publication-content-audit'

const valid = {
  statement_tex: '実数 \\(x\\) が \\(2x+1=7\\) を満たす。\\(x\\) を求めよ。',
  answer_tex: '\\(x=3\\)',
  solution_tex: '\\(2x=6\\) より \\(x=3\\) である。',
}

test('accepts a complete Japanese mathematical artifact', () => {
  assert.deepEqual(auditPublicationContent(valid), { passed: true, errors: [] })
})

test('rejects a dangling recurrence coefficient before a TeX delimiter', () => {
  const audit = auditPublicationContent({
    ...valid,
    statement_tex: '整数列 \\(a_{n+2}=3a_{n+1}-2a_n+\\) を考える。',
  })
  assert.equal(audit.passed, false)
  assert.ok(audit.errors.some(error => error.includes('binary operator')))
})

test('rejects replacement characters and unresolved placeholders', () => {
  const audit = auditPublicationContent({
    ...valid,
    answer_tex: '\\(x=undefined\\) \uFFFD',
  })
  assert.equal(audit.passed, false)
  assert.ok(audit.errors.some(error => error.includes('replacement character')))
  assert.ok(audit.errors.some(error => error.includes('placeholder')))
})

test('rejects unbalanced TeX delimiters and braces', () => {
  const audit = auditPublicationContent({
    ...valid,
    solution_tex: '\\[x^{2=9\\)',
  })
  assert.equal(audit.passed, false)
  assert.ok(audit.errors.some(error => error.includes('delimiter')))
  assert.ok(audit.errors.some(error => error.includes('grouping braces')))
})
