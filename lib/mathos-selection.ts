import { createHash } from 'node:crypto'

export type SelectableMathOSProblem = {
  structureKey: string
  domain: string
}

const DOMAIN_ALIASES: Record<string, string[]> = {
  algebra: ['algebra', '代数', '方程式', '多項式'],
  geometry: ['geometry', '幾何', '図形'],
  number_theory: ['number_theory', '整数', '数論', '素数', '合同'],
  probability: ['probability', '確率', '期待値'],
  analysis: ['analysis', '解析', '微分', '積分', '極限'],
  linear_algebra: ['linear_algebra', '線形代数', '行列'],
  combinatorics: ['combinatorics', '組合せ', '数え上げ'],
  complex: ['complex', '複素数'],
}

export function canonicalDomain(input?: string): string | undefined {
  if (!input) return undefined
  const normalized = input.trim().toLowerCase()
  if (
    !normalized ||
    normalized === 'おまかせ' ||
    normalized === 'any' ||
    normalized === 'all'
  ) {
    return undefined
  }
  for (const [canonical, aliases] of Object.entries(DOMAIN_ALIASES)) {
    if (
      canonical === normalized ||
      aliases.some((alias) => alias.toLowerCase() === normalized)
    ) {
      return canonical
    }
  }
  return normalized
}

export function domainMatches(
  problemDomain: string,
  requested?: string,
): boolean {
  const canonical = canonicalDomain(requested)
  if (!canonical) return true
  const normalized = problemDomain.toLowerCase()
  if (canonical === 'geometry') return normalized.includes('geometry')
  if (canonical === 'algebra') return normalized.includes('algebra')
  if (canonical === 'analysis') return normalized.includes('analysis')
  if (canonical === 'number_theory') {
    return normalized.includes('number_theory')
  }
  if (canonical === 'linear_algebra') {
    return normalized.includes('linear_algebra')
  }
  if (canonical === 'combinatorics') {
    return normalized.includes('combinatorics')
  }
  if (canonical === 'complex') return normalized.includes('complex')
  if (canonical === 'probability') return normalized.includes('probability')
  return normalized === canonical
}

export function structureKeyFromRecord(problem: {
  family_id: string
  structure_key?: string
  lift_certificate: {
    morphism_chain?: string[]
    constraint_skeleton?: unknown
    query_signature?: unknown
  }
}): string {
  if (problem.structure_key) return problem.structure_key
  const payload = {
    family_id: problem.family_id,
    morphism_chain: problem.lift_certificate.morphism_chain ?? [],
    constraint_skeleton:
      problem.lift_certificate.constraint_skeleton ?? [],
    query_signature: problem.lift_certificate.query_signature ?? '',
  }
  return createHash('sha256')
    .update(JSON.stringify(payload))
    .digest('hex')
}

export function orderForInteraction<T extends SelectableMathOSProblem>(
  problems: T[],
  interactionId: string,
): T[] {
  return [...problems].sort((left, right) => {
    const leftRank = createHash('sha256')
      .update(`${interactionId}:${left.structureKey}`)
      .digest('hex')
    const rightRank = createHash('sha256')
      .update(`${interactionId}:${right.structureKey}`)
      .digest('hex')
    return leftRank.localeCompare(rightRank)
  })
}

