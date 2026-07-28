/**
 * 作図が定理を満たしているかを確かめる。
 * 絵として線を並べただけではなく、9点が本当に同一円周上にあり、
 * 外心・重心・九点円の中心・垂心が本当に一直線に並ぶことを検査する。
 */
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import test from 'node:test'
import { fileURLToPath, pathToFileURL } from 'node:url'

const repoRoot = dirname(dirname(fileURLToPath(import.meta.url)))
const outDir = mkdtempSync(join(tmpdir(), 'sakumon-con-'))
const entry = join(outDir, 'construction.ts')
writeFileSync(entry, readFileSync(join(repoRoot, 'lib', 'construction.ts'), 'utf8'), 'utf8')
execFileSync(
  process.execPath,
  [
    join(repoRoot, 'node_modules', 'typescript', 'bin', 'tsc'),
    entry, '--target', 'es2021', '--module', 'esnext',
    '--moduleResolution', 'bundler', '--skipLibCheck',
  ],
  { cwd: repoRoot, stdio: 'pipe' },
)
const con = await import(pathToFileURL(join(outDir, 'construction.js')).href)

/** 印のストロークから中心点を取り出す（十字の交点 = 3番目の点） */
function markCenter(stroke) {
  return stroke.points[2]
}

test('9つの点がすべて同一円周上にある', () => {
  const { strokes } = con.ninePointConstruction()
  const marks = strokes.filter((s) => s.kind === 'mark')
  const circle = strokes.find((s) => s.kind === 'circle')
  assert.ok(circle, '円のストロークがない')

  // 円の中心と半径を、円ストロークの点列から復元する
  const xs = circle.points.map((p) => p.x)
  const ys = circle.points.map((p) => p.y)
  const center = {
    x: (Math.min(...xs) + Math.max(...xs)) / 2,
    y: (Math.min(...ys) + Math.max(...ys)) / 2,
  }
  const radius = (Math.max(...xs) - Math.min(...xs)) / 2

  // 九点円が通るべき 9 点: 垂線の足3・辺の中点3・頂点と垂心の中点3
  const wanted = marks.filter((s) =>
    /垂線の足|中点 M|中点 P/.test(s.label),
  )
  assert.equal(wanted.length, 9, `9点そろっていない: ${wanted.length}`)

  for (const stroke of wanted) {
    const p = markCenter(stroke)
    const d = Math.hypot(p.x - center.x, p.y - center.y)
    assert.ok(
      Math.abs(d - radius) < 1e-6,
      `${stroke.label} が円周上にない（差 ${Math.abs(d - radius)}）`,
    )
  }
  console.log(`  9点すべてが半径 ${radius.toFixed(4)} の円周上（誤差 < 1e-6）`)
})

test('外心・重心・九点円の中心・垂心が一直線に並ぶ（オイラー線）', () => {
  const { strokes } = con.ninePointConstruction()
  const pick = (pattern) =>
    markCenter(strokes.find((s) => s.kind === 'mark' && pattern.test(s.label)))
  const O = pick(/外心/)
  const G = pick(/重心/)
  const N = pick(/OH の中点/)
  const H = pick(/垂心/)

  const cross = (p) =>
    (H.x - O.x) * (p.y - O.y) - (H.y - O.y) * (p.x - O.x)
  assert.ok(Math.abs(cross(G)) < 1e-6, `重心が線上にない: ${cross(G)}`)
  assert.ok(Math.abs(cross(N)) < 1e-6, `九点円の中心が線上にない: ${cross(N)}`)

  // OG : GH = 1 : 2
  const og = Math.hypot(G.x - O.x, G.y - O.y)
  const gh = Math.hypot(H.x - G.x, H.y - G.y)
  assert.ok(Math.abs(gh / og - 2) < 1e-6, `OG:GH が 1:2 でない (${gh / og})`)
  console.log('  OG : GH = 1 : 2 も一致')
})

test('作図の工程数が十分にある', () => {
  const { strokes } = con.ninePointConstruction()
  assert.ok(strokes.length >= 18, `工程が少ない: ${strokes.length}`)
  const total = strokes.reduce(
    (sum, s) => sum + con.resample(s.points).length,
    0,
  )
  console.log(`  ${strokes.length} 工程 / 経由点 ${total} 個`)
  assert.ok(total > 300)
})
