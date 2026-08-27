import assert from 'node:assert/strict'
import test from 'node:test'

import {
  compileDirectionalWord,
  endpointNormalFormLosesSupport,
  parseDirectionalWord,
  verifyDirectionalWordCompilation,
  verifyEndpointNormalFormCertificate,
} from '../lib/mortra/cross-domain/directional-word.js'
import {
  buildCanonicalNormalFormAtlas,
  normalizeGeneratorWord,
  verifyCanonicalNormalFormAtlas,
  verifyNormalizationWitness,
} from '../lib/mortra/kernel/canonical-generator-normal-form.js'

test('one directional word compiles into geometry, support, schedule, and matrix views', () => {
  const built = compileDirectionalWord('paper-weight-7', String.raw`N^2 E S E N^2`)
  assert.ok(built.compilation)
  assert.equal(built.compilation.steps.join(''), 'NNESENN')
  assert.deepEqual(built.compilation.geometry.endpoint, { x: 2, y: 3 })
  assert.equal(built.compilation.stabilizer.weight, 7)
  assert.deepEqual(built.compilation.stabilizer.codeAdmissibility, {
    simpleEdgeSupport: true,
    mutualPrimalDualCommutation: true,
    displacementParityCondition: true,
    certifiedDirectionalTile: true,
  })
  assert.equal(built.compilation.stabilizer.cssCertificate.mutualCondition.checkedEdges, 7)
  assert.equal(built.compilation.stabilizer.cssCertificate.staticCssCommutation.oddOverlapViolations.length, 0)
  assert.equal(built.compilation.stabilizer.cssCertificate.displacementParity.oddMultiplicityViolations.length, 0)
  assert.equal(built.compilation.schedule.interactionDepth, 7)
  assert.equal(built.compilation.schedule.roundDepthWithPreparationAndMeasurement, 9)
  assert.equal(built.compilation.schedule.forwardInverseRestoresOrigin, true)
  assert.deepEqual(built.compilation.translationMatrix, [[1, 0, 2], [0, 1, 3], [0, 0, 1]])
  assert.deepEqual(verifyDirectionalWordCompilation(built.compilation), [])

  const sorts = new Set([...built.compilation.kernel.objects.values()].map(object => object.sort))
  assert.deepEqual([...sorts].sort(), ['Matrix', 'Sequence', 'Stabilizer', 'VisualElement'])
})

test('the five paper words preserve their stated weights and circuit depths', () => {
  const examples = [
    ['N E S E N', 5],
    ['N^2 E S E N^2', 7],
    ['N^2 E^2 S E^2 N^2', 9],
    ['N^2 E^2 S E S E^2 N^2', 11],
    ['N^2 E^2 S E^3 S E^2 N^2', 13],
  ] as const
  for (const [input, weight] of examples) {
    const built = compileDirectionalWord(`paper-weight-${weight}`, input)
    assert.ok(built.compilation)
    assert.equal(built.compilation.steps.length, weight)
    assert.equal(built.compilation.stabilizer.weight, weight)
    assert.equal(built.compilation.schedule.roundDepthWithPreparationAndMeasurement, weight + 2)
    assert.equal(built.compilation.stabilizer.codeAdmissibility.certifiedDirectionalTile, true)
    assert.deepEqual(verifyDirectionalWordCompilation(built.compilation), [])
  }
})

test('parser accepts compact, exponent, and TeX directional words but rejects unknown generators', () => {
  assert.equal(parseDirectionalWord('NESEN').steps?.join(''), 'NESEN')
  assert.equal(parseDirectionalWord(String.raw`\mathfrak D=N^{2}\texttt{E}S\texttt{E}N^2`).steps?.join(''), 'NNESENN')
  assert.match(parseDirectionalWord('NEQ').errors.join(' '), /invalid directional token/)
})

test('translation normal form declares and demonstrates the invariants it loses', () => {
  const built = compileDirectionalWord('closed-loop', 'NESW')
  assert.ok(built.compilation)
  assert.deepEqual(built.compilation.geometry.endpoint, { x: 0, y: 0 })
  assert.deepEqual(built.compilation.endpointNormalForm.normalWord, [])
  assert.equal(endpointNormalFormLosesSupport(built.compilation), true)
  assert.deepEqual(built.compilation.endpointNormalForm.notPreserved, [
    'ordered-support',
    'stabilizer-support',
    'measurement-schedule',
  ])
  assert.deepEqual(verifyEndpointNormalFormCertificate(built.compilation.endpointNormalForm), [])
})

test('a backtracking word is represented but is not mislabelled as a simple code support', () => {
  const built = compileDirectionalWord('backtrack', 'NS')
  assert.ok(built.compilation)
  assert.equal(built.compilation.stabilizer.weight, 1)
  assert.deepEqual(built.compilation.stabilizer.repeatedEdges, ['0,0|0,1'])
  assert.equal(built.compilation.stabilizer.codeAdmissibility.simpleEdgeSupport, false)
  assert.equal(built.compilation.stabilizer.codeAdmissibility.certifiedDirectionalTile, false)
})

test('the displacement condition rejects an odd singleton vector instead of silently certifying it', () => {
  const built = compileDirectionalWord('odd-displacement', 'NE')
  assert.ok(built.compilation)
  assert.equal(built.compilation.stabilizer.codeAdmissibility.mutualPrimalDualCommutation, true)
  assert.equal(built.compilation.stabilizer.codeAdmissibility.displacementParityCondition, false)
  assert.deepEqual(
    built.compilation.stabilizer.cssCertificate.displacementParity.oddMultiplicityViolations.map(item => [
      item.dx2,
      item.dy2,
      item.multiplicity,
    ]),
    [[1, 1, 1]],
  )
  assert.deepEqual(verifyDirectionalWordCompilation(built.compilation), [])
})

test('stale multi-view and normal-form certificates are rejected', () => {
  const built = compileDirectionalWord('mutation', 'NNESENN')
  assert.ok(built.compilation)

  const staleCompilation = structuredClone(built.compilation)
  staleCompilation.geometry.endpoint.x += 1
  assert.match(verifyDirectionalWordCompilation(staleCompilation).join(' '), /geometric path replay mismatch/)

  const staleCssCertificate = structuredClone(built.compilation)
  staleCssCertificate.stabilizer.cssCertificate.staticCssCommutation.witnesses[0].overlap += 1
  assert.match(verifyDirectionalWordCompilation(staleCssCertificate).join(' '), /CSS certificate replay mismatch/)

  const staleCertificate = structuredClone(built.compilation.endpointNormalForm)
  staleCertificate.originalMatrix[0][2] += 1
  assert.match(verifyEndpointNormalFormCertificate(staleCertificate).join(' '), /original matrix is stale/)

  const nonminimal = structuredClone(built.compilation.endpointNormalForm)
  nonminimal.normalWord.push('N', 'S')
  nonminimal.normalMatrix = nonminimal.originalMatrix
  assert.match(
    verifyEndpointNormalFormCertificate(nonminimal).join(' '),
    /not the canonical shortest translation representative/,
  )
})

type TorusPoint = { x: number; y: number }

const mod = (value: number, modulus: number) => ((value % modulus) + modulus) % modulus

test('finite generated actions receive complete shortest canonical normal forms', () => {
  const modulus = 5
  const atlas = buildCanonicalNormalFormAtlas<TorusPoint>({
    initial: { x: 0, y: 0 },
    key: state => `${state.x},${state.y}`,
    generators: [
      { id: 'E', apply: state => ({ x: mod(state.x + 1, modulus), y: state.y }) },
      { id: 'N', apply: state => ({ x: state.x, y: mod(state.y + 1, modulus) }) },
      { id: 'W', apply: state => ({ x: mod(state.x - 1, modulus), y: state.y }) },
      { id: 'S', apply: state => ({ x: state.x, y: mod(state.y - 1, modulus) }) },
    ],
  })

  assert.equal(atlas.certificate.reachableStates, 25)
  assert.equal(atlas.certificate.maxDistance, 4)
  assert.deepEqual(atlas.certificate.distanceHistogram, { 0: 1, 1: 4, 2: 8, 3: 8, 4: 4 })
  assert.deepEqual(verifyCanonicalNormalFormAtlas(atlas, state => `${state.x},${state.y}`), [])

  const normalized = normalizeGeneratorWord(
    atlas,
    state => `${state.x},${state.y}`,
    ['E', 'E', 'E', 'E', 'E', 'N', 'N', 'N', 'N', 'N', 'W'],
  )
  assert.ok(normalized.witness)
  assert.deepEqual(normalized.witness.canonicalWord, ['W'])
  assert.deepEqual(verifyNormalizationWitness(atlas, state => `${state.x},${state.y}`, normalized.witness), [])
})

test('normal-form verifier detects a noncanonical or incomplete certificate', () => {
  const modulus = 3
  const atlas = buildCanonicalNormalFormAtlas<TorusPoint>({
    initial: { x: 0, y: 0 },
    key: state => `${state.x},${state.y}`,
    generators: [
      { id: 'E', apply: state => ({ x: mod(state.x + 1, modulus), y: state.y }) },
      { id: 'N', apply: state => ({ x: state.x, y: mod(state.y + 1, modulus) }) },
      { id: 'W', apply: state => ({ x: mod(state.x - 1, modulus), y: state.y }) },
      { id: 'S', apply: state => ({ x: state.x, y: mod(state.y - 1, modulus) }) },
    ],
  })
  const mutated = {
    ...atlas,
    entries: atlas.entries.map(entry => ({ ...entry, word: [...entry.word] })),
    certificate: { ...atlas.certificate, distanceHistogram: { ...atlas.certificate.distanceHistogram } },
  }
  const target = mutated.entries.find(entry => entry.distance === 1 && entry.word[0] === 'E')
  assert.ok(target)
  target.word = ['N']
  assert.ok(verifyCanonicalNormalFormAtlas(mutated, state => `${state.x},${state.y}`).length > 0)
})
