export type LinearCongruenceSpec = {
  id: string
  sourceSemanticIds: string[]
  coefficient: string
  rhs: string
  modulus: string
}

export type ValuationWitness = {
  prime: string
  required: number
  available: number | 'infinity'
  satisfied: boolean
}

export type ValuationCongruenceDivisibilityChart = {
  kind: 'valuation-congruence-divisibility'
  sourceId: string
  sourceSemanticIds: string[]
  normalized: {
    coefficient: string
    rhs: string
    modulus: string
    gcd: string
  }
  equivalentStatements: string[]
  solvable: boolean
  baseSolution?: string
  solutionModulus?: string
  valuationWitnesses: ValuationWitness[]
  certificates: Array<{ claim: string; method: string; status: 'certified' }>
}

function abs(value: bigint): bigint { return value < 0n ? -value : value }

function gcd(left: bigint, right: bigint): bigint {
  let a = abs(left)
  let b = abs(right)
  while (b !== 0n) [a, b] = [b, a % b]
  return a
}

function extendedGcd(left: bigint, right: bigint): { gcd: bigint; x: bigint; y: bigint } {
  let oldR = left
  let r = right
  let oldS = 1n
  let s = 0n
  let oldT = 0n
  let t = 1n
  while (r !== 0n) {
    const quotient = oldR / r
    ;[oldR, r] = [r, oldR - quotient * r]
    ;[oldS, s] = [s, oldS - quotient * s]
    ;[oldT, t] = [t, oldT - quotient * t]
  }
  if (oldR < 0n) return { gcd: -oldR, x: -oldS, y: -oldT }
  return { gcd: oldR, x: oldS, y: oldT }
}

function canonical(value: bigint, modulus: bigint): bigint {
  return ((value % modulus) + modulus) % modulus
}

function parseInteger(value: string): bigint | null {
  return /^[+-]?\d+$/.test(value.trim()) ? BigInt(value.trim()) : null
}

function primeFactors(value: bigint): Array<{ prime: bigint; exponent: number }> {
  let remaining = abs(value)
  const factors: Array<{ prime: bigint; exponent: number }> = []
  let prime = 2n
  while (prime * prime <= remaining) {
    if (remaining % prime !== 0n) {
      prime = prime === 2n ? 3n : prime + 2n
      continue
    }
    let exponent = 0
    while (remaining % prime === 0n) {
      remaining /= prime
      exponent += 1
    }
    factors.push({ prime, exponent })
  }
  if (remaining > 1n) factors.push({ prime: remaining, exponent: 1 })
  return factors
}

function valuation(value: bigint, prime: bigint): number | 'infinity' {
  if (value === 0n) return 'infinity'
  let remaining = abs(value)
  let exponent = 0
  while (remaining % prime === 0n) {
    remaining /= prime
    exponent += 1
  }
  return exponent
}

export function buildValuationCongruenceDivisibilityChart(
  spec: LinearCongruenceSpec,
): { chart?: ValuationCongruenceDivisibilityChart; errors: string[] } {
  const coefficient = parseInteger(spec.coefficient)
  const rhs = parseInteger(spec.rhs)
  const rawModulus = parseInteger(spec.modulus)
  const errors: string[] = []
  if (!spec.id.trim()) errors.push('id is required')
  if (!spec.sourceSemanticIds.length) errors.push('sourceSemanticIds must not be empty')
  if (coefficient === null) errors.push('coefficient must be an integer')
  if (rhs === null) errors.push('rhs must be an integer')
  if (rawModulus === null || rawModulus === 0n) errors.push('modulus must be a nonzero integer')
  if (errors.length || coefficient === null || rhs === null || rawModulus === null || rawModulus === 0n) {
    return { errors }
  }

  const modulus = abs(rawModulus)
  const normalizedCoefficient = canonical(coefficient, modulus)
  const normalizedRhs = canonical(rhs, modulus)
  const divisor = gcd(normalizedCoefficient, modulus)
  const solvable = normalizedRhs % divisor === 0n
  const valuationWitnesses = primeFactors(divisor).map(({ prime, exponent }) => {
    const available = valuation(normalizedRhs, prime)
    return {
      prime: prime.toString(),
      required: exponent,
      available,
      satisfied: available === 'infinity' || available >= exponent,
    }
  })

  let baseSolution: string | undefined
  let solutionModulus: string | undefined
  if (solvable) {
    const reducedModulus = modulus / divisor
    const reducedCoefficient = normalizedCoefficient / divisor
    const reducedRhs = normalizedRhs / divisor
    const inverse = reducedModulus === 1n ? 0n : canonical(extendedGcd(reducedCoefficient, reducedModulus).x, reducedModulus)
    baseSolution = (reducedModulus === 1n ? 0n : canonical(inverse * reducedRhs, reducedModulus)).toString()
    solutionModulus = reducedModulus.toString()
  }

  const chart: ValuationCongruenceDivisibilityChart = {
    kind: 'valuation-congruence-divisibility',
    sourceId: spec.id,
    sourceSemanticIds: spec.sourceSemanticIds,
    normalized: {
      coefficient: normalizedCoefficient.toString(),
      rhs: normalizedRhs.toString(),
      modulus: modulus.toString(),
      gcd: divisor.toString(),
    },
    equivalentStatements: [
      `${normalizedCoefficient}x ≡ ${normalizedRhs} (mod ${modulus})`,
      `${modulus} divides (${normalizedCoefficient}x-${normalizedRhs})`,
      `${divisor} divides ${normalizedRhs}`,
      'for every prime p dividing the gcd, v_p(rhs) >= v_p(gcd)',
    ],
    solvable,
    baseSolution,
    solutionModulus,
    valuationWitnesses,
    certificates: [
      {
        claim: 'the congruence is solvable exactly when gcd(a,m) divides b',
        method: 'Bezout identity and exact integer divisibility',
        status: 'certified',
      },
      {
        claim: 'divisibility by the gcd is equivalent to all recorded prime-valuation inequalities',
        method: 'exact factorization of gcd(a,m)',
        status: 'certified',
      },
      ...(solvable ? [{
        claim: 'the base solution satisfies the original congruence',
        method: 'exact modular substitution',
        status: 'certified' as const,
      }] : []),
    ],
  }
  const verification = verifyValuationCongruenceDivisibilityChart(chart)
  return verification.certified ? { chart, errors: [] } : { errors: verification.errors }
}

export function verifyValuationCongruenceDivisibilityChart(
  chart: ValuationCongruenceDivisibilityChart,
): { certified: boolean; errors: string[] } {
  const errors: string[] = []
  const coefficient = BigInt(chart.normalized.coefficient)
  const rhs = BigInt(chart.normalized.rhs)
  const modulus = BigInt(chart.normalized.modulus)
  const divisor = gcd(coefficient, modulus)
  if (chart.kind !== 'valuation-congruence-divisibility') errors.push('wrong chart kind')
  if (!chart.sourceSemanticIds.length) errors.push('sourceSemanticIds must not be empty')
  if (modulus <= 0n) errors.push('normalized modulus must be positive')
  if (divisor.toString() !== chart.normalized.gcd) errors.push('gcd certificate is inconsistent')
  const solvable = rhs % divisor === 0n
  if (solvable !== chart.solvable) errors.push('solvability classification is inconsistent')
  const expectedWitnesses = primeFactors(divisor).map(({ prime, exponent }) => {
    const available = valuation(rhs, prime)
    return {
      prime: prime.toString(), required: exponent, available,
      satisfied: available === 'infinity' || available >= exponent,
    }
  })
  if (JSON.stringify(expectedWitnesses) !== JSON.stringify(chart.valuationWitnesses)) {
    errors.push('prime-valuation witnesses are inconsistent')
  }
  if (chart.solvable) {
    if (chart.baseSolution === undefined || chart.solutionModulus === undefined) {
      errors.push('solvable chart is missing its solution class')
    } else {
      const solution = BigInt(chart.baseSolution)
      const period = BigInt(chart.solutionModulus)
      if (period !== modulus / divisor) errors.push('solution modulus is inconsistent')
      if (canonical(coefficient * solution - rhs, modulus) !== 0n) {
        errors.push('base solution does not satisfy the congruence')
      }
    }
  } else if (chart.baseSolution !== undefined || chart.solutionModulus !== undefined) {
    errors.push('unsolvable chart must not contain a solution class')
  }
  return { certified: errors.length === 0, errors }
}
