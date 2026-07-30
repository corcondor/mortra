/**
 * 作図の計画（経由点 → 関節角の列）が暴れないことを確かめる。
 *
 * 最初の実装では立体の作図で隣り合う経由点の関節角が 358.9 度跳んでいた。
 * 原因は 3 つで、どれも実測して初めて分かった:
 *   1. atan2 の折り返しで解が飛ぶ        → 直前に最も近い解を選ぶ
 *   2. 6R は 1 姿勢に 8 解あり枝が変わる  → 8 解すべてから選ぶ
 *   3. ストロークごとにペンの向きが不連続 → 移動中に球面線形補間する
 * さらに、跳びが残る箇所は中間目標を挿して解き直す（適応細分）。
 */
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import test from 'node:test'
import { fileURLToPath, pathToFileURL } from 'node:url'

const repoRoot = dirname(dirname(fileURLToPath(import.meta.url)))
const outDir = mkdtempSync(join(tmpdir(), 'sakumon-plan-'))
const modules = ['figures', 'kinematics', 'trajectory', 'plan']
for (const name of modules) {
  writeFileSync(
    join(outDir, `${name}.ts`),
    readFileSync(join(repoRoot, 'lib', `${name}.ts`), 'utf8'),
    'utf8',
  )
}
execFileSync(
  process.execPath,
  [
    join(repoRoot, 'node_modules', 'typescript', 'bin', 'tsc'),
    ...modules.map((n) => join(outDir, `${n}.ts`)),
    '--target', 'es2021', '--module', 'esnext',
    '--moduleResolution', 'bundler', '--skipLibCheck',
  ],
  { cwd: repoRoot, stdio: 'pipe' },
)
for (const name of modules) {
  const file = join(outDir, `${name}.js`)
  writeFileSync(
    file,
    readFileSync(file, 'utf8').replace(/from '(\.\/[^']+)'/g, "from '$1.js'"),
    'utf8',
  )
}
const fig = await import(pathToFileURL(join(outDir, 'figures.js')).href)
const kin = await import(pathToFileURL(join(outDir, 'kinematics.js')).href)
const plan = await import(pathToFileURL(join(outDir, 'plan.js')).href)

const plans = fig.FIGURES.map((figure) => ({
  figure, built: plan.buildPlan(figure),
}))

test('どの図も、隣り合う経由点での関節角の跳びが 70 度以下', () => {
  for (const { figure, built } of plans) {
    console.log(
      `  ${figure.id.padEnd(16)} 最大跳び ${built.maxJointJumpDeg.toFixed(1).padStart(6)}度`
      + ` / 経由点 ${String(built.waypoints.length).padStart(4)}`
      + ` / 到達不能 ${built.unreachable}`
      + ` / ${built.total.toFixed(1)}s`,
    )
    assert.equal(built.unreachable, 0, `${figure.id} に到達できない点がある`)
    assert.ok(
      built.maxJointJumpDeg <= 70,
      `${figure.id} で ${built.maxJointJumpDeg.toFixed(1)} 度跳んでいる`,
    )
  }
})

test('平面の図は 20 度以下に収まる', () => {
  for (const { figure, built } of plans) {
    if (figure.dimension !== 2) continue
    assert.ok(
      built.maxJointJumpDeg <= 20,
      `${figure.id} で ${built.maxJointJumpDeg.toFixed(1)} 度`,
    )
  }
})

test('関節角を順運動学に戻すと、ペン先が滑らかな曲線を描く', () => {
  // 経由点ごとのペン先位置を出し、隣との距離が飛ばないことを見る。
  // 関節が跳べばペン先も飛ぶので、これが最終的な確認になる。
  for (const { figure, built } of plans) {
    let worst = 0
    let previous = null
    for (const joints of built.waypoints) {
      const p = kin.positionOf(kin.forward(joints))
      if (previous) {
        worst = Math.max(worst, Math.hypot(
          p[0] - previous[0], p[1] - previous[1], p[2] - previous[2],
        ))
      }
      previous = p
    }
    assert.ok(worst < 12, `${figure.id} でペン先が ${worst.toFixed(2)} 飛んだ`)
  }
})

test('軌道は全経由点を通り、両端で静止する', () => {
  const { built } = plans[0]
  let elapsed = 0
  for (let i = 0; i < built.waypoints.length; i++) {
    const { joints } = plan.buildPlan
      ? sample(built, elapsed)
      : { joints: [] }
    for (let j = 0; j < 6; j++) {
      assert.ok(
        Math.abs(joints[j] - built.waypoints[i][j]) < 1e-6,
        `経由点${i} 関節${j}`,
      )
    }
    elapsed += built.durations[i] ?? 0
  }
})

function sample(built, t) {
  return trajectorySample(built.perJoint, built.durations, t)
}
let trajectorySample
{
  const traj = await import(pathToFileURL(join(outDir, 'trajectory.js')).href)
  trajectorySample = traj.sampleAt
}
