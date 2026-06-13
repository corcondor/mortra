'use client'
import { useEffect, useState, useMemo } from 'react'
import { createBrowserClient } from '@supabase/ssr'
import type { User, Session } from '@supabase/supabase-js'
import { Background } from './Background'

/** オーナーのメールアドレス — 無制限生成 & 管理権限 */
export const ADMIN_EMAIL = 'imtceed@gmail.com'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? ''
const SUPABASE_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? ''

export function useAuth() {
  const supabase = useMemo(
    () => createBrowserClient(SUPABASE_URL, SUPABASE_KEY),
    [],
  )
  const [user,        setUser]        = useState<User | null>(null)
  const [session,     setSession]     = useState<Session | null>(null)
  const [loading,     setLoading]     = useState(true)

  useEffect(() => {
    if (!SUPABASE_URL || !SUPABASE_KEY) { setLoading(false); return }
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      setUser(data.session?.user ?? null)
      setLoading(false)
    })
    const { data: sub } = supabase.auth.onAuthStateChange((_, s) => {
      setSession(s)
      setUser(s?.user ?? null)
    })
    return () => sub.subscription.unsubscribe()
  }, [supabase])

  const signIn = () =>
    supabase.auth.signInWithOAuth({
      provider: 'google',
      options:  { redirectTo: window.location.origin },
    })

  const signOut = () => supabase.auth.signOut()

  const isAdmin     = user?.email === ADMIN_EMAIL
  const accessToken = session?.access_token ?? null

  return { user, loading, isAdmin, accessToken, signIn, signOut, supabase }
}

interface Props { children: React.ReactNode }

function EnvVarError() {
  return (
    <div className="fixed inset-0 flex items-center justify-center bg-[#05050f]">
      <div className="glass rounded-2xl p-8 text-center space-y-3 max-w-sm w-full mx-4">
        <div className="text-xl">⚠️</div>
        <p className="text-[13px] text-white/60 font-semibold">環境変数が未設定</p>
        <p className="text-[11px] text-white/35 leading-relaxed">
          Vercel Dashboard → Settings → Environment Variables に<br />
          <code className="text-apple-blue">NEXT_PUBLIC_SUPABASE_URL</code> と<br />
          <code className="text-apple-blue">NEXT_PUBLIC_SUPABASE_ANON_KEY</code><br />
          を追加して Redeploy してください。
        </p>
      </div>
    </div>
  )
}

function AuthGuardInner({ children }: Props) {
  const { user, loading, signIn, signOut } = useAuth()

  if (loading) {
    return (
      <div className="fixed inset-0 flex items-center justify-center bg-[#05050f]">
        <div className="w-6 h-6 border-2 border-apple-blue border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (!user) {
    return (
      <div className="fixed inset-0 flex items-center justify-center">
        <Background />
        <div className="glass rounded-2xl p-8 text-center space-y-4 max-w-sm w-full mx-4">
          <div className="text-[22px] font-bold text-white/90">✦ Sakumon Station</div>
          <p className="text-[13px] text-white/40">Google アカウントでログインしてください</p>
          <button
            onClick={signIn}
            className="w-full py-3 bg-white text-gray-800 rounded-xl text-[14px] font-semibold
                       hover:bg-white/90 transition-colors flex items-center justify-center gap-2"
          >
            <svg viewBox="0 0 24 24" width="18" height="18">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
            </svg>
            Google でログイン
          </button>
        </div>
      </div>
    )
  }

  return <>{children}</>
}

export function AuthGuard({ children }: Props) {
  if (!SUPABASE_URL || !SUPABASE_KEY) return <EnvVarError />
  return <AuthGuardInner>{children}</AuthGuardInner>
}
