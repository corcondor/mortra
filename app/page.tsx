'use client'
import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Background }            from '@/components/Background'
import { Sidebar, type Filters } from '@/components/Sidebar'
import { ProblemCardCuration }   from '@/components/ProblemCardCuration'
import { GenerationPanel }       from '@/components/GenerationPanel'
import { PostModal }             from '@/components/PostModal'
import { SpotlightSearch }       from '@/components/SpotlightSearch'
import { AuthGuard, useAuth }    from '@/components/AuthGuard'
import { PastExamDB, type PastExamEntry } from '@/components/PastExamDB'
import { XConnectButton } from '@/components/XConnectButton'
import type { ProblemWithRating } from '@/lib/types'

type Tab = 'list' | 'selected' | 'pastexam'

const DEFAULT_FILTERS: Filters = {
  topic: null, status: null,
  sort: 'total', perPage: 12, showSol: false,
}

export default function Home() {
  return <AuthGuard><HomeInner /></AuthGuard>
}

function HomeInner() {
  const { user, signOut, accessToken, isAdmin, supabase } = useAuth()
  const [problems,  setProblems]  = useState<ProblemWithRating[]>([])
  const [loading,   setLoading]   = useState(true)
  const [tab,       setTab]       = useState<Tab>('list')
  const [filters,   setFilters]   = useState<Filters>(DEFAULT_FILTERS)
  const [page,      setPage]      = useState(0)
  const [postTarget,    setPostTarget]   = useState<ProblemWithRating | null>(null)
  const [showSearch,    setShowSearch]   = useState(false)
  const [sidebarOpen,   setSidebarOpen]  = useState(false)
  const [fusionExams,   setFusionExams]  = useState<PastExamEntry[]>([])
  const [examTexts,     setExamTexts]    = useState<Record<string, string>>({})
  const [examFusionCount, setExamFusionCount] = useState(3)
  const [examRunning,   setExamRunning]  = useState(false)
  const [examLogs,      setExamLogs]     = useState<string[]>([])
  const [examDone,      setExamDone]     = useState<{ ok: boolean; message: string } | null>(null)
  const contentRef = useRef<HTMLDivElement>(null)

  // ── データ取得（Supabase クライアント経由 = ユーザーセッションで RLS が効く） ──
  const loadProblems = useCallback(async () => {
    setLoading(true)
    const { data, error } = await supabase
      .from('problems')
      .select('*, rating:ratings(*)')
      .order('total', { ascending: false })
    if (error) { console.error(error); setLoading(false); return }
    const normalized = (data ?? []).map((p: Record<string, unknown>) => ({
      ...p,
      rating: Array.isArray(p.rating) ? (p.rating as unknown[])[0] ?? null : p.rating,
    }))
    setProblems(normalized as ProblemWithRating[])
    setLoading(false)
  }, [supabase])

  useEffect(() => { loadProblems() }, [loadProblems])

  // ── フィルター ─────────────────────────────────────────────────────────
  const filtered = useMemo(() => {
    let ps = [...problems]
    if (filters.topic)  ps = ps.filter(p => p.topic_a === filters.topic || p.topic_b === filters.topic)
    if (filters.status) ps = ps.filter(p => (p.rating?.status ?? 'pending') === filters.status)
    if (filters.sort === 'surprise')   ps.sort((a, b) => (b.surprise||0) - (a.surprise||0))
    else if (filters.sort === 'topic') ps.sort((a, b) => a.topic_a.localeCompare(b.topic_a))
    return ps
  }, [problems, filters])

  const selected   = useMemo(() => problems.filter(p => p.rating?.status === 'selected'), [problems])
  const totalPages = Math.max(1, Math.ceil(filtered.length / filters.perPage))
  const paginated  = filtered.slice(page * filters.perPage, (page + 1) * filters.perPage)

  // ── ステータス更新（楽観的UI） ─────────────────────────────────────────
  const blankRating = (id: string) => ({
    problem_id: id, status: 'pending' as never, x_posted: false,
    note: null, is_incorrect: false, corrected_answer: null, updated_at: '',
  })

  const handleStatusChange = useCallback((id: string, status: string) => {
    setProblems(prev => prev.map(p =>
      p.id !== id ? p : {
        ...p,
        rating: { ...(p.rating ?? blankRating(id)), status: status as never },
      }
    ))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleAnswerChange = useCallback((id: string, correctedAnswer: string | null, isIncorrect: boolean) => {
    setProblems(prev => prev.map(p =>
      p.id !== id ? p : {
        ...p,
        rating: {
          ...(p.rating ?? blankRating(id)),
          is_incorrect:     isIncorrect,
          corrected_answer: correctedAnswer,
        },
      }
    ))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handlePosted = useCallback((id: string) => {
    setProblems(prev => prev.map(p =>
      p.id !== id ? p : {
        ...p,
        rating: { ...(p.rating ?? blankRating(id)), x_posted: true, status: 'posted' as never },
      }
    ))
  }, [])

  const handleFiltersChange = (f: Filters) => { setFilters(f); setPage(0) }

  // ── 過去問融合生成ハンドラ ─────────────────────────────────────────────
  const handleStartFusion = (exams: PastExamEntry[]) => {
    setFusionExams(exams)
    setExamTexts({})
    setExamLogs([])
    setExamDone(null)
    setTab('pastexam')
  }

  const handleExamFusion = async () => {
    const missingText = fusionExams.find(e => !examTexts[e.id]?.trim())
    if (missingText) {
      alert(`「${missingText.univShort} ${missingText.year} ${missingText.type}」の問題文を入力してください`)
      return
    }
    setExamRunning(true); setExamLogs([]); setExamDone(null)

    const parents = fusionExams.map(e => ({
      id:        e.id,
      topic_a:   e.univCode,
      topic_b:   e.type,
      statement: examTexts[e.id] ?? '',
      answer:    '',
      inspiration: `${e.univName} ${e.year}年度${e.type}`,
      total:     80,
      solution:  '',
    }))

    const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
    const enqueueUrl  = supabaseUrl
      ? `${supabaseUrl}/functions/v1/enqueue-generation`
      : '/api/generate'

    try {
      const res = await fetch(enqueueUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        },
        body: JSON.stringify({ parents, mode: 'fusion', count: examFusionCount }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => null)
        const msg = data?.error ?? `エラー: ${res.status}`
        setExamLogs([msg]); setExamDone({ ok: false, message: msg }); setExamRunning(false); return
      }
      const { job_id } = await res.json()
      setExamLogs([`🚀 ジョブ受付: ${job_id} — 「選択済み・生成」タブで進捗を確認できます`])
      setExamDone({ ok: true, message: `✅ エンキュー完了 (${job_id})` })
    } catch (e) {
      const msg = `送信失敗: ${e}`
      setExamLogs([msg]); setExamDone({ ok: false, message: msg })
    }
    setExamRunning(false)
  }

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
            {([['list','問題一覧'], ['selected','選択済み・生成'], ['pastexam','過去問DB']] as [Tab, string][]).map(([t, label]) => (
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

          {/* X接続 */}
          {user && <XConnectButton accessToken={accessToken} />}

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
              {isAdmin && (
                <span className="text-[10px] text-apple-blue/70 font-semibold">ADMIN</span>
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
        <div ref={contentRef} className="flex-1 overflow-y-auto scroll-smooth px-4 md:px-6 py-5">

          {/* ── TAB 1: 問題一覧 ── */}
          {tab === 'list' && (
            <div>
              <div className="flex items-center gap-4 mb-5">
                <div>
                  <h1 className="text-[22px] font-bold tracking-tight text-white/90">問題一覧</h1>
                  <p className="text-[12px] text-white/30 mt-0.5">
                    {loading ? '読み込み中…' : `${filtered.length} 件  ·  ${page + 1} / ${totalPages} ページ`}
                  </p>
                </div>
                <div className="flex-1" />
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
                          scrollRootRef={contentRef}
                          showSol={filters.showSol}
                          accessToken={accessToken}
                          onStatusChange={handleStatusChange}
                          onAnswerChange={handleAnswerChange}
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

          {/* ── TAB 3: 過去問DB ── */}
          {tab === 'pastexam' && fusionExams.length === 0 && (
            <PastExamDB onStartFusion={handleStartFusion} isAdmin={isAdmin} />
          )}

          {/* 過去問 融合生成パネル */}
          {tab === 'pastexam' && fusionExams.length > 0 && (
            <div className="max-w-2xl mx-auto space-y-4">
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setFusionExams([])}
                  className="text-white/40 hover:text-white/80 text-sm transition-colors"
                >← 戻る</button>
                <h1 className="text-[20px] font-bold text-white/90">過去問 融合生成</h1>
              </div>

              {fusionExams.map(e => (
                <div key={e.id} className="glass rounded-2xl p-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-white/80">
                      {e.univName}　{e.year}年度　{e.type}
                    </span>
                    <a
                      href={e.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[12px] text-apple-blue/70 hover:text-apple-blue underline transition-colors"
                    >
                      問題を開く →
                    </a>
                  </div>
                  <p className="text-[11px] text-white/30">
                    上のリンクで問題を確認し、問題文（LaTeX可）を貼り付けてください
                  </p>
                  <textarea
                    value={examTexts[e.id] ?? ''}
                    onChange={ev => setExamTexts(prev => ({ ...prev, [e.id]: ev.target.value }))}
                    placeholder={`${e.univShort} ${e.year} ${e.type} の問題文をここに貼り付け…`}
                    rows={5}
                    className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2
                               text-[12px] text-white/80 placeholder-white/20 outline-none
                               focus:border-apple-blue/40 resize-y font-mono"
                  />
                </div>
              ))}

              {/* 生成数 + 実行ボタン */}
              <div className="glass rounded-2xl p-4 space-y-3">
                <div className="flex items-center gap-3">
                  <span className="text-[12px] text-white/60 w-20 shrink-0">生成数</span>
                  <input
                    type="range" min={1} max={6} value={examFusionCount}
                    onChange={ev => setExamFusionCount(+ev.target.value)}
                    className="flex-1 accent-apple-blue h-1"
                  />
                  <span className="text-[12px] text-white/50 tabular-nums w-4 text-right">
                    {examFusionCount}
                  </span>
                </div>

                <button
                  onClick={handleExamFusion}
                  disabled={examRunning || !isAdmin}
                  className="w-full py-2.5 bg-apple-blue hover:bg-apple-blue/80
                             disabled:opacity-40 text-white text-[13px] font-semibold
                             rounded-xl transition-all"
                >
                  {examRunning ? '送信中…' : `⚡ ${examFusionCount} 問 融合生成`}
                </button>
                {!isAdmin && (
                  <p className="text-[11px] text-white/25 text-center">
                    管理者のみ生成可能
                  </p>
                )}
              </div>

              {/* ログ */}
              {examLogs.length > 0 && (
                <div className="glass rounded-2xl p-4 space-y-1 font-mono text-[11px]">
                  {examLogs.map((l, i) => <div key={i} className="text-white/60">{l}</div>)}
                  {examDone && (
                    <div className={`mt-2 font-semibold ${examDone.ok ? 'text-emerald-400' : 'text-red-400'}`}>
                      {examDone.message}
                    </div>
                  )}
                  {examDone?.ok && (
                    <button
                      onClick={() => { setTab('selected'); setFusionExams([]) }}
                      className="mt-2 text-apple-blue hover:text-apple-blue/80 underline text-[11px]"
                    >
                      選択済み・生成タブで進捗を確認 →
                    </button>
                  )}
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
                accessToken={accessToken}
                isAdmin={isAdmin}
                userId={user?.id ?? null}
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
        accessToken={accessToken}
        onClose={() => setPostTarget(null)}
        onPosted={handlePosted}
      />
    </div>
  )
}
