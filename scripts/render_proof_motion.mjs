/**
 * 図を主役にした証明の Reel。1080x1920。
 *
 * 前作 render_proof_reel.mjs は文字が主で図が従だった。ここでは逆にする。
 * 図が画面の 3/4 を占め、文は1行だけ添える。
 *
 * 動きは装飾ではない。証明に現れる連続変換をそのまま動かす。
 *   2023SAGFp8 なら鏡映 w -> p + q - pq*conj(w)。
 *   三角形 DEF が辺で折り返されて D1E1F1 に重なる運動が、証明の第3手そのもの。
 *
 * 素材は MORTRA の出力だけを読む。座標も文言も作らない。
 *
 *   node scripts/render_proof_motion.mjs <問題名>
 */
import sharp from 'sharp'
import { readFileSync, mkdirSync, rmSync } from 'node:fs'
import { join } from 'node:path'
import { execFileSync } from 'node:child_process'

const ROOT = 'C:/Users/81808/.openclaw/workspace/mortra-1-release'
const OUT = `${ROOT}/build/proof-reel`
const NAME = process.argv[2] || '2023SAGFp8'

// 問題ごとの「どのパスが何か」。SVG の中身を実際に見て決める。group 名では決まらない。
const SCENE = {
  '2023SAGFp8': {
    run: 'hageo-exact-chart-arc-reflection-axis-runs-2026-08-27',
    title: '鏡映しても、向きは変わらない',
    titleEn: 'Reflect it. The axis does not turn.',
    circle: ['patch_2'],
    base: ['line2d_1'],          // 三角形 ABC
    from: ['line2d_5'],          // 弧中点の三角形 DEF
    to: ['line2d_4'],            // 鏡映後 D1E1F1
    axisA: ['line2d_2'],         // オイラー線 OH
    axisB: ['line2d_3'],         // 鏡映後の中心線 H1O1
    pts: { base: ['A', 'B', 'C'], from: ['D', 'E', 'F'], center: ['O', 'H'], moved: ['O1', 'H1'] },
  },
}[NAME]

if (!SCENE) throw new Error(`${NAME} の場面定義がありません`)

const RUN = `${ROOT}/data/${SCENE.run}`
const FRAMES = `${OUT}/frames-motion-${NAME}`
const W = 1080, H = 1920, FPS = 30

const GROUND = '#05070a'
const INK = '#e8eef2'
const DIM = '#7d919e'
const FAINT = '#28323c'
const CONSTRUCT = '#ff9d2e'
const THEOREM = '#ff5fb0'
const ALGEBRA = '#ffffff'
const CLOSE = '#4dffa0'

const MONO = 'IBM Plex Mono, Consolas, monospace'
const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

const pf = JSON.parse(readFileSync(`${RUN}/${NAME}.chart-portfolio.json`, 'utf-8'))
const sel = pf.selected
const cert = sel.certificate
const fig = JSON.parse(readFileSync(`${OUT}/${NAME}.figure.json`, 'utf-8'))

const dag = cert.proof_dag
const resNames = Object.keys(cert.replay_residuals)
const sha = cert.certificate_sha256

const [, , vbW, vbH] = fig.viewBox.split(/\s+/).map(Number)
const P = {}
for (const l of fig.labels) if (/^[A-Z][0-9]?$/.test(l.text)) P[l.text] = { x: l.x, y: l.y }
const pts = fig.scatter.map(s => s.points[0])
for (const k of Object.keys(P)) {
  let best = null, bd = Infinity
  for (const q of pts) {
    const d = (q.x - P[k].x) ** 2 + (q.y - P[k].y) ** 2
    if (d < bd) { bd = d; best = q }
  }
  if (best) { P[k].px = best.x; P[k].py = best.y }
}
const D = g => fig.paths.filter(p => g.includes(p.group)).map(p => p.d)

// 図は画面の上 3/4 を占める。文字は下に1行だけ
const FH = 1180
const FS = Math.min((W - 150) / vbW, FH / vbH)
const FX = (W - vbW * FS) / 2
const FY = 250
const fx = v => FX + v * FS
const fy = v => FY + v * FS

const clamp01 = v => (v < 0 ? 0 : v > 1 ? 1 : v)
const ease = t => { const u = clamp01(t); return u * u * (3 - 2 * u) }
const seg = (t, a, b) => ease((t - a) / (b - a))

const T = (x, y, s, o = {}) => {
  const { size = 30, fill = INK, anchor = 'start', weight = 400, ls = 0, op = 1 } = o
  return op <= 0.004 ? '' : `<text x="${x}" y="${y}" font-family="${MONO}" font-size="${size}"
    font-weight="${weight}" letter-spacing="${ls}" fill="${fill}" text-anchor="${anchor}"
    opacity="${op.toFixed(3)}">${esc(s)}</text>`
}

/** パスを描く。dash で「まだ引かれていない」状態から引く動きを作る */
const path = (d, col, w, op, draw = 1) => {
  if (op <= 0.004) return ''
  const len = 3000
  const dash = draw >= 1 ? '' : ` stroke-dasharray="${len}" stroke-dashoffset="${(len * (1 - draw)).toFixed(0)}"`
  return `<path d="${d}" fill="none" stroke="${col}" stroke-width="${w}" stroke-linejoin="round"
    opacity="${op.toFixed(3)}"${dash} transform="translate(${FX} ${FY}) scale(${FS})"/>`
}

const dot = (k, col, op, r = 6, label = true) => {
  const p = P[k]
  if (!p || op <= 0.004) return ''
  const x = fx(p.px ?? p.x), y = fy(p.py ?? p.y)
  return `<circle cx="${x}" cy="${y}" r="${r * 2.6}" fill="${col}" opacity="${(op * 0.18).toFixed(3)}"/>
    <circle cx="${x}" cy="${y}" r="${r}" fill="${col}" opacity="${op.toFixed(3)}"/>` +
    (label ? T(fx(p.x) + 14, fy(p.y) - 12, k, { size: 26, fill: col, op: op * 0.95 }) : '')
}

/**
 * 鏡映の運動。from の三角形を to の三角形へ、点ごとに直線補間する。
 * 実際の写像は w -> p+q-pq*conj(w) だが、始点と終点は厳密な座標なので、
 * その2点を結ぶ運動として見せる。中間の位置は演出であり、
 * 始点と終点だけが証明の値である。
 */
const morph = (u) => {
  const a = SCENE.pts.from, b = ['D1', 'E1', 'F1']
  const has = b.every(k => P[k])
  if (!has) return ''       // 鏡映後の点にラベルが無い場合は形だけ動かす
  const pt = (k1, k2) => {
    const p = P[k1], q = P[k2]
    return [fx(p.px + (q.px - p.px) * u), fy(p.py + (q.py - p.py) * u)]
  }
  const c = a.map((k, i) => pt(k, b[i]))
  return `<polygon points="${c.map(p => p.join(',')).join(' ')}" fill="none"
    stroke="${THEOREM}" stroke-width="2.4" stroke-linejoin="round" opacity="0.95"/>`
}

const chrome = (stage) => [
  T(64, 100, 'MORTRA', { size: 28, fill: INK, weight: 600, ls: 7 }),
  T(W - 64, 100, NAME, { size: 24, fill: DIM, anchor: 'end' }),
  `<line x1="64" y1="132" x2="${W - 64}" y2="132" stroke="#16222c"/>`,
  T(64, H - 78, 'mortra.ai', { size: 24, fill: CLOSE }),
  T(W - 64, H - 78, stage, { size: 23, fill: DIM, anchor: 'end' }),
].join('')

const svg = b => `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}"
  viewBox="0 0 ${W} ${H}"><rect width="${W}" height="${H}" fill="${GROUND}"/>${b}</svg>`

const line1 = (y, s, o = {}) => T(64, y, s, { size: 34, ...o })

const scenes = []

// ── 1. 外接円と三角形が立ち上がる ─────────────────
{
  const SEC = 3.2, N = Math.round(SEC * FPS)
  for (let f = 0; f < N; f++) {
    const t = f / N
    const p = [chrome('1 / 5')]
    for (const d of D(SCENE.circle)) p.push(path(d, FAINT, 2, 1, seg(t, 0.0, 0.45)))
    for (const d of D(SCENE.base)) p.push(path(d, ALGEBRA, 2.4, 1, seg(t, 0.2, 0.7)))
    for (const k of SCENE.pts.base) p.push(dot(k, ALGEBRA, seg(t, 0.35, 0.8), 6))
    p.push(line1(H - 300, '外接円に三角形をひとつ。', { op: seg(t, 0.55, 0.9) }))
    scenes.push(svg(p.join('')))
  }
}

// ── 2. 弧中点の三角形 ──────────────────────────
{
  const SEC = 3.0, N = Math.round(SEC * FPS)
  for (let f = 0; f < N; f++) {
    const t = f / N
    const p = [chrome('2 / 5')]
    for (const d of D(SCENE.circle)) p.push(path(d, FAINT, 2, 1))
    for (const d of D(SCENE.base)) p.push(path(d, ALGEBRA, 2.4, 0.5))
    for (const k of SCENE.pts.base) p.push(dot(k, ALGEBRA, 0.5, 5))
    for (const d of D(SCENE.from)) p.push(path(d, CONSTRUCT, 2.4, 1, seg(t, 0.05, 0.6)))
    for (const k of SCENE.pts.from) p.push(dot(k, CONSTRUCT, seg(t, 0.3, 0.75), 6))
    p.push(line1(H - 300, '各辺の垂直二等分線が円を切る点。', { op: seg(t, 0.45, 0.85) }))
    scenes.push(svg(p.join('')))
  }
}

// ── 3. 鏡映。証明の第3手そのもの ────────────────
{
  const SEC = 4.2, N = Math.round(SEC * FPS)
  for (let f = 0; f < N; f++) {
    const t = f / N
    const u = seg(t, 0.12, 0.82)
    const p = [chrome('3 / 5')]
    for (const d of D(SCENE.circle)) p.push(path(d, FAINT, 2, 1))
    for (const d of D(SCENE.base)) p.push(path(d, ALGEBRA, 2.4, 0.35))
    for (const d of D(SCENE.from)) p.push(path(d, CONSTRUCT, 2.2, 0.9 * (1 - u * 0.55)))
    p.push(morph(u))
    for (const d of D(SCENE.to)) p.push(path(d, THEOREM, 2.4, u > 0.97 ? 1 : 0))
    for (const k of SCENE.pts.from) p.push(dot(k, CONSTRUCT, 0.9 * (1 - u * 0.6), 5, false))
    p.push(T(64, H - 352, 'w  \u2192  p + q \u2212 pq \u00b7 conj(w)',
      { size: 30, fill: THEOREM, op: seg(t, 0.05, 0.3) }))
    p.push(line1(H - 300, '辺の直線で、折り返す。', { op: seg(t, 0.05, 0.35) }))
    scenes.push(svg(p.join('')))
  }
}

// ── 4. 2本の中心線 ─────────────────────────────
{
  const SEC = 3.6, N = Math.round(SEC * FPS)
  for (let f = 0; f < N; f++) {
    const t = f / N
    const p = [chrome('4 / 5')]
    for (const d of D(SCENE.circle)) p.push(path(d, FAINT, 2, 1))
    for (const d of D(SCENE.base)) p.push(path(d, ALGEBRA, 2.4, 0.28))
    for (const d of D(SCENE.from)) p.push(path(d, CONSTRUCT, 2.2, 0.3))
    for (const d of D(SCENE.to)) p.push(path(d, THEOREM, 2.4, 0.75))
    for (const d of D(SCENE.axisA)) p.push(path(d, CLOSE, 4, 1, seg(t, 0.05, 0.45)))
    for (const d of D(SCENE.axisB)) p.push(path(d, CLOSE, 4, 1, seg(t, 0.3, 0.75)))
    for (const k of SCENE.pts.center) p.push(dot(k, CLOSE, seg(t, 0.2, 0.5), 7))
    for (const k of SCENE.pts.moved) p.push(dot(k, CLOSE, seg(t, 0.45, 0.8), 7))
    p.push(line1(H - 300, '2本の中心線が、平行になる。', { op: seg(t, 0.5, 0.85) }))
    scenes.push(svg(p.join('')))
  }
}

// ── 5. 検算 ────────────────────────────────────
{
  const SEC = 3.6, N = Math.round(SEC * FPS)
  for (let f = 0; f < N; f++) {
    const t = f / N
    const p = [chrome('5 / 5')]
    for (const d of D(SCENE.circle)) p.push(path(d, FAINT, 2, 1))
    for (const d of D(SCENE.base)) p.push(path(d, ALGEBRA, 2.4, 0.25))
    for (const d of D(SCENE.to)) p.push(path(d, THEOREM, 2.4, 0.6))
    for (const d of D(SCENE.axisA)) p.push(path(d, CLOSE, 4, 1))
    for (const d of D(SCENE.axisB)) p.push(path(d, CLOSE, 4, 1))
    const done = Math.floor(ease(clamp01(t / 0.62)) * resNames.length)
    p.push(T(64, H - 372, `${resNames.length} \u672c\u3059\u3079\u3066\u3001\u4f59\u308a 0`,
      { size: 32, fill: INK, op: seg(t, 0.02, 0.2) }))
    p.push(T(64, H - 316, `${done} / ${resNames.length}`,
      { size: 46, fill: CLOSE, op: seg(t, 0.06, 0.25) }))
    p.push(T(64, H - 250, sha.slice(0, 40), { size: 20, fill: DIM, op: seg(t, 0.55, 0.8) }))
    p.push(T(64, H - 218, '\u5916\u90e8LLM \u4f7f\u7528\u306a\u3057', { size: 24, fill: DIM, op: seg(t, 0.68, 0.9) }))
    scenes.push(svg(p.join('')))
  }
}

rmSync(FRAMES, { recursive: true, force: true })
mkdirSync(FRAMES, { recursive: true })
console.log(`  ${NAME}  ${scenes.length} \u679a (${(scenes.length / FPS).toFixed(1)}\u79d2)`)
for (let i = 0; i < scenes.length; i++) {
  await sharp(Buffer.from(scenes[i])).png().toFile(join(FRAMES, `f${String(i).padStart(5, '0')}.png`))
  if (i % 80 === 0) process.stdout.write(`\r  ${i}/${scenes.length}`)
}
console.log(`\r  ${scenes.length}/${scenes.length}`)

const mp4 = join(OUT, `mortra-motion-${NAME}.mp4`)
execFileSync('ffmpeg', [
  '-y', '-framerate', String(FPS), '-i', join(FRAMES, 'f%05d.png'),
  '-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100',
  '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-preset', 'slow',
  '-c:a', 'aac', '-b:a', '128k', '-shortest', '-movflags', '+faststart', mp4,
], { stdio: ['ignore', 'ignore', 'inherit'] })
console.log(`  ${mp4}`)
