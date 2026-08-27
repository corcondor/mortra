import {
  buildLinearRecurrenceMatrixChart,
  solveWithLinearRecurrenceMatrix,
  verifyLinearRecurrenceMatrixChart,
  type LinearRecurrenceMatrixChart,
  type ModularMatrix,
} from '../chart/linear-recurrence-matrix'
import {
  buildValuationCongruenceDivisibilityChart,
  verifyValuationCongruenceDivisibilityChart,
  type LinearCongruenceSpec,
  type ValuationCongruenceDivisibilityChart,
} from '../chart/valuation-congruence-divisibility'
import type { FiniteRecurrenceSpec } from '../diagram/finite-state-transition'
import {
  buildCanonicalNormalFormAtlas,
  verifyCanonicalNormalFormAtlas,
  type CanonicalNormalFormAtlas,
} from '../kernel/canonical-generator-normal-form'

export type RecurrenceGeneratedActionSolution = {
  status: 'certified' | 'abstained' | 'invalid'
  answer?: number
  errors: string[]
  chart?: LinearRecurrenceMatrixChart
  atlas?: CanonicalNormalFormAtlas<number[]>
  orbit?: {
    preperiod: number
    period: number
    targetIndex: string
    reducedIndex: number
  }
}

export type CongruenceGeneratedActionSolution = {
  status: 'certified' | 'abstained' | 'invalid'
  solvable?: boolean
  baseSolution?: string
  solutionModulus?: string
  errors: string[]
  chart?: ValuationCongruenceDivisibilityChart
  atlas?: CanonicalNormalFormAtlas<number>
  targetReachable?: boolean
}

function canonical(value: number, modulus: number): number {
  return ((value % modulus) + modulus) % modulus
}

function multiplyMod(left: number, right: number, modulus: number): number {
  return Number((BigInt(left) * BigInt(right)) % BigInt(modulus))
}

function addMod(left: number, right: number, modulus: number): number {
  return Number((BigInt(left) + BigInt(right)) % BigInt(modulus))
}

function applyMatrix(matrix: ModularMatrix, state: number[], modulus: number): number[] {
  return matrix.map(row => row.reduce(
    (sum, coefficient, index) => addMod(sum, multiplyMod(coefficient, state[index], modulus), modulus),
    0,
  ))
}

function vectorKey(state: number[]): string {
  return state.join(',')
}

function parseNonnegativeInteger(value: string): bigint | null {
  return /^\d+$/.test(value.trim()) ? BigInt(value.trim()) : null
}

function reduceOrbitIndex(target: bigint, preperiod: number, period: number): number {
  if (target < BigInt(preperiod)) return Number(target)
  return preperiod + Number((target - BigInt(preperiod)) % BigInt(period))
}

/**
 * Treat a modular affine recurrence as the action of one generator T on its
 * homogeneous state. This is the same finite-action interface used by geometry.
 */
export function solveRecurrenceByGeneratedAction(
  spec: FiniteRecurrenceSpec,
  maxStates = 100_000,
): RecurrenceGeneratedActionSolution {
  const built = buildLinearRecurrenceMatrixChart(spec)
  if (!built.chart) {
    return {
      status: built.errors.some(error => error.includes('nonlinear')) ? 'abstained' : 'invalid',
      errors: built.errors,
    }
  }
  const target = parseNonnegativeInteger(spec.targetIndex)
  if (target === null) return { status: 'invalid', errors: ['targetIndex must be a nonnegative integer'] }
  const chart = built.chart
  const initial = [...chart.normalForm.initial, 1]
  let atlas: CanonicalNormalFormAtlas<number[]>
  try {
    atlas = buildCanonicalNormalFormAtlas({
      initial,
      key: vectorKey,
      generators: [{
        id: 'T',
        apply: state => applyMatrix(chart.transitionMatrix, state, chart.normalForm.modulus),
      }],
      maxStates,
    })
  } catch (error) {
    return {
      status: 'abstained',
      errors: [error instanceof Error ? error.message : String(error)],
      chart,
    }
  }

  const errors = verifyCanonicalNormalFormAtlas(atlas, vectorKey)
  const last = atlas.entries[atlas.entries.length - 1]
  const repeated = applyMatrix(chart.transitionMatrix, last.state, chart.normalForm.modulus)
  const cycleStart = atlas.entries.findIndex(entry => entry.key === vectorKey(repeated))
  if (cycleStart < 0) errors.push('orbit did not close inside the certified atlas')
  const period = cycleStart < 0 ? 0 : atlas.entries.length - cycleStart
  if (period <= 0) errors.push('orbit period must be positive')
  const reducedIndex = period > 0 ? reduceOrbitIndex(target, cycleStart, period) : 0
  const answer = atlas.entries[reducedIndex]?.state[0]
  if (answer === undefined) errors.push('reduced target is absent from the orbit atlas')

  const matrixSolution = solveWithLinearRecurrenceMatrix(spec)
  if (matrixSolution.status !== 'certified' || matrixSolution.answer !== answer) {
    errors.push('generated-action answer disagrees with independent matrix exponentiation')
  }
  if (!verifyLinearRecurrenceMatrixChart(chart).certified) errors.push('recurrence chart certificate failed')
  return {
    status: errors.length ? 'invalid' : 'certified',
    answer,
    errors: [...new Set(errors)],
    chart,
    atlas,
    orbit: {
      preperiod: Math.max(0, cycleStart),
      period,
      targetIndex: spec.targetIndex,
      reducedIndex,
    },
  }
}

/**
 * Interpret ax=b (mod m) as reachability of b from 0 under the single action
 * x |-> x+a. The shortest generator word is the canonical base solution.
 */
export function solveCongruenceByGeneratedAction(
  spec: LinearCongruenceSpec,
  maxStates = 100_000,
): CongruenceGeneratedActionSolution {
  const built = buildValuationCongruenceDivisibilityChart(spec)
  if (!built.chart) return { status: 'invalid', errors: built.errors }
  const chart = built.chart
  const modulusBig = BigInt(chart.normalized.modulus)
  const coefficientBig = BigInt(chart.normalized.coefficient)
  const rhsBig = BigInt(chart.normalized.rhs)
  if (modulusBig > BigInt(Number.MAX_SAFE_INTEGER)) {
    return { status: 'abstained', errors: ['modulus exceeds exact Number state representation'], chart }
  }
  const modulus = Number(modulusBig)
  const coefficient = Number(coefficientBig)
  const rhs = Number(rhsBig)
  let atlas: CanonicalNormalFormAtlas<number>
  try {
    atlas = buildCanonicalNormalFormAtlas({
      initial: 0,
      key: state => String(state),
      generators: [{
        id: 'add-coefficient',
        apply: state => Number((BigInt(state) + coefficientBig) % modulusBig),
      }],
      maxStates,
    })
  } catch (error) {
    return {
      status: 'abstained',
      errors: [error instanceof Error ? error.message : String(error)],
      chart,
    }
  }

  const errors = verifyCanonicalNormalFormAtlas(atlas, state => String(state))
  const target = atlas.entries.find(entry => entry.state === rhs)
  const targetReachable = target !== undefined
  if (targetReachable !== chart.solvable) errors.push('action reachability disagrees with gcd/valuation solvability')
  if (atlas.entries.length !== Number(modulusBig / BigInt(chart.normalized.gcd))) {
    errors.push('orbit size disagrees with the additive subgroup index')
  }

  const baseSolution = target?.distance.toString()
  const solutionModulus = atlas.entries.length.toString()
  if (chart.solvable) {
    if (baseSolution !== chart.baseSolution) errors.push('shortest action word disagrees with the Bezout base solution')
    if (solutionModulus !== chart.solutionModulus) errors.push('action period disagrees with the congruence solution modulus')
  }
  if (!verifyValuationCongruenceDivisibilityChart(chart).certified) errors.push('valuation chart certificate failed')

  return {
    status: errors.length ? 'invalid' : 'certified',
    solvable: targetReachable,
    baseSolution: targetReachable ? baseSolution : undefined,
    solutionModulus: targetReachable ? solutionModulus : undefined,
    errors: [...new Set(errors)],
    chart,
    atlas,
    targetReachable,
  }
}
