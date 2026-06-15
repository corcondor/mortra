export type SceneObject = {
  id: string
  type: string
  size?: number
  side?: number
  area?: number
  position?: number[]
}

export type SceneRelation = {
  type: string
  subject: string
  object: string
  range?: number[]
  samples?: number
}

export type VisualSceneGraph = {
  objects: SceneObject[]
  relations: SceneRelation[]
}

export type VisualVerifierMetrics = {
  area: number
  side: number
  samplesInSquare: number
  totalSamples: number
  currentInside: number
  enoughSweep: boolean
  centerInside: boolean
}

export type VisualCompilerInput = {
  prompt: string
  sceneGraph: VisualSceneGraph
  metrics: VisualVerifierMetrics
  sweepRange: [number, number]
}

export type ToolAction = {
  id: string
  tool: string
  purpose: string
  arguments: Record<string, string | number | boolean | string[] | number[]>
  status: 'ready' | 'needs_verification' | 'blocked'
}

export type VisualCompileResult = {
  problem_type: string[]
  extracted: {
    fixed_objects: string[]
    moving_objects: string[]
    parameters: string[]
    target: string
  }
  subproblems: string[]
  next_action: string
  tool_pipeline: ToolAction[]
  verification_plan: string[]
  risk_flags: string[]
  compiled_json: {
    problem_type: string[]
    next_action: string
    tool: string
    arguments: Record<string, string | number | boolean | string[] | number[]>
  }
}

function hasAny(text: string, words: string[]) {
  return words.some((word) => text.includes(word))
}

function objectIds(sceneGraph: VisualSceneGraph, type: string) {
  return sceneGraph.objects.filter((obj) => obj.type.includes(type)).map((obj) => obj.id)
}

function relationSubjects(sceneGraph: VisualSceneGraph, type: string) {
  return sceneGraph.relations.filter((rel) => rel.type === type).map((rel) => rel.subject)
}

export function compileVisualProblem(input: VisualCompilerInput): VisualCompileResult {
  const text = input.prompt.toLowerCase()
  const sweepDegrees = Math.abs(input.sweepRange[1] - input.sweepRange[0])
  const hasSweep = hasAny(input.prompt, ['通過', '軌跡', '掃引', '動く']) || hasAny(text, ['sweep', 'trace', 'passage'])
  const hasArea = hasAny(input.prompt, ['面積', '領域']) || hasAny(text, ['area', 'region'])
  const hasTriangle = input.sceneGraph.objects.some((obj) => obj.type.includes('triangle'))
  const hasSquare = input.sceneGraph.objects.some((obj) => obj.type.includes('square'))
  const hasRotation = input.sceneGraph.relations.some((rel) => rel.type === 'rotates_about')

  const problemType = [
    'geometry',
    hasSweep ? 'swept_region' : 'static_configuration',
    hasRotation ? 'rotation_parameterized_motion' : 'continuous_motion',
    hasArea ? 'area_measurement' : 'construction',
  ]

  const fixedObjects = [
    ...objectIds(input.sceneGraph, 'square'),
    ...objectIds(input.sceneGraph, 'rotation_center'),
  ]
  const movingObjects = hasRotation
    ? relationSubjects(input.sceneGraph, 'rotates_about')
    : objectIds(input.sceneGraph, 'triangle')

  const riskFlags = [
    sweepDegrees < 60 ? 'sweep_range_too_small_for_boundary_inference' : '',
    input.metrics.samplesInSquare === 0 ? 'swept_region_does_not_intersect_reference_square' : '',
    input.metrics.samplesInSquare < input.metrics.totalSamples ? 'boundary_switching_possible' : '',
    hasSweep ? 'must_distinguish_union_region_from_single_configuration' : '',
    hasTriangle && hasSquare ? 'contact_modes_vertex_edge_and_edge_vertex_must_be_checked' : '',
  ].filter(Boolean)

  const toolPipeline: ToolAction[] = [
    {
      id: 'classify',
      tool: 'visual_problem_classifier',
      purpose: '自然言語とScene Graphから問題型を決める',
      arguments: { labels: problemType, has_triangle: hasTriangle, has_square: hasSquare },
      status: 'ready',
    },
    {
      id: 'parameterize',
      tool: 'configuration_parameterizer',
      purpose: '回転角と固定点を変数化し、配置空間を作る',
      arguments: {
        moving_object: movingObjects[0] ?? 'unknown',
        pivot: objectIds(input.sceneGraph, 'rotation_center')[0] ?? 'P',
        sweep_start_deg: input.sweepRange[0],
        sweep_end_deg: input.sweepRange[1],
      },
      status: hasRotation ? 'ready' : 'blocked',
    },
    {
      id: 'sample_boundary',
      tool: 'geometry_sampler',
      purpose: '数値探索で通過領域の境界候補を推定する',
      arguments: {
        samples: Math.max(10000, input.metrics.totalSamples * 40),
        output: 'boundary_points, hull, contact_candidates',
      },
      status: 'ready',
    },
    {
      id: 'detect_modes',
      tool: 'boundary_event_classifier',
      purpose: '境界を決める接触・包絡線・切替点を分類する',
      arguments: {
        check_modes: ['vertex_edge', 'edge_vertex', 'envelope_arc', 'intersection_switch'],
        risk_flags: riskFlags,
      },
      status: riskFlags.length > 0 ? 'needs_verification' : 'ready',
    },
    {
      id: 'symbolic_pass',
      tool: 'sympy_resultant_or_cad',
      purpose: '境界候補を式に落とし、量化変数を消去する',
      arguments: {
        variables: ['theta', 'x', 'y'],
        constraints: ['point_in_rotated_triangle', 'theta_range', 'reference_square'],
      },
      status: 'needs_verification',
    },
    {
      id: 'verify_area',
      tool: 'geometry_verifier',
      purpose: '数値面積・境界分割・サンプル包含を相互検算する',
      arguments: {
        current_area_px2: Math.round(input.metrics.area),
        samples_inside_reference: input.metrics.samplesInSquare,
        total_samples: input.metrics.totalSamples,
      },
      status: input.metrics.enoughSweep && input.metrics.centerInside ? 'ready' : 'needs_verification',
    },
    {
      id: 'write_problem',
      tool: 'solution_writer',
      purpose: '検証済み操作列から作問文・解答文・TikZを生成する',
      arguments: {
        outputs: ['problem_statement', 'solution_outline', 'tikz_diagram'],
        language: 'ja',
      },
      status: 'needs_verification',
    },
  ]

  const nextAction = toolPipeline.find((action) => action.status !== 'ready')?.id ?? 'write_problem'
  const nextTool = toolPipeline.find((action) => action.id === nextAction) ?? toolPipeline[0]

  return {
    problem_type: problemType,
    extracted: {
      fixed_objects: fixedObjects,
      moving_objects: movingObjects,
      parameters: ['theta', 'P', 'side(ABC)', 'square(S)'],
      target: hasArea ? '通過領域の面積' : '通過領域の境界構成',
    },
    subproblems: [
      '配置を角度 theta で変数化する',
      '各頂点の軌跡と三角形内部の和集合を分離する',
      '境界を作る接触モードと包絡線を列挙する',
      '数値サンプルから境界候補を推定する',
      '候補境界を記号条件へ戻して検証する',
      '面積を境界ごとに分割して計算する',
    ],
    next_action: nextAction,
    tool_pipeline: toolPipeline,
    verification_plan: [
      '単一配置の三角形と通過領域の和集合を混同していないか確認する',
      '頂点-辺、辺-頂点、包絡線、切替点の全モードを列挙する',
      '数値面積と記号積分結果を比較する',
      '境界点を再サンプリングし、漏れた孤立領域がないか確認する',
      '最終図をTikZ化し、PDF上で視覚検算する',
    ],
    risk_flags: riskFlags,
    compiled_json: {
      problem_type: problemType,
      next_action: nextAction,
      tool: nextTool.tool,
      arguments: nextTool.arguments,
    },
  }
}
