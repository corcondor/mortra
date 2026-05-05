import { NextRequest, NextResponse } from 'next/server'
import { spawn } from 'child_process'
import path      from 'path'
import fs        from 'fs'
import os        from 'os'
import crypto    from 'crypto'
import { IS_VERCEL, LOCAL_ONLY_RESPONSE } from '@/lib/env'

const SCRIPTS_DIR = 'C:/Users/81808/.openclaw/workspace/math-web/scripts'
const PYTHON      = 'python'

export async function POST(req: NextRequest) {
  if (IS_VERCEL) return LOCAL_ONLY_RESPONSE()
  const { statement, answer, topic, score } = await req.json()
  if (!statement)
    return NextResponse.json({ error: 'statement required' }, { status: 400 })

  const tmpFile = path.join(
    os.tmpdir(),
    `sakumon_preview_${crypto.randomBytes(6).toString('hex')}.png`,
  )

  return new Promise<NextResponse>(resolve => {
    const proc = spawn(PYTHON, [
      path.join(SCRIPTS_DIR, 'render_math_png.py'),
      '--statement', statement,
      '--answer',    answer  ?? '',
      '--topic',     topic   ?? '数学',
      '--score',     String(score ?? 0),
      '--out',       tmpFile,
    ])

    let err = ''
    proc.stderr.on('data', (d: Buffer) => { err += d.toString() })

    proc.on('close', (code: number) => {
      if (code !== 0 || !fs.existsSync(tmpFile)) {
        resolve(NextResponse.json(
          { error: err || 'render failed' }, { status: 500 },
        ))
        return
      }
      const buf = fs.readFileSync(tmpFile)
      try { fs.unlinkSync(tmpFile) } catch { /* ignore */ }
      resolve(new NextResponse(buf, {
        headers: {
          'Content-Type':  'image/png',
          'Cache-Control': 'no-store',
        },
      }))
    })

    setTimeout(() => {
      proc.kill()
      try { fs.unlinkSync(tmpFile) } catch { /* ignore */ }
      resolve(NextResponse.json({ error: 'render timeout' }, { status: 504 }))
    }, 20_000)
  })
}
