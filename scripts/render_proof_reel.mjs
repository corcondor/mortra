/**
 * 証明1段 = 図1段 = 文1段。実物の証明成果物から Reel を書き出す。
 *
 * 題材は IMO 2011 Shortlist G3。
 * 出典 https://www.imo-official.org/problems/IMO2011SL.pdf
 *
 * 素材はすべて MORTRA が実際に出力したものから読む。
 *   - 証明の手順   certificate.proof_dag
 *   - 表現の移動   certificate.representation_chart
 *   - 恒等式と残差 certificate.replay_residuals
 *   - 証明書       certificate.certificate_sha256
 *   - 図の実座標   proof-focus.svg から extract_proof_figure.py で抽出したもの
 * このスクリプトの中で数式も文言も座標も作らない。読んで並べるだけ。
 *
 *   python scripts/extract_proof_figure.py <svg> build/proof-reel/2011G3.figure.json
 *   node   scripts/render_proof_reel.mjs
 */
import sharp from 'sharp'
import { readFileSync, mkdirSync, rmSync } from 'node:fs'
import { join } from 'node:path'
import { execFileSync } from 'node:child_process'

const ROOT = 'C:/Users/81808/.openclaw/workspace/mortra-1-release'
const RUN = `${ROOT}/data/hageo-exact-chart-two-diameter-pedal-runs-2026-08-26`
const NAME = '2011G3'
const OUT = `${ROOT}/build/proof-reel`
const FIG = `${OUT}/${NAME}.figure.json`

// 言語は引数で切り替える。証明の本文（proof_dag / representation_chart）は
// MORTRA の出力そのものなので、どちらの版でも原文の英語のまま出す。
// 訳すと「実物をそのまま見せている」という性質が消えるため。
const LANG = (process.argv[2] === 'en') ? 'en' : 'ja'
const FRAMES = `${OUT}/frames-${LANG}`

const L = {
  ja: {
    stageSubject: '題材', stageProof: n => `証明 ${n}`, stageReplay: '厳密再生', stageCert: '証明書',
    theorem: '定理', goal: '目標',
    allZero: n => `${n} 本すべて、余り 0`,
    reproducible: '誰でも、同じものを再生できる。',
    rows: [['外部LLM', '使用なし'], ['期待解答', '使用なし'], ['問題IDによる分岐', 'なし']],
    source: 'IMO 2011 Shortlist G3',
  },
  en: {
    stageSubject: 'Problem', stageProof: n => `Proof ${n}`, stageReplay: 'Exact replay', stageCert: 'Certificate',
    theorem: 'Theorem', goal: 'Goal',
    allZero: n => `${n} identities, every remainder 0`,
    reproducible: 'Anyone can replay the same proof.',
    rows: [['External LLM', 'none'], ['Expected answer', 'none'], ['Branch on problem ID', 'none']],
    source: 'IMO 2011 Shortlist G3',
  },
}[LANG]

const W = 1080, H = 1920, FPS = 30

const GROUND = '#05070a'
const INK = '#e8eef2'
const DIM = '#7d919e'
const FAINT = '#2b3742'
const CONSTRUCT = '#ff9d2e'
const THEOREM = '#ff5fb0'
const ALGEBRA = '#ffffff'
const CLOSE = '#4dffa0'
const NUMERIC = '#4fc3ff'

const MONO = 'IBM Plex Mono, Consolas, monospace'
const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

// ── 実物を読む ────────────────────────────────
const pf = JSON.parse(readFileSync(`${RUN}/${NAME}.chart-portfolio.json`, 'utf-8'))
const sel = pf.selected
const cert = sel.certificate
const md = readFileSync(`${RUN}/${NAME}.proof.md`, 'utf-8')
const fig = JSON.parse(readFileSync(FIG, 'utf-8'))

const theorem = (md.match(/## Theorem\s*\n\s*([\s\S]*?)\n\s*##/) || [])[1]
  ?.split('\n').map(s => s.trim()).filter(Boolean).join(' ') || ''
const dag = cert.proof_dag
const repChart = cert.representation_chart
const residuals = cert.replay_residuals
const resNames = Object.keys(residuals)
const sha = cert.certificate_sha256

console.log(`  証明 ${dag.length}手 / 表現移動 ${repChart.length}本 / 恒等式 ${resNames.length}本`)

// ── 図。抽出した実座標をそのまま使う ──────────────
const [, , vbW, vbH] = fig.viewBox.split(/\s+/).map(Number)
const P = {}
for (const l of fig.labels) {
  if (/^[A-Z][0-9]?$/.test(l.text)) P[l.text] = { x: l.x, y: l.y }
}
// ラベルは点から少しずれた位置に置かれるので、散布点の実座標へ寄せ直す
const pts = fig.scatter.map(s => s.points[0])
for (const key of Object.keys(P)) {
  let best = null, bd = Infinity
  for (const q of pts) {
    const d = (q.x - P[key].x) ** 2 + (q.y - P[key].y) ** 2
    if (d < bd) { bd = d; best = q }
  }
  if (best) { P[key].px = best.x; P[key].py = best.y }
}
const circleD = fig.paths.filter(p => p.group === 'patch_2' || p.group === 'patch_3').map(p => p.d)
const lineD = fig.paths.filter(p => p.group.startsWith('line2d_')).map(p => p.d)

// 図の描画枠。画面の上半分
const FX = 70, FY = 210, FW = W - 140
const FS = FW / vbW
const fx = v => FX + v * FS
const fy = v => FY + v * FS
const FH = vbH * FS

const clamp01 = v => (v < 0 ? 0 : v > 1 ? 1 : v)
const ease = t => { const u = clamp01(t); return u * u * (3 - 2 * u) }

const T = (x, y, s, { size = 30, fill = INK, anchor = 'start', weight = 400, ls = 0, op = 1 } = {}) =>
  op <= 0.004 ? '' : `<text x="${x}" y="${y}" font-family="${MONO}" font-size="${size}" font-weight="${weight}"
     letter-spacing="${ls}" fill="${fill}" text-anchor="${anchor}" opacity="${op.toFixed(3)}">${esc(s)}</text>`

const wrap = (s, cols) => {
  const words = String(s).split(' ')
  const out = []
  let cur = ''
  for (const w of words) {
    if ((cur + ' ' + w).trim().length > cols) { out.push(cur.trim()); cur = w }
    else cur = (cur + ' ' + w).trim()
  }
  if (cur) out.push(cur)
  return out
}

const seg = (x1, y1, x2, y2, col, op, w = 1.6) =>
  op <= 0.004 ? '' : `<line x1="${fx(x1)}" y1="${fy(y1)}" x2="${fx(x2)}" y2="${fy(y2)}"
    stroke="${col}" stroke-width="${w}" stroke-linecap="round" opacity="${op.toFixed(3)}"/>`

const dot = (k, col, op, r = 5, label = true) => {
  const p = P[k]
  if (!p || op <= 0.004) return ''
  const x = fx(p.px ?? p.x), y = fy(p.py ?? p.y)
  return `<circle cx="${x}" cy="${y}" r="${r * 2.4}" fill="${col}" opacity="${(op * 0.2).toFixed(3)}"/>
    <circle cx="${x}" cy="${y}" r="${r}" fill="${col}" opacity="${op.toFixed(3)}"/>` +
    (label ? T(fx(p.x) + 12, fy(p.y) - 10, k, { size: 24, fill: col, op }) : '')
}

const pathOf = (d, col, op, w = 1.5) =>
  op <= 0.004 ? '' : `<path d="${d}" fill="none" stroke="${col}" stroke-width="${w}"
    opacity="${op.toFixed(3)}" transform="translate(${FX} ${FY}) scale(${FS})"/>`

/**
 * 証明の第 i 手までを図にする。0 は初期構成。
 * 各手が図のどの要素を足すかは proof_dag の記述に対応させる。
 */
function figure(step, sub) {
  const g = []
  const s = k => ease(clamp01(step - k + sub))

  // 初期構成 ABCD と、2円の共有点 E,F
  const base = s(0)
  g.push(seg(P.A?.px, P.A?.py, P.B?.px, P.B?.py, FAINT, base, 1.2))
  g.push(seg(P.B?.px, P.B?.py, P.C?.px, P.C?.py, FAINT, base, 1.2))
  g.push(seg(P.C?.px, P.C?.py, P.D?.px, P.D?.py, FAINT, base, 1.2))
  g.push(seg(P.D?.px, P.D?.py, P.A?.px, P.A?.py, FAINT, base, 1.2))
  for (const k of ['A', 'B', 'C', 'D']) g.push(dot(k, DIM, base, 4))
  g.push(dot('E', CONSTRUCT, base, 5))
  g.push(dot('F', CONSTRUCT, base, 5))

  // 1手目 omega_E、2手目 omega_F
  if (circleD[0]) g.push(pathOf(circleD[0], THEOREM, s(1), 1.6))
  if (circleD[1]) g.push(pathOf(circleD[1], THEOREM, s(2), 1.6))

  // 3〜5手目 E と F を結ぶ弦と、その中点 M
  g.push(seg(P.E?.px, P.E?.py, P.F?.px, P.F?.py, ALGEBRA, s(4), 1.8))
  g.push(dot('M', ALGEBRA, s(5), 6))

  // 6手目 2円の共有点 K1,K2 と根軸
  g.push(dot('K1', CLOSE, s(6), 5))
  g.push(dot('K2', CLOSE, s(6), 5))
  for (const d of lineD) g.push(pathOf(d, CLOSE, s(7), 2))

  return g.join('')
}

function chrome(stage, right) {
  return [
    T(64, 92, 'MORTRA', { size: 26, fill: INK, weight: 600, ls: 6 }),
    T(W - 64, 92, right, { size: 23, fill: NUMERIC, anchor: 'end' }),
    `<line x1="64" y1="120" x2="${W - 64}" y2="120" stroke="#16222c"/>`,
    T(64, H - 132, L.source, { size: 23, fill: DIM }),
    T(64, H - 96, 'imo-official.org / IMO2011SL.pdf', { size: 21, fill: FAINT }),
    T(W - 64, H - 96, stage, { size: 22, fill: DIM, anchor: 'end' }),
  ].join('')
}

const svg = body => `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}"
  viewBox="0 0 ${W} ${H}"><rect width="${W}" height="${H}" fill="${GROUND}"/>${body}</svg>`

const scenes = []

// ── 1. 定理 ────────────────────────────────
{
  const SEC = 5.0, F0 = Math.round(SEC * FPS)
  const lines = wrap(theorem, 42)
  for (let f = 0; f < F0; f++) {
    const t = f / F0
    const parts = [chrome(L.stageSubject, NAME)]
    parts.push(figure(0, ease(clamp01(t / 0.35))))
    let y = FY + FH + 110
    parts.push(T(64, y, L.theorem, { size: 24, fill: DIM, ls: 3 })); y += 58
    const shown = ease(clamp01((t - 0.18) / 0.6)) * lines.length
    lines.forEach((ln, i) => {
      parts.push(T(64, y + i * 42, ln, { size: 28, fill: INK, op: clamp01(shown - i) }))
    })
    y += lines.length * 42 + 40
    parts.push(T(64, y, L.goal, { size: 24, fill: DIM, op: ease(clamp01((t - 0.8) / 0.15)) }))
    parts.push(T(180, y, sel.goal, { size: 30, fill: THEOREM, weight: 600, op: ease(clamp01((t - 0.8) / 0.15)) }))
    scenes.push(svg(parts.join('')))
  }
}

// ── 2. 証明の各手。1手ごとに図が1段進む ──────────
for (let i = 0; i < dag.length; i++) {
  const SEC = 2.9, F1 = Math.round(SEC * FPS)
  const stepLines = wrap(dag[i], 40)
  const rep = repChart[i] ? String(repChart[i]).split('->').map(s => s.trim()) : null
  for (let f = 0; f < F1; f++) {
    const t = f / F1
    const parts = [chrome(L.stageProof(`${i + 1} / ${dag.length}`), NAME)]
    parts.push(figure(i + 1, ease(clamp01(t / 0.5))))

    let y = FY + FH + 110
    parts.push(T(64, y, String(i + 1).padStart(2, '0'), { size: 26, fill: NUMERIC, ls: 2 }))
    stepLines.forEach((ln, j) => parts.push(T(132, y + j * 40, ln, { size: 28, fill: INK })))
    y += stepLines.length * 40 + 56

    if (rep) {
      const op = ease(clamp01((t - 0.3) / 0.3))
      parts.push(`<line x1="64" y1="${y - 26}" x2="${W - 64}" y2="${y - 26}" stroke="#16222c" opacity="${op}"/>`)
      wrap(rep[0], 38).forEach((ln, j) => parts.push(T(64, y + 22 + j * 34, ln, { size: 25, fill: CONSTRUCT, op })))
      const h = wrap(rep[0], 38).length * 34
      parts.push(T(64, y + 58 + h, '\u2193', { size: 24, fill: FAINT, op }))
      wrap(rep[1], 38).forEach((ln, j) => parts.push(T(64, y + 100 + h + j * 34, ln, { size: 25, fill: CLOSE, op })))
    }
    scenes.push(svg(parts.join('')))
  }
}

// ── 3. 恒等式が余り0で閉じる ──────────────────
{
  const SEC = 5.4, F2 = Math.round(SEC * FPS)
  for (let f = 0; f < F2; f++) {
    const t = f / F2
    const done = Math.floor(ease(clamp01(t / 0.78)) * resNames.length)
    const parts = [chrome(L.stageReplay, NAME)]
    parts.push(figure(dag.length, 1))
    let y = FY + FH + 104
    parts.push(T(64, y, L.allZero(resNames.length), { size: 32, fill: INK })); y += 56
    resNames.forEach((n, i) => {
      const on = i < done
      const yy = y + i * 38
      parts.push(T(64, yy, n.length > 34 ? n.slice(0, 33) + '\u2026' : n,
        { size: 22, fill: on ? DIM : FAINT }))
      parts.push(T(W - 64, yy, on ? '0' : '\u00b7',
        { size: 22, fill: on ? CLOSE : FAINT, anchor: 'end' }))
    })
    scenes.push(svg(parts.join('')))
  }
}

// ── 4. 証明書 ──────────────────────────────
{
  const SEC = 4.4, F3 = Math.round(SEC * FPS)
  for (let f = 0; f < F3; f++) {
    const t = f / F3
    const parts = [chrome(L.stageCert, NAME)]
    parts.push(figure(dag.length, 1))
    let y = FY + FH + 104
    parts.push(T(64, y, L.reproducible, { size: 32, fill: INK })); y += 76
    const op = ease(clamp01(t / 0.22))
    parts.push(T(64, y, sha.slice(0, 32), { size: 27, fill: CLOSE, op })); y += 42
    parts.push(T(64, y, sha.slice(32), { size: 27, fill: CLOSE, op })); y += 84

    const b = ease(clamp01((t - 0.3) / 0.24))
    const row = (k, v) => {
      parts.push(T(64, y, k, { size: 26, fill: DIM, op: b }))
      parts.push(T(W - 64, y, v, { size: 26, fill: INK, anchor: 'end', op: b }))
      parts.push(`<line x1="64" y1="${y + 22}" x2="${W - 64}" y2="${y + 22}" stroke="#16222c" opacity="${b}"/>`)
      y += 62
    }
    for (const [k, v] of L.rows) row(k, v)

    const e = ease(clamp01((t - 0.62) / 0.3))
    parts.push(T(64, y + 70, 'Finite primitives. Infinite mathematics.', { size: 29, fill: INK, op: e }))
    parts.push(T(64, y + 120, 'mortra.ai', { size: 28, fill: CLOSE, op: e }))
    scenes.push(svg(parts.join('')))
  }
}

// ── 書き出し ────────────────────────────────
rmSync(FRAMES, { recursive: true, force: true })
mkdirSync(FRAMES, { recursive: true })
console.log(`  フレーム ${scenes.length} 枚 (${(scenes.length / FPS).toFixed(1)}秒)`)
for (let i = 0; i < scenes.length; i++) {
  await sharp(Buffer.from(scenes[i])).png().toFile(join(FRAMES, `f${String(i).padStart(5, '0')}.png`))
  if (i % 60 === 0) process.stdout.write(`\r  ${i}/${scenes.length}`)
}
console.log(`\r  ${scenes.length}/${scenes.length}`)

// X は音声トラックが無いと変換に失敗するので無音AACを足す
const mp4 = join(OUT, `mortra-proof-${LANG}.mp4`)
execFileSync('ffmpeg', [
  '-y', '-framerate', String(FPS), '-i', join(FRAMES, 'f%05d.png'),
  '-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100',
  '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-preset', 'slow',
  '-c:a', 'aac', '-b:a', '128k', '-shortest', '-movflags', '+faststart', mp4,
], { stdio: ['ignore', 'ignore', 'inherit'] })
console.log(`  ${mp4}`)
