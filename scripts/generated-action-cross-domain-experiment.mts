import { createHash } from 'node:crypto'
import { existsSync, readFileSync, renameSync, rmSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  solveCongruenceByGeneratedAction,
  solveRecurrenceByGeneratedAction,
} from '../lib/mortra/cross-domain/generated-action-adapters.js'
import type { FiniteRecurrenceSpec } from '../lib/mortra/diagram/finite-state-transition.js'

type Manifest = {
  benchmarkId: string
  frozenOn: string
  congruence: { minimumModulus: number; maximumModulus: number }
  affineRecurrenceOrderOne: { minimumModulus: number; maximumModulus: number }
}

type Case =
  | { domain: 'congruence'; modulus: number; coefficient: number; rhs: number }
  | { domain: 'recurrence'; modulus: number; coefficient: number; constant: number; initial: number; target: string }

type Counters = {
  congruenceTotal: number
  congruenceCertified: number
  congruenceSolvable: number
  recurrenceTotal: number
  recurrenceCertified: number
  wrongAnswers: number
  abstentions: number
  invalid: number
  totalReachableStates: number
  firstErrors: Array<{ index: number; domain: Case['domain']; detail: string[] }>
}

type Checkpoint = { digest: string; nextIndex: number; counters: Counters }

const scriptPath = fileURLToPath(import.meta.url)
const root = resolve(dirname(scriptPath), '..')
const manifestPath = resolve(root, 'data/generated-action-cross-domain-frozen-v1.json')
const resultPath = resolve(root, 'data/generated-action-cross-domain-benchmark-2026-08-27.json')
const checkpointPath = `${resultPath}.progress.json`
const manifestText = readFileSync(manifestPath, 'utf8')
const scriptText = readFileSync(scriptPath, 'utf8')
const manifest = JSON.parse(manifestText) as Manifest
const implementationText = [
  'lib/mortra/cross-domain/generated-action-adapters.ts',
  'lib/mortra/kernel/canonical-generator-normal-form.ts',
  'lib/mortra/chart/linear-recurrence-matrix.ts',
  'lib/mortra/chart/valuation-congruence-divisibility.ts',
].map(path => readFileSync(resolve(root, path), 'utf8')).join('\n')
const digest = createHash('sha256')
  .update(scriptText).update('\n').update(implementationText).update('\n').update(manifestText)
  .digest('hex')

function gcd(left: number, right: number): number {
  let a = Math.abs(left)
  let b = Math.abs(right)
  while (b) [a, b] = [b, a % b]
  return a
}

function bruteCongruence(coefficient: number, rhs: number, modulus: number) {
  for (let candidate = 0; candidate < modulus; candidate += 1) {
    if ((coefficient * candidate - rhs) % modulus === 0) {
      return { solvable: true, baseSolution: candidate, solutionModulus: modulus / gcd(coefficient, modulus) }
    }
  }
  return { solvable: false }
}

function directAffineRecurrence(
  coefficient: number,
  constant: number,
  initial: number,
  modulus: number,
  target: bigint,
): number {
  const values: number[] = []
  const seen = new Map<number, number>()
  let state = initial
  while (!seen.has(state)) {
    seen.set(state, values.length)
    values.push(state)
    state = (coefficient * state + constant) % modulus
  }
  const cycleStart = seen.get(state)!
  const cycleLength = values.length - cycleStart
  const reduced = target < BigInt(cycleStart)
    ? Number(target)
    : cycleStart + Number((target - BigInt(cycleStart)) % BigInt(cycleLength))
  return values[reduced]
}

function buildCases(): Case[] {
  const cases: Case[] = []
  for (let modulus = manifest.congruence.minimumModulus; modulus <= manifest.congruence.maximumModulus; modulus += 1) {
    for (let coefficient = 0; coefficient < modulus; coefficient += 1) {
      for (let rhs = 0; rhs < modulus; rhs += 1) cases.push({ domain: 'congruence', modulus, coefficient, rhs })
    }
  }
  for (
    let modulus = manifest.affineRecurrenceOrderOne.minimumModulus;
    modulus <= manifest.affineRecurrenceOrderOne.maximumModulus;
    modulus += 1
  ) {
    for (let coefficient = 0; coefficient < modulus; coefficient += 1) {
      for (let constant = 0; constant < modulus; constant += 1) {
        for (let initial = 0; initial < modulus; initial += 1) {
          const target = (1_000_000_000_000_000_000n
            + BigInt(coefficient * modulus * modulus + constant * modulus + initial)).toString()
          cases.push({ domain: 'recurrence', modulus, coefficient, constant, initial, target })
        }
      }
    }
  }
  return cases
}

function emptyCounters(): Counters {
  return {
    congruenceTotal: 0,
    congruenceCertified: 0,
    congruenceSolvable: 0,
    recurrenceTotal: 0,
    recurrenceCertified: 0,
    wrongAnswers: 0,
    abstentions: 0,
    invalid: 0,
    totalReachableStates: 0,
    firstErrors: [],
  }
}

function writeAtomic(path: string, value: unknown) {
  const temporary = `${path}.tmp`
  writeFileSync(temporary, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
  renameSync(temporary, path)
}

const cases = buildCases()
let checkpoint: Checkpoint = { digest, nextIndex: 0, counters: emptyCounters() }
if (existsSync(checkpointPath)) {
  const previous = JSON.parse(readFileSync(checkpointPath, 'utf8')) as Checkpoint
  if (previous.digest === digest && previous.nextIndex <= cases.length) checkpoint = previous
}

const startedAt = performance.now()
for (let index = checkpoint.nextIndex; index < cases.length; index += 1) {
  const item = cases[index]
  const failures: string[] = []
  if (item.domain === 'congruence') {
    checkpoint.counters.congruenceTotal += 1
    const result = solveCongruenceByGeneratedAction({
      id: `congruence-${index}`,
      sourceSemanticIds: ['frozen:integer'],
      coefficient: String(item.coefficient),
      rhs: String(item.rhs),
      modulus: String(item.modulus),
    }, item.modulus + 1)
    const expected = bruteCongruence(item.coefficient, item.rhs, item.modulus)
    if (result.status === 'certified') checkpoint.counters.congruenceCertified += 1
    else if (result.status === 'abstained') checkpoint.counters.abstentions += 1
    else checkpoint.counters.invalid += 1
    if (result.solvable) checkpoint.counters.congruenceSolvable += 1
    checkpoint.counters.totalReachableStates += result.atlas?.entries.length ?? 0
    if (result.solvable !== expected.solvable) failures.push('solvability mismatch')
    if (expected.solvable) {
      if (result.baseSolution !== String(expected.baseSolution)) failures.push('base solution mismatch')
      if (result.solutionModulus !== String(expected.solutionModulus)) failures.push('solution modulus mismatch')
    }
    failures.push(...result.errors)
  } else {
    checkpoint.counters.recurrenceTotal += 1
    const spec: FiniteRecurrenceSpec = {
      id: `recurrence-${index}`,
      sourceSemanticIds: ['frozen:recurrence'] as FiniteRecurrenceSpec['sourceSemanticIds'],
      modulus: item.modulus,
      initial: [item.initial],
      update: { terms: [
        { coefficient: item.coefficient, powers: [1] },
        { coefficient: item.constant, powers: [0] },
      ] },
      targetIndex: item.target,
    }
    const result = solveRecurrenceByGeneratedAction(spec, item.modulus + 1)
    const expected = directAffineRecurrence(
      item.coefficient,
      item.constant,
      item.initial,
      item.modulus,
      BigInt(item.target),
    )
    if (result.status === 'certified') checkpoint.counters.recurrenceCertified += 1
    else if (result.status === 'abstained') checkpoint.counters.abstentions += 1
    else checkpoint.counters.invalid += 1
    checkpoint.counters.totalReachableStates += result.atlas?.entries.length ?? 0
    if (result.answer !== expected) failures.push(`answer mismatch: expected ${expected}, received ${result.answer}`)
    failures.push(...result.errors)
  }
  if (failures.length) {
    checkpoint.counters.wrongAnswers += 1
    if (checkpoint.counters.firstErrors.length < 20) {
      checkpoint.counters.firstErrors.push({ index, domain: item.domain, detail: [...new Set(failures)] })
    }
  }
  checkpoint.nextIndex = index + 1
  if ((index + 1) % 500 === 0 || index + 1 === cases.length) writeAtomic(checkpointPath, checkpoint)
}
const elapsedMilliseconds = performance.now() - startedAt

const counters = checkpoint.counters
const total = cases.length
const result = {
  benchmarkId: manifest.benchmarkId,
  completedAt: new Date().toISOString(),
  digest,
  method: {
    model: 'symbolic only; no external LLM',
    totalCases: total,
    commonKernel: 'finite generated action with canonical shortest witnesses',
    domains: ['integer congruence', 'affine modular recurrence'],
    independentOracles: ['brute residue substitution', 'direct orbit/cycle reduction'],
    newMathSortDeclarations: 0,
    elapsedMilliseconds: Number(elapsedMilliseconds.toFixed(3)),
    timingClaim: 'diagnostic only; not a controlled speed benchmark',
  },
  results: {
    congruence: `${counters.congruenceCertified}/${counters.congruenceTotal}`,
    congruenceSolvable: counters.congruenceSolvable,
    recurrence: `${counters.recurrenceCertified}/${counters.recurrenceTotal}`,
    wrongAnswers: counters.wrongAnswers,
    abstentions: counters.abstentions,
    invalid: counters.invalid,
    totalReachableStatesReplayed: counters.totalReachableStates,
  },
  errors: counters.firstErrors,
  allClaimsPassed: counters.congruenceCertified === counters.congruenceTotal
    && counters.recurrenceCertified === counters.recurrenceTotal
    && counters.wrongAnswers === 0
    && counters.abstentions === 0
    && counters.invalid === 0,
  limitations: [
    'The recurrence cohort is order-one affine over small residue rings.',
    'The congruence cohort is linear and uses moduli at most 40.',
    'Explicit atlas enumeration is bounded and abstains for large state spaces.',
  ],
}

writeAtomic(resultPath, result)
if (existsSync(checkpointPath)) rmSync(checkpointPath)
console.log(JSON.stringify(result, null, 2))
if (!result.allClaimsPassed) process.exitCode = 1
