import { createHash } from 'node:crypto'

export type MathTokenKind =
  | 'command'
  | 'identifier'
  | 'number'
  | 'keyword'
  | 'particle'
  | 'relation'
  | 'delimiter'
  | 'punctuation'
  | 'text'

export type MathToken = {
  kind: MathTokenKind
  value: string
  start: number
  end: number
}

export type QuantifierSyntax = {
  kind: 'forall' | 'exists'
  variable: string | null
  clause: number
  start: number
  end: number
}

export type DefinitionSyntax = {
  symbol: string
  body: string
  clause: number
  start: number
  end: number
}

export type QuerySyntax = {
  kind: 'compute' | 'prove' | 'classify' | 'optimize' | 'measure' | 'observe'
  clause: number
}

export type ClauseSyntax = {
  id: number
  raw: string
  tokens: MathToken[]
  quantifiers: QuantifierSyntax[]
  definitions: DefinitionSyntax[]
  query: QuerySyntax | null
}

export type DocumentSyntax = {
  clauses: ClauseSyntax[]
  attachment_order: Array<{ modifier_clause: number; head_clause: number }>
}

export type MathematicalParseForest = {
  tokens: MathToken[]
  analyses: DocumentSyntax[]
  truncated: boolean
  diagnostics: string[]
}

export type ElaboratedDefinition = DefinitionSyntax & {
  id: string
  canonical: string
  inferred_sort: string
  dependencies: string[]
}

export type ElaboratedMathematicalIR = {
  selected_analysis: number
  definitions: ElaboratedDefinition[]
  quantifiers: QuantifierSyntax[]
  quantifier_prefix: string[]
  query: QuerySyntax | null
  free_symbols: string[]
  bound_symbols: string[]
  unresolved_references: string[]
  diagnostics: string[]
}

const PARTICLES = ['に対して', 'について', 'によって', 'において', 'として', 'から', 'まで', 'より', 'ならば', 'とき', 'ので', 'を', 'が', 'は', 'の', 'に', 'で', 'と']
const KEYWORDS = [
  'すべて', '全て', '任意', '存在する', '存在し', '満たす', '定める', '定義する',
  'とする', '求めよ', '示せ', '証明せよ', '分類せよ', '最大値', '最小値',
]
const MULTI_RELATIONS = ['<=>', '=>', '<=', '>=', '!=', '==', '≦', '≧', '≠', '∈', '⊂', '⊆', '→', '↦']

function hash(value: unknown, length = 12): string {
  return createHash('sha256').update(JSON.stringify(value)).digest('hex').slice(0, length)
}

function startsWithOneOf(text: string, index: number, values: string[]): string | null {
  for (const value of values.sort((left, right) => right.length - left.length)) {
    if (text.startsWith(value, index)) return value
  }
  return null
}

function isAsciiIdentifierStart(char: string): boolean {
  return /[A-Za-zα-ωΑ-Ω]/u.test(char)
}

function isAsciiIdentifierPart(char: string): boolean {
  return /[A-Za-z0-9_α-ωΑ-Ω]/u.test(char)
}

export function lexMathematicalText(text: string): MathToken[] {
  const tokens: MathToken[] = []
  let index = 0
  while (index < text.length) {
    const char = text[index]
    if (/\s/u.test(char)) {
      index++
      continue
    }
    if (char === '\\') {
      let end = index + 1
      if (/[A-Za-z]/.test(text[end] ?? '')) {
        while (end < text.length && /[A-Za-z]/.test(text[end])) end++
      } else {
        end = Math.min(text.length, end + 1)
      }
      tokens.push({ kind: 'command', value: text.slice(index, end), start: index, end })
      index = end
      continue
    }
    const phrase = startsWithOneOf(text, index, [...KEYWORDS, ...PARTICLES])
    if (phrase) {
      tokens.push({
        kind: PARTICLES.includes(phrase) ? 'particle' : 'keyword',
        value: phrase,
        start: index,
        end: index + phrase.length,
      })
      index += phrase.length
      continue
    }
    const relation = startsWithOneOf(text, index, MULTI_RELATIONS)
    if (relation || '=<>'.includes(char)) {
      const value = relation ?? char
      tokens.push({ kind: 'relation', value, start: index, end: index + value.length })
      index += value.length
      continue
    }
    if (isAsciiIdentifierStart(char)) {
      let end = index + 1
      while (end < text.length && isAsciiIdentifierPart(text[end])) end++
      if (text[end] === '_' && text[end + 1] === '{') {
        end += 2
        while (end < text.length && text[end] !== '}') end++
        if (text[end] === '}') end++
      }
      tokens.push({ kind: 'identifier', value: text.slice(index, end), start: index, end })
      index = end
      continue
    }
    if (/\d/.test(char)) {
      let end = index + 1
      while (end < text.length && /[\d.]/.test(text[end])) end++
      tokens.push({ kind: 'number', value: text.slice(index, end), start: index, end })
      index = end
      continue
    }
    if ('{}()[]$'.includes(char)) {
      tokens.push({ kind: 'delimiter', value: char, start: index, end: index + 1 })
      index++
      continue
    }
    if ('。、，,.;；:：'.includes(char)) {
      tokens.push({ kind: 'punctuation', value: char, start: index, end: index + 1 })
      index++
      continue
    }
    let end = index + 1
    while (end < text.length) {
      const next = text[end]
      if (/\s/u.test(next) || '\\=<>[]{}()$。、，,.；;：:'.includes(next)) break
      if (startsWithOneOf(text, end, [...KEYWORDS, ...PARTICLES, ...MULTI_RELATIONS])) break
      if (isAsciiIdentifierStart(next) || /\d/.test(next)) break
      end++
    }
    tokens.push({ kind: 'text', value: text.slice(index, end), start: index, end })
    index = end
  }
  return tokens
}

function queryOf(raw: string, clause: number): QuerySyntax | null {
  if (/示せ|証明せよ/.test(raw)) return { kind: 'prove', clause }
  if (/分類せよ|すべて求めよ|全て求めよ/.test(raw)) return { kind: 'classify', clause }
  if (/最大|最小|極値/.test(raw)) return { kind: 'optimize', clause }
  if (/面積|体積|測度/.test(raw) && /求めよ/.test(raw)) return { kind: 'measure', clause }
  if (/求めよ/.test(raw)) return { kind: 'compute', clause }
  return null
}

function variableAfter(tokens: MathToken[], index: number): string | null {
  return tokens.slice(index + 1).find(token => token.kind === 'identifier')?.value ?? null
}

function quantifiersOf(tokens: MathToken[], clause: number): QuantifierSyntax[] {
  const quantifiers: QuantifierSyntax[] = []
  tokens.forEach((token, index) => {
    if (token.kind !== 'keyword') return
    if (['すべて', '全て', '任意'].includes(token.value)) {
      quantifiers.push({ kind: 'forall', variable: variableAfter(tokens, index), clause, start: token.start, end: token.end })
    } else if (token.value.startsWith('存在')) {
      const before = [...tokens.slice(0, index)].reverse().find(candidate => candidate.kind === 'identifier')
      quantifiers.push({ kind: 'exists', variable: before?.value ?? variableAfter(tokens, index), clause, start: token.start, end: token.end })
    }
  })
  return quantifiers
}

function definitionsOf(raw: string, clause: number, offset: number): DefinitionSyntax[] {
  const definitions: DefinitionSyntax[] = []
  const pattern = /([A-Za-zα-ωΑ-Ω](?:_\{?[A-Za-z0-9]+\}?)?(?:\s*,\s*[A-Za-zα-ωΑ-Ω](?:_\{?[A-Za-z0-9]+\}?)?)*)\s*を\s*([^。；;]+?)(?:とする|と定める|で定める|と定義する)/gu
  for (const match of raw.matchAll(pattern)) {
    const start = offset + (match.index ?? 0)
    definitions.push({ symbol: match[1].replace(/\s+/g, ''), body: match[2].trim(), clause, start, end: start + match[0].length })
  }
  return definitions
}

function clauseRanges(text: string): Array<{ raw: string; start: number }> {
  const ranges: Array<{ raw: string; start: number }> = []
  const pattern = /[^。；;\n]+[。；;]?/gu
  for (const match of text.matchAll(pattern)) {
    const raw = match[0].trim()
    if (raw) ranges.push({ raw, start: match.index ?? 0 })
  }
  return ranges
}

export function parseMathematicalText(text: string, maxAnalyses = 32): MathematicalParseForest {
  const tokens = lexMathematicalText(text)
  const ranges = clauseRanges(text)
  const clauses = ranges.map((range, index) => {
    const clauseTokens = tokens.filter(token => token.start >= range.start && token.end <= range.start + range.raw.length)
    return {
      id: index,
      raw: range.raw,
      tokens: clauseTokens,
      quantifiers: quantifiersOf(clauseTokens, index),
      definitions: definitionsOf(range.raw, index, range.start),
      query: queryOf(range.raw, index),
    }
  })
  const ambiguousLinks = Math.max(0, clauses.length - 1)
  const theoretical = Math.max(1, 2 ** Math.min(ambiguousLinks, 20))
  const analysisCount = Math.min(maxAnalyses, theoretical)
  const analyses = Array.from({ length: analysisCount }, (_, variant) => ({
    clauses,
    attachment_order: clauses.slice(1).map((clause, index) => ({
      modifier_clause: clause.id,
      head_clause: (variant >> Math.min(index, 30)) & 1 ? Math.max(0, clause.id - 1) : 0,
    })),
  }))
  return {
    tokens,
    analyses,
    truncated: theoretical > maxAnalyses,
    diagnostics: theoretical > maxAnalyses ? [`parse forest capped at ${maxAnalyses}/${theoretical} analyses`] : [],
  }
}

function normalizedBody(body: string): string {
  const identifierMap = new Map<string, string>()
  let next = 0
  return lexMathematicalText(body).map(token => {
    if (token.kind !== 'identifier') return token.value
    if (!identifierMap.has(token.value)) identifierMap.set(token.value, `v${next++}`)
    return identifierMap.get(token.value)!
  }).join('')
}

export function elaborateMathematicalText(
  text: string,
  inferSort: (body: string) => string = () => 'OpaqueDefinedObject',
): { forest: MathematicalParseForest; ir: ElaboratedMathematicalIR } {
  const forest = parseMathematicalText(text)
  const selected = forest.analyses[0] ?? { clauses: [], attachment_order: [] }
  const definitions = selected.clauses.flatMap(clause => clause.definitions).map(definition => {
    const bodyTokens = lexMathematicalText(definition.body)
    const dependencies = [...new Set(bodyTokens.filter(token => token.kind === 'identifier').map(token => token.value))]
    return {
      ...definition,
      id: `definition.${hash([definition.symbol, normalizedBody(definition.body)])}`,
      canonical: `DefinedObject[${hash(normalizedBody(definition.body), 10)}]`,
      inferred_sort: inferSort(definition.body),
      dependencies,
    }
  })
  const quantifiers = selected.clauses.flatMap(clause => clause.quantifiers)
    .sort((left, right) => left.start - right.start)
  const identifiers = [...new Set(forest.tokens.filter(token => token.kind === 'identifier').map(token => token.value))]
  const bound = [...new Set([
    ...quantifiers.map(quantifier => quantifier.variable).filter((value): value is string => Boolean(value)),
    ...definitions.flatMap(definition => definition.symbol.split(',')),
  ])]
  const defined = new Set(definitions.flatMap(definition => definition.symbol.split(',')))
  const unresolved = identifiers.filter(identifier => !bound.includes(identifier) && !defined.has(identifier))
  return {
    forest,
    ir: {
      selected_analysis: 0,
      definitions,
      quantifiers,
      quantifier_prefix: quantifiers.map(quantifier => `${quantifier.kind}:${quantifier.variable ?? '?'}`),
      query: [...selected.clauses].reverse().find(clause => clause.query)?.query ?? null,
      free_symbols: identifiers.filter(identifier => !bound.includes(identifier)),
      bound_symbols: bound,
      unresolved_references: unresolved,
      diagnostics: [...forest.diagnostics],
    },
  }
}
