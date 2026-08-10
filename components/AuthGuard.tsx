'use client'
import { useEffect, useState, useMemo } from 'react'
import { createBrowserClient } from '@supabase/ssr'
import type { User, Session } from '@supabase/supabase-js'

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
    <div className="fixed inset-0 flex items-center justify-center bg-[#09090b] text-zinc-100">
      <div className="glass mx-4 w-full max-w-sm space-y-3 rounded-md p-8 text-center">
        <div className="text-xl text-rose-400">!</div>
        <p className="text-[13px] font-semibold text-zinc-100">環境変数が未設定</p>
        <p className="text-[11px] leading-relaxed text-zinc-400">
          Vercel Dashboard → Settings → Environment Variables に<br />
          <code className="text-blue-400">NEXT_PUBLIC_SUPABASE_URL</code> と<br />
          <code className="text-blue-400">NEXT_PUBLIC_SUPABASE_ANON_KEY</code><br />
          を追加して Redeploy してください。
        </p>
      </div>
    </div>
  )
}

function AuthGuardInner({ children }: Props) {
  const { user, loading, signIn } = useAuth()

  if (loading) {
    return (
      <div className="fixed inset-0 flex items-center justify-center bg-[#09090b]">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-blue-400 border-t-transparent" />
      </div>
    )
  }

  if (!user) {
    return (
      <div className="fixed inset-0 flex items-center justify-center bg-[#09090b] px-4 text-zinc-100">
        <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.018)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.018)_1px,transparent_1px)] bg-[size:24px_24px]" />
        <main className="relative grid w-full max-w-4xl overflow-hidden rounded-md border border-zinc-800 bg-[#141416] shadow-[0_24px_80px_rgba(0,0,0,0.55)] md:grid-cols-[1.2fr_0.8fr]">
          <section className="border-b border-zinc-800 p-7 md:border-b-0 md:border-r md:p-10">
            <div className="mb-8 flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded bg-blue-600 text-lg font-bold text-white">Σ</span>
              <div>
                <h1 className="text-[20px] font-bold text-zinc-100">Sakumon</h1>
                <p className="text-[11px] tracking-[0.14em] text-zinc-500">by MORTRA</p>
              </div>
            </div>
            <h2 className="max-w-lg text-[24px] font-bold leading-snug text-zinc-100">
              数学問題を作る人のための作業場。
            </h2>
            <p className="mt-3 max-w-lg text-[13px] leading-7 text-zinc-400">
              種を選び、生成し、検証し、比べ、直し、図にし、書き出す。
              作問の全工程を一つの画面で扱います。
            </p>
            <p className="mt-4 max-w-lg text-[12px] leading-6 text-zinc-500">
              表現の間を移動する研究基盤 MORTRA の、最初の応用です。
            </p>
            <ol className="mt-7 grid gap-3 text-[12px] text-zinc-300 sm:grid-cols-3 md:grid-cols-1 lg:grid-cols-3">
              {['問題を比較', '構造を合成', '検証して公開'].map((label, index) => (
                <li key={label} className="border-l-2 border-blue-500/50 pl-3">
                  <span className="block text-[10px] font-bold text-blue-400">0{index + 1}</span>
                  {label}
                </li>
              ))}
            </ol>
          </section>
          <section className="flex flex-col justify-center p-7 md:p-9">
            <h2 className="text-[16px] font-bold text-zinc-100">ワークスペースに入る</h2>
            <p className="mt-1 text-[12px] leading-5 text-zinc-400">
              Googleアカウントで認証します。
            </p>
          <button
            onClick={signIn}
              className="mt-6 flex w-full items-center justify-center gap-2 rounded border border-zinc-700 bg-zinc-900 py-3 text-[13px] font-semibold text-zinc-100 transition-colors hover:border-zinc-500 hover:bg-zinc-800"
          >
            <svg viewBox="0 0 24 24" width="18" height="18">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
            </svg>
            Google でログイン
          </button>
            <p className="mt-4 text-center text-[10px] leading-5 text-zinc-600">
              認証後、問題一覧・生成履歴・過去問DBを利用できます。
            </p>
          </section>
        </main>
      </div>
    )
  }

  return <>{children}</>
}

export function AuthGuard({ children }: Props) {
  if (!SUPABASE_URL || !SUPABASE_KEY) return <EnvVarError />
  return <AuthGuardInner>{children}</AuthGuardInner>
}
