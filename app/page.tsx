'use client'
import { useState, useEffect, useMemo, useCallback } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Background }            from '@/components/Background'
import { Sidebar, type Filters } from '@/components/Sidebar'
import { ProblemCardCuration }   from '@/components/ProblemCardCuration'
import { GenerationPanel }       from '@/components/GenerationPanel'
import { PostModal }             from '@/components/PostModal'
import { SpotlightSearch }       from '@/components/SpotlightSearch'
import { AuthGuard, useAuth }    from '@/components/AuthGuard'
import type { ProblemWithRating } from '@/lib/types'

type Tab = 'list' | 'selected'

const DEFAULT_FILTERS: Filters = {
  topic: null, status: null,
  sort: 'total', perPage: 12, showSol: false,
}

export default function Home() {
  return <AuthGuard><HomeInner /></AuthGuard>
}

function HomeInner() {
  const { user, signOut } = useAuth()
  const [problems,  setProblems]  = useState<ProblemWithRating[]>([])
  const [loading,   setLoading]   = useState(true)
  const [tab,       setTab]       = useState<Tab>('list')
  const [filters,   setFilters]   = useState<Filters>(DEFAULT_FILTERS)
  const [page,      setPage]      = useState(0)
  const [postTarget,   setPostTarget]   = useState<ProblemWithRating | null>(null)
  const [showSearch,   setShowSearch]   = useState(false)
  const [sidebarOpen,  setSidebarOpen]  = useState(false)

  // ── データ取得 ────────────────────────────────────────────────────────
  const loadProblems = useCallback(async () => {
    setLoading(true)
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_SUPABASE_URL}/rest/v1/problems?select=*,rating:ratings(*)&order=total.desc`,
      {
        headers: {
          apikey:        process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
          Authorization: `Bearer ${process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY}`,
        },
      },
    )
    const data = await res.json()
    const normalized = (data ?? []).map((p: any) => ({
      ...p,
      rating: Array.isArray(p.rating) ? p.rating[0] ?? null : p.rating,
    }))
    setProblems(normalized)
    setLoading(false)
  }, [])

  useEffect(() => { loadProblems() }, [loadProblems])

  // ── フィルター ─────────────────────────────────────────────────────────
  const filtered = useMemo(() => {
    let ps = [...problems]
    if (filters.topic)  ps = ps.filter(p => p.topic_a === filters.topic || p.topic_b === filters.topic)
    if (filters.status) ps = ps.filter(p => (p.rating?.status ?? 'pending') === filters.status)
    if (filters.sort === 'surprise')   ps.sort((a, b) => (b.surprise||0) - (a.surprise||0))
    else if (filters.sort === 'topic') ps.sort((a, b) => a.topic_a.localeCompare(b.topic_a))
    // default: total (already sorted)
    return ps
  }, [problems, filters])

  const selected   = useMemo(() => problems.filter(p => p.rating?.status === 'selected'), [problems])
  const totalPages = Math.max(1, Math.ceil(filtered.length / filters.perPage))
  const paginated  = filtered.slice(page * filters.perPage, (page + 1) * filters.perPage)

  // ── ステータス更新（楽観的UI） ─────────────────────────────────────────
  const handleStatusChange = useCallback((id: string, status: string) => {
    setProblems(prev => prev.map(p =>
      p.id !== id ? p : {
        ...p,
        rating: { ...(p.rating ?? { problem_id: id, x_posted: false, note: null, updated_at: '' }), status: status as any },
      }
    ))
  }, [])

  const handlePosted = useCallback((id: string) => {
    setProblems(prev => prev.map(p =>
      p.id !== id ? p : {
        ...p,
        rating: { ...(p.rating ?? { problem_id: id, status: 'posted' as any, note: null, updated_at: '' }), x_posted: true, status: 'posted' as any },
      }
    ))
  }, [])

  // フィルター変更時はページをリセット
  const handleFiltersChange = (f: Filters) => { setFilters(f); setPage(0) }

  // ── CMD+K でSpotlight ─────────────────────────────────────────────────
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') { e.preventDefault(); setShowSearch(s => !s) }
      if (e.key === 'Escape') setShowSearch(false)
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [])

  return (
    <div className="flex h-screen overflow-hidden text-white relative md:flex-row flex-col">
      <Background />

      {/* Mobile sidebar backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/60 backdrop-blur-sm md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div className={`fixed md:relative z-40 md:z-auto h-full transition-transform duration-300
                       ${sidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}>
        <Sidebar
          filters={filters}
          onChange={handleFiltersChange}
          onReload={loadProblems}
          onClose={() => setSidebarOpen(false)}
        />
      </div>

      {/* Main */}
      <main className="flex-1 flex flex-col overflow-hidden">

        {/* Top bar */}
        <header className="flex items-center gap-4 px-4 md:px-6 py-3.5 border-b border-white/8 shrink-0">
          {/* Hamburger (mobile only) */}
          <button
            onClick={() => setSidebarOpen(s => !s)}
            className="md:hidden flex flex-col gap-1.5 p-1.5 text-white/50 hover:text-white/90"
            aria-label="メニュー"
          >
            <span className="block w-5 h-0.5 bg-current rounded" />
            <span className="block w-5 h-0.5 bg-current rounded" />
            <span className="block w-5 h-0.5 bg-current rounded" />
          </button>

          {/* Tabs */}
          <nav className="flex gap-1">
            {([['list','問題一覧'], ['selected','選択済み・生成']] as [Tab, string][]).map(([t, label]) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-4 py-1.5 text-[13px] font-medium rounded-xl transition-all
                  ${tab === t
                    ? 'bg-white/10 text-white/90'
                    : 'text-white/40 hover:text-white/70'}`}
              >
                {label}
                {t === 'selected' && selected.length > 0 && (
                  <span className="ml-1.5 text-[10px] bg-apple-blue text-white px-1.5 py-0.5 rounded-full">
                    {selected.length}
                  </span>
                )}
              </button>
            ))}
          </nav>

          <div className="flex-1" />

          {/* Spotlight trigger */}
          <button
            onClick={() => setShowSearch(true)}
            className="flex items-center gap-2 glass rounded-xl px-3 py-1.5 text-[12px] text-white/30
                       hover:text-white/60 hover:bg-white/8 transition-all"
          >
            <span>⌕</span>
            <span>検索</span>
            <kbd className="text-[10px] border border-white/10 rounded px-1">⌘K</kbd>
          </button>

          {/* User avatar + logout */}
          {user && (
            <div className="flex items-center gap-2">
              {user.user_metadata?.avatar_url && (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={user.user_metadata.avatar_url}
                  alt="avatar"
                  className="w-7 h-7 rounded-full border border-white/15"
                />
              )}
              <button
                onClick={signOut}
                className="text-[11px] text-white/25 hover:text-white/60 transition-colors"
                title="ログアウト"
              >
                ログアウト
              </button>
            </div>
          )}
        </header>

        {/* Content */}
        <div className="flex-1 overflow-y-auto scroll-smooth px-4 md:px-6 py-5">

          {/* ── TAB 1: 問題一覧 ── */}
          {tab === 'list' && (
            <div>
              {/* Sub-header */}
              <div className="flex items-center gap-4 mb-5">
                <div>
                  <h1 className="text-[22px] font-bold tracking-tight text-white/90">問題一覧</h1>
                  <p className="text-[12px] text-white/30 mt-0.5">
                    {loading ? '読み込み中…' : `${filtered.length} 件  ·  ${page + 1} / ${totalPages} ページ`}
                  </p>
                </div>
                <div className="flex-1" />
                {/* Pagination */}
                <div className="flex items-center gap-2">
                  <button
                    disabled={page === 0}
                    onClick={() => setPage(p => p - 1)}
                    className="w-8 h-8 flex items-center justify-center glass rounded-xl
                               text-white/50 hover:text-white/90 disabled:opacity-30 transition-colors"
                  >◀</button>
                  <span className="text-[12px] text-white/40 tabular-nums w-16 text-center">
                    {page + 1} / {totalPages}
                  </span>
                  <button
                    disabled={page >= totalPages - 1}
                    onClick={() => setPage(p => p + 1)}
                    className="w-8 h-8 flex items-center justify-center glass rounded-xl
                               text-white/50 hover:text-white/90 disabled:opacity-30 transition-colors"
                  >▶</button>
                </div>
              </div>

              {/* Scroll-linked note viewer */}
              {loading ? (
                <div className="note-scroll">
                  {Array(8).fill(0).map((_, i) => (
                    <section key={i} className="note-stage">
                      <div className="paper-note rounded-md h-[58vh] max-w-3xl w-full animate-pulse" />
                    </section>
                  ))}
                </div>
              ) : paginated.length > 0 ? (
                <AnimatePresence mode="wait">
                  <motion.div
                    key={page}
                    initial={{ opacity: 0, rotateX: -8, y: 24 }}
                    animate={{ opacity: 1, rotateX: 0,  y: 0 }}
                    exit={{    opacity: 0, rotateX:  8, y: -24 }}
                    transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
                    style={{ perspective: 1200, transformStyle: 'preserve-3d' }}
                    className="note-scroll"
                  >
                    {paginated.map((p, i) => (
                      <section key={p.id} className="note-stage">
                        <ProblemCardCuration
                          problem={p}
                          index={i}
                          showSol={filters.showSol}
                          onStatusChange={handleStatusChange}
                          onPostClick={setPostTarget}
                        />
                      </section>
                    ))}
                  </motion.div>
                </AnimatePresence>
              ) : (
                <div className="glass rounded-2xl p-10 text-center text-white/30 text-sm">
                  条件に一致する問題がありません
                </div>
              )}
            </div>
          )}

          {/* ── TAB 2: 選択済み + 生成 ── */}
          {tab === 'selected' && (
            <div className="max-w-2xl mx-auto">
              <div className="mb-5">
                <h1 className="text-[22px] font-bold tracking-tight text-white/90">選択済み問題</h1>
                <p className="text-[12px] text-white/30 mt-0.5">{selected.length} 件</p>
              </div>
              <GenerationPanel
                selectedProblems={selected}
                onStatusChange={handleStatusChange}
                onPostClick={setPostTarget}
              />
            </div>
          )}
        </div>
      </main>

      {/* Spotlight overlay */}
      {showSearch && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex flex-col items-center pt-[15vh]">
          <div className="w-full max-w-2xl px-4">
            <SpotlightSearch problems={problems} />
          </div>
          <button
            onClick={() => setShowSearch(false)}
            className="mt-4 text-white/30 text-sm hover:text-white/60"
          >
            Esc で閉じる
          </button>
        </div>
      )}

      {/* Post modal */}
      <PostModal
        problem={postTarget}
        onClose={() => setPostTarget(null)}
        onPosted={handlePosted}
      />
    </div>
  )
}
