export const PROBLEM_DOCUMENT_ACCEPT = 'image/png,image/jpeg,image/webp,application/pdf'
export const MAX_PROBLEM_DOCUMENT_BYTES = 15 * 1024 * 1024
export const MAX_PROBLEM_DOCUMENT_PAGES = 12
export const MAX_PROBLEM_INPUT_PAGES = 1

export type ProblemDocumentKind = 'image' | 'pdf'
export type ProblemDocumentMethod = 'ocr' | 'pdf_text' | 'hybrid'

export type ProblemDocumentProgress = {
  phase: 'loading' | 'extracting' | 'recognizing' | 'complete'
  progress: number
  page?: number
  pages?: number
}

export type ProblemDocumentResult = {
  text: string
  kind: ProblemDocumentKind
  method: ProblemDocumentMethod
  pages: number
  ocrPages: number
  fileName: string
  formulaBoxes: number
  rejectedFormulaBoxes: number
  ocrConfidence?: number
  warnings: string[]
}

type ProgressListener = (progress: ProblemDocumentProgress) => void

type PdfTextItem = {
  str?: string
  hasEOL?: boolean
}

export type RecognizedProblemSymbol = {
  text: string
  confidence: number
  bbox: { x0: number; y0: number; x1: number; y1: number }
}

export type RecognizedProblemLine = {
  text: string
  confidence: number
  bbox: { x0: number; y0: number; x1: number; y1: number }
  symbols: RecognizedProblemSymbol[]
}

export type RecognizedFormulaBox = {
  type: 'embedding' | 'isolated'
  box: { x0: number; y0: number; x1: number; y1: number }
  latex: string
  detectionConfidence: number
  recognitionConfidence: number
}

type TesseractBlock = {
  paragraphs: Array<{
    lines: Array<{
      text: string
      confidence: number
      bbox: RecognizedProblemLine['bbox']
      words: Array<{
        symbols: RecognizedProblemSymbol[]
      }>
    }>
  }>
}

const PDF_MIME = 'application/pdf'
const IMAGE_MIMES = new Set(['image/png', 'image/jpeg', 'image/webp'])

function normalizeFullWidthAscii(value: string) {
  return value.replace(/[！-～]/g, character => (
    String.fromCharCode(character.charCodeAt(0) - 0xfee0)
  ))
}

export function normalizeRecognizedProblemText(value: string) {
  let normalized = normalizeFullWidthAscii(value.normalize('NFC'))
    .replace(/\r\n?/g, '\n')
    .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g, '')
    .replace(/\u00ad/g, '')
    .replace(/[\u00a0\u3000]/g, ' ')
    .replace(/[¥￥](?=[A-Za-z]+(?:\{|\b))/g, '\\')
    .split('\n')
    .map(line => line.replace(/[ \t]+$/g, ''))
    .join('\n')
    .replace(/\n{4,}/g, '\n\n\n')
    .trim()

  normalized = normalized
    .replace(/\\operatorname\{\s*c\s*o\s*s\s*\}\s*/giu, '\\cos ')
    .replace(/\\operatorname\{\s*s\s*i\s*n\s*\}\s*/giu, '\\sin ')
    .replace(/\\operatorname\{\s*t\s*a\s*n\s*\}\s*/giu, '\\tan ')
    .replace(/\b([A-Za-z])\s+\$([_^])/gu, (_match, base: string, operator: string) => `$${base}${operator}`)
    .replace(/(?:\\bullet\s*){2,}/g, '\\cdots ')
    .replace(/よう[。．]\s*な/gu, 'ような')
    .replace(/(内心\s*を)\s*[1l](?=\s*(?:と|、|,|\.|。))/gu, '$1I')

  const namedPoints = new Set(
    [...normalized.matchAll(/(?:外心|内心|重心|垂心|傍心|中心)\s*を\s*([A-Z])/gu)]
      .map(match => match[1]),
  )
  const canonicalPoint = (value: string) => {
    const upper = value.toUpperCase()
    if (namedPoints.has(upper)) return upper
    if (namedPoints.has('I') && /^[1l]$/u.test(value)) return 'I'
    if (namedPoints.has('O') && /^[0o]$/u.test(value)) return 'O'
    return value
  }
  normalized = normalized.replace(
    /\\mathrm\{\s*([A-Za-z0-9])\s+([A-Za-z0-9])\s*\^\{([0-9]+)\}\s*\}/gu,
    (match, first: string, second: string, exponent: string) => {
      const canonicalFirst = canonicalPoint(first)
      const canonicalSecond = canonicalPoint(second)
      return namedPoints.has(canonicalFirst) && namedPoints.has(canonicalSecond)
        ? `${canonicalFirst}${canonicalSecond}^{${exponent}}`
        : match
    },
  )

  const denominatorCounts = new Map<string, number>()
  for (let index = 0; index < normalized.length; index += 1) {
    if (!normalized.startsWith('\\frac', index)) continue
    let cursor = index + 5
    const readGroup = () => {
      while (/\s/u.test(normalized[cursor] ?? '')) cursor += 1
      if (normalized[cursor] !== '{') return null
      const start = ++cursor
      let depth = 1
      while (cursor < normalized.length && depth > 0) {
        if (normalized[cursor] === '{') depth += 1
        if (normalized[cursor] === '}') depth -= 1
        cursor += 1
      }
      return depth === 0 ? normalized.slice(start, cursor - 1).trim() : null
    }
    if (readGroup() === null) continue
    const denominator = readGroup()
    if (denominator && /^[A-Za-z]$/u.test(denominator)) {
      denominatorCounts.set(denominator, (denominatorCounts.get(denominator) ?? 0) + 1)
    }
  }
  const repeatedDenominators = [...denominatorCounts].filter(([, count]) => count >= 2)
  if (repeatedDenominators.length === 1) {
    const denominator = repeatedDenominators[0][0]
    normalized = normalized.replace(/(正の整数)\s*[A-Za-z]\s*(の)/gu, `$1${denominator}$2`)
  }

  if (normalized.includes('\ufffd')) {
    throw new Error('文字を復元できない箇所があります。画像を撮り直すか、認識結果を確認してください。')
  }
  if (normalized.length < 3) {
    throw new Error('問題文を読み取れませんでした。文字が大きく写った画像または文字層のあるPDFを使用してください。')
  }
  return normalized
}

export function problemDocumentKind(file: Pick<File, 'name' | 'type' | 'size'>): ProblemDocumentKind {
  const extension = file.name.toLowerCase().split('.').pop() ?? ''
  if (file.type === PDF_MIME || extension === 'pdf') return 'pdf'
  if (IMAGE_MIMES.has(file.type) || ['png', 'jpg', 'jpeg', 'webp'].includes(extension)) return 'image'
  throw new Error('PNG、JPEG、WebP、PDFのいずれかを選択してください。')
}

export function validateProblemDocument(file: Pick<File, 'name' | 'type' | 'size'>) {
  const kind = problemDocumentKind(file)
  if (file.size <= 0) throw new Error('空のファイルは読み取れません。')
  if (file.size > MAX_PROBLEM_DOCUMENT_BYTES) {
    throw new Error(`ファイルは${Math.floor(MAX_PROBLEM_DOCUMENT_BYTES / 1024 / 1024)}MB以内にしてください。`)
  }
  return kind
}

function textFromPdfItems(items: PdfTextItem[]) {
  const lines: string[] = []
  let line = ''
  for (const item of items) {
    const value = item.str ?? ''
    if (value) line += value
    if (item.hasEOL) {
      if (line.trim()) lines.push(line.trim())
      line = ''
    } else if (value && !/\s$/.test(value)) {
      line += ' '
    }
  }
  if (line.trim()) lines.push(line.trim())
  return lines.join('\n')
}

function hasUsablePdfText(value: string) {
  const compact = value.replace(/\s/g, '')
  if (compact.length < 8) return false
  const meaningful = compact.match(/[A-Za-z0-9\u3040-\u30ff\u3400-\u9fff\u00c0-\u024f\u0370-\u03ff=+\-*/^_(){}\[\]<>≤≥∫∑√π]/g)?.length ?? 0
  return meaningful / compact.length >= 0.62
}

export function pdfTextNeedsFormulaOcr(value: string) {
  const compact = value.replace(/\s/g, '')
  if (!compact) return false
  const structuralSymbols = compact.match(/[∫∑∏√∞≤≥≠≈∂]/gu)?.length ?? 0
  const relationSymbols = compact.match(/[=<>]/g)?.length ?? 0
  const scriptLikeRuns = compact.match(/[A-Za-z0-9][0-9]+|[0-9]+[A-Za-z]/g)?.length ?? 0
  return structuralSymbols > 0 || relationSymbols >= 2 || scriptLikeRuns >= 4
}

export function extractPrimaryProblemText(value: string) {
  const displays = [...value.matchAll(/\$\$\s*([\s\S]*?)\s*\$\$/g)]
  if (displays.length < 2) return { text: value, trimmed: false }

  const first = displays[0]
  const firstLatex = first[1] ?? ''
  const rest = value.slice((first.index ?? 0) + first[0].length)
  const hasProblemStructure = /(?:\\int|\\sum|\\lim|\\prod|\\frac|[=<>]|\\leq?|\\geq?)/u.test(firstLatex)
  const hasWorkedContinuation = displays.length >= 3
    || /(?:^|\n)\s*(?:解答|解法|証明|別解|[A-Za-z]\s*=)/mu.test(rest)
  if (!hasProblemStructure || !hasWorkedContinuation) return { text: value, trimmed: false }

  const prefix = value.slice(0, first.index ?? 0)
    .split('\n')
    .map(line => line.trim())
    .filter(line => (line.match(/[\u3040-\u30ff\u3400-\u9fff]/gu)?.length ?? 0) >= 3)
    .join('\n')
  return {
    text: [prefix, first[0].trim()].filter(Boolean).join('\n'),
    trimmed: true,
  }
}

function overlapLength(a0: number, a1: number, b0: number, b1: number) {
  return Math.max(0, Math.min(a1, b1) - Math.max(a0, b0))
}

function verticalOverlapRatio(line: RecognizedProblemLine, formula: RecognizedFormulaBox) {
  const overlap = overlapLength(line.bbox.y0, line.bbox.y1, formula.box.y0, formula.box.y1)
  return overlap / Math.max(1, Math.min(line.bbox.y1 - line.bbox.y0, formula.box.y1 - formula.box.y0))
}

function lineOverlapRatio(a: RecognizedProblemLine, b: RecognizedProblemLine) {
  const overlap = overlapLength(a.bbox.y0, a.bbox.y1, b.bbox.y0, b.bbox.y1)
  return overlap / Math.max(1, Math.min(a.bbox.y1 - a.bbox.y0, b.bbox.y1 - b.bbox.y0))
}

function isJapanese(value: string) {
  return /[\u3040-\u30ff\u3400-\u9fff]/u.test(value)
}

function isClosingPunctuation(value: string) {
  return /^[、。，．,.!?！？:：;；)）\]】}」』]/u.test(value)
}

function joinRecognizedTokens(tokens: Array<{
  text: string
  x0: number
  x1: number
  formula: boolean
}>, lineHeight: number) {
  let output = ''
  let previous: (typeof tokens)[number] | null = null
  for (const token of tokens.sort((a, b) => a.x0 - b.x0 || a.x1 - b.x1)) {
    if (!token.text) continue
    if (previous) {
      const gap = token.x0 - previous.x1
      const needsSpace = previous.formula
        || token.formula
        || (!isJapanese(previous.text) && !isJapanese(token.text) && gap > lineHeight * 0.16)
      if (needsSpace && !isClosingPunctuation(token.text) && !/\s$/u.test(output)) output += ' '
    }
    output += token.text
    previous = token
  }
  return output.trim()
}

function symbolBelongsToFormula(symbol: RecognizedProblemSymbol, formula: RecognizedFormulaBox) {
  const centerX = (symbol.bbox.x0 + symbol.bbox.x1) / 2
  const centerY = (symbol.bbox.y0 + symbol.bbox.y1) / 2
  if (centerX < formula.box.x0 || centerX > formula.box.x1 || centerY < formula.box.y0 || centerY > formula.box.y1) {
    return false
  }
  const relativeX = (centerX - formula.box.x0) / Math.max(1, formula.box.x1 - formula.box.x0)
  const reliableJapaneseBoundary = symbol.confidence >= 97
    && isJapanese(symbol.text)
    && (relativeX <= 0.25 || relativeX >= 0.78)
  return !reliableJapaneseBoundary
}

function formulaDisplayBox(formula: RecognizedFormulaBox, symbols: RecognizedProblemSymbol[]) {
  const width = Math.max(1, formula.box.x1 - formula.box.x0)
  const preserved = symbols.filter(symbol => {
    const centerX = (symbol.bbox.x0 + symbol.bbox.x1) / 2
    const centerY = (symbol.bbox.y0 + symbol.bbox.y1) / 2
    return centerX >= formula.box.x0
      && centerX <= formula.box.x1
      && centerY >= formula.box.y0
      && centerY <= formula.box.y1
      && !symbolBelongsToFormula(symbol, formula)
  })
  const left = preserved.filter(symbol => (
    (symbol.bbox.x0 + symbol.bbox.x1) / 2 <= formula.box.x0 + width * 0.35
  ))
  const right = preserved.filter(symbol => (
    (symbol.bbox.x0 + symbol.bbox.x1) / 2 >= formula.box.x0 + width * 0.65
  ))
  return {
    x0: left.length > 0
      ? Math.max(formula.box.x0, Math.max(...left.map(symbol => symbol.bbox.x1)) + 2)
      : formula.box.x0,
    x1: right.length > 0
      ? Math.min(formula.box.x1, Math.min(...right.map(symbol => symbol.bbox.x0)) - 2)
      : formula.box.x1,
  }
}

function consolidateRecognizedLines(lines: RecognizedProblemLine[]) {
  const groups: RecognizedProblemLine[][] = []
  for (const line of [...lines].sort((a, b) => a.bbox.y0 - b.bbox.y0 || a.bbox.x0 - b.bbox.x0)) {
    const group = groups.find(candidate => candidate.some(other => lineOverlapRatio(line, other) >= 0.55))
    if (group) group.push(line)
    else groups.push([line])
  }
  return groups.map(group => {
    const symbols = group.flatMap(line => line.symbols)
      .filter((symbol, index, all) => !all.slice(0, index).some(previous => {
        if (previous.text !== symbol.text) return false
        const centerX = (symbol.bbox.x0 + symbol.bbox.x1) / 2
        const centerY = (symbol.bbox.y0 + symbol.bbox.y1) / 2
        const previousX = (previous.bbox.x0 + previous.bbox.x1) / 2
        const previousY = (previous.bbox.y0 + previous.bbox.y1) / 2
        return Math.abs(centerX - previousX) <= 2 && Math.abs(centerY - previousY) <= 2
      }))
    return {
      text: group.map(line => line.text).join(' '),
      confidence: group.reduce((sum, line) => sum + line.confidence, 0) / group.length,
      bbox: {
        x0: Math.min(...group.map(line => line.bbox.x0)),
        y0: Math.min(...group.map(line => line.bbox.y0)),
        x1: Math.max(...group.map(line => line.bbox.x1)),
        y1: Math.max(...group.map(line => line.bbox.y1)),
      },
      symbols,
    }
  })
}

export function mergeRecognizedProblemLines(
  lines: RecognizedProblemLine[],
  fallbackText: string,
  formulas: RecognizedFormulaBox[],
) {
  if (lines.length === 0 || formulas.length === 0) return fallbackText
  lines = consolidateRecognizedLines(lines)
  const assigned = new Map<number, RecognizedFormulaBox[]>()
  const unassigned = new Set(formulas)
  for (const formula of formulas) {
    let bestLine = -1
    let bestOverlap = 0
    lines.forEach((line, index) => {
      const overlap = verticalOverlapRatio(line, formula)
      if (overlap > bestOverlap) {
        bestLine = index
        bestOverlap = overlap
      }
    })
    if (bestLine >= 0 && bestOverlap >= 0.35) {
      assigned.set(bestLine, [...(assigned.get(bestLine) ?? []), formula])
      unassigned.delete(formula)
    }
  }

  const output: Array<{ y: number; text: string }> = []
  lines.forEach((line, index) => {
    const lineFormulas = assigned.get(index) ?? []
    if (lineFormulas.some(formula => formula.type === 'isolated')) {
      const surroundingText = line.symbols
        .filter(symbol => !formulas.some(formula => symbolBelongsToFormula(symbol, formula)))
        .map(symbol => symbol.text)
        .join('')
        .trim()
      if (surroundingText) output.push({ y: line.bbox.y0, text: surroundingText })
      for (const formula of lineFormulas) {
        output.push({ y: formula.box.y0 + 0.1, text: `$$\n${formula.latex}\n$$` })
      }
      return
    }

    const tokens = line.symbols
      .filter(symbol => !formulas.some(formula => symbolBelongsToFormula(symbol, formula)))
      .map(symbol => ({
        text: symbol.text,
        x0: symbol.bbox.x0,
        x1: symbol.bbox.x1,
        formula: false,
      }))
    for (const formula of lineFormulas) {
      const display = formulaDisplayBox(formula, line.symbols)
      tokens.push({
        text: `$${formula.latex}$`,
        x0: display.x0,
        x1: display.x1,
        formula: true,
      })
    }
    const text = joinRecognizedTokens(tokens, Math.max(1, line.bbox.y1 - line.bbox.y0))
    const punctuationOnly = !/[A-Za-z0-9぀-ヿ㐀-鿿]/u.test(text)
    if (text && !(line.confidence < 50 && punctuationOnly)) output.push({ y: line.bbox.y0, text })
  })
  for (const formula of unassigned) {
    output.push({ y: formula.box.y0, text: `$$\n${formula.latex}\n$$` })
  }
  return output.sort((a, b) => a.y - b.y).map(item => item.text).join('\n')
}

function linesFromTesseractBlocks(blocks: TesseractBlock[] | null) {
  if (!blocks) return []
  return blocks.flatMap(block => block.paragraphs.flatMap(paragraph => paragraph.lines.map(line => ({
    text: line.text,
    confidence: line.confidence,
    bbox: line.bbox,
    symbols: line.words.flatMap(word => word.symbols),
  }))))
}

async function createOcrWorker(listener: ProgressListener) {
  const { createWorker, OEM, PSM } = await import('tesseract.js')
  const worker = await createWorker(['jpn', 'eng'], OEM.LSTM_ONLY, {
    logger(message) {
      if (message.status !== 'recognizing text') return
      listener({ phase: 'recognizing', progress: Math.max(0, Math.min(1, message.progress)) })
    },
  })
  await worker.setParameters({
    preserve_interword_spaces: '1',
    tessedit_pageseg_mode: PSM.AUTO,
    user_defined_dpi: '300',
  })
  return worker
}

async function recognizeImage(file: File | Blob, listener: ProgressListener) {
  const worker = await createOcrWorker(listener)
  try {
    const result = await worker.recognize(file, { rotateAuto: true }, { blocks: true, text: true })
    const lines = linesFromTesseractBlocks(result.data.blocks as TesseractBlock[] | null)
    const symbols = lines.flatMap(line => line.symbols)
    let formulas: RecognizedFormulaBox[] = []
    let detected = 0
    let rejected = 0
    const warnings: string[] = []
    try {
      const { recognizeFormulaRegions } = await import('./problem-formula-ocr')
      const formulaResult = await recognizeFormulaRegions(file, symbols, progress => listener({
        phase: 'recognizing',
        progress,
      }))
      formulas = formulaResult.boxes
      detected = formulaResult.detected
      rejected = formulaResult.rejected
      if (rejected > 0) warnings.push('確度の低い数式候補を自動採用せず、本文OCRを残しました。')
    } catch (error) {
      warnings.push(error instanceof Error ? error.message : String(error))
    }
    return {
      text: mergeRecognizedProblemLines(lines, result.data.text, formulas),
      confidence: result.data.confidence,
      formulaBoxes: formulas.length,
      rejectedFormulaBoxes: rejected || Math.max(0, detected - formulas.length),
      warnings,
    }
  } finally {
    await worker.terminate()
  }
}

async function canvasBlob(canvas: HTMLCanvasElement) {
  return await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(blob => {
      if (blob) resolve(blob)
      else reject(new Error('PDFページを画像へ変換できませんでした。'))
    }, 'image/png')
  })
}

async function extractPdf(file: File, listener: ProgressListener): Promise<ProblemDocumentResult> {
  listener({ phase: 'loading', progress: 0 })
  const pdfjs = await import('pdfjs-dist/legacy/build/pdf.mjs')
  pdfjs.GlobalWorkerOptions.workerSrc = new URL(
    'pdfjs-dist/legacy/build/pdf.worker.min.mjs',
    import.meta.url,
  ).toString()

  const data = new Uint8Array(await file.arrayBuffer())
  const loadingTask = pdfjs.getDocument({ data, useSystemFonts: true })
  const pdfDocument = await loadingTask.promise
  const pageCount = pdfDocument.numPages
  if (pageCount > MAX_PROBLEM_DOCUMENT_PAGES) {
    await loadingTask.destroy()
    throw new Error(`PDFは${MAX_PROBLEM_DOCUMENT_PAGES}ページ以内にしてください。`)
  }

  const output: string[] = []
  let ocrPages = 0
  let formulaBoxes = 0
  let rejectedFormulaBoxes = 0
  const ocrConfidences: number[] = []
  const warnings: string[] = []
  const inputPageCount = Math.min(pageCount, MAX_PROBLEM_INPUT_PAGES)
  if (pageCount > inputPageCount) {
    warnings.push(`一つの問題入力として、PDF ${pageCount}ページ中の先頭${inputPageCount}ページだけを読み取りました。`)
  }

  try {
    for (let index = 1; index <= inputPageCount; index += 1) {
      listener({ phase: 'extracting', progress: (index - 1) / inputPageCount, page: index, pages: inputPageCount })
      const page = await pdfDocument.getPage(index)
      const content = await page.getTextContent()
      const extracted = textFromPdfItems(content.items as PdfTextItem[])
      if (hasUsablePdfText(extracted) && !pdfTextNeedsFormulaOcr(extracted)) {
        const primary = extractPrimaryProblemText(extracted)
        output.push(primary.text)
        if (primary.trimmed) warnings.push('先頭ページの後続解答を分離し、最初の問題だけを入力しました。')
        page.cleanup()
        continue
      }

      const base = page.getViewport({ scale: 1 })
      const scale = Math.max(1.35, Math.min(2.4, 2400 / Math.max(base.width, base.height)))
      const viewport = page.getViewport({ scale })
      const canvas = window.document.createElement('canvas')
      canvas.width = Math.ceil(viewport.width)
      canvas.height = Math.ceil(viewport.height)
      const context = canvas.getContext('2d', { alpha: false })
      if (!context) throw new Error('PDFページの描画を開始できませんでした。')
      context.fillStyle = '#ffffff'
      context.fillRect(0, 0, canvas.width, canvas.height)
      await page.render({ canvas, canvasContext: context, viewport }).promise
      const image = await canvasBlob(canvas)
      const recognized = await recognizeImage(image, progress => listener({
        ...progress,
        progress: ((index - 1) + progress.progress) / inputPageCount,
        page: index,
        pages: inputPageCount,
      }))
      const primary = extractPrimaryProblemText(recognized.text)
      output.push(primary.text)
      if (primary.trimmed) warnings.push('先頭ページの後続解答を分離し、最初の問題だけを入力しました。')
      ocrPages += 1
      formulaBoxes += recognized.formulaBoxes
      rejectedFormulaBoxes += recognized.rejectedFormulaBoxes
      ocrConfidences.push(recognized.confidence)
      warnings.push(...recognized.warnings)
      canvas.width = 1
      canvas.height = 1
      page.cleanup()
    }
  } finally {
    await loadingTask.destroy()
  }

  listener({ phase: 'complete', progress: 1, pages: inputPageCount })
  return {
    text: normalizeRecognizedProblemText(output.join('\n\n')),
    kind: 'pdf',
    method: ocrPages === 0 ? 'pdf_text' : ocrPages === inputPageCount ? 'ocr' : 'hybrid',
    pages: pageCount,
    ocrPages,
    fileName: file.name,
    formulaBoxes,
    rejectedFormulaBoxes,
    ocrConfidence: ocrConfidences.length > 0
      ? ocrConfidences.reduce((sum, value) => sum + value, 0) / ocrConfidences.length
      : undefined,
    warnings: [...new Set(warnings)],
  }
}

export async function extractProblemDocument(
  file: File,
  listener: ProgressListener = () => undefined,
): Promise<ProblemDocumentResult> {
  const kind = validateProblemDocument(file)
  if (kind === 'pdf') return extractPdf(file, listener)

  listener({ phase: 'loading', progress: 0, page: 1, pages: 1 })
  const recognized = await recognizeImage(file, progress => listener({ ...progress, page: 1, pages: 1 }))
  listener({ phase: 'complete', progress: 1, page: 1, pages: 1 })
  return {
    text: normalizeRecognizedProblemText(recognized.text),
    kind: 'image',
    method: 'ocr',
    pages: 1,
    ocrPages: 1,
    fileName: file.name,
    formulaBoxes: recognized.formulaBoxes,
    rejectedFormulaBoxes: recognized.rejectedFormulaBoxes,
    ocrConfidence: recognized.confidence,
    warnings: recognized.warnings,
  }
}
