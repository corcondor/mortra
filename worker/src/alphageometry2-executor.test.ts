import assert from 'node:assert/strict'
import test from 'node:test'
import { spawnSync } from 'node:child_process'
import { resolve } from 'node:path'
import { executeAlphaGeometry2 } from './alphageometry2-executor'

test('official AlphaGeometry2 DDAR checkout proves formalized problems without answer leakage', {
  skip: !process.env.MATHOS_AG2_DIR,
}, () => {
  const adapter = resolve(__dirname, '..', 'backend', 'alphageometry2_adapter.py')
  const result = spawnSync(process.platform === 'win32' ? 'python' : 'python3', [
    adapter,
    '--engine-dir', process.env.MATHOS_AG2_DIR!,
    '--official-suite',
    '--limit', '2',
  ], { encoding: 'utf8', timeout: 120_000 })
  assert.equal(result.status, 0, result.stderr)
  const report = JSON.parse(result.stdout)
  assert.equal(report.total, 2)
  assert.equal(report.proved, 2)
})

test('finite typed search discovers an auxiliary intersection without an LLM', {
  skip: !process.env.MATHOS_AG2_DIR,
}, () => {
  const problem = [
    'a@0_0 = ',
    'b@4_0 = ',
    'c@1_3 = ',
    'd@1_1 = perp b d a c, perp c d a b ? perp a d b c',
  ].join('; ')
  const result = executeAlphaGeometry2(problem, {
    searchAuxiliary: true,
    maxDepth: 1,
    beamWidth: 8,
    maxAttempts: 32,
  })
  assert.equal(result.proved, true, result.error)
  assert.equal(result.baseline_proved, false)
  assert.equal(result.uses_language_model, false)
  assert.equal(result.proposal_engine, 'finite_SKEST_style_ensemble')
  assert.ok(result.analysis?.S2.some(fact => fact.includes('perp')))
  assert.equal(result.trees?.[0]?.name, 'classic')
  assert.ok(result.constructions?.some(item => item.kind === 'line_intersection'))
})

test('Japanese TeX is formalized, diagram-checked, searched, and proved without an LLM', {
  skip: !process.env.MATHOS_AG2_DIR,
}, () => {
  const result = executeAlphaGeometry2(
    String.raw`三角形ABCにおいて、BD\perp AC、CD\perp ABである。AD\perp BCを示せ。`,
    { inputFormat: 'natural', maxDepth: 2, beamWidth: 8, maxAttempts: 64 },
  )
  assert.equal(result.proved, true, result.error)
  assert.equal(result.input_mode, 'natural_or_tex')
  assert.equal(result.formalization?.status, 'formalized')
  assert.ok((result.formalization?.diagram_residual ?? 1) < 1e-6)
  assert.ok(result.constructions?.some(item => item.kind === 'line_intersection'))
  assert.equal(result.uses_language_model, false)
})

test('surface language changes preserve the formal goal and construction family', {
  skip: !process.env.MATHOS_AG2_DIR,
}, () => {
  const variants = [
    String.raw`三角形ABCにおいて、BD\perp AC、CD\perp ABである。AD\perp BCを示せ。`,
    'In triangle ABC, BD is perpendicular to AC and CD is perpendicular to AB. Prove that AD is perpendicular to BC.',
  ]
  const results = variants.map(problem => executeAlphaGeometry2(problem, {
    inputFormat: 'natural', maxDepth: 2, beamWidth: 8, maxAttempts: 64,
  }))
  assert.ok(results.every(result => result.proved), results.map(result => result.error).join('\n'))
  assert.deepEqual(
    results.map(result => result.formalization?.formal_problem?.split(' ? ')[1]),
    ['perp a d b c', 'perp a d b c'],
  )
  assert.ok(results.every(result => result.constructions?.some(item => item.kind === 'line_intersection')))
})

test('unsupported natural-language relations abstain instead of being dropped', {
  skip: !process.env.MATHOS_AG2_DIR,
}, () => {
  const result = executeAlphaGeometry2(
    String.raw`三角形ABCにおいて、Jは三角形ABCの傍心である。AJ\perp BCを示せ。`,
    { inputFormat: 'natural' },
  )
  assert.equal(result.status, 'unformalized')
  assert.equal(result.proved, false)
  assert.ok(result.formalization?.unresolved_relations.includes('傍心'))
})

test('a numerically realizable goal is not leaked into the symbolic premises', {
  skip: !process.env.MATHOS_AG2_DIR,
}, () => {
  const result = executeAlphaGeometry2(
    '三角形ABCにおいて、AB=ACを示せ。',
    { inputFormat: 'natural', maxDepth: 1, beamWidth: 8, maxAttempts: 24 },
  )
  assert.equal(result.formalization?.status, 'formalized')
  assert.equal(result.proved, false)
  assert.equal(result.status, 'unproved')
})

test('a metric premise and angle query are lowered to DDAR predicates', {
  skip: !process.env.MATHOS_AG2_DIR,
}, () => {
  const result = executeAlphaGeometry2(
    String.raw`三角形ABCにおいて、AB=ACである。\angle ABC=\angle BCAを示せ。`,
    { inputFormat: 'natural', maxDepth: 1, beamWidth: 8, maxAttempts: 24 },
  )
  assert.equal(result.proved, true, result.error)
  assert.equal(result.baseline_proved, true)
  assert.equal(result.formalization?.formal_problem?.split(' ? ')[1], 'eqangle b a b c c b c a')
})

test('centers are elaborated into executable primitive predicates', {
  skip: !process.env.MATHOS_AG2_DIR,
}, () => {
  const orthocenter = executeAlphaGeometry2(
    String.raw`三角形ABCにおいて、Hは三角形ABCの垂心である。AH\perp BCを示せ。`,
    { inputFormat: 'natural', maxDepth: 1, maxAttempts: 16 },
  )
  const incenter = executeAlphaGeometry2(
    String.raw`三角形ABCにおいて、Iは三角形ABCの内心である。\angle BAI=\angle IACを示せ。`,
    { inputFormat: 'natural', maxDepth: 1, maxAttempts: 16 },
  )
  const centroid = executeAlphaGeometry2(
    '三角形ABCにおいて、Gは三角形ABCの重心である。AG/AG=1を示せ。',
    { inputFormat: 'natural', maxDepth: 1, maxAttempts: 16 },
  )
  assert.equal(orthocenter.proved, true, orthocenter.error)
  assert.equal(incenter.proved, true, incenter.error)
  assert.equal(centroid.proved, true, centroid.error)
  assert.match(centroid.formalization?.formal_problem ?? '', /g_mid_bc/)
  assert.match(centroid.formalization?.formal_problem ?? '', /distseq a g g g_mid_bc a g_mid_bc 1 1 -1/)
})

test('incidence, tangency, ratio, and angle constants reach executable DDAR predicates', {
  skip: !process.env.MATHOS_AG2_DIR,
}, () => {
  const problems = [
    String.raw`三角形ABCにおいて、Pは直線ABと直線CDの交点である。A,P,Bは一直線上にあることを示せ。`,
    String.raw`直線ABは点Aで中心Oの円に接する。AB\perp OAを示せ。`,
    'AB:CD=EF:GHである。AB:CD=EF:GHを示せ。',
    String.raw`三角形ABCにおいて、\angle ABC=60^\circである。\angle ABC=60^\circを示せ。`,
    'Pは円ABC上にある。A,B,C,Pは同一円周上にあることを示せ。',
  ]
  const results = problems.map(problem => executeAlphaGeometry2(problem, {
    inputFormat: 'natural', maxDepth: 1, beamWidth: 4, maxAttempts: 16,
  }))
  assert.ok(results.every(result => result.proved), results.map(result => result.error).join('\n'))
  const formal = results.map(result => result.formalization?.formal_problem ?? '')
  assert.match(formal[0], /coll a p b/)
  assert.match(formal[1], /perp a b o a/)
  assert.match(formal[2], /eqratio a b c d e f g h/)
  assert.match(formal[3], /s_angle b a b c 60/)
  assert.match(formal[4], /cyclic a b c p/)
})

test('English center and incidence charts lower to the same predicate skeleton', {
  skip: !process.env.MATHOS_AG2_DIR,
}, () => {
  const results = [
    'H is the orthocenter of triangle ABC. Show that AH is perpendicular to BC.',
    'P lies on the circle through A, B and C. Show that A, B, C, P are cyclic.',
  ].map(problem => executeAlphaGeometry2(problem, {
    inputFormat: 'natural', maxDepth: 1, beamWidth: 4, maxAttempts: 16,
  }))
  assert.ok(results.every(result => result.proved), results.map(result => result.error).join('\n'))
  assert.match(results[0].formalization?.formal_problem ?? '', /perp a h b c/)
  assert.match(results[1].formalization?.formal_problem ?? '', /cyclic a b c p/)
})

test('named circles and anaphoric tangent references elaborate to one typed object', {
  skip: !process.env.MATHOS_AG2_DIR,
}, () => {
  const variants = [
    String.raw`Oを中心としAを通る円\Gammaを考える。直線BTはその円に点Tで接する。BT\perp OTを示せ。`,
    'Let Gamma be the circle centered at O through A. Line BT is tangent to Gamma at T. Show that BT is perpendicular to OT.',
  ]
  const results = variants.map(problem => executeAlphaGeometry2(problem, {
    inputFormat: 'natural', maxDepth: 1, beamWidth: 4, maxAttempts: 16,
  }))
  assert.ok(results.every(result => result.proved), results.map(result => result.error).join('\n'))
  assert.ok(results.every(result => result.formalization?.discourse_objects?.length === 1))
  assert.ok(results.every(result => result.formalization?.formal_problem?.includes('cong o t o a')))
  assert.ok(results.every(result => result.formalization?.formal_problem?.endsWith('? perp b t o t')))
  assert.ok(results.every(result => result.uses_language_model === false))
})

test('named-circle membership has the same cyclic skeleton in Japanese and English', {
  skip: !process.env.MATHOS_AG2_DIR,
}, () => {
  const variants = [
    String.raw`三角形ABCの外接円を\Gammaとする。Pは\Gamma上にある。A,B,C,Pは同一円周上にあることを示せ。`,
    'Let Gamma be the circle through A, B and C. P lies on Gamma. Show that A, B, C, P are cyclic.',
  ]
  const results = variants.map(problem => executeAlphaGeometry2(problem, {
    inputFormat: 'natural', maxDepth: 1, beamWidth: 4, maxAttempts: 16,
  }))
  assert.ok(results.every(result => result.proved), results.map(result => result.error).join('\n'))
  assert.ok(results.every(result => result.formalization?.formal_problem?.includes('cyclic a b c p')))
})

test('a tangent with an omitted contact introduces an existential contact point', {
  skip: !process.env.MATHOS_AG2_DIR,
}, () => {
  const result = executeAlphaGeometry2(
    String.raw`Oを中心としAを通る円\Gammaを考える。直線BCは\Gammaに接する。OA=OAを示せ。`,
    { inputFormat: 'natural', maxDepth: 1, beamWidth: 4, maxAttempts: 16 },
  )
  assert.equal(result.proved, true, result.error)
  assert.match(result.formalization?.formal_problem ?? '', /gamma_contact_bc/)
  assert.match(result.formalization?.formal_problem ?? '', /coll b gamma_contact_bc c/)
  assert.match(result.formalization?.formal_problem ?? '', /perp b c o gamma_contact_bc/)
})

test('anaphora selects the most recently declared typed circle', {
  skip: !process.env.MATHOS_AG2_DIR,
}, () => {
  const result = executeAlphaGeometry2(
    String.raw`Oを中心としAを通る円\Gammaを考える。Iを中心としCを通る円\omegaを考える。直線BTはその円に点Tで接する。BT\perp ITを示せ。`,
    { inputFormat: 'natural', maxDepth: 1, beamWidth: 4, maxAttempts: 16 },
  )
  assert.equal(result.proved, true, result.error)
  assert.equal(result.formalization?.discourse_objects?.length, 2)
  assert.match(result.formalization?.formal_problem ?? '', /cong i t i c/)
  assert.doesNotMatch(result.formalization?.formal_problem ?? '', /cong o t o a/)
  assert.match(result.formalization?.formal_problem ?? '', /perp b t i t/)
})

test('deterministic image grounding binds diagram labels without an LLM', () => {
  const grounder = resolve(__dirname, '..', 'backend', 'geometry_diagram_grounder.py')
  const result = spawnSync(process.platform === 'win32' ? 'python' : 'python3', [grounder, '--self-test'], {
    encoding: 'utf8', timeout: 120_000,
  })
  assert.equal(result.status, 0, result.stderr)
  const report = JSON.parse(result.stdout)
  assert.equal(report.passed, true)
  assert.equal(report.grounding.status, 'grounded')
  assert.equal(report.grounding.uses_language_model, false)
  assert.deepEqual(report.grounding.unresolved_labels, [])
  assert.ok(Object.values(report.perturbations).every((item: any) => item.status === 'grounded'))
})

test('a ratio satisfied only by the generated diagram remains unproved', {
  skip: !process.env.MATHOS_AG2_DIR,
}, () => {
  const result = executeAlphaGeometry2(
    '4点A,B,C,Dについて、AB/CD=2を示せ。',
    { inputFormat: 'natural', maxDepth: 1, beamWidth: 4, maxAttempts: 16 },
  )
  assert.equal(result.formalization?.status, 'formalized')
  assert.equal(result.proved, false)
  assert.equal(result.status, 'unproved')
})

test('degenerate directed segments are rejected by typed elaboration', {
  skip: !process.env.MATHOS_AG2_DIR,
}, () => {
  const result = executeAlphaGeometry2(
    String.raw`3点A,B,Cについて、AA\perp BCを示せ。`,
    { inputFormat: 'natural' },
  )
  assert.equal(result.status, 'unformalized')
  assert.ok(result.formalization?.unresolved_relations.some(issue => issue.includes('identical endpoints')))
})

test('auxiliary search is invariant under a similarity coordinate change', {
  skip: !process.env.MATHOS_AG2_DIR,
}, () => {
  const configurations = [
    ['2_-1', '10_-1', '4_5', '4_1'],
    ['3_4', '3_8', '0_5', '2_5'],
    ['-2_7', '-14_7', '-5_-2', '-5_4'],
    ['1_1', '3_1', '1.5_2.5', '1.5_1.5'],
  ]
  for (const [a, b, c, d] of configurations) {
    const problem = [
      `a@${a} = `,
      `b@${b} = `,
      `c@${c} = `,
      `d@${d} = perp b d a c, perp c d a b ? perp a d b c`,
    ].join('; ')
    const result = executeAlphaGeometry2(problem, {
      searchAuxiliary: true,
      maxDepth: 1,
      beamWidth: 8,
      maxAttempts: 32,
    })
    assert.equal(result.proved, true, result.error)
    assert.equal(result.baseline_proved, false)
    assert.ok(result.constructions?.some(item => item.kind === 'line_intersection'))
    assert.equal(result.attempt_trace?.at(-1)?.status, 'proved')
  }
})

test('auxiliary search does not turn a false goal into a proof', {
  skip: !process.env.MATHOS_AG2_DIR,
}, () => {
  const problem = [
    'a@0_0 = ',
    'b@4_0 = ',
    'c@1_3 = ',
    'd@1_1 = perp b d a c, perp c d a b ? para a d b c',
  ].join('; ')
  const result = executeAlphaGeometry2(problem, {
    searchAuxiliary: true,
    maxDepth: 1,
    beamWidth: 8,
    maxAttempts: 32,
  })
  assert.equal(result.proved, false)
  assert.equal(result.status, 'unproved')
  assert.equal(result.baseline_proved, false)
})
