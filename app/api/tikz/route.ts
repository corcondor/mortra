import { NextResponse } from 'next/server'

export async function POST() {
  return NextResponse.json(
    {
      error: '旧AI TikZ生成経路は削除されました。MORTRAの検証済み図生成経路を利用してください。',
      code: 'LEGACY_ROUTE_REMOVED',
    },
    { status: 410 },
  )
}
