/**
 * 作図が (1) 定理として正しく (2) アームで実際に到達可能か を確かめる。
 * 立体は板の上ではなく空間に描くので、ペンの向きが点ごとに変わる。
 * その姿勢まで含めて逆運動学が解けることを検査する。
 */
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import test from 'node:test'
import { fileURLToPath, pathToFileURL } from 'node:url'

const repoRoot = dirname(dirname(fileURLToPath(import.meta.url)))
const scratchDir = mkdtempSync(join(tmpdir(), 'sakumon-fig-'))
const sourceDir = join(scratchDir, 'lib')
const glyphDir = join(scratchDir, 'data', 'strokes')
const compiledDir = join(scratchDir, 'out', 'lib')
mkdirSync(sourceDir, { recursive: true })
mkdirSync(glyphDir, { recursive: true })

const modules = ['figures', 'kinematics', 'handwriting']
for (const name of modules) {
  writeFileSync(
    join(sourceDir, `${name}.ts`),
    readFileSync(join(repoRoot, 'lib', `${name}.ts`), 'utf8'),
    'utf8',
  )
}
writeFileSync(
  join(glyphDir, 'ja.json'),
  readFileSync(join(repoRoot, 'data', 'strokes', 'ja.json'), 'utf8'),
  'utf8',
)
execFileSync(
  process.execPath,
  [
    join(repoRoot, 'node_modules', 'typescript', 'bin', 'tsc'),
    ...modules.map(name => join(sourceDir, `${name}.ts`)),
    '--target', 'es2021', '--module', 'commonjs',
    '--moduleResolution', 'node', '--resolveJsonModule', '--esModuleInterop',
    '--skipLibCheck', '--outDir', join(scratchDir, 'out'), '--rootDir', scratchDir,
  ],
  { cwd: repoRoot, stdio: 'pipe' },
)
const fig = await import(pathToFileURL(join(compiledDir, 'figures.js')).href)
const kin = await import(pathToFileURL(join(compiledDir, 'kinematics.js')).href)

const BOARD_UP = [0, 0, 1]
const DEFAULT_APPROACH = [0, 1, 0]

/**
 * 印の中心。点列の形に依存しないよう、ひし形の頂点の平均で取る。
 * 以前は十字の 3 番目の点を中心としていたが、十字は 1 筆で描くと
 * 中心を通り直すためジグザグに見えたので、ひし形に変えた。
 */
function markCentre(stroke) {
  const pts = stroke.points.slice(0, 4)
  return {
    x: pts.reduce((a, q) => a + q.x, 0) / pts.length,
    y: pts.reduce((a, q) => a + q.y, 0) / pts.length,
    z: pts.reduce((a, q) => a + q.z, 0) / pts.length,
  }
}

test('図が7つ以上あり、平面と立体の両方を含む', () => {
  assert.ok(fig.FIGURES.length >= 7, `図が少ない: ${fig.FIGURES.length}`)
  const solid = fig.FIGURES.filter((f) => f.dimension === 3)
  assert.ok(solid.length >= 2, `立体が少ない: ${solid.length}`)
  console.log(
    `  ${fig.FIGURES.length} 図（平面 ${fig.FIGURES.length - solid.length} / 立体 ${solid.length}）`,
  )
})

test('すべての経由点が逆運動学で解ける（姿勢も含めて）', () => {
  let total = 0
  let failed = 0
  const report = []
  for (const figure of fig.FIGURES) {
    let points = 0
    for (const stroke of figure.strokes) {
      const approach = stroke.approach
        ? [stroke.approach.x, stroke.approach.y, stroke.approach.z]
        : DEFAULT_APPROACH
      for (const p of fig.resample3(stroke.points)) {
        total++
        points++
        const joints = kin.inverse([p.x, p.y, p.z], approach, BOARD_UP, true)
        if (!joints) { failed++; continue }
        const got = kin.positionOf(kin.forward(joints))
        const error = Math.hypot(got[0] - p.x, got[1] - p.y, got[2] - p.z)
        assert.ok(error < 1e-6, `${figure.id} で位置誤差 ${error}`)
      }
    }
    report.push(`${figure.id}:${points}`)
  }
  console.log(`  経由点 ${total} 個 / 到達不能 ${failed}`)
  console.log(`  ${report.join('  ')}`)
  assert.equal(failed, 0, `到達できない点が ${failed} 個ある`)
})

test('九点円の図で、9点が本当に同一円周上にある', () => {
  const figure = fig.FIGURES.find((f) => f.id === 'nine_point')
  const circle = figure.strokes.find((s) => s.kind === 'curve')
  const xs = circle.points.map((p) => p.x)
  const zs = circle.points.map((p) => p.z)
  const centre = {
    x: (Math.min(...xs) + Math.max(...xs)) / 2,
    z: (Math.min(...zs) + Math.max(...zs)) / 2,
  }
  const radius = (Math.max(...xs) - Math.min(...xs)) / 2
  const wanted = figure.strokes.filter(
    (s) => s.kind === 'mark' && /垂線の足|中点 M|中点 P/.test(s.label),
  )
  assert.equal(wanted.length, 9)
  for (const stroke of wanted) {
    const p = markCentre(stroke)
    const d = Math.hypot(p.x - centre.x, p.z - centre.z)
    assert.ok(Math.abs(d - radius) < 1e-6, `${stroke.label}: ${d} vs ${radius}`)
  }
  console.log(`  9点すべてが半径 ${radius.toFixed(3)} の円周上`)
})

test('立方体の断面が正六角形になっている', () => {
  const figure = fig.FIGURES.find((f) => f.id === 'cube_section')
  const sides = figure.strokes.filter((s) => /断面の辺/.test(s.label))
  assert.equal(sides.length, 6)
  const lengths = sides.map((s) => {
    const [a, b] = [s.points[0], s.points[s.points.length - 1]]
    return Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z)
  })
  const first = lengths[0]
  for (const l of lengths) {
    assert.ok(Math.abs(l - first) < 1e-9, `辺の長さが違う: ${l} vs ${first}`)
  }
  // 6 頂点が中心から等距離
  const marks = figure.strokes.filter((s) => /辺の中点 \d\/6/.test(s.label))
  assert.equal(marks.length, 6)
  const centre = markCentre(
    figure.strokes.find((s) => /立方体の中心/.test(s.label)),
  )
  const radii = marks.map((s) => {
    const p = markCentre(s)
    return Math.hypot(p.x - centre.x, p.y - centre.y, p.z - centre.z)
  })
  for (const r of radii) {
    assert.ok(Math.abs(r - radii[0]) < 1e-9, `中心からの距離が違う: ${r}`)
  }
  console.log(`  6辺すべて長さ ${first.toFixed(4)}、6頂点すべて中心から ${radii[0].toFixed(4)}`)
})

test('通過領域の境界が曲線族の各縦断面の最小値・最大値に一致する', () => {
  const figure = fig.FIGURES.find((f) => f.id === 'passage_region')
  assert.ok(figure)
  const family = figure.strokes.filter((s) => /^曲線族/.test(s.label))
  const sections = figure.strokes.filter((s) => /縦断面/.test(s.label))
  assert.equal(family.length, 5)
  assert.equal(sections.length, 6)

  for (const section of sections) {
    const [low, high] = section.points
    const x = (low.x + 9) / 18
    const values = [0, 0.25, 0.5, 0.75, 1].map(
      (t) => 46 + 7 * (x + 2 * x * t - t * t),
    )
    assert.ok(Math.abs(low.z - Math.min(...values)) < 1e-9)
    assert.ok(Math.abs(high.z - Math.max(...values)) < 1e-9)
  }
})

test('正四面体で外接球と内接球の半径比が 3 : 1', () => {
  const figure = fig.FIGURES.find((f) => f.id === 'tetrahedron')
  const centre = markCentre(
    figure.strokes.find((s) => /外接球の中心/.test(s.label)),
  )
  const contacts = figure.strokes.filter((s) => /内接球の接点/.test(s.label))
  assert.equal(contacts.length, 4)
  const inner = contacts.map((s) => {
    const p = markCentre(s)
    return Math.hypot(p.x - centre.x, p.y - centre.y, p.z - centre.z)
  })
  for (const r of inner) {
    assert.ok(Math.abs(r - inner[0]) < 1e-9, `接点が等距離でない: ${r}`)
  }
  const edge = figure.strokes.find((s) => /正四面体の辺 1\/6/.test(s.label))
  const vertex = edge.points[0]
  const outer = Math.hypot(
    vertex.x - centre.x, vertex.y - centre.y, vertex.z - centre.z,
  )
  const ratio = outer / inner[0]
  assert.ok(Math.abs(ratio - 3) < 1e-9, `R : r = ${ratio} : 1`)
  console.log(`  外接球 ${outer.toFixed(3)} / 内接球 ${inner[0].toFixed(3)} = ${ratio.toFixed(6)}`)
})

test('作図の工程数が図ごとに測れる（難易度の手がかり）', () => {
  const rows = fig.FIGURES.map((figure) => ({
    id: figure.id,
    ...fig.figureComplexity(figure),
  }))
  rows.sort((a, b) => b.operations - a.operations)
  for (const row of rows) {
    console.log(
      `  ${row.id.padEnd(16)} 工程 ${String(row.operations).padStart(3)}`
      + ` / 印 ${String(row.marks).padStart(2)}`
      + ` / 補助線 ${String(row.auxiliary).padStart(2)}`
      + ` / 経由点 ${row.points}`,
    )
    assert.ok(row.operations > 0)
    assert.ok(row.points > row.operations)
  }
  assert.ok(rows[0].operations >= 20)
})
