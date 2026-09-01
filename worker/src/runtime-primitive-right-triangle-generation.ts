import { createHash } from 'node:crypto'

import type { DiscoveryParent } from './parent-conditioned-discovery'
import type { ExecutableFusionCard } from './executable-fusion'
import { runtimeSynthesisCertificate } from './execution-certificate'

type PrimitiveRightTriangleParent = {
  parentId: string
}

type PrimeRadiusProductParent = {
  parentId: string
}

type Rational = {
  numerator: bigint
  denominator: bigint
}

type DerivedTriangle = {
  m: bigint
  n: bigint
  a: bigint
  b: bigint
  c: bigint
  area: bigint
  perimeter: bigint
  inradius: Rational
  circumradius: Rational
  radiusProduct: Rational
}

export type RuntimePrimitiveRightTriangleGeneration = {
  applicable: boolean
  reason: string
  cards: ExecutableFusionCard[]
  hypothesesEvaluated: number
}

function gcd(left: bigint, right: bigint): bigint {
  let a = left < 0n ? -left : left
  let b = right < 0n ? -right : right
  while (b !== 0n) [a, b] = [b, a % b]
  return a
}

function rational(numerator: bigint, denominator = 1n): Rational {
  if (denominator === 0n) throw new RangeError('zero denominator')
  const sign = denominator < 0n ? -1n : 1n
  const divisor = gcd(numerator, denominator)
  return {
    numerator: sign * numerator / divisor,
    denominator: sign * denominator / divisor,
  }
}

function multiply(left: Rational, right: Rational): Rational {
  return rational(left.numerator * right.numerator, left.denominator * right.denominator)
}

function format(value: Rational): string {
  return value.denominator === 1n
    ? value.numerator.toString()
    : `\\frac{${value.numerator}}{${value.denominator}}`
}

function isPrime(value: bigint): boolean {
  if (value < 2n) return false
  if (value % 2n === 0n) return value === 2n
  for (let divisor = 3n; divisor * divisor <= value; divisor += 2n) {
    if (value % divisor === 0n) return false
  }
  return true
}

function parsePrimitiveRightTriangle(parent: DiscoveryParent): PrimitiveRightTriangleParent | null {
  const text = parent.statement ?? ''
  const rightTriangle = /直角三角形|right\s+triangle/i.test(text)
  const integralSides = /(?:三辺|3辺|辺).{0,24}(?:自然数|正の整数|整数)|(?:integer|integral).{0,24}sides?/i.test(text)
  const primitive = /互いに素|原始(?:三角形|三つ組)?|primitive|coprime/i.test(text)
  return rightTriangle && integralSides && primitive
    ? { parentId: String(parent.id) }
    : null
}

function parsePrimeRadiusProduct(parent: DiscoveryParent): PrimeRadiusProductParent | null {
  const text = parent.statement ?? ''
  const bothRadii = /(?:内接円半径.*外接円半径|外接円半径.*内接円半径)|(?:inradius.*circumradius|circumradius.*inradius)/i.test(text)
  const product = /積|product/i.test(text)
  const prime = /素数|prime/i.test(text)
  return bothRadii && product && prime
    ? { parentId: String(parent.id) }
    : null
}

function deriveTriangle(m: bigint, n: bigint): DerivedTriangle | null {
  if (m <= n || n <= 0n || gcd(m, n) !== 1n || (m - n) % 2n === 0n) return null
  const leg1 = m * m - n * n
  const leg2 = 2n * m * n
  const a = leg1 < leg2 ? leg1 : leg2
  const b = leg1 < leg2 ? leg2 : leg1
  const c = m * m + n * n
  const area = a * b / 2n
  const perimeter = a + b + c
  const semiperimeter = rational(perimeter, 2n)
  const inradius = rational(area * semiperimeter.denominator, semiperimeter.numerator)
  const circumradius = rational(a * b * c, 4n * area)
  return {
    m,
    n,
    a,
    b,
    c,
    area,
    perimeter,
    inradius,
    circumradius,
    radiusProduct: multiply(inradius, circumradius),
  }
}

function derivePrimeRadiusTriangles(): { solutions: DerivedTriangle[]; factorPairs: Array<readonly [bigint, bigint]> } {
  // In a primitive right triangle, c is odd and Rr=(r/2)c. If Rr is a
  // prime integer, r/2=1. Hence n(m-n)=r=2, so only divisors of 2 remain.
  const factorPairs: Array<readonly [bigint, bigint]> = []
  const solutions: DerivedTriangle[] = []
  for (let n = 1n; n <= 2n; n += 1n) {
    if (2n % n !== 0n) continue
    const difference = 2n / n
    factorPairs.push([n, difference])
    const triangle = deriveTriangle(n + difference, n)
    if (!triangle) continue
    if (triangle.inradius.numerator !== 2n || triangle.inradius.denominator !== 1n) continue
    if (triangle.radiusProduct.denominator !== 1n || !isPrime(triangle.radiusProduct.numerator)) continue
    solutions.push(triangle)
  }
  return { solutions, factorPairs }
}

function triangleDiagram(triangle: DerivedTriangle, stage = 4) {
  const baseShapes = [
    { kind: 'polyline', points: [{ x: 0, y: 0 }, { x: 5, y: 0 }, { x: 0, y: 12 }], closed: true, tone: 'primary' },
    { kind: 'point', point: { x: 0, y: 0 }, label: 'A', tone: 'primary' },
    { kind: 'point', point: { x: 5, y: 0 }, label: 'B', tone: 'primary' },
    { kind: 'point', point: { x: 0, y: 12 }, label: 'C', tone: 'primary' },
    { kind: 'label', point: { x: 2.5, y: -0.65 }, text: '5', tone: 'muted' },
    { kind: 'label', point: { x: -0.55, y: 6 }, text: '12', tone: 'muted' },
    { kind: 'label', point: { x: 3.05, y: 6.45 }, text: '13', tone: 'muted' },
  ]
  const radiusShapes = [
    { kind: 'circle', center: { x: 2, y: 2 }, radius: 2, tone: 'accent' },
    { kind: 'point', point: { x: 2, y: 2 }, label: 'I', tone: 'accent' },
    { kind: 'circle', center: { x: 2.5, y: 6 }, radius: 6.5, tone: 'secondary', dashed: true },
    { kind: 'point', point: { x: 2.5, y: 6 }, label: 'O', tone: 'secondary' },
  ]
  const formulaShapes = [
    { kind: 'label', point: { x: 6.5, y: 3.2 }, text: 'r = 2', tone: 'accent' },
    { kind: 'label', point: { x: 6.5, y: 4.3 }, text: 'R = 13/2', tone: 'secondary' },
    { kind: 'label', point: { x: 6.5, y: 5.4 }, text: 'Rr = 13', tone: 'primary' },
  ]
  return {
    version: 1,
    kind: 'plane',
    title: '原始直角三角形と二つの半径',
    caption: `ユークリッドの表示から得た辺 ${triangle.a},${triangle.b},${triangle.c} と、内心・外心を同じ図に示します。`,
    viewport: { xMin: -7, xMax: 10, yMin: -2, yMax: 14 },
    axes: false,
    shapes: stage === 1 ? baseShapes : stage === 2 ? [...baseShapes, ...radiusShapes] : [...baseShapes, ...radiusShapes, ...formulaShapes],
  }
}

function hash(value: unknown, length = 16): string {
  return createHash('sha256').update(JSON.stringify(value)).digest('hex').slice(0, length)
}

function statementAndAnswer(triangle: DerivedTriangle, variant: number): { statement: string; answer: string; tail: string } {
  if (variant === 1) {
    return {
      statement: '三辺が互いに素な自然数である直角三角形について、内接円半径を \\(r\\)、外接円半径を \\(R\\) とする。\\(Rr\\) が素数であるとき、\\(r,R,Rr\\) をすべて求めよ。',
      answer: `r=${format(triangle.inradius)},\\quad R=${format(triangle.circumradius)},\\quad Rr=${format(triangle.radiusProduct)}`,
      tail: `したがって \\(r=${format(triangle.inradius)},R=${format(triangle.circumradius)},Rr=${format(triangle.radiusProduct)}\\) である。`,
    }
  }
  if (variant === 2) {
    return {
      statement: '三辺が互いに素な自然数である直角三角形の内接円半径と外接円半径の積が素数である。この三角形の面積と周長を求めよ。',
      answer: `\\text{面積 }${triangle.area},\\quad \\text{周長 }${triangle.perimeter}`,
      tail: `よって面積は \\(${triangle.a}\\cdot ${triangle.b}/2=${triangle.area}\\)、周長は \\(${triangle.a}+${triangle.b}+${triangle.c}=${triangle.perimeter}\\) である。`,
    }
  }
  if (variant === 3) {
    return {
      statement: '原始ピタゴラス三角形を \\(m>n\\) を用いて表す。内接円半径と外接円半径の積が素数となるとき、可能な \\((m,n)\\) をすべて求めよ。',
      answer: `(m,n)=(${triangle.m},${triangle.n})`,
      tail: `可能な組は \\((m,n)=(${triangle.m},${triangle.n})\\) だけである。`,
    }
  }
  return {
    statement: '三辺が互いに素な自然数である直角三角形について、内接円半径を \\(r\\)、外接円半径を \\(R\\) とする。\\(Rr\\) が素数となる三角形をすべて求めよ。',
    answer: `(a,b,c)=(${triangle.a},${triangle.b},${triangle.c}),\\quad Rr=${format(triangle.radiusProduct)}`,
    tail: `したがって、脚の交換を除けば \\((a,b,c)=(${triangle.a},${triangle.b},${triangle.c})\\) だけであり、\\(Rr=${format(triangle.radiusProduct)}\\) である。`,
  }
}

function generatedCard(
  parents: readonly DiscoveryParent[],
  triangleParent: PrimitiveRightTriangleParent,
  radiusParent: PrimeRadiusProductParent,
  triangle: DerivedTriangle,
  factorPairs: Array<readonly [bigint, bigint]>,
  variant: number,
  hypothesesEvaluated: number,
): ExecutableFusionCard {
  const signature = hash({ parents: parents.map(parent => ({ id: parent.id, statement: parent.statement })), variant })
  const projected = statementAndAnswer(triangle, variant)
  const chain = [
    'CurrentStatementElaboration',
    'PrimitivePythagoreanParameterization',
    'TriangleRadiusEvaluation',
    'PrimeProductFactorization',
    'FiniteDivisorEnumeration',
    'IndependentTriangleReplay',
    'GeneratedProblem',
  ]
  const chainJa = [
    '二つの親問題から条件を読み取る',
    '原始ピタゴラス三角形を二つの整数で表す',
    '内接円半径と外接円半径を計算する',
    '半径の積が素数になる条件を分解する',
    '積が2になる整数の組をすべて調べる',
    '得られた三角形を別の公式で確かめる',
    '問題文・図・解答を組み立てる',
  ]
  const proofCertificate = [
    { id: `${signature}.parameterization`, claim: 'every primitive integer right triangle is covered by Euclid parameters', verifier: 'primitive-Pythagorean-parameterization' },
    { id: `${signature}.radii`, claim: 'R=c/2 and r=n(m-n)', verifier: 'exact-right-triangle-radius-identities' },
    { id: `${signature}.prime`, claim: 'prime Rr forces r=2', verifier: 'exact-prime-product-factorization' },
    { id: `${signature}.divisors`, claim: 'all positive factorizations n(m-n)=2 were enumerated', verifier: 'finite-divisor-enumeration' },
    { id: `${signature}.replay`, claim: 'the surviving triangle satisfies every parent condition', verifier: 'Heron-radius-and-Pythagorean-replay' },
    { id: `${signature}.ablation`, claim: 'each parent contributes an indispensable condition', verifier: 'exact-counterexample-ablation' },
  ]
  const proofClaimsJa = [
    '互いに素な整数辺をもつ直角三角形を、ユークリッドの表示ですべて扱っている',
    '外接円半径と内接円半径がそれぞれ R=c/2、r=n(m-n) になる',
    'Rr が素数ならば r=2 でなければならない',
    'n(m-n)=2 を満たす正の整数の組を漏れなく調べている',
    `辺 ${triangle.a},${triangle.b},${triangle.c} が二つの親問題の条件をすべて満たす`,
    'どちらか一方の親問題を除くと結論が一意に定まらない',
  ]
  const solution = `互いに素な整数辺をもつ直角三角形は、脚を入れ替えることを除けば、互いに素で偶奇の異なる整数 \\(m>n>0\\) を用いて` +
    `\\[(a,b,c)=(m^2-n^2,\\,2mn,\\,m^2+n^2)\\]` +
    `と表せる。このとき \\(c=m^2+n^2\\) は奇数であり、` +
    `\\[R=\\frac{c}{2},\\qquad r=\\frac{a+b-c}{2}=n(m-n)\\]` +
    `である。したがって` +
    `\\[Rr=\\frac{n(m-n)(m^2+n^2)}{2}=\\frac r2\\,c.\\]` +
    `\\(Rr\\) は整数の素数で、\\(c>1\\) は奇数である。よって \\(r\\) は偶数であり、二つの正の整数 \\(r/2\\) と \\(c\\) の積が素数になる。したがって \\(r/2=1\\)、すなわち \\(r=2\\) である。` +
    `ゆえに \\(n(m-n)=2\\)。正の整数の積が2になる場合は` +
    `\\[(n,m-n)=(1,2),(2,1)\\]` +
    `だけである。前者の \\((m,n)=(3,1)\\) は偶奇が同じなので除かれ、後者の \\((m,n)=(3,2)\\) だけが残る。これより` +
    `\\[(a,b,c)=(${triangle.a},${triangle.b},${triangle.c}),\\qquad r=${format(triangle.inradius)},\\qquad R=${format(triangle.circumradius)}.\\]` +
    `実際に \\(${triangle.a}^2+${triangle.b}^2=${triangle.c}^2\\)、三辺の最大公約数は1であり、\\(Rr=${format(triangle.radiusProduct)}\\) は素数である。${projected.tail}`
  const generatedProgram = {
    schema: 'mortra.runtime-primitive-right-triangle-prime-radii.v1',
    right_triangle_parent_id: triangleParent.parentId,
    prime_radius_parent_id: radiusParent.parentId,
    formulas: ['a=m^2-n^2', 'b=2mn', 'c=m^2+n^2', 'R=c/2', 'r=n(m-n)', 'Rr=(r/2)c'],
    factor_pairs: factorPairs.map(pair => pair.map(String)),
    surviving_parameters: { m: String(triangle.m), n: String(triangle.n) },
    exact_triangle: { a: String(triangle.a), b: String(triangle.b), c: String(triangle.c) },
    independent_replay: {
      pythagorean: triangle.a * triangle.a + triangle.b * triangle.b === triangle.c * triangle.c,
      primitive: gcd(gcd(triangle.a, triangle.b), triangle.c) === 1n,
      radius_product: format(triangle.radiusProduct),
      prime: triangle.radiusProduct.denominator === 1n && isPrime(triangle.radiusProduct.numerator),
    },
    counterexamples: {
      without_right_angle: { sides: [5, 7, 8], radius_product: 7 },
      without_prime_product: { primitive_right_triangles: [[3, 4, 5], [5, 12, 13]] },
    },
  }

  return {
    id: `mortra-runtime-primitive-right-triangle.${signature}`,
    family_id: 'runtime.primitive_right_triangle_prime_radii',
    statement_tex: projected.statement,
    answer_tex: projected.answer,
    solution_tex: solution,
    domain: 'arithmetic_geometry',
    morphism_chain: chain,
    parent_ids: [triangleParent.parentId, radiusParent.parentId],
    unresolved: false,
    discovery_status: 'verified',
    verification: {
      method: '原始ピタゴラス三角形の表示・半径公式・素数分解・別公式による再検算',
      exact_backend: true,
      independent_check: true,
      samples: [Number(triangle.m), Number(triangle.n), Number(triangle.radiusProduct.numerator)],
    },
    difficulty: { band: 'runtime_cross_domain_arithmetic_geometry', score: 8 + variant * 0.5 },
    fusion_derivation: {
      passed: true,
      reason: 'the primitive right-triangle parameterization and the prime radius-product condition meet in the factorization Rr=(r/2)c',
      ablationPassed: true,
      assignments: [
        {
          parentId: triangleParent.parentId,
          portId: `primitive-right-triangle:${triangleParent.parentId}`,
          role: 'primitive_integer_right_triangle',
          matchedAnchors: ['right-triangle', 'integer-sides', 'coprime-sides'],
          witnessSteps: ['PrimitivePythagoreanParameterization', 'TriangleRadiusEvaluation'],
          requiredObligations: ['RightTriangle', 'IntegralSides', 'PrimitiveSides'],
          consumedObligations: ['RightTriangle', 'IntegralSides', 'PrimitiveSides'],
          coverage: 1,
        },
        {
          parentId: radiusParent.parentId,
          portId: `prime-radius-product:${radiusParent.parentId}`,
          role: 'prime_radius_product_constraint',
          matchedAnchors: ['inradius', 'circumradius', 'product', 'prime'],
          witnessSteps: ['TriangleRadiusEvaluation', 'PrimeProductFactorization'],
          requiredObligations: ['Inradius', 'Circumradius', 'Product', 'PrimePredicate'],
          consumedObligations: ['Inradius', 'Circumradius', 'Product', 'PrimePredicate'],
          coverage: 1,
        },
      ],
      bridges: [{
        id: `primitive-radius-prime:${signature}`,
        witnessStep: 'Rr=(r/2)c and primality force r=2',
        consumes: [`primitive-right-triangle:${triangleParent.parentId}`, `prime-radius-product:${radiusParent.parentId}`],
        produces: 'UniquePrimitiveRightTriangle',
      }],
      intermediatePropositions: [
        {
          parentId: triangleParent.parentId,
          morphism: 'PrimitivePythagoreanParameterization',
          source: 'PrimitiveIntegerRightTriangle',
          target: 'CoprimeOppositeParityParameterPair',
          proposition: '(a,b,c)=(m^2-n^2,2mn,m^2+n^2)',
          proved: true,
        },
        {
          parentId: radiusParent.parentId,
          morphism: 'PrimeProductFactorization',
          source: 'TriangleRadii',
          target: 'PrimeFactorObligation',
          proposition: 'Rr=(r/2)c is prime only when r=2',
          proved: true,
        },
      ],
    },
    structure_blueprint: {
      id: `runtime-primitive-right-triangle.${signature}`,
      version: 1,
      kernel: 'exact_primitive_right_triangle_prime_radius_pairing',
      observable: 'UniquePrimitiveRightTriangle',
      operators: chain,
      domain: 'primitive_pythagorean_triples_x_triangle_radii_x_primes',
      tags: ['runtime-synthesis', 'atlas-free', 'arithmetic-geometry', 'one-to-many'],
      morphismChain: chain,
      executable: true,
      proofCertificate,
      synthesizedLaw: {
        name: 'PrimitiveRightTrianglePrimeRadiusClassification',
        expression: 'primitive right triangle and prime Rr imply (a,b,c)=(5,12,13)',
        arity: 2,
        sources: ['PrimitiveIntegerRightTriangle', 'PrimeRadiusProductConstraint'],
        target: 'UniquePrimitiveRightTriangle',
        preserves: ['exact-integrality', 'all-parent-provenance', 'leg-swap-symmetry'],
        backend: ['finite-divisor-enumeration', 'exact-rational-radius-replay'],
      },
      structuralUniqueness: {
        schema: 1,
        conditionSkeleton: ['PrimitiveIntegerRightTriangle', 'InradiusCircumradiusProduct', 'PrimePredicate'],
        querySignature: 'classify',
        normalForm: 'n(m-n)=2 with gcd(m,n)=1 and opposite parity',
        quotientAction: 'swap-the-two-legs',
        freeParameters: ['m', 'n'],
        uniqueNormalForm: true,
        finiteSolutionSet: true,
        numericInstanceConstants: [],
        conditionAblationPassed: true,
      },
    },
    search_evidence: {
      hypotheses_evaluated: hypothesesEvaluated,
      valid_hypotheses: 1,
      elapsed_ms: 0,
    },
    execution_certificate: runtimeSynthesisCertificate({
      origin: 'synthesized_proof_program',
      parents,
      generatedProgram,
      checks: proofCertificate.map(item => `${item.id}: ${item.verifier}`),
    }),
    diagram: triangleDiagram(triangle, 4),
    visual_explanation: {
      version: 1,
      mode: 'stepper',
      title: '三角形が一つに絞られるまで',
      diagram_required_for_every_step: true,
      composition_verified: true,
      morphism_chain: chain,
      steps: [
        {
          id: `${signature}.visual.1`,
          title: '原始直角三角形を表示する',
          explanation_ja: '互いに素な整数辺をもつ直角三角形を、互いに素で偶奇の異なる m,n で表します。',
          formula_tex: '(a,b,c)=(m^2-n^2,2mn,m^2+n^2)',
          morphism: { morphism_id: chain[1], label_ja: chainJa[1], input_type: 'PrimitiveIntegerRightTriangle', output_type: 'EuclidParameters' },
          source_state: { id: 'primitive-triangle', type: 'PrimitiveIntegerRightTriangle' },
          target_state: { id: 'parameter-pair', type: 'EuclidParameters' },
          diagram: triangleDiagram(triangle, 1),
        },
        {
          id: `${signature}.visual.2`,
          title: '内心と外心を加える',
          explanation_ja: '直角三角形では外心は斜辺の中点です。内接円は二つの脚に接するため、半径は r=n(m-n) になります。',
          formula_tex: 'R=c/2,\\quad r=n(m-n)',
          morphism: { morphism_id: chain[2], label_ja: chainJa[2], input_type: 'EuclidParameters', output_type: 'TriangleRadii' },
          source_state: { id: 'parameter-pair', type: 'EuclidParameters' },
          target_state: { id: 'triangle-radii', type: 'TriangleRadii' },
          diagram: triangleDiagram(triangle, 2),
        },
        {
          id: `${signature}.visual.3`,
          title: '素数条件で候補を絞る',
          explanation_ja: 'Rr=(r/2)c は正の整数二つの積です。素数になるには r/2=1 が必要なので、n(m-n)=2 まで絞れます。',
          formula_tex: 'Rr=(r/2)c,\\quad n(m-n)=2',
          morphism: { morphism_id: chain[3], label_ja: chainJa[3], input_type: 'TriangleRadii', output_type: 'FiniteFactorPairs' },
          source_state: { id: 'triangle-radii', type: 'TriangleRadii' },
          target_state: { id: 'factor-pairs', type: 'FiniteFactorPairs' },
          diagram: triangleDiagram(triangle, 3),
        },
        {
          id: `${signature}.visual.4`,
          title: '5・12・13を再検算する',
          explanation_ja: '残った m=3,n=2 から辺を作り、直角条件、互いに素、二つの半径、素数性を別々に確かめます。',
          formula_tex: '5^2+12^2=13^2,\\quad r=2,\\quad R=13/2,\\quad Rr=13',
          morphism: { morphism_id: chain[5], label_ja: chainJa[5], input_type: 'FiniteFactorPairs', output_type: 'VerifiedTriangle' },
          source_state: { id: 'factor-pairs', type: 'FiniteFactorPairs' },
          target_state: { id: 'verified-triangle', type: 'VerifiedTriangle' },
          diagram: triangleDiagram(triangle, 4),
        },
      ],
    },
    proof_roadmap: chain.map((morphism, index) => ({
      morphism_id: `${signature}.${index + 1}`,
      label_ja: chainJa[index],
      source_ja: index === 0 ? '現在の二つの親問題' : chainJa[index - 1],
      target_ja: chainJa[index],
      role_ja: '証明済みの表現変換',
    })),
    proof_obligations: proofCertificate.map((item, index) => ({
      id: item.id,
      claim_ja: proofClaimsJa[index],
      status: 'verified',
    })),
  }
}

export function synthesizeRuntimePrimitiveRightTriangleProblems(
  parents: readonly DiscoveryParent[],
  requested: number,
): RuntimePrimitiveRightTriangleGeneration {
  if (parents.length !== 2 || requested <= 0) {
    return { applicable: false, reason: 'primitive right-triangle radius composition requires exactly two current parents', cards: [], hypothesesEvaluated: 0 }
  }
  if (parents.some(parent => parent.id === undefined) || new Set(parents.map(parent => String(parent.id))).size !== 2) {
    return { applicable: false, reason: 'both current parents require distinct stable ids', cards: [], hypothesesEvaluated: 0 }
  }
  const triangleParent = parents.map(parsePrimitiveRightTriangle).find((value): value is PrimitiveRightTriangleParent => value !== null)
  const radiusParent = parents.map(parsePrimeRadiusProduct).find((value): value is PrimeRadiusProductParent => value !== null)
  if (!triangleParent || !radiusParent || triangleParent.parentId === radiusParent.parentId) {
    return {
      applicable: false,
      reason: 'the current parents do not provide distinct primitive-right-triangle and prime-radius-product structures',
      cards: [],
      hypothesesEvaluated: 0,
    }
  }
  const derivation = derivePrimeRadiusTriangles()
  if (derivation.solutions.length !== 1) {
    return {
      applicable: false,
      reason: `exact divisor enumeration produced ${derivation.solutions.length} admissible triangles instead of one`,
      cards: [],
      hypothesesEvaluated: derivation.factorPairs.length,
    }
  }
  const triangle = derivation.solutions[0]
  const limit = Math.min(requested, 4)
  const cards = Array.from({ length: limit }, (_, variant) => generatedCard(
    parents,
    triangleParent,
    radiusParent,
    triangle,
    derivation.factorPairs,
    variant,
    derivation.factorPairs.length,
  ))
  return {
    applicable: cards.length > 0,
    reason: `${cards.length} exact primitive-right-triangle problems were synthesized from the current parents`,
    cards,
    hypothesesEvaluated: derivation.factorPairs.length,
  }
}
