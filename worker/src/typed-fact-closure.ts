/**
 * Finite typed predicate closure with proof provenance.
 *
 * The engine is deliberately domain-independent. Geometry, arithmetic,
 * probability, and topology contribute predicate schemas and sound rules;
 * saturation, type checking, deduplication, and traceback are shared.
 */

export type TypedTerm = {
  id: string
  sort: string
  depth?: number
}

export type PredicateSchema = {
  name: string
  argumentSorts: string[]
  symmetric?: boolean
}

export type PredicateFact = {
  predicate: string
  args: string[]
  provenance: string[]
}

export type PatternArgument =
  | { variable: string; sort?: string }
  | { constant: string }

export type PredicatePattern = {
  predicate: string
  args: PatternArgument[]
}

export type PredicateRule = {
  id: string
  premises: PredicatePattern[]
  conclusion: PredicatePattern
}

export type FactDerivation = {
  fact: PredicateFact
  rule: string | null
  premises: string[]
  round: number
}

export type TypedClosureProgram = {
  terms: TypedTerm[]
  schemas: PredicateSchema[]
  facts: PredicateFact[]
  rules: PredicateRule[]
  goal?: Omit<PredicateFact, 'provenance'>
  maxRounds?: number
  maxFacts?: number
}

export type TypedClosureCertificate = {
  status: 'proved' | 'unproved' | 'invalid' | 'truncated'
  goalKey: string | null
  facts: PredicateFact[]
  proof: FactDerivation[]
  rounds: number
  diagnostics: string[]
}

type Binding = Map<string, string>

function canonicalArgs(schema: PredicateSchema, args: string[]): string[] {
  return schema.symmetric ? [...args].sort() : [...args]
}

function factKey(schema: PredicateSchema, fact: Pick<PredicateFact, 'predicate' | 'args'>): string {
  return `${fact.predicate}(${canonicalArgs(schema, fact.args).join(',')})`
}

function patternVariables(pattern: PredicatePattern): string[] {
  return pattern.args.flatMap(argument => 'variable' in argument ? [argument.variable] : [])
}

function validatePattern(
  pattern: PredicatePattern,
  schemas: Map<string, PredicateSchema>,
  diagnostics: string[],
  label: string,
): boolean {
  const schema = schemas.get(pattern.predicate)
  if (!schema) {
    diagnostics.push(`${label}: unknown predicate ${pattern.predicate}`)
    return false
  }
  if (schema.argumentSorts.length !== pattern.args.length) {
    diagnostics.push(`${label}: ${pattern.predicate} expects ${schema.argumentSorts.length} arguments`)
    return false
  }
  pattern.args.forEach((argument, index) => {
    if ('variable' in argument && argument.sort && argument.sort !== schema.argumentSorts[index]) {
      diagnostics.push(`${label}: variable ${argument.variable} has sort ${argument.sort}, expected ${schema.argumentSorts[index]}`)
    }
  })
  return true
}

function validateFact(
  fact: PredicateFact,
  terms: Map<string, TypedTerm>,
  schemas: Map<string, PredicateSchema>,
  diagnostics: string[],
  label: string,
): boolean {
  const schema = schemas.get(fact.predicate)
  if (!schema) {
    diagnostics.push(`${label}: unknown predicate ${fact.predicate}`)
    return false
  }
  if (schema.argumentSorts.length !== fact.args.length) {
    diagnostics.push(`${label}: ${fact.predicate} expects ${schema.argumentSorts.length} arguments`)
    return false
  }
  let valid = true
  fact.args.forEach((argument, index) => {
    const term = terms.get(argument)
    if (!term) {
      diagnostics.push(`${label}: unknown term ${argument}`)
      valid = false
    } else if (term.sort !== schema.argumentSorts[index]) {
      diagnostics.push(`${label}: term ${argument} has sort ${term.sort}, expected ${schema.argumentSorts[index]}`)
      valid = false
    }
  })
  return valid
}

function bindPattern(
  pattern: PredicatePattern,
  fact: PredicateFact,
  binding: Binding,
  terms: Map<string, TypedTerm>,
): Binding | null {
  if (pattern.predicate !== fact.predicate || pattern.args.length !== fact.args.length) return null
  const next = new Map(binding)
  for (let index = 0; index < pattern.args.length; index++) {
    const expected = pattern.args[index]
    const actual = fact.args[index]
    if ('constant' in expected) {
      if (expected.constant !== actual) return null
      continue
    }
    if (expected.sort && terms.get(actual)?.sort !== expected.sort) return null
    const prior = next.get(expected.variable)
    if (prior && prior !== actual) return null
    next.set(expected.variable, actual)
  }
  return next
}

function instantiate(pattern: PredicatePattern, binding: Binding): PredicateFact | null {
  const args: string[] = []
  for (const argument of pattern.args) {
    if ('constant' in argument) args.push(argument.constant)
    else {
      const value = binding.get(argument.variable)
      if (!value) return null
      args.push(value)
    }
  }
  return { predicate: pattern.predicate, args, provenance: [] }
}

function matchesForRule(
  rule: PredicateRule,
  facts: PredicateFact[],
  terms: Map<string, TypedTerm>,
  schemas: Map<string, PredicateSchema>,
): Array<{ binding: Binding; premises: PredicateFact[] }> {
  let states: Array<{ binding: Binding; premises: PredicateFact[] }> = [{ binding: new Map(), premises: [] }]
  for (const premise of rule.premises) {
    const next: typeof states = []
    for (const state of states) {
      for (const fact of facts) {
        const variants = schemas.get(fact.predicate)?.symmetric && fact.args.length === 2
          ? [fact, { ...fact, args: [fact.args[1], fact.args[0]] }]
          : [fact]
        for (const variant of variants) {
          const binding = bindPattern(premise, variant, state.binding, terms)
          if (binding) next.push({ binding, premises: [...state.premises, fact] })
        }
      }
    }
    states = next
    if (!states.length) break
  }
  return states
}

export function executeTypedFactClosure(program: TypedClosureProgram): TypedClosureCertificate {
  const diagnostics: string[] = []
  const terms = new Map(program.terms.map(term => [term.id, term]))
  const schemas = new Map(program.schemas.map(schema => [schema.name, schema]))
  if (terms.size !== program.terms.length) diagnostics.push('duplicate term id')
  if (schemas.size !== program.schemas.length) diagnostics.push('duplicate predicate schema')
  program.rules.forEach(rule => {
    rule.premises.forEach((premise, index) => validatePattern(premise, schemas, diagnostics, `${rule.id}.premise.${index}`))
    validatePattern(rule.conclusion, schemas, diagnostics, `${rule.id}.conclusion`)
    const bound = new Set(rule.premises.flatMap(patternVariables))
    for (const variable of patternVariables(rule.conclusion)) {
      if (!bound.has(variable)) diagnostics.push(`${rule.id}: unbound conclusion variable ${variable}`)
    }
  })
  program.facts.forEach((fact, index) => validateFact(fact, terms, schemas, diagnostics, `fact.${index}`))
  if (program.goal) validateFact({ ...program.goal, provenance: [] }, terms, schemas, diagnostics, 'goal')
  if (diagnostics.length) {
    return { status: 'invalid', goalKey: null, facts: [], proof: [], rounds: 0, diagnostics }
  }

  const factsByKey = new Map<string, PredicateFact>()
  const derivations = new Map<string, FactDerivation>()
  for (const input of program.facts) {
    const schema = schemas.get(input.predicate)!
    const fact = { ...input, args: canonicalArgs(schema, input.args) }
    const key = factKey(schema, fact)
    if (!factsByKey.has(key)) {
      factsByKey.set(key, fact)
      derivations.set(key, { fact, rule: null, premises: [], round: 0 })
    }
  }

  const maxRounds = program.maxRounds ?? 32
  const maxFacts = program.maxFacts ?? 10_000
  let truncated = false
  let rounds = 0
  for (let round = 1; round <= maxRounds; round++) {
    let changed = false
    const snapshot = [...factsByKey.values()]
    for (const rule of program.rules) {
      for (const match of matchesForRule(rule, snapshot, terms, schemas)) {
        const raw = instantiate(rule.conclusion, match.binding)
        if (!raw) continue
        const schema = schemas.get(raw.predicate)!
        const premiseKeys = match.premises.map(fact => factKey(schemas.get(fact.predicate)!, fact))
        const fact: PredicateFact = {
          ...raw,
          args: canonicalArgs(schema, raw.args),
          provenance: [...new Set(match.premises.flatMap(item => item.provenance).concat(rule.id))].sort(),
        }
        const key = factKey(schema, fact)
        if (factsByKey.has(key)) continue
        factsByKey.set(key, fact)
        derivations.set(key, { fact, rule: rule.id, premises: premiseKeys, round })
        changed = true
        if (factsByKey.size >= maxFacts) {
          truncated = true
          break
        }
      }
      if (truncated) break
    }
    rounds = round
    if (truncated || !changed) break
  }

  let goalKey: string | null = null
  if (program.goal) {
    const schema = schemas.get(program.goal.predicate)!
    goalKey = factKey(schema, program.goal)
  }
  const status = truncated ? 'truncated' : goalKey && factsByKey.has(goalKey) ? 'proved' : 'unproved'
  const needed = new Set<string>()
  const visit = (key: string) => {
    if (needed.has(key)) return
    needed.add(key)
    derivations.get(key)?.premises.forEach(visit)
  }
  if (status === 'proved' && goalKey) visit(goalKey)
  const proof = [...needed]
    .map(key => derivations.get(key)!)
    .sort((left, right) => left.round - right.round || factKey(schemas.get(left.fact.predicate)!, left.fact).localeCompare(factKey(schemas.get(right.fact.predicate)!, right.fact)))
  return { status, goalKey, facts: [...factsByKey.values()], proof, rounds, diagnostics }
}

export const EQUALITY_TRANSITIVITY_RULE: PredicateRule = {
  id: 'equality-transitivity',
  premises: [
    { predicate: 'Equal', args: [{ variable: 'x' }, { variable: 'y' }] },
    { predicate: 'Equal', args: [{ variable: 'y' }, { variable: 'z' }] },
  ],
  conclusion: { predicate: 'Equal', args: [{ variable: 'x' }, { variable: 'z' }] },
}
