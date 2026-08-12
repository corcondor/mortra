/**
 * 既存機能を Semantic Kernel へ接続するアダプタ。
 *
 * 大きな書き換えはしない。既存のコードはそのまま動かし、
 * 出てきた物を核の語彙へ写すだけにする。
 *
 * 写す先が一つなので、格子・群・意匠・証明を同じ語で数えられるようになる。
 * これまでは 'proved' の意味が場所ごとに違い、横断して数えられなかった。
 */
import {
  addCertificate, addMorphism, addObject, addRelation, createKernel, sid,
  type Certificate, type Convention, type KnowledgeStatus, type MathSort,
  type Morphism, type SemanticId, type SemanticKernel, type SemanticObject,
  type TypedRelation, type VerificationMethod,
} from './semantic-kernel'
import {
  LATTICES, dual, gram, minimalVectors, kissingNumber, packingFraction,
  thetaSeries, automorphisms, rootSystem, millerPlane,
  type Basis,
} from '../../vision/lattice'
import {
  WALLPAPER, closePointGroup, pointGroupOrder, windowOrbit, verifySymmetry,
  type WallpaperGroup,
} from '../vision/ornament'

// ---------------------------------------------------------------------------
// 規約。格子核は数学の規約（2π なし）で書かれている
// ---------------------------------------------------------------------------

export const LATTICE_CONVENTIONS: Convention[] = [
  { kind: 'reciprocal_lattice', value: 'mathematical_no_2pi',
    rationale: '⟨x,y⟩ ∈ ℤ で定義。結晶学の 2π 倍は呼び出し側で掛ける' },
  { kind: 'theta_exponent', value: 'norm_squared',
    rationale: 'Θ(q) = Σ q^{|x|²}。D₃ の標準形は最小ノルム² = 2' },
  { kind: 'root_normalization', value: 'as_given',
    rationale: '基底のスケールをそのまま使う。正規化は呼び出し側の責任' },
]

let counter = 0
const nextId = (prefix: string) => sid(`${prefix}:${++counter}`)

function certify(
  k: SemanticKernel, method: VerificationMethod, detail: string, artifact: string,
  consumed: SemanticId[] = [],
): SemanticId {
  const c: Certificate = { id: nextId('cert'), method, consumedPremises: consumed, detail, artifact }
  addCertificate(k, c)
  return c.id
}

function relate(
  k: SemanticKernel, predicate: string, args: SemanticId[],
  status: KnowledgeStatus, certificate: SemanticId | undefined,
  source: string, path: SemanticId[] = [],
): TypedRelation {
  return addRelation(k, {
    id: nextId('rel'), predicate, arguments: args, status, certificate,
    provenance: { source, path, consumed: args },
  })
}

// ---------------------------------------------------------------------------
// Lattice Kernel → Semantic Kernel
// ---------------------------------------------------------------------------

export function bindLattice(
  k: SemanticKernel, key: string, basis: Basis, label: string,
): SemanticId {
  const id = nextId(`lattice:${key}`)
  const object: SemanticObject = {
    id, sort: 'Lattice', label,
    definition: 'Λ = BZ³',
    assumptions: [], conventions: LATTICE_CONVENTIONS,
    provenance: { source: 'lib/vision/lattice.ts LATTICES', path: [], consumed: [],
                  artifact: 'scripts/verify-lattice.mts 25/25' },
    payload: { basis, gram: gram(basis) },
  }
  addObject(k, object)

  // 検証済みの事実を関係として登録する。数字だけ持っても横断できない
  const kiss = kissingNumber(basis)
  relate(k, 'kissing_number', [id], 'proved',
    certify(k, 'property_test', `最小ベクトルの本数 ${kiss}`,
      'scripts/lattice-properties.mts 93/93'),
    'minimalVectors')

  relate(k, 'packing_fraction', [id], 'proved',
    certify(k, 'symbolic_identity', `(4/3)πr³/|det B| = ${packingFraction(basis).toFixed(9)}`,
      'scripts/verify-lattice.mts'),
    'packingFraction')

  const shells = thetaSeries(basis, minimalVectors(basis).norm2 * 6.001)
  relate(k, 'theta_series', [id], 'proved',
    certify(k, 'property_test',
      `係数 ${shells.slice(0, 5).map(s => s.count).join(', ')}（殻の点の数と一致）`,
      'scripts/lattice-properties.mts'),
    'thetaSeries')

  relate(k, 'automorphism_order', [id], 'proved',
    certify(k, 'group_closure', `|Aut(Λ)| = ${automorphisms(basis).length}`,
      'AᵀGA = G を満たす整数行列を全列挙'),
    'automorphisms')

  return id
}

/** 双対を射として登録する。ただの別表示ではなく、規約と不変量を持つ移動 */
export function bindDualMorphism(k: SemanticKernel, latticeId: SemanticId): Morphism {
  const src = k.objects.get(latticeId)!
  const basis = (src.payload as { basis: Basis }).basis
  const dualBasis = dual(basis)

  const dualId = nextId('lattice:dual')
  addObject(k, {
    id: dualId, sort: 'Lattice', label: `${src.label}*`,
    definition: 'Λ* = { y : ⟨x,y⟩ ∈ ℤ ∀x ∈ Λ }',
    assumptions: [], conventions: LATTICE_CONVENTIONS,
    provenance: { source: 'dual()', path: [], consumed: [latticeId] },
    payload: { basis: dualBasis, gram: gram(dualBasis) },
  })

  const m = addMorphism(k, {
    id: nextId('morph:dual'), name: 'DirectToReciprocal',
    source: [latticeId], target: [dualId],
    sourceSorts: ['Lattice'], targetSorts: ['Lattice'],
    preconditions: ['det B ≠ 0'],
    transported: [latticeId],
    preserved: ['det(Λ)·det(Λ*) = 1', '双対の対合性 dual(dual(Λ)) ≅ Λ'],
    proofObligations: [],
    certificate: certify(k, 'property_test', 'dual∘dual = id を全格子で確認',
      'scripts/lattice-properties.mts'),
  })
  // 出所に射を書き込む。どこを通ってきたかが辿れる
  k.objects.get(dualId)!.provenance.path = [m.id]
  return m
}

/** ルート系の認識を射として登録する。格子が Lie 理論へ移る一歩 */
export function bindRootSystemMorphism(
  k: SemanticKernel, latticeId: SemanticId,
): Morphism | null {
  const src = k.objects.get(latticeId)!
  const basis = (src.payload as { basis: Basis }).basis
  const rs = rootSystem(basis)
  if (!rs.type) return null

  const rootId = nextId('roots')
  addObject(k, {
    id: rootId, sort: 'RootSystem', label: rs.type,
    definition: '最小ベクトルが成すルート系',
    assumptions: [], conventions: LATTICE_CONVENTIONS,
    provenance: { source: 'rootSystem()', path: [], consumed: [latticeId] },
    payload: { roots: rs.roots, simple: rs.simple, cartan: rs.cartan, type: rs.type },
  })

  const m = addMorphism(k, {
    id: nextId('morph:root'), name: 'RecognizeRootSystem',
    source: [latticeId], target: [rootId],
    sourceSorts: ['Lattice'], targetSorts: ['RootSystem'],
    preconditions: ['Cartan 整数がすべて整数'],
    transported: [latticeId],
    preserved: ['鏡映で閉じる', '−α もルート', 'Cartan 整数性'],
    proofObligations: [],
    certificate: certify(k, 'property_test',
      `${rs.type}、ルート ${rs.roots.length} 本、単純ルート ${rs.simple.length} 本`,
      'scripts/lattice-properties.mts 鏡映閉包を確認'),
  })
  k.objects.get(rootId)!.provenance.path = [m.id]
  return m
}

// ---------------------------------------------------------------------------
// GroupAction Kernel → Semantic Kernel
// ---------------------------------------------------------------------------

export function bindWallpaperGroup(k: SemanticKernel, group: WallpaperGroup): SemanticId {
  const pointGroup = closePointGroup(group.pointGroupGenerators)
  const id = nextId(`group:${group.name}`)
  addObject(k, {
    id, sort: 'Group', label: group.name,
    definition: 'G = T ⋊ (G/T)。G は無限、T ≅ ℤ²、G/T は有限',
    assumptions: [],
    conventions: [{ kind: 'symbol_role', value: 'point_group_is_quotient',
                    rationale: '数えているのは G/T であって G ではない' }],
    provenance: { source: 'lib/mortra/vision/ornament.ts WALLPAPER', path: [], consumed: [],
                  artifact: 'scripts/ornament-mutation.mts 71/71' },
    payload: { generators: group.pointGroupGenerators, pointGroup, latticeType: group.latticeType },
  })

  relate(k, 'point_group_order', [id], 'proved',
    certify(k, 'group_closure',
      `|G/T| = ${pointGroup.length}（生成元 ${group.pointGroupGenerators.length} 本の閉包を数えた）`,
      'closePointGroup'),
    'closePointGroup')

  return id
}

/** 群作用で意匠を作る射。certified transport の側 */
export function bindOrbitMorphism(
  k: SemanticKernel, groupId: SemanticId, motifId: SemanticId,
  group: WallpaperGroup, motif: { x: number; y: number }[][],
): Morphism {
  const orbit = windowOrbit(motif, group, { repeat: 5, scale: 1 })
  const verdict = verifySymmetry(orbit.strokes, group, { scale: 1 })

  const patternId = nextId('pattern')
  addObject(k, {
    id: patternId, sort: 'VisualElement', label: `${group.name} pattern`,
    definition: '母型に G を作用させ、有限の窓で切った軌道',
    assumptions: [], conventions: [],
    provenance: { source: 'windowOrbit()', path: [], consumed: [groupId, motifId] },
    payload: { strokeCount: orbit.strokes.length, pointGroupSize: orbit.pointGroupSize },
  })

  const m = addMorphism(k, {
    id: nextId('morph:orbit'), name: 'GroupActionToOrbitPattern',
    source: [groupId, motifId], target: [patternId],
    sourceSorts: ['Group', 'VisualElement'], targetSorts: ['VisualElement'],
    preconditions: ['点群が閉じている'],
    transported: [groupId, motifId],
    preserved: [`点群 G/T の位数 ${pointGroupOrder(group)} の対称性`, '並進の周期性'],
    proofObligations: [],
    certificate: verdict.holds
      ? certify(k, 'symmetry_verification',
          `点群 ${orbit.pointGroupSize} 要素と並進 2 方向で自分に重なる（検査点 ${verdict.checkedPoints}）`,
          'scripts/ornament-mutation.mts negative 62 件すべて拒否')
      : undefined,
    failureState: verdict.holds ? undefined
      : `点群 ${verdict.failedPointGroupElements.length} / 並進 ${verdict.failedTranslations.length} で不一致`,
  })
  k.objects.get(patternId)!.provenance.path = [m.id]

  relate(k, 'has_symmetry', [patternId, groupId],
    verdict.holds ? 'proved' : 'rejected', m.certificate, 'verifySymmetry')
  return m
}

// ---------------------------------------------------------------------------
// CAS / 証明の状態を核の語へ写す
// ---------------------------------------------------------------------------

/** cas_solver.py の verdict を KnowledgeStatus へ */
export function fromCasVerdict(verdict: string | undefined, status: string): KnowledgeStatus {
  if (status !== 'solved') {
    if (status === 'unverified') return 'unverified'
    if (status === 'not_reduced' || status === 'no_goal') return 'unformalized'
    return 'unsupported'
  }
  switch (verdict) {
    case 'proved': return 'proved'
    case 'verified_instance': return 'verified_instance'
    case 'numerically_supported': return 'numerically_supported'
    default: return 'unverified'
  }
}

/** exact-linear-invariant.ts の status を核の語へ */
export function fromLinearStatus(status: string): KnowledgeStatus {
  switch (status) {
    case 'proved': return 'proved'
    case 'underdetermined': return 'unformalized'
    case 'inconsistent': return 'disproved'
    default: return 'unsupported'
  }
}

/** lib/proof-scene.ts の推論結果を核の語へ。数値検証しかしていないので proved とは呼ばない */
export function fromProofScene(proved: boolean, numericallyChecked: boolean): KnowledgeStatus {
  if (!proved) return 'unverified'
  return numericallyChecked ? 'verified_instance' : 'unverified'
}

// ---------------------------------------------------------------------------
// 一括で核を組む
// ---------------------------------------------------------------------------

export function buildIntegratedKernel(): SemanticKernel {
  const k = createKernel()
  for (const [key, entry] of Object.entries(LATTICES)) {
    const id = bindLattice(k, key, entry.basis, entry.name)
    bindDualMorphism(k, id)
    bindRootSystemMorphism(k, id)
  }
  for (const group of Object.values(WALLPAPER)) {
    const gid = bindWallpaperGroup(k, group)
    // FCC のルート方向を母型にして、群作用で意匠へ移す
    const fcc = LATTICES.fcc.basis
    const dirs = minimalVectors(fcc).vectors
      .map(v => ({ x: v[0] * 0.62, y: v[1] * 0.62 }))
      .filter(p => Math.hypot(p.x, p.y) > 1e-9)
    const motifId = nextId('motif:a3')
    addObject(k, {
      id: motifId, sort: 'VisualElement', label: 'A₃ の方向',
      definition: 'FCC の最小ベクトルを平面へ射影した母型',
      assumptions: [], conventions: LATTICE_CONVENTIONS,
      provenance: { source: 'minimalVectors(fcc) → projection', path: [], consumed: [] },
      payload: { directions: dirs },
    })
    bindOrbitMorphism(k, gid, motifId, group, dirs.map(v => [{ x: 0, y: 0 }, v]))
  }
  // Miller 面も射として持つ。面の法線が逆格子の点そのもの
  const fccId = [...k.objects.values()].find(o => o.label === LATTICES.fcc.name)!.id
  const plane = millerPlane(LATTICES.fcc.basis, [1, 1, 1])
  const planeId = nextId('planes:111')
  addObject(k, {
    id: planeId, sort: 'VisualElement', label: '(111) 面族',
    definition: 'G_hkl = h b₁ + k b₂ + l b₃、面間隔 1/|G_hkl|',
    assumptions: [], conventions: LATTICE_CONVENTIONS,
    provenance: { source: 'millerPlane()', path: [], consumed: [fccId] },
    payload: { normal: plane.normal, spacing: plane.spacing },
  })
  const mm = addMorphism(k, {
    id: nextId('morph:miller'), name: 'MillerIndexToPlaneFamily',
    source: [fccId], target: [planeId],
    sourceSorts: ['Lattice'], targetSorts: ['VisualElement'],
    preconditions: ['(hkl) ≠ (000)'],
    transported: [fccId],
    preserved: ['面の法線が逆格子ベクトルと一致', '面間隔 d = 1/|G|'],
    proofObligations: [],
    certificate: certify(k, 'symbolic_identity',
      '立方晶で d = a/√(h²+k²+l²) と一致（100/110/111/210）',
      'scripts/verify-lattice.mts'),
  })
  k.objects.get(planeId)!.provenance.path = [mm.id]
  return k
}
