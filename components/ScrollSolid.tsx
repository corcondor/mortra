'use client'

/**
 * 記事の背後で、立方体が平面に切られていく。
 *
 * ここは装飾ではない。スクロール量 s∈[0,1] が切断平面の位置 c(s) に対応し、
 * 断面の多角形は**実際に計算している**。辺と平面の交点を求め、
 * 面の周りに並べ直して閉じる。動いているように見せているのではない。
 *
 * 立方体の対角線に垂直な平面で切ると、途中で断面が正六角形になる。
 * スクロールしていくと 三角形 → 五角形 → 六角形 → 五角形 → 三角形 と
 * 辺の数が変わる。その瞬間が目で見える。
 *
 * MORTRA の主張そのもの: 同じ構造が、式でも図でも運動でもある。
 * だからサイトの背景も、飾りではなく数学でなければならない。
 */

import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { Line2 } from 'three/examples/jsm/lines/Line2.js'
import { LineGeometry } from 'three/examples/jsm/lines/LineGeometry.js'
import { LineMaterial } from 'three/examples/jsm/lines/LineMaterial.js'

type V3 = THREE.Vector3

/** 単位立方体の 12 辺（頂点の番号の組） */
const CUBE_EDGES: Array<[number, number]> = [
  [0, 1], [1, 3], [3, 2], [2, 0],
  [4, 5], [5, 7], [7, 6], [6, 4],
  [0, 4], [1, 5], [2, 6], [3, 7],
]

const cubeVertices = (r: number): V3[] =>
  [0, 1, 2, 3, 4, 5, 6, 7].map(i =>
    new THREE.Vector3(
      (i & 1 ? 1 : -1) * r,
      (i & 2 ? 1 : -1) * r,
      (i & 4 ? 1 : -1) * r,
    ),
  )

/**
 * 平面 n·x = c と立方体の断面多角形を求める。
 *
 * 各辺について、両端の n·x − c の符号が違えば交点がある。
 * 交点を集めたあと、平面上の角度で並べ替えて閉じる。
 * 並べ替えないと多角形が自己交差する。
 */
function crossSection(vertices: V3[], normal: V3, c: number): V3[] {
  const points: V3[] = []
  for (const [a, b] of CUBE_EDGES) {
    const pa = vertices[a], pb = vertices[b]
    const da = normal.dot(pa) - c
    const db = normal.dot(pb) - c
    if (da === 0) points.push(pa.clone())
    if (da * db < 0) {
      const t = da / (da - db)
      points.push(pa.clone().lerp(pb, t))
    }
  }
  if (points.length < 3) return points

  // 平面上に基底を取り、重心まわりの偏角で並べる
  const centre = points
    .reduce((acc, p) => acc.add(p), new THREE.Vector3())
    .multiplyScalar(1 / points.length)
  const u = new THREE.Vector3(1, 0, 0)
  if (Math.abs(normal.dot(u)) > 0.9) u.set(0, 1, 0)
  const e1 = u.clone().sub(normal.clone().multiplyScalar(normal.dot(u))).normalize()
  const e2 = new THREE.Vector3().crossVectors(normal, e1).normalize()

  return points
    .map(p => {
      const d = p.clone().sub(centre)
      return { p, angle: Math.atan2(d.dot(e2), d.dot(e1)) }
    })
    .sort((a, b) => a.angle - b.angle)
    .map(x => x.p)
}

export default function ScrollSolid({ className }: { className?: string } = {}) {
  const mountRef = useRef<HTMLDivElement | null>(null)
  const progressRef = useRef(0)

  useEffect(() => {
    const mount = mountRef.current
    if (!mount) return

    // 動きを減らす設定を尊重する。静止画にフォールバックせず、切断を止める
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 200)
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.0
    mount.appendChild(renderer.domElement)

    const R = 6
    const vertices = cubeVertices(R)
    // 対角線 (1,1,1)/√3 に垂直な平面で切る。途中で断面が正六角形になる
    const normal = new THREE.Vector3(1, 1, 1).normalize()
    const cMax = normal.dot(new THREE.Vector3(R, R, R))

    const group = new THREE.Group()
    scene.add(group)

    const white = 0xf2f2f2
    const edgeMaterials: LineMaterial[] = []
    const makeLine = (width: number, opacity: number) => {
      const material = new LineMaterial({
        color: white, linewidth: width, worldUnits: true,
        transparent: true, opacity, alphaToCoverage: true,
      })
      edgeMaterials.push(material)
      return material
    }

    // 立方体の枠。細く、控えめに
    for (const [a, b] of CUBE_EDGES) {
      const geometry = new LineGeometry()
      geometry.setPositions([
        vertices[a].x, vertices[a].y, vertices[a].z,
        vertices[b].x, vertices[b].y, vertices[b].z,
      ])
      group.add(new Line2(geometry, makeLine(0.028, 0.26)))
    }

    // 断面。ここだけ明るくする
    const MAX = 8
    const sectionGeometry = new LineGeometry()
    sectionGeometry.setPositions(new Array((MAX + 1) * 3).fill(0))
    const sectionMaterial = makeLine(0.075, 0.95)
    const section = new Line2(sectionGeometry, sectionMaterial)
    section.frustumCulled = false
    group.add(section)

    const setSection = (points: V3[]) => {
      const attribute = section.geometry.getAttribute('instanceStart') as THREE.InterleavedBufferAttribute
      const array = attribute.data.array as Float32Array
      if (points.length < 3) { section.geometry.instanceCount = 0; return }
      const closed = [...points, points[0]]
      const count = Math.min(closed.length - 1, MAX)
      for (let i = 0; i < count; i++) {
        const base = i * 6
        array[base] = closed[i].x; array[base + 1] = closed[i].y; array[base + 2] = closed[i].z
        array[base + 3] = closed[i + 1].x; array[base + 4] = closed[i + 1].y; array[base + 5] = closed[i + 1].z
      }
      attribute.data.needsUpdate = true
      section.geometry.instanceCount = count
    }

    const resize = () => {
      const w = mount.clientWidth, h = mount.clientHeight
      camera.aspect = w / h
      camera.updateProjectionMatrix()
      renderer.setSize(w, h)
      for (const m of edgeMaterials) m.resolution.set(w, h)
    }
    resize()
    window.addEventListener('resize', resize)

    const onScroll = () => {
      const max = document.documentElement.scrollHeight - window.innerHeight
      progressRef.current = max > 0 ? Math.min(1, Math.max(0, window.scrollY / max)) : 0
    }
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })

    let raf = 0
    let shown = 0
    const tick = () => {
      raf = requestAnimationFrame(tick)
      // 追従を少し遅らせると、切断が滑らかに見える
      shown += (progressRef.current - shown) * 0.08

      // 平面は端から端へ。s=0.5 で中心を通り、そこで正六角形になる
      const c = (shown * 2 - 1) * cMax * 0.98
      setSection(crossSection(vertices, normal, c))

      if (!reduced) {
        group.rotation.y = 0.6 + shown * 1.7
        group.rotation.x = 0.32 + Math.sin(shown * Math.PI) * 0.16
      }
      camera.position.set(0, 0, 26)
      camera.lookAt(0, 0, 0)
      renderer.render(scene, camera)
    }
    tick()

    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', resize)
      window.removeEventListener('scroll', onScroll)
      renderer.dispose()
      mount.removeChild(renderer.domElement)
    }
  }, [])

  return (
    <div
      ref={mountRef}
      aria-hidden
      className={className ?? 'pointer-events-none fixed inset-0 -z-10 opacity-[0.55]'}
    />
  )
}
