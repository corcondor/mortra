#!/usr/bin/env node
/**
 * sincos001 / c54ead4683de の statement・answer・topic を正しく修正するスクリプト
 *
 * 問題点:
 *  - sincos001  : 生LaTeX（$...$なし）→ \theta が \t (タブ), \beta が \b (BS) に化ける
 *  - c54ead4683de: JSON内 \frac → \f (FF文字) に化けてKaTeXが壊れる
 */

const SUPABASE_URL = 'https://dvzzsxczqatotgzlestu.supabase.co'
const SERVICE_KEY  = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImR2enpzeGN6cWF0b3Rnemxlc3R1Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3Nzk3MjA2MiwiZXhwIjoyMDkzNTQ4MDYyfQ.TowYOtOLChN-py_4GArGPNgwLkSGhMIvgb_7iAGf_nQ'

async function patch(id, fields) {
  const res = await fetch(
    `${SUPABASE_URL}/rest/v1/problems?id=eq.${encodeURIComponent(id)}`,
    {
      method: 'PATCH',
      headers: {
        'Content-Type':  'application/json',
        'apikey':        SERVICE_KEY,
        'Authorization': `Bearer ${SERVICE_KEY}`,
        'Prefer':        'return=minimal',
      },
      body: JSON.stringify(fields),
    }
  )
  return res.ok ? '✅' : `❌ (${res.status}) ${await res.text()}`
}

// ──────────────────────────────────────────────────────────────────────────────
// 1. sincos001 — sin,cos.tex から正確に転記
//    問題: x^2 + sin θ · x + cos θ = 0 の 2 解 α, β に対して
//          α乗根√β + β乗根√α = β^{1/α} + α^{1/β} の最大値・最小値
// ──────────────────────────────────────────────────────────────────────────────
const sincos = {
  topic_a: 'trigonometry',
  topic_b: 'analysis',

  statement:
    '$x^2 + \\sin\\theta \\cdot x + \\cos\\theta = 0$'
    + ' の 2 実数解を $\\alpha,\\,\\beta$ とする．'
    + '$\\sqrt[\\alpha]{\\beta}+\\sqrt[\\beta]{\\alpha}$ の最大値と最小値を求めよ．',

  answer:
    '最大値 $2(\\sqrt{5}-2)^{\\frac{1}{2\\sqrt{\\sqrt{5}-2}}}$'
    + '（$\\alpha=\\beta=\\sqrt{\\sqrt{5}-2}$，重解のとき）．'
    + '最小値は存在せず，下限は $\\dfrac{1}{e}$'
    + '（$\\theta\\to-\\dfrac{\\pi}{2}^{+}$ のとき $\\alpha\\to0,\\,\\beta\\to1$）．',

  inspiration:
    'ヴィエタより $\\alpha+\\beta=-\\sin\\theta,\\;\\alpha\\beta=\\cos\\theta$．'
    + '$\\sin^2\\theta+\\cos^2\\theta=1$ を代入して'
    + ' $(\\alpha+\\beta)^2+(\\alpha\\beta)^2=1$（$\\theta$ を消去した制約式）．'
    + '$\\beta=\\beta(\\alpha)$ に 1 変数化し'
    + ' $f(\\alpha)=\\beta(\\alpha)^{1/\\alpha}+\\alpha^{1/\\beta(\\alpha)}$ を定義．'
    + '対数微分を 2 回行い $f\'\'(\\alpha)<0$（凹性）を区間演算で確認，'
    + '$f\'(\\alpha)>0$（単調増加）が従う．'
    + '$\\alpha\\in(0,\\,t]$（$t=\\sqrt{\\sqrt{5}-2}$）の上端で最大値を実現．',

  solution:
    '制約式: $(\\alpha+\\beta)^2+(\\alpha\\beta)^2=1$（$\\sin^2+\\cos^2=1$ より）．'
    + '$\\alpha$ の範囲: $0<\\alpha\\le t$，$t=\\sqrt{\\sqrt{5}-2}$（重解条件 $4t^2+t^4=1$ の正の解）．'
    + '1変数化: $w(\\alpha)=\\sqrt{1+\\alpha^2-\\alpha^4}$，'
    + '$\\beta(\\alpha)=\\dfrac{w(\\alpha)-\\alpha}{1+\\alpha^2}$．'
    + '$f(\\alpha)=\\beta^{1/\\alpha}+\\alpha^{1/\\beta}$ の対数微分（2回）と'
    + '区間演算により $f\'\'(\\alpha)<0$，$f\'(t^-)=0$ から $f\'(\\alpha)>0$ を確定．'
    + '最大値: $f(t)=2t^{1/t}$（$t=\\sqrt{\\sqrt{5}-2}$）．'
    + '下限: $\\alpha\\to0^+$ で $\\beta^{1/\\alpha}\\to e^{-1}$，$\\alpha^{1/\\beta}\\to0$（最小値は非達成）．',
}

// ──────────────────────────────────────────────────────────────────────────────
// 2. c54ead4683de — 多項式×多項式 Gen32
//    問題: 7 サイクル x_{k+1} = x_k^2 - 2 (x_8=x_1) の下で
//          Σ 1/(x_k^2 - x_k - 1) を求める
// ──────────────────────────────────────────────────────────────────────────────
const poly7cycle = {
  topic_a: 'polynomial',
  topic_b: 'recurrence',   // 7サイクル漸化式の要素が強いのでrecurrenceに変更

  statement:
    '相異なる実数 $x_1, x_2, \\dots, x_7$ が，$k=1,2,\\dots,7$ に対して'
    + ' $x_{k+1} = x_k^2 - 2$（ただし $x_8 = x_1$）をすべて満たすとき，'
    + '$\\displaystyle\\sum_{k=1}^{7} \\frac{1}{x_k^2 - x_k - 1}$ の値を求めよ．',

  answer: '$-7$',

  inspiration:
    '$x_k = 2\\cos\\theta_k$（チェビシェフ代入）と置くと'
    + ' $x_{k+1}=x_k^2-2=2\\cos 2\\theta_k$ は倍角公式に対応．'
    + '7サイクル条件より $\\theta_k = \\dfrac{2\\pi \\cdot 2^{k-1}}{127}$（$2^7\\equiv1\\pmod{127}$）．'
    + '$x_k^2-x_k-1=(x_k-\\varphi)(x_k-\\hat\\varphi)$（$\\varphi=\\dfrac{1+\\sqrt5}{2}$）と因数分解し，'
    + '$\\sum\\dfrac{1}{x_k^2-x_k-1}=\\dfrac{1}{\\sqrt5}\\left[-\\dfrac{p\'(\\varphi)}{p(\\varphi)}'
    + '+\\dfrac{p\'(\\hat\\varphi)}{p(\\hat\\varphi)}\\right]$'
    + '（$p(x)=\\prod_{k=1}^7(x-x_k)$）．この7次多項式 $p$ は'
    + '円分多項式の因子で，$p(\\varphi)/p(\\hat\\varphi)$ を計算すると $-7$ が出る．',

  solution:
    '（1）チェビシェフ代入 $x_k=2\\cos\\theta_k$，$\\theta_1=2\\pi/127$，$\\theta_{k+1}=2\\theta_k$．'
    + '（2）$x_k^2-x_k-1=(x_k-\\varphi)(x_k-\\hat\\varphi)$，'
    + '$\\varphi=(1+\\sqrt5)/2=2\\cos(\\pi/5)$，$\\hat\\varphi=(1-\\sqrt5)/2=2\\cos(3\\pi/5)$．'
    + '（3）部分分数: $\\dfrac{1}{x_k^2-x_k-1}=\\dfrac{1}{\\sqrt5}\\left(\\dfrac{1}{x_k-\\varphi}'
    + '-\\dfrac{1}{x_k-\\hat\\varphi}\\right)$．'
    + '（4）$p(x)=\\prod(x-x_k)$ は 127 次円分多項式 $\\Phi_{127}(x)$ の因子（7次）．'
    + '$p\'(c)/p(c)=\\sum 1/(c-x_k)$ を利用．'
    + '計算により $\\dfrac{1}{\\sqrt5}(-F_\\varphi+F_{\\hat\\varphi})=-7$，答え $-7$．',
}

;(async () => {
  console.log('\n🔧 2問の statement / answer / topic を修正中...\n')

  process.stdout.write('  sincos001 ... ')
  console.log(await patch('sincos001', sincos))

  process.stdout.write('  c54ead4683de ... ')
  console.log(await patch('c54ead4683de', poly7cycle))

  console.log('\n✨ 完了！')
})()
