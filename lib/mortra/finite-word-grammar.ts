export type BinaryGenerator = 'L' | 'R'

export type ForbiddenWordTransition = {
  from: number
  to: number
  symbol: BinaryGenerator
}

export type ForbiddenWordAutomaton = {
  forbiddenWords: string[]
  states: string[]
  startState: number
  transitions: ForbiddenWordTransition[]
}

function validateWord(word: string): string {
  const normalized = word.toUpperCase()
  if (!/^[LR]{2,}$/.test(normalized)) {
    throw new Error('forbidden words must contain only L/R and have length at least two')
  }
  return normalized
}

function removeRedundantWords(words: string[]): string[] {
  return words.filter((word, index) =>
    !words.some((other, otherIndex) =>
      index !== otherIndex && word.includes(other)))
}

function swapSymbols(word: string): string {
  return [...word].map(symbol => symbol === 'L' ? 'R' : 'L').join('')
}

export function normalizeForbiddenWords(forbiddenWords: readonly string[]): string[] {
  if (!forbiddenWords.length) throw new Error('at least one forbidden word is required')
  const unique = [...new Set(forbiddenWords.map(validateWord))]
    .sort((left, right) => left.length - right.length || left.localeCompare(right))
  return removeRedundantWords(unique)
}

/**
 * L/R have no intrinsic names. A language and its mirror under L <-> R are
 * therefore one structural species.
 */
export function canonicalForbiddenWords(forbiddenWords: readonly string[]): string[] {
  const normalized = normalizeForbiddenWords(forbiddenWords)
  const mirrored = normalizeForbiddenWords(normalized.map(swapSymbols))
  const directKey = normalized.join(',')
  const mirroredKey = mirrored.join(',')
  return mirroredKey < directKey ? mirrored : normalized
}

export function buildForbiddenWordAutomaton(
  forbiddenWords: readonly string[],
): ForbiddenWordAutomaton {
  const normalized = normalizeForbiddenWords(forbiddenWords)
  const prefixes = new Set<string>([''])
  for (const word of normalized) {
    for (let length = 1; length < word.length; length += 1) {
      prefixes.add(word.slice(0, length))
    }
  }
  const states = [...prefixes].sort((left, right) =>
    left.length - right.length || left.localeCompare(right))
  const stateIndex = new Map(states.map((state, index) => [state, index]))
  const transitions: ForbiddenWordTransition[] = []

  for (const [from, state] of states.entries()) {
    for (const symbol of ['L', 'R'] as const) {
      const candidate = state + symbol
      if (normalized.some(word => candidate.endsWith(word))) continue
      const suffix = states
        .filter(prefix => candidate.endsWith(prefix))
        .sort((left, right) => right.length - left.length)[0]
      transitions.push({
        from,
        to: stateIndex.get(suffix) ?? 0,
        symbol,
      })
    }
  }

  return {
    forbiddenWords: normalized,
    states,
    startState: 0,
    transitions,
  }
}

export function acceptedBinaryWords(
  forbiddenWords: readonly string[],
  length: number,
): string[] {
  if (!Number.isSafeInteger(length) || length < 0) {
    throw new Error('word length must be a nonnegative safe integer')
  }
  const automaton = buildForbiddenWordAutomaton(forbiddenWords)
  let current = [{ word: '', state: automaton.startState }]
  for (let depth = 0; depth < length; depth += 1) {
    current = current.flatMap(item =>
      automaton.transitions
        .filter(transition => transition.from === item.state)
        .map(transition => ({
          word: item.word + transition.symbol,
          state: transition.to,
        })))
  }
  return current.map(item => item.word)
}
