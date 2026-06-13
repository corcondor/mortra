'use client'
/**
 * /scan — 写真 → LaTeX → 鉄緑会風PDF (TeX64 再現)
 * 画像を選択 or 貼り付け → Vision AI で LaTeX 書き起こし → 編集 → PDF生成・保存
 * 水墨画風の和風UI (Three.js)
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { InkBackground } from '@/components/InkBackground'

interface HistoryEntry {
  id: string
  title: string
  date: string
  statement: string
  solution: string
}

type Phase = 'idle' | 'ocr' | 'compiling'

const HISTORY_KEY = 'scan-history-v1'

export default function ScanPage() {
  const [image, setImage] = useState<string | null>(null)
  const [quality, setQuality] = useState<'standard' | 'high'>('standard')
  const [title, setTitle] = useState('')
  const [statement, setStatement] = useState('')
  const [solution, setSolution] = useState('')
  const [phase, setPhase] = useState<Phase>('idle')
  const [error, setError] = useState<string | null>(null)
  const [pdfUrl, setPdfUrl] = useState<string | null>(null)
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    try { setHistory(JSON.parse(localStorage.getItem(HISTORY_KEY) ?? '[]')) } catch { /* noop */ }
  }, [])

  const saveHistory = useCallback((entry: HistoryEntry) => {
    setHistory(prev => {
      const next = [entry, ...prev.filter(h => h.id !== entry.id)].slice(0, 30)
      localStorage.setItem(HISTORY_KEY, JSON.stringify(next))
      return next
    })
  }, [])

  function loadFile(file: File) {
    const reader = new FileReader()
    reader.onload = () => setImage(reader.result as string)
    reader.readAsDataURL(file)
  }

  // クリップボード貼り付け（ページ全体で受け付け）
  useEffect(() => {
    const onPaste = (e: ClipboardEvent) => {
      const item = Array.from(e.clipboardData?.items ?? []).find(i => i.type.startsWith('image/'))
      const f = item?.getAsFile()
      if (f) { loadFile(f); e.preventDefault() }
    }
    window.addEventListener('paste', onPaste)
    return () => window.removeEventListener('paste', onPaste)
  }, [])

  async function runOcr() {
    if (!image) return
    setPhase('ocr'); setError(null)
    try {
      const res = await fetch('/api/ocr', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image, quality }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.error)
      setTitle(data.title)
      setStatement(data.statement)
      setSolution(data.solution ?? '')
    } catch (e: any) {
      setError(e.message)
    } finally {
      setPhase('idle')
    }
  }

  async function generatePdf() {
    if (!statement.trim()) return
    setPhase('compiling'); setError(null)
    try {
      const res = await fetch('/api/pdf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          doc: { title: title || '問題', statement, solution: solution || null },
        }),
      })
      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.log ? `${data.error}\n${data.log}` : data.error)
      }
      const blob = await res.blob()
      setPdfUrl(prev => { if (prev) URL.revokeObjectURL(prev); return URL.createObjectURL(blob) })
      saveHistory({
        id: crypto.randomUUID(),
        title: title || '無題',
        date: new Date().toLocaleString('ja-JP', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }),
        statement, solution,
      })
    } catch (e: any) {
      setError(e.message)
    } finally {
      setPhase('idle')
    }
  }

  function downloadPdf() {
    if (!pdfUrl) return
    const a = document.createElement('a')
    a.href = pdfUrl
    a.download = `${title || 'sakumon'}.pdf`
    a.click()
  }

  function restoreEntry(h: HistoryEntry) {
    setTitle(h.title); setStatement(h.statement); setSolution(h.solution)
  }

  function deleteEntry(id: string) {
    setHistory(prev => {
      const next = prev.filter(h => h.id !== id)
      localStorage.setItem(HISTORY_KEY, JSON.stringify(next))
      return next
    })
  }

  const busy = phase !== 'idle'

  return (
    <div className="min-h-screen text-[#2a2a2e]" style={{ fontFamily: '"Hiragino Mincho ProN", "Yu Mincho", serif' }}>
      <InkBackground />

      <div className="flex min-h-screen">
        {/* ── 履歴サイドバー ── */}
        <aside className="w-60 shrink-0 border-r border-black/10 bg-white/40 backdrop-blur-sm p-4 hidden md:block">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xl font-bold tracking-wider">墨写</span>
            <span className="text-[10px] text-black/40 tracking-widest">SCAN → TeX</span>
          </div>
          <a href="/" className="text-[11px] text-black/40 hover:text-black/70">← Sakumon Station</a>
          <div className="mt-5 text-[11px] text-black/40 tracking-widest mb-2">履歴</div>
          <div className="space-y-1.5 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 140px)' }}>
            {history.length === 0 && <p className="text-[11px] text-black/30">まだありません</p>}
            {history.map(h => (
              <div key={h.id}
                className="group rounded-lg px-3 py-2 bg-white/50 hover:bg-white/80 cursor-pointer border border-black/5 transition-colors"
                onClick={() => restoreEntry(h)}>
                <div className="flex justify-between items-start gap-1">
                  <span className="text-[12px] font-semibold leading-tight">{h.title}</span>
                  <button onClick={e => { e.stopPropagation(); deleteEntry(h.id) }}
                    className="opacity-0 group-hover:opacity-100 text-black/30 hover:text-black/70 text-[11px]">✕</button>
                </div>
                <span className="text-[10px] text-black/35">{h.date}</span>
              </div>
            ))}
          </div>
        </aside>

        {/* ── メイン ── */}
        <main className="flex-1 grid lg:grid-cols-2 gap-6 p-6 max-w-[1500px] mx-auto w-full">
          {/* 入力カラム */}
          <section className="space-y-4">
            <div className="flex items-center justify-between">
              <h1 className="text-lg font-bold tracking-wide">写真 → LaTeX → PDF</h1>
              <div className="flex rounded-full border border-black/15 overflow-hidden text-[12px]">
                <button onClick={() => setQuality('standard')}
                  className={`px-3 py-1 ${quality === 'standard' ? 'bg-[#2a2a2e] text-white' : 'bg-white/50'}`}>標準</button>
                <button onClick={() => setQuality('high')}
                  className={`px-3 py-1 ${quality === 'high' ? 'bg-[#2a2a2e] text-white' : 'bg-white/50'}`}>高品質</button>
              </div>
            </div>

            {/* 画像ドロップ/貼り付けゾーン */}
            <div
              onClick={() => fileRef.current?.click()}
              onDragOver={e => e.preventDefault()}
              onDrop={e => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) loadFile(f) }}
              className="rounded-2xl border-2 border-dashed border-black/20 bg-white/40 backdrop-blur-sm
                         min-h-[200px] flex items-center justify-center cursor-pointer hover:border-black/40 transition-colors overflow-hidden"
            >
              {image
                ? <img src={image} alt="入力画像" className="max-h-[320px] w-full object-contain" />
                : <div className="text-center text-black/40 text-[13px] p-8">
                    <div className="text-3xl mb-2">⛩</div>
                    クリックして画像を選択<br />または Ctrl+V で貼り付け / ドラッグ&ドロップ
                  </div>}
            </div>
            <input ref={fileRef} type="file" accept="image/*" className="hidden"
              onChange={e => { const f = e.target.files?.[0]; if (f) loadFile(f) }} />

            <div className="flex gap-2">
              <button onClick={runOcr} disabled={!image || busy}
                className="px-4 py-2 rounded-xl bg-[#2a2a2e] text-white text-[13px] disabled:opacity-40 hover:bg-black transition-colors">
                {phase === 'ocr' ? '読み取り中…' : '⌘ LaTeX 書き起こし'}
              </button>
              <button onClick={generatePdf} disabled={!statement.trim() || busy}
                className="px-4 py-2 rounded-xl border border-[#2a2a2e] text-[13px] disabled:opacity-40 bg-white/60 hover:bg-white transition-colors">
                {phase === 'compiling' ? '組版中…' : '▷ PDFを生成'}
              </button>
              {pdfUrl && (
                <button onClick={downloadPdf}
                  className="px-4 py-2 rounded-xl border border-black/20 text-[13px] bg-white/60 hover:bg-white transition-colors">
                  ↓ 保存
                </button>
              )}
            </div>

            {error && (
              <p className="text-[12px] text-red-700/90 whitespace-pre-wrap bg-red-50/70 rounded-xl p-3 border border-red-200">{error}</p>
            )}

            {/* LaTeX 編集 */}
            <div className="space-y-3">
              <input value={title} onChange={e => setTitle(e.target.value)} placeholder="タイトル"
                className="w-full rounded-xl border border-black/15 bg-white/60 px-3 py-2 text-[13px] focus:outline-none focus:border-black/40" />
              <div>
                <label className="text-[11px] text-black/40 tracking-widest">問題文 (LaTeX)</label>
                <textarea value={statement} onChange={e => setStatement(e.target.value)} rows={6}
                  placeholder="$\int_0^1 x^2\,dx$ を求めよ."
                  className="w-full rounded-xl border border-black/15 bg-white/60 px-3 py-2 text-[12px] font-mono focus:outline-none focus:border-black/40" />
              </div>
              <div>
                <label className="text-[11px] text-black/40 tracking-widest">解答 (LaTeX・省略可)</label>
                <textarea value={solution} onChange={e => setSolution(e.target.value)} rows={8}
                  className="w-full rounded-xl border border-black/15 bg-white/60 px-3 py-2 text-[12px] font-mono focus:outline-none focus:border-black/40" />
              </div>
            </div>
          </section>

          {/* PDF プレビューカラム */}
          <section className="space-y-2">
            <h2 className="text-[11px] text-black/40 tracking-widest">PDF プレビュー（鉄緑会風）</h2>
            {pdfUrl ? (
              <object data={pdfUrl} type="application/pdf"
                className="w-full rounded-2xl border border-black/10 bg-white shadow-lg"
                style={{ height: 'calc(100vh - 120px)' }}>
                <a href={pdfUrl} target="_blank" className="text-[13px] underline">PDFを開く</a>
              </object>
            ) : (
              <div className="rounded-2xl border border-black/10 bg-white/50 backdrop-blur-sm flex items-center justify-center text-black/30 text-[13px]"
                style={{ height: 'calc(100vh - 120px)' }}>
                生成するとここに表示されます
              </div>
            )}
          </section>
        </main>
      </div>
    </div>
  )
}
