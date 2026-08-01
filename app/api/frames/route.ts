import { NextRequest, NextResponse } from 'next/server'
import { mkdir, writeFile } from 'node:fs/promises'
import { join } from 'node:path'

/**
 * 書き出し用のフレーム受け口。
 *
 * /robot?export=1 が canvas を 1 枚ずつ PNG にして投げてくる。
 * 受けたものを export/frames/ に連番で置き、あとで ffmpeg が MP4 にする。
 * 開発時にだけ使う想定なので本番では無効にする。
 */
export const runtime = 'nodejs'

const OUT_DIR = join(process.cwd(), 'export', 'frames')

export async function POST(request: NextRequest) {
  if (process.env.NODE_ENV === 'production') {
    return NextResponse.json({ error: 'disabled in production' }, { status: 403 })
  }
  let index = 0
  let dataUrl = ''
  let session = 'default'
  try {
    const body = await request.json()
    index = Number(body?.index ?? 0)
    dataUrl = String(body?.dataUrl ?? '')
    session = String(body?.session ?? 'default').replace(/[^a-zA-Z0-9_-]/g, '')
  } catch {
    return NextResponse.json({ error: 'bad body' }, { status: 400 })
  }
  const base64 = dataUrl.replace(/^data:image\/png;base64,/, '')
  if (!base64) {
    return NextResponse.json({ error: 'no image' }, { status: 400 })
  }
  const directory = join(OUT_DIR, session)
  await mkdir(directory, { recursive: true })
  const name = `${String(index).padStart(5, '0')}.png`
  await writeFile(join(directory, name), Buffer.from(base64, 'base64'))
  return NextResponse.json({ ok: true, file: name })
}

export async function GET() {
  return NextResponse.json({
    usage: 'POST { index, dataUrl, session } — /robot?export=1 から呼ばれる',
    outDir: OUT_DIR,
  })
}
