import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { generateKeyPairSync, sign } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

const require = createRequire(import.meta.url)
const source = await readFile(
  new URL('../lib/discord-interactions.ts', import.meta.url),
  'utf8',
)
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
    esModuleInterop: true,
  },
}).outputText
const module = { exports: {} }
new Function('require', 'module', 'exports', compiled)(
  require,
  module,
  module.exports,
)
const {
  interactionUserId,
  stringOption,
  verifyDiscordRequest,
} = module.exports

test('accepts a valid Discord Ed25519 signature and rejects tampering', () => {
  const { privateKey, publicKey } = generateKeyPairSync('ed25519')
  const publicDer = publicKey.export({ format: 'der', type: 'spki' })
  const publicKeyHex = publicDer.subarray(-32).toString('hex')
  const body = JSON.stringify({ type: 1 })
  const timestamp = '1721736000'
  const signature = sign(
    null,
    Buffer.from(timestamp + body),
    privateKey,
  ).toString('hex')

  assert.equal(
    verifyDiscordRequest(body, signature, timestamp, publicKeyHex),
    true,
  )
  assert.equal(
    verifyDiscordRequest(`${body} `, signature, timestamp, publicKeyHex),
    false,
  )
})

test('reads command options and user identity from guild interactions', () => {
  const interaction = {
    id: '1',
    application_id: '2',
    token: 'token',
    type: 2,
    member: { user: { id: '42' } },
    data: {
      name: 'sakumon',
      options: [{ name: 'domain', type: 3, value: '整数' }],
    },
  }
  assert.equal(interactionUserId(interaction), '42')
  assert.equal(stringOption(interaction, 'domain'), '整数')
})

test('the bundled MathOS pool contains only gate-passing problems', async () => {
  const batch = JSON.parse(
    await readFile(
      new URL(
        '../data/mathos/continuous_verified_problem_batch1.json',
        import.meta.url,
      ),
      'utf8',
    ),
  )
  const accepted = batch.problems.filter(
    (problem) =>
      problem.accepted &&
      problem.verification.exact_backend &&
      problem.verification.independent_check &&
      problem.lift_certificate.type_checked &&
      problem.novelty.corpus_novel,
  )
  assert.equal(accepted.length, 309)
})
