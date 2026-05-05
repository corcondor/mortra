import { NextResponse } from 'next/server'
import { spawn } from 'child_process'
import path      from 'path'
import { IS_VERCEL, LOCAL_ONLY_RESPONSE } from '@/lib/env'

const SCRIPTS_DIR = 'C:/Users/81808/.openclaw/workspace/math-web/scripts'
const PYTHON      = 'python'

export async function POST() {
  if (IS_VERCEL) return LOCAL_ONLY_RESPONSE()
  const subEnv = {
    ...process.env,
    NEXT_PUBLIC_SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL ?? '',
    SUPABASE_SERVICE_KEY:     process.env.SUPABASE_SERVICE_KEY ?? '',
  }

  return new Promise<NextResponse>(resolve => {
    const proc = spawn(PYTHON,
      [path.join(SCRIPTS_DIR, 'purge_unselected.py')],
      { env: subEnv }
    )

    let out = '', err = ''
    proc.stdout.on('data', (d: Buffer) => { out += d.toString() })
    proc.stderr.on('data', (d: Buffer) => { err += d.toString() })

    proc.on('close', (code: number) => {
      // last line is JSON
      const lines = out.trim().split('\n')
      let result: Record<string, unknown> = { deleted: 0 }
      for (let i = lines.length - 1; i >= 0; i--) {
        try { result = JSON.parse(lines[i]); break } catch { /* skip */ }
      }
      if (code === 0) resolve(NextResponse.json({ ok: true, ...result, log: out }))
      else            resolve(NextResponse.json({ ok: false, error: err }, { status: 500 }))
    })

    setTimeout(() => {
      proc.kill()
      resolve(NextResponse.json({ ok: false, error: 'timeout' }, { status: 504 }))
    }, 60_000)
  })
}
