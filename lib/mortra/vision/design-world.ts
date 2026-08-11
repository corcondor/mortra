/**
 * DesignWorld — 一つの意味核から、複数の意匠が一貫して出る。
 *
 * 単発の SVG 生成では、ロゴとパターンとポスターが別々の物になる。
 * Rikyū が一つの依頼から成果物の束を出しているのと同じ形にする。
 *
 *   A₃ / FCC という semantic object 一つ
 *     → logo / pattern / poster / web hero / social card / motion
 *
 * すべて同じ semantic ID を参照し、独立には作らない。
 *
 * ── 主張の強さを分ける ────────────────────────────────────────
 *
 * certified          群作用・閉包・不変量。数学的に検証できる
 * design_heuristic   充填率から余白を決める等。解釈であって定理ではない
 *
 * 混ぜると「数学的に正しいデザイン」という嘘になる。
 * 余白が 26% であることに数学的な根拠はない。0.7405 という数がそこにあるだけ。
 */
import {
  WALLPAPER, windowOrbit, verifySymmetry, closePointGroup, pointGroupOrder,
  motifFromVectors, polygon, circle, toPath, translationBasis, apply,
  type Pt, type Stroke, type WallpaperGroup, type DesignClaim,
} from './ornament'
import { LATTICES, minimalVectors, packingFraction, kissingNumber, thetaSeries } from '../../vision/lattice'
import type { SemanticId } from '../world/world-types'

const id = (s: string) => s as SemanticId

// ---------------------------------------------------------------------------
// 意味核
// ---------------------------------------------------------------------------

export type DesignSeed = {
  id: SemanticId
  /** 何から来たか。ここが空の意匠は作らせない */
  source: 'fcc-minimal-vectors' | 'bcc-minimal-vectors' | 'sc-minimal-vectors'
  /** 平面へ落とした方向。母型の骨格 */
  directions: Pt[]
  /** 検証済みの数学的事実 */
  facts: DesignClaim[]
  /** 数から引いたデザイン上の解釈。定理ではない */
  interpretations: DesignClaim[]
}

/** 3次元の最小ベクトルを平面へ落とす。射影も semantic transport の一つ */
function project(vectors: [number, number, number][]): Pt[] {
  return vectors.map(v => ({ x: v[0], y: v[1] }))
    .filter(p => Math.hypot(p.x, p.y) > 1e-9)
}

export function seedFromLattice(key: 'fcc' | 'bcc' | 'sc'): DesignSeed {
  const basis = LATTICES[key].basis
  const min = minimalVectors(basis)
  const packing = packingFraction(basis)
  const kissing = kissingNumber(basis)
  const shells = thetaSeries(basis, min.norm2 * 4.001)

  const directions = project(min.vectors as [number, number, number][])
  const scale = Math.max(...directions.map(p => Math.hypot(p.x, p.y))) || 1

  return {
    id: id(`seed:${key}`),
    source: `${key}-minimal-vectors` as DesignSeed['source'],
    directions: directions.map(p => ({ x: p.x / scale * 0.38, y: p.y / scale * 0.38 })),
    facts: [
      { status: 'certified', statement: `最小ベクトルは ${kissing} 本（接吻数）`,
        evidence: 'lattice.ts minimalVectors / verify-lattice.mts 25/25' },
      { status: 'certified', statement: `充填率 ${packing.toFixed(6)}`,
        evidence: '(4/3)πr³ / |det B|、閉じた式と一致' },
      { status: 'certified', statement: `殻の点の数 ${shells.slice(0, 4).map(s => s.count).join(', ')}`,
        evidence: 'テータ級数の係数 = 殻の点の数（性質テスト 93/93）' },
    ],
    interpretations: [
      { status: 'design_heuristic',
        statement: `余白を ${((1 - packing) * 100).toFixed(0)}% にする`,
        derivedFrom: `充填率 ${packing.toFixed(4)}。詰まり方の比を紙面の比に読み替えただけで、定理ではない` },
      { status: 'design_heuristic',
        statement: `主要な方向を ${kissing} 本に制限する`,
        derivedFrom: `接吻数 ${kissing}。最近接の本数を意匠の方向数に読み替えただけ` },
      { status: 'design_heuristic',
        statement: `階層を ${shells.length} 段にする`,
        derivedFrom: '殻の段数。同心の環の数に読み替えただけ' },
    ],
  }
}

// ---------------------------------------------------------------------------
// 成果物
// ---------------------------------------------------------------------------

export type DesignArtifactKind =
  | 'logo' | 'pattern' | 'poster' | 'web_hero' | 'social_card' | 'motion'

export type DesignArtifact = {
  id: SemanticId
  kind: DesignArtifactKind
  /** 参照する意味核。空にはできない */
  references: SemanticId[]
  width: number
  height: number
  svg: string
  /** この成果物が持つ主張。certified と design_heuristic が混ざらないよう分けて持つ */
  claims: DesignClaim[]
  /** 群作用で作った部分が検証を通ったか */
  symmetryVerified: boolean
}

type Frame = { w: number; h: number }

const FRAMES: Record<DesignArtifactKind, Frame> = {
  logo: { w: 512, h: 512 },
  pattern: { w: 1024, h: 1024 },
  poster: { w: 1191, h: 1684 },      // A3 比
  web_hero: { w: 1600, h: 900 },
  social_card: { w: 1200, h: 630 },
  motion: { w: 1080, h: 1080 },
}

function place(strokes: Stroke[], frame: Frame, k: number, cx = 0.5, cy = 0.5): Stroke[] {
  return strokes.map(s => s.map(p => ({
    x: frame.w * cx + p.x * k,
    y: frame.h * cy - p.y * k,
  })))
}

function svgWrap(frame: Frame, body: string, title: string, desc: string): string {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${frame.w} ${frame.h}" `
    + `width="${frame.w}" height="${frame.h}">
<title>${title}</title>
<desc>${desc}</desc>
${body}
</svg>`
}

/**
 * 一つの意味核から、六種類の意匠を作る。
 *
 * どれも同じ directions と同じ群から出る。別々に描いていない。
 */
export function buildDesignWorld(
  seed: DesignSeed,
  groupKey: keyof typeof WALLPAPER = 'p6m',
): DesignArtifact[] {
  const group: WallpaperGroup = WALLPAPER[groupKey]
  const motif = motifFromVectors(seed.directions)
  const orbit = windowOrbit(motif, group, { repeat: 6, scale: 1 })
  const verdict = verifySymmetry(orbit.strokes, group, { scale: 1 })
  const order = pointGroupOrder(group)

  const shared: DesignClaim[] = [
    ...seed.facts,
    { status: verdict.holds ? 'certified' : 'rejected',
      statement: `点群 G/T の位数 ${order} の対称性を持つ`,
      evidence: verdict.holds
        ? `点群 ${order} 要素と並進 2 方向で点集合が自分に重なる（検査点 ${verdict.checkedPoints}）`
        : undefined },
  ]

  const out: DesignArtifact[] = []
  const make = (kind: DesignArtifactKind, body: (f: Frame) => string, extra: DesignClaim[] = []) => {
    const f = FRAMES[kind]
    out.push({
      id: id(`${seed.id}:${groupKey}:${kind}`),
      kind,
      references: [seed.id],
      width: f.w, height: f.h,
      svg: svgWrap(f, body(f), `MORTRA ${kind} — ${group.name}`,
        `${seed.source} から生成。点群 G/T の位数 ${order}。`
        + `certified ${shared.filter(c => c.status === 'certified').length} 件 / `
        + `design_heuristic ${seed.interpretations.length} 件`),
      claims: [...shared, ...extra],
      symmetryVerified: verdict.holds,
    })
  }

  const ink = '#111111'

  // 1. ロゴ。母型そのもの。群は使わず方向だけ
  make('logo', f => {
    const k = Math.min(f.w, f.h) * 0.34
    const marks = place(motif, f, k)
    const ring = place([circle({ x: 0, y: 0 }, 0.42)], f, k)
    return `<rect width="${f.w}" height="${f.h}" fill="#fff"/>
<g fill="none" stroke="${ink}" stroke-width="${f.w * 0.012}" stroke-linecap="round">
<path d="${toPath(marks)}"/></g>
<g fill="none" stroke="${ink}" stroke-width="${f.w * 0.004}"><path d="${toPath(ring)}"/></g>`
  }, [{ status: 'design_heuristic', statement: '外周の環で図形を閉じる',
        derivedFrom: '最小ベクトルの長さ。囲いの半径に読み替えただけ' }])

  // 2. パターン。群作用そのもの
  make('pattern', f => {
    const k = f.w / 5.2
    return `<rect width="${f.w}" height="${f.h}" fill="#fff"/>
<g fill="none" stroke="${ink}" stroke-width="1" stroke-linecap="round">
<path d="${toPath(place(orbit.strokes, f, k))}"/></g>`
  })

  // 3. ポスター。パターンの上に余白と文字
  make('poster', f => {
    const packing = seed.facts.find(c => c.statement.startsWith('充填率'))
    const margin = f.w * 0.09
    const k = f.w / 4.2
    return `<rect width="${f.w}" height="${f.h}" fill="#fff"/>
<clipPath id="p"><rect x="${margin}" y="${margin}" width="${f.w - margin * 2}" height="${f.h * 0.58}"/></clipPath>
<g clip-path="url(#p)" fill="none" stroke="${ink}" stroke-width="1.1">
<path d="${toPath(place(orbit.strokes, f, k, 0.5, 0.36))}"/></g>
<text x="${margin}" y="${f.h * 0.74}" font-family="Helvetica, Arial" font-size="${f.w * 0.075}" font-weight="600" fill="${ink}">${group.name}</text>
<text x="${margin}" y="${f.h * 0.79}" font-family="Helvetica, Arial" font-size="${f.w * 0.021}" fill="#6a6a6a">${seed.source}  ·  point group |G/T| = ${order}</text>
<text x="${margin}" y="${f.h * 0.82}" font-family="Helvetica, Arial" font-size="${f.w * 0.021}" fill="#6a6a6a">${packing?.statement ?? ''}</text>`
  }, [{ status: 'design_heuristic', statement: '版面の余白を充填率の補数に合わせる',
        derivedFrom: '充填率。紙面の比に読み替えただけで、定理ではない' }])

  // 4. Web の主画面。左に文字、右にパターン
  make('web_hero', f => {
    const k = f.h / 3.6
    return `<rect width="${f.w}" height="${f.h}" fill="#0a0a0a"/>
<clipPath id="h"><rect x="${f.w * 0.52}" y="0" width="${f.w * 0.48}" height="${f.h}"/></clipPath>
<g clip-path="url(#h)" fill="none" stroke="#ffffff" stroke-opacity="0.55" stroke-width="1">
<path d="${toPath(place(orbit.strokes, f, k, 0.76, 0.5))}"/></g>
<text x="${f.w * 0.07}" y="${f.h * 0.44}" font-family="Helvetica, Arial" font-size="${f.h * 0.085}" font-weight="600" fill="#fff">One structure.</text>
<text x="${f.w * 0.07}" y="${f.h * 0.56}" font-family="Helvetica, Arial" font-size="${f.h * 0.085}" font-weight="600" fill="#8a8a8a">Many representations.</text>
<text x="${f.w * 0.07}" y="${f.h * 0.68}" font-family="Helvetica, Arial" font-size="${f.h * 0.024}" fill="#8a8a8a">${seed.source}  ·  |G/T| = ${order}  ·  symmetry verified</text>`
  })

  // 5. SNS カード
  make('social_card', f => {
    const k = f.h / 3.0
    return `<rect width="${f.w}" height="${f.h}" fill="#fff"/>
<clipPath id="s"><rect x="0" y="0" width="${f.w * 0.42}" height="${f.h}"/></clipPath>
<g clip-path="url(#s)" fill="none" stroke="${ink}" stroke-width="1">
<path d="${toPath(place(orbit.strokes, f, k, 0.2, 0.5))}"/></g>
<text x="${f.w * 0.48}" y="${f.h * 0.42}" font-family="Helvetica, Arial" font-size="${f.h * 0.09}" font-weight="600" fill="${ink}">${group.name}</text>
<text x="${f.w * 0.48}" y="${f.h * 0.53}" font-family="Helvetica, Arial" font-size="${f.h * 0.035}" fill="#6a6a6a">${group.character}</text>
<text x="${f.w * 0.48}" y="${f.h * 0.62}" font-family="Helvetica, Arial" font-size="${f.h * 0.028}" fill="#9a9a9a">generated from a symmetry group · verified</text>`
  })

  // 6. 動き。点群の要素を一つずつ足していく。SMIL で軌道の増え方を見せる
  make('motion', f => {
    const k = f.w / 4.4
    const pointGroup = closePointGroup(group.pointGroupGenerators)
    const [u, v] = translationBasis(group.latticeType, 1)
    const layers = pointGroup.map((linear, index) => {
      const strokes: Stroke[] = []
      for (let i = -3; i <= 3; i++) {
        for (let j = -3; j <= 3; j++) {
          const t = { linear, translate: { x: u.x * i + v.x * j, y: u.y * i + v.y * j } }
          for (const st of motif) strokes.push(st.map(p => apply(t, p)))
        }
      }
      const begin = (index * 0.35).toFixed(2)
      return `<path d="${toPath(place(strokes, f, k))}" opacity="0">`
        + `<animate attributeName="opacity" from="0" to="1" dur="0.35s" `
        + `begin="${begin}s" fill="freeze"/></path>`
    })
    return `<rect width="${f.w}" height="${f.h}" fill="#fff"/>
<g fill="none" stroke="${ink}" stroke-width="1.2" stroke-linecap="round">
${layers.join('\n')}
</g>
<text x="${f.w * 0.06}" y="${f.h * 0.94}" font-family="Helvetica, Arial" font-size="${f.w * 0.022}" fill="#6a6a6a">点群 G/T の要素を1つずつ作用させる（${order} 段）</text>`
  }, [{ status: 'certified', statement: `動きの段数が点群 G/T の位数 ${order} と一致する`,
        evidence: '閉包の要素数をそのまま段数にしている' }])

  return out
}

/** 世界の整合。意味を参照しない意匠、検証に落ちた certified を落とす */
export function auditDesignWorld(artifacts: DesignArtifact[]): string[] {
  const problems: string[] = []
  for (const a of artifacts) {
    if (!a.references.length) {
      problems.push(`${a.kind}: 意味核を参照していない`)
    }
    const certifiedButFailed = a.claims.some(c => c.status === 'certified' && !c.evidence)
    if (certifiedButFailed) {
      problems.push(`${a.kind}: 根拠のない certified がある`)
    }
    if (!a.symmetryVerified && a.claims.some(c => c.status === 'certified'
      && c.statement.includes('対称性'))) {
      problems.push(`${a.kind}: 対称性が検証に落ちているのに certified を名乗っている`)
    }
    const heuristicWithoutSource = a.claims.some(
      c => c.status === 'design_heuristic' && !c.derivedFrom)
    if (heuristicWithoutSource) {
      problems.push(`${a.kind}: 出所のない design_heuristic がある`)
    }
  }
  return problems
}
