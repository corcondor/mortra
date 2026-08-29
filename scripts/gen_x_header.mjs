/**
 * X のヘッダー 1500x500。
 *
 * 素材は 2011G3 の証明成果物から読む。恒等式の名前も残差も、ここでは作らない。
 * 図の座標は extract_proof_figure.py が抽出したものをそのまま使う。
 *
 * X のヘッダーには重なりがある。
 *   - 左下にアイコンが重なる（およそ x<300, y>250 の円）
 *   - 上下は端末によって切られる。安全域は縦中央の 380px 程度
 * したがって主役は右側に置き、左下は空けておく。
 *
 *   node scripts/gen_x_header.mjs
 *   -> build/proof-reel/x-header.png
 */
import sharp from 'sharp'
import { readFileSync, mkdirSync } from 'node:fs'

const ROOT = 'C:/Users/81808/.openclaw/workspace/mortra-1-release'
const RUN = `${ROOT}/data/hageo-exact-chart-two-diameter-pedal-runs-2026-08-26`
const OUT = `${ROOT}/build/proof-reel`
const NAME = '2011G3'

const W = 1500, H = 500
const GROUND = '#05070a'
const INK = '#e8eef2'
const DIM = '#7d919e'
const FAINT = '#22303b'
const CONSTRUCT = '#ff9d2e'
const THEOREM = '#ff5fb0'
const ALGEBRA = '#ffffff'
const CLOSE = '#4dffa0'

const MONO = 'IBM Plex Mono, Consolas, monospace'
const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

const pf = JSON.parse(readFileSync(`${RUN}/${NAME}.chart-portfolio.json`, 'utf-8'))
const cert = pf.selected.certificate
const fig = JSON.parse(readFileSync(`${OUT}/${NAME}.figure.json`, 'utf-8'))
const resNames = Object.keys(cert.replay_residuals)

// 図の座標。ラベル位置は散布点へ寄せ直す
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
// path の中身を確認したうえで役割を割り当てる。group 名だけで決めない。
//   patch_1  枠。使わない
//   patch_2  ペダル円 omega_E
//   patch_3  ペダル円 omega_F
//   line2d_1 四角形 ABCD の輪郭。地の色で引く
//   line2d_2 K1 と K2 を結ぶ根軸。ここだけが結論の線なので緑
const circles = fig.paths.filter(p => p.group === 'patch_2' || p.group === 'patch_3').map(p => p.d)
const quad = fig.paths.filter(p => p.group === 'line2d_1').map(p => p.d)
const radical = fig.paths.filter(p => p.group === 'line2d_2').map(p => p.d)

// 図は右側に置く。左下はアイコンが重なるので使わない
const FH = 400
const FS = FH / vbH
const FX = W - vbW * FS - 90
const FY = (H - FH) / 2
const fx = v => FX + v * FS
const fy = v => FY + v * FS

const parts = [`<rect width="${W}" height="${H}" fill="${GROUND}"/>`]

// 背景に恒等式の名前を薄く敷く。実際に検算された15本。
// X はヘッダーを 450px 幅ほどに縮めて出すので、薄すぎると完全に消える。
// 読ませる文字ではなく「検算の列がそこにある」という手触りとして置く。
resNames.forEach((n, i) => {
  parts.push(`<text x="34" y="${36 + i * 30}" font-family="${MONO}" font-size="15"
    fill="${FAINT}">${esc(n)}</text>`)
  parts.push(`<text x="476" y="${36 + i * 30}" font-family="${MONO}" font-size="15"
    fill="${CLOSE}" opacity="0.42">0</text>`)
})

// 図
const line = (a, b, col, w) =>
  `<line x1="${fx(P[a].px)}" y1="${fy(P[a].py)}" x2="${fx(P[b].px)}" y2="${fy(P[b].py)}"
     stroke="${col}" stroke-width="${w}" stroke-linecap="round"/>`
const pathOf = (d, col, w, op = 1) =>
  `<path d="${d}" fill="none" stroke="${col}" stroke-width="${w}" opacity="${op}"
     transform="translate(${FX} ${FY}) scale(${FS})"/>`

for (const d of quad) parts.push(pathOf(d, '#33424f', 1.4))          // 四角形は地の色
for (const d of circles) parts.push(pathOf(d, THEOREM, 2.1))          // ペダル円
parts.push(line('E', 'F', ALGEBRA, 2))                                // 弦 EF
for (const d of radical) parts.push(pathOf(d, CLOSE, 2.6))            // 根軸。結論の線

const dot = (k, col, r) => {
  const p = P[k]
  return `<circle cx="${fx(p.px)}" cy="${fy(p.py)}" r="${r * 2.4}" fill="${col}" opacity="0.2"/>
    <circle cx="${fx(p.px)}" cy="${fy(p.py)}" r="${r}" fill="${col}"/>`
}
for (const k of ['A', 'B', 'C', 'D']) parts.push(dot(k, DIM, 3.5))
for (const k of ['E', 'F']) parts.push(dot(k, CONSTRUCT, 4.5))
for (const k of ['K1', 'K2']) parts.push(dot(k, CLOSE, 4.5))
parts.push(dot('M', ALGEBRA, 5))

// 文字は中央帯に置く。上下が切られても残る位置
parts.push(`<text x="34" y="${H / 2 - 14}" font-family="${MONO}" font-size="40" font-weight="600"
  letter-spacing="1" fill="${INK}">Finite primitives.</text>`)
parts.push(`<text x="34" y="${H / 2 + 34}" font-family="${MONO}" font-size="40" font-weight="600"
  letter-spacing="1" fill="${CLOSE}">Infinite mathematics.</text>`)
parts.push(`<text x="36" y="${H / 2 + 78}" font-family="${MONO}" font-size="17"
  fill="${DIM}">IMO 2011 Shortlist G3 &#183; 7 steps &#183; ${resNames.length} identities &#183; every remainder 0</text>`)

const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}"
  viewBox="0 0 ${W} ${H}">${parts.join('')}</svg>`

mkdirSync(OUT, { recursive: true })
await sharp(Buffer.from(svg)).png({ compressionLevel: 9 }).toFile(`${OUT}/x-header.png`)
console.log(`  ${OUT}/x-header.png  ${W}x${H}`)
