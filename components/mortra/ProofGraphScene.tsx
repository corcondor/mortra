'use client'

import { useEffect, useRef } from 'react'
import * as THREE from 'three'

type ProofGraphSceneProps = {
  phase?: string
  progress?: number
  running?: boolean
  inputCount?: 1 | 2
  className?: string
}

type GraphNode = {
  id: string
  layer: number
  position: [number, number, number]
}

const CYAN = new THREE.Color('#28d7f2')
const GREEN = new THREE.Color('#a8f12f')
const AMBER = new THREE.Color('#f4b942')
const WHITE = new THREE.Color('#d7dde5')
const MUTED = new THREE.Color('#4b5563')

const GRAPH_NODES: GraphNode[] = [
  { id: 'parent-a', layer: 0, position: [-3.5, 0.92, 0.16] },
  { id: 'parent-b', layer: 0, position: [-3.5, -0.92, -0.16] },
  { id: 'a-object', layer: 1, position: [-2.15, 1.34, 0.12] },
  { id: 'a-relation', layer: 1, position: [-2.15, 0.48, -0.1] },
  { id: 'b-object', layer: 1, position: [-2.15, -0.48, 0.1] },
  { id: 'b-relation', layer: 1, position: [-2.15, -1.34, -0.12] },
  { id: 'invariant-a', layer: 2, position: [-0.68, 0.72, 0.06] },
  { id: 'invariant-b', layer: 2, position: [-0.68, -0.72, -0.06] },
  { id: 'bridge', layer: 3, position: [0.72, 0, 0] },
  { id: 'candidate', layer: 4, position: [2.05, 0.54, 0.05] },
  { id: 'counterexample', layer: 4, position: [2.05, -0.54, -0.05] },
  { id: 'certificate', layer: 5, position: [3.42, 0, 0] },
]

const GRAPH_EDGES: Array<[string, string]> = [
  ['parent-a', 'a-object'],
  ['parent-a', 'a-relation'],
  ['parent-b', 'b-object'],
  ['parent-b', 'b-relation'],
  ['a-object', 'invariant-a'],
  ['a-relation', 'invariant-a'],
  ['b-object', 'invariant-b'],
  ['b-relation', 'invariant-b'],
  ['invariant-a', 'bridge'],
  ['invariant-b', 'bridge'],
  ['bridge', 'candidate'],
  ['bridge', 'counterexample'],
  ['candidate', 'certificate'],
  ['counterexample', 'certificate'],
]

function phaseColor(phase: string) {
  if (phase === 'complete' || phase === 'done') return GREEN
  if (phase === 'error') return AMBER
  return CYAN
}

function edgeLine(
  start: THREE.Vector3,
  end: THREE.Vector3,
  color: THREE.ColorRepresentation,
  opacity: number,
) {
  const midpoint = start.clone().lerp(end, 0.5)
  midpoint.z += Math.abs(start.y - end.y) * 0.08
  const curve = new THREE.QuadraticBezierCurve3(start, midpoint, end)
  const geometry = new THREE.BufferGeometry().setFromPoints(curve.getPoints(24))
  const material = new THREE.LineBasicMaterial({ color, transparent: true, opacity })
  return new THREE.Line(geometry, material)
}

export function ProofGraphScene({
  phase = 'searching',
  progress = 0.38,
  running = true,
  inputCount = 2,
  className,
}: ProofGraphSceneProps) {
  const hostRef = useRef<HTMLDivElement>(null)
  const stateRef = useRef({ phase, progress, running })
  stateRef.current = { phase, progress, running }

  useEffect(() => {
    const host = hostRef.current
    if (!host) return

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75))
    renderer.setClearColor(0x000000, 0)
    host.appendChild(renderer.domElement)

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(34, 1, 0.1, 50)
    camera.position.set(0, 0, 9.6)

    const root = new THREE.Group()
    root.rotation.x = -0.06
    root.rotation.y = -0.08
    scene.add(root)

    const omitted = inputCount === 1
      ? new Set(['parent-b', 'b-object', 'b-relation', 'invariant-b'])
      : new Set<string>()
    const graphNodes = GRAPH_NODES
      .filter(node => !omitted.has(node.id))
      .map(node => {
        if (inputCount !== 1) return node
        if (node.id === 'parent-a') return { ...node, position: [-3.5, 0, 0] as [number, number, number] }
        if (node.id === 'a-object') return { ...node, position: [-2.15, 0.48, 0.08] as [number, number, number] }
        if (node.id === 'a-relation') return { ...node, position: [-2.15, -0.48, -0.08] as [number, number, number] }
        if (node.id === 'invariant-a') return { ...node, position: [-0.68, 0, 0] as [number, number, number] }
        return node
      })
    const graphEdges = GRAPH_EDGES.filter(([from, to]) => !omitted.has(from) && !omitted.has(to))
    const positions = new Map(graphNodes.map(node => [node.id, new THREE.Vector3(...node.position)]))

    const baseEdges = new THREE.Group()
    const activeEdges: Array<{ line: THREE.Line; layer: number }> = []
    graphEdges.forEach(([from, to]) => {
      const start = positions.get(from)
      const end = positions.get(to)
      if (!start || !end) return
      baseEdges.add(edgeLine(start, end, MUTED, 0.28))
      const targetLayer = graphNodes.find(node => node.id === to)?.layer ?? 0
      const line = edgeLine(start, end, CYAN, 0)
      activeEdges.push({ line, layer: targetLayer })
    })
    root.add(baseEdges)
    activeEdges.forEach(({ line }) => root.add(line))

    const nodeMeshes: Array<{ mesh: THREE.Mesh; layer: number; id: string }> = []
    graphNodes.forEach(node => {
      const geometry = node.id === 'bridge' || node.id === 'certificate'
        ? new THREE.OctahedronGeometry(node.id === 'certificate' ? 0.16 : 0.13, 0)
        : new THREE.SphereGeometry(node.layer === 0 ? 0.12 : 0.085, 20, 20)
      const material = new THREE.MeshBasicMaterial({ color: WHITE, transparent: true, opacity: 0.34 })
      const mesh = new THREE.Mesh(geometry, material)
      mesh.position.set(...node.position)
      root.add(mesh)
      nodeMeshes.push({ mesh, layer: node.layer, id: node.id })
    })

    const endpointRings = graphNodes.filter(node => node.layer === 0).map(node => {
      const ring = new THREE.Mesh(
        new THREE.RingGeometry(0.17, 0.185, 40),
        new THREE.MeshBasicMaterial({ color: CYAN, transparent: true, opacity: 0.72, side: THREE.DoubleSide }),
      )
      ring.position.set(...node.position)
      root.add(ring)
      return ring
    })

    const targetRotation = { x: root.rotation.x, y: root.rotation.y }
    const onPointerMove = (event: PointerEvent) => {
      const rect = host.getBoundingClientRect()
      targetRotation.y = -0.08 + ((event.clientX - rect.left) / rect.width - 0.5) * 0.12
      targetRotation.x = -0.06 + ((event.clientY - rect.top) / rect.height - 0.5) * 0.08
    }
    host.addEventListener('pointermove', onPointerMove, { passive: true })

    let visible = true
    const observer = new IntersectionObserver(entries => { visible = entries[0]?.isIntersecting ?? true }, { threshold: 0.02 })
    observer.observe(host)

    const resize = () => {
      const width = Math.max(1, host.clientWidth)
      const height = Math.max(1, host.clientHeight)
      const aspect = width / height
      renderer.setSize(width, height, true)
      camera.aspect = aspect
      camera.position.z = aspect < 1 ? 13.4 : aspect < 1.45 ? 10.8 : 9.6
      camera.updateProjectionMatrix()
    }
    const resizeObserver = new ResizeObserver(resize)
    resizeObserver.observe(host)
    resize()

    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    let frame = 0
    const started = performance.now()
    const animate = (time: number) => {
      frame = window.requestAnimationFrame(animate)
      if (!visible) return
      const elapsed = (time - started) / 1000
      const current = stateRef.current
      const reachedLayer = current.phase === 'complete' ? 5 : Math.min(5, current.progress * 6)
      const color = phaseColor(current.phase)

      root.rotation.x += (targetRotation.x - root.rotation.x) * 0.045
      root.rotation.y += (targetRotation.y - root.rotation.y) * 0.045
      if (!reduced && current.running) root.position.y = Math.sin(elapsed * 0.55) * 0.025

      activeEdges.forEach(({ line, layer }) => {
        const material = line.material as THREE.LineBasicMaterial
        material.color.copy(color)
        material.opacity += ((layer <= reachedLayer ? 0.92 : 0) - material.opacity) * 0.08
      })

      nodeMeshes.forEach(({ mesh, layer, id }) => {
        const material = mesh.material as THREE.MeshBasicMaterial
        const reached = layer <= reachedLayer
        const nodeColor = id === 'certificate' && current.phase === 'complete' ? GREEN : color
        material.color.copy(reached ? nodeColor : WHITE)
        material.opacity += ((reached ? 0.98 : 0.34) - material.opacity) * 0.08
        const pulse = reached && current.running && !reduced ? 1 + Math.sin(elapsed * 3.1 - layer * 0.7) * 0.07 : 1
        mesh.scale.setScalar(pulse)
      })

      endpointRings.forEach((ring, index) => {
        const material = ring.material as THREE.MeshBasicMaterial
        material.color.copy(color)
        const pulse = reduced ? 1 : 1 + Math.sin(elapsed * 2.2 + index * Math.PI) * 0.05
        ring.scale.setScalar(pulse)
      })

      renderer.render(scene, camera)
    }
    frame = window.requestAnimationFrame(animate)

    return () => {
      window.cancelAnimationFrame(frame)
      observer.disconnect()
      resizeObserver.disconnect()
      host.removeEventListener('pointermove', onPointerMove)
      root.traverse(object => {
        const candidate = object as THREE.Mesh
        if (candidate.geometry) candidate.geometry.dispose()
        const material = candidate.material
        if (Array.isArray(material)) material.forEach(item => item.dispose())
        else material?.dispose()
      })
      renderer.dispose()
      renderer.domElement.remove()
    }
  }, [inputCount])

  return <div ref={hostRef} className={className} aria-label={inputCount === 1 ? '一つの問題から検証済み解答へ進む証明DAG' : '二つの親問題から検証済み結論へ合流する証明DAG'} role="img" />
}
