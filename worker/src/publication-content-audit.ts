export type PublicationMathArtifact = {
  statement_tex: string
  answer_tex: string
  solution_tex: string
}

export type PublicationContentAudit = {
  passed: boolean
  errors: string[]
}

function occurrences(source: string, token: string): number {
  let count = 0
  let cursor = 0
  while ((cursor = source.indexOf(token, cursor)) >= 0) {
    count += 1
    cursor += token.length
  }
  return count
}

function balancedGroupingBraces(source: string): boolean {
  let depth = 0
  for (let index = 0; index < source.length; index += 1) {
    const character = source[index]
    if (character === '\\') {
      if (source[index + 1] === '{' || source[index + 1] === '}') index += 1
      continue
    }
    if (character === '{') depth += 1
    if (character === '}') {
      depth -= 1
      if (depth < 0) return false
    }
  }
  return depth === 0
}

function unescapedDollarCount(source: string): number {
  let count = 0
  for (let index = 0; index < source.length; index += 1) {
    if (source[index] !== '$') continue
    let slashes = 0
    for (let cursor = index - 1; cursor >= 0 && source[cursor] === '\\'; cursor -= 1) slashes += 1
    if (slashes % 2 === 0) count += 1
  }
  return count
}

function auditField(name: string, source: string): string[] {
  const errors: string[] = []
  if (!source.trim()) errors.push(`${name} is empty`)
  if (source.includes('\uFFFD')) errors.push(`${name} contains a Unicode replacement character`)
  if (/\b(?:undefined|NaN|Infinity|TODO|TBD)\b|\[object Object\]/i.test(source)) {
    errors.push(`${name} contains an unresolved placeholder`)
  }
  if (/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/u.test(source)) {
    errors.push(`${name} contains a control character`)
  }
  if (occurrences(source, '\\(') !== occurrences(source, '\\)')) {
    errors.push(`${name} has unbalanced inline TeX delimiters`)
  }
  if (occurrences(source, '\\[') !== occurrences(source, '\\]')) {
    errors.push(`${name} has unbalanced display TeX delimiters`)
  }
  if (unescapedDollarCount(source) % 2 !== 0) {
    errors.push(`${name} has an unbalanced dollar delimiter`)
  }
  if (!balancedGroupingBraces(source)) errors.push(`${name} has unbalanced TeX grouping braces`)

  // A binary operator immediately before a math delimiter or sentence end is
  // malformed output, not a legitimate unfinished proof obligation.
  if (/(?:^|[^\\])[+\-*/=]\s*(?:\\\)|\\\]|[。．,，;；]|$)/u.test(source)) {
    errors.push(`${name} ends a mathematical expression with a binary operator`)
  }
  return errors
}

export function auditPublicationContent(artifact: PublicationMathArtifact): PublicationContentAudit {
  const errors = [
    ...auditField('statement', artifact.statement_tex),
    ...auditField('answer', artifact.answer_tex),
    ...auditField('solution', artifact.solution_tex),
  ]
  return { passed: errors.length === 0, errors: [...new Set(errors)] }
}
