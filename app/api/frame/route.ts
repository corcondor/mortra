/**
 * canvas のフレームを受け取ってディスクへ落とす。開発時のみ。
 *
 * 書き出し用のページ（/proof?export=1 など）が 1 フレームずつ送ってくる。
 * 溜まった PNG を ffmpeg で繋げば縦動画になる。
 * ブラウザ側でスクリーンショットを撮る経路に頼らないので、
 * 表示していないタブでも、解像度が違う画面でも、必ず 1080×1920 で出る。
 */
import { writeFile, mkdir } from 'node:fs/promises'
import path from 'node:path'
import { NextResponse } from 'next/server'

export const runtime = 'nodejs'

const ROOT = process.cwd()
/** 書き出し先はここより外に出さない */
const BASE = path.join(ROOT, 'export', 'frames')

export async function POST(request: Request) {
  if (process.env.NODE_ENV === 'production') {
    return NextResponse.json({ error: 'development only' }, { status: 403 })
  }

  const { dir, name, dataUrl } = await request.json()
  if (typeof dir !== 'string' || typeof name !== 'string' || typeof dataUrl !== 'string') {
    return NextResponse.json({ error: 'dir, name, dataUrl required' }, { status: 400 })
  }
  if (!/^[a-zA-Z0-9._-]+$/.test(dir) || !/^[a-zA-Z0-9._-]+\.png$/.test(name)) {
    return NextResponse.json({ error: 'bad name' }, { status: 400 })
  }
  const match = /^data:image\/png;base64,(.+)$/.exec(dataUrl)
  if (!match) return NextResponse.json({ error: 'png data url required' }, { status: 400 })

  const target = path.join(BASE, dir)
  await mkdir(target, { recursive: true })
  await writeFile(path.join(target, name), Buffer.from(match[1], 'base64'))
  return NextResponse.json({ ok: true, path: path.relative(ROOT, path.join(target, name)) })
}
