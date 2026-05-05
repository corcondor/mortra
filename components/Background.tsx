'use client'
import { useEffect, useRef } from 'react'

// ── Shaders ──────────────────────────────────────────────────────────────────

const VERT = /* glsl */`
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`

const FRAG = /* glsl */`
uniform float uTime;
uniform float uScroll;
varying vec2 vUv;

float hash(vec2 p) {
  return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}
float noise(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  return mix(
    mix(hash(i), hash(i + vec2(1,0)), f.x),
    mix(hash(i + vec2(0,1)), hash(i + vec2(1,1)), f.x),
    f.y);
}
float fbm(vec2 p) {
  float v = 0.0, a = 0.5;
  for (int i = 0; i < 6; i++) {
    v += a * noise(p);
    p = p * 2.1 + vec2(1.7, 9.2);
    a *= 0.5;
  }
  return v;
}

void main() {
  vec2  uv = vUv;
  float t  = uTime * 0.12;
  float sc = uScroll;

  float nx = fbm(uv * 2.8 + vec2(t, 0.0));
  float ny = fbm(uv * 2.8 + vec2(0.0, t) + 3.1);
  vec2  warped = uv + (vec2(nx, ny) - 0.5) * 0.35;
  float f  = fbm(warped * 2.2 + vec2(t * 0.4));

  float band = smoothstep(0.0, 0.55, uv.y) * smoothstep(1.0, 0.35, uv.y);
  band *= 0.8 + 0.2 * sin(t * 2.5 + uv.x * 10.0);

  vec3 base = vec3(0.018, 0.008, 0.045);
  vec3 colA = mix(vec3(0.28, 0.04, 0.60), vec3(0.70, 0.02, 0.38), sc);
  vec3 colB = mix(vec3(0.04, 0.22, 0.75), vec3(0.00, 0.55, 0.55), sc);
  vec3 colC = mix(vec3(0.50, 0.01, 0.30), vec3(0.10, 0.70, 0.40), sc);

  vec3 aurora = mix(colA, colB, smoothstep(0.25, 0.75, f + uv.x * 0.3));
  aurora      = mix(aurora, colC, smoothstep(0.60, 0.95, f + uv.y * 0.15));
  aurora     *= band * (0.35 + 0.65 * f);

  float glowL = (1.0 - length(uv - vec2(0.15, 0.35))) * 0.18;
  float glowR = (1.0 - length(uv - vec2(0.85, 0.20))) * 0.14;
  aurora += colA * max(glowL, 0.0);
  aurora += colB * max(glowR, 0.0);
  aurora += colC * smoothstep(0.25, 0.0, uv.y) * 0.12;

  gl_FragColor = vec4(base + aurora, 1.0);
}
`

const STAR_VERT = /* glsl */`
attribute float aSize;
attribute float aOpacity;
uniform float uTime;
varying float vOpacity;
void main() {
  vOpacity = aOpacity * (0.5 + 0.5 * sin(uTime * 1.5 + position.x * 37.0));
  vec4 mvPos = modelViewMatrix * vec4(position, 1.0);
  gl_PointSize = aSize * (600.0 / -mvPos.z);
  gl_Position  = projectionMatrix * mvPos;
}
`

const STAR_FRAG = /* glsl */`
varying float vOpacity;
void main() {
  float d = length(gl_PointCoord - 0.5) * 2.0;
  float a = (1.0 - smoothstep(0.5, 1.0, d)) * vOpacity;
  gl_FragColor = vec4(1.0, 1.0, 1.0, a);
}
`

// ── Component ─────────────────────────────────────────────────────────────────

export function Background() {
  const mountRef   = useRef<HTMLDivElement>(null)
  const cleanupRef = useRef<(() => void) | null>(null)

  useEffect(() => {
    const mount = mountRef.current
    if (!mount) return

    // クリーンアップ関数を ref に保存して非同期でも有効にする
    let destroyed = false

    import('three').then((THREE) => {
      if (destroyed) return

      // ── Renderer ──────────────────────────────
      const renderer = new THREE.WebGLRenderer({ antialias: false, alpha: false })
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5))
      renderer.setSize(window.innerWidth, window.innerHeight)
      Object.assign(renderer.domElement.style, {
        position: 'fixed', inset: '0', zIndex: '-10', pointerEvents: 'none',
      })
      mount.appendChild(renderer.domElement)

      const scene  = new THREE.Scene()
      const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1)

      // ── Aurora plane ──────────────────────────
      const auroraUniforms = {
        uTime:   { value: 0 },
        uScroll: { value: 0 },
      }
      scene.add(new THREE.Mesh(
        new THREE.PlaneGeometry(2, 2),
        new THREE.ShaderMaterial({
          vertexShader: VERT, fragmentShader: FRAG, uniforms: auroraUniforms,
        }),
      ))

      // ── Star particles ────────────────────────
      const N   = 180
      const pos = new Float32Array(N * 3)
      const sz  = new Float32Array(N)
      const op  = new Float32Array(N)
      for (let i = 0; i < N; i++) {
        pos[i * 3]     = (Math.random() - 0.5) * 2
        pos[i * 3 + 1] = (Math.random() - 0.5) * 2
        pos[i * 3 + 2] = 0
        sz[i]          = Math.random() * 2.5 + 0.5
        op[i]          = Math.random() * 0.5 + 0.08
      }
      const starGeo = new THREE.BufferGeometry()
      starGeo.setAttribute('position', new THREE.BufferAttribute(pos, 3))
      starGeo.setAttribute('aSize',    new THREE.BufferAttribute(sz,  1))
      starGeo.setAttribute('aOpacity', new THREE.BufferAttribute(op,  1))
      const starUniforms = { uTime: { value: 0 } }
      scene.add(new THREE.Points(starGeo,
        new THREE.ShaderMaterial({
          vertexShader: STAR_VERT, fragmentShader: STAR_FRAG,
          uniforms: starUniforms, transparent: true, depthWrite: false,
          blending: THREE.AdditiveBlending,
        }),
      ))

      // ── Scroll tracking ───────────────────────
      let scrollY = 0
      const mainEl = document.querySelector('main')
      const onScroll = () => {
        scrollY = mainEl ? mainEl.scrollTop : window.scrollY
      }
      mainEl?.addEventListener('scroll', onScroll, { passive: true })
      window.addEventListener('scroll', onScroll, { passive: true })

      const onResize = () => renderer.setSize(window.innerWidth, window.innerHeight)
      window.addEventListener('resize', onResize)

      // ── Render loop ───────────────────────────
      let rafId: number
      const getMaxScroll = () => mainEl
        ? Math.max(mainEl.scrollHeight - mainEl.clientHeight, 1)
        : Math.max(document.body.scrollHeight - window.innerHeight, 1)

      const tick = (t: number) => {
        const elapsed = t * 0.001
        const target  = Math.min(scrollY / getMaxScroll(), 1)
        auroraUniforms.uScroll.value += (target - auroraUniforms.uScroll.value) * 0.04
        auroraUniforms.uTime.value    = elapsed
        starUniforms.uTime.value      = elapsed
        renderer.render(scene, camera)
        rafId = requestAnimationFrame(tick)
      }
      rafId = requestAnimationFrame(tick)

      // クリーンアップを ref に登録
      cleanupRef.current = () => {
        cancelAnimationFrame(rafId)
        window.removeEventListener('resize', onResize)
        mainEl?.removeEventListener('scroll', onScroll)
        window.removeEventListener('scroll', onScroll)
        renderer.dispose()
        if (mount.contains(renderer.domElement)) mount.removeChild(renderer.domElement)
      }
    })

    return () => {
      destroyed = true
      cleanupRef.current?.()
      cleanupRef.current = null
    }
  }, [])

  return <div ref={mountRef} aria-hidden />
}
