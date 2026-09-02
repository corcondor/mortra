export type TriangleVertices = [string, string, string]

export type EuclideanTypedRelation =
  | { kind: 'triangle'; vertices: TriangleVertices }
  | { kind: 'orthocenter'; point: string; triangle: TriangleVertices }
  | { kind: 'perpendicular'; first: [string, string]; second: [string, string]; origin: 'orthocenter_definition' }
  | { kind: 'line_reflection'; source: string; axis: [string, string]; result: string; oppositeVertex: string }
  | { kind: 'on_circumcircle'; point: string; triangle: TriangleVertices; role: 'goal' }

type LineReflectionRelation = Extract<EuclideanTypedRelation, { kind: 'line_reflection' }>

export interface EuclideanStatementElaboration {
  semanticRoots: string[]
  constraints: string[]
  relations: EuclideanTypedRelation[]
  queryTarget?: 'each_reflection_on_triangle_circumcircle'
}

const POINT_SOURCE = "[A-Z](?:[_']?[A-Za-z0-9]+)?"

function normalizeStatement(statement: string): string {
  return statement
    .replace(/\\text\s*\{([^{}]*)\}/g, '$1')
    .replace(/\\triangle|△/g, '三角形')
    .replace(/[（]/g, '(')
    .replace(/[）]/g, ')')
    .replace(/[，]/g, ',')
    .replace(/[；]/g, ';')
    .replace(/[：]/g, ':')
    .replace(/[−]/g, '-')
    .replace(/\s+/g, ' ')
    .trim()
}

function extractTriangle(text: string): TriangleVertices | null {
  const patterns = [
    /(?:(?:鋭角|鈍角|直角)\s*)?三角形\s*([A-Z])\s*([A-Z])\s*([A-Z])/i,
    /(?:acute\s+|obtuse\s+|right\s+)?triangle\s+([A-Z])\s*([A-Z])\s*([A-Z])/i,
  ]
  for (const pattern of patterns) {
    const match = text.match(pattern)
    if (!match) continue
    const vertices = match.slice(1, 4).map(value => value.toUpperCase()) as TriangleVertices
    if (new Set(vertices).size === 3) return vertices
  }
  return null
}

function extractOrthocenter(text: string, vertices: TriangleVertices): string | null {
  const triangle = vertices.join('\\s*')
  const patterns = [
    new RegExp(`(?:三角形\\s*${triangle}\\s*の\\s*)?垂心\\s*を\\s*(${POINT_SOURCE})\\s*と(?:する|し|おく|置く)`, 'i'),
    new RegExp(`(${POINT_SOURCE})\\s*を\\s*(?:三角形\\s*${triangle}\\s*の\\s*)?垂心\\s*と(?:する|し|おく|置く)`, 'i'),
    new RegExp(`(${POINT_SOURCE})\\s+is\\s+(?:the\\s+)?orthocenter\\s+of\\s+(?:triangle\\s+)?${triangle}`, 'i'),
    new RegExp(`(?:the\\s+)?orthocenter\\s+of\\s+(?:triangle\\s+)?${triangle}\\s+is\\s+(${POINT_SOURCE})`, 'i'),
  ]
  for (const pattern of patterns) {
    const match = text.match(pattern)
    if (match) return match[1].toUpperCase()
  }
  return null
}

function triangleSides(vertices: TriangleVertices): Array<[string, string]> {
  const [a, b, c] = vertices
  return [[b, c], [c, a], [a, b]]
}

function axisKey(axis: [string, string]): string {
  return [...axis].map(value => value.toUpperCase()).sort().join(':')
}

function oppositeVertex(vertices: TriangleVertices, axis: [string, string]): string | null {
  const axisPoints = new Set(axis.map(value => value.toUpperCase()))
  const remaining = vertices.filter(vertex => !axisPoints.has(vertex))
  return remaining.length === 1 ? remaining[0] : null
}

function extractNamedReflections(
  text: string,
  vertices: TriangleVertices,
  source: string,
): LineReflectionRelation[] {
  const patterns = [
    new RegExp(`(?:直線|線分|辺)?\\s*([A-Z])\\s*([A-Z])\\s*に関(?:する|して)\\s*(?:点\\s*)?${source}\\s*(?:の|と)\\s*対称(?:な)?(?:点|な点)?\\s*を\\s*(${POINT_SOURCE})`, 'gi'),
    new RegExp(`(?:点\\s*)?${source}\\s*を\\s*(?:直線|線分|辺)?\\s*([A-Z])\\s*([A-Z])\\s*に関(?:して|する)\\s*対称(?:移動)?(?:した|させた)?(?:点)?\\s*を\\s*(${POINT_SOURCE})`, 'gi'),
    new RegExp(`(${POINT_SOURCE})\\s+is\\s+the\\s+reflection\\s+of\\s+${source}\\s+(?:across|in|about)\\s+(?:side|line)?\\s*([A-Z])\\s*([A-Z])`, 'gi'),
  ]
  const sideKeys = new Set(triangleSides(vertices).map(axisKey))
  const relations: LineReflectionRelation[] = []
  patterns.forEach((pattern, patternIndex) => {
    for (const match of text.matchAll(pattern)) {
      const groups = match.slice(1).map(value => value.toUpperCase())
      const [left, right, result] = patternIndex === 2
        ? [groups[1], groups[2], groups[0]]
        : [groups[0], groups[1], groups[2]]
      const axis: [string, string] = [left, right]
      const opposite = oppositeVertex(vertices, axis)
      if (!opposite || !sideKeys.has(axisKey(axis))) continue
      relations.push({ kind: 'line_reflection', source, axis, result, oppositeVertex: opposite })
    }
  })
  return relations
}

function extractPluralReflections(
  text: string,
  vertices: TriangleVertices,
  source: string,
): LineReflectionRelation[] {
  const sides = triangleSides(vertices)
  const sideByKey = new Map(sides.map(side => [axisKey(side), side]))
  let axes: Array<[string, string]> = []
  const allSidesPattern = new RegExp(
    `${source}\\s*を\\s*(?:三角形\\s*[A-Z]\\s*[A-Z]\\s*[A-Z]\\s*の\\s*)?(?:三つの|3つの|各)辺\\s*に関(?:して|する).{0,24}?(?:対称|折り返)`,
    'i',
  )
  if (allSidesPattern.test(text)) {
    axes = sides
  } else {
    const listedAxesPattern = new RegExp(
      `${source}\\s*を\\s*([^。.!?]{1,90}?)\\s*に関(?:して|する)\\s*(?:それぞれ\\s*)?(?:対称(?:移動)?|折り返)`,
      'i',
    )
    const listed = text.match(listedAxesPattern)?.[1]
    if (!listed) return []
    for (const match of listed.matchAll(/(?:直線|線分|辺)?\s*([A-Z])\s*([A-Z])/gi)) {
      const key = axisKey([match[1], match[2]])
      const side = sideByKey.get(key)
      if (side && !axes.some(axis => axisKey(axis) === key)) axes.push(side)
    }
  }
  return axes.flatMap(axis => {
    const opposite = oppositeVertex(vertices, axis)
    return opposite
      ? [{
          kind: 'line_reflection' as const,
          source,
          axis,
          result: `${source}_${opposite}`,
          oppositeVertex: opposite,
        }]
      : []
  })
}

function uniqueRelations(relations: EuclideanTypedRelation[]): EuclideanTypedRelation[] {
  const seen = new Set<string>()
  return relations.filter(relation => {
    const key = JSON.stringify(relation)
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

export function elaborateEuclideanStatement(statement: string): EuclideanStatementElaboration | null {
  const text = normalizeStatement(statement)
  const vertices = extractTriangle(text)
  if (!vertices) return null

  const relations: EuclideanTypedRelation[] = [{ kind: 'triangle', vertices }]
  const roots = ['Triangle', 'PointConfiguration']
  const constraints: string[] = []
  const orthocenter = extractOrthocenter(text, vertices)
  if (!orthocenter) return { semanticRoots: roots, constraints, relations }

  roots.unshift('OrthocenterConfiguration')
  constraints.push('perpendicular_incidence')
  relations.push({ kind: 'orthocenter', point: orthocenter, triangle: vertices })
  for (const [opposite, axis] of vertices.map((vertex, index) => [vertex, triangleSides(vertices)[index]] as const)) {
    relations.push({
      kind: 'perpendicular',
      first: [opposite, orthocenter],
      second: axis,
      origin: 'orthocenter_definition',
    })
  }

  const reflectionByAxis = new Map<string, LineReflectionRelation>()
  const reflectionRelations = [
    ...extractPluralReflections(text, vertices, orthocenter),
    ...extractNamedReflections(text, vertices, orthocenter),
  ]
  for (const relation of reflectionRelations) reflectionByAxis.set(axisKey(relation.axis), relation)
  const orderedReflections = triangleSides(vertices).flatMap(side => {
    const relation = reflectionByAxis.get(axisKey(side))
    return relation ? [relation] : []
  })
  if (orderedReflections.length) {
    roots.unshift('LineReflectionConfiguration')
    constraints.push('line_reflection')
    relations.push(...orderedReflections)
  }

  const asksForCircumcircleProof = /(?:外接円|circumcircle)/i.test(text)
    && /(?:証明|示せ|prove|show)/i.test(text)
  if (!asksForCircumcircleProof || !orderedReflections.length) {
    return { semanticRoots: [...new Set(roots)], constraints, relations: uniqueRelations(relations) }
  }

  roots.unshift('CircumcircleIncidence')
  constraints.push('circle_incidence')
  for (const reflection of orderedReflections) {
    relations.push({
      kind: 'on_circumcircle',
      point: reflection.result,
      triangle: vertices,
      role: 'goal',
    })
  }
  return {
    semanticRoots: [...new Set(roots)],
    constraints: [...new Set(constraints)],
    relations: uniqueRelations(relations),
    queryTarget: 'each_reflection_on_triangle_circumcircle',
  }
}
