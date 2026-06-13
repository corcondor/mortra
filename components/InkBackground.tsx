'use client'
/**
 * 水墨画風インタラクティブ背景 (Three.js)
 * - fbmノイズによる墨の濃淡
 * - カーソルの軌跡に沿って墨が滲む（速度で濃さが変わる）
 * - 和紙のような生成り色の紙面
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
uniform vec2  uRes;
uniform vec3  uTrail[${TRAIL}]; // xy: pos(uv), z: strength(age減衰)

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

  // 和紙の地（生成り + 繊維ムラ）
  vec3 paper = vec3(0.955, 0.945, 0.915);
  paper -= 0.03 * fbm(p * 40.0);

  // 遠山（画面上部にうっすら墨の山並み）
  float ridge = 0.78 + 0.07 * fbm(vec2(p.x * 1.8, 3.0));
  float mountain = smoothstep(ridge + 0.015, ridge - 0.06, uv.y)
                 * (0.10 + 0.08 * fbm(p * 3.0 + uTime * 0.01));

  // 下部の霞
  float mist = smoothstep(0.25, 0.0, uv.y) * 0.06 * (0.5 + fbm(p * 2.5 - uTime * 0.008));

  // カーソル軌跡の墨溜まり
  float ink = 0.0;
  for (int i = 0; i < ${TRAIL}; i++) {
    vec3 t = uTrail[i];
    if (t.z <= 0.001) continue;
    vec2 tp = vec2(t.x * aspect, t.y);
    float d = distance(p, tp);
    // 滲み: fbmで輪郭を揺らす
    float edge = 0.05 + 0.18 * t.z + 0.05 * fbm(p * 9.0 + float(i));
    ink += t.z * 0.7 * exp(-d * d / (edge * edge));
  }
  // 墨の粒状感
  ink *= 0.75 + 0.45 * fbm(p * 14.0 + uTime * 0.03);
  ink = min(ink, 0.82);

  float density = clamp(mountain + mist + ink, 0.0, 0.9);
  vec3 sumi = vec3(0.13, 0.13, 0.15);
  vec3 col = mix(paper, sumi, density);
  gl_FragColor = vec4(col, 1.0);
}
`

export function InkBackground() {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return

    const renderer = new THREE.WebGLRenderer({ antialias: false, powerPreference: 'low-power' })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5))
    renderer.setSize(window.innerWidth, window.innerHeight)
    el.appendChild(renderer.domElement)

    const scene = new THREE.Scene()
    const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1)

    const trail = Array.from({ length: TRAIL }, () => new THREE.Vector3(0.5, 0.5, 0))
    let head = 0

    const uniforms = {
      uTime: { value: 0 },
      uRes: { value: new THREE.Vector2(window.innerWidth, window.innerHeight) },
      uTrail: { value: trail },
    }

    const mat = new THREE.ShaderMaterial({ vertexShader: VERT, fragmentShader: FRAG, uniforms })
    scene.add(new THREE.Mesh(new THREE.PlaneGeometry(2, 2), mat))

    let last = { x: 0.5, y: 0.5, t: performance.now() }
    const onMove = (e: PointerEvent) => {
      const now = performance.now()
      const x = e.clientX / window.innerWidth
      const y = 1 - e.clientY / window.innerHeight
      const dt = Math.max(now - last.t, 1)
      const speed = Math.hypot(x - last.x, y - last.y) / dt * 1000
      // 速く動かすほど濃く太い墨
      const strength = Math.min(0.25 + speed * 0.9, 1.0)
      trail[head].set(x, y, strength)
      head = (head + 1) % TRAIL
      last = { x, y, t: now }
    }
    window.addEventListener('pointermove', onMove)

    const onResize = () => {
      renderer.setSize(window.innerWidth, window.innerHeight)
      uniforms.uRes.value.set(window.innerWidth, window.innerHeight)
    }
    window.addEventListener('resize', onResize)

    let raf = 0
    const tick = (t: number) => {
      uniforms.uTime.value = t / 1000
      // 墨が紙に染み込んでゆっくり薄れていく
      for (const v of trail) v.z *= 0.993
      renderer.render(scene, camera)
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)

    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('resize', onResize)
      renderer.dispose()
      el.removeChild(renderer.domElement)
    }
  }, [])

  return <div ref={ref} className="fixed inset-0 -z-10 pointer-events-none" aria-hidden />
}
