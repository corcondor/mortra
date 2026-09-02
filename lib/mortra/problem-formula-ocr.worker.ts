import { AutoTokenizer } from '@huggingface/transformers'
import * as ort from 'onnxruntime-web'

import type {
  FormulaOcrBox,
  FormulaOcrResult,
  FormulaOcrSymbol,
} from './problem-formula-regions'
import { proposeFormulaFallbackBoxes } from './problem-formula-regions'

type WorkerRequest = {
  type: 'recognize'
  id: string
  image: File | Blob
  symbols: FormulaOcrSymbol[]
}

type DetectorBox = {
  type: 'embedding' | 'isolated'
  score: number
  x0: number
  y0: number
  x1: number
  y1: number
}

type Tokenizer = Awaited<ReturnType<typeof AutoTokenizer.from_pretrained>>
type Session = Awaited<ReturnType<typeof ort.InferenceSession.create>>

const MODEL_ROOT = 'https://huggingface.co/breezedeus'
const MODEL_FILES = {
  detector: {
    url: `${MODEL_ROOT}/pix2text-mfd-1.5/resolve/main/pix2text-mfd-1.5.onnx`,
    bytes: 80_311_115,
  },
  encoder: {
    url: `${MODEL_ROOT}/pix2text-mfr-1.5/resolve/main/encoder_model.onnx`,
    bytes: 87_510_770,
  },
  decoder: {
    url: `${MODEL_ROOT}/pix2text-mfr-1.5/resolve/main/decoder_model.onnx`,
    bytes: 32_026_253,
  },
} as const
const MODEL_TOTAL_BYTES = Object.values(MODEL_FILES).reduce((sum, file) => sum + file.bytes, 0)
const DETECTOR_SIZE = 768
const RECOGNIZER_SIZE = 384
const DETECTOR_THRESHOLD = 0.25
const NMS_THRESHOLD = 0.45
const MAX_FORMULA_TOKENS = 160

const scope = globalThis as unknown as {
  onmessage: ((event: MessageEvent<WorkerRequest>) => void) | null
  postMessage: (message: unknown) => void
}

function report(id: string, progress: number) {
  scope.postMessage({ type: 'progress', id, progress: Math.max(0, Math.min(1, progress)) })
}

async function fetchModel(
  id: string,
  asset: { url: string; bytes: number },
  precedingBytes: number,
) {
  const response = await fetch(asset.url, { cache: 'force-cache', mode: 'cors' })
  if (!response.ok) throw new Error(`数式認識モデルを取得できませんでした (${response.status})。`)
  if (!response.body) {
    const buffer = await response.arrayBuffer()
    report(id, (precedingBytes + asset.bytes) / MODEL_TOTAL_BYTES * 0.72)
    return new Uint8Array(buffer)
  }

  const reader = response.body.getReader()
  const chunks: Uint8Array[] = []
  let loaded = 0
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    if (!value) continue
    chunks.push(value)
    loaded += value.byteLength
    report(id, (precedingBytes + Math.min(asset.bytes, loaded)) / MODEL_TOTAL_BYTES * 0.72)
  }
  const output = new Uint8Array(loaded)
  let offset = 0
  for (const chunk of chunks) {
    output.set(chunk, offset)
    offset += chunk.byteLength
  }
  return output
}

async function createSession(
  id: string,
  asset: { url: string; bytes: number },
  precedingBytes: number,
) {
  const model = await fetchModel(id, asset, precedingBytes)
  return await ort.InferenceSession.create(model, {
    executionProviders: ['wasm'],
    graphOptimizationLevel: 'all',
  })
}

async function loadModels(id: string) {
  ort.env.wasm.numThreads = 1
  ort.env.wasm.proxy = false
  ort.env.wasm.wasmPaths = 'https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.8.1/dist/'

  let preceding = 0
  const detector = await createSession(id, MODEL_FILES.detector, preceding)
  preceding += MODEL_FILES.detector.bytes
  const encoder = await createSession(id, MODEL_FILES.encoder, preceding)
  preceding += MODEL_FILES.encoder.bytes
  const decoder = await createSession(id, MODEL_FILES.decoder, preceding)
  const tokenizer = await AutoTokenizer.from_pretrained('breezedeus/pix2text-mfr-1.5')
  report(id, 0.76)
  return { detector, encoder, decoder, tokenizer }
}

function detectorInput(bitmap: ImageBitmap) {
  const scale = Math.min(DETECTOR_SIZE / bitmap.width, DETECTOR_SIZE / bitmap.height)
  const width = Math.max(1, Math.round(bitmap.width * scale))
  const height = Math.max(1, Math.round(bitmap.height * scale))
  const left = Math.floor((DETECTOR_SIZE - width) / 2)
  const top = Math.floor((DETECTOR_SIZE - height) / 2)
  const canvas = new OffscreenCanvas(DETECTOR_SIZE, DETECTOR_SIZE)
  const context = canvas.getContext('2d', { willReadFrequently: true })
  if (!context) throw new Error('数式領域の画像処理を開始できませんでした。')
  context.fillStyle = 'rgb(114, 114, 114)'
  context.fillRect(0, 0, DETECTOR_SIZE, DETECTOR_SIZE)
  context.drawImage(bitmap, left, top, width, height)
  const pixels = context.getImageData(0, 0, DETECTOR_SIZE, DETECTOR_SIZE).data
  const area = DETECTOR_SIZE * DETECTOR_SIZE
  const input = new Float32Array(area * 3)
  for (let index = 0; index < area; index += 1) {
    input[index] = pixels[index * 4] / 255
    input[area + index] = pixels[index * 4 + 1] / 255
    input[area * 2 + index] = pixels[index * 4 + 2] / 255
  }
  return { input, scale, left, top }
}

function intersectionOverUnion(a: DetectorBox, b: DetectorBox) {
  const x0 = Math.max(a.x0, b.x0)
  const y0 = Math.max(a.y0, b.y0)
  const x1 = Math.min(a.x1, b.x1)
  const y1 = Math.min(a.y1, b.y1)
  const intersection = Math.max(0, x1 - x0) * Math.max(0, y1 - y0)
  const areaA = Math.max(0, a.x1 - a.x0) * Math.max(0, a.y1 - a.y0)
  const areaB = Math.max(0, b.x1 - b.x0) * Math.max(0, b.y1 - b.y0)
  return intersection / Math.max(1, areaA + areaB - intersection)
}

async function detectFormulaBoxes(bitmap: ImageBitmap, detector: Session) {
  const { input, scale, left, top } = detectorInput(bitmap)
  const outputs = await detector.run({
    images: new ort.Tensor('float32', input, [1, 3, DETECTOR_SIZE, DETECTOR_SIZE]),
  })
  const prediction = outputs.output0
  const anchors = prediction.dims[2]
  const values = prediction.data as Float32Array
  const candidates: DetectorBox[] = []
  for (let index = 0; index < anchors; index += 1) {
    const embedding = values[anchors * 4 + index]
    const isolated = values[anchors * 5 + index]
    const type = isolated > embedding ? 'isolated' : 'embedding'
    const score = Math.max(embedding, isolated)
    if (score < DETECTOR_THRESHOLD) continue
    const centerX = values[index]
    const centerY = values[anchors + index]
    const width = values[anchors * 2 + index]
    const height = values[anchors * 3 + index]
    candidates.push({
      type,
      score,
      x0: Math.max(0, (centerX - width / 2 - left) / scale),
      y0: Math.max(0, (centerY - height / 2 - top) / scale),
      x1: Math.min(bitmap.width, (centerX + width / 2 - left) / scale),
      y1: Math.min(bitmap.height, (centerY + height / 2 - top) / scale),
    })
  }

  const selected: DetectorBox[] = []
  for (const candidate of candidates.sort((a, b) => b.score - a.score)) {
    if (selected.some(box => box.type === candidate.type && intersectionOverUnion(box, candidate) > NMS_THRESHOLD)) {
      continue
    }
    selected.push(candidate)
  }
  return selected.sort((a, b) => a.y0 - b.y0 || a.x0 - b.x0)
}

function verticalOverlap(box: DetectorBox, symbol: FormulaOcrSymbol) {
  const overlap = Math.max(0, Math.min(box.y1, symbol.bbox.y1) - Math.max(box.y0, symbol.bbox.y0))
  return overlap / Math.max(1, Math.min(box.y1 - box.y0, symbol.bbox.y1 - symbol.bbox.y0))
}

function recognitionBox(box: DetectorBox, symbols: FormulaOcrSymbol[]) {
  const height = Math.max(1, box.y1 - box.y0)
  const preceding = symbols
    .filter(symbol => verticalOverlap(box, symbol) >= 0.45)
    .filter(symbol => symbol.bbox.x1 <= box.x0)
    .filter(symbol => box.x0 - symbol.bbox.x1 <= height * 0.7)
    .filter(symbol => !/[\u3040-\u30ff\u3400-\u9fff]/u.test(symbol.text))
    .sort((a, b) => b.bbox.x1 - a.bbox.x1)
  const expandLeft = preceding.find(symbol => /[A-Za-z0-9]/u.test(symbol.text))
  const expanded = expandLeft ? { ...box, x0: Math.max(0, expandLeft.bbox.x0 - 4) } : box
  const width = expanded.x1 - expanded.x0
  const trailingJapanese = symbols
    .filter(symbol => symbol.confidence >= 96)
    .filter(symbol => /[\u3040-\u30ff\u3400-\u9fff]/u.test(symbol.text))
    .filter(symbol => verticalOverlap(expanded, symbol) >= 0.45)
    .filter(symbol => (symbol.bbox.x0 + symbol.bbox.x1) / 2 >= expanded.x0 + width * 0.78)
    .sort((a, b) => a.bbox.x0 - b.bbox.x0)[0]
  if (!trailingJapanese) return expanded
  const x1 = Math.max(expanded.x0 + 16, trailingJapanese.bbox.x0 - 10)
  return { ...expanded, x1: Math.min(expanded.x1, x1) }
}

function recognizerInput(bitmap: ImageBitmap, box: DetectorBox) {
  const canvas = new OffscreenCanvas(RECOGNIZER_SIZE, RECOGNIZER_SIZE)
  const context = canvas.getContext('2d', { willReadFrequently: true })
  if (!context) throw new Error('数式画像の復号を開始できませんでした。')
  context.fillStyle = '#ffffff'
  context.fillRect(0, 0, RECOGNIZER_SIZE, RECOGNIZER_SIZE)
  const x0 = Math.max(0, Math.floor(box.x0))
  const y0 = Math.max(0, Math.floor(box.y0))
  const x1 = Math.min(bitmap.width, Math.ceil(box.x1))
  const y1 = Math.min(bitmap.height, Math.ceil(box.y1))
  context.drawImage(bitmap, x0, y0, Math.max(1, x1 - x0), Math.max(1, y1 - y0), 0, 0, RECOGNIZER_SIZE, RECOGNIZER_SIZE)
  const pixels = context.getImageData(0, 0, RECOGNIZER_SIZE, RECOGNIZER_SIZE).data
  const area = RECOGNIZER_SIZE * RECOGNIZER_SIZE
  const input = new Float32Array(area * 3)
  for (let index = 0; index < area; index += 1) {
    input[index] = (pixels[index * 4] / 255 - 0.5) / 0.5
    input[area + index] = (pixels[index * 4 + 1] / 255 - 0.5) / 0.5
    input[area * 2 + index] = (pixels[index * 4 + 2] / 255 - 0.5) / 0.5
  }
  return input
}

async function recognizeFormula(
  bitmap: ImageBitmap,
  box: DetectorBox,
  encoder: Session,
  decoder: Session,
  tokenizer: Tokenizer,
) {
  const input = recognizerInput(bitmap, box)
  const encoded = await encoder.run({
    pixel_values: new ort.Tensor('float32', input, [1, 3, RECOGNIZER_SIZE, RECOGNIZER_SIZE]),
  })
  const hidden = encoded.last_hidden_state
  const ids = [1]
  const logProbabilities: number[] = []
  for (let step = 0; step < MAX_FORMULA_TOKENS; step += 1) {
    const decoded = await decoder.run({
      input_ids: new ort.Tensor('int64', BigInt64Array.from(ids, BigInt), [1, ids.length]),
      encoder_hidden_states: hidden,
    })
    const logits = decoded.logits
    const values = logits.data as Float32Array
    const vocabulary = logits.dims[2]
    const offset = (ids.length - 1) * vocabulary
    let bestId = 0
    let bestLogit = Number.NEGATIVE_INFINITY
    for (let index = 0; index < vocabulary; index += 1) {
      const value = values[offset + index]
      if (value > bestLogit) {
        bestId = index
        bestLogit = value
      }
    }
    let denominator = 0
    for (let index = 0; index < vocabulary; index += 1) {
      denominator += Math.exp(values[offset + index] - bestLogit)
    }
    logProbabilities.push(-Math.log(Math.max(Number.EPSILON, denominator)))
    ids.push(bestId)
    if (bestId === 2) break
  }
  const confidence = Math.exp(logProbabilities.reduce((sum, value) => sum + value, 0) / Math.max(1, logProbabilities.length))
  return {
    latex: normalizeLatex(tokenizer.decode(ids, { skip_special_tokens: true })),
    confidence,
    terminated: ids.at(-1) === 2,
  }
}

function normalizeLatex(value: string) {
  return value
    .replace(/\s+/g, ' ')
    .replace(/\\operatorname\{\s*c\s*o\s*s\s*\}\s*/gi, '\\cos ')
    .replace(/\\operatorname\{\s*s\s*i\s*n\s*\}\s*/gi, '\\sin ')
    .replace(/\\operatorname\{\s*t\s*a\s*n\s*\}\s*/gi, '\\tan ')
    .replace(/\\([A-Za-z]+)\s+\{/g, '\\$1{')
    .replace(/\{\s+/g, '{')
    .replace(/\s+\}/g, '}')
    .replace(/\}\s+\{/g, '}{')
    .replace(/\s*([=+<>^_,])\s*/g, '$1')
    .replace(/\s*\(\s*/g, '(')
    .replace(/\s*\)\s*/g, ')')
    .replace(/\\,d\s+([A-Za-z])/g, '\\,d$1')
    .trim()
}

function balancedBraces(value: string) {
  let depth = 0
  for (const character of value) {
    if (character === '{') depth += 1
    if (character === '}') depth -= 1
    if (depth < 0) return false
  }
  return depth === 0
}

function acceptableFormula(box: DetectorBox, latex: string, confidence: number, terminated: boolean) {
  if (!terminated || confidence < 0.72 || latex.length === 0 || latex.length > 600) return false
  if (!balancedBraces(latex) || /(.)\1{9,}/u.test(latex)) return false
  const structural = /\\(?:frac|sqrt|sum|int|lim|prod|binom)\b|[=<>^_]/u.test(latex)
  if (box.type === 'isolated') return box.score >= 0.45
  return box.score >= 0.72 || (box.score >= 0.5 && structural)
}

async function run(request: WorkerRequest): Promise<FormulaOcrResult> {
  report(request.id, 0.01)
  const models = await loadModels(request.id)
  const bitmap = await createImageBitmap(request.image)
  try {
    const detectorBoxes = await detectFormulaBoxes(bitmap, models.detector)
    const detected = [...detectorBoxes]
    for (const fallback of proposeFormulaFallbackBoxes(request.symbols, bitmap.width, bitmap.height)) {
      const covered = detected.some(box => {
        const centerX = (fallback.x0 + fallback.x1) / 2
        const centerY = (fallback.y0 + fallback.y1) / 2
        return intersectionOverUnion(box, fallback) >= 0.18
          || (centerX >= box.x0 && centerX <= box.x1 && centerY >= box.y0 && centerY <= box.y1)
      })
      if (!covered) detected.push(fallback)
    }
    report(request.id, 0.79)
    const boxes: FormulaOcrBox[] = []
    let attempted = 0
    for (const box of detected) {
      if (box.score < (box.type === 'isolated' ? 0.35 : 0.45)) continue
      attempted += 1
      const cropBox = recognitionBox(box, request.symbols)
      const recognized = await recognizeFormula(
        bitmap,
        cropBox,
        models.encoder,
        models.decoder,
        models.tokenizer,
      )
      if (acceptableFormula(box, recognized.latex, recognized.confidence, recognized.terminated)) {
        boxes.push({
          type: box.type,
          box: { x0: cropBox.x0, y0: cropBox.y0, x1: cropBox.x1, y1: cropBox.y1 },
          latex: recognized.latex,
          detectionConfidence: box.score,
          recognitionConfidence: recognized.confidence,
        })
      }
      report(request.id, 0.79 + attempted / Math.max(1, detected.length) * 0.21)
    }
    return { boxes, detected: detected.length, rejected: detected.length - boxes.length }
  } finally {
    bitmap.close()
    await Promise.all([
      models.detector.release(),
      models.encoder.release(),
      models.decoder.release(),
    ])
  }
}

scope.onmessage = event => {
  const request = event.data
  if (request.type !== 'recognize') return
  void run(request)
    .then(result => scope.postMessage({ type: 'result', id: request.id, result }))
    .catch(error => scope.postMessage({
      type: 'error',
      id: request.id,
      error: error instanceof Error ? error.message : String(error),
    }))
}
