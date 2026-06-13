'use client'
/**
 * 和風水墨背景 (Three.js) — sakumon app 全体の背景
 * - 深い墨色の紙面に霞・遠山のような濃淡 (fbm)
 * - カーソルの軌跡に沿って銀墨が滲む（速く動かすほど濃く）
 * - スクロールで霞がゆっくり流れる
 */
import { useEffect, useRef } from 'react'
import * as THREE from 'three'

const TRAIL = 16

const VERT = /* glsl */ `
void main() { gl_Position = vec4(position, 1.0); }
`

const FRAG = /* glsl */ `
precision highp float;
uniform float uTime;
uniform float uScroll;
uniform vec2  uRes;
uniform vec3  uTrail[${TRAIL}]; // xy: pos(uv), z: strength

float hash(vec2 p) {
  return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}
float noise(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1,0)), u.x),
             mix(hash(i + vec2(0,1)), hash(i + vec2(1,1)), u.x), u.y);
}
float fbm(vec2 p) {
  float v = 0.0, a = 0.5;
  for (int i = 0; i < 5; i++) {
    v += a * noise(p);
    p = p * 2.05 + vec2(13.7, 7.3);
    a *= 0.5;
  }
  return v;
}

void main() {
  vec2 uv = gl_FragCoord.xy / uRes;
  float aspect = uRes.x / uRes.y;
  vec2 p = vec2(uv.x * aspect, uv.y);
  float t = uTime * 0.02;

  // 夜の墨紙（深い藍墨 + 紙の繊維ムラ）
  vec3 base = vec3(0.020, 0.020, 0.040);
  base += 0.012 * fbm(p * 30.0);

  // 銀墨の色（月明かりに薄く光る墨）
  vec3 gin = vec3(0.62, 0.66, 0.78);

  // 流れる霞（スクロールでゆっくり動く）
  float drift = uScroll * 0.4;
  float kasumi = fbm(p * 1.8 + vec2(t * 2.0 + drift, -t));
  float band = smoothstep(0.05, 0.45, uv.y) * smoothstep(0.95, 0.45, uv.y);
  float mist = smoothstep(0.45, 0.85, kasumi) * band * 0.10;

  // 遠山の稜線（下部にうっすら2層）
  float ridge1 = 0.22 + 0.06 * fbm(vec2(p.x * 1.6 + 8.0, 1.0));
  float m1 = smoothstep(ridge1 + 0.012, ridge1 - 0.05, uv.y) * 0.055;
  float ridge2 = 0.13 + 0.05 * fbm(vec2(p.x * 2.3 + 21.0, 5.0));
  float m2 = smoothstep(ridge2 + 0.010, ridge2 - 0.04, uv.y) * 0.085;

  // カーソル軌跡の銀墨だまり（fbmで輪郭を滲ませる）
  float ink = 0.0;
  for (int i = 0; i < ${TRAIL}; i++) {
    vec3 tr = uTrail[i];
    if (tr.z <= 0.001) continue;
    vec2 tp = vec2(tr.x * aspect, tr.y);
    float d = distance(p, tp);
    float edge = 0.05 + 0.16 * tr.z + 0.05 * fbm(p * 9.0 + float(i));
    ink += tr.z * 0.16 * exp(-d * d / (edge * edge));
  }
  ink *= 0.7 + 0.5 * fbm(p * 12.0 + uTime * 0.03);
  ink = min(ink, 0.30);

  vec3 col = base + gin * (mist + m1 + m2 + ink);
  gl_FragColor = vec4(col, 1.0);
}
`

export function Background() {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return

    const renderer = new THREE.WebGLRenderer({ antialias: false, powerPreference: 'low-power' })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5))
    renderer.setSize(window.innerWidth, window.innerHeight)
    Object.assign(renderer.domElement.style, {
      position: 'fixed', inset: '0', zIndex: '-10', pointerEvents: 'none',
    })
    el.appendChild(renderer.domElement)

    const scene = new THREE.Scene()
    const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1)

    const trail = Array.from({ length: TRAIL }, () => new THREE.Vector3(0.5, 0.5, 0))
    let head = 0

    const uniforms = {
      uTime: { value: 0 },
      uScroll: { value: 0 },
      uRes: { value: new THREE.Vector2(window.innerWidth, window.innerHeight) },
      uTrail: { value: trail },
    }

    scene.add(new THREE.Mesh(
      new THREE.PlaneGeometry(2, 2),
      new THREE.ShaderMaterial({ vertexShader: VERT, fragmentShader: FRAG, uniforms }),
    ))

    let last = { x: 0.5, y: 0.5, t: performance.now() }
    const onMove = (e: PointerEvent) => {
      const now = performance.now()
      const x = e.clientX / window.innerWidth
      const y = 1 - e.clientY / window.innerHeight
      const dt = Math.max(now - last.t, 1)
      const speed = Math.hypot(x - last.x, y - last.y) / dt * 1000
      const strength = Math.min(0.25 + speed * 0.9, 1.0)
      trail[head].set(x, y, strength)
      head = (head + 1) % TRAIL
      last = { x, y, t: now }
    }
    window.addEventListener('pointermove', onMove)

    // スクロール追従（main要素 or window）
    let scrollY = 0
    const mainEl = document.querySelector('main')
    const onScroll = () => { scrollY = mainEl ? mainEl.scrollTop : window.scrollY }
    mainEl?.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('scroll', onScroll, { passive: true })

    const onResize = () => {
      renderer.setSize(window.innerWidth, window.innerHeight)
      uniforms.uRes.value.set(window.innerWidth, window.innerHeight)
    }
    window.addEventListener('resize', onResize)

    let raf = 0
    const tick = (t: number) => {
      uniforms.uTime.value = t / 1000
      uniforms.uScroll.value += (scrollY * 0.001 - uniforms.uScroll.value) * 0.04
      // 墨が紙に染み込んでゆっくり薄れる
      for (const v of trail) v.z *= 0.993
      renderer.render(scene, camera)
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)

    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('resize', onResize)
      mainEl?.removeEventListener('scroll', onScroll)
      window.removeEventListener('scroll', onScroll)
      renderer.dispose()
      if (el.contains(renderer.domElement)) el.removeChild(renderer.domElement)
    }
  }, [])

  return <div ref={ref} aria-hidden />
}
