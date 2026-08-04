import assert from 'node:assert/strict'
import test from 'node:test'
import {
  extractMathRelations,
  mathExpressionToSympy,
  parseLatexRelation,
  renameMathSymbol,
} from './math-expression-ir'

test('parses a TeX relation into a MathJSON-style semantic tree', () => {
  const relation = parseLatexRelation('u^2-2=0')
  assert.ok(relation)
  assert.equal(relation.operator, 'Equal')
  assert.deepEqual(relation.variables, ['u'])
  assert.match(mathExpressionToSympy(relation.lhs), /u/)
})

test('parses nested fractions, roots, and implicit multiplication without regex rewriting', () => {
  const relation = parseLatexRelation('\\frac{x^2-1}{x+1}=2\\sqrt{x}')
  assert.ok(relation)
  assert.deepEqual(relation.variables, ['x'])
  const sympy = mathExpressionToSympy(relation.lhs)
  assert.match(sympy, /\/\(/)
  assert.match(mathExpressionToSympy(relation.rhs), /sqrt\(x\)/)
})

test('keeps Japanese prose outside TeX and extracts only mathematical relations', () => {
  const relations = extractMathRelations('実数 $a$ に対して、方程式 $x^3-3x+a=0$ の根を考える。')
  assert.equal(relations.length, 1)
  assert.deepEqual(relations[0].variables, ['a', 'x'])
})

test('renames bound endpoint symbols structurally', () => {
  const relation = parseLatexRelation('\\frac{t^2-1}{t+1}=0')!
  const renamed = renameMathSymbol(relation.lhs, 't', 'x')
  assert.doesNotMatch(mathExpressionToSympy(renamed), /t/)
  assert.match(mathExpressionToSympy(renamed), /x/)
})
