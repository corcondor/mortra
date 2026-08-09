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
}

function pythonCommands(): string[] {
  return process.platform === 'win32' ? ['python', 'py'] : ['python3', 'python']
}

export function executeAlphaGeometry2(formalProblem: string): AlphaGeometry2Result {
  const engineDirectory = process.env.MATHOS_AG2_DIR
  if (!engineDirectory) {
    return { status: 'unavailable', proved: false, error: 'MATHOS_AG2_DIR is not configured' }
  }
  const adapter = resolve(__dirname, '..', 'backend', 'alphageometry2_adapter.py')
  for (const command of pythonCommands()) {
    const result = spawnSync(command, [adapter, '--engine-dir', engineDirectory], {
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
