'use client'

import Link from 'next/link'
import { useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { Line2 } from 'three/examples/jsm/lines/Line2.js'
import { LineGeometry } from 'three/examples/jsm/lines/LineGeometry.js'
import { LineMaterial } from 'three/examples/jsm/lines/LineMaterial.js'

import demoData from '@/data/euclidean-construction-demo.json'
import experimentData from '@/data/euclidean-construction-experiment.json'
import {
  constructionDrawingPaths,
  type ConstructionPlan,
} from '@/lib/mortra/construction/euclidean-construction'
import {
  buildTorusCircleFamily,
  spatialCirclePaths,
} from '@/lib/mortra/construction/spatial-circle-family'

type Mode = 'plane' | 'space'

const plan = demoData as ConstructionPlan
const experiment = experimentData as typeof experimentData
const SCALE = 1.45
const spatialFamily = buildTorusCircleFamily()
const torusPaths = spatialCirclePaths(spatialFamily, 96)

const clamp = (value: number, low = 0, high = 1) => Math.max(low, Math.min(high, value))

export default function DynamicConstructionPage() {
  const mountRef = useRef<HTMLDivElement>(null)
  const playingRef = useRef(true)
  const modeRef = useRef<Mode>('plane')
  const progressRef = useRef(0)
  const resetRef = useRef(false)
  const [playing, setPlaying] = useState(true)
  const [mode, setMode] = useState<Mode>('plane')
  const [progress, setProgress] = useState(0)
  const [ready, setReady] = useState(false)

  const paths = useMemo(() => constructionDrawingPaths(plan, 7.8), [])
  const drawableSteps = useMemo(
    () => plan.steps.filter(step => step.produced.length > 0),
    [],
  )
  const activeIndex = Math.min(
    plan.steps.length - 1,
    Math.max(0, Math.floor(progress * plan.steps.length)),
  )
  const activeStep = plan.steps[activeIndex]
  const spatialIndex = Math.min(
    spatialFamily.circles.length - 1,
    Math.max(0, Math.floor(progress * spatialFamily.circles.length)),
  )
  const spatialCircle = spatialFamily.circles[spatialIndex]
  const displayIndex = mode === 'space' ? spatialIndex : activeIndex
  const displayTotal = mode === 'space' ? spatialFamily.circles.length : plan.steps.length
  const displayLabel = mode === 'space'
    ? spatialCircle.family === 'meridian'
      ? `子午円 ${spatialIndex + 1} / 48`
      : `緯円 ${spatialIndex - 47} / 48`
    : activeStep?.label

  useEffect(() => { playingRef.current = playing }, [playing])
  useEffect(() => { modeRef.current = mode }, [mode])

  useEffect(() => {
    const mount = mountRef.current
    if (!mount) return

    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0x050607)
    scene.fog = new THREE.FogExp2(0x050607, 0.018)

    const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 120)
    camera.position.set(0, 0, 24)

    const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5))
    renderer.outputColorSpace = THREE.SRGBColorSpace
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.15
    mount.appendChild(renderer.domElement)

    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.dampingFactor = 0.055
    controls.enablePan = false
    controls.minDistance = 13
    controls.maxDistance = 32
    controls.target.set(0, 0, 0)

    scene.add(new THREE.AmbientLight(0xffffff, 0.72))
    const key = new THREE.DirectionalLight(0xffffff, 2.2)
    key.position.set(6, 8, 14)
    scene.add(key)
    const cyan = new THREE.PointLight(0x6ee7f5, 14, 28)
    cyan.position.set(-7, -4, 7)
    scene.add(cyan)
    const rose = new THREE.PointLight(0xfb7185, 10, 24)
    rose.position.set(7, 4, 5)
    scene.add(rose)

    const construction = new THREE.Group()
    scene.add(construction)
    const spatialConstruction = new THREE.Group()
    spatialConstruction.visible = false
    spatialConstruction.scale.setScalar(0.78)
    scene.add(spatialConstruction)

    // A colorless depth pre-pass hides the rear arcs. The visible torus is
    // still made entirely from the 96 certified circles, not from this mesh.
    const spatialDepthMaterial = new THREE.MeshBasicMaterial({
      colorWrite: false,
      depthWrite: true,
      depthTest: true,
      side: THREE.DoubleSide,
    })
    const spatialDepthMask = new THREE.Mesh(
      new THREE.TorusGeometry(
        spatialFamily.majorRadius,
        spatialFamily.minorRadius,
        64,
        192,
      ),
      spatialDepthMaterial,
    )
    spatialDepthMask.renderOrder = -1
    spatialConstruction.add(spatialDepthMask)

    const plane = new THREE.Mesh(
      new THREE.PlaneGeometry(24, 20),
      new THREE.MeshStandardMaterial({
        color: 0x080a0b,
        roughness: 0.92,
        metalness: 0.08,
        transparent: true,
        opacity: 0.76,
      }),
    )
    plane.position.z = -0.24
    construction.add(plane)

    const grid = new THREE.GridHelper(22, 22, 0x273036, 0x151a1d)
    grid.rotation.x = Math.PI / 2
    grid.position.z = -0.18
    ;(grid.material as THREE.Material).transparent = true
    ;(grid.material as THREE.Material).opacity = 0.24
    construction.add(grid)

    type Visual = {
      root: THREE.Object3D
      stepIndex: number
      segments: number
      line?: Line2
      material?: LineMaterial
      point?: THREE.Mesh
      depth: number
      baseOpacity?: number
    }
    const visuals: Visual[] = []
    const stepById = new Map(plan.steps.map((step, index) => [step.id, index]))
    const circlePalette = [0x60a5fa, 0x34d399, 0xf472b6, 0xfbbf24, 0xa78bfa, 0x22d3ee]
    let circleIndex = 0

    for (const path of paths) {
      const stepIndex = stepById.get(path.stepId) ?? 0
      const depth = stepIndex * 0.095
      if (path.kind === 'point') {
        const isGiven = plan.steps[stepIndex]?.operation === 'given-point'
        const point = new THREE.Mesh(
          new THREE.SphereGeometry(isGiven ? 0.12 : 0.1, 24, 18),
          new THREE.MeshStandardMaterial({
            color: isGiven ? 0xf8fafc : 0xfbbf24,
            emissive: isGiven ? 0x293238 : 0x4b3410,
            emissiveIntensity: 0.7,
            roughness: 0.28,
          }),
        )
        point.position.set(path.points[0].x * SCALE, path.points[0].y * SCALE, depth)
        point.visible = false
        construction.add(point)
        visuals.push({ root: point, point, stepIndex, segments: 1, depth })
        continue
      }

      const geometry = new LineGeometry()
      const positions = path.points.flatMap(point => [point.x * SCALE, point.y * SCALE, 0])
      geometry.setPositions(positions)
      geometry.instanceCount = 0
      const color = path.kind === 'circle'
        ? circlePalette[circleIndex++ % circlePalette.length]
        : plan.steps[stepIndex]?.label.includes('三角形') ? 0xf8fafc : 0x94a3b8
      const material = new LineMaterial({
        color,
        linewidth: path.kind === 'circle' ? 0.025 : 0.018,
        worldUnits: true,
        transparent: true,
        opacity: path.kind === 'circle' ? 0.88 : 0.72,
        alphaToCoverage: true,
        depthWrite: false,
      })
      const line = new Line2(geometry, material)
      line.frustumCulled = false
      line.position.z = depth
      construction.add(line)
      visuals.push({
        root: line,
        line,
        material,
        stepIndex,
        segments: Math.max(1, path.points.length - 1),
        depth,
        baseOpacity: path.kind === 'circle' ? 0.88 : 0.72,
      })
    }

    const spatialVisuals: Visual[] = []
    for (const [index, path] of torusPaths.entries()) {
      const geometry = new LineGeometry()
      geometry.setPositions(path.points.flatMap(point => [point.x, point.y, point.z]))
      geometry.instanceCount = 0
      const material = new LineMaterial({
        color: path.family === 'meridian' ? 0x67e8f9 : 0xf9a8d4,
        linewidth: path.family === 'meridian' ? 0.012 : 0.009,
        worldUnits: true,
        transparent: true,
        opacity: 0,
        alphaToCoverage: true,
        depthWrite: false,
        depthTest: true,
        blending: THREE.NormalBlending,
      })
      const line = new Line2(geometry, material)
      line.frustumCulled = false
      spatialConstruction.add(line)
      spatialVisuals.push({
        root: line,
        line,
        material,
        stepIndex: index,
        segments: path.points.length - 1,
        depth: 0,
        baseOpacity: path.family === 'meridian' ? 0.68 : 0.52,
      })
    }

    const resize = () => {
      const width = Math.max(1, mount.clientWidth)
      const height = Math.max(1, mount.clientHeight)
      camera.aspect = width / height
      camera.updateProjectionMatrix()
      renderer.setSize(width, height, false)
      for (const visual of visuals) visual.material?.resolution.set(width, height)
      for (const visual of spatialVisuals) visual.material?.resolution.set(width, height)
    }
    resize()
    window.addEventListener('resize', resize)

    let last = performance.now()
    let lastUi = 0
    let raf = 0
    let modeMix = 0
    const total = plan.steps.length

    const tick = (now: number) => {
      raf = requestAnimationFrame(tick)
      if (now - last < 1000 / 30) return
      const dt = Math.min(0.05, (now - last) / 1000)
      last = now
      if (resetRef.current) {
        resetRef.current = false
        progressRef.current = 0
      }
      if (playingRef.current) {
        progressRef.current += dt / 24
        if (progressRef.current >= 1) {
          progressRef.current = 1
          playingRef.current = false
          setPlaying(false)
        }
      }

      const targetMix = modeRef.current === 'space' ? 1 : 0
      modeMix += (targetMix - modeMix) * Math.min(1, dt * 3.2)
      controls.enableRotate = modeMix > 0.45
      controls.autoRotate = modeMix > 0.75 && playingRef.current
      controls.autoRotateSpeed = 0.52

      const planeCamera = new THREE.Vector3(0, 0, 24)
      const spaceCamera = new THREE.Vector3(13.5, -16.5, 10.5)
      if (modeMix < 0.98) camera.position.lerpVectors(planeCamera, spaceCamera, modeMix)
      construction.rotation.z = modeMix * 0.08
      construction.visible = modeMix < 0.985
      spatialConstruction.visible = modeMix > 0.015
      plane.visible = modeMix < 0.98
      grid.visible = modeMix < 0.98

      const exactStep = progressRef.current * total
      for (const visual of visuals) {
        const local = clamp(exactStep - visual.stepIndex)
        const eased = 1 - Math.pow(1 - local, 3)
        visual.root.position.z = visual.depth * modeMix
        if (visual.line) {
          visual.line.geometry.instanceCount = Math.floor(visual.segments * eased)
          visual.line.visible = local > 0
          if (visual.material) visual.material.opacity = (visual.baseOpacity ?? 0.8) * (1 - modeMix)
        }
        if (visual.point) {
          visual.point.visible = local > 0
          const scale = 0.35 + eased * 0.65
          visual.point.scale.setScalar(scale)
          const pointMaterial = visual.point.material as THREE.MeshStandardMaterial
          pointMaterial.transparent = true
          pointMaterial.opacity = 1 - modeMix
        }
      }

      const spatialExact = progressRef.current * spatialVisuals.length
      for (const visual of spatialVisuals) {
        const local = clamp(spatialExact - visual.stepIndex)
        const eased = 1 - Math.pow(1 - local, 3)
        if (visual.line) {
          visual.line.geometry.instanceCount = Math.floor(visual.segments * eased)
          visual.line.visible = local > 0 && modeMix > 0.01
        }
        if (visual.material) visual.material.opacity = (visual.baseOpacity ?? 0.4) * modeMix
      }

      controls.update()
      renderer.render(scene, camera)
      renderer.domElement.dataset.renderState = 'ready'
      renderer.domElement.dataset.step = String(Math.min(total, Math.floor(exactStep) + 1))
      if (now - lastUi > 90) {
        lastUi = now
        setProgress(progressRef.current)
      }
    }
    raf = requestAnimationFrame(tick)
    setReady(true)

    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', resize)
      controls.dispose()
      scene.traverse(object => {
        const mesh = object as THREE.Mesh
        mesh.geometry?.dispose?.()
        const material = mesh.material
        if (Array.isArray(material)) material.forEach(item => item.dispose())
        else material?.dispose?.()
      })
      renderer.dispose()
      if (renderer.domElement.parentNode === mount) mount.removeChild(renderer.domElement)
    }
  }, [paths])

  const seek = (value: number) => {
    progressRef.current = value
    setProgress(value)
  }

  return (
    <main className="min-h-[100dvh] bg-[#050607] text-zinc-100">
      <header className="flex h-14 items-center justify-between border-b border-zinc-900 px-4 sm:px-6">
        <div className="flex min-w-0 items-baseline gap-3">
          <Link href="/mortra" className="shrink-0 text-[11px] font-semibold tracking-[0.28em] text-zinc-200">
            MORTRA
          </Link>
          <span className="truncate text-[11px] text-zinc-600">CONSTRUCTION / 01</span>
        </div>
        <div className="flex items-center gap-2 text-[11px]">
          <span className={`h-1.5 w-1.5 rounded-full ${ready ? 'bg-emerald-400' : 'bg-amber-400'}`} />
          <span className="text-zinc-500">{ready ? 'LIVE' : 'INITIALIZING'}</span>
        </div>
      </header>

      <div className="grid min-h-[calc(100dvh-3.5rem)] md:h-[calc(100dvh-3.5rem)] md:min-h-0 md:grid-cols-[minmax(0,1fr)_340px]">
        <section className="relative min-h-[62dvh] overflow-hidden border-b border-zinc-900 md:min-h-0 md:border-b-0 md:border-r">
          <div ref={mountRef} className="absolute inset-0" data-construction-canvas />

          <div className="pointer-events-none absolute left-4 top-4 z-10 max-w-[min(520px,calc(100%-2rem))] sm:left-7 sm:top-7">
            <p className="text-[10px] font-semibold tracking-[0.2em] text-cyan-300">EXECUTABLE CONSTRUCTION</p>
            <h1 className="mt-3 text-[clamp(1.35rem,3vw,2.4rem)] font-medium leading-tight">
              {mode === 'plane'
                ? '19円を、交点の反復だけで構成する'
                : '96本の平面円を重ね、立体を露出する'}
            </h1>
            <p className="mt-3 text-[12px] text-zinc-500">
              {mode === 'plane'
                ? plan.label
                : '48本の子午円と48本の緯円が、同じトーラス方程式を満たす'}
            </p>
          </div>

          <div className="absolute bottom-5 left-4 right-4 z-10 sm:bottom-7 sm:left-7 sm:right-7">
            <div className="mb-3 flex items-end justify-between gap-5">
              <div className="min-w-0">
                <p className="text-[10px] tracking-[0.18em] text-zinc-600">
                  {mode === 'space' ? 'CIRCLE' : 'STEP'} {displayIndex + 1} / {displayTotal}
                </p>
                <p className="mt-1 truncate text-[13px] text-zinc-200">{displayLabel}</p>
              </div>
              <span className="shrink-0 font-mono text-[12px] text-zinc-500">
                {(progress * 100).toFixed(0)}%
              </span>
            </div>
            <input
              aria-label="作図の進行"
              type="range"
              min={0}
              max={1}
              step={0.001}
              value={progress}
              onChange={event => seek(Number(event.target.value))}
              className="h-1 w-full cursor-pointer accent-cyan-300"
            />
            <div className="mt-4 flex items-center justify-between gap-3">
              <div className="flex gap-2">
                <button
                  type="button"
                  title={playing ? '一時停止' : '再生'}
                  aria-label={playing ? '一時停止' : '再生'}
                  onClick={() => setPlaying(value => !value)}
                  className="grid h-9 w-9 place-items-center border border-zinc-700 bg-black/70 text-sm hover:border-zinc-400"
                >
                  {playing ? 'Ⅱ' : '▶'}
                </button>
                <button
                  type="button"
                  title="最初から"
                  aria-label="最初から"
                  onClick={() => { resetRef.current = true; setPlaying(true) }}
                  className="grid h-9 w-9 place-items-center border border-zinc-700 bg-black/70 text-lg hover:border-zinc-400"
                >
                  ↺
                </button>
              </div>
              <div className="flex border border-zinc-700 bg-black/70 p-0.5">
                {(['plane', 'space'] as Mode[]).map(value => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setMode(value)}
                    className={`h-8 min-w-11 px-3 text-[11px] ${mode === value ? 'bg-zinc-100 text-black' : 'text-zinc-500'}`}
                  >
                    {value === 'plane' ? '2D' : '3D'}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </section>

        <aside className="flex min-h-0 flex-col bg-[#090a0b]">
          <div className="border-b border-zinc-900 p-5 sm:p-6">
            <p className="text-[10px] tracking-[0.18em] text-zinc-600">A/B RESULT</p>
            <div className="mt-5 grid grid-cols-[1fr_auto_1fr] items-end gap-3">
              <div>
                <p className="text-[10px] text-zinc-600">補助作図なし</p>
                <p className="mt-1 text-2xl font-medium text-zinc-500">
                  {experiment.summary.baseline_without_auxiliary_construction}/{experiment.summary.cases}
                </p>
              </div>
              <span className="pb-1 text-zinc-700">→</span>
              <div>
                <p className="text-[10px] text-zinc-600">作図探索あり</p>
                <p className="mt-1 text-2xl font-medium text-emerald-300">
                  {experiment.summary.construction_search_solved}/{experiment.summary.cases}
                </p>
              </div>
            </div>
            <div className="mt-5 flex justify-between border-t border-zinc-900 pt-4 text-[11px]">
              <span className="text-zinc-600">負例の誤受理</span>
              <span className="font-mono text-zinc-300">
                {experiment.summary.false_acceptance}/{experiment.summary.negative_cases}
              </span>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-px bg-zinc-900">
              <div className="bg-[#090a0b] py-3 pr-3">
                <p className="text-[10px] text-zinc-600">平面ロゼット</p>
                <p className="mt-1 font-mono text-sm text-zinc-200">
                  {experiment.design_benchmark.circles} circles
                </p>
              </div>
              <div className="bg-[#090a0b] py-3 pl-3">
                <p className="text-[10px] text-zinc-600">立体円族</p>
                <p className="mt-1 font-mono text-sm text-zinc-200">
                  {experiment.spatial_benchmark.planar_circles} circles
                </p>
              </div>
              <div className="col-span-2 bg-[#090a0b] pt-3">
                <p className="text-[10px] text-zinc-600">型付きセル複体</p>
                <p className="mt-1 font-mono text-sm text-zinc-200">
                  {experiment.diagrammatic_benchmark.torus_cells.toLocaleString()} cells
                  {' · '}χ={experiment.diagrammatic_benchmark.torus_euler_characteristic}
                </p>
                <p className="mt-1 font-mono text-[10px] text-zinc-600">
                  Betti {Object.values(experiment.diagrammatic_benchmark.torus_betti_numbers).join(' / ')}
                </p>
              </div>
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto p-5 sm:p-6">
            <p className="text-[10px] tracking-[0.18em] text-zinc-600">CONSTRUCTION HISTORY</p>
            <ol className="mt-5 space-y-0">
              {drawableSteps.map(step => {
                const index = plan.steps.findIndex(item => item.id === step.id)
                const current = index === activeIndex
                const complete = index < activeIndex
                return (
                  <li key={step.id} className="grid grid-cols-[20px_1fr] gap-3 border-l border-zinc-800 pb-5 pl-4 last:pb-0">
                    <span
                      className={`-ml-[21px] mt-0.5 grid h-4 w-4 place-items-center rounded-full border text-[8px] ${
                        current
                          ? 'border-cyan-300 bg-cyan-300 text-black'
                          : complete
                            ? 'border-emerald-400 bg-emerald-400 text-black'
                            : 'border-zinc-700 bg-[#090a0b] text-zinc-600'
                      }`}
                    >
                      {complete ? '✓' : ''}
                    </span>
                    <div>
                      <p className={`text-[12px] leading-5 ${current ? 'text-zinc-100' : 'text-zinc-500'}`}>
                        {step.label}
                      </p>
                      {current && <p className="mt-1 text-[10px] leading-5 text-zinc-600">{step.reason}</p>}
                    </div>
                  </li>
                )
              })}
            </ol>
          </div>

          <div className="border-t border-zinc-900 px-5 py-4 text-[10px] leading-5 text-zinc-600 sm:px-6">
            数値再生検証 {experiment.summary.independently_replayed}/{experiment.summary.cases}
            {' · '}立体不変量 {experiment.spatial_benchmark.invariant_verified ? 'verified' : 'failed'}
            {' · '}セル境界² {experiment.diagrammatic_benchmark.boundary_squared_residuals}
            {' · '}一般522問ベンチは未測定
          </div>
        </aside>
      </div>
    </main>
  )
}
