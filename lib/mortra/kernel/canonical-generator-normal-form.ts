export type FiniteGenerator<State> = {
  id: string
  apply: (state: State) => State
}

export type CanonicalNormalFormEntry<State> = {
  key: string
  state: State
  distance: number
  word: string[]
}

export type CanonicalNormalFormCertificate = {
  generatorOrder: string[]
  reachableStates: number
  maxDistance: number
  distanceHistogram: Record<string, number>
  deterministicDigest: string
}

export type CanonicalNormalFormAtlas<State> = {
  initial: State
  initialKey: string
  generators: FiniteGenerator<State>[]
  entries: CanonicalNormalFormEntry<State>[]
  certificate: CanonicalNormalFormCertificate
}

export type NormalizationWitness = {
  originalWord: string[]
  canonicalWord: string[]
  reachedKey: string
  originalLength: number
  canonicalLength: number
}

type AtlasOptions<State> = {
  initial: State
  key: (state: State) => string
  generators: FiniteGenerator<State>[]
  maxStates?: number
}

function stableHash(text: string): string {
  let hash = 2166136261
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index)
    hash = Math.imul(hash, 16777619)
  }
  return (hash >>> 0).toString(16).padStart(8, '0')
}

function histogram(entries: CanonicalNormalFormEntry<unknown>[]): Record<string, number> {
  const result: Record<string, number> = {}
  for (const entry of entries) {
    const distance = String(entry.distance)
    result[distance] = (result[distance] ?? 0) + 1
  }
  return result
}

function digestEntries<State>(entries: CanonicalNormalFormEntry<State>[]): string {
  return stableHash(entries
    .map(entry => `${entry.key}:${entry.distance}:${entry.word.join('.')}`)
    .sort()
    .join('|'))
}

function validateGenerators<State>(generators: FiniteGenerator<State>[]): void {
  if (!generators.length) throw new Error('at least one generator is required')
  const ids = generators.map(generator => generator.id)
  if (ids.some(id => !id.trim())) throw new Error('generator ids must not be empty')
  if (new Set(ids).size !== ids.length) throw new Error('generator ids must be unique')
}

/**
 * Enumerate a finite generated action and retain the first BFS witness.
 * Queue order and generator order define a total, deterministic tie-break, so the
 * retained word is the lexicographically first shortest representative.
 */
export function buildCanonicalNormalFormAtlas<State>(
  options: AtlasOptions<State>,
): CanonicalNormalFormAtlas<State> {
  validateGenerators(options.generators)
  const maxStates = options.maxStates ?? 100_000
  if (!Number.isInteger(maxStates) || maxStates < 1) throw new Error('maxStates must be a positive integer')

  const initialKey = options.key(options.initial)
  const entries: CanonicalNormalFormEntry<State>[] = [{
    key: initialKey,
    state: options.initial,
    distance: 0,
    word: [],
  }]
  const seen = new Map<string, number>([[initialKey, 0]])

  for (let cursor = 0; cursor < entries.length; cursor += 1) {
    const current = entries[cursor]
    for (const generator of options.generators) {
      const next = generator.apply(current.state)
      const nextKey = options.key(next)
      if (seen.has(nextKey)) continue
      if (entries.length >= maxStates) {
        throw new Error(`generated action exceeded maxStates=${maxStates}`)
      }
      seen.set(nextKey, entries.length)
      entries.push({
        key: nextKey,
        state: next,
        distance: current.distance + 1,
        word: [...current.word, generator.id],
      })
    }
  }

  const maxDistance = entries.reduce((maximum, entry) => Math.max(maximum, entry.distance), 0)
  return {
    initial: options.initial,
    initialKey,
    generators: options.generators,
    entries,
    certificate: {
      generatorOrder: options.generators.map(generator => generator.id),
      reachableStates: entries.length,
      maxDistance,
      distanceHistogram: histogram(entries),
      deterministicDigest: digestEntries(entries),
    },
  }
}

function replay<State>(
  initial: State,
  word: string[],
  generators: Map<string, FiniteGenerator<State>>,
): { state?: State; error?: string } {
  let state = initial
  for (const id of word) {
    const generator = generators.get(id)
    if (!generator) return { error: `unknown generator ${id}` }
    state = generator.apply(state)
  }
  return { state }
}

/** Independently rebuild every shortest canonical witness and compare all fields. */
export function verifyCanonicalNormalFormAtlas<State>(
  atlas: CanonicalNormalFormAtlas<State>,
  key: (state: State) => string,
): string[] {
  const errors: string[] = []
  try {
    validateGenerators(atlas.generators)
  } catch (error) {
    errors.push(error instanceof Error ? error.message : String(error))
    return errors
  }

  if (key(atlas.initial) !== atlas.initialKey) errors.push('initial key does not match the initial state')
  const generatorMap = new Map(atlas.generators.map(generator => [generator.id, generator]))
  const entryByKey = new Map<string, CanonicalNormalFormEntry<State>>()
  for (const entry of atlas.entries) {
    if (entryByKey.has(entry.key)) errors.push(`duplicate state key ${entry.key}`)
    entryByKey.set(entry.key, entry)
    const replayed = replay(atlas.initial, entry.word, generatorMap)
    if (replayed.error) errors.push(replayed.error)
    else if (replayed.state === undefined || key(replayed.state) !== entry.key) errors.push(`path replay failed for ${entry.key}`)
    if (entry.distance !== entry.word.length) errors.push(`distance/path mismatch for ${entry.key}`)
  }

  let rebuilt: CanonicalNormalFormAtlas<State>
  try {
    rebuilt = buildCanonicalNormalFormAtlas({
      initial: atlas.initial,
      key,
      generators: atlas.generators,
      maxStates: Math.max(100_000, atlas.entries.length * (atlas.generators.length + 1)),
    })
  } catch (error) {
    errors.push(`independent atlas rebuild failed: ${error instanceof Error ? error.message : String(error)}`)
    return [...new Set(errors)]
  }
  if (rebuilt.entries.length !== atlas.entries.length) errors.push('reachable state count is not complete')
  for (const expected of rebuilt.entries) {
    const actual = entryByKey.get(expected.key)
    if (!actual) {
      errors.push(`missing reachable state ${expected.key}`)
      continue
    }
    if (actual.distance !== expected.distance) errors.push(`non-minimal distance for ${expected.key}`)
    if (actual.word.join('\u0000') !== expected.word.join('\u0000')) {
      errors.push(`non-canonical shortest witness for ${expected.key}`)
    }
  }

  const certificate = atlas.certificate
  if (certificate.generatorOrder.join('\u0000') !== atlas.generators.map(item => item.id).join('\u0000')) {
    errors.push('certificate generator order mismatch')
  }
  if (certificate.reachableStates !== atlas.entries.length) errors.push('certificate reachable-state count mismatch')
  const maxDistance = atlas.entries.reduce((maximum, entry) => Math.max(maximum, entry.distance), 0)
  if (certificate.maxDistance !== maxDistance) errors.push('certificate maximum distance mismatch')
  if (JSON.stringify(certificate.distanceHistogram) !== JSON.stringify(histogram(atlas.entries))) {
    errors.push('certificate distance histogram mismatch')
  }
  if (certificate.deterministicDigest !== digestEntries(atlas.entries)) {
    errors.push('certificate deterministic digest mismatch')
  }
  return [...new Set(errors)]
}

export function normalizeGeneratorWord<State>(
  atlas: CanonicalNormalFormAtlas<State>,
  key: (state: State) => string,
  word: string[],
): { witness?: NormalizationWitness; errors: string[] } {
  const generators = new Map(atlas.generators.map(generator => [generator.id, generator]))
  const result = replay(atlas.initial, word, generators)
  if (result.error || result.state === undefined) return { errors: [result.error ?? 'word replay failed'] }
  const reachedKey = key(result.state)
  const canonical = atlas.entries.find(entry => entry.key === reachedKey)
  if (!canonical) return { errors: [`word reached state outside certified atlas: ${reachedKey}`] }
  return {
    witness: {
      originalWord: [...word],
      canonicalWord: [...canonical.word],
      reachedKey,
      originalLength: word.length,
      canonicalLength: canonical.word.length,
    },
    errors: [],
  }
}

export function verifyNormalizationWitness<State>(
  atlas: CanonicalNormalFormAtlas<State>,
  key: (state: State) => string,
  witness: NormalizationWitness,
): string[] {
  const errors: string[] = []
  const generators = new Map(atlas.generators.map(generator => [generator.id, generator]))
  const original = replay(atlas.initial, witness.originalWord, generators)
  const canonical = replay(atlas.initial, witness.canonicalWord, generators)
  if (original.error) errors.push(original.error)
  if (canonical.error) errors.push(canonical.error)
  if (original.state !== undefined && key(original.state) !== witness.reachedKey) {
    errors.push('original word reached-key mismatch')
  }
  if (canonical.state !== undefined && key(canonical.state) !== witness.reachedKey) {
    errors.push('canonical word changed the action')
  }
  if (witness.originalLength !== witness.originalWord.length) errors.push('original length mismatch')
  if (witness.canonicalLength !== witness.canonicalWord.length) errors.push('canonical length mismatch')
  const certified = atlas.entries.find(entry => entry.key === witness.reachedKey)
  if (!certified) errors.push('witness target is absent from the atlas')
  else if (certified.word.join('\u0000') !== witness.canonicalWord.join('\u0000')) {
    errors.push('witness is not the certified canonical shortest word')
  }
  return [...new Set(errors)]
}
