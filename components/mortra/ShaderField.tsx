'use client'

/**
 * 背景シェーダ。生の WebGL2 で全画面フラグメントシェーダを1枚走らせる。
 *
 * 参考にした4サイト（pryzm.design / grainient.supply / gradientora.com /
 * backgrounds.supply）を解析したところ、Three.js を使っているものは
 * 一つも無かった。全部が raw WebGL2 の fragment shader だった。
 * Three.js は3Dシーングラフのためのもので、全画面に三角形を貼るだけの
 * この用途では数百KBの無駄になる。だから使わない。
 *
 * ただし、あの4サイトと同じ「綺麗なグラデーション」は作らない。
 * MORTRA は幾何の証明器なので、背景も幾何にする。
 * 点の配置から距離場を作り、その等位線を出す。画面に出ているのは
 * 装飾ではなく、Voronoi 境界と外接円という実際の幾何対象である。
 */
import { useEffect, useRef } from 'react'

const VERT = `#version 300 es
void main() {
  // 全画面三角形。頂点バッファを持たず gl_VertexID だけで出す
  vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
  gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}`

const FRAG = `#version 300 es
precision highp float;
out vec4 outColor;

uniform vec2  uRes;
uniform float uTime;
uniform vec2  uPointer;
uniform float uReduce;

#define N 7

// 点集合。証明で扱う配置に近い、規則的すぎない置き方をする
vec2 site(int i, float t) {
  float f = float(i);
  float a = f * 2.39996 + t * 0.06;          // 黄金角。周期的な整列を避ける
  float r = 0.28 + 0.20 * sin(f * 1.7 + t * 0.11);
  return vec2(cos(a), sin(a) * 0.62) * r;
}

void main() {
  vec2 uv = (gl_FragCoord.xy - 0.5 * uRes) / uRes.y;
  float t = uTime * (1.0 - 0.85 * uReduce);

  // ポインタを弱い引力として入れる。触ると場が寄る
  vec2 pull = (uPointer - 0.5 * uRes) / uRes.y;
  uv -= pull * 0.035 * (1.0 - uReduce);

  // 最近点と二番目に近い点の距離。差が Voronoi 境界になる
  float d1 = 1e9, d2 = 1e9;
  for (int i = 0; i < N; i++) {
    float d = length(uv - site(i, t));
    if (d < d1) { d2 = d1; d1 = d; } else if (d < d2) { d2 = d; }
  }
  float edge = d2 - d1;                       // 0 に近いほど境界

  // 境界線。細く、遠いほど薄い
  float border = smoothstep(0.035, 0.0, edge) * 0.55;

  // 最近点からの等距離円。作図の外接円に相当する
  float rings = 0.0;
  for (int i = 0; i < N; i++) {
    float d = length(uv - site(i, t));
    float k = fract(d * 6.0 - t * 0.15);
    rings += smoothstep(0.02, 0.0, min(k, 1.0 - k)) * smoothstep(0.65, 0.0, d) * 0.09;
  }

  // 点そのもの
  float nodes = 0.0;
  for (int i = 0; i < N; i++) {
    nodes += smoothstep(0.014, 0.0, length(uv - site(i, t)));
  }

  // 配色。参考サイトに倣い地は純黒に近づけ、線だけを浮かせる
  vec3 col = vec3(0.02, 0.024, 0.031);
  col += vec3(0.14, 0.52, 0.62) * border;
  col += vec3(0.10, 0.34, 0.44) * rings;
  col += vec3(0.55, 0.95, 0.90) * nodes;

  // 中心から外へ落とす
  col *= 1.0 - 0.42 * length(uv);

  // 粒子。バンディングを消すのが目的で、質感は副次
  float g = fract(sin(dot(gl_FragCoord.xy + t, vec2(12.9898, 78.233))) * 43758.5453);
  col += (g - 0.5) * 0.028;

  outColor = vec4(max(col, 0.0), 1.0);
}`

function compile(gl: WebGL2RenderingContext, type: number, src: string) {
  const s = gl.createShader(type)
  if (!s) return null
  gl.shaderSource(s, src)
  gl.compileShader(s)
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
    console.warn('[ShaderField]', gl.getShaderInfoLog(s))
    gl.deleteShader(s)
    return null
  }
  return s
}

export function ShaderField({ className }: { className?: string }) {
  const ref = useRef<HTMLCanvasElement | null>(null)

  useEffect(() => {
    const canvas = ref.current
    if (!canvas) return
    const gl = canvas.getContext('webgl2', { antialias: false, alpha: false })
    // WebGL2 が無い環境では静かに諦める。CSS の背景色が残るだけで壊れない
    if (!gl) return

    const vs = compile(gl, gl.VERTEX_SHADER, VERT)
    const fs = compile(gl, gl.FRAGMENT_SHADER, FRAG)
    if (!vs || !fs) return
    const prog = gl.createProgram()
    if (!prog) return
    gl.attachShader(prog, vs)
    gl.attachShader(prog, fs)
    gl.linkProgram(prog)
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
      console.warn('[ShaderField]', gl.getProgramInfoLog(prog))
      return
    }
    gl.useProgram(prog)

    const uRes = gl.getUniformLocation(prog, 'uRes')
    const uTime = gl.getUniformLocation(prog, 'uTime')
    const uPointer = gl.getUniformLocation(prog, 'uPointer')
    const uReduce = gl.getUniformLocation(prog, 'uReduce')

    const motion = window.matchMedia('(prefers-reduced-motion: reduce)')
    let reduce = motion.matches ? 1 : 0
    const onMotion = () => { reduce = motion.matches ? 1 : 0 }
    motion.addEventListener('change', onMotion)

    // 目標位置へ追従させる。生のポインタ座標をそのまま使うと動きが硬い
    const target = { x: 0, y: 0 }
    const eased = { x: 0, y: 0 }
    let hasPointer = false
    const onPointer = (e: PointerEvent) => {
      hasPointer = true
      target.x = e.clientX * devicePixelRatio
      target.y = (innerHeight - e.clientY) * devicePixelRatio
    }
    window.addEventListener('pointermove', onPointer, { passive: true })

    const resize = () => {
      const dpr = Math.min(devicePixelRatio || 1, 2)  // 高DPRで焼かない
      const w = Math.floor(canvas.clientWidth * dpr)
      const h = Math.floor(canvas.clientHeight * dpr)
      if (w === 0 || h === 0 || (canvas.width === w && canvas.height === h)) return
      canvas.width = w
      canvas.height = h
      gl.viewport(0, 0, w, h)
      if (!hasPointer) { target.x = w * 0.5; target.y = h * 0.5; eased.x = target.x; eased.y = target.y }
    }
    const ro = new ResizeObserver(resize)
    ro.observe(canvas)
    resize()

    // 画面外では止める。スクロールで見えなくなった背景を回し続けない
    let visible = true
    const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting }, { threshold: 0 })
    io.observe(canvas)

    let raf = 0
    const start = performance.now()
    const frame = (now: number) => {
      raf = requestAnimationFrame(frame)
      if (!visible) return
      eased.x += (target.x - eased.x) * 0.045
      eased.y += (target.y - eased.y) * 0.045
      gl.uniform2f(uRes, canvas.width, canvas.height)
      gl.uniform1f(uTime, (now - start) / 1000)
      gl.uniform2f(uPointer, eased.x, eased.y)
      gl.uniform1f(uReduce, reduce)
      gl.drawArrays(gl.TRIANGLES, 0, 3)
    }
    raf = requestAnimationFrame(frame)

    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect()
      io.disconnect()
      motion.removeEventListener('change', onMotion)
      window.removeEventListener('pointermove', onPointer)
      gl.deleteProgram(prog)
      gl.deleteShader(vs)
      gl.deleteShader(fs)
    }
  }, [])

  return <canvas ref={ref} className={className} aria-hidden="true" />
}
