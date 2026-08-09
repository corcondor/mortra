export type MathExpression =
  | number
  | string
  | ['Add' | 'Multiply', ...MathExpression[]]
  | ['Subtract' | 'Divide' | 'Power', MathExpression, MathExpression]
  | ['Negate' | 'Sqrt', MathExpression]
  | ['Apply', string, ...MathExpression[]]

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
      tokens.push({ kind: 'identifier', value: source.slice(index, end) })
      index = end
      continue
    }
    if ('+-*/^=<>'.includes(char)) tokens.push({ kind: 'operator', value: char })
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

export function parseLatexRelation(latex: string): MathRelationIR | null {
  return new Parser(tokenize(latex)).parseRelation(latex)
}

export function parseLatexExpression(latex: string): MathExpression | null {
  return new Parser(tokenize(latex)).parseExpression()
}

export function extractMathRelations(statement: string): MathRelationIR[] {
  return extractLatexSegments(statement).map(parseLatexRelation).filter((value): value is MathRelationIR => value !== null)
}

export function symbolsInMathExpression(expression: MathExpression): string[] {
  if (typeof expression === 'number') return []
  if (typeof expression === 'string') {
    return ['pi', 'e', 'i'].includes(expression.toLowerCase()) ? [] : [expression]
  }
  return expression.slice(1).flatMap(value =>
    typeof value === 'string' && expression[0] === 'Apply' ? [] : symbolsInMathExpression(value as MathExpression),
  )
}

export function renameMathSymbol(expression: MathExpression, source: string, target: string): MathExpression {
  if (typeof expression === 'number') return expression
  if (typeof expression === 'string') return expression === source ? target : expression
  return [expression[0], ...expression.slice(1).map(value =>
    typeof value === 'string' && expression[0] === 'Apply'
      ? value
      : renameMathSymbol(value as MathExpression, source, target),
  )] as MathExpression
}

export function mathExpressionToSympy(expression: MathExpression): string {
  if (typeof expression === 'number') return Number.isInteger(expression) ? String(expression) : String(expression)
  if (typeof expression === 'string') return expression.replace(/[^A-Za-z0-9_]/g, '_')
  const [operator, ...args] = expression
  const rendered = args.map(value => mathExpressionToSympy(value as MathExpression))
  if (operator === 'Add') return `(${rendered.join(')+(')})`
  if (operator === 'Multiply') return `(${rendered.join(')*(')})`
  if (operator === 'Subtract') return `((${rendered[0]})-(${rendered[1]}))`
  if (operator === 'Divide') return `((${rendered[0]})/(${rendered[1]}))`
  if (operator === 'Power') return `((${rendered[0]})^(${rendered[1]}))`
  if (operator === 'Negate') return `(-(${rendered[0]}))`
  if (operator === 'Sqrt') return `sqrt(${rendered[0]})`
  return `${String(args[0])}(${rendered.slice(1).join(',')})`
}
