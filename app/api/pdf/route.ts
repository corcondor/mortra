/**
 * 鉄緑会風 解説プリント PDF 生成
 *
 * POST /api/pdf
 *   { problem_id }              → 問題+指針+TikZ図+解答 のセット文書 PDF
 *   { problem_id, mode:'tikz' } → TikZ 図のみ standalone PDF（プレビュー用）
 *   { tex }                     → 任意の LaTeX ソースをコンパイル（/scan・/ideas 用）
 *   { ..., format:'tex' }       → PDF の代わりに .tex ソースを返す
 *
 * コンパイルは texlive.net (lualatex)。検証済み: scripts/test-tetsuryoku.tex
 */
import { NextRequest, NextResponse } from 'next/server'
import { supabaseAdmin } from '@/lib/supabase-admin'
import { buildTetsuryokuTex, buildTikzStandalone, compileTex, type TetsuryokuDoc } from '@/lib/latex'

export const maxDuration = 120

export async function POST(req: NextRequest) {
  const body = await req.json()
  const { problem_id, tex: rawTex, doc, mode, format } = body

  let tex = rawTex as string | undefined
  let filename = 'document'
  let builtDoc: TetsuryokuDoc | null = null  // 自前で組んだ場合、失敗時に解答抜き再試行できる

  // doc: {title, statement, solution?, tikz?, ...} → 鉄緑会風に組版（/scan・/ideas 用）
  if (!tex && doc?.statement) {
    builtDoc = doc
    tex = buildTetsuryokuTex(doc)
    filename = 'sakumon-scan'
  }

  if (!tex) {
    if (!problem_id) {
      return NextResponse.json({ error: 'problem_id or tex required' }, { status: 400 })
    }
    const { data: p } = await supabaseAdmin
      .from('problems')
      .select('id, statement, solution, meta, difficulty')
      .eq('id', problem_id)
      .single()
    if (!p) return NextResponse.json({ error: 'Problem not found' }, { status: 404 })

    let meta: Record<string, unknown> = {}
    try { meta = p.meta ? JSON.parse(p.meta) : {} } catch { /* 旧形式 */ }

    const tikz = typeof meta.tikz === 'string' ? meta.tikz : null

    if (mode === 'tikz') {
      if (!tikz) return NextResponse.json({ error: 'No TikZ cached. 先に図を生成してください。' }, { status: 404 })
      tex = buildTikzStandalone(tikz)
      filename = `tikz-${String(p.id).slice(0, 8)}`
    } else {
      // difficulty: meta.difficulty10 (1-10数値) 優先、なければ A-D 文字から換算
      const letterTo10: Record<string, number> = { A: 9, B: 7, C: 5, D: 3 }
      const diff10 = typeof meta.difficulty10 === 'number'
        ? meta.difficulty10
        : (p.difficulty ? letterTo10[p.difficulty] ?? null : null)

      builtDoc = {
        title: typeof meta.title === 'string' ? meta.title : '問題',
        statement: p.statement,
        solution: p.solution,
        tikz,
        features: typeof meta.features === 'string' ? meta.features : null,
        tags: Array.isArray(meta.tags) ? (meta.tags as string[]) : [],
        difficulty: diff10,
        points: typeof meta.points === 'number' ? meta.points : null,
      }
      tex = buildTetsuryokuTex(builtDoc)
      filename = `sakumon-${String(p.id).slice(0, 8)}`
    }
  }

  if (format === 'tex') {
    return new NextResponse(tex, {
      headers: {
        'Content-Type': 'application/x-tex; charset=utf-8',
        'Content-Disposition': `attachment; filename="${filename}.tex"`,
      },
    })
  }

  let result = await compileTex(tex!, 'lualatex')

  // 解答部の LaTeX が壊れている場合は解答抜きで再試行（コーパス原文に typo があるケース）
  if (!result.ok && builtDoc?.solution) {
    const fallback = await compileTex(buildTetsuryokuTex({
      ...builtDoc,
      solution: '\\textit{（解答の自動組版に失敗したため省略。元データのLaTeXに誤りがあります）}',
    }), 'lualatex')
    if (fallback.ok) result = fallback
  }

  if (!result.ok) {
    return NextResponse.json(
      { error: 'LaTeXコンパイル失敗', log: result.log },
      { status: 422 },
    )
  }

  return new NextResponse(result.pdf, {
    headers: {
      'Content-Type': 'application/pdf',
      'Content-Disposition': `inline; filename="${filename}.pdf"`,
      'Cache-Control': 'no-store',
    },
  })
}
