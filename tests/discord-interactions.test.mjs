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

const selectionSource = await readFile(
  new URL('../lib/mathos-selection.ts', import.meta.url),
  'utf8',
)
const selectionCompiled = ts.transpileModule(selectionSource, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
    esModuleInterop: true,
  },
}).outputText
const selectionModule = { exports: {} }
new Function('require', 'module', 'exports', selectionCompiled)(
  require,
  selectionModule,
  selectionModule.exports,
)
const {
  canonicalDomain,
  domainMatches,
  orderForInteraction,
} = selectionModule.exports

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
      problem.novelty.corpus_novel &&
      problem.curriculum_certificate?.scope ===
        'jp_upper_secondary_math_IA_IIB_IIIC' &&
      problem.curriculum_certificate?.type_checked,
  )
  assert.equal(accepted.length, batch.summary.certified_structures)
  assert.ok(accepted.length >= 30)
  assert.equal(
    new Set(accepted.map((problem) => problem.structure_key)).size,
    accepted.length,
  )
  // 族の名前ではなく、配信される文章そのものを検査する。
  // 内部で平方剰余やグラフを使うこと自体は禁止しない。禁止するのは、
  // 高校の語彙へ書き換えられないまま配信されることだけ。
  // 例:「x-y が平方数と合同なとき結んで得られるグラフ」は高校範囲であり、
  // 「Paley グラフ」という固有名詞が残っていたら未整形とみなす。
  const outOfVocabulary =
    /Paley|ラプラシアン|隣接行列|全域木|固有値|スペクトル|Minkowski|ミンコフスキー|ルジャンドル記号|行列木定理/
  const unlowered = accepted.filter((problem) =>
    outOfVocabulary.test(
      `${problem.statement_tex ?? ''} ${problem.solution_tex ?? ''}`,
    ),
  )
  assert.deepEqual(
    unlowered.map((problem) => problem.family_id),
    [],
  )
  assert.ok(
    accepted.some((problem) =>
      problem.family_id.includes('geometry'),
    ),
  )
})

test('geometry requests include every geometry subdomain', () => {
  assert.equal(canonicalDomain('幾何'), 'geometry')
  for (const domain of [
    'geometry',
    'algebraic_geometry',
    'analytic_geometry',
    'complex_geometry',
    'differential_geometry',
    'euclidean_geometry',
    'geometry_algebra',
    'geometry_analysis',
    'projective_geometry',
  ]) {
    assert.equal(domainMatches(domain, '幾何'), true, domain)
  }
  assert.equal(domainMatches('probability', '幾何'), false)
})

test('different Discord interactions randomize structures without weighting', async () => {
  const batch = JSON.parse(
    await readFile(
      new URL(
        '../data/mathos/continuous_verified_problem_batch1.json',
        import.meta.url,
      ),
      'utf8',
    ),
  )
  const selectable = batch.problems.map((problem) => ({
    structureKey: problem.structure_key,
    domain: problem.domain,
  }))
  const firstSelections = new Set(
    Array.from({ length: 100 }, (_, index) =>
      orderForInteraction(selectable, `interaction-${index}`)[0]
        .structureKey,
    ),
  )
  assert.ok(firstSelections.size >= 28)
  assert.equal(
    orderForInteraction(selectable, 'same-event')[0].structureKey,
    orderForInteraction(selectable, 'same-event')[0].structureKey,
  )
})
