/**
 * 6軸アームの運動学が本物かを確かめる。
 *
 * 見せかけのアニメーションではないことの根拠は 1 つだけで、
 *   逆運動学で解いた関節角を順運動学に入れ直すと、狙った位置と姿勢に戻る
 * ことである。ここではそれを板面上の多数の点について検査する。
 */
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import test from 'node:test'
import { fileURLToPath, pathToFileURL } from 'node:url'

const repoRoot = dirname(dirname(fileURLToPath(import.meta.url)))
const outDir = mkdtempSync(join(tmpdir(), 'sakumon-kin-'))
const source = readFileSync(join(repoRoot, 'lib', 'kinematics.ts'), 'utf8')
const entry = join(outDir, 'kinematics.ts')
writeFileSync(entry, source, 'utf8')
execFileSync(
  process.execPath,
  [
    join(repoRoot, 'node_modules', 'typescript', 'bin', 'tsc'),
    entry,
    '--target', 'es2021',
    '--module', 'esnext',
    '--moduleResolution', 'bundler',
    '--skipLibCheck',
  ],
  { cwd: repoRoot, stdio: 'pipe' },
)
const kin = await import(pathToFileURL(join(outDir, 'kinematics.js')).href)

const BOARD_Y = 55          // 板面の位置（y = 一定の垂直面）
const APPROACH = [0, 1, 0]  // ペンは板に垂直に当たる
const UP = [0, 0, 1]

test('順運動学は同次変換の積になっている', () => {
  const frames = kin.forwardAll([0, 0, 0, 0, 0, 0])
  assert.equal(frames.length, 6)
  for (const m of frames) {
    assert.equal(m.length, 16)
    // 最下行は (0,0,0,1)
    assert.ok(Math.abs(m[12]) < 1e-9)
    assert.ok(Math.abs(m[13]) < 1e-9)
    assert.ok(Math.abs(m[14]) < 1e-9)
    assert.ok(Math.abs(m[15] - 1) < 1e-9)
  }
})

test('回転部分は直交行列である（各軸が単位で互いに直交）', () => {
  const m = kin.forward([0.3, -0.4, 0.8, 0.2, 0.5, -0.6])
  const r = kin.rotationOf(m)
  const col = (c) => [r[c], r[3 + c], r[6 + c]]
  for (let c = 0; c < 3; c++) {
    const v = col(c)
    assert.ok(Math.abs(Math.hypot(...v) - 1) < 1e-9, `列${c}が単位でない`)
  }
  const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
  assert.ok(Math.abs(dot(col(0), col(1))) < 1e-9)
  assert.ok(Math.abs(dot(col(0), col(2))) < 1e-9)
  assert.ok(Math.abs(dot(col(1), col(2))) < 1e-9)
})

test('逆運動学の解を順運動学に戻すと、狙った点に一致する', () => {
  let checked = 0
  let unreachable = 0
  for (let x = -30; x <= 30; x += 10) {
    for (let z = 20; z <= 70; z += 10) {
      const target = [x, BOARD_Y, z]
      const joints = kin.inverse(target, APPROACH, UP, true)
      if (joints === null) { unreachable++; continue }
      const pose = kin.forward(joints)
      const got = kin.positionOf(pose)
      const error = Math.hypot(
        got[0] - target[0],
        got[1] - target[1],
        got[2] - target[2],
      )
      assert.ok(error < 1e-6, `(${x},${z}) で誤差 ${error}`)
      checked++
    }
  }
  assert.ok(checked >= 20, `検査できた点が少なすぎる: ${checked}`)
  console.log(`  到達可能 ${checked} 点で位置誤差 < 1e-6 / 到達不能 ${unreachable} 点`)
})

test('ペン先の向きが板の法線に一致する', () => {
  const joints = kin.inverse([10, BOARD_Y, 45], APPROACH, UP, true)
  assert.ok(joints)
  const pose = kin.forward(joints)
  const r = kin.rotationOf(pose)
  const zAxis = [r[2], r[5], r[8]] // 手先の z 軸 = ペンの向き
  const error = Math.hypot(
    zAxis[0] - APPROACH[0],
    zAxis[1] - APPROACH[1],
    zAxis[2] - APPROACH[2],
  )
  assert.ok(error < 1e-6, `姿勢誤差 ${error}`)
})

test('肘の上向き・下向きの両方が同じ点に到達する', () => {
  const target = [5, BOARD_Y, 50]
  const up = kin.inverse(target, APPROACH, UP, true)
  const down = kin.inverse(target, APPROACH, UP, false)
  assert.ok(up && down)
  assert.notDeepEqual(up, down)
  for (const solution of [up, down]) {
    const got = kin.positionOf(kin.forward(solution))
    const error = Math.hypot(
      got[0] - target[0], got[1] - target[1], got[2] - target[2],
    )
    assert.ok(error < 1e-6)
  }
})

test('到達範囲の外は解なしを返す（黙って嘘の角度を出さない）', () => {
  assert.equal(kin.inverse([0, 500, 0], APPROACH, UP, true), null)
})
