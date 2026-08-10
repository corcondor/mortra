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
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js'
import { Line2 } from 'three/examples/jsm/lines/Line2.js'
import { LineGeometry } from 'three/examples/jsm/lines/LineGeometry.js'
import { LineMaterial } from 'three/examples/jsm/lines/LineMaterial.js'
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

  // ?figure=<id> で図を指定できる。書き出しを図ごとに回すために使う。
  useEffect(() => {
    const wanted = new URLSearchParams(window.location.search).get('figure')
    if (!wanted) return
    const index = FIGURES.findIndex((f) => f.id === wanted)
    if (index >= 0) setFigureIndex(index)
  }, [])

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

    /*
     * 配色。
     *
     * 以前は板が暗い青緑、枠が茶、関節がオレンジ、床が灰、インクが5色だった。
     * 色数が多いと 3D ソフトの既定マテリアルをそのまま出したように見える。
     * 実際そう見えていた。白と黒だけに畳む。
     *
     *   board … 黒板。背景が黒、線が白
     *   paper … iPad のノート。背景が白、線が黒
     *
     * ?theme=board で切り替える。既定は paper。
     */
    const theme =
      typeof window !== 'undefined' &&
      new URLSearchParams(window.location.search).get('theme') === 'board'
        ? 'board' : 'paper'
    const P = theme === 'board'
      ? {
          bg: 0x000000, surface: 0x080808, ground: 0x000000,
          body: 0xf2f2f2, accent: 0x141414, ink: 0xffffff,
          surfaceRough: 0.92, exposure: 1.0,
        }
      : {
          // 白い紙の上では、腕は暗くないと消える。黒板とは明暗を入れ替える。
          bg: 0xffffff, surface: 0xffffff, ground: 0xffffff,
          body: 0x1c1c1c, accent: 0xf2f2f2, ink: 0x111111,
          surfaceRough: 1.0, exposure: 1.55,
        }

    const scene = new THREE.Scene()
    scene.background = new THREE.Color(P.bg)
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
    // 書き出しは画面の大きさに依存させない。リールは 1080×1920 固定。
    // 以前はウィンドウの形をそのまま使っていたので、横長の窓で書き出すと
    // 横長の動画が出てしまった。
    const OUT_W = 1080
    const OUT_H = 1920
    const viewW = exporting ? OUT_W : mount.clientWidth
    const viewH = exporting ? OUT_H : mount.clientHeight
    camera.aspect = viewW / viewH
    camera.updateProjectionMatrix()
    renderer.setPixelRatio(exporting ? 1 : Math.min(window.devicePixelRatio, 2))
    renderer.setSize(viewW, viewH, !exporting)
    // 金属を金属に見せるには映り込みが要る。露出とトーンマッピングを
    // 決めないとハイライトが白飛びして、樹脂のような平坦な面になる。
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = P.exposure
    renderer.shadowMap.enabled = true
    renderer.shadowMap.type = THREE.PCFSoftShadowMap
    mount.appendChild(renderer.domElement)

    // 環境マップ。metalness の高い材質は周囲を映すことでしか金属に見えない。
    // これが無いと roughness をいくら下げても暗い灰色の塊にしかならない。
    const pmrem = new THREE.PMREMGenerator(renderer)
    const environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture
    scene.environment = environment

    // 環境光は落とす。環境マップが回り込みを担うので、
    // AmbientLight を強くすると陰影が消えて平坦になる。
    scene.add(new THREE.AmbientLight(0xffffff, theme === 'paper' ? 0.55 : 0.12))
    const key = new THREE.DirectionalLight(0xffffff, theme === 'paper' ? 1.5 : 2.1)
    key.position.set(70, -90, 130)
    key.castShadow = true
    key.shadow.mapSize.set(2048, 2048)
    key.shadow.camera.near = 20
    key.shadow.camera.far = 400
    key.shadow.camera.left = -120
    key.shadow.camera.right = 120
    key.shadow.camera.top = 120
    key.shadow.camera.bottom = -120
    key.shadow.bias = -0.0009
    key.shadow.normalBias = 0.4
    scene.add(key)
    // リムも返しも白にする。青いリムと橙の返しを入れていたが、
    // 白黒の画面に色付きの光を足すと、そこだけ色が乗って濁る。
    const rim = new THREE.DirectionalLight(0xffffff, theme === 'paper' ? 0.5 : 1.1)
    rim.position.set(-80, -50, 40)
    scene.add(rim)
    const bounce = new THREE.DirectionalLight(0xffffff, 0.35)
    bounce.position.set(10, 60, -40)
    scene.add(bounce)

    // 黒板は完全なマットにしない。わずかな光沢があると面の向きが読めて、
    // 板が「空間に置かれた物」に見える。
    const board = new THREE.Mesh(
      new THREE.PlaneGeometry(124, 88),
      new THREE.MeshStandardMaterial({
        color: P.surface, roughness: P.surfaceRough, metalness: 0.0,
        envMapIntensity: 0.2,
      }),
    )
    board.position.set(0, 55.8, 46)
    board.rotation.x = Math.PI / 2
    board.receiveShadow = true
    scene.add(board)

    // 紙の見え方には枠が要らない。黒板のときだけ細い縁を出す。
    if (theme === 'board') {
      const frame = new THREE.Mesh(
        new THREE.BoxGeometry(130, 2.2, 94),
        new THREE.MeshStandardMaterial({
          color: P.accent, roughness: 0.7, metalness: 0.0, envMapIntensity: 0.3,
        }),
      )
      frame.position.set(0, 57.4, 46)
      frame.castShadow = true
      frame.receiveShadow = true
      scene.add(frame)
    }

    // 金属らしさを metalness で出すのをやめた。metalness を上げると
    // 環境マップの色が乗って、白黒の画面に灰色と色被りが出る。
    // 艶消しの単色にして、形と影で立体を見せる。
    const darkMetal = new THREE.MeshStandardMaterial({
      color: P.accent, roughness: 0.5, metalness: 0.1, envMapIntensity: 0.5,
    })
    // 台座は円柱の素置きではなく、段を付けて機械らしい輪郭にする
    const pedestal = new THREE.Group()
    const plinth = new THREE.Mesh(new THREE.CylinderGeometry(13, 14.5, 2.6, 64), darkMetal)
    plinth.position.y = 1.3
    const column = new THREE.Mesh(new THREE.CylinderGeometry(10.4, 11.6, 4.6, 64), darkMetal)
    column.position.y = 4.9
    const collar = new THREE.Mesh(new THREE.TorusGeometry(10.4, 0.55, 16, 64), darkMetal)
    collar.rotation.x = Math.PI / 2
    collar.position.y = 7.2
    for (const m of [plinth, column, collar]) {
      m.castShadow = true; m.receiveShadow = true; pedestal.add(m)
    }
    pedestal.rotation.x = Math.PI / 2
    scene.add(pedestal)

    const ground = new THREE.Mesh(
      new THREE.PlaneGeometry(500, 500),
      new THREE.MeshStandardMaterial({
        color: P.ground, roughness: 0.95, metalness: 0.0, envMapIntensity: 0.15,
      }),
    )
    ground.receiveShadow = true
    scene.add(ground)

    // 関節のオレンジをやめる。白い本体に黒い関節、それだけ。
    const linkMaterial = new THREE.MeshStandardMaterial({
      color: P.body, roughness: 0.42, metalness: 0.08, envMapIntensity: 0.55,
    })
    const jointMaterial = new THREE.MeshStandardMaterial({
      color: P.accent, roughness: 0.44, metalness: 0.08, envMapIntensity: 0.5,
    })
    const links: THREE.Mesh[] = []
    const joints: THREE.Object3D[] = []
    for (let i = 0; i < ARM.length; i++) {
      const radius = 2.6 - i * 0.22
      const link = new THREE.Mesh(
        new THREE.CylinderGeometry(radius, radius, 1, 32), linkMaterial,
      )
      link.castShadow = true
      scene.add(link); links.push(link)

      // 関節は伸縮しないので、ここに機械らしいディテールを持たせる。
      // 面取りのリングがあるだけで、輪郭に沿ってハイライトが走り、
      // 「円柱を並べただけ」に見えなくなる。
      const jointRadius = 3.4 - i * 0.28
      const housing = new THREE.Group()
      const barrel = new THREE.Mesh(
        new THREE.CylinderGeometry(jointRadius, jointRadius, 3.2, 40), jointMaterial,
      )
      housing.add(barrel)
      for (const sign of [1, -1]) {
        const rim = new THREE.Mesh(
          new THREE.TorusGeometry(jointRadius * 0.98, 0.3, 12, 40), linkMaterial,
        )
        rim.rotation.x = Math.PI / 2
        rim.position.y = sign * 1.6
        housing.add(rim)
        const cap = new THREE.Mesh(
          new THREE.CylinderGeometry(jointRadius * 0.62, jointRadius * 0.62, 3.5, 32),
          linkMaterial,
        )
        housing.add(cap)
      }
      housing.traverse((o) => {
        if ((o as THREE.Mesh).isMesh) { o.castShadow = true; o.receiveShadow = true }
      })
      scene.add(housing); joints.push(housing)
    }

    // ペンは円錐の素置きをやめる。軸・金具・芯の3段にすると
    // 「筆記具」として読めるようになる。
    // 芯の先端をローカル原点に置く。こうすると pen.position が
    // そのまま筆跡の点になり、位置合わせの補正値が要らない。
    const pen = new THREE.Group()
    const penBarrel = new THREE.Mesh(
      new THREE.CylinderGeometry(1.05, 1.15, 6.2, 24),
      new THREE.MeshStandardMaterial({
        color: P.body, roughness: 0.45, metalness: 0.08, envMapIntensity: 0.5,
      }),
    )
    penBarrel.position.y = -6.5
    // 金の口金をやめる。白黒の中で金属色はそこだけ浮く。
    const ferrule = new THREE.Mesh(
      new THREE.CylinderGeometry(0.72, 1.05, 1.4, 24),
      new THREE.MeshStandardMaterial({
        color: P.accent, roughness: 0.4, metalness: 0.1, envMapIntensity: 0.5,
      }),
    )
    ferrule.position.y = -2.7
    // 芯はインクと同じ色。何で書いているかが一目で繋がる。
    const nib = new THREE.Mesh(
      new THREE.ConeGeometry(0.72, 2.0, 20),
      new THREE.MeshStandardMaterial({ color: P.ink, roughness: 0.6 }),
    )
    nib.position.y = -1.0
    for (const m of [penBarrel, ferrule, nib]) { m.castShadow = true; pen.add(m) }
    scene.add(pen)

    const inkGroup = new THREE.Group()
    scene.add(inkGroup)
    // 5色で描き分けていたが、色が増えるほど図が散らかって見えた。
    // 1色に固定し、区別は太さと発光で付ける。
    const inkColors = [P.ink]
    let currentCount = 0
    let lastStroke = -1

    /*
     * 線の太さについて。
     *
     * THREE.Line は WebGL の制約で 1px 固定になるため、以前は同じ線を
     * 11 本わずかにずらして重ね、太さを偽装していた。これが失敗だった。
     * ずらした複製どうしが視点によって重ならず、輪郭が二重三重にぶれて、
     * 手が震えているように見えていた（「ふなふな」の正体）。
     *
     * Line2 は線を実際の板ポリゴンとして押し出すので、太さが本物になり、
     * 継ぎ目も正しく繋がる。1 本の線につきコア 1 本と発光 1 本で足りる。
     */
    const MAX_POINTS = 2900
    const inkMaterials: LineMaterial[] = []

    const makeInkMaterial = (color: number, width: number, glow: boolean) => {
      const material = new LineMaterial({
        color,
        linewidth: width,
        worldUnits: true,          // 太さを世界座標で持つ。寄っても破綻しない
        alphaToCoverage: true,
        transparent: glow,
        // 黒板では加算で発光させる（チョークの滲み）。
        // 紙では加算すると黒インクが明るくなって消えるので、
        // 同じ色を薄く重ねて滲みだけ作る。
        opacity: glow ? (theme === 'board' ? 0.16 : 0.10) : 1,
        blending: glow && theme === 'board'
          ? THREE.AdditiveBlending : THREE.NormalBlending,
        depthWrite: !glow,
      })
      material.resolution.set(viewW, viewH)
      inkMaterials.push(material)
      return material
    }

    type InkStroke = { core: Line2; glow: Line2 }
    let currentInk: InkStroke | null = null
    const previousInk = new THREE.Vector3()

    const startLine = (strokeIndex: number) => {
      const color = inkColors[strokeIndex % inkColors.length]
      const build = (width: number, glow: boolean) => {
        const geometry = new LineGeometry()
        // 実際の点が入る前に器だけ確保する。setPositions は
        // 内部で (点数-1) 本ぶんの区間バッファを作る。
        geometry.setPositions(new Float32Array(MAX_POINTS * 3))
        geometry.instanceCount = 0
        const line = new Line2(geometry, makeInkMaterial(color, width, glow))
        line.frustumCulled = false   // 器が原点に潰れているので切られないようにする
        inkGroup.add(line)
        return line
      }
      // 太さは世界座標。図だけなら 0.20 でよいが、字を書くと潰れる。
      // 「題」は 18 画。1 字 5 単位なら画の間隔は 0.28 しかない。
      currentInk = { core: build(0.075, false), glow: build(0.22, true) }
      currentCount = 0
    }

    /** ペン先の実位置を筆跡に足す（図をなぞるのではなく腕の跡を残す） */
    const pushInk = (v: THREE.Vector3) => {
      if (!currentInk || currentCount >= MAX_POINTS) return
      if (currentCount > 0) {
        // 区間 i は 点[i] と 点[i+1] を結ぶ。バッファは stride 6 の
        // インターリーブで、前半 3 が始点、後半 3 が終点。
        const segment = currentCount - 1
        for (const line of [currentInk.core, currentInk.glow]) {
          const attribute = line.geometry.getAttribute('instanceStart') as THREE.InterleavedBufferAttribute
          const array = attribute.data.array as Float32Array
          const base = segment * 6
          if (segment === 0) {
            array[base] = previousInk.x
            array[base + 1] = previousInk.y
            array[base + 2] = previousInk.z
          } else {
            array[base] = array[base - 3]
            array[base + 1] = array[base - 2]
            array[base + 2] = array[base - 1]
          }
          array[base + 3] = v.x
          array[base + 4] = v.y
          array[base + 5] = v.z
          attribute.data.needsUpdate = true
          line.geometry.instanceCount = currentCount
        }
      }
      previousInk.copy(v)
      currentCount++
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
      // 芯の先端がローカル原点なので、ペン先の位置をそのまま入れる
      pen.position.copy(previous)
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
        currentInk = null
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
      // 距離を数値で決め打ちしていたので、図ごとに画面からはみ出していた。
      // 外接箱を測り、縦横の画角から「収まる距離」を計算する。
      const box = new THREE.Box3()
      for (const stroke of figure.strokes) {
        for (const p of stroke.points) box.expandByPoint(new THREE.Vector3(p.x, p.y, p.z))
      }
      const centre = box.getCenter(new THREE.Vector3())
      const size = box.getSize(new THREE.Vector3())

      const vFov = (camera.fov * Math.PI) / 180
      const hFov = 2 * Math.atan(Math.tan(vFov / 2) * camera.aspect)
      /** 図が収まる距離。margin は余白の倍率 */
      const fitDistance = (margin: number) => {
        const halfH = Math.max(size.z, size.y) / 2
        const halfW = Math.max(size.x, size.y) / 2
        return margin * Math.max(
          halfH / Math.tan(vFov / 2),
          halfW / Math.tan(hFov / 2),
        )
      }
      const far = fitDistance(1.55)
      const near = fitDistance(1.15)

      /** 進行度 0→1 に対するカメラ */
      const choreograph = (u: number, dist: number, az: number, el: number) => {
        camera.position.set(
          centre.x + dist * Math.sin(az) * Math.cos(el),
          centre.y - dist * Math.cos(az) * Math.cos(el),
          centre.z + dist * Math.sin(el),
        )
        camera.lookAt(centre)
      }

      // 平面図はノートを覗き込む角度に寄せる。斜め45度から見ると
      // 板が台形に潰れて、何が描かれているか読めなくなる。
      const flat = figure.dimension === 2
      const azFrom = flat ? 0.10 : 0.28
      const azTo = flat ? 0.30 : 0.72
      const elFrom = flat ? 0.12 : 0.30
      const elTo = flat ? 0.06 : 0.18

      const shot = (u: number) => {
        const e = easeInOut(Math.min(1, Math.max(0, u)))
        choreograph(u, far + (near - far) * e,
          azFrom + (azTo - azFrom) * e, elFrom + (elTo - elFrom) * e)
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
        if (figure.dimension === 3) {
          // 立体は「figure 自体を回す」。カメラを一周させると黒板を
          // 突き抜けて真っ茶色の画になる（実際にそうなった）。
          // 描いた線は世界座標で持っているので、重心まわりの回転を
          // group の position で打ち消して与える。
          const angle = 2 * Math.PI * u
          const cos = Math.cos(angle)
          const sin = Math.sin(angle)
          inkGroup.rotation.z = angle
          inkGroup.position.set(
            centre.x - (centre.x * cos - centre.y * sin),
            centre.y - (centre.x * sin + centre.y * cos),
            0,
          )
          choreograph(u, 74, 0.52, 0.20)
        } else {
          choreograph(u, 64 - 4 * Math.sin(u * Math.PI), 0.78 + 0.34 * u, 0.16 + 0.06 * u)
        }
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
      if (exporting) return   // 書き出し中は 1080×1920 のまま動かさない
      camera.aspect = mount.clientWidth / mount.clientHeight
      camera.updateProjectionMatrix()
      renderer.setSize(mount.clientWidth, mount.clientHeight)
      // Line2 は太さを画面解像度から逆算するので、伝え忘れると線が消える
      for (const material of inkMaterials) {
        material.resolution.set(mount.clientWidth, mount.clientHeight)
      }
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
