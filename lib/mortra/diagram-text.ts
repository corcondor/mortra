const superscriptDigits: Record<string, string> = {
  '-': '\u207b',
  '0': '\u2070',
  '1': '\u00b9',
  '2': '\u00b2',
  '3': '\u00b3',
  '4': '\u2074',
  '5': '\u2075',
  '6': '\u2076',
  '7': '\u2077',
  '8': '\u2078',
  '9': '\u2079',
}

function superscript(value: string): string {
  return [...value].map(character => superscriptDigits[character] ?? character).join('')
}

/** Convert the small TeX subset used by SVG annotations into readable Unicode. */
export function diagramMathToPlainText(value: string): string {
  return value
    .replace(/\\left|\\right/g, '')
    .replace(/\\text\{([^{}]+)\}/g, '$1')
    .replace(/\\operatorname\{([^{}]+)\}/g, '$1')
    .replace(/\\frac\{([^{}]+)\}\{([^{}]+)\}/g, '$1/$2')
    .replace(/\\sqrt\{([^{}]+)\}/g, '\u221a$1')
    .replace(/\\infty/g, '\u221e')
    .replace(/\\pi/g, '\u03c0')
    .replace(/\\cdot/g, '\u00b7')
    .replace(/\\to/g, '\u2192')
    .replace(/\\q?quad/g, ' ')
    .replace(/\^\{(-?\d+)\}/g, (_, exponent: string) => superscript(exponent))
    .replace(/\^(-?\d+)/g, (_, exponent: string) => superscript(exponent))
    .replace(/\\[,;!]/g, ' ')
    .replace(/[{}]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}
