import { NextResponse } from 'next/server'
import { supabaseAdmin } from '@/lib/supabase-admin'

export async function GET() {
  const [pRes, rRes] = await Promise.all([
    supabaseAdmin.from('problems').select('generation', { count: 'exact' }),
    supabaseAdmin.from('ratings').select('status, x_posted', { count: 'exact' }),
  ])

  const ratings = rRes.data ?? []
  const problems = pRes.data ?? []

  const total    = pRes.count ?? 0
  const selected = ratings.filter(r => r.status === 'selected').length
  const skipped  = ratings.filter(r => r.status === 'rejected').length
  const posted   = ratings.filter(r => r.x_posted).length
  const pending  = ratings.filter(r => r.status === 'pending').length
  const maxGen   = problems.reduce((m, p) => Math.max(m, p.generation ?? 0), 0)

  return NextResponse.json({ total, selected, skipped, posted, pending, generations: maxGen })
}
