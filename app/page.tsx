'use client'
import { useState, useEffect, useMemo, useCallback, useRef } from 'react'
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
  sort: 'newest', perPage: 12, showSol: false,
}

type ProblemSource = 'current' | 'own' | 'past' | 'all'

export default function Home() {
  return <AuthGuard><HomeInner /></AuthGuard>
}

function HomeInner() {
  const { user, signOut, accessToken, isAdmin, supabase } = useAuth()
  const [problems,  setProblems]  = useState<ProblemWithRating[]>([])
  const [source,    setSource]    = useState<ProblemSource>('current')
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
    // 5,000件超を ratings と JOIN して全件取得すると DB が statement timeout に
    // なり、一覧が空になっていた。スコア上位に絞り、ratings は別途まとめて引く。
    // 出所で分ける。過去問の source_file は 01_tokyo/... のように数字で始まる。
    // 自作（MathOS 生成・手作り）はそれ以外か null。
    // 分けないと total 降順の上位600件が過去問で埋まり、
    // 自作の問題が一覧に1問も出てこない（実測で 0/600 だった）。
    const LIMIT = 600
    let query = supabase.from('problems').select('*')
    if (source === 'current') {
      query = query.eq('source_file', 'mathos_discord_entrance_v2')
    } else if (source === 'own') {
      query = query.or('source_file.is.null,source_file.not.like.0*')
    } else if (source === 'past') {
      query = query.like('source_file', '0%')
    }
    const { data, error } = await query
      .order('total', { ascending: false })
      .limit(LIMIT)
    if (error) { console.error(error); setLoading(false); return }

    const rows = ((data ?? []) as Record<string, unknown>[]).filter((row) => {
      if (row.source_file === 'mathos_discord_archive') return false
      if (row.source_file !== 'mathos_discord_entrance_v2') return true
      try {
        const meta = typeof row.meta === 'string' ? JSON.parse(row.meta) : row.meta
        return meta?.activePool !== false
      } catch {
        return true
      }
    })
    const ids = rows.map((p) => String(p.id))
    const ratingById = new Map<string, unknown>()
    if (ids.length) {
      const { data: ratings } = await supabase
        .from('ratings')
        .select('*')
        .in('problem_id', ids)
      const ratingRows = (ratings ?? []) as Record<string, unknown>[]
      for (const r of ratingRows) {
        if (r.user_id == null) ratingById.set(String(r.problem_id), r)
      }
      for (const r of ratingRows) {
        if (user?.id && r.user_id === user.id) ratingById.set(String(r.problem_id), r)
      }
    }
    const normalized = rows.map((p) => ({
      ...p,
      rating: ratingById.get(String(p.id)) ?? null,
    }))
    setProblems(normalized as ProblemWithRating[])
    setLoading(false)
  }, [supabase, source, user?.id])

  useEffect(() => { loadProblems() }, [loadProblems])

  // ── フィルター ─────────────────────────────────────────────────────────
  const filtered = useMemo(() => {
    let ps = [...problems]
    if (filters.topic)  ps = ps.filter(p => p.topic_a === filters.topic || p.topic_b === filters.topic)
    if (filters.status) ps = ps.filter(p => (p.rating?.status ?? 'pending') === filters.status)
    if (filters.sort === 'newest')     ps.sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))
    else if (filters.sort === 'surprise')   ps.sort((a, b) => (b.surprise||0) - (a.surprise||0))
    else if (filters.sort === 'topic') ps.sort((a, b) => a.topic_a.localeCompare(b.topic_a))
    return ps
  }, [problems, filters])

  const selected   = useMemo(() => problems.filter(p => p.rating?.status === 'selected'), [problems])
  const unreviewed = useMemo(
    () => problems.filter(p => !p.rating || p.rating.status === 'pending').length,
    [problems],
  )
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

    // MathOS で生成する。外部 LLM を使わないので API 残高で止まらない。
    try {
      const res = await fetch('/api/mathos-generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        },
        body: JSON.stringify({
          count: examFusionCount,
          domain: parents[0]?.topic_a || undefined,
        }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => null)
        const msg = data?.error ?? `エラー: ${res.status}`
        setExamLogs([msg]); setExamDone({ ok: false, message: msg }); setExamRunning(false); return
      }
      const data = await res.json() as {
        generated: number
        requested: number
        engine: string
        cards: { family_id?: string; answer_tex?: string }[]
        errors: string[]
      }
      const lines = data.cards.map(
        (card, index) => `${index + 1}. ${card.family_id ?? '?'} → ${card.answer_tex ?? '?'}`,
      )
      const ok = data.generated > 0
      const msg = ok
        ? `✅ 完了: ${data.generated}/${data.requested} 問（${data.engine}）`
        : `❌ 生成できませんでした（${data.errors[0] ?? '理由不明'}）`
      setExamLogs([...lines, ...data.errors, msg])
      setExamDone({ ok, message: msg })
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
    <div className="light-shell relative flex h-screen flex-col overflow-hidden text-[#14213d] md:flex-row">
      <Background />

      {/* Mobile sidebar backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-[#14213d]/30 md:hidden"
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
      <main className="flex min-w-0 flex-1 flex-col overflow-hidden">

        {/* Top bar */}
        <header className="flex h-16 shrink-0 items-center gap-3 border-b border-[#d8dee9] bg-white px-3 md:px-5">
          <button
            onClick={() => setSidebarOpen(s => !s)}
            className="flex h-9 w-9 flex-col items-center justify-center gap-1.5 text-[#667085] md:hidden"
            aria-label="メニュー"
          >
            <span className="block h-px w-5 bg-current" />
            <span className="block h-px w-5 bg-current" />
            <span className="block h-px w-5 bg-current" />
          </button>

          {/* Tabs */}
          <nav className="flex h-full items-stretch gap-1 overflow-x-auto" aria-label="主要機能">
            {([['list','問題一覧'], ['selected','選択済み・生成'], ['pastexam','過去問DB']] as [Tab, string][]).map(([t, label]) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`relative whitespace-nowrap border-b-2 px-3 text-[12px] font-semibold transition-colors md:px-4 md:text-[13px]
                  ${tab === t
                    ? 'border-[#175cd3] text-[#175cd3]'
                    : 'border-transparent text-[#667085] hover:text-[#344054]'}`}
              >
                {label}
                {t === 'selected' && selected.length > 0 && (
                  <span className="ml-1.5 rounded-full bg-[#175cd3] px-1.5 py-0.5 text-[10px] text-white">
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
            className="hidden h-9 items-center gap-2 rounded border border-[#d0d5dd] bg-white px-3 text-[12px] text-[#667085] transition-colors hover:border-[#98a2b3] md:flex"
            aria-label="問題を検索"
          >
            <span aria-hidden>⌕</span>
            <span>検索</span>
            <kbd className="rounded border border-[#e4e7ec] bg-[#f8fafc] px-1 text-[10px]">⌘K</kbd>
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
                  className="h-7 w-7 rounded-full border border-[#d0d5dd]"
                />
              )}
              {isAdmin && (
                <span className="text-[10px] font-semibold text-[#175cd3]">ADMIN</span>
              )}
              <button
                onClick={signOut}
                className="text-[11px] text-[#667085] transition-colors hover:text-[#344054]"
                title="ログアウト"
              >
                ログアウト
              </button>
            </div>
          )}
        </header>

        {/* Content */}
        <div ref={contentRef} className="flex-1 overflow-y-auto px-3 py-4 md:px-5 md:py-5">

          {/* ── TAB 1: 問題一覧 ── */}
          {tab === 'list' && (
            <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_220px]">
              <div className="min-w-0">
              {/* 出所の切り替え。過去問と自作を混ぜると選別ができない。 */}
              <div className="mb-3 flex flex-wrap items-center gap-1.5">
                {([
                  ['current', '最新MathOS'],
                  ['own',  '自作（MathOS・手作り）'],
                  ['past', '過去問'],
                  ['all',  'すべて'],
                ] as [ProblemSource, string][]).map(([key, label]) => (
                  <button
                    key={key}
                    onClick={() => { setSource(key); setPage(0) }}
                    className="rounded-full border px-3.5 py-1.5 text-[12px] font-medium transition-colors"
                    style={{
                      borderColor: source === key ? '#175cd3' : '#d0d5dd',
                      background:  source === key ? '#eff6ff' : '#fff',
                      color:       source === key ? '#175cd3' : '#667085',
                    }}
                  >
                    {label}
                  </button>
                ))}
              </div>

              <div className="mb-4 flex items-center gap-4">
                <div>
                  <h1 className="text-[22px] font-bold text-[#14213d]">
                    {source === 'current' ? '最新のMathOS問題' : source === 'past' ? '過去問' : source === 'own' ? '自作の問題' : '問題一覧'}
                  </h1>
                  <p className="mt-0.5 text-[12px] text-[#667085]">
                    {loading
                      ? '読み込み中…'
                      : `${filtered.length} 件 · 未評価 ${unreviewed} 件 · ${page + 1} / ${totalPages} ページ`}
                  </p>
                </div>
                <div className="flex-1" />
                <div className="flex items-center gap-2">
                  <button
                    disabled={page === 0}
                    onClick={() => setPage(p => p - 1)}
                    className="glass flex h-8 w-8 items-center justify-center rounded text-[#667085] transition-colors hover:border-[#98a2b3] hover:text-[#175cd3] disabled:opacity-30"
                    aria-label="前のページ"
                  >‹</button>
                  <span className="w-16 text-center text-[12px] tabular-nums text-[#667085]">
                    {page + 1} / {totalPages}
                  </span>
                  <button
                    disabled={page >= totalPages - 1}
                    onClick={() => setPage(p => p + 1)}
                    className="glass flex h-8 w-8 items-center justify-center rounded text-[#667085] transition-colors hover:border-[#98a2b3] hover:text-[#175cd3] disabled:opacity-30"
                    aria-label="次のページ"
                  >›</button>
                </div>
              </div>

              {loading ? (
                <div className="note-scroll">
                  {Array(8).fill(0).map((_, i) => (
                    <section key={i} className="note-stage">
                      <div className="paper-note h-[286px] w-full animate-pulse rounded-md" />
                    </section>
                  ))}
                </div>
              ) : paginated.length > 0 ? (
                  <div
                    key={page}
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
                  </div>
              ) : (
                <div className="glass rounded-md p-10 text-center text-sm text-[#667085]">
                  条件に一致する問題がありません
                </div>
              )}
              </div>
              <ReviewRail problems={problems} />
            </div>
          )}

          {/* ── TAB 3: 過去問DB ── */}
          {tab === 'pastexam' && fusionExams.length === 0 && (
            <PastExamDB onStartFusion={handleStartFusion} isAdmin={isAdmin} />
          )}

          {/* 過去問 融合生成パネル */}
          {tab === 'pastexam' && fusionExams.length > 0 && (
            <div className="mx-auto max-w-3xl space-y-4">
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setFusionExams([])}
                  className="text-sm text-[#667085] transition-colors hover:text-[#175cd3]"
                >← 戻る</button>
                <h1 className="text-[20px] font-bold text-[#14213d]">過去問 融合生成</h1>
              </div>

              {fusionExams.map(e => (
                <div key={e.id} className="glass space-y-2 rounded-md p-4">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-[#344054]">
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
                  <p className="text-[11px] text-[#667085]">
                    上のリンクで問題を確認し、問題文（LaTeX可）を貼り付けてください
                  </p>
                  <textarea
                    value={examTexts[e.id] ?? ''}
                    onChange={ev => setExamTexts(prev => ({ ...prev, [e.id]: ev.target.value }))}
                    placeholder={`${e.univShort} ${e.year} ${e.type} の問題文をここに貼り付け…`}
                    rows={5}
                    className="w-full resize-y rounded border border-[#d0d5dd] bg-white px-3 py-2 font-mono text-[12px] text-[#344054] outline-none placeholder:text-[#98a2b3] focus:border-[#84adff]"
                  />
                </div>
              ))}

              {/* 生成数 + 実行ボタン */}
              <div className="glass space-y-3 rounded-md p-4">
                <div className="flex items-center gap-3">
                  <span className="w-20 shrink-0 text-[12px] text-[#475467]">生成数</span>
                  <input
                    type="range" min={1} max={6} value={examFusionCount}
                    onChange={ev => setExamFusionCount(+ev.target.value)}
                    className="flex-1 accent-apple-blue h-1"
                  />
                  <span className="w-4 text-right text-[12px] tabular-nums text-[#475467]">
                    {examFusionCount}
                  </span>
                </div>

                <button
                  onClick={handleExamFusion}
                  disabled={examRunning || !isAdmin}
                  className="w-full rounded bg-[#175cd3] py-2.5 text-[13px] font-semibold text-white transition-colors hover:bg-[#004eeb] disabled:opacity-40"
                >
                  {examRunning ? '送信中…' : `⚡ ${examFusionCount} 問 融合生成`}
                </button>
                {!isAdmin && (
                    <p className="text-center text-[11px] text-[#667085]">
                    管理者のみ生成可能
                  </p>
                )}
              </div>

              {/* ログ */}
              {examLogs.length > 0 && (
                <div className="glass space-y-1 rounded-md p-4 font-mono text-[11px]">
                  {examLogs.map((l, i) => <div key={i} className="text-[#475467]">{l}</div>)}
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
            <div className="mx-auto max-w-4xl">
              <div className="mb-5">
                <h1 className="text-[22px] font-bold text-[#14213d]">選択済み問題</h1>
                <p className="mt-0.5 text-[12px] text-[#667085]">{selected.length} 件</p>
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
        <div className="fixed inset-0 z-50 flex flex-col items-center bg-[#14213d]/35 pt-[15vh]">
          <div className="w-full max-w-2xl px-4">
            <SpotlightSearch problems={problems} />
          </div>
          <button
            onClick={() => setShowSearch(false)}
            className="mt-4 text-sm text-white hover:text-white/80"
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

function ReviewRail({ problems }: { problems: ProblemWithRating[] }) {
  const summary = useMemo(() => {
    let selected = 0
    let rejected = 0
    let posted = 0
    let incorrect = 0

    for (const problem of problems) {
      const status = problem.rating?.status ?? 'pending'
      if (status === 'selected') selected += 1
      if (status === 'rejected') rejected += 1
      if (problem.rating?.x_posted) posted += 1
      if (problem.rating?.is_incorrect) incorrect += 1
    }

    return {
      selected,
      rejected,
      posted,
      incorrect,
      pending: Math.max(0, problems.length - selected - rejected),
    }
  }, [problems])

  const rows = [
    { label: '未判定', value: summary.pending, color: 'bg-[#98a2b3]' },
    { label: '選択済み', value: summary.selected, color: 'bg-[#175cd3]' },
    { label: '投稿済み', value: summary.posted, color: 'bg-[#067647]' },
    { label: '除外', value: summary.rejected, color: 'bg-[#667085]' },
    { label: '要修正', value: summary.incorrect, color: 'bg-[#d92d20]' },
  ]

  return (
    <aside className="glass sticky top-0 hidden rounded-md xl:block" aria-labelledby="review-heading">
      <div className="border-b border-[#e4e7ec] px-4 py-3">
        <h2 id="review-heading" className="text-[13px] font-bold text-[#14213d]">レビュー状況</h2>
        <p className="mt-0.5 text-[10px] text-[#667085]">現在の問題ライブラリ</p>
      </div>
      <div className="space-y-3 px-4 py-4">
        {rows.map(row => (
          <div key={row.label} className="flex items-center gap-2.5">
            <span className={`h-2 w-2 rounded-full ${row.color}`} aria-hidden />
            <span className="flex-1 text-[11px] text-[#667085]">{row.label}</span>
            <span className="text-[12px] font-semibold tabular-nums text-[#344054]">{row.value}</span>
          </div>
        ))}
      </div>
      <div className="border-t border-[#e4e7ec] px-4 py-3">
        <p className="text-[10px] leading-5 text-[#667085]">
          問題を比較し、選択した候補を「選択・生成」で融合・類題生成できます。
        </p>
      </div>
    </aside>
  )
}
