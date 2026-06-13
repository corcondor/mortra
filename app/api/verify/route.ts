/**
 * Level 1: 閉形式自動検証
 * POST /api/verify  { problem_id, answer? }
 * → WolframAlpha で数値検証 → verified フラグを ratings に保存
 */
import { NextRequest, NextResponse } from 'next/server'
import { supabaseAdmin } from '@/lib/supabase-admin'

const WOLFRAM_APP_ID = process.env.WOLFRAM_APP_ID ?? ''

async function wolframVerify(expression: string): Promise<{ result: string; valid: boolean }> {
  if (!WOLFRAM_APP_ID) {
    return { result: 'WOLFRAM_APP_ID not set', valid: false }
  }
  const url = `https://api.wolframalpha.com/v2/query?input=${encodeURIComponent(expression)}&appid=${WOLFRAM_APP_ID}&format=plaintext&output=JSON`
  const res = await fetch(url, { next: { revalidate: 3600 } })
  const data = await res.json()
  const pods = data?.queryresult?.pods ?? []
  const resultPod = pods.find((p: any) => p.id === 'Result' || p.title === 'Result')
  const plaintext = resultPod?.subpods?.[0]?.plaintext ?? ''
  return { result: plaintext, valid: plaintext.length > 0 }
}

export async function POST(req: NextRequest) {
  const { problem_id, answer } = await req.json()

  // 問題取得
  const { data: problem, error } = await supabaseAdmin
    .from('problems')
    .select('id, statement, answer, topic_a')
    .eq('id', problem_id)
    .single()

  if (error || !problem) {
    return NextResponse.json({ error: 'Problem not found' }, { status: 404 })
  }

  const targetAnswer = answer ?? problem.answer ?? ''
  if (!targetAnswer) {
    return NextResponse.json({ error: 'No answer to verify' }, { status: 400 })
  }

  // WolframAlpha で検証
  const verification = await wolframVerify(`Simplify[${targetAnswer}]`)

  // note フィールドに検証結果を保存
  const note = JSON.stringify({
    verified_at: new Date().toISOString(),
    wolfram_result: verification.result,
    wolfram_valid: verification.valid,
  })

  await supabaseAdmin
    .from('ratings')
    .upsert({ problem_id, note }, { onConflict: 'problem_id' })

  return NextResponse.json({
    problem_id,
    answer: targetAnswer,
    wolfram_result: verification.result,
    valid: verification.valid,
  })
}

/** バッチ検証: GET /api/verify?batch=true で全 selected 問題を検証 */
export async function GET(req: NextRequest) {
  const batch = req.nextUrl.searchParams.get('batch')
  if (batch !== 'true') {
    return NextResponse.json({ error: 'Use ?batch=true' }, { status: 400 })
  }

  const { data: problems } = await supabaseAdmin
    .from('problems')
    .select('id, answer, rating:ratings!inner(status)')
    .eq('ratings.status', 'selected')
    .not('answer', 'is', null)
    .limit(20)

  const results = []
  for (const p of problems ?? []) {
    const v = await wolframVerify(`Simplify[${p.answer}]`)
    results.push({ id: p.id, answer: p.answer, wolfram: v.result, valid: v.valid })
  }

  return NextResponse.json({ verified: results.length, results })
}
