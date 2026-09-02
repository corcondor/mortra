export type FormulaOcrSymbol = {
  text: string
  confidence: number
  bbox: { x0: number; y0: number; x1: number; y1: number }
}

export type FormulaOcrBox = {
  type: 'embedding' | 'isolated'
  box: { x0: number; y0: number; x1: number; y1: number }
  latex: string
  detectionConfidence: number
  recognitionConfidence: number
}

export type FormulaOcrResult = {
  boxes: FormulaOcrBox[]
  detected: number
  rejected: number
}

export type FormulaOcrRegionProposal = {
  type: 'embedding'
  score: number
  x0: number
  y0: number
  x1: number
  y1: number
}

function symbolVerticalOverlap(a: FormulaOcrSymbol, b: FormulaOcrSymbol) {
  const overlap = Math.max(0, Math.min(a.bbox.y1, b.bbox.y1) - Math.max(a.bbox.y0, b.bbox.y0))
  return overlap / Math.max(1, Math.min(a.bbox.y1 - a.bbox.y0, b.bbox.y1 - b.bbox.y0))
}

export function proposeFormulaFallbackBoxes(
  symbols: FormulaOcrSymbol[],
  imageWidth: number,
  imageHeight: number,
): FormulaOcrRegionProposal[] {
  const candidates = symbols
    .filter(symbol => !/[\u3040-\u30ff\u3400-\u9fff]/u.test(symbol.text))
    .filter(symbol => /[A-Za-z0-9=+\-*/^_()[\]{}<>]/u.test(symbol.text))
    .sort((a, b) => a.bbox.y0 - b.bbox.y0 || a.bbox.x0 - b.bbox.x0)
  const rows: FormulaOcrSymbol[][] = []
  for (const symbol of candidates) {
    const row = rows.find(items => items.some(item => symbolVerticalOverlap(item, symbol) >= 0.55))
    if (row) row.push(symbol)
    else rows.push([symbol])
  }

  const proposals: FormulaOcrRegionProposal[] = []
  for (const row of rows) {
    const runs: FormulaOcrSymbol[][] = []
    for (const symbol of row.sort((a, b) => a.bbox.x0 - b.bbox.x0)) {
      const run = runs.at(-1)
      const previous = run?.at(-1)
      const height = Math.max(1, symbol.bbox.y1 - symbol.bbox.y0, previous ? previous.bbox.y1 - previous.bbox.y0 : 1)
      if (!run || !previous || symbol.bbox.x0 - previous.bbox.x1 > height * 0.9) runs.push([symbol])
      else run.push(symbol)
    }
    for (const run of runs) {
      const compact = run.map(symbol => symbol.text).join('').replace(/\s/g, '')
      const alphanumeric = compact.replace(/[^A-Za-z0-9]/g, '')
      const formulaLike = /[=+\-*/^_0-9]/u.test(compact) || /^[A-Z]{2,4}$/u.test(alphanumeric)
      if (alphanumeric.length < 2 || !formulaLike) continue
      const x0 = Math.min(...run.map(symbol => symbol.bbox.x0))
      const y0 = Math.min(...run.map(symbol => symbol.bbox.y0))
      const x1 = Math.max(...run.map(symbol => symbol.bbox.x1))
      const y1 = Math.max(...run.map(symbol => symbol.bbox.y1))
      const padding = Math.max(3, (y1 - y0) * 0.28)
      proposals.push({
        type: 'embedding',
        score: 0.52,
        x0: Math.max(0, x0 - padding),
        y0: Math.max(0, y0 - padding),
        x1: Math.min(imageWidth, x1 + padding),
        y1: Math.min(imageHeight, y1 + padding),
      })
    }
  }
  return proposals
}
