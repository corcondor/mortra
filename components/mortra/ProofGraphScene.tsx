'use client'

import { useEffect, useRef } from 'react'
import * as THREE from 'three'

type ProofGraphSceneProps = {
  phase?: string
  progress?: number
  running?: boolean
  className?: string
}

const CYAN = new THREE.Color('#28d7f2')
const GREEN = new THREE.Color('#a8f12f')
const AMBER = new THREE.Color('#f4b942')
const WHITE = new THREE.Color('#d7dde5')

function phaseColor(phase: string) {
  if (phase === 'complete' || phase === 'done') return GREEN
  if (phase === 'error') return AMBER
  return CYAN
}

function lineFromPoints(points: THREE.Vector3[], color: THREE.ColorRepresentation, opacity: number) {
  const geometry = new THREE.BufferGeometry().setFromPoints(points)
  const material = new THREE.LineBasicMaterial({ color, transparent: true, opacity })
  return new THREE.Line(geometry, material)
}

export function ProofGraphScene({
  phase = 'searching',
  progress = 0.38,
  running = true,
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
    const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 50)
    camera.position.set(0.1, 0.1, 10.2)

    const root = new THREE.Group()
    root.rotation.x = -0.12
    root.rotation.y = -0.18
    scene.add(root)

    const nodes: THREE.Vector3[] = []
    for (let layer = 0; layer < 3; layer += 1) {
      const z = (layer - 1) * 1.35
      for (let index = 0; index < 22; index += 1) {
        const angle = (index / 22) * Math.PI * 2 + layer * 0.42
        const radial = 2.55 + 0.3 * Math.sin(index * 1.73 + layer)
        nodes.push(new THREE.Vector3(
          Math.cos(angle) * radial + (layer - 1) * 0.24,
          Math.sin(angle) * (1.34 + layer * 0.08),
          z + 0.28 * Math.sin(angle * 3),
        ))
      }
    }

    const edgePoints: number[] = []
    const addEdge = (a: number, b: number) => {
      edgePoints.push(nodes[a].x, nodes[a].y, nodes[a].z, nodes[b].x, nodes[b].y, nodes[b].z)
    }
    for (let layer = 0; layer < 3; layer += 1) {
      const offset = layer * 22
      for (let index = 0; index < 22; index += 1) {
        addEdge(offset + index, offset + ((index + 1) % 22))
        if (index % 2 === 0) addEdge(offset + index, offset + ((index + 5) % 22))
        if (layer < 2 && index % 2 === 0) addEdge(offset + index, offset + 22 + ((index + 3) % 22))
      }
    }
    const edgeGeometry = new THREE.BufferGeometry()
    edgeGeometry.setAttribute('position', new THREE.Float32BufferAttribute(edgePoints, 3))
    const edgeMaterial = new THREE.LineBasicMaterial({ color: 0x6b7280, transparent: true, opacity: 0.26 })
    root.add(new THREE.LineSegments(edgeGeometry, edgeMaterial))

    const pointGeometry = new THREE.BufferGeometry().setFromPoints(nodes)
    const pointMaterial = new THREE.PointsMaterial({ color: WHITE, size: 0.052, transparent: true, opacity: 0.9 })
    root.add(new THREE.Points(pointGeometry, pointMaterial))

    const circleMaterial = new THREE.LineBasicMaterial({ color: 0x9ca3af, transparent: true, opacity: 0.22 })
    const circles: THREE.LineLoop[] = []
    for (let index = 0; index < 5; index += 1) {
      const curve = new THREE.EllipseCurve(0, 0, 0.48 + index * 0.09, 0.48 + index * 0.09, 0, Math.PI * 2)
      const points = curve.getPoints(72).map(point => new THREE.Vector3(point.x, point.y, 0))
      const circle = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(points), circleMaterial.clone())
      circle.position.copy(nodes[6 + index * 10])
      circle.rotation.set(0.35 + index * 0.18, 0.25 + index * 0.31, index * 0.14)
      circles.push(circle)
      root.add(circle)
    }

    const planes: THREE.LineSegments[] = []
    for (let index = 0; index < 3; index += 1) {
      const geometry = new THREE.EdgesGeometry(new THREE.PlaneGeometry(4.4 - index * 0.45, 2.15 - index * 0.12, 4, 3))
      const plane = new THREE.LineSegments(
        geometry,
        new THREE.LineBasicMaterial({ color: 0x64748b, transparent: true, opacity: 0.12 }),
      )
      plane.position.z = (index - 1) * 1.4
      plane.rotation.z = 0.08 * (index - 1)
      planes.push(plane)
      root.add(plane)
    }

    const pathIndices = [3, 28, 51, 34, 61, 17]
    const pathPoints = pathIndices.map(index => nodes[index])
    const activeMaterial = new THREE.LineBasicMaterial({ color: phaseColor(stateRef.current.phase), transparent: true, opacity: 0.95 })
    const activePath = lineFromPoints(pathPoints, phaseColor(stateRef.current.phase), 0.95)
    activePath.material = activeMaterial
    root.add(activePath)

    const pulseGeometry = new THREE.SphereGeometry(0.095, 18, 18)
    const pulses = pathPoints.map((point, index) => {
      const material = new THREE.MeshBasicMaterial({ color: index === pathPoints.length - 1 ? GREEN : phaseColor(stateRef.current.phase) })
      const mesh = new THREE.Mesh(pulseGeometry, material)
      mesh.position.copy(point)
      root.add(mesh)
      return mesh
    })

    const targetRotation = { x: root.rotation.x, y: root.rotation.y }
    const onPointerMove = (event: PointerEvent) => {
      const rect = host.getBoundingClientRect()
      targetRotation.y = -0.18 + ((event.clientX - rect.left) / rect.width - 0.5) * 0.28
      targetRotation.x = -0.12 + ((event.clientY - rect.top) / rect.height - 0.5) * 0.16
    }
    host.addEventListener('pointermove', onPointerMove, { passive: true })

    let visible = true
    const observer = new IntersectionObserver(entries => { visible = entries[0]?.isIntersecting ?? true }, { threshold: 0.02 })
    observer.observe(host)

    const resize = () => {
      const width = Math.max(1, host.clientWidth)
      const height = Math.max(1, host.clientHeight)
      renderer.setSize(width, height, true)
      camera.aspect = width / height
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
      root.rotation.x += (targetRotation.x - root.rotation.x) * 0.035
      root.rotation.y += (targetRotation.y - root.rotation.y) * 0.035
      const current = stateRef.current
      if (!reduced && current.running) root.rotation.z = Math.sin(elapsed * 0.12) * 0.025
      pulses.forEach((mesh, index) => {
        const reached = index <= Math.max(0, Math.floor(current.progress * pathPoints.length))
        mesh.visible = reached
        const scale = 0.82 + (reduced ? 0 : Math.sin(elapsed * 3.2 - index * 0.7) * 0.2)
        mesh.scale.setScalar(scale)
      })
      activeMaterial.color.copy(phaseColor(current.phase))
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
  }, [])

  return <div ref={hostRef} className={className} aria-label="型付き証明グラフの3D表示" role="img" />
}
