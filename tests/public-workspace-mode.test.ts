import assert from 'node:assert/strict'
import test from 'node:test'

import { resolvePublicWorkspace } from '../lib/mortra/public-workspace-mode'

test('auto mode solves a single problem entered in A', () => {
  assert.deepEqual(resolvePublicWorkspace('auto', 'problem A', ''), {
    taskMode: 'solve',
    inputSlots: ['a'],
    command: '/solve',
    error: null,
  })
})

test('auto mode solves a single problem entered in B', () => {
  assert.deepEqual(resolvePublicWorkspace('auto', '', 'problem B'), {
    taskMode: 'solve',
    inputSlots: ['b'],
    command: '/solve',
    error: null,
  })
})

test('auto mode fuses two entered problems', () => {
  assert.deepEqual(resolvePublicWorkspace('auto', 'problem A', 'problem B'), {
    taskMode: 'fusion',
    inputSlots: ['a', 'b'],
    command: '/combine',
    error: null,
  })
})

test('explicit combine still requires two problems', () => {
  assert.equal(resolvePublicWorkspace('fusion', 'problem A', '').error, 'needs_two')
})

test('draw remains a single-problem operation', () => {
  assert.deepEqual(resolvePublicWorkspace('draw', 'problem A', 'ignored problem B'), {
    taskMode: 'solve',
    inputSlots: ['a'],
    command: '/draw',
    error: null,
  })
})

test('empty auto workspace does not submit', () => {
  assert.deepEqual(resolvePublicWorkspace('auto', ' ', '\n'), {
    taskMode: 'solve',
    inputSlots: [],
    command: '/try',
    error: 'empty',
  })
})
