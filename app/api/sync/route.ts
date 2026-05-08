import { NextResponse } from 'next/server'
import { spawn } from 'child_process'
import path      from 'path'
import { IS_VERCEL, LOCAL_ONLY_RESPONSE } from '@/lib/env'

const SCRIPTS_DIR = path.join(process.cwd(), 'scripts')
const PYTHON      = process.env.PYTHON_BIN ?? 'python'

function summarizeOutput(value: string, limit = 1200) {
  const text = value.replace(/\s+/g, ' ').trim()
  return text.length > limit ? `${text.slice(0, limit)}...` : text
}

export async function POST() {
  if (IS_VERCEL && process.env.ENABLE_VERCEL_PYTHON_ACTIONS !== '1') return LOCAL_ONLY_RESPONSE()

  const subEnv = {
    ...process.env,
    NEXT_PUBLIC_SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL ?? '',
    SUPABASE_SERVICE_KEY:     process.env.SUPABASE_SERVICE_KEY ?? '',
  }

  return new Promise<NextResponse>(resolve => {
    let settled = false
    let out = '', err = ''
    let timer: ReturnType<typeof setTimeout> | undefined
    const script = path.join(SCRIPTS_DIR, 'sync_sqlite_supabase.py')
    const finish = (response: NextResponse) => {
      if (settled) return
      settled = true
      if (timer) clearTimeout(timer)
      resolve(response)
    }

    const proc = spawn(PYTHON, [script], { env: subEnv })
    proc.stdout.on('data', (d: Buffer) => { out += d.toString() })
    proc.stderr.on('data', (d: Buffer) => { err += d.toString() })
    proc.on('error', (error: Error) => {
      finish(NextResponse.json({
        ok: false,
        error: summarizeOutput(err || error.message),
        log: out,
        script,
      }, { status: 500 }))
    })
    proc.on('close', (code: number) => {
      if (code === 0) {
        finish(NextResponse.json({ ok: true, log: out }))
      } else {
        finish(NextResponse.json({
          ok: false,
          error: summarizeOutput(err) || 'sync failed',
          log: out,
          script,
        }, { status: 500 }))
      }
    })

    timer = setTimeout(() => {
      proc.kill()
      finish(NextResponse.json({ ok: false, error: 'timeout', log: out, script }, { status: 504 }))
    }, 120_000)
  })
}
