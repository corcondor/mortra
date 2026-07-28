'use client'

/**
 * 6軸アームが黒板に作図する。
 *
 * アニメーションではなく運動学で動かしている。各経由点についてペン先の
 * 位置と姿勢（板の法線）を与え、球面手首の decoupling で関節角を閉形式で
 * 解き、その角度を順運動学に入れてリンクを描いている。
 * つまり画面の腕は、解いた関節角の結果として、そこにある。
 */

import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import {
  ARM,
  forwardAll,
  inverse,
  lerpJoints,
  positionOf,
  type Vec3,
} from '@/lib/kinematics'
import { ninePointConstruction, resample, type P2 } from '@/lib/construction'

const BOARD_Y = 55            // 板面の位置
const APPROACH: Vec3 = [0, 1, 0]  // ペンは板に垂直
const BOARD_UP: Vec3 = [0, 0, 1]
const LIFT = 6                // ペンを浮かせる距離
const BOARD_Z = 46            // 板の中心高さ

type Waypoint = {
  joints: number[]
  world: THREE.Vector3
  penDown: boolean
  stroke: number
  label: string
}

/** 板面座標 → ワールド座標 */
function toWorld(p: P2, lift = 0): Vec3 {
  return [p.x, BOARD_Y - lift, BOARD_Z + p.y]
}

function buildPlan(): { plan: Waypoint[]; unreachable: number } {
  const { strokes } = ninePointConstruction()
  const plan: Waypoint[] = []
  let unreachable = 0
  strokes.forEach((stroke, index) => {
    const dense = resample(stroke.points)
    // ペンを上げたまま描き始めへ移動する
    const approachPoints = [dense[0]]
    for (const [pointList, penDown, lift] of [
      [approachPoints, false, LIFT],
      [dense, true, 0],
      [[dense[dense.length - 1]], false, LIFT],
    ] as [P2[], boolean, number][]) {
      for (const p of pointList) {
        const target = toWorld(p, lift)
        const joints = inverse(target, APPROACH, BOARD_UP, true)
        if (!joints) { unreachable++; continue }
        plan.push({
          joints,
          world: new THREE.Vector3(target[0], target[1], target[2]),
          penDown,
          stroke: index,
          label: stroke.label,
        })
      }
    }
  })
  return { plan, unreachable }
}

/** 2点間に円柱を張る */
function orientSegment(
  mesh: THREE.Mesh,
  a: THREE.Vector3,
  b: THREE.Vector3,
) {
  const direction = new THREE.Vector3().subVectors(b, a)
  const length = direction.length()
  if (length < 1e-6) { mesh.visible = false; return }
  mesh.visible = true
  mesh.position.copy(a).addScaledVector(direction, 0.5)
  mesh.scale.set(1, length, 1)
  mesh.quaternion.setFromUnitVectors(
    new THREE.Vector3(0, 1, 0),
    direction.clone().normalize(),
  )
}

export default function RobotPage() {
  const mountRef = useRef<HTMLDivElement>(null)
  const [speed, setSpeed] = useState(1)
  const [running, setRunning] = useState(true)
  const [angles, setAngles] = useState<number[]>([0, 0, 0, 0, 0, 0])
  const [caption, setCaption] = useState('準備中')
  const [progress, setProgress] = useState(0)
  const [meta, setMeta] = useState({ steps: 0, points: 0, unreachable: 0 })
  const speedRef = useRef(1)
  const runningRef = useRef(true)
  const resetRef = useRef(false)

  useEffect(() => { speedRef.current = speed }, [speed])
  useEffect(() => { runningRef.current = running }, [running])

  useEffect(() => {
    const mount = mountRef.current
    if (!mount) return

    const { plan, unreachable } = buildPlan()
    const { strokes, facts } = ninePointConstruction()
    setMeta({ steps: strokes.length, points: plan.length, unreachable })
    void facts

    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0x0b0d0c)
    scene.fog = new THREE.Fog(0x0b0d0c, 180, 420)

    const camera = new THREE.PerspectiveCamera(
      42, mount.clientWidth / mount.clientHeight, 0.1, 1000,
    )
    camera.position.set(78, -95, 92)
    camera.up.set(0, 0, 1)
    camera.lookAt(0, BOARD_Y, BOARD_Z)

    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.setSize(mount.clientWidth, mount.clientHeight)
    mount.appendChild(renderer.domElement)

    scene.add(new THREE.AmbientLight(0xffffff, 0.55))
    const key = new THREE.DirectionalLight(0xffffff, 1.1)
    key.position.set(60, -80, 120)
    scene.add(key)
    const rim = new THREE.DirectionalLight(0x88bbff, 0.5)
    rim.position.set(-70, -40, 40)
    scene.add(rim)

    // 黒板
    const board = new THREE.Mesh(
      new THREE.PlaneGeometry(120, 84),
      new THREE.MeshStandardMaterial({
        color: 0x21302a, roughness: 0.95, metalness: 0.0,
      }),
    )
    board.position.set(0, BOARD_Y + 0.6, BOARD_Z)
    board.rotation.x = Math.PI / 2
    scene.add(board)
    const frame = new THREE.Mesh(
      new THREE.BoxGeometry(126, 2.2, 90),
      new THREE.MeshStandardMaterial({ color: 0x6b4a2c, roughness: 0.8 }),
    )
    frame.position.set(0, BOARD_Y + 2.2, BOARD_Z)
    scene.add(frame)

    // 台座
    const base = new THREE.Mesh(
      new THREE.CylinderGeometry(11, 13, 6, 40),
      new THREE.MeshStandardMaterial({ color: 0x2a2f33, roughness: 0.5, metalness: 0.6 }),
    )
    base.position.set(0, 0, 3)
    base.rotation.x = Math.PI / 2
    scene.add(base)
    const floor = new THREE.Mesh(
      new THREE.PlaneGeometry(400, 400),
      new THREE.MeshStandardMaterial({ color: 0x121514, roughness: 1 }),
    )
    scene.add(floor)

    // アームのリンクと関節
    const linkMaterial = new THREE.MeshStandardMaterial({
      color: 0xd8dde0, roughness: 0.35, metalness: 0.75,
    })
    const jointMaterial = new THREE.MeshStandardMaterial({
      color: 0xffb454, roughness: 0.4, metalness: 0.4,
    })
    const links: THREE.Mesh[] = []
    const joints: THREE.Mesh[] = []
    for (let i = 0; i < ARM.length; i++) {
      const link = new THREE.Mesh(
        new THREE.CylinderGeometry(2.6 - i * 0.22, 2.6 - i * 0.22, 1, 20),
        linkMaterial,
      )
      scene.add(link)
      links.push(link)
      const joint = new THREE.Mesh(
        new THREE.CylinderGeometry(3.4 - i * 0.28, 3.4 - i * 0.28, 3.2, 24),
        jointMaterial,
      )
      scene.add(joint)
      joints.push(joint)
    }
    const pen = new THREE.Mesh(
      new THREE.ConeGeometry(1.1, 5, 16),
      new THREE.MeshStandardMaterial({ color: 0xfff3d0, emissive: 0x554422 }),
    )
    scene.add(pen)

    // 描いた線を貯める
    const inkGroup = new THREE.Group()
    scene.add(inkGroup)
    const inkColors = [0xf6f2e7, 0x9fe0b0, 0xffd79a, 0x8fd0ff]
    let currentPositions: number[] = []
    let currentLine: THREE.Line | null = null

    const startLine = (strokeIndex: number) => {
      currentPositions = []
      const geometry = new THREE.BufferGeometry()
      geometry.setAttribute(
        'position',
        new THREE.BufferAttribute(new Float32Array(6000), 3),
      )
      geometry.setDrawRange(0, 0)
      currentLine = new THREE.Line(
        geometry,
        new THREE.LineBasicMaterial({
          color: inkColors[strokeIndex % inkColors.length],
        }),
      )
      inkGroup.add(currentLine)
    }
    const pushInk = (v: THREE.Vector3) => {
      if (!currentLine) return
      currentPositions.push(v.x, v.y - 0.4, v.z)
      const attribute = currentLine.geometry.getAttribute(
        'position',
      ) as THREE.BufferAttribute
      const count = Math.min(currentPositions.length / 3, 2000)
      for (let i = 0; i < count * 3; i++) attribute.array[i] = currentPositions[i]
      attribute.needsUpdate = true
      currentLine.geometry.setDrawRange(0, count)
    }

    let index = 0
    let blend = 0
    let shown = [...(plan[0]?.joints ?? [0, 0, 0, 0, 0, 0])]
    let lastStroke = -1
    let raf = 0
    let disposed = false

    const drawArm = (jointAngles: number[]) => {
      const frames = forwardAll(jointAngles)
      let previous = new THREE.Vector3(0, 0, 0)
      frames.forEach((m, i) => {
        const p = positionOf(m)
        const point = new THREE.Vector3(p[0], p[1], p[2])
        orientSegment(links[i], previous, point)
        joints[i].position.copy(point)
        const zAxis = new THREE.Vector3(m[2], m[6], m[10])
        joints[i].quaternion.setFromUnitVectors(
          new THREE.Vector3(0, 1, 0), zAxis.normalize(),
        )
        previous = point
      })
      const tip = previous
      const last = frames[frames.length - 1]
      const dir = new THREE.Vector3(last[2], last[6], last[10]).normalize()
      pen.position.copy(tip).addScaledVector(dir, -2.5)
      pen.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir)
    }

    const tick = () => {
      if (disposed) return
      raf = requestAnimationFrame(tick)

      if (resetRef.current) {
        resetRef.current = false
        index = 0; blend = 0; lastStroke = -1
        shown = [...(plan[0]?.joints ?? shown)]
        inkGroup.clear()
        currentLine = null
      }

      if (runningRef.current && index < plan.length - 1) {
        blend += 0.16 * speedRef.current
        while (blend >= 1 && index < plan.length - 1) {
          blend -= 1
          index++
          const wp = plan[index]
          if (wp.penDown) {
            if (wp.stroke !== lastStroke) {
              lastStroke = wp.stroke
              startLine(wp.stroke)
              setCaption(`${wp.stroke + 1}. ${wp.label}`)
            }
            pushInk(wp.world)
          }
        }
        const from = plan[index].joints
        const to = plan[Math.min(index + 1, plan.length - 1)].joints
        shown = lerpJoints(from, to, Math.min(1, Math.max(0, blend)))
        setProgress(index / Math.max(1, plan.length - 1))
        setAngles(shown.map((r) => (r * 180) / Math.PI))
      }

      drawArm(shown)
      renderer.render(scene, camera)
    }
    drawArm(shown)
    tick()

    const onResize = () => {
      if (!mount) return
      camera.aspect = mount.clientWidth / mount.clientHeight
      camera.updateProjectionMatrix()
      renderer.setSize(mount.clientWidth, mount.clientHeight)
    }
    window.addEventListener('resize', onResize)

    // ドラッグで視点を回す
    let dragging = false
    let lastX = 0
    let lastY = 0
    let azimuth = Math.atan2(camera.position.x, -camera.position.y)
    let elevation = 0.28
    const radius = 155
    const applyCamera = () => {
      camera.position.set(
        radius * Math.sin(azimuth) * Math.cos(elevation),
        -radius * Math.cos(azimuth) * Math.cos(elevation),
        BOARD_Z + radius * Math.sin(elevation),
      )
      camera.lookAt(0, BOARD_Y * 0.5, BOARD_Z * 0.8)
    }
    applyCamera()
    const down = (e: PointerEvent) => { dragging = true; lastX = e.clientX; lastY = e.clientY }
    const move = (e: PointerEvent) => {
      if (!dragging) return
      azimuth += (e.clientX - lastX) * 0.006
      elevation = Math.max(-0.4, Math.min(1.1, elevation + (e.clientY - lastY) * 0.004))
      lastX = e.clientX; lastY = e.clientY
      applyCamera()
    }
    const up = () => { dragging = false }
    renderer.domElement.addEventListener('pointerdown', down)
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)

    return () => {
      disposed = true
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', onResize)
      renderer.domElement.removeEventListener('pointerdown', down)
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
      renderer.dispose()
      if (renderer.domElement.parentNode === mount) {
        mount.removeChild(renderer.domElement)
      }
    }
  }, [])

  const { facts } = ninePointConstruction()

  return (
    <main className="min-h-screen bg-[#0b0d0c] px-4 py-6 text-[#dfe6e2] sm:px-8">
      <div className="mx-auto max-w-6xl">
        <header className="mb-4 flex flex-wrap items-baseline justify-between gap-3">
          <div>
            <h1 className="text-lg tracking-[0.3em]">6軸アーム作図</h1>
            <p className="mt-1 text-xs text-[#7f9b8c]">
              九点円とオイラー線を、逆運動学で解いた関節角で実際に描いています
            </p>
          </div>
          <div className="text-xs text-[#7f9b8c]">
            {meta.steps} 工程 · 経由点 {meta.points} · 到達不能 {meta.unreachable}
          </div>
        </header>

        <div
          ref={mountRef}
          className="w-full overflow-hidden rounded border border-[#26302c]"
          style={{ height: '58vh', minHeight: 380, cursor: 'grab' }}
        />

        <div className="mt-3 h-1 w-full rounded bg-[#1b211e]">
          <div
            className="h-1 rounded bg-[#9fe0b0] transition-[width] duration-150"
            style={{ width: `${progress * 100}%` }}
          />
        </div>

        <div className="mt-3 grid gap-4 md:grid-cols-[1fr_auto]">
          <div>
            <div className="text-sm text-[#f2efe6]">{caption}</div>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
              <button
                onClick={() => setRunning((r) => !r)}
                className="rounded border border-[#31403a] px-3 py-1.5 hover:bg-[#18211d]"
              >
                {running ? '一時停止' : '再生'}
              </button>
              <button
                onClick={() => { resetRef.current = true; setRunning(true) }}
                className="rounded border border-[#31403a] px-3 py-1.5 hover:bg-[#18211d]"
              >
                最初から
              </button>
              <span className="ml-2 text-[#6f8a7d]">速さ</span>
              {[0.5, 1, 2, 4].map((s) => (
                <button
                  key={s}
                  onClick={() => setSpeed(s)}
                  className="rounded border px-2 py-1"
                  style={{
                    borderColor: speed === s ? '#9fe0b0' : '#31403a',
                    color: speed === s ? '#9fe0b0' : '#7f9b8c',
                  }}
                >
                  ×{s}
                </button>
              ))}
              <span className="ml-2 text-[#6f8a7d]">画面をドラッグで視点移動</span>
            </div>

            <div className="mt-4 grid grid-cols-3 gap-2 sm:grid-cols-6">
              {angles.map((deg, i) => (
                <div key={i} className="rounded border border-[#26302c] px-2 py-1.5">
                  <div className="text-[10px] tracking-widest text-[#6f8a7d]">
                    J{i + 1}
                  </div>
                  <div className="font-mono text-sm text-[#cfe6d8]">
                    {deg.toFixed(1)}°
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded border border-[#26302c] p-3 text-xs">
            <div className="mb-2 tracking-[0.2em] text-[#6f8a7d]">
              この図から切り出せる量
            </div>
            {facts.map((fact) => (
              <div key={fact.label} className="flex justify-between gap-6 py-0.5">
                <span className="text-[#9db5a8]">{fact.label}</span>
                <span className="font-mono text-[#ffd79a]">{fact.value}</span>
              </div>
            ))}
            <div className="mt-3 border-t border-[#26302c] pt-2 text-[10px] leading-relaxed text-[#6f8a7d]">
              手首3軸が1点で交わる球面手首（Pieper の条件）なので、
              位置は J1–J3、姿勢は J4–J6 に分離して閉形式で解けます。
            </div>
          </div>
        </div>
      </div>
    </main>
  )
}
