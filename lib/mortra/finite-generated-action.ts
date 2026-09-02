export type FiniteOrbit<S> = {
  states: S[]
  cycleOffset: number
  cycleStart: number
  repeatAt: number
  period: number
  transitionsEvaluated: number
}

export type FiniteOrbitOptions<S> = {
  initial: S
  next: (state: S) => S
  key: (state: S) => string
  startIndex?: number
  maxStates?: number
}

/**
 * Enumerate the reachable part of a deterministic finite action. The kernel
 * knows nothing about recurrences, trigonometry, Pell equations, or congruences;
 * those domains only provide a state, an action, and an equality key.
 */
export function enumerateFiniteOrbit<S>(options: FiniteOrbitOptions<S>): FiniteOrbit<S> | null {
  const startIndex = options.startIndex ?? 0
  const maxStates = options.maxStates ?? 250_000
  if (!Number.isSafeInteger(startIndex) || startIndex < 0) throw new Error('startIndex must be a non-negative safe integer')
  if (!Number.isSafeInteger(maxStates) || maxStates < 1) throw new Error('maxStates must be a positive safe integer')

  const states: S[] = []
  const seen = new Map<string, number>()
  let state = options.initial
  let transitionsEvaluated = 0

  for (;;) {
    const key = options.key(state)
    const cycleOffset = seen.get(key)
    if (cycleOffset !== undefined) {
      return {
        states,
        cycleOffset,
        cycleStart: startIndex + cycleOffset,
        repeatAt: startIndex + states.length,
        period: states.length - cycleOffset,
        transitionsEvaluated,
      }
    }
    if (states.length >= maxStates) return null
    seen.set(key, states.length)
    states.push(state)
    state = options.next(state)
    transitionsEvaluated += 1
  }
}

export function divisors(value: number): number[] {
  if (!Number.isSafeInteger(value) || value < 1) throw new Error('value must be a positive safe integer')
  const small: number[] = []
  const large: number[] = []
  for (let divisor = 1; divisor * divisor <= value; divisor += 1) {
    if (value % divisor !== 0) continue
    small.push(divisor)
    if (divisor * divisor !== value) large.push(value / divisor)
  }
  return [...small, ...large.reverse()]
}

/** Find the least period of one complete cyclic observation. */
export function minimalDivisorPeriod<T>(
  cycle: readonly T[],
  equal: (left: T, right: T) => boolean = Object.is,
): number {
  if (!cycle.length) throw new Error('cycle must not be empty')
  for (const period of divisors(cycle.length)) {
    if (cycle.every((value, index) => equal(value, cycle[(index + period) % cycle.length]))) {
      return period
    }
  }
  return cycle.length
}

/**
 * Move the start of an already certified periodic observation as far left as
 * possible. This keeps transient state handling separate from domain logic.
 */
export function minimalPeriodicStart<T>(options: {
  stateCycleStart: number
  observablePeriod: number
  verificationLength?: number
  minimumStart?: number
  valueAt: (index: number) => T
  equal?: (left: T, right: T) => boolean
}): number {
  const equal = options.equal ?? Object.is
  const verificationLength = options.verificationLength ?? options.observablePeriod
  const minimumStart = options.minimumStart ?? 0
  for (let candidate = minimumStart; candidate <= options.stateCycleStart; candidate += 1) {
    let valid = true
    for (
      let index = candidate;
      index < options.stateCycleStart + verificationLength;
      index += 1
    ) {
      if (!equal(options.valueAt(index), options.valueAt(index + options.observablePeriod))) {
        valid = false
        break
      }
    }
    if (valid) return candidate
  }
  return options.stateCycleStart
}
