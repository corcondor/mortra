/**
 * Instagram 用カルーセル。1080x1350（4:5）。
 *
 * 2011G3 の証明が、一括展開から U+V=E+F へ畳まれる過程を4枚に分ける。
 * 粒子の配置は種を固定した線形合同法なので、何度実行しても同じ絵になる。
 *
 *   node gen_mortra_carousel.mjs
 *   → workspace/automation/media/mortra-collapse-{1..4}.png
 */
import sharp from 'sharp'
import { mkdirSync } from 'node:fs'
import { join } from 'node:path'

const OUT = 'C:/Users/81808/.openclaw/workspace/automation/media'
mkdirSync(OUT, { recursive: true })

const W = 1080, H = 1350
const GROUND = '#05070a'
const INK = '#e8eef2'
const DIM = '#7d919e'
const CONSTRUCT = '#ff9d2e'
const CLOSE = '#4dffa0'

// 種を固定。毎回同じ配置
let seed = 20110303
const rnd = () => (seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff

const N = 420
const terms = []
for (let i = 0; i < N; i++) {
  const a = rnd() * Math.PI * 2
  const r = Math.pow(rnd(), 0.62) * 0.46
  const bridge = Math.floor(rnd() * 4)
  terms.push({
    ex: 0.5 + Math.cos(a) * r * 1.35, ey: 0.5 + Math.sin(a) * r * 0.92,
    bx: 0.17 + bridge * 0.22,         by: 0.62 + (rnd() - 0.5) * 0.05,
    fx: 0.28 + (i / N) * 0.44,        fy: 0.44 + (rnd() - 0.5) * 0.014,
    bridge, w: 0.5 + rnd() * 1.6, keep: i % 7 === 0 || bridge === 3,
  })
}

const clamp01 = v => (v < 0 ? 0 : v > 1 ? 1 : v)
const ease = t => { const u = clamp01(t); return u * u * (3 - 2 * u) }
const lerp = (a, b, u) => a + (b - a) * u
const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

/** 粒子を描く。toBridge / toFinal で位置と色が決まる */
function particles(toBridge, toFinal, fade) {
  const out = []
  for (const p of terms) {
    const x1 = lerp(p.ex, p.bx, toBridge), y1 = lerp(p.ey, p.by, toBridge)
    const x = lerp(x1, p.fx, toFinal) * W, y = lerp(y1, p.fy, toFinal) * H
    const k = toFinal
    const col = k < 0.5
      ? `rgb(255,${Math.round(157 + 98 * k * 2)},${Math.round(46 + 209 * k * 2)})`
      : `rgb(${Math.round(255 - 178 * (k - 0.5) * 2)},255,${Math.round(255 - 95 * (k - 0.5) * 2)})`
    const kept = p.keep ? 1 : 1 - fade
    const a = (0.16 + 0.5 * (1 - k * 0.45)) * kept
    if (a <= 0.01) continue
    const rr = (1.4 + p.w * 1.15) * (1 - k * 0.22)
    out.push(
      `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${(rr * 2.5).toFixed(1)}" fill="${col}" opacity="${(a * 0.22).toFixed(3)}"/>`,
      `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${rr.toFixed(1)}" fill="${col}" opacity="${a.toFixed(3)}"/>`
    )
  }
  return out.join('')
}

const F = {
  mono: 'IBM Plex Mono, Consolas, monospace',
  serif: 'Georgia, Times New Roman, serif',
}

function slide({ toBridge, toFinal, fade, kicker, title, sub, footer, bridges, identity }) {
  const parts = []
  parts.push(`<rect width="${W}" height="${H}" fill="${GROUND}"/>`)

  // 粒子は加算合成にしたいが SVG では素直に重ねる
  parts.push(`<g>${particles(toBridge, toFinal, fade)}</g>`)

  if (bridges) {
    const names = ['直径円上の点', '3垂足円', '交差する割線', '平行四辺形']
    names.forEach((n, b) => {
      parts.push(`<text x="${((0.17 + b * 0.22) * W).toFixed(0)}" y="${(H * 0.70).toFixed(0)}"
        text-anchor="middle" font-family="${F.mono}" font-size="21" fill="${DIM}">${esc(n)}</text>`)
    })
  }

  if (identity) {
    parts.push(`<text x="${W / 2}" y="${H * 0.50}" text-anchor="middle"
      font-family="${F.mono}" font-size="66" font-weight="600" fill="${CLOSE}">U + V = E + F</text>`)
    parts.push(`<text x="${W / 2}" y="${H * 0.545}" text-anchor="middle"
      font-family="${F.mono}" font-size="24" fill="${DIM}">局所恒等式 15/15 ・ 余り 0</text>`)
  }

  // 文字は下 1/3 に置く。図と重ねない
  let y = H * 0.775
  if (kicker) {
    parts.push(`<text x="88" y="${y}" font-family="${F.mono}" font-size="23"
      letter-spacing="4" fill="${DIM}">${esc(kicker)}</text>`)
    y += 66
  }
  for (const line of title) {
    parts.push(`<text x="88" y="${y}" font-family="${F.serif}" font-size="60"
      fill="${INK}">${esc(line)}</text>`)
    y += 74
  }
  if (sub) {
    y += 12
    for (const line of sub) {
      parts.push(`<text x="88" y="${y}" font-family="${F.serif}" font-size="30"
        fill="${DIM}">${esc(line)}</text>`)
      y += 44
    }
  }
  if (footer) {
    parts.push(`<text x="88" y="${H - 74}" font-family="${F.mono}" font-size="22"
      fill="${CLOSE}">${esc(footer)}</text>`)
  }
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">${parts.join('')}</svg>`
}

const SLIDES = [
  {
    toBridge: 0, toFinal: 0, fade: 0,
    kicker: 'IMO 2011 SHORTLIST G3',
    title: ['4つの変数を', '一括で展開した。'],
    sub: ['式が膨れ、3分を過ぎても終わらない。', 'この経路は採用しなかった。'],
  },
  {
    toBridge: 1, toFinal: 0, fade: 0, bridges: true,
    kicker: '書き方を変える',
    title: ['長い構成を、', '4つの橋に分けた。'],
    sub: ['規則も探索の深さも増やしていない。'],
  },
  {
    toBridge: 1, toFinal: 1, fade: 1, identity: true,
    kicker: '閉じた',
    title: ['2つの項に', '畳まれた。'],
    sub: ['成分ごとに足すと、元の2点に戻る。'],
  },
  {
    toBridge: 1, toFinal: 1, fade: 1,
    kicker: '固定89問・凍結SPLIT',
    title: ['28 → 76'],
    sub: ['公式エンジン単体は28問。', 'MORTRAの監査済み能力和は76問。', '外部LLMは経路に入っていない。'],
    footer: 'mortra.ai',
  },
]

for (let i = 0; i < SLIDES.length; i++) {
  const svg = slide(SLIDES[i])
  const out = join(OUT, `mortra-collapse-${i + 1}.png`)
  await sharp(Buffer.from(svg)).png({ compressionLevel: 9 }).toFile(out)
  console.log(`  ${out}  ${W}x${H}`)
}
