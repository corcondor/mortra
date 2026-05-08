import { NextRequest, NextResponse } from 'next/server'
import { spawn } from 'child_process'
import path      from 'path'
import fs        from 'fs'
import os        from 'os'
import crypto    from 'crypto'
import { supabaseAdmin } from '@/lib/supabase-admin'
import { IS_VERCEL, LOCAL_ONLY_RESPONSE } from '@/lib/env'

const SCRIPTS_DIR = path.join(process.cwd(), 'scripts')
const PYTHON      = process.env.PYTHON_BIN ?? 'python'

type RenderResult = {
  imagePath: string | null
  warning?: string
}

type ScriptResult = {
  code: number | null
  stdout: string
  stderr: string
  timedOut: boolean
  command: string
}

function summarizeOutput(value: string, limit = 1200) {
  const text = value.replace(/\s+/g, ' ').trim()
  return text.length > limit ? `${text.slice(0, limit)}...` : text
}

function runPythonScript(name: string, args: string[], timeoutMs: number): Promise<ScriptResult> {
  const script = path.join(SCRIPTS_DIR, name)
  const command = `${PYTHON} ${script}`

  return new Promise(resolve => {
    let settled = false
    let stdout = ''
    let stderr = ''
    let timer: ReturnType<typeof setTimeout> | undefined
    const finish = (result: ScriptResult) => {
      if (settled) return
      settled = true
      if (timer) clearTimeout(timer)
      resolve(result)
    }

    const proc = spawn(PYTHON, [script, ...args])
    proc.stdout.on('data', (d: Buffer) => { stdout += d.toString() })
    proc.stderr.on('data', (d: Buffer) => { stderr += d.toString() })
    proc.on('error', (error: Error) => {
      finish({ code: null, stdout, stderr: stderr || error.message, timedOut: false, command })
    })
    proc.on('close', (code: number) => {
      finish({ code, stdout, stderr, timedOut: false, command })
    })
    timer = setTimeout(() => {
      proc.kill()
      finish({ code: null, stdout, stderr, timedOut: true, command })
    }, timeoutMs)
  })
}

/** PNG を一時ファイルにレンダリングする。失敗しても投稿はテキストのみで続行できる。 */
async function renderPng(statement: string, answer: string, topic: string, score: number): Promise<RenderResult> {
  const tmpFile = path.join(
    os.tmpdir(),
    `sakumon_post_${crypto.randomBytes(6).toString('hex')}.png`,
  )
  const result = await runPythonScript('render_math_png.py', [
    '--statement', statement,
    '--answer',    answer,
    '--topic',     topic,
    '--score',     String(score),
    '--out',       tmpFile,
  ], 20_000)

  if (result.code === 0 && fs.existsSync(tmpFile)) return { imagePath: tmpFile }

  try { fs.unlinkSync(tmpFile) } catch { /* ignore */ }
  return {
    imagePath: null,
    warning: result.timedOut
      ? '画像レンダリングがタイムアウトしたため、テキストのみで投稿します。'
      : `画像レンダリングに失敗したため、テキストのみで投稿します: ${summarizeOutput(result.stderr) || summarizeOutput(result.stdout) || 'reason unknown'}`,
  }
}

export async function POST(req: NextRequest) {
  if (IS_VERCEL && process.env.ENABLE_VERCEL_PYTHON_ACTIONS !== '1') return LOCAL_ONLY_RESPONSE()

  const body = await req.json()
  const { problem_id, statement, answer, topic, score } = body as {
    problem_id: string
    statement:  string
    answer?:    string
    topic?:     string
    score?:     number
  }

  if (!problem_id || !statement)
    return NextResponse.json(
      { error: 'problem_id and statement required' }, { status: 400 },
    )

  // 1. PNG レンダリング（失敗しても投稿は続行）
  const render = await renderPng(
    statement,
    answer  ?? '',
    topic   ?? '数学',
    score   ?? 0,
  )
  const imagePath = render.imagePath

  // 2. X 投稿
  const args = ['--text', statement]
  if (imagePath) args.push('--image-path', imagePath)

  const result = await runPythonScript('post_to_x.py', args, 60_000)
  if (imagePath) try { fs.unlinkSync(imagePath) } catch { /* ignore */ }

  if (result.timedOut) {
    return NextResponse.json({
      ok: false,
      error: 'posting timeout',
      code: 'POST_TIMEOUT',
      renderWarning: render.warning,
    }, { status: 504 })
  }

  if (result.code !== 0) {
    return NextResponse.json({
      ok: false,
      error: summarizeOutput(result.stderr) || summarizeOutput(result.stdout) || 'posting failed',
      code: 'POST_FAILED',
      renderWarning: render.warning,
      command: result.command,
    }, { status: 500 })
  }

  let parsed: { ok: boolean; tweet_id?: string; url?: string; error?: string }
  try   { parsed = JSON.parse(result.stdout.trim()) }
  catch { parsed = { ok: false, error: 'invalid JSON from script' } }

  if (parsed.ok) {
    await supabaseAdmin.from('ratings').upsert({
      problem_id,
      status:   'posted',
      x_posted: true,
    }, { onConflict: 'problem_id' })
  }

  return NextResponse.json({ ...parsed, renderWarning: render.warning })
}
