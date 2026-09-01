export type MathExpression =
  | number
  | string
  | ['Add' | 'Multiply', ...MathExpression[]]
  | ['Subtract' | 'Divide' | 'Power' | 'Binomial', MathExpression, MathExpression]
  | ['Negate' | 'Sqrt', MathExpression]
  | ['Apply', string, ...MathExpression[]]
  | ['Sum', string, MathExpression, MathExpression, MathExpression]
  | ['Limit', string, MathExpression, MathExpression]
  | ['Integral', string, MathExpression, MathExpression, MathExpression]

export type MathRelationIR = {
  operator: 'Equal' | 'Less' | 'LessEqual' | 'Greater' | 'GreaterEqual'
  lhs: MathExpression
  rhs: MathExpression
  latex: string
  variables: string[]
}

type Token = {
  kind: 'number' | 'identifier' | 'command' | 'operator' | 'open' | 'close' | 'comma'
  value: string
}

const RELATIONS: Record<string, MathRelationIR['operator']> = {
  '=': 'Equal',
  '<': 'Less',
  '>': 'Greater',
  '\\le': 'LessEqual',
  '\\leq': 'LessEqual',
  '\\ge': 'GreaterEqual',
  '\\geq': 'GreaterEqual',
}

const FUNCTION_COMMANDS = new Set(['sin', 'cos', 'tan', 'log', 'ln', 'exp'])
const IGNORED_COMMANDS = new Set(['left', 'right', 'displaystyle'])

function tokenize(source: string): Token[] {
  const tokens: Token[] = []
  for (let index = 0; index < source.length;) {
    const char = source[index]
    if (/\s/u.test(char)) {
      index++
      continue
    }
    if (char === '\\') {
      let end = index + 1
      while (end < source.length && /[A-Za-z]/.test(source[end])) end++
      const command = source.slice(index + 1, end)
      if (IGNORED_COMMANDS.has(command)) {
        index = end
        continue
      }
      if (command === 'cdot' || command === 'times') {
        tokens.push({ kind: 'operator', value: '*' })
      } else if (['le', 'leq', 'ge', 'geq'].includes(command)) {
        tokens.push({ kind: 'operator', value: `\\${command}` })
      } else {
        tokens.push({ kind: 'command', value: command })
      }
      index = end
      continue
    }
    if (/\d/.test(char)) {
      let end = index + 1
      while (end < source.length && /[\d.]/.test(source[end])) end++
      tokens.push({ kind: 'number', value: source.slice(index, end) })
      index = end
      continue
    }
    if (/[A-Za-z\u0370-\u03ff]/u.test(char)) {
      let end = index + 1
      while (end < source.length && /[A-Za-z0-9_\u0370-\u03ff]/u.test(source[end])) end++
      const identifier = source.slice(index, end)
      // In TeX, adjacent bare letters denote multiplication: `en` is e*n,
      // while a multi-letter symbol must be introduced by a command or a
      // textual wrapper. Keeping the lexical rule here avoids a benchmark-
      // specific rewrite for each juxtaposed product.
      if (/^[A-Za-z]{2,}$/u.test(identifier)) {
        for (const value of identifier) tokens.push({ kind: 'identifier', value })
      } else {
        tokens.push({ kind: 'identifier', value: identifier })
      }
      index = end
      continue
    }
    if ('_+-*/^=<>'.includes(char)) tokens.push({ kind: 'operator', value: char })
    else if ('({['.includes(char)) tokens.push({ kind: 'open', value: char })
    else if (')}]'.includes(char)) tokens.push({ kind: 'close', value: char })
    else if (char === ',') tokens.push({ kind: 'comma', value: char })
    index++
  }
  return tokens
}

class Parser {
  private index = 0

  constructor(private readonly tokens: Token[]) {}

  parseRelation(latex: string): MathRelationIR | null {
    const lhs = this.parseAdditive()
    if (lhs === null) return null
    const relation = this.peek()
    if (!relation || relation.kind !== 'operator' || !RELATIONS[relation.value]) return null
    this.index++
    const rhs = this.parseAdditive()
    if (rhs === null || this.index !== this.tokens.length) return null
    return {
      operator: RELATIONS[relation.value],
      lhs,
      rhs,
      latex,
      variables: [...new Set([...symbolsInMathExpression(lhs), ...symbolsInMathExpression(rhs)])].sort(),
    }
  }

  parseExpression(): MathExpression | null {
    const expression = this.parseAdditive()
    return expression !== null && this.index === this.tokens.length ? expression : null
  }

  private peek(offset = 0): Token | undefined {
    return this.tokens[this.index + offset]
  }

  private parseAdditive(): MathExpression | null {
    let current = this.parseMultiplicative()
    if (current === null) return null
    while (this.peek()?.kind === 'operator' && ['+', '-'].includes(this.peek()!.value)) {
      const operator = this.peek()!.value
      this.index++
      const right = this.parseMultiplicative()
      if (right === null) return null
      current = operator === '+' ? ['Add', current, right] : ['Subtract', current, right]
    }
    return current
  }

  private parseMultiplicative(): MathExpression | null {
    let current = this.parsePower()
    if (current === null) return null
    while (true) {
      const token = this.peek()
      const explicit = token?.kind === 'operator' && ['*', '/'].includes(token.value)
      const implicit = this.startsPrimary(token)
      if (!explicit && !implicit) break
      const operator = explicit ? token!.value : '*'
      if (explicit) this.index++
      const right = this.parsePower()
      if (right === null) return null
      current = operator === '*' ? ['Multiply', current, right] : ['Divide', current, right]
    }
    return current
  }

  private parsePower(): MathExpression | null {
    let current = this.parseUnary()
    if (current === null) return null
    if (this.peek()?.kind === 'operator' && this.peek()!.value === '^') {
      this.index++
      const exponent = this.parsePower()
      if (exponent === null) return null
      current = ['Power', current, exponent]
    }
    return current
  }

  private parseUnary(): MathExpression | null {
    if (this.peek()?.kind === 'operator' && this.peek()!.value === '-') {
      this.index++
      const value = this.parseUnary()
      return value === null ? null : ['Negate', value]
    }
    return this.parsePrimary()
  }

  private parsePrimary(): MathExpression | null {
    const token = this.peek()
    if (!token) return null
    if (token.kind === 'number') {
      this.index++
      const value = Number(token.value)
      return Number.isFinite(value) ? value : null
    }
    if (token.kind === 'identifier') {
      this.index++
      return token.value
    }
    if (token.kind === 'open') {
      this.index++
      const value = this.parseAdditive()
      if (value === null || this.peek()?.kind !== 'close') return null
      this.index++
      return value
    }
    if (token.kind !== 'command') return null
    this.index++
    if (token.value === 'sum') return this.parseSum()
    if (token.value === 'lim') return this.parseLimit()
    if (token.value === 'int') return this.parseIntegral()
    if (token.value === 'binom') {
      const upper = this.parseRequiredGroup()
      const lower = this.parseRequiredGroup()
      return upper !== null && lower !== null ? ['Binomial', upper, lower] : null
    }
    if (token.value === 'infty') return 'Infinity'
    if (token.value === 'frac' || token.value === 'dfrac') {
      const numerator = this.parseRequiredGroup()
      const denominator = this.parseRequiredGroup()
      return numerator !== null && denominator !== null ? ['Divide', numerator, denominator] : null
    }
    if (token.value === 'sqrt') {
      const radicand = this.parseRequiredGroup()
      return radicand === null ? null : ['Sqrt', radicand]
    }
    if (FUNCTION_COMMANDS.has(token.value)) {
      const argument = this.parsePrimary()
      return argument === null ? null : ['Apply', token.value, argument]
    }
    return token.value
  }

  private parseSum(): MathExpression | null {
    if (!this.consumeOperator('_')) return null
    const lowerTokens = this.consumeScriptTokens()
    if (!lowerTokens) return null
    const equalityIndex = lowerTokens.findIndex(token => token.kind === 'operator' && token.value === '=')
    if (equalityIndex !== 1 || lowerTokens[0]?.kind !== 'identifier') return null
    const index = lowerTokens[0].value
    const lower = new Parser(lowerTokens.slice(equalityIndex + 1)).parseExpression()
    if (lower === null || !this.consumeOperator('^')) return null
    const upper = this.parseScriptExpression()
    if (upper === null) return null
    const body = this.parsePower()
    return body === null ? null : ['Sum', index, lower, upper, body]
  }

  private parseLimit(): MathExpression | null {
    if (!this.consumeOperator('_')) return null
    const binder = this.consumeScriptTokens()
    if (!binder || binder[0]?.kind !== 'identifier') return null
    const toIndex = binder.findIndex(token => token.kind === 'command' && token.value === 'to')
    if (toIndex !== 1) return null
    const variable = binder[0].value
    const target = new Parser(binder.slice(toIndex + 1)).parseExpression()
    if (target === null) return null
    const body = this.parseAdditive()
    return body === null ? null : ['Limit', variable, target, body]
  }

  private parseIntegral(): MathExpression | null {
    if (!this.consumeOperator('_')) return null
    const lower = this.parseScriptExpression()
    if (lower === null || !this.consumeOperator('^')) return null
    const upper = this.parseScriptExpression()
    if (upper === null) return null

    const differential = this.findDifferential()
    if (!differential) return null
    const body = new Parser(this.tokens.slice(this.index, differential.start)).parseExpression()
    if (body === null) return null
    this.index = differential.end
    return ['Integral', differential.variable, lower, upper, body]
  }

  private consumeOperator(value: string): boolean {
    if (this.peek()?.kind !== 'operator' || this.peek()?.value !== value) return false
    this.index++
    return true
  }

  private consumeScriptTokens(): Token[] | null {
    if (this.peek()?.kind !== 'open') {
      const token = this.peek()
      if (!token) return null
      this.index++
      return [token]
    }
    this.index++
    const start = this.index
    let depth = 1
    while (this.index < this.tokens.length && depth > 0) {
      const token = this.tokens[this.index]
      if (token.kind === 'open') depth++
      if (token.kind === 'close') depth--
      this.index++
    }
    if (depth !== 0) return null
    return this.tokens.slice(start, this.index - 1)
  }

  private parseScriptExpression(): MathExpression | null {
    const tokens = this.consumeScriptTokens()
    return tokens ? new Parser(tokens).parseExpression() : null
  }

  private findDifferential(): { start: number; end: number; variable: string } | null {
    let depth = 0
    for (let cursor = this.index; cursor < this.tokens.length; cursor++) {
      const token = this.tokens[cursor]
      if (token.kind === 'open') depth++
      if (token.kind === 'close') depth--
      if (depth !== 0 || token.kind !== 'identifier') continue
      const compact = token.value.match(/^d([A-Za-z\u0370-\u03ff][A-Za-z0-9_\u0370-\u03ff]*)$/u)
      if (compact) return { start: cursor, end: cursor + 1, variable: compact[1] }
      if (token.value === 'd' && this.tokens[cursor + 1]?.kind === 'identifier') {
        return { start: cursor, end: cursor + 2, variable: this.tokens[cursor + 1].value }
      }
    }
    return null
  }

  private parseRequiredGroup(): MathExpression | null {
    if (this.peek()?.kind !== 'open') return null
    return this.parsePrimary()
  }

  private startsPrimary(token?: Token): boolean {
    return token?.kind === 'number' || token?.kind === 'identifier' ||
      token?.kind === 'command' || token?.kind === 'open'
  }
}

export function extractLatexSegments(statement: string): string[] {
  const segments: Array<{ start: number; value: string }> = []
  for (const pattern of [/\$([^$]+)\$/g, /\\\(([^]*?)\\\)/g, /\\\[([^]*?)\\\]/g]) {
    for (const match of statement.matchAll(pattern)) {
      segments.push({ start: match.index ?? 0, value: match[1].trim() })
    }
  }
  return segments.sort((left, right) => left.start - right.start).map(segment => segment.value)
}

function delimitedMathRanges(statement: string): Array<{ start: number; end: number; value: string }> {
  const ranges: Array<{ start: number; end: number; value: string }> = []
  for (const pattern of [/\$([^$]+)\$/g, /\\\(([^]*?)\\\)/g, /\\\[([^]*?)\\\]/g]) {
    for (const match of statement.matchAll(pattern)) {
      const start = match.index ?? 0
      ranges.push({ start, end: start + match[0].length, value: match[1].trim() })
    }
  }
  return ranges.sort((left, right) => left.start - right.start)
}

function isPlainMathCharacter(char: string): boolean {
  return /[A-Za-z0-9_\u0370-\u03ff]/u.test(char) ||
    /[+\-*/^=<>.(){}\[\]\\]/.test(char) ||
    /\s/u.test(char)
}

function isPlausiblePlainMath(candidate: string): boolean {
  if (!candidate || !/[A-Za-z0-9\u0370-\u03ff]/u.test(candidate)) return false
  if (/[=+\-*/^<>\\]/.test(candidate) || /\d/.test(candidate)) return true
  const words = candidate.trim().split(/\s+/).filter(Boolean)
  return words.length === 1 && /^[A-Za-z\u0370-\u03ff][A-Za-z0-9_\u0370-\u03ff]*$/u.test(words[0])
}

/**
 * Extract both delimited TeX and bare formulas embedded in natural language.
 *
 * Bare formulas are found by a lexical scan over mathematical characters;
 * Japanese prose is therefore a delimiter rather than part of the formula.
 * Delimited TeX ranges are skipped by the bare scan so no expression is
 * duplicated. Commas also delimit candidates because this linear lowering
 * stage expects one relation per candidate.
 */
export function extractMathSegments(statement: string): string[] {
  const delimited = delimitedMathRanges(statement)
  const located: Array<{ start: number; value: string }> = delimited.map(range => ({
    start: range.start,
    value: range.value,
  }))
  let rangeIndex = 0
  let candidateStart = -1
  let candidate = ''

  const flush = () => {
    const value = candidate.trim()
    if (candidateStart >= 0 && isPlausiblePlainMath(value)) {
      located.push({ start: candidateStart, value })
    }
    candidateStart = -1
    candidate = ''
  }

  for (let index = 0; index < statement.length;) {
    const range = delimited[rangeIndex]
    if (range && index === range.start) {
      flush()
      index = range.end
      rangeIndex++
      continue
    }
    const char = statement[index]
    if (char !== ',' && isPlainMathCharacter(char)) {
      if (candidateStart < 0 && !/\s/u.test(char)) candidateStart = index
      if (candidateStart >= 0) candidate += char
    } else {
      flush()
    }
    index++
  }
  flush()
  return located.sort((left, right) => left.start - right.start).map(segment => segment.value)
}

export function parseLatexRelation(latex: string): MathRelationIR | null {
  return new Parser(tokenize(latex)).parseRelation(latex)
}

export function parseLatexExpression(latex: string): MathExpression | null {
  const normalized = normalizeBinderLatex(latex)
  return new Parser(tokenize(normalized)).parseExpression()
}

export function containsBoundMathOperator(expression: MathExpression): boolean {
  if (typeof expression === 'number' || typeof expression === 'string') return false
  if (expression[0] === 'Sum' || expression[0] === 'Limit' || expression[0] === 'Integral') return true
  return expression.slice(1).some(value =>
    typeof value !== 'string' && containsBoundMathOperator(value as MathExpression))
}

/**
 * Return a bound expression actually present in the current statement.
 *
 * This is syntax directed: it never supplies a missing sequence, family, or
 * limit object from an Atlas entry. If the input has no complete expression,
 * callers must retain an open obligation.
 */
export function extractBoundMathExpression(
  statement: string,
): { expression: MathExpression; surface: string } | null {
  for (const surface of [...extractLatexSegments(statement)].reverse()) {
    const expression = parseLatexExpression(surface)
    if (expression && containsBoundMathOperator(expression)) return { expression, surface }
  }
  return null
}

/**
 * Return true only when the whole query asks for the value of the extracted
 * bound expression. A bound expression may instead be evidence inside a proof,
 * integrality test, optimization task, or one part of a multipart problem.
 */
export function isDirectBoundExpressionQuery(statement: string): boolean {
  if (!extractBoundMathExpression(statement)) return false
  const normalized = statement.replace(/\s+/g, ' ').trim()
  const numberedParts = normalized.match(/(?:\(\s*\d+\s*\)|（\s*\d+\s*）)/g) ?? []
  if (numberedParts.length > 1) return false
  if (/(?:示せ|証明|整数か|自然数か|有理数か|無理数か|成り立つか|真偽|最大|最小|範囲|領域|個数|すべて求め|分類せよ)/.test(normalized)) {
    return false
  }
  if (/(?:となる|を満たす)[^。．]*?(?:数|整数|実数|自然数|[A-Za-z])[^。．]*?求め/.test(normalized)) {
    return false
  }
  return /(?:求めよ|計算せよ|計算しなさい|evaluate|compute)/i.test(normalized)
}

export function normalizeBinderLatex(latex: string): string {
  return latex
    .replace(/\\left|\\right/g, '')
    .replace(/\\[!,;:]/g, '')
    .replace(/\\\{/g, '{')
    .replace(/\\\}/g, '}')
    .replace(
      /\{\}\s*_\s*\{([^{}]+)\}\s*C\s*_\s*\{([^{}]+)\}/g,
      '\\binom{$1}{$2}',
    )
    .replace(/\{\}\s*_\s*\{([^{}]+)\}\s*C\s*_\s*([A-Za-z0-9]+)/g, '\\binom{$1}{$2}')
    .replace(/\{\}\s*_\s*([A-Za-z0-9]+)\s*C\s*_\s*\{([^{}]+)\}/g, '\\binom{$1}{$2}')
    .replace(/\{\}\s*_\s*([A-Za-z0-9]+)\s*C\s*_\s*([A-Za-z0-9]+)/g, '\\binom{$1}{$2}')
}

export function extractMathRelations(statement: string): MathRelationIR[] {
  return extractMathSegments(statement).map(parseLatexRelation).filter((value): value is MathRelationIR => value !== null)
}

export function symbolsInMathExpression(expression: MathExpression): string[] {
  if (typeof expression === 'number') return []
  if (typeof expression === 'string') {
    return ['pi', 'e', 'i', 'infinity'].includes(expression.toLowerCase()) ? [] : [expression]
  }
  if (expression[0] === 'Sum') {
    const [, index, lower, upper, body] = expression
    return [...symbolsInMathExpression(lower), ...symbolsInMathExpression(upper),
      ...symbolsInMathExpression(body).filter(symbol => symbol !== index)]
  }
  if (expression[0] === 'Limit') {
    const [, variable, target, body] = expression
    return [...symbolsInMathExpression(target),
      ...symbolsInMathExpression(body).filter(symbol => symbol !== variable)]
  }
  if (expression[0] === 'Integral') {
    const [, variable, lower, upper, body] = expression
    return [...symbolsInMathExpression(lower), ...symbolsInMathExpression(upper),
      ...symbolsInMathExpression(body).filter(symbol => symbol !== variable)]
  }
  return expression.slice(1).flatMap(value =>
    typeof value === 'string' && expression[0] === 'Apply' ? [] : symbolsInMathExpression(value as MathExpression),
  )
}

export function renameMathSymbol(expression: MathExpression, source: string, target: string): MathExpression {
  if (typeof expression === 'number') return expression
  if (typeof expression === 'string') return expression === source ? target : expression
  if (expression[0] === 'Sum') {
    const [, index, lower, upper, body] = expression
    const renamedIndex = index === source ? target : index
    return ['Sum', renamedIndex, renameMathSymbol(lower, source, target),
      renameMathSymbol(upper, source, target), renameMathSymbol(body, source, target)]
  }
  if (expression[0] === 'Limit') {
    const [, variable, destination, body] = expression
    const renamedVariable = variable === source ? target : variable
    return ['Limit', renamedVariable, renameMathSymbol(destination, source, target),
      renameMathSymbol(body, source, target)]
  }
  if (expression[0] === 'Integral') {
    const [, variable, lower, upper, body] = expression
    const renamedVariable = variable === source ? target : variable
    return ['Integral', renamedVariable, renameMathSymbol(lower, source, target),
      renameMathSymbol(upper, source, target), renameMathSymbol(body, source, target)]
  }
  return [expression[0], ...expression.slice(1).map(value =>
    typeof value === 'string' && expression[0] === 'Apply'
      ? value
      : renameMathSymbol(value as MathExpression, source, target),
  )] as MathExpression
}

export function mathExpressionToSympy(expression: MathExpression): string {
  if (typeof expression === 'number') return Number.isInteger(expression) ? String(expression) : String(expression)
  if (typeof expression === 'string') {
    if (expression === 'Infinity') return 'oo'
    return expression.replace(/[^A-Za-z0-9_]/g, '_')
  }
  const [operator, ...args] = expression
  if (operator === 'Sum') {
    const [, index, lower, upper, body] = expression
    return `Sum(${mathExpressionToSympy(body)},(${index},${mathExpressionToSympy(lower)},${mathExpressionToSympy(upper)}))`
  }
  if (operator === 'Limit') {
    const [, variable, destination, body] = expression
    return `limit(${mathExpressionToSympy(body)},${variable},${mathExpressionToSympy(destination)})`
  }
  if (operator === 'Integral') {
    const [, variable, lower, upper, body] = expression
    return `Integral(${mathExpressionToSympy(body)},(${variable},${mathExpressionToSympy(lower)},${mathExpressionToSympy(upper)}))`
  }
  const rendered = args.map(value => mathExpressionToSympy(value as MathExpression))
  if (operator === 'Add') return `(${rendered.join(')+(')})`
  if (operator === 'Multiply') return `(${rendered.join(')*(')})`
  if (operator === 'Subtract') return `((${rendered[0]})-(${rendered[1]}))`
  if (operator === 'Divide') return `((${rendered[0]})/(${rendered[1]}))`
  if (operator === 'Power') return `((${rendered[0]})^(${rendered[1]}))`
  if (operator === 'Binomial') return `binomial(${rendered[0]},${rendered[1]})`
  if (operator === 'Negate') return `(-(${rendered[0]}))`
  if (operator === 'Sqrt') return `sqrt(${rendered[0]})`
  return `${String(args[0])}(${rendered.slice(1).join(',')})`
}

export function mathExpressionToLatex(expression: MathExpression): string {
  if (typeof expression === 'number') return String(expression)
  if (typeof expression === 'string') {
    if (expression === 'Infinity') return '\\infty'
    if (expression === 'pi') return '\\pi'
    return expression.replace(/_/g, '\\_')
  }
  const operator = expression[0]
  if (operator === 'Sum') {
    const [, index, lower, upper, body] = expression
    return `\\sum_{${index}=${mathExpressionToLatex(lower)}}^{${mathExpressionToLatex(upper)}}` +
      `\\left(${mathExpressionToLatex(body)}\\right)`
  }
  if (operator === 'Limit') {
    const [, variable, destination, body] = expression
    return `\\lim_{${variable}\\to ${mathExpressionToLatex(destination)}}` +
      `\\left(${mathExpressionToLatex(body)}\\right)`
  }
  if (operator === 'Integral') {
    const [, variable, lower, upper, body] = expression
    return `\\int_{${mathExpressionToLatex(lower)}}^{${mathExpressionToLatex(upper)}}` +
      `${mathExpressionToLatex(body)}\\,d${variable}`
  }
  if (operator === 'Apply') {
    const [, name, ...args] = expression
    return `\\${name}\\left(${args.map(mathExpressionToLatex).join(',')}\\right)`
  }
  const args = expression.slice(1).map(value => mathExpressionToLatex(value as MathExpression))
  if (operator === 'Add') return `\\left(${args.join('+')}\\right)`
  if (operator === 'Multiply') return `\\left(${args.join('\\cdot ')}\\right)`
  if (operator === 'Subtract') return `\\left(${args[0]}-${args[1]}\\right)`
  if (operator === 'Divide') return `\\frac{${args[0]}}{${args[1]}}`
  if (operator === 'Power') return `\\left(${args[0]}\\right)^{${args[1]}}`
  if (operator === 'Binomial') return `\\binom{${args[0]}}{${args[1]}}`
  if (operator === 'Negate') return `-\\left(${args[0]}\\right)`
  return `\\sqrt{${args[0]}}`
}
