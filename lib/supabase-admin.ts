import { createClient } from '@supabase/supabase-js'

/** サーバーサイド専用。ビルド時ではなく、実際のAPI呼び出し時に初期化する。 */
export function getSupabaseAdmin() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? process.env.SUPABASE_URL
  const key = process.env.SUPABASE_SERVICE_KEY ?? process.env.SUPABASE_SERVICE_ROLE_KEY
  if (!url || !key) throw new Error('Supabase server environment is not configured')
  return createClient(url, key)
}
