import type { FormulaOcrResult, FormulaOcrSymbol } from './problem-formula-regions'

export type {
  FormulaOcrBox,
  FormulaOcrRegionProposal,
  FormulaOcrResult,
  FormulaOcrSymbol,
} from './problem-formula-regions'
export { proposeFormulaFallbackBoxes } from './problem-formula-regions'

type FormulaWorkerProgress = {
  type: 'progress'
  id: string
  progress: number
}

type FormulaWorkerResult = {
  type: 'result'
  id: string
  result: FormulaOcrResult
}

type FormulaWorkerError = {
  type: 'error'
  id: string
  error: string
}

type FormulaWorkerMessage = FormulaWorkerProgress | FormulaWorkerResult | FormulaWorkerError

export async function recognizeFormulaRegions(
  image: File | Blob,
  symbols: FormulaOcrSymbol[],
  onProgress: (progress: number) => void = () => undefined,
): Promise<FormulaOcrResult> {
  if (typeof Worker === 'undefined') {
    throw new Error('数式認識を実行できるブラウザ環境ではありません。')
  }

  const id = crypto.randomUUID()
  const worker = new Worker(new URL('./problem-formula-ocr.worker.ts', import.meta.url), {
    type: 'module',
  })

  return await new Promise<FormulaOcrResult>((resolve, reject) => {
    const dispose = () => worker.terminate()
    worker.onerror = event => {
      dispose()
      reject(new Error(event.message || '数式認識ワーカーを開始できませんでした。'))
    }
    worker.onmessage = (event: MessageEvent<FormulaWorkerMessage>) => {
      const message = event.data
      if (message.id !== id) return
      if (message.type === 'progress') {
        onProgress(Math.max(0, Math.min(1, message.progress)))
        return
      }
      dispose()
      if (message.type === 'error') {
        reject(new Error(message.error))
        return
      }
      resolve(message.result)
    }
    worker.postMessage({ type: 'recognize', id, image, symbols })
  })
}
