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
      [path.join(SCRIPTS_DIR, 'sync_sqlite_supabase.py')],
      { env: subEnv }
    )

    let out = '', err = ''
    proc.stdout.on('data', (d: Buffer) => { out += d.toString() })
    proc.stderr.on('data', (d: Buffer) => { err += d.toString() })

    proc.on('close', (code: number) => {
      if (code === 0) resolve(NextResponse.json({ ok: true,  log: out }))
      else            resolve(NextResponse.json({ ok: false, error: err, log: out }, { status: 500 }))
    })

    setTimeout(() => {
      proc.kill()
      resolve(NextResponse.json({ ok: false, error: 'timeout' }, { status: 504 }))
    }, 120_000)
  })
}
