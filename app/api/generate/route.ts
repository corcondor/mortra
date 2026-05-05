import { NextRequest } from 'next/server'
import { spawn }       from 'child_process'
import path            from 'path'
import os              from 'os'
import fs              from 'fs/promises'
import { IS_VERCEL, LOCAL_ONLY_RESPONSE } from '@/lib/env'

const PIPELINE_DIR = 'C:/Users/81808/.openclaw/workspace/automation/pipeline'
const SCRIPTS_DIR  = 'C:/Users/81808/.openclaw/workspace/math-web/scripts'
const PYTHON       = 'python'

// ── シンプルな直列キュー ──────────────────────────────────────────
// 複数ユーザーが同時にボタンを押しても1つずつ処理する
let _queue: (() => void)[] = []
let _busy  = false

function enqueue(): Promise<void> {
  return new Promise(resolve => {
    _queue.push(resolve)
    if (!_busy) _drain()
  })
}
function _drain() {
  if (_queue.length === 0) { _busy = false; return }
  _busy = true
  const next = _queue.shift()!
  next()
}
function dequeue() {
  _drain()
}

export function GET() {
  if (IS_VERCEL) return LOCAL_ONLY_RESPONSE()
  return new Response(
    JSON.stringify({ queueLength: _queue.length, busy: _busy }),
    { headers: { 'Content-Type': 'application/json' } }
  )
}

// ── ログ行からステップ判定 ────────────────────────────────────────
function detectStep(line: string): string {
  const l = line.toLowerCase()
  if (l.includes('起動') || l.includes('start'))                    return 'start'
  if (l.includes('gemini') || l.includes('chrome') || l.includes('接続'))  return 'opening'
  if (l.includes('プロンプト') || l.includes('送信') || l.includes('入力')) return 'typing'
  if (l.includes('待ち') || l.includes('wait') || l.includes('応答'))       return 'waiting'
  if (l.includes('json') || l.includes('取得') || l.includes('成功'))       return 'extracting'
  if (l.includes('保存') || l.includes('insert') || l.includes('db'))       return 'saving'
  if (l.includes('同期') || l.includes('sync') || l.includes('supabase'))   return 'syncing'
  if (l.includes('完了') || l.includes('✅'))                               return 'done'
  return 'working'
}

export async function POST(req: NextRequest) {
  if (IS_VERCEL) return LOCAL_ONLY_RESPONSE()
  const { parents, mode = 'auto', count = 3 } = await req.json()
  if (!parents || parents.length === 0)
    return new Response(JSON.stringify({ error: 'parents required' }), { status: 400 })

  const tmpFile = path.join(os.tmpdir(), `parents_${Date.now()}.json`)
  await fs.writeFile(tmpFile, JSON.stringify(parents), 'utf-8')

  const encoder = new TextEncoder()

  const stream = new ReadableStream({
    async start(controller) {
      const send = (type: string, payload: Record<string, unknown>) => {
        try {
          controller.enqueue(
            encoder.encode(`data: ${JSON.stringify({ type, ...payload })}\n\n`)
          )
        } catch { /* client disconnected */ }
      }

      // キューに入れて待機
      const qPos = _queue.length + (_busy ? 1 : 0)
      if (qPos > 0) {
        send('status', { step: 'queued', message: `キュー待ち（あと ${qPos} 件）...` })
      }

      await enqueue()   // 自分の番まで待つ

      send('status', { step: 'start', message: '生成パイプライン起動...' })

      const subEnv = {
        ...process.env,
        NEXT_PUBLIC_SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL ?? '',
        SUPABASE_SERVICE_KEY:     process.env.SUPABASE_SERVICE_KEY ?? '',
      }

      const proc = spawn(PYTHON, [
        path.join(PIPELINE_DIR, 'mutate_problems.py'),
        '--parents-file', tmpFile,
        '--mode',         mode,
        '--count',        String(count),
      ], { cwd: PIPELINE_DIR, env: subEnv })

      proc.stdout.on('data', (d: Buffer) => {
        d.toString().split('\n').filter(Boolean).forEach(line => {
          send('log', { message: line, step: detectStep(line) })
        })
      })
      proc.stderr.on('data', (d: Buffer) =>
        d.toString().split('\n').filter(Boolean).forEach(line =>
          send('log', { message: line, isError: true, step: 'working' })
        )
      )

      proc.on('close', async (code: number) => {
        await fs.unlink(tmpFile).catch(() => {})
        dequeue()   // 次のキューを解放

        if (code === 0) {
          send('status', { step: 'syncing', message: 'Supabase に同期中...' })
          const syncProc = spawn(PYTHON,
            [path.join(SCRIPTS_DIR, 'sync_sqlite_supabase.py')],
            { env: subEnv }
          )
          syncProc.stdout.on('data', (d: Buffer) =>
            d.toString().split('\n').filter(Boolean).forEach(line =>
              send('log', { message: line, step: 'syncing' })
            )
          )
          syncProc.on('close', () => {
            send('status', { step: 'complete', message: '完了！問題一覧を更新してください。' })
            send('done', { ok: true })
            controller.close()
          })
        } else {
          send('status', { step: 'error', message: 'エラーが発生しました' })
          send('done', { ok: false })
          controller.close()
        }
      })

      // 15 分タイムアウト
      setTimeout(() => {
        proc.kill()
        dequeue()
        send('status', { step: 'error', message: 'タイムアウト (15 分)' })
        send('done', { ok: false })
        controller.close()
      }, 900_000)
    },
  })

  return new Response(stream, {
    headers: {
      'Content-Type':  'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection':    'keep-alive',
    },
  })
}
