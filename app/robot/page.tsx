'use client'

/**
 * 6軸アームが黒板と空間に作図する。
 *
 * 3つが本物であることが要点:
 *   1. 姿勢  — 逆運動学は球面手首の decoupling で閉形式に解いている
 *   2. 軌道  — 関節角は最小ジャーク spline（節点で4階微分まで連続）で繋ぐ
 *   3. 筆跡  — 描く線は順運動学で出したペン先の位置そのもの
 * 画面の線は「アームが通った跡」であって、別に用意した図をなぞってはいない。
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import { ARM, forwardAll, positionOf } from '@/lib/kinematics'
import { FIGURES, figureComplexity } from '@/lib/figures'
import { sampleAt } from '@/lib/trajectory'
import { buildPlan } from '@/lib/plan'

function orientSegment(mesh: THREE.Mesh, a: THREE.Vector3, b: THREE.Vector3) {
  const direction = new THREE.Vector3().subVectors(b, a)
  const length = direction.length()
  if (length < 1e-6) { mesh.visible = false; return }
  mesh.visible = true
  mesh.position.copy(a).addScaledVector(direction, 0.5)
  mesh.scale.set(1, length, 1)
  mesh.quaternion.setFromUnitVectors(
    new THREE.Vector3(0, 1, 0), direction.clone().normalize(),
  )
}

export default function RobotPage() {
  const mountRef = useRef<HTMLDivElement>(null)
  const [figureIndex, setFigureIndex] = useState(0)
  const [speed, setSpeed] = useState(1)
  const [running, setRunning] = useState(true)
  const [angles, setAngles] = useState<number[]>([0, 0, 0, 0, 0, 0])
  const [jerk, setJerk] = useState(0)
  const [caption, setCaption] = useState('準備中')
  const [progress, setProgress] = useState(0)
  const [stats, setStats] = useState({
    points: 0, unreachable: 0, seconds: 0,
    peak: { speed: 0, acceleration: 0, jerk: 0 },
  })

  const speedRef = useRef(1)
  const runningRef = useRef(true)
  const resetRef = useRef(false)
  useEffect(() => { speedRef.current = speed }, [speed])
  useEffect(() => { runningRef.current = running }, [running])

  const figure = FIGURES[figureIndex]
  const complexity = useMemo(() => figureComplexity(figure), [figure])

  useEffect(() => {
    const mount = mountRef.current
    if (!mount) return

    const plan = buildPlan(figure)
    setStats({
      points: plan.waypoints.length,
      unreachable: plan.unreachable,
      seconds: plan.total,
      peak: plan.peak,
    })

    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0x0a0c0b)
    const camera = new THREE.PerspectiveCamera(
      42, mount.clientWidth / mount.clientHeight, 0.1, 1200,
    )
    camera.up.set(0, 0, 1)
    // ?export=1 のときは書き出しモード。requestAnimationFrame は画面が
    // 表示されていないと止まるので、時間を自分で刻んで 1 枚ずつ PNG にする。
    // toDataURL を使うので preserveDrawingBuffer が要る。
    const exporting =
      typeof window !== 'undefined' &&
      new URLSearchParams(window.location.search).get('export') === '1'
    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      preserveDrawingBuffer: exporting,
    })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.setSize(mount.clientWidth, mount.clientHeight)
    mount.appendChild(renderer.domElement)

    scene.add(new THREE.AmbientLight(0xffffff, 0.55))
    const key = new THREE.DirectionalLight(0xffffff, 1.15)
    key.position.set(70, -90, 130)
    scene.add(key)
    const rim = new THREE.DirectionalLight(0x88bbff, 0.45)
    rim.position.set(-80, -50, 40)
    scene.add(rim)

    const board = new THREE.Mesh(
      new THREE.PlaneGeometry(124, 88),
      new THREE.MeshStandardMaterial({ color: 0x1f2d27, roughness: 0.96 }),
    )
    board.position.set(0, 55.8, 46)
    board.rotation.x = Math.PI / 2
    scene.add(board)
    const frame = new THREE.Mesh(
      new THREE.BoxGeometry(130, 2.2, 94),
      new THREE.MeshStandardMaterial({ color: 0x6b4a2c, roughness: 0.8 }),
    )
    frame.position.set(0, 57.4, 46)
    scene.add(frame)
    const base = new THREE.Mesh(
      new THREE.CylinderGeometry(11, 13, 6, 40),
      new THREE.MeshStandardMaterial({ color: 0x2a2f33, roughness: 0.5, metalness: 0.65 }),
    )
    base.position.set(0, 0, 3)
    base.rotation.x = Math.PI / 2
    scene.add(base)
    scene.add(new THREE.Mesh(
      new THREE.PlaneGeometry(500, 500),
      new THREE.MeshStandardMaterial({ color: 0x101312, roughness: 1 }),
    ))

    const linkMaterial = new THREE.MeshStandardMaterial({
      color: 0xd8dde0, roughness: 0.35, metalness: 0.78,
    })
    const jointMaterial = new THREE.MeshStandardMaterial({
      color: 0xffb454, roughness: 0.4, metalness: 0.45,
    })
    const links: THREE.Mesh[] = []
    const joints: THREE.Mesh[] = []
    for (let i = 0; i < ARM.length; i++) {
      const link = new THREE.Mesh(
        new THREE.CylinderGeometry(2.6 - i * 0.22, 2.6 - i * 0.22, 1, 20), linkMaterial,
      )
      scene.add(link); links.push(link)
      const joint = new THREE.Mesh(
        new THREE.CylinderGeometry(3.4 - i * 0.28, 3.4 - i * 0.28, 3.2, 24), jointMaterial,
      )
      scene.add(joint); joints.push(joint)
    }
    const pen = new THREE.Mesh(
      new THREE.ConeGeometry(1.1, 5, 16),
      new THREE.MeshStandardMaterial({ color: 0xfff3d0, emissive: 0x554422 }),
    )
    scene.add(pen)

    const inkGroup = new THREE.Group()
    scene.add(inkGroup)
    const inkColors = [0xf6f2e7, 0x9fe0b0, 0xffd79a, 0x8fd0ff, 0xffa8c0]
    let currentLine: THREE.Line | null = null
    let currentCount = 0
    let lastStroke = -1

    const startLine = (strokeIndex: number) => {
      const geometry = new THREE.BufferGeometry()
      geometry.setAttribute('position',
        new THREE.BufferAttribute(new Float32Array(9000), 3))
      geometry.setDrawRange(0, 0)
      currentLine = new THREE.Line(geometry, new THREE.LineBasicMaterial({
        color: inkColors[strokeIndex % inkColors.length],
      }))
      currentCount = 0
      inkGroup.add(currentLine)
    }
    /** ペン先の実位置を筆跡に足す（図をなぞるのではなく腕の跡を残す） */
    const pushInk = (v: THREE.Vector3) => {
      if (!currentLine || currentCount >= 2900) return
      const attribute = currentLine.geometry.getAttribute('position') as THREE.BufferAttribute
      attribute.array[currentCount * 3] = v.x
      attribute.array[currentCount * 3 + 1] = v.y
      attribute.array[currentCount * 3 + 2] = v.z
      currentCount++
      attribute.needsUpdate = true
      currentLine.geometry.setDrawRange(0, currentCount)
    }

    let elapsed = 0
    let raf = 0
    let disposed = false
    let lastNow = performance.now()

    const drawArm = (jointAngles: number[]) => {
      const frames = forwardAll(jointAngles)
      let previous = new THREE.Vector3(0, 0, 0)
      frames.forEach((m, i) => {
        const p = positionOf(m)
        const point = new THREE.Vector3(p[0], p[1], p[2])
        orientSegment(links[i], previous, point)
        joints[i].position.copy(point)
        const axis = new THREE.Vector3(m[2], m[6], m[10]).normalize()
        joints[i].quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), axis)
        previous = point
      })
      const last = frames[frames.length - 1]
      const dir = new THREE.Vector3(last[2], last[6], last[10]).normalize()
      pen.position.copy(previous).addScaledVector(dir, -2.5)
      pen.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir)
      return previous
    }

    const tick = () => {
      if (disposed) return
      raf = requestAnimationFrame(tick)
      const now = performance.now()
      const dt = Math.min(0.05, (now - lastNow) / 1000)
      lastNow = now

      if (resetRef.current) {
        resetRef.current = false
        elapsed = 0
        lastStroke = -1
        currentLine = null
        inkGroup.clear()
      }
      if (runningRef.current && elapsed < plan.total) {
        elapsed = Math.min(plan.total, elapsed + dt * speedRef.current)
      }

      const sample = sampleAt(plan.perJoint, plan.durations, elapsed)
      const marker = plan.markers[Math.min(sample.segment, plan.markers.length - 1)]
      const tip = drawArm(sample.joints)

      if (marker?.penDown) {
        if (marker.stroke !== lastStroke) {
          lastStroke = marker.stroke
          startLine(marker.stroke)
          setCaption(`${marker.stroke + 1}. ${marker.label}`)
        }
        pushInk(tip)
      }
      setAngles(sample.joints.map((r) => (r * 180) / Math.PI))
      setJerk(Math.max(...sample.jerk.map(Math.abs)))
      setProgress(plan.total ? elapsed / plan.total : 0)

      renderer.render(scene, camera)
    }

    // 視点
    let azimuth = 0.55
    let elevation = 0.3
    let radius = figure.dimension === 3 ? 150 : 165
    const applyCamera = () => {
      camera.position.set(
        radius * Math.sin(azimuth) * Math.cos(elevation),
        -radius * Math.cos(azimuth) * Math.cos(elevation),
        30 + radius * Math.sin(elevation),
      )
      camera.lookAt(0, figure.dimension === 3 ? 24 : 34, 38)
    }
    applyCamera()

    /**
     * 書き出し: 時間を固定間隔で刻み、1 枚ずつ PNG にして API へ送る。
     *
     * ただの記録ではなく、見せ方を作る。この図の驚きは
     * 「無関係に見える 9 点が 1 つの円に乗る」ことなので、
     *   序盤  引きで作図の全体を見せる
     *   中盤  寄っていく（点が増えていくのを近くで見せる）
     *   終盤  円が 9 点を貫くところで最も寄る
     *   最後  少し引いて完成図を回しながら見せる
     * というカメラ運びにする。
     */
    const runExport = async () => {
      const fps = 30
      const step = 1 / fps
      const holdSeconds = 3.5           // 完成図を見せる尺
      const drawSeconds = 26.5          // 作図の尺
      const session = figure.id
      const speed = plan.total / drawSeconds
      let index = 0

      const easeInOut = (u: number) =>
        u < 0.5 ? 2 * u * u : 1 - Math.pow(-2 * u + 2, 2) / 2

      // 図の中心を実際に計算して、そこを見る。
      // 原点を見ていると被写体が画面の端に寄って小さくなる。
      const centre = new THREE.Vector3()
      let count = 0
      for (const stroke of figure.strokes) {
        for (const p of stroke.points) {
          centre.add(new THREE.Vector3(p.x, p.y, p.z))
          count++
        }
      }
      if (count) centre.multiplyScalar(1 / count)

      /** 進行度 0→1 に対するカメラ */
      const choreograph = (u: number, dist: number, az: number, el: number) => {
        camera.position.set(
          centre.x + dist * Math.sin(az) * Math.cos(el),
          centre.y - dist * Math.cos(az) * Math.cos(el),
          centre.z + dist * Math.sin(el),
        )
        camera.lookAt(centre)
      }

      const shot = (u: number) => {
        const e = easeInOut(Math.min(1, Math.max(0, u)))
        // 引き 120 → 寄り 62
        choreograph(u, 120 - 58 * e, 0.28 + 0.50 * e, 0.30 - 0.14 * e)
      }

      const shoot = async () => {
        renderer.render(scene, camera)
        const dataUrl = renderer.domElement.toDataURL('image/png')
        await fetch('/api/frames', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ index, dataUrl, session }),
        })
        index++
      }

      elapsed = 0
      for (let t = 0; t <= plan.total; t += step * speed) {
        if (disposed) return
        elapsed = t
        const sample = sampleAt(plan.perJoint, plan.durations, elapsed)
        const marker = plan.markers[Math.min(sample.segment, plan.markers.length - 1)]
        const tip = drawArm(sample.joints)
        if (marker?.penDown) {
          if (marker.stroke !== lastStroke) {
            lastStroke = marker.stroke
            startLine(marker.stroke)
          }
          pushInk(tip)
        }
        shot(t / plan.total)
        await shoot()
        setProgress(t / plan.total)
        setCaption(`書き出し中 ${index} 枚`)
      }

      // 完成図を回しながら見せる。腕は邪魔なので隠す。
      links.forEach((m) => { m.visible = false })
      joints.forEach((m) => { m.visible = false })
      pen.visible = false
      const holdFrames = Math.round(holdSeconds * fps)
      for (let i = 0; i < holdFrames; i++) {
        if (disposed) return
        const u = i / holdFrames
        // 完成図をゆっくり回して見せる
        choreograph(u, 64 - 4 * Math.sin(u * Math.PI), 0.78 + 0.34 * u, 0.16 + 0.06 * u)
        await shoot()
      }
      setCaption(`書き出し完了 ${index} 枚（${session}）`)
    }

    if (exporting) {
      void runExport()
    } else {
      tick()
    }

    const onResize = () => {
      camera.aspect = mount.clientWidth / mount.clientHeight
      camera.updateProjectionMatrix()
      renderer.setSize(mount.clientWidth, mount.clientHeight)
    }
    window.addEventListener('resize', onResize)
    let dragging = false
    let lastX = 0, lastY = 0
    const down = (e: PointerEvent) => { dragging = true; lastX = e.clientX; lastY = e.clientY }
    const move = (e: PointerEvent) => {
      if (!dragging) return
      azimuth += (e.clientX - lastX) * 0.006
      elevation = Math.max(-0.45, Math.min(1.15, elevation + (e.clientY - lastY) * 0.004))
      lastX = e.clientX; lastY = e.clientY
      applyCamera()
    }
    const up = () => { dragging = false }
    const wheel = (e: WheelEvent) => {
      e.preventDefault()
      radius = Math.max(70, Math.min(300, radius + e.deltaY * 0.15))
      applyCamera()
    }
    renderer.domElement.addEventListener('pointerdown', down)
    renderer.domElement.addEventListener('wheel', wheel, { passive: false })
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)

    return () => {
      disposed = true
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', onResize)
      renderer.domElement.removeEventListener('pointerdown', down)
      renderer.domElement.removeEventListener('wheel', wheel)
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
      renderer.dispose()
      if (renderer.domElement.parentNode === mount) {
        mount.removeChild(renderer.domElement)
      }
    }
  }, [figure])

  const selectFigure = useCallback((index: number) => {
    setFigureIndex(index)
    setRunning(true)
    setProgress(0)
  }, [])

  return (
    <main className="min-h-screen bg-[#0a0c0b] px-4 py-6 text-[#dfe6e2] sm:px-8">
      <div className="mx-auto max-w-6xl">
        <header className="mb-3">
          <h1 className="text-lg tracking-[0.3em]">6軸アーム作図</h1>
          <p className="mt-1 text-xs text-[#7f9b8c]">
            逆運動学（球面手首の閉形式）＋ 最小ジャーク軌道。線はペン先が通った跡です。
          </p>
        </header>

        <div className="mb-3 flex flex-wrap gap-1.5 text-xs">
          {FIGURES.map((f, i) => (
            <button
              key={f.id}
              onClick={() => selectFigure(i)}
              className="rounded border px-2.5 py-1"
              style={{
                borderColor: i === figureIndex ? '#9fe0b0' : '#2b3833',
                color: i === figureIndex ? '#9fe0b0' : '#8b9a92',
                background: i === figureIndex ? '#16211c' : 'transparent',
              }}
            >
              {f.dimension === 3 ? '立体 ' : ''}{f.title}
            </button>
          ))}
        </div>

        <div
          ref={mountRef}
          className="w-full overflow-hidden rounded border border-[#26302c]"
          style={{ height: '56vh', minHeight: 360, cursor: 'grab' }}
        />

        <div className="mt-2 h-1 w-full rounded bg-[#1b211e]">
          <div className="h-1 rounded bg-[#9fe0b0]"
            style={{ width: `${progress * 100}%` }} />
        </div>

        <div className="mt-3 grid gap-4 md:grid-cols-[1fr_300px]">
          <div>
            <div className="text-sm text-[#f2efe6]">{caption}</div>
            <div className="mt-1 text-[11px] text-[#6f8a7d]">
              作図 {complexity.operations} 工程（印 {complexity.marks} / 補助線{' '}
              {complexity.auxiliary}）· 経由点 {stats.points} · 到達不能{' '}
              {stats.unreachable} · 総時間 {stats.seconds.toFixed(1)}s
            </div>

            <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
              <button onClick={() => setRunning((r) => !r)}
                className="rounded border border-[#31403a] px-3 py-1.5 hover:bg-[#18211d]">
                {running ? '一時停止' : '再生'}
              </button>
              <button onClick={() => { resetRef.current = true; setRunning(true) }}
                className="rounded border border-[#31403a] px-3 py-1.5 hover:bg-[#18211d]">
                最初から
              </button>
              <span className="ml-1 text-[#6f8a7d]">速さ</span>
              {[0.5, 1, 2, 4, 8].map((s) => (
                <button key={s} onClick={() => setSpeed(s)}
                  className="rounded border px-2 py-1"
                  style={{
                    borderColor: speed === s ? '#9fe0b0' : '#31403a',
                    color: speed === s ? '#9fe0b0' : '#7f9b8c',
                  }}>×{s}</button>
              ))}
              <span className="ml-1 text-[#6f8a7d]">
                ドラッグで視点 · ホイールで寄り引き
              </span>
            </div>

            <div className="mt-3 grid grid-cols-3 gap-2 sm:grid-cols-6">
              {angles.map((deg, i) => (
                <div key={i} className="rounded border border-[#26302c] px-2 py-1.5">
                  <div className="text-[10px] tracking-widest text-[#6f8a7d]">J{i + 1}</div>
                  <div className="font-mono text-sm text-[#cfe6d8]">{deg.toFixed(1)}°</div>
                </div>
              ))}
            </div>
            <div className="mt-2 text-[11px] leading-relaxed text-[#6f8a7d]">
              現在のジャーク{' '}
              <span className="font-mono text-[#ffd79a]">{jerk.toFixed(1)}</span>
              {' '}rad/s³　·　軌道全体のピーク 速度{' '}
              <span className="font-mono text-[#cfe6d8]">
                {stats.peak.speed.toFixed(2)}
              </span>{' '}rad/s ／ 加速度{' '}
              <span className="font-mono text-[#cfe6d8]">
                {stats.peak.acceleration.toFixed(1)}
              </span>{' '}rad/s²
              <br />
              節点で位置・速度・加速度・ジャーク・スナップまで連続しているので、
              段差なく繋がります。
            </div>
          </div>

          <div className="rounded border border-[#26302c] p-3 text-xs">
            <div className="mb-2 tracking-[0.2em] text-[#6f8a7d]">
              この図から切り出せる量
            </div>
            {figure.facts.map((fact) => (
              <div key={fact.label} className="flex justify-between gap-4 py-0.5">
                <span className="text-[#9db5a8]">{fact.label}</span>
                <span className="text-right font-mono text-[#ffd79a]">{fact.value}</span>
              </div>
            ))}
            <div className="mt-3 border-t border-[#26302c] pt-2 text-[10px] leading-relaxed text-[#6f8a7d]">
              対応する MathOS の族:
              <div className="mt-1 space-y-0.5 font-mono text-[#7fa891]">
                {figure.families.map((family) => <div key={family}>{family}</div>)}
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  )
}
