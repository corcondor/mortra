#!/usr/bin/env node
/**
 * OneDrive の 5 .tex ファイルを解析した問題を Supabase に挿入するスクリプト
 */

const SUPABASE_URL = 'https://dvzzsxczqatotgzlestu.supabase.co'
const SERVICE_KEY  = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImR2enpzeGN6cWF0b3Rnemxlc3R1Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3Nzk3MjA2MiwiZXhwIjoyMDkzNTQ4MDYyfQ.TowYOtOLChN-py_4GArGPNgwLkSGhMIvgb_7iAGf_nQ'

const problems = [
  // ──────────────────────────────────────────────────────────────────────────
  {
    id:         'kansu_kinki_001',
    topic_a:    'analysis',
    topic_b:    'polynomial',
    difficulty: 'A',
    generation: 0,
    total:      9.2,
    surprise:   9.0,
    minimality: 9.0,
    connection: 9.5,
    inevitability: 9.0,
    diff_cal:   9.5,
    statement:
      '正の整数 $n$ に対し，$n$ 次以下の実係数多項式 $P(x)$ で $P(0)=1,\\, P(1)=0$ を満たすもの全体を $S_n$ とする．'
      + '$M_n = \\min_{P \\in S_n} \\int_0^1 \\bigl\\{P(x)^2 + P\'(x)^2\\bigr\\}\\,dx$ とするとき，'
      + '(1) $\\lim_{n\\to\\infty} M_n$ を求めよ．'
      + '\\quad (2) この結果を用いて $e > 2.718$ を示せ．',
    answer:
      '(1)\\; $\\dfrac{e^2+1}{e^2-1}$．'
      + '\\quad (2) $M_3 = \\dfrac{9316}{7095}$ を求め，$e^2 \\ge \\dfrac{16411}{2221} > (2.718)^2$ を示す（$e>0$ より結論）．',
    inspiration:
      '$Q = P + P\'$ と置くと $J(P) = 1 + \\int_0^1 Q^2\\,dx$ に変形できる．'
      + '一方 $\\int_0^1 e^x Q\\,dx = eP(1)-P(0) = -1$ をCauchy--Schwarzに使うと '
      + '$\\int_0^1 Q^2 \\ge \\dfrac{2}{e^2-1}$ が得られ，等号は $Q = Ce^x$ すなわち '
      + '$u(x)=\\dfrac{\\sinh(1-x)}{\\sinh 1}$ で達成（多項式近似可）．'
      + '(2) は $S_3$ を3次基底で Gram 行列展開し $M_3$ を具体的に算出，'
      + '$e^2 = \\frac{L+1}{L-1}$ が $M_3$ の単調性から下から抑えられることを使う．',
    solution:
      '(1) $J(P)=1+\\int_0^1(P+P\')^2\\,dx - [P^2]_0^1 = 1+\\int_0^1 Q^2\\,dx$．'
      + 'CS不等式と $\\int_0^1 e^xQ\\,dx=-1$, $\\int_0^1 e^{2x}\\,dx=\\frac{e^2-1}{2}$ より '
      + '$\\int_0^1 Q^2\\ge\\frac{2}{e^2-1}$，故 $J(P)\\ge\\frac{e^2+1}{e^2-1}$．'
      + '下限は $u(x)=\\sinh(1-x)/\\sinh1$ を多項式近似して達成．'
      + '(2) 内積 $\\langle f,g\\rangle=\\int_0^1(fg+f\'g\')\\,dx$ で $S_3$ 上のGram行列を計算，'
      + '$M_3=9316/7095$．$L=\\lim M_n=\\frac{e^2+1}{e^2-1}\\le M_3$ より '
      + '$e^2\\ge\\frac{M_3+1}{M_3-1}=\\frac{16411}{2221}>2.718^2$．',
  },

  // ──────────────────────────────────────────────────────────────────────────
  {
    id:         'kikagaku_hukuso_001',
    topic_a:    'geometry',
    topic_b:    'complex',
    difficulty: 'A',
    generation: 0,
    total:      9.5,
    surprise:   9.5,
    minimality: 9.5,
    connection: 10.0,
    inevitability: 9.0,
    diff_cal:   9.5,
    statement:
      '中心 $O$ の単位円 $\\Gamma$ 上の相異なる 7 点 $P_1,\\ldots,P_7$（円周順，添字は $\\bmod 7$）が，'
      + '各 $k=1,\\ldots,7$ について $\\dfrac{P_kP_{k+2}\\cdot P_{k+1}P_{k+3}}{P_kP_{k+3}\\cdot P_{k+1}P_{k+2}}$ が $k$ によらず一定，'
      + 'かつ $\\sum_{i=1}^{7}\\overrightarrow{OP_i}=\\mathbf{0}$ を満たすとする．'
      + '三辺 $P_1P_2,\\,P_1P_3,\\,P_1P_4$ の三角形 $T$ の内接円半径を $r_0$，傍接円半径を $r_1,r_2,r_3$ とするとき，'
      + '$\\displaystyle\\sum_{i=0}^{3}\\dfrac{1}{r_i^2}$ を求めよ．',
    answer: '$16$',
    inspiration:
      '交比一定 $\\Rightarrow$ 円を保つ Möbius 変換 $f$ が $f(P_k)=P_{k+1}$ かつ $f^7=\\mathrm{id}$ $\\Rightarrow$ '
      + 'ある $\\alpha$ （$|\\alpha|<1$）で $z_k=\\lambda\\dfrac{\\omega^k-\\alpha}{1-\\bar\\alpha\\omega^k}$ と書ける．'
      + '重心条件 $\\sum z_k=0$ をフーリエ展開すると $\\bar\\alpha^6=\\alpha$，$|\\alpha|<1$ より $\\alpha=0$，正七角形確定．'
      + '$x=\\pi/7$ として $a=2\\sin x,b=2\\sin 2x,c=2\\sin 3x$．'
      + '$\\sum 1/r_i^2 = \\frac{4(\\sin^2 x+\\sin^2 2x+\\sin^2 3x)}{\\Delta^2}$，'
      + '$\\sin^2 x+\\sin^2 2x+\\sin^2 3x=7/4$（半角対称和），$\\Delta=\\sqrt7/4$（$\\prod_{k=1}^6 2\\sin\\frac{k\\pi}{7}=7$），答え $16$．',
    solution:
      '正七角形確定後：$r_i$ 公式より $\\sum 1/r_i^2 = [s^2+(s-a)^2+(s-b)^2+(s-c)^2]/\\Delta^2 = 4(A^2+B^2+C^2)/\\Delta^2$．'
      + '$A^2+B^2+C^2$：$\\sum_{k=1}^6\\sin^2\\frac{k\\pi}{7}=7/2$，対称性から $A^2+B^2+C^2=7/4$．'
      + '$\\Delta$：$x^6+\\cdots+1=\\prod(x-\\omega^k)$ に $x=1$ 代入 $\\Rightarrow$ '
      + '$\\prod_{k=1}^6|1-\\omega^k|=7$，$|1-\\omega^k|=2\\sin\\frac{k\\pi}{7}$ より $(8ABC)^2=7$，$\\Delta=abc/4=\\sqrt7/4$．'
      + '代入して $16$．',
  },

  // ──────────────────────────────────────────────────────────────────────────
  {
    id:         'sankakukei_housetsu_001',
    topic_a:    'geometry',
    topic_b:    'analysis',
    difficulty: 'B',
    generation: 0,
    total:      8.0,
    surprise:   8.0,
    minimality: 8.5,
    connection: 8.0,
    inevitability: 7.5,
    diff_cal:   8.0,
    statement:
      '放物線 $y=x^2$ 上の相異なる 3 点 $A,B,C$ について，$\\triangle ABC$ の内接円半径が $\\dfrac{\\sqrt{2}}{2}$ であるとする．'
      + '(1) 内心の軌跡を求めよ．'
      + '\\quad (2) $\\triangle ABC$ が整数三角形（3辺がすべて整数）となるとき，三辺の長さを求めよ．',
    answer:
      '(1) $y = x^2 + \\dfrac{1}{2} + \\dfrac{\\sqrt{2}}{2}\\sqrt{4x^2+1}$．'
      + '\\quad (2) 三辺は $2,\\,3,\\,3$．',
    inspiration:
      '(1) 内心を $I=(p,\\,p^2+h)$ と置く（$x$ 座標の対称性）．'
      + '3 辺 $P(p+\\alpha)P(p+\\beta)$ 等の直線式と $I$ の距離 $=r$ の条件を整理すると '
      + '$(h-r^2)^2 = r^2(4p^2+1)$ が得られ，内心は放物線の上側を取ると軌跡が確定．'
      + '(2) ヘロン+$r=\\sqrt{2}/2$ から $2(s-a)(s-b)(s-c)=s$．$x=s-a,y=s-b,z=s-c$ と置いて '
      + '$2xyz=x+y+z$，$x\\le y\\le z$ として上界 $x\\le \\sqrt{3/2}$ より $x=1$，$(2y-1)(2z-1)=3$で一意確定．',
    solution:
      '(1) 放物線上の 3 点を $P(p+\\alpha),P(p+\\beta),P(p+\\gamma)$ とし，弦の直線式は '
      + '$y=(2p+\\alpha+\\beta)x-(p+\\alpha)(p+\\beta)$．内心 $I=(p,p^2+h)$ との距離 $=r$ の条件を '
      + '3 辺について立てて引き算すると $(h+\\alpha\\beta)^2=r^2\\{1+(2p+\\alpha+\\beta)^2\\}$ 等が得られ，'
      + '辺を 2 枚引いて整理すると $h=r^2\\pm r\\sqrt{4p^2+1}$（正号を採用）．'
      + '(2) 整数三角形条件 + $2xyz=x+y+z$：半整数仮定は奇偶矛盾，$x\\le y\\le z$ として '
      + '$2\\le3/x^2$ より $x=1$，$2yz=y+z+1\\Rightarrow(2y-1)(2z-1)=3\\Rightarrow y=1,z=2$，三辺 $2,3,3$．',
  },

  // ──────────────────────────────────────────────────────────────────────────
  {
    id:         'fibonacci_pi_001',
    topic_a:    'trigonometry',
    topic_b:    'recurrence',
    difficulty: 'A',
    generation: 0,
    total:      9.0,
    surprise:   9.0,
    minimality: 9.0,
    connection: 9.5,
    inevitability: 8.5,
    diff_cal:   9.0,
    statement:
      '$z_n = n + i$（$n$：正の整数）として，$1 \\le j_1 \\le j_2 \\le \\cdots \\le j_m \\le n$ に対して '
      + '$\\tan(\\arg z_{j_1} + \\arg z_{j_2} + \\cdots + \\arg z_{j_m}) = 1$'
      + ' を満たす数列 $\\{j_k\\}$ の条件を求め，それを用いて $3.141 < \\pi < 3.142$ を示せ．',
    answer:
      '(1) $(j_1,\\ldots,j_m) = (F_3,F_5,\\ldots,F_{2m-1},F_{2m})$（$F_k$：フィボナッチ数列 $F_1=1,F_2=1,\\ldots$）．'
      + '\\quad (2) $n=55$ で $(j_k)=(2,5,13,34,55)$ とし，$\\frac{\\pi}{4}=\\arctan\\frac{1}{2}+\\arctan\\frac{1}{5}+\\arctan\\frac{1}{13}+\\arctan\\frac{1}{34}+\\arctan\\frac{1}{55}$ を多項式不等式で挟み $3.141<\\pi<3.142$．',
    inspiration:
      '$\\arg z_n = \\arctan(1/n)$．フィボナッチ加法定理 '
      + '$\\arctan(1/F_k)+\\arctan(1/F_{k+1})=\\arctan(1/F_{k-1})$（$k$ 奇数, $\\tan$ 加法定理で確認）'
      + 'から帰納的に $\\pi/4=\\arctan(1/F_3)+\\arctan(1/F_5)+\\cdots$ と分解可能．'
      + '$\\arctan x$ の積分評価 $x-x^3/3\\le\\arctan x\\le x-x^3/3+x^5/5$ で各項を数値挟み撃ち．'
      + '$x=1/2$ だけは項を多く取り精度を上げる（$L = 3290137/7096320$ まで展開）．',
    solution:
      '(1) $\\arg z_n=\\arctan(1/n)$，$\\tan(\\text{和})=1\\Leftrightarrow$ 和 $=\\pi/4$．'
      + 'フィボナッチ加法定理 $(*)$：$F_{2r}$ への適用を繰り返し $\\pi/4 = \\sum_{k=1}^{m-1}\\arctan(1/F_{2k+1})+\\arctan(1/F_{2m})$．'
      + '(2) $n=55(=F_{10})$：$(j_k)=(2,5,13,34,55)$．'
      + '下界：各 $\\arctan x > x-x^3/3$ を数値計算 $\\Rightarrow \\pi/4>78525/100000=3141/4000$．'
      + '上界：各 $\\arctan x < x-x^3/3+x^5/5$（$x=1/2$ は多項式 12 次まで）$\\Rightarrow \\pi/4<78546/100000$．',
  },

  // ──────────────────────────────────────────────────────────────────────────
  {
    id:         'cos2pi7_001',
    topic_a:    'trigonometry',
    topic_b:    'polynomial',
    difficulty: 'B',
    generation: 0,
    total:      8.5,
    surprise:   8.5,
    minimality: 8.5,
    connection: 9.0,
    inevitability: 8.0,
    diff_cal:   8.5,
    statement:
      '(1) $\\dfrac{1}{1-\\cos\\dfrac{2\\pi}{7}}$ を有理化せよ（分母から $\\cos$ を消去した形で答えよ）．'
      + '\\quad (2) $\\cos\\dfrac{2\\pi}{7}$ を小数第 2 位まで求め，その値であることを証明せよ．',
    answer:
      '(1) $\\dfrac{4}{7}\\!\\left(2\\cos^2\\dfrac{2\\pi}{7}+3\\cos\\dfrac{2\\pi}{7}+2\\right)$．'
      + '\\quad (2) $\\cos\\dfrac{2\\pi}{7} = 0.62$（$0.62 < \\cos\\dfrac{2\\pi}{7} < 0.63$）．',
    inspiration:
      '$x=\\cos\\frac{2\\pi}{7}$は $\\zeta=e^{2\\pi i/7}$ の最小多項式の議論から $8x^3+4x^2-4x-1=0$ を満たす．'
      + '$S=1/(1-x)$ と置き，方程式に $S$ を乗じて整理すると $7S = 4(2x^2+3x+2)$（有理化完了）．'
      + '(2) は $F(t)=1-7/(4(2t^2+3t+2))$ の不動点反復を $I_0=[1/2,3/4]$ で行う．'
      + '$F$ の Lipschitz 定数 $\\le 21/32 < 1$ から収束が保証され，数ステップで $0.62<x<0.63$ を確認．',
    solution:
      '(1) $\\zeta=e^{2\\pi i/7}$，$1+\\zeta+\\cdots+\\zeta^6=0$ から '
      + '$(\\zeta+\\zeta^{-1})+(\\zeta^2+\\zeta^{-2})+(\\zeta^3+\\zeta^{-3})=-1$，'
      + '$\\zeta^k+\\zeta^{-k}=2\\cos\\frac{2\\pi k}{7}$ を代入して $8x^3+4x^2-4x-1=0$．'
      + '$S=1/(1-x)$ を乗じて $0=(8x^3S+4x^2S-4xS-S)$，$x^kS=S-1-x-\\cdots-x^{k-1}$ を代入 $\\Rightarrow 7S=4(2x^2+3x+2)$．'
      + '(2) 不動点反復 $a_0=1/2,b_0=3/4$，$a_{n+1}=F(a_n),b_{n+1}=F(b_n)$，'
      + '$\\alpha\\in[a_n,b_n]$ を保ちながら幅 $(21/32)^n/4\\to0$．'
      + '数ステップ後 $47/79<\\alpha<11/17$，さらに押し込んで $0.62<\\alpha<0.63$．',
  },
]

async function upsertProblem(p) {
  // problems テーブル upsert
  const res = await fetch(`${SUPABASE_URL}/rest/v1/problems`, {
    method:  'POST',
    headers: {
      'Content-Type':  'application/json',
      'apikey':        SERVICE_KEY,
      'Authorization': `Bearer ${SERVICE_KEY}`,
      'Prefer':        'resolution=merge-duplicates',
    },
    body: JSON.stringify({
      id:           p.id,
      topic_a:      p.topic_a,
      topic_b:      p.topic_b,
      difficulty:   p.difficulty,
      generation:   p.generation,
      total:        p.total,
      surprise:     p.surprise,
      minimality:   p.minimality,
      connection:   p.connection,
      inevitability: p.inevitability,
      diff_cal:     p.diff_cal,
      statement:    p.statement,
      answer:       p.answer,
      inspiration:  p.inspiration,
      solution:     p.solution,
      variation:    0,
      parent_ids:   JSON.stringify([]),
      source_file:  'onedrive_manual',
    }),
  })

  if (!res.ok) {
    const txt = await res.text()
    console.error(`  ❌ problems upsert failed (${res.status}): ${txt.slice(0, 200)}`)
    return false
  }

  // ratings テーブル upsert（selected 状態で登録）
  const res2 = await fetch(`${SUPABASE_URL}/rest/v1/ratings`, {
    method:  'POST',
    headers: {
      'Content-Type':  'application/json',
      'apikey':        SERVICE_KEY,
      'Authorization': `Bearer ${SERVICE_KEY}`,
      'Prefer':        'resolution=merge-duplicates',
    },
    body: JSON.stringify({
      problem_id: p.id,
      status:     'selected',
      x_posted:   false,
    }),
  })

  if (!res2.ok) {
    const txt = await res2.text()
    console.error(`  ⚠️ ratings upsert failed (${res2.status}): ${txt.slice(0, 200)}`)
  }

  return true
}

;(async () => {
  console.log('\n🚀 Supabase へ 5 問を投入中...\n')
  for (const p of problems) {
    process.stdout.write(`  • ${p.id} (${p.topic_a}×${p.topic_b}) ... `)
    const ok = await upsertProblem(p)
    console.log(ok ? '✅' : '❌')
  }
  console.log('\n✨ 完了！')
})()
