import assert from 'node:assert/strict'
import test from 'node:test'
import {
  elaborateMathematicalText,
  lexMathematicalText,
  parseMathematicalText,
} from './mathematical-language'

test('lexer separates TeX commands, identifiers, relations, and Japanese particles', () => {
  const tokens = lexMathematicalText('任意の x に対して \\int_0^1 f(x)dx = 0 を満たす。')
  assert.ok(tokens.some(token => token.kind === 'command' && token.value === '\\int'))
  assert.ok(tokens.some(token => token.kind === 'identifier' && token.value === 'x'))
  assert.ok(tokens.some(token => token.kind === 'relation' && token.value === '='))
  assert.ok(tokens.some(token => token.kind === 'particle' && token.value === 'に対して'))
})

test('quantifier order is preserved and changes the IR certificate', () => {
  const forallExists = elaborateMathematicalText('任意の x に対して y が存在する。')
  const existsForall = elaborateMathematicalText('y が存在し、任意の x に対して条件を満たす。')
  assert.deepEqual(forallExists.ir.quantifier_prefix, ['forall:x', 'exists:y'])
  assert.deepEqual(existsForall.ir.quantifier_prefix, ['exists:y', 'forall:x'])
  assert.notDeepEqual(forallExists.ir.quantifier_prefix, existsForall.ir.quantifier_prefix)
})

test('new mathematical names are introduced from definitions without a lexicon entry', () => {
  const result = elaborateMathematicalText('X を x^2+y^2=1 を満たす点全体の集合と定める。Xの面積を求めよ。')
  assert.equal(result.ir.definitions.length, 1)
  assert.equal(result.ir.definitions[0].symbol, 'X')
  assert.match(result.ir.definitions[0].canonical, /^DefinedObject\[/)
  assert.equal(result.ir.query?.kind, 'measure')
})

test('parse forest is finite and explicitly reports truncation', () => {
  const text = Array.from({ length: 10 }, (_, index) => `条件${index}を満たす`).join('。')
  const forest = parseMathematicalText(text, 8)
  assert.equal(forest.analyses.length, 8)
  assert.equal(forest.truncated, true)
  assert.match(forest.diagnostics[0], /capped/)
})

test('alpha-renaming preserves normalized defined-object structure', () => {
  const left = elaborateMathematicalText('Xを x^2+x=0 の解全体と定める。')
  const right = elaborateMathematicalText('Yを t^2+t=0 の解全体と定める。')
  assert.equal(left.ir.definitions[0].canonical, right.ir.definitions[0].canonical)
})

test('typed declarations induce ordered implicit universal quantifiers', () => {
  const result = elaborateMathematicalText('素数 p と整数 a に対し、a が p を法として平方剰余となる条件を示せ。')
  assert.deepEqual(result.ir.declarations.map(item => [item.symbol, item.sort]), [['p', 'Prime'], ['a', 'Integer']])
  assert.deepEqual(result.ir.quantifier_prefix, ['forall:p', 'forall:a'])
  assert.ok(!result.ir.unresolved_references.includes('p'))
  assert.ok(!result.ir.unresolved_references.includes('a'))
})

test('equation-style definitions and relations are elaborated structurally', () => {
  const result = elaborateMathematicalText('関数 f に対し I_n=\\int_0^1 x^n f(x)dx と定める。')
  assert.equal(result.ir.definitions[0]?.symbol, 'I_n')
  assert.ok(result.ir.constraints.some(item => item.operator === '='))
})
