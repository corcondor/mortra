import assert from 'node:assert/strict'
import test from 'node:test'
import { discoverParentStructures } from './parent-conditioned-discovery'

const integral = (id: string, variable = 'a_n', upper = '1') => ({
  id,
  statement: `数列 ${variable}=\\int_0^${upper}x^n dx の極限を求めよ。`,
})
const congruence = (id: string, variable = 'x', residue = '1') => ({
  id,
  statement: `素数 p に対し ${variable}^2\\equiv-${residue}\\pmod p の可解性を示せ。`,
})

test('one problem creates a query-closure obligation instead of being rejected', () => {
  const result = discoverParentStructures([{
    id: 'single',
    statement: '実数 $x,y$ は $x+y=19$, $y=4$ を満たす。$x$ を求めよ。',
  }])
  assert.equal(result.parent_graphs.length, 1)
  assert.ok(result.hypotheses.length > 0)
  assert.equal(result.cards[0].parent_ids[0], 'single')
  assert.match(result.cards[0].structure_blueprint.observable, /QueryClosure/)
})

test('unknown parents are lifted from their operators instead of a remembered family', () => {
  const result = discoverParentStructures([integral('i'), congruence('n')], 3)
  assert.equal(result.discovered, 3)
  assert.match(result.cards[0].structure_blueprint.observable, /IntegralFunctional/)
  assert.match(result.cards[0].structure_blueprint.observable, /IntegerStructure/)
  assert.deepEqual(result.cards[0].parent_ids, ['i', 'n'])
  assert.equal(result.cards[0].unresolved, true)
})

test('surface variable and numeric changes preserve the abstract lift', () => {
  const first = discoverParentStructures([integral('i1'), congruence('n1')])
  const second = discoverParentStructures([integral('i2', 'b_k', '2'), congruence('n2', 'y', '2')])
  assert.deepEqual(
    first.parent_graphs.map(graph => graph.semantic_roots),
    second.parent_graphs.map(graph => graph.semantic_roots),
  )
})

test('all selected parents remain distinct proof inputs', () => {
  const result = discoverParentStructures([integral('i'), congruence('n'), { id: 'g', statement: '三角形の重心の軌跡が囲む面積を求めよ。' }])
  const derivation = result.cards[0].fusion_derivation
  assert.equal(derivation.ablationPassed, true)
  assert.equal(derivation.assignments.length, 3)
  assert.equal(new Set(derivation.assignments.map(item => item.parentId)).size, 3)
})

test('coprimality alone does not elaborate an unrelated problem as a primitive right triangle', () => {
  const result = discoverParentStructures([{
    id: 'lattice-line',
    statement: '互いに素な正の整数 a,b に対し、直線 ax+by=ab 上の格子点を分類せよ。',
  }])
  const roots = result.parent_graphs[0].semantic_roots
  assert.ok(!roots.includes('PrimitiveIntegerRightTriangle'))
  assert.ok(!roots.includes('EuclidParameterPair'))
  assert.ok(roots.includes('CoprimeIntegerTuple'))
  assert.ok(roots.includes('AffineLattice'))
  assert.ok(roots.includes('LinearDiophantineConstraint'))
})

test('primitive right-triangle elaboration requires both structural conditions', () => {
  const result = discoverParentStructures([{
    id: 'primitive-right-triangle',
    statement: '二辺が互いに素である整数直角三角形の三辺を分類せよ。',
  }])
  const roots = result.parent_graphs[0].semantic_roots
  assert.ok(roots.includes('PrimitiveIntegerRightTriangle'))
  assert.ok(roots.includes('EuclidParameterPair'))
})

test('primality alone does not elaborate an unrelated problem as a prime radius product', () => {
  const result = discoverParentStructures([{
    id: 'cyclotomic-prime',
    statement: '素数 p に対し、円分多項式の整数係数因子を分類せよ。',
  }])
  const roots = result.parent_graphs[0].semantic_roots
  assert.ok(!roots.includes('TriangleRadii'))
  assert.ok(!roots.includes('PrimeProductConstraint'))
  assert.ok(roots.includes('IntegerStructure'))
})

test('rational-angle classification retains reusable trigonometric and integer structure', () => {
  const result = discoverParentStructures([{
    id: 'rational-angle',
    statement: '互いに素な自然数 p,q に対し、cos^n(p*pi/q)+sin^n(p*pi/q)=1 となる組を分類せよ。',
  }])
  const roots = result.parent_graphs[0].semantic_roots
  assert.ok(roots.includes('IntegerStructure'))
  assert.ok(roots.includes('CoprimeIntegerTuple'))
  assert.ok(roots.includes('TrigonometricExpression'))
  assert.ok(!roots.some(root => root.startsWith('OpaqueStructure[')))
})

test('prime radius-product elaboration requires radius and primality evidence', () => {
  const result = discoverParentStructures([{
    id: 'prime-radius-product',
    statement: '整数三角形の内接円半径と外接円半径の積が素数となる場合を求めよ。',
  }])
  const roots = result.parent_graphs[0].semantic_roots
  assert.ok(roots.includes('TriangleRadii'))
  assert.ok(roots.includes('PrimeProductConstraint'))
})
