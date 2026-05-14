import { NextRequest, NextResponse } from 'next/server'
import { supabaseAdmin } from '@/lib/supabase-admin'

export async function GET(req: NextRequest) {
  const token = req.headers.get('Authorization')?.replace('Bearer ', '') ?? ''
  const { data: { user } } = await supabaseAdmin.auth.getUser(token)
  if (!user) return NextResponse.json({ connected: false })

  const { data } = await supabaseAdmin
    .from('user_x_tokens')
    .select('x_username, x_user_id, updated_at')
    .eq('user_id', user.id)
    .single()

  if (!data) return NextResponse.json({ connected: false })

  return NextResponse.json({
    connected:  true,
    x_username: data.x_username,
    x_user_id:  data.x_user_id,
    updated_at: data.updated_at,
  })
}
