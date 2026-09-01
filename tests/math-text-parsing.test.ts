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
