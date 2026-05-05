import { createClient } from '@supabase/supabase-js'
import type { ProblemWithRating } from './types'

const url  = process.env.NEXT_PUBLIC_SUPABASE_URL!
const anon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!

export const supabase = createClient(url, anon)

/** selected 問題を全件取得（rating 付き） */
export async function fetchProblems(): Promise<ProblemWithRating[]> {
  const { data, error } = await supabase
    .from('problems')
    .select(`
      *,
      rating:ratings(*)
    `)
    .order('total', { ascending: false })

  if (error) throw error

  // ratings は 1:1 なので配列→オブジェクトに flatten
  return (data ?? []).map((p: any) => ({
    ...p,
    rating: Array.isArray(p.rating) ? p.rating[0] ?? null : p.rating,
  }))
}

/** selected 問題のみ */
export async function fetchSelectedProblems(): Promise<ProblemWithRating[]> {
  const { data, error } = await supabase
    .from('problems')
    .select(`*, rating:ratings(*)`)
    .eq('ratings.status', 'selected')
    .order('total', { ascending: false })

  if (error) throw error

  return (data ?? []).map((p: any) => ({
    ...p,
    rating: Array.isArray(p.rating) ? p.rating[0] ?? null : p.rating,
  }))
}
