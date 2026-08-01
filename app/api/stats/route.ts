import { NextResponse } from 'next/server'
import { supabaseAdmin } from '@/lib/supabase-admin'

export async function GET() {
  const [pRes, selectedRes, skippedRes, postedRes, pendingRes, generationRes] = await Promise.all([
    supabaseAdmin.from('problems').select('id', { count: 'exact', head: true }),
    supabaseAdmin.from('ratings').select('problem_id', { count: 'exact', head: true }).eq('status', 'selected'),
    supabaseAdmin.from('ratings').select('problem_id', { count: 'exact', head: true }).eq('status', 'rejected'),
    supabaseAdmin.from('ratings').select('problem_id', { count: 'exact', head: true }).eq('x_posted', true),
    supabaseAdmin.from('ratings').select('problem_id', { count: 'exact', head: true }).eq('status', 'pending'),
    supabaseAdmin.from('problems').select('generation').order('generation', { ascending: false }).limit(1),
  ])

  const total    = pRes.count ?? 0
  const selected = selectedRes.count ?? 0
  const skipped  = skippedRes.count ?? 0
  const posted   = postedRes.count ?? 0
  const pending  = pendingRes.count ?? 0
  const maxGen   = generationRes.data?.[0]?.generation ?? 0

  return NextResponse.json({ total, selected, skipped, posted, pending, generations: maxGen })
}
