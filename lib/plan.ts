/**
 * 作図を「アームが辿る関節角の列」に変換する。
 *
 * ここが雑だと腕が暴れる。実測して分かった原因は 2 つあった:
 *
 *  1. 逆運動学の解の枝が途中で切り替わる
 *     6R アームは 1 姿勢に最大 8 解あり、素直に atan2 を使うと解が飛ぶ。
 *     立体の作図で隣り合う経由点の関節角が 358.9 度跳んでいた。
 *     → inverseNear で直前に最も近い解を選ぶ。
 *
 *  2. ストロークごとにペンの向きが不連続に変わる
 *     立方体の 12 辺はそれぞれ別方向を向くので、辺から辺へ移る瞬間に
 *     手首が一気に回る。
 *     → ペンを上げている間に向きを球面線形補間で少しずつ変える。
 */

import {
  inverseNear, type Vec3,
} from './kinematics'
import { resample3, type Figure, type P3 } from './figures'
import {
  peakDerivatives, planJointTrajectory, timeParameterize,
  type QuinticSegment,
} from './trajectory'

const BOARD_UP: Vec3 = [0, 0, 1]
const DEFAULT_APPROACH: Vec3 = [0, 1, 0]
const LIFT = 7
/** 向きを切り替えるときに挟む中間姿勢の数 */
const TRANSITION_STEPS = 14

export type Marker = { penDown: boolean; stroke: number; label: string }

export type Plan = {
  waypoints: number[][]
  markers: Marker[]
  durations: number[]
  perJoint: QuinticSegment[][]
  total: number
  unreachable: number
  peak: { speed: number; acceleration: number; jerk: number }
  maxJointJumpDeg: number
}

const dot3 = (a: Vec3, b: Vec3) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

function unit(v: Vec3): Vec3 {
  const n = Math.hypot(v[0], v[1], v[2]) || 1
  return [v[0] / n, v[1] / n, v[2] / n]
}

/** 単位ベクトルの球面線形補間 */
export function slerp(a: Vec3, b: Vec3, t: number): Vec3 {
  const u = unit(a)
  const v = unit(b)
  let cos = Math.max(-1, Math.min(1, dot3(u, v)))
  if (cos < 0) cos = Math.max(-1, Math.min(1, cos)) // 反対向きでも素直に回す
  const angle = Math.acos(cos)
  if (angle < 1e-6) return u
  const sin = Math.sin(angle)
  const wa = Math.sin((1 - t) * angle) / sin
  const wb = Math.sin(t * angle) / sin
  return unit([
    u[0] * wa + v[0] * wb,
    u[1] * wa + v[1] * wb,
    u[2] * wa + v[2] * wb,
  ])
}

const strokeApproach = (stroke: Figure['strokes'][number]): Vec3 =>
  stroke.approach
    ? unit([stroke.approach.x, stroke.approach.y, stroke.approach.z])
    : DEFAULT_APPROACH

const lifted = (p: P3, approach: Vec3): P3 => ({
  x: p.x - approach[0] * LIFT,
  y: p.y - approach[1] * LIFT,
  z: p.z - approach[2] * LIFT,
})

/** 経由点の目標（位置・ペンの向き・意味） */
type Target = { point: P3; approach: Vec3; marker: Marker }

/** 許容する関節の 1 ステップあたりの変化（度） */
const MAX_STEP_DEG = 12
/** 細分の深さの上限。これを超えても縮まらない跳びは解の枝の不連続 */
const MAX_SUBDIVISION = 5

export function buildPlan(figure: Figure): Plan {
  const targets: Target[] = []
  let lastApproach: Vec3 | null = null
  let lastLift: P3 | null = null

  figure.strokes.forEach((stroke, index) => {
    const approach = strokeApproach(stroke)
    const dense = resample3(stroke.points)
    if (!dense.length) return
    const up: Marker = { penDown: false, stroke: index, label: stroke.label }
    const down: Marker = { penDown: true, stroke: index, label: stroke.label }
    const entry = lifted(dense[0], approach)

    // 前のストロークから、位置と向きを同時に少しずつ変えながら移る。
    // 向きを一気に変えると手首が跳ねるので、必ず中間姿勢を挟む。
    if (lastApproach && lastLift) {
      for (let i = 1; i <= TRANSITION_STEPS; i++) {
        const t = i / TRANSITION_STEPS
        targets.push({
          point: {
            x: lastLift.x + (entry.x - lastLift.x) * t,
            y: lastLift.y + (entry.y - lastLift.y) * t,
            z: lastLift.z + (entry.z - lastLift.z) * t,
          },
          approach: slerp(lastApproach, approach, t),
          marker: up,
        })
      }
    } else {
      targets.push({ point: entry, approach, marker: up })
    }

    for (const p of dense) targets.push({ point: p, approach, marker: down })

    const exit = lifted(dense[dense.length - 1], approach)
    targets.push({ point: exit, approach, marker: up })
    lastApproach = approach
    lastLift = exit
  })

  // 目標列を関節角へ。跳びが大きいところは中間目標を挿して解き直す。
  // 位置が近くても、その付近で解が急に変わる領域（基部の真上を通る等）が
  // あり、そこは細かく刻まないと 1 ステップで 40 度以上動いてしまう。
  const waypoints: number[][] = []
  const markers: Marker[] = []
  let unreachable = 0
  let previous: number[] | null = null

  const solve = (target: Target): number[] | null =>
    inverseNear(
      [target.point.x, target.point.y, target.point.z],
      target.approach, BOARD_UP, previous, true,
    )

  const midway = (a: Target, b: Target): Target => ({
    point: {
      x: (a.point.x + b.point.x) / 2,
      y: (a.point.y + b.point.y) / 2,
      z: (a.point.z + b.point.z) / 2,
    },
    approach: slerp(a.approach, b.approach, 0.5),
    marker: b.marker,
  })

  const jumpDeg = (from: number[], to: number[]): number => {
    let worst = 0
    for (let i = 0; i < to.length; i++) {
      worst = Math.max(worst, (Math.abs(to[i] - from[i]) * 180) / Math.PI)
    }
    return worst
  }

  const emit = (target: Target, previousTarget: Target | null, depth: number) => {
    const joints = solve(target)
    if (!joints) { unreachable++; return }
    if (
      previous && previousTarget && depth < MAX_SUBDIVISION
      && jumpDeg(previous, joints) > MAX_STEP_DEG
    ) {
      emit(midway(previousTarget, target), previousTarget, depth + 1)
      emit(target, previousTarget, depth + 1)
      return
    }
    previous = joints
    waypoints.push(joints)
    markers.push(target.marker)
  }

  targets.forEach((target, index) => {
    emit(target, index > 0 ? targets[index - 1] : null, 0)
  })

  const durations = timeParameterize(waypoints)
  const perJoint = planJointTrajectory(waypoints, durations)
  const total = durations.reduce((a, b) => a + b, 0)
  const peak = peakDerivatives(perJoint)

  let maxJointJumpDeg = 0
  for (let i = 1; i < waypoints.length; i++) {
    for (let j = 0; j < waypoints[i].length; j++) {
      maxJointJumpDeg = Math.max(
        maxJointJumpDeg,
        (Math.abs(waypoints[i][j] - waypoints[i - 1][j]) * 180) / Math.PI,
      )
    }
  }

  return {
    waypoints, markers, durations, perJoint, total,
    unreachable, peak, maxJointJumpDeg,
  }
}
