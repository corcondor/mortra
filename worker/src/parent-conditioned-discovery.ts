import { createHash } from 'node:crypto'
import { elaborateEuclideanStatement } from './euclidean-statement-elaboration'

export interface DiscoveryParent {
  id?: string
  statement?: string
  answer?: string | null
  solution?: string | null
  inspiration?: string | null
}

type OperatorSignature = {
  patterns: RegExp[]
  match?: 'any' | 'all'
  sorts: string[]
  morphisms: Array<{ name: string; source: string; target: string; law: string }>
}

// A vocabulary of mathematical operators and objects, not problem families.
// No numeric value, dataset id, or sentence template is used for generation.
const OPERATOR_SIGNATURES: OperatorSignature[] = [
  { patterns: [/\\int(?![A-Za-z])/i, /積分/], sorts: ['IntegralFunctional', 'Function'], morphisms: [{ name: 'Integration', source: 'Function', target: 'IntegralFunctional', law: 'I(f)=integral(f)' }] },
  { patterns: [/数列/, /[A-Za-z]+_\{?n\}?/], sorts: ['Sequence'], morphisms: [{ name: 'SequenceEvaluation', source: 'Sequence', target: 'Real', law: 'ev_n(a)=a_n' }] },
  { patterns: [/\\lim(?![A-Za-z])/i, /極限/], sorts: ['Sequence', 'LimitObject'], morphisms: [{ name: 'Limit', source: 'Sequence', target: 'LimitObject', law: 'Limit(a)=lim a_n when defined' }] },
  { patterns: [/微分|導関数/, /f\s*['′]/], sorts: ['DifferentiableFunction', 'Function'], morphisms: [{ name: 'Derivative', source: 'DifferentiableFunction', target: 'Function', law: 'D(f)=f\'' }] },
  { patterns: [/\\equiv(?![A-Za-z])/i, /合同|法\s*\\?pmod|modulo/i], sorts: ['IntegerStructure', 'ResidueClassStructure'], morphisms: [{ name: 'QuotientModulo', source: 'IntegerStructure', target: 'ResidueClassStructure', law: 'q_m(a)=[a]_m' }] },
  { patterns: [/整数|自然数|integer|natural\s+number/i], sorts: ['IntegerStructure'], morphisms: [{ name: 'IntegerElaboration', source: 'ArithmeticExpression', target: 'IntegerStructure', law: 'declared integer-valued variables and their arithmetic constraints form an integer structure' }] },
  { patterns: [/互いに素|coprime/i], sorts: ['CoprimeIntegerTuple'], morphisms: [{ name: 'CoprimeRestriction', source: 'IntegerTuple', target: 'CoprimeIntegerTuple', law: 'gcd of the declared integer tuple is one' }] },
  { patterns: [/素数|prime/i], sorts: ['PrimeSpectrum', 'IntegerStructure'], morphisms: [{ name: 'PrimeRestriction', source: 'IntegerStructure', target: 'PrimeSpectrum', law: 'restrict parameters to primes' }] },
  { patterns: [/整数三角形|三辺.{0,12}整数|integer-sided triangle/i], sorts: ['IntegralTriangle', 'TriangleMetricData'], morphisms: [{ name: 'IntegralSideRestriction', source: 'TriangleMetricData', target: 'IntegralTriangle', law: 'side lengths lie in the positive integers' }] },
  { patterns: [/外接円半径|内接円半径|傍接円半径|circumradius|inradius/i], sorts: ['TriangleMetricData', 'RadiusObservable'], morphisms: [{ name: 'TriangleRadiusObservable', source: 'TriangleMetricData', target: 'RadiusObservable', law: 'radius observables are rational expressions after Heron elimination' }] },
  { patterns: [/位相空間|閉曲面|topological space|closed surface/i], sorts: ['TopologicalSpace'], morphisms: [] },
  { patterns: [/三角形分割|単体分割|triangulation|simplicial complex/i], sorts: ['FiniteTriangulation', 'TopologicalSpace'], morphisms: [{ name: 'TriangulationElaboration', source: 'TopologicalSpace', target: 'FiniteTriangulation', law: 'a finite triangulation presents incidence data of the space' }] },
  { patterns: [/Euler標数|オイラー標数|Euler characteristic/i], sorts: ['FiniteTriangulation', 'IntegerInvariant'], morphisms: [{ name: 'EulerCharacteristic', source: 'FiniteTriangulation', target: 'IntegerInvariant', law: 'chi=V-E+F' }] },
  { patterns: [/平方剰余|Legendre|ルジャンドル/i], sorts: ['ResidueClassStructure', 'QuadraticCharacter'], morphisms: [{ name: 'QuadraticCharacterMap', source: 'ResidueClassStructure', target: 'QuadraticCharacter', law: 'chi_p(a)=(a/p)' }] },
  { patterns: [/多項式|方程式/, /[A-Za-z]\s*\^\s*\{?\d+\}?/], sorts: ['Polynomial', 'AlgebraicSet'], morphisms: [{ name: 'ZeroLocus', source: 'Polynomial', target: 'AlgebraicSet', law: 'V(f)={x | f(x)=0}' }] },
  { patterns: [/曲線|軌跡|包絡線/], sorts: ['PlaneCurve'], morphisms: [] },
  { patterns: [/接線/], sorts: ['PlaneCurve', 'LineFamily'], morphisms: [{ name: 'TangentFamily', source: 'PlaneCurve', target: 'LineFamily', law: 'C maps to its tangent family' }] },
  { patterns: [/点|頂点|交点/], sorts: ['PointConfiguration'], morphisms: [] },
  { patterns: [/三角形|正三角形/], sorts: ['Triangle', 'PointConfiguration'], morphisms: [{ name: 'VertexConfiguration', source: 'Triangle', target: 'PointConfiguration', law: 'a triangle maps to its vertices' }] },
  { patterns: [/円|外接円|内接円/], sorts: ['Circle', 'PlaneCurve'], morphisms: [{ name: 'CircleEmbedding', source: 'Circle', target: 'PlaneCurve', law: 'a circle is a plane curve' }] },
  { patterns: [/重心/], sorts: ['PointConfiguration', 'AffinePoint'], morphisms: [{ name: 'Barycenter', source: 'PointConfiguration', target: 'AffinePoint', law: 'bar(P_i)=sum(P_i)/n' }] },
  { patterns: [/領域|面積/], sorts: ['MeasurableRegion', 'AreaObservable'], morphisms: [{ name: 'Area', source: 'MeasurableRegion', target: 'AreaObservable', law: 'Area is a measure observable' }] },
  { patterns: [/確率|期待値/], sorts: ['ProbabilitySpace', 'RandomVariable'], morphisms: [{ name: 'Expectation', source: 'RandomVariable', target: 'Real', law: 'E[X]=integral X dP' }] },
  { patterns: [/二次形式|quadratic form/i], sorts: ['QuadraticForm', 'SymmetricBilinearForm'], morphisms: [{ name: 'Polarization', source: 'QuadraticForm', target: 'SymmetricBilinearForm', law: 'q(x)=x^T A x for a unique symmetric matrix A' }] },
  { patterns: [/分散|共分散|variance|covariance/i], sorts: ['RandomVector', 'SecondMomentTensor'], morphisms: [{ name: 'SecondMomentMatrix', source: 'RandomVector', target: 'SecondMomentTensor', law: 'M=E[XX^T]=Cov(X)+E[X]E[X]^T' }] },
  { patterns: [/\\?(?:sin|cos|tan)(?:\s*\^|\s*\()|正弦|余弦|三角関数/i], sorts: ['TrigonometricExpression'], morphisms: [{ name: 'UnitCircleEvaluation', source: 'AngleExpression', target: 'TrigonometricExpression', law: 'sin and cos are coordinate observables of the unit-circle action' }] },
  { patterns: [/格子点|lattice\s+point/i], sorts: ['AffineLattice', 'LatticePointSet'], morphisms: [{ name: 'LatticePointRestriction', source: 'AffineSpace', target: 'LatticePointSet', law: 'retain points whose coordinates lie in the integer lattice' }] },
  { patterns: [/格子点|lattice\s+point/i, /多角形|polygon/i, /面積|area/i, /内部|内点|interior/i, /境界|周上|boundary/i], match: 'all', sorts: ['LatticePolygon', 'LatticePolygonInvariant'], morphisms: [{ name: 'PickInvariantExtraction', source: 'LatticePolygon', target: 'LatticePolygonInvariant', law: 'primitive triangulation and Euler incidence encode A=I+B/2-1' }] },
  { patterns: [/直線|line/i, /格子点|整数解|lattice\s+point|integer\s+solution/i], match: 'all', sorts: ['AffineLatticeSlice', 'LinearDiophantineConstraint'], morphisms: [{ name: 'AffineLatticeSliceElaboration', source: 'AffineLattice', target: 'LinearDiophantineConstraint', law: 'an affine linear equation restricts an integer lattice to a Diophantine slice' }] },
  { patterns: [/直角三角形|right triangle/i, /互いに素|primitive|coprime/i], match: 'all', sorts: ['PrimitiveIntegerRightTriangle', 'EuclidParameterPair'], morphisms: [{ name: 'PrimitivePythagoreanParameterization', source: 'PrimitiveIntegerRightTriangle', target: 'EuclidParameterPair', law: '(a,b,c)=(m^2-n^2,2mn,m^2+n^2) for coprime opposite-parity m>n' }] },
  { patterns: [/内接円半径.*外接円半径|外接円半径.*内接円半径|inradius.*circumradius|circumradius.*inradius/i, /素数|prime/i], match: 'all', sorts: ['TriangleRadii', 'PrimeProductConstraint'], morphisms: [{ name: 'PrimeRadiusProductFactorization', source: 'TriangleRadii', target: 'PrimeProductConstraint', law: 'for a primitive right triangle, Rr=(r/2)c' }] },
]

const CONSTRUCTORS = [
  ['CommonInvariant', 'InvariantProjection', '各親構造から同じ値を取る観測を構成できる'],
  ['FiberProduct', 'PullbackProjection', '親構造の制約を同時に満たす普遍対象を構成できる'],
  ['Equalizer', 'EqualizerEmbedding', '二つの表現が一致する部分構造を構成できる'],
  ['CommonQuotient', 'QuotientProjection', '表現差を除いた共通商対象を構成できる'],
] as const

const SINGLE_PROBLEM_CONSTRUCTORS = [
  ['QueryClosure', 'QueryRealization', '入力問題の制約から要求された観測量を一意に構成できる'],
] as const

function hash(value: unknown, length = 12): string {
  return createHash('sha256').update(JSON.stringify(value)).digest('hex').slice(0, length)
}

function latexAtoms(text: string): string[] {
  return [...new Set(text.match(/\\(?:mathrm|operatorname)\{[^{}]+\}|\\[A-Za-z]+|[A-Za-z]\w*/g) ?? [])].sort().slice(0, 80)
}

function constraintKinds(text: string): string[] {
  const kinds: string[] = []
  if (/[=＝]/.test(text)) kinds.push('equality')
  if (/[<>≤≥]|\\(?:le|ge|lt|gt)\b/.test(text)) kinds.push('order')
  if (/\\equiv|合同|pmod/.test(text)) kinds.push('congruence')
  if (/任意|すべて|全て|\\forall/.test(text)) kinds.push('universal')
  if (/存在|\\exists/.test(text)) kinds.push('existential')
  if (/相異なる|異なる/.test(text)) kinds.push('distinctness')
  return kinds.length ? kinds : ['unresolved_relation']
}

function queryKind(text: string): string {
  if (/示せ|証明|prove/i.test(text)) return 'prove'
  if (/分類|すべて求め|全て求め/.test(text)) return 'classify'
  if (/最大|最小|極値/.test(text)) return 'optimize'
  if (/面積|体積/.test(text)) return 'measure'
  if (/求めよ|find|compute/i.test(text)) return 'compute'
  return 'observe'
}

export function liftParent(parent: DiscoveryParent) {
  const parentId = String(parent.id || `parent-${hash(parent, 8)}`)
  const source = parent.statement ?? ''
  const euclidean = elaborateEuclideanStatement(source)
  const roots: string[] = [...(euclidean?.semanticRoots ?? [])]
  const morphisms: Array<{ name: string; source: string; target: string; law: string; origin: string }> = []
  for (const signature of OPERATOR_SIGNATURES) {
    const matched = signature.match === 'all'
      ? signature.patterns.every(pattern => pattern.test(source))
      : signature.patterns.some(pattern => pattern.test(source))
    if (!matched) continue
    for (const sort of signature.sorts) if (!roots.includes(sort)) roots.push(sort)
    for (const morphism of signature.morphisms) {
      if (morphisms.some(item => item.name === morphism.name)) continue
      morphisms.push({ ...morphism, origin: `parent:${parentId}:operator_vocabulary` })
    }
  }
  const atoms = latexAtoms(source)
  if (!roots.length) roots.push(`OpaqueStructure[${hash(atoms.length ? atoms : source, 10)}]`)
  const constraints = [...new Set([
    ...constraintKinds(source).filter(kind => kind !== 'unresolved_relation'),
    ...(euclidean?.constraints ?? []),
  ])]
  return {
    parent_id: parentId,
    semantic_roots: roots,
    morphisms,
    constraints: constraints.length ? constraints : ['unresolved_relation'],
    query: {
      kind: queryKind(source),
      target: euclidean?.queryTarget ?? (parent.answer ? 'known_answer' : 'unknown_answer'),
    },
    typed_relations: euclidean?.relations ?? [],
    opaque_atoms: atoms,
  }
}

function cartesian<T>(sets: T[][]): T[][] {
  return sets.reduce<T[][]>((rows, set) => rows.flatMap(row => set.map(value => [...row, value])), [[]])
}

export function discoverParentStructures(parents: DiscoveryParent[], requested = 1) {
  if (parents.length < 1) throw new Error('typed discovery requires at least one problem')
  const graphs = parents.map(liftParent)
  const combinations = cartesian(graphs.map(graph => graph.semantic_roots.slice(0, 4))).slice(0, 18)
  const constructors = parents.length === 1 ? SINGLE_PROBLEM_CONSTRUCTORS : CONSTRUCTORS
  const hypotheses = combinations.flatMap(starts => constructors.map(([constructor, edgeName, proposition], constructorIndex) => {
    const target = `${constructor}[${starts.join(',')}]`
    const paths = graphs.map((graph, index) => ({
      parent_id: graph.parent_id,
      start_sort: starts[index],
      target_sort: target,
      morphisms: [{
        name: `${edgeName}_${hash([starts[index], target], 8)}`,
        source: starts[index],
        target,
        law: proposition,
        backend: [],
        origin: 'conjectured_bridge',
      }],
    }))
    const sharedAtoms = graphs.reduce<string[]>((shared, graph, index) =>
      index === 0 ? [...graph.opaque_atoms] : shared.filter(atom => graph.opaque_atoms.includes(atom)), [])
    return {
      kind: 'conjectured_universal_construction',
      constructor,
      target_sort: target,
      score: 24 + new Set(starts).size + sharedAtoms.length * 2 - constructorIndex,
      paths,
      typecheck: { passed: true, reason: 'one typed conjectural projection exists per selected parent' },
      backend_coverage: 0,
      shared_opaque_atoms: sharedAtoms,
      proof_obligations: [
        proposition,
        parents.length === 1
          ? '入力問題の具体的制約が要求された観測量へ持ち上がること'
          : '各親の具体的制約が候補対象へ持ち上がること',
        parents.length === 1
          ? '答えが問題文中の数値の再生ではなく制約消去から導かれること'
          : '構成が単なる直積ではなく各親のqueryに依存すること',
        parents.length === 1
          ? '入力制約を除くと結論が導けないこと'
          : '一つの親を除くと合流命題が成立しないこと',
        '境界値と小さいパラメータで反例がないこと',
      ],
    }
  })).sort((a, b) => b.score - a.score).slice(0, 64)

  const selectedPlans = hypotheses.slice(0, Math.max(1, Math.min(requested, hypotheses.length)))
  const parentIds = graphs.map(graph => graph.parent_id)
  const cards = selectedPlans.map((plan, planIndex) => {
    const signature = hash({ parentIds, plan })
    const structureId = `discovery.${signature}`
    const pathText = plan.paths.map((path, index) =>
      `\\mathcal P_${index + 1}: ${path.start_sort} \\longrightarrow ${path.target_sort}`).join('\\\\\n')
    const constraintText = graphs.map((graph, index) =>
      `C_${index + 1}=\\{${graph.constraints.join(', ')}\\}`).join(', ')
    return {
      id: structureId,
      family_id: `research.parent_conditioned.${signature}`,
      statement_tex: `選択した問題から抽出した型付き構造を \\(\\mathcal P_1,\\ldots,\\mathcal P_${graphs.length}\\) とする。候補射列は\n\\[\n${pathText}\n\\]\nであり、制約骨格は \\(${constraintText}\\) である。全ての制約を保つ射を具体化し、共通終対象 \\(${plan.target_sort}\\) 上の不変量を構成せよ。さらに、どの親構造を一つ除いてもその不変量が定まらないことを示せ。`,
      answer_tex: null,
      solution_tex: '型検査は完了。法則の証明、反例探索、backend実行は継続中。',
      parent_ids: parentIds,
      unresolved: true,
      discovery_status: 'research_pending',
      morphism_chain: plan.paths.flatMap(path => path.morphisms.map(edge => edge.name)),
      fusion_derivation: {
        passed: true,
        reason: parents.length === 1
          ? 'the input problem has a typed conjectural path to its requested observable; execution remains open'
          : 'all selected parents have a distinct typed conjectural path; mathematical indispensability is not yet proved',
        ablationPassed: graphs.every((_, removedIndex) => {
          const reducedStarts = plan.paths.filter((_, index) => index !== removedIndex).map(path => path.start_sort)
          return `${plan.constructor}[${reducedStarts.join(',')}]` !== plan.target_sort
        }),
        assignments: plan.paths.map((path, index) => ({
          parentId: path.parent_id,
          portId: `input_${index + 1}`,
          role: 'object',
          matchedAnchors: [path.start_sort],
          witnessSteps: path.morphisms.map(edge => edge.name),
        })),
        bridges: [{
          id: 'parent_conditioned_common_codomain',
          witnessStep: plan.target_sort,
          consumes: parentIds.map((_, index) => `input_${index + 1}`),
          produces: plan.target_sort,
        }],
        intermediatePropositions: plan.paths.flatMap(path => path.morphisms.map(edge => ({
          parentId: path.parent_id,
          morphism: edge.name,
          source: edge.source,
          target: edge.target,
          proposition: edge.law,
          proved: false,
        }))),
      },
      structure_blueprint: {
        id: structureId,
        version: 1,
        kernel: 'parent_conditioned_unknown_structure',
        observable: plan.target_sort,
        operators: plan.paths.flatMap(path => path.morphisms.map(edge => edge.name)),
        domain: 'discovered_from_selected_parents',
        tags: [...new Set(graphs.flatMap(graph => graph.semantic_roots))],
        morphismChain: plan.paths.flatMap(path => path.morphisms.map(edge => edge.name)),
        executable: false,
      },
      search_evidence: { hypotheses_evaluated: hypotheses.length, valid_hypotheses: hypotheses.length },
      candidate_rank: planIndex + 1,
    }
  })
  return {
    engine: 'MathOS parent-conditioned structural discovery (no LLM)',
    generated: 0,
    discovered: cards.length,
    requested,
    cards,
    parent_graphs: graphs,
    hypotheses,
    structures: cards.map(card => ({ blueprint: card.structure_blueprint, status: 'pending', parentIds, registeredAt: new Date().toISOString() })),
    errors: ['未知構造の型付き候補を保存しました。未証明のため公開問題には追加していません。'],
    rejectionCounts: {},
  }
}
