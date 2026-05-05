import { NextRequest, NextResponse } from 'next/server'
import { spawn } from 'child_process'
import path      from 'path'
import fs        from 'fs'
import os        from 'os'
import crypto    from 'crypto'
import { supabaseAdmin } from '@/lib/supabase-admin'
import { IS_VERCEL, LOCAL_ONLY_RESPONSE } from '@/lib/env'

const SCRIPTS_DIR = 'C:/Users/81808/.openclaw/workspace/math-web/scripts'
const PYTHON      = 'python'

/** PNG を一時ファイルにレンダリングして絶対パスを返す。失敗したら null */
async function renderPng(statement: string, answer: string, topic: string, score: number): Promise<string | null> {
  const tmpFile = path.join(
    os.tmpdir(),
    `sakumon_post_${crypto.randomBytes(6).toString('hex')}.png`,
  )
  return new Promise<string | null>(resolve => {
    const proc = spawn(PYTHON, [
      path.join(SCRIPTS_DIR, 'render_math_png.py'),
      '--statement', statement,
      '--answer',    answer,
      '--topic',     topic,
      '--score',     String(score),
      '--out',       tmpFile,
    ])
    let err = ''
    proc.stderr.on('data', (d: Buffer) => { err += d.toString() })
    proc.on('close', (code: number) => {
      if (code === 0 && fs.existsSync(tmpFile)) resolve(tmpFile)
      else { console.error('[render]', err); resolve(null) }
    })
    setTimeout(() => { proc.kill(); resolve(null) }, 20_000)
  })
}

export async function POST(req: NextRequest) {
  if (IS_VERCEL) return LOCAL_ONLY_RESPONSE()
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
  const imagePath = await renderPng(
    statement,
    answer  ?? '',
    topic   ?? '数学',
    score   ?? 0,
  )

  // 2. X 投稿
  return new Promise<NextResponse>(resolve => {
    const args = [
      path.join(SCRIPTS_DIR, 'post_to_x.py'),
      '--text', statement,
    ]
    if (imagePath) args.push('--image-path', imagePath)

    const proc = spawn(PYTHON, args)
    let out = '', err = ''
    proc.stdout.on('data', (d: Buffer) => { out += d.toString() })
    proc.stderr.on('data', (d: Buffer) => { err += d.toString() })

    proc.on('close', async (code: number) => {
      // 一時ファイルを削除
      if (imagePath) try { fs.unlinkSync(imagePath) } catch { /* ignore */ }

      if (code !== 0) {
        resolve(NextResponse.json({ error: err || 'posting failed' }, { status: 500 }))
        return
      }

      let result: { ok: boolean; tweet_id?: string; url?: string; error?: string }
      try   { result = JSON.parse(out.trim()) }
      catch { result = { ok: false, error: 'invalid JSON from script' } }

      if (result.ok) {
        await supabaseAdmin.from('ratings').upsert({
          problem_id,
          status:   'posted',
          x_posted: true,
        }, { onConflict: 'problem_id' })
      }

      resolve(NextResponse.json(result))
    })

    setTimeout(() => {
      proc.kill()
      if (imagePath) try { fs.unlinkSync(imagePath) } catch { /* ignore */ }
      resolve(NextResponse.json({ error: 'timeout' }, { status: 504 }))
    }, 60_000) // 画像アップロード込みで長めに
  })
}
