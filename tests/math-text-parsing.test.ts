import assert from 'node:assert/strict'
import test from 'node:test'

import { parseMath } from '../lib/utils'

test('delimiter-free polynomial answers are typeset as math', () => {
  assert.deepEqual(parseMath('P(z)=z^{6}-9z^{5}+10z^{4}'), [
    { type: 'inline', content: 'P(z)=z^{6}-9z^{5}+10z^{4}' },
    { type: 'text', content: '\n' },
  ])
})

test('ordinary prose with braces is not treated as math', () => {
  assert.deepEqual(parseMath('result {draft}'), [
    { type: 'text', content: 'result {draft}' },
  ])
})

test('Japanese prose remains text when it contains a scripted token', () => {
  assert.deepEqual(parseMath('答えは z^{6} である。'), [
    { type: 'text', content: '答えは z^{6} である。' },
  ])
})

test('mixed Japanese and an integral are split at mathematical boundaries', () => {
  const statement = String.raw`I=\int_0^{\pi/2}\{\cos(\cos x+\sin x)+\sin(\cos x+\sin x)\}\,dx とする。0<I<2 を証明せよ。`
  assert.deepEqual(parseMath(statement), [
    {
      type: 'inline',
      content: String.raw`I=\int_0^{\pi/2}\{\cos(\cos x+\sin x)+\sin(\cos x+\sin x)\}\,dx`,
    },
    { type: 'text', content: ' とする。' },
    { type: 'inline', content: '0<I<2' },
    { type: 'text', content: ' を証明せよ。' },
    { type: 'text', content: '\n' },
  ])
})

test('a bare polynomial relation inside Japanese prose is typeset', () => {
  assert.deepEqual(parseMath('関数 f(x)=x^4-4x^2+1 の増減を調べよ。'), [
    { type: 'text', content: '関数 ' },
    { type: 'inline', content: 'f(x)=x^4-4x^2+1' },
    { type: 'text', content: ' の増減を調べよ。' },
    { type: 'text', content: '\n' },
  ])
})
