import { createClient } from '@supabase/supabase-js'

/** サーバーサイド専用 (service_role — RLS バイパス) */
export const supabaseAdmin = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_KEY!,
)
