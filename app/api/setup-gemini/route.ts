/**
 * GET /api/setup-gemini
 * 専用 Chrome プロファイルでブラウザを起動し、Gemini にログインできる状態にする。
 * ログイン後ブラウザを閉じると完了。（初回 1 回だけ実行）
 */
import { NextResponse } from 'next/server'
import { spawn } from 'child_process'
import path from 'path'
import { IS_VERCEL, LOCAL_ONLY_RESPONSE } from '@/lib/env'

const PIPELINE_DIR = 'C:/Users/81808/.openclaw/workspace/automation/pipeline'
const PYTHON = 'python'

export async function GET() {
  if (IS_VERCEL) return LOCAL_ONLY_RESPONSE()
  const proc = spawn(PYTHON,
    [path.join(PIPELINE_DIR, 'playwright_gemini.py'), '--setup'],
    { cwd: PIPELINE_DIR, detached: true, stdio: 'ignore' }
  )
  proc.unref()
  return NextResponse.json({
    ok: true,
    message: 'Chrome が起動しました。Gemini にログインして閉じてください。',
  })
}
