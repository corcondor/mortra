import { spawnSync } from 'node:child_process'
import { resolve } from 'node:path'

export type AlphaGeometry2Result = {
  status: 'proved' | 'unproved' | 'unformalized' | 'unavailable' | 'error'
  proved: boolean
  goal?: string
  point_count?: number
  premise_count?: number
  closure_rounds?: number
  backend?: string
  error?: string
  baseline_proved?: boolean
  attempts?: number
  depth?: number
  constructions?: Array<{
    name: string
    kind: string
    value: number[]
    predicates: string[]
    numeric_validation: string
  }>
  goal_gap?: number
  derived_size?: number
  proposal_engine?: string
  construction_grammar?: string[]
  uses_language_model?: boolean
  input_mode?: 'natural_or_tex'
  formalization?: {
    status: string
    normalized_text: string
    points: string[]
    unresolved_relations: string[]
    diagram_residual: number | null
    restarts: number
    formal_problem: string | null
    discourse_objects?: Array<{
      name: string
      center: string | null
      through: string[]
      source: string
    }>
  }
  diagram_grounding?: {
    status: 'grounded' | 'partial' | 'unresolved'
    labels?: Array<{
      label: string
      label_position: number[]
      point_position: number[] | null
      confidence: number
      distance: number | null
    }>
    unresolved_labels: string[]
    uses_language_model: false
  } | null
  analysis?: {
    S1: string[]
    S2: string[]
    S3: string[]
    preferred_points: string[]
    analysis_text: string
    soundness_boundary: string
  }
  trees?: Array<{
    name: string
    proved: boolean
    attempts: number
    depth: number
    goal_gap?: number
    shared_fact_count?: number
  }>
  shared_workspace?: {
    facts: string[]
    fact_count: number
    policy: string
  }
  attempt_trace?: Array<{
    attempt: number
    depth: number
    kind: string
    source_points: string[]
    status: 'rejected' | 'retained_for_ranking' | 'proved'
    reason?: string
    goal_gap_before?: number
    goal_gap_after?: number
    derived_size_before?: number
    derived_size_after?: number
    closure_rounds?: number
    shared_facts_added?: string[]
  }>
}

export type AlphaGeometry2Options = {
  searchAuxiliary?: boolean
  maxDepth?: number
  beamWidth?: number
  maxAttempts?: number
  inputFormat?: 'auto' | 'formal' | 'natural'
  ensemble?: boolean
  maxRestarts?: number
  diagram?: string
}

function pythonCommands(): string[] {
  return process.platform === 'win32' ? ['python', 'py'] : ['python3', 'python']
}

export function executeAlphaGeometry2(formalProblem: string, options: AlphaGeometry2Options = {}): AlphaGeometry2Result {
  const engineDirectory = process.env.MATHOS_AG2_DIR
  if (!engineDirectory) {
    return { status: 'unavailable', proved: false, error: 'MATHOS_AG2_DIR is not configured' }
  }
  const adapter = resolve(__dirname, '..', 'backend', 'alphageometry2_adapter.py')
  for (const command of pythonCommands()) {
    const args = [adapter, '--engine-dir', engineDirectory]
    args.push('--input-format', options.inputFormat ?? 'auto')
    if (options.searchAuxiliary ?? true) {
      args.push(
        '--auto-aux',
        '--max-depth', String(options.maxDepth ?? 2),
        '--beam-width', String(options.beamWidth ?? 8),
        '--max-attempts', String(options.maxAttempts ?? 96),
      )
      if (options.ensemble ?? true) args.push('--ensemble')
    }
    args.push('--max-restarts', String(options.maxRestarts ?? 20))
    const result = spawnSync(command, args, {
      input: JSON.stringify({ problem: formalProblem, diagram: options.diagram }),
      encoding: 'utf8',
      env: {
        ...process.env,
        PYTHONUTF8: '1',
        PYTHONIOENCODING: 'utf-8',
      },
      timeout: 120_000,
      maxBuffer: 4 * 1024 * 1024,
    })
    if (result.error && (result.error as NodeJS.ErrnoException).code === 'ENOENT') continue
    if (result.status !== 0) {
      const detail = result.stderr || result.stdout || result.error?.message || `DDAR exited with status ${result.status}`
      return { status: 'error', proved: false, error: detail.trim() }
    }
    try {
      return JSON.parse(result.stdout) as AlphaGeometry2Result
    } catch (error) {
      return { status: 'error', proved: false, error: `invalid DDAR output: ${String(error)}` }
    }
  }
  return { status: 'unavailable', proved: false, error: 'Python runtime was not found' }
}
