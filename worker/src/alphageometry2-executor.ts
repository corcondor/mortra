import { spawnSync } from 'node:child_process'
import { resolve } from 'node:path'

export type AlphaGeometry2Result = {
  status: 'proved' | 'unproved' | 'unavailable' | 'error'
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
  }>
}

export type AlphaGeometry2Options = {
  searchAuxiliary?: boolean
  maxDepth?: number
  beamWidth?: number
  maxAttempts?: number
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
    if (options.searchAuxiliary ?? true) {
      args.push(
        '--auto-aux',
        '--max-depth', String(options.maxDepth ?? 2),
        '--beam-width', String(options.beamWidth ?? 8),
        '--max-attempts', String(options.maxAttempts ?? 96),
      )
    }
    const result = spawnSync(command, args, {
      input: JSON.stringify({ problem: formalProblem }),
      encoding: 'utf8',
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
