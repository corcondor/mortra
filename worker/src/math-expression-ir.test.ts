import assert from 'node:assert/strict'
import test from 'node:test'
import {
  extractBoundMathExpression,
  extractMathRelations,
  isDirectBoundExpressionQuery,
  mathExpressionToLatex,
  mathExpressionToSympy,
  parseLatexExpression,
  parseLatexRelation,
  renameMathSymbol,
  symbolsInMathExpression,
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

test('parses a nested limit of a finite sum without a remembered problem family', () => {
  const expression = parseLatexExpression(
    String.raw`\lim_{n\to\infty}\left\{\sum_{k=0}^{n}\left(1+\frac{1}{{}_n C_k}\right)^{{}_n C_k}-en\right\}`,
  )
  assert.deepEqual(expression, [
    'Limit',
    'n',
    'Infinity',
    [
      'Subtract',
      [
        'Sum',
        'k',
        0,
        'n',
        ['Power', ['Add', 1, ['Divide', 1, ['Binomial', 'n', 'k']]], ['Binomial', 'n', 'k']],
      ],
      ['Multiply', 'e', 'n'],
    ],
  ])
  assert.equal(
    mathExpressionToSympy(expression!),
    'limit(((Sum((((1)+(((1)/(binomial(n,k)))))^(binomial(n,k))),(k,0,n)))-((e)*(n))),n,oo)',
  )
  assert.deepEqual(symbolsInMathExpression(expression!), [])
})

test('parses a definite integral with an explicit differential', () => {
  const expression = parseLatexExpression(
    String.raw`\int_0^{\frac{\pi}{2}}(\cos x+\sin x)\,dx`,
  )
  assert.deepEqual(expression, [
    'Integral',
    'x',
    0,
    ['Divide', 'pi', 2],
    ['Add', ['Apply', 'cos', 'x'], ['Apply', 'sin', 'x']],
  ])
  assert.deepEqual(symbolsInMathExpression(expression!), [])
})

test('extracts the current bound expression without supplying a missing family', () => {
  const extracted = extractBoundMathExpression(
    String.raw`次を求めよ。\[\lim_{r\to\infty}\frac{\sum_{j=1}^{r}j}{r^2}\]`,
  )
  assert.ok(extracted)
  assert.deepEqual(extracted.expression, [
    'Limit',
    'r',
    'Infinity',
    ['Divide', ['Sum', 'j', 1, 'r', 'j'], ['Power', 'r', 2]],
  ])
  assert.equal(extractBoundMathExpression('未知の数列の極限を求めよ。'), null)
  assert.equal(
    mathExpressionToLatex(extracted.expression),
    String.raw`\lim_{r\to \infty}\left(\frac{\sum_{j=1}^{r}\left(j\right)}{\left(r\right)^{2}}\right)`,
  )
})

test('distinguishes a direct value query from a predicate about the same expression', () => {
  assert.equal(isDirectBoundExpressionQuery(
    String.raw`次の極限を求めよ。\[\lim_{r\to\infty}\frac{\sum_{j=1}^{r}j}{r^2}\]`,
  ), true)
  assert.equal(isDirectBoundExpressionQuery(
    String.raw`(1) e<1+\sqrt3 を示せ。(2) \int_0^1 e^x\sin x\,dx は整数か。`,
  ), false)
})
