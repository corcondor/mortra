/**
 * 最小ジャーク軌道が本当に「最小」かを確かめる。
 *
 * spline を作っただけなら誰でもできる。ここで検査するのは
 *   1) 2点間では Flash & Hogan の厳密解 10t^3-15t^4+6t^5 に一致する
 *   2) 経由点を厳密に通る
 *   3) 節点で 4 階微分（スナップ）まで連続 = ジャーク最小の必要条件
 *   4) 内部節点の速度・加速度をどちらへ動かしてもコストが増える（本当に極小）
 *   5) 素朴な区間ごと停止の軌道よりコストが小さい
 */
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import test from 'node:test'
import { fileURLToPath, pathToFileURL } from 'node:url'

const repoRoot = dirname(dirname(fileURLToPath(import.meta.url)))
const outDir = mkdtempSync(join(tmpdir(), 'sakumon-traj-'))
const entry = join(outDir, 'trajectory.ts')
writeFileSync(entry, readFileSync(join(repoRoot, 'lib', 'trajectory.ts'), 'utf8'), 'utf8')
execFileSync(
  process.execPath,
  [
    join(repoRoot, 'node_modules', 'typescript', 'bin', 'tsc'),
    entry, '--target', 'es2021', '--module', 'esnext',
    '--moduleResolution', 'bundler', '--skipLibCheck',
  ],
  { cwd: repoRoot, stdio: 'pipe' },
)
const traj = await import(pathToFileURL(join(outDir, 'trajectory.js')).href)

const POINTS = [0, 1.2, 0.4, 2.1, 1.7, -0.6, 0.9]
const DURATIONS = [0.4, 0.55, 0.3, 0.7, 0.45, 0.5]

test('2点間は Flash & Hogan の厳密解に一致する', () => {
  const h = 1.3
  const segments = traj.minimumJerkSpline([0, 5], [h])
  assert.equal(segments.length, 1)
  for (let i = 0; i <= 20; i++) {
    const s = (i / 20) * h
    const tau = s / h
    const expected = 5 * (10 * tau ** 3 - 15 * tau ** 4 + 6 * tau ** 5)
    const got = traj.evaluate(segments[0], s).position
    assert.ok(Math.abs(got - expected) < 1e-9, `τ=${tau} で ${got} ≠ ${expected}`)
  }
})

test('すべての経由点をちょうど通る', () => {
  const segments = traj.minimumJerkSpline(POINTS, DURATIONS)
  assert.equal(segments.length, POINTS.length - 1)
  for (let i = 0; i < segments.length; i++) {
    const start = traj.evaluate(segments[i], 0).position
    const end = traj.evaluate(segments[i], segments[i].h).position
    assert.ok(Math.abs(start - POINTS[i]) < 1e-9, `節点${i} 始端 ${start}`)
    assert.ok(Math.abs(end - POINTS[i + 1]) < 1e-9, `節点${i + 1} 終端 ${end}`)
  }
})

test('始点と終点で速度も加速度も 0', () => {
  const segments = traj.minimumJerkSpline(POINTS, DURATIONS)
  const first = traj.evaluate(segments[0], 0)
  const last = traj.evaluate(
    segments[segments.length - 1],
    segments[segments.length - 1].h,
  )
  for (const [name, value] of [
    ['始点の速度', first.velocity], ['始点の加速度', first.acceleration],
    ['終点の速度', last.velocity], ['終点の加速度', last.acceleration],
  ]) {
    assert.ok(Math.abs(value) < 1e-9, `${name} = ${value}`)
  }
})

test('節点で速度・加速度・ジャーク・スナップがすべて連続', () => {
  const segments = traj.minimumJerkSpline(POINTS, DURATIONS)
  const snap = (segment, s) => {
    const [, , , , c4, c5] = segment.c
    return 24 * c4 + 120 * c5 * s
  }
  let worst = 0
  for (let i = 0; i < segments.length - 1; i++) {
    const left = traj.evaluate(segments[i], segments[i].h)
    const right = traj.evaluate(segments[i + 1], 0)
    const pairs = [
      [left.position, right.position],
      [left.velocity, right.velocity],
      [left.acceleration, right.acceleration],
      [left.jerk, right.jerk],
      [snap(segments[i], segments[i].h), snap(segments[i + 1], 0)],
    ]
    for (const [a, b] of pairs) {
      worst = Math.max(worst, Math.abs(a - b))
      assert.ok(Math.abs(a - b) < 1e-7, `節点${i + 1} で不連続: ${a} vs ${b}`)
    }
  }
  console.log(`  節点での最大不連続量 ${worst.toExponential(2)}（4階微分まで連続）`)
})

test('内部節点をどちらへ動かしてもコストが増える（本当に極小）', () => {
  const segments = traj.minimumJerkSpline(POINTS, DURATIONS)
  const base = traj.jerkCost(segments)

  // 解から節点の速度・加速度を読み出す
  const velocity = [0]
  const acceleration = [0]
  for (let i = 1; i < POINTS.length - 1; i++) {
    const v = traj.evaluate(segments[i], 0)
    velocity.push(v.velocity)
    acceleration.push(v.acceleration)
  }
  velocity.push(0)
  acceleration.push(0)

  const rebuild = (vs, as) => {
    const built = []
    for (let i = 0; i < POINTS.length - 1; i++) {
      built.push({
        c: traj.quinticCoefficients(
          POINTS[i], vs[i], as[i], POINTS[i + 1], vs[i + 1], as[i + 1],
          DURATIONS[i],
        ),
        h: DURATIONS[i],
      })
    }
    return built
  }
  // 解に一致することを先に確認
  assert.ok(Math.abs(traj.jerkCost(rebuild(velocity, acceleration)) - base) < 1e-6)

  let checks = 0
  for (const eps of [0.02, -0.02]) {
    for (let k = 1; k < POINTS.length - 1; k++) {
      for (const which of ['v', 'a']) {
        const vs = [...velocity]
        const as = [...acceleration]
        if (which === 'v') vs[k] += eps
        else as[k] += eps
        const cost = traj.jerkCost(rebuild(vs, as))
        assert.ok(
          cost > base + 1e-9,
          `節点${k} の ${which} を ${eps} 動かしたらコストが減った (${cost} < ${base})`,
        )
        checks++
      }
    }
  }
  console.log(`  ${checks} 通りの摂動すべてでコスト増加（基準 ${base.toFixed(3)}）`)
})

test('区間ごとに停止する素朴な軌道よりコストが小さい', () => {
  const optimal = traj.minimumJerkSpline(POINTS, DURATIONS)
  const naive = []
  for (let i = 0; i < POINTS.length - 1; i++) {
    naive.push({
      c: traj.quinticCoefficients(
        POINTS[i], 0, 0, POINTS[i + 1], 0, 0, DURATIONS[i],
      ),
      h: DURATIONS[i],
    })
  }
  const optimalCost = traj.jerkCost(optimal)
  const naiveCost = traj.jerkCost(naive)
  assert.ok(
    optimalCost < naiveCost,
    `最小ジャークの方が大きい: ${optimalCost} vs ${naiveCost}`,
  )
  console.log(
    `  ジャーク二乗積分: 最小 ${optimalCost.toFixed(1)} / 区間ごと停止 ${naiveCost.toFixed(1)}`
    + `（${((1 - optimalCost / naiveCost) * 100).toFixed(1)}% 減）`,
  )
})

test('多関節でも同じ性質が保たれる', () => {
  const waypoints = []
  for (let i = 0; i < 40; i++) {
    waypoints.push([
      Math.sin(i * 0.3), Math.cos(i * 0.21), Math.sin(i * 0.17) * 0.6,
      Math.cos(i * 0.11), Math.sin(i * 0.07), Math.cos(i * 0.13) * 0.4,
    ])
  }
  const durations = traj.timeParameterize(waypoints)
  assert.equal(durations.length, waypoints.length - 1)
  const perJoint = traj.planJointTrajectory(waypoints, durations)
  assert.equal(perJoint.length, 6)

  // 各関節が全経由点を通る
  let elapsed = 0
  for (let i = 0; i < waypoints.length; i++) {
    const { joints } = traj.sampleAt(perJoint, durations, elapsed)
    for (let j = 0; j < 6; j++) {
      assert.ok(
        Math.abs(joints[j] - waypoints[i][j]) < 1e-6,
        `経由点${i} 関節${j}: ${joints[j]} ≠ ${waypoints[i][j]}`,
      )
    }
    elapsed += durations[i] ?? 0
  }
  const total = durations.reduce((a, b) => a + b, 0)
  console.log(`  6関節 / 経由点40個 / 総時間 ${total.toFixed(2)}s を全点通過`)
})
