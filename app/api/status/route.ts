import { NextRequest, NextResponse } from 'next/server'
import { supabaseAdmin } from '@/lib/supabase-admin'

export async function POST(req: NextRequest) {
  const { problem_id, status } = await req.json()
  if (!problem_id || !status) {
    return NextResponse.json({ error: 'missing fields' }, { status: 400 })
  }
  const { error } = await supabaseAdmin
    .from('ratings')
    .upsert(
      { problem_id, status, updated_at: new Date().toISOString() },
      { onConflict: 'problem_id' },
    )
  if (error) return NextResponse.json({ error: error.message }, { status: 500 })
  return NextResponse.json({ ok: true })
}
