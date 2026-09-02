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
    .replace(/\\sum/g, '\u03a3')
    .replace(/\\alpha/g, '\u03b1')
    .replace(/\\beta/g, '\u03b2')
    .replace(/\\gamma/g, '\u03b3')
    .replace(/\\theta/g, '\u03b8')
    .replace(/\\varphi|\\phi/g, '\u03c6')
    .replace(/\\lambda/g, '\u03bb')
    .replace(/\\mu/g, '\u03bc')
    .replace(/\\sigma/g, '\u03c3')
    .replace(/\\omega/g, '\u03c9')
    .replace(/\\infty/g, '\u221e')
    .replace(/\\pi/g, '\u03c0')
    .replace(/\\cdot/g, '\u00b7')
    .replace(/\\to/g, '\u2192')
    .replace(/\\geq?/g, '\u2265')
    .replace(/\\leq?/g, '\u2264')
    .replace(/\\neq/g, '\u2260')
    .replace(/\\q?quad/g, ' ')
    .replace(/\^\{(-?\d+)\}/g, (_, exponent: string) => superscript(exponent))
    .replace(/\^(-?\d+)/g, (_, exponent: string) => superscript(exponent))
    .replace(/_\{([^{}]+)\}/g, '[$1]')
    .replace(/_([A-Za-z0-9]+)/g, '[$1]')
    .replace(/\\[,;!]/g, ' ')
    .replace(/\\[()[\]]/g, '')
    .replace(/[{}]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}
