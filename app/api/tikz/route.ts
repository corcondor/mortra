/** Read a previously verified TikZ artifact from MORTRA problem metadata. */
import { NextRequest, NextResponse } from 'next/server'
import { supabaseAdmin } from '@/lib/supabase-admin'

export async function GET(request: NextRequest) {
  const id = request.nextUrl.searchParams.get('problem_id')
  if (!id) return NextResponse.json({ error: 'problem_id required' }, { status: 400 })

  const { data } = await supabaseAdmin.from('problems').select('meta').eq('id', id).single()
  let meta: Record<string, unknown> = {}
  try {
    meta = data?.meta ? JSON.parse(data.meta) : {}
  } catch {
    return NextResponse.json({ error: 'Invalid problem metadata' }, { status: 422 })
  }

  if (typeof meta.tikz !== 'string') {
    return NextResponse.json({ error: 'No certified TikZ artifact' }, { status: 404 })
  }
  return NextResponse.json({
    tikz: meta.tikz,
    type: meta.tikz_type,
    verified: meta.tikz_verified === true,
  })
}

export async function POST() {
  return NextResponse.json(
    { error: 'Ad-hoc diagram generation was removed; diagrams must be compiled from MORTRA semantic state.' },
    { status: 410 },
  )
}
