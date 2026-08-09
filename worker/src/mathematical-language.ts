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

export type DeclarationSyntax = {
  symbol: string
  sort: string
  surface_sort: string
  implicit_forall: boolean
  clause: number
  start: number
  end: number
}

export type RelationSyntax = {
  operator: string
  lhs: string
  rhs: string
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
  declarations: DeclarationSyntax[]
  relations: RelationSyntax[]
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
  declarations: DeclarationSyntax[]
  constraints: Array<RelationSyntax & { canonical: string }>
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
  'find', 'determine', 'compute', 'calculate', 'prove', 'show', 'classify',
]
const MULTI_RELATIONS = ['<=>', '=>', '<=', '>=', '!=', '==', '≦', '≧', '≠', '∈', '⊂', '⊆', '→', '↦']
const SORT_WORDS: Record<string, string> = {
  関数: 'Function', 数列: 'Sequence', 整数: 'Integer', 自然数: 'Natural', 実数: 'Real',
  複素数: 'Complex', 素数: 'Prime', 点: 'Point', 直線: 'Line', 曲線: 'Curve', 円: 'Circle',
  三角形: 'Triangle', 集合: 'Set', 多項式: 'Polynomial', 行列: 'Matrix', 確率変数: 'RandomVariable',
  位相空間: 'TopologicalSpace', 曲面: 'Surface', 三角形分割: 'FiniteTriangulation',
}

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
  if (/示せ|証明せよ|\b(?:prove|show)\b/i.test(raw)) return { kind: 'prove', clause }
  if (/分類せよ|すべて求めよ|全て求めよ|\b(?:classify|find all|determine all)\b/i.test(raw)) return { kind: 'classify', clause }
  if (/最大|最小|極値|\b(?:maximum|minimum|maximize|minimize|largest|smallest)\b/i.test(raw)) return { kind: 'optimize', clause }
  if (/(?:面積|体積|測度|\barea\b|\bvolume\b)/i.test(raw) && /求めよ|\b(?:find|determine|compute|calculate)\b/i.test(raw)) return { kind: 'measure', clause }
  if (/求めよ|\b(?:find|determine|compute|calculate|evaluate)\b/i.test(raw)) return { kind: 'compute', clause }
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
  const equalityPattern = /([A-Za-zα-ωΑ-Ω](?:_\{?[A-Za-z0-9]+\}?)?)\s*=\s*([^。；;]+?)\s*(?:とする|と定める|で定める|と定義する)/gu
  for (const match of raw.matchAll(equalityPattern)) {
    const start = offset + (match.index ?? 0)
    if (definitions.some(definition => definition.symbol === match[1] && definition.start === start)) continue
    definitions.push({ symbol: match[1], body: match[2].trim(), clause, start, end: start + match[0].length })
  }
  return definitions
}

function declarationsOf(raw: string, clause: number, offset: number): DeclarationSyntax[] {
  const declarations: DeclarationSyntax[] = []
  const sortPattern = Object.keys(SORT_WORDS).sort((left, right) => right.length - left.length).join('|')
  const pattern = new RegExp(`(${sortPattern})\\s*([A-Za-zα-ωΑ-Ω](?:_\\{?[A-Za-z0-9]+\\}?)?)`, 'gu')
  const implicitForall = /に対し|に対して|任意|すべて|全て/.test(raw)
  for (const match of raw.matchAll(pattern)) {
    const start = offset + (match.index ?? 0)
    declarations.push({
      symbol: match[2],
      sort: SORT_WORDS[match[1]],
      surface_sort: match[1],
      implicit_forall: implicitForall,
      clause,
      start,
      end: start + match[0].length,
    })
  }
  return declarations
}

function relationsOf(raw: string, tokens: MathToken[], clause: number, offset: number): RelationSyntax[] {
  return tokens.filter(token => token.kind === 'relation').map(token => {
    const localStart = Math.max(0, token.start - offset)
    const localEnd = Math.max(0, token.end - offset)
    const prefix = raw.slice(0, localStart)
    const boundaryMarkers = ['、', ',', '。', 'に対し', 'に対して']
    const boundary = Math.max(...boundaryMarkers.map(marker => {
      const index = prefix.lastIndexOf(marker)
      return index < 0 ? -1 : index + marker.length - 1
    }))
    return {
      operator: token.value,
      lhs: prefix.slice(boundary + 1).trim(),
      rhs: raw.slice(localEnd).replace(/(?:とする|と定める|で定める|と定義する).*$/u, '').trim(),
      clause,
      start: token.start,
      end: token.end,
    }
  }).filter(relation => relation.lhs.length > 0 && relation.rhs.length > 0)
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
      declarations: declarationsOf(range.raw, index, range.start),
      relations: relationsOf(range.raw, clauseTokens, index, range.start),
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
    const valueSort = inferSort(definition.body)
    const indexMatch = definition.symbol.match(/_\{?([A-Za-z][A-Za-z0-9]*)\}?/u)
    return {
      ...definition,
      id: `definition.${hash([definition.symbol, normalizedBody(definition.body)])}`,
      canonical: `DefinedObject[${hash(normalizedBody(definition.body), 10)}]`,
      inferred_sort: indexMatch ? `Sequence[${valueSort}]` : valueSort,
      dependencies,
    }
  })
  const declarations = selected.clauses.flatMap(clause => clause.declarations)
  const explicitQuantifiers = selected.clauses.flatMap(clause => clause.quantifiers)
  const explicitVariables = new Set(explicitQuantifiers.map(quantifier => quantifier.variable).filter(Boolean))
  const implicitQuantifiers: QuantifierSyntax[] = declarations
    .filter(declaration => declaration.implicit_forall && !explicitVariables.has(declaration.symbol))
    .map(declaration => ({
      kind: 'forall',
      variable: declaration.symbol,
      clause: declaration.clause,
      start: declaration.start,
      end: declaration.end,
    }))
  const quantifiers = [...explicitQuantifiers, ...implicitQuantifiers]
    .sort((left, right) => left.start - right.start)
  const constraints = selected.clauses.flatMap(clause => clause.relations).map(relation => ({
    ...relation,
    canonical: `Relation[${relation.operator},${normalizedBody(relation.lhs)},${normalizedBody(relation.rhs)}]`,
  }))
  const identifiers = [...new Set(forest.tokens.filter(token => token.kind === 'identifier').map(token => token.value))]
  const definitionIndices = definitions.flatMap(definition => {
    const match = definition.symbol.match(/_\{?([A-Za-z][A-Za-z0-9]*)\}?/u)
    return match ? [match[1]] : []
  })
  const integrationDifferentials = identifiers.filter(identifier => /^d[A-Za-z]$/u.test(identifier))
  const integrationVariables = integrationDifferentials.map(identifier => identifier.slice(1))
  const bound = [...new Set([
    ...quantifiers.map(quantifier => quantifier.variable).filter((value): value is string => Boolean(value)),
    ...declarations.map(declaration => declaration.symbol),
    ...definitions.flatMap(definition => definition.symbol.split(',')),
    ...definitionIndices,
    ...integrationDifferentials,
    ...integrationVariables,
  ])]
  const defined = new Set(definitions.flatMap(definition => definition.symbol.split(',')))
  const unresolved = identifiers.filter(identifier => !bound.includes(identifier) && !defined.has(identifier))
  return {
    forest,
    ir: {
      selected_analysis: 0,
      definitions,
      declarations,
      constraints,
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
