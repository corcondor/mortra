import { NextRequest, NextResponse } from 'next/server'
import { spawn } from 'child_process'
import path      from 'path'
import fs        from 'fs'
import os        from 'os'
import crypto    from 'crypto'
import { IS_VERCEL, LOCAL_ONLY_RESPONSE } from '@/lib/env'

const SCRIPTS_DIR = path.join(process.cwd(), 'scripts')
const PYTHON      = process.env.PYTHON_BIN ?? 'python'

function summarizeOutput(value: string, limit = 1200) {
  const text = value.replace(/\s+/g, ' ').trim()
  return text.length > limit ? `${text.slice(0, limit)}...` : text
}

export async function POST(req: NextRequest) {
  if (IS_VERCEL && process.env.ENABLE_VERCEL_PYTHON_ACTIONS !== '1') return LOCAL_ONLY_RESPONSE()

  const { statement, answer, topic, score } = await req.json()
  if (!statement)
    return NextResponse.json({ error: 'statement required' }, { status: 400 })

  const tmpFile = path.join(
    os.tmpdir(),
    `sakumon_preview_${crypto.randomBytes(6).toString('hex')}.png`,
  )

  return new Promise<NextResponse>(resolve => {
    let settled = false
    let timer: ReturnType<typeof setTimeout> | undefined
    const finish = (response: NextResponse) => {
      if (settled) return
      settled = true
      if (timer) clearTimeout(timer)
      resolve(response)
    }

    const script = path.join(SCRIPTS_DIR, 'render_math_png.py')
    const proc = spawn(PYTHON, [
      script,
      '--statement', statement,
      '--answer',    answer  ?? '',
      '--topic',     topic   ?? '数学',
      '--score',     String(score ?? 0),
      '--out',       tmpFile,
    ])

    let out = '', err = ''
    proc.stdout.on('data', (d: Buffer) => { out += d.toString() })
    proc.stderr.on('data', (d: Buffer) => { err += d.toString() })
    proc.on('error', (e: Error) => {
      try { fs.unlinkSync(tmpFile) } catch { /* ignore */ }
      finish(NextResponse.json({
        ok: false,
        error: 'render process failed',
        code: 'RENDER_PROCESS_ERROR',
        stderr: summarizeOutput(err || e.message),
        script,
      }, { status: 500 }))
    })

    proc.on('close', (code: number) => {
      if (code !== 0 || !fs.existsSync(tmpFile)) {
        try { fs.unlinkSync(tmpFile) } catch { /* ignore */ }
        finish(NextResponse.json({
          ok: false,
          error: 'render failed',
          code: 'RENDER_FAILED',
          stderr: summarizeOutput(err) || summarizeOutput(out) || 'no stderr',
          script,
        }, { status: 500 }))
        return
      }
      const buf = fs.readFileSync(tmpFile)
      try { fs.unlinkSync(tmpFile) } catch { /* ignore */ }
      finish(new NextResponse(buf, {
        headers: {
          'Content-Type':  'image/png',
          'Cache-Control': 'no-store',
        },
      }))
    })

    timer = setTimeout(() => {
      proc.kill()
      try { fs.unlinkSync(tmpFile) } catch { /* ignore */ }
      finish(NextResponse.json({
        ok: false,
        error: 'render timeout',
        code: 'RENDER_TIMEOUT',
        stderr: summarizeOutput(err),
        script,
      }, { status: 504 }))
    }, 20_000)
  })
}
