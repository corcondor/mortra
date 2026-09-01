import { existsSync } from 'node:fs'
import { delimiter, resolve } from 'node:path'

type RepositoryRootOptions = {
  cwd?: string
  moduleDir?: string
}

export function locateRepositoryRoot(
  requiredRelativePath: string,
  options: RepositoryRootOptions = {},
): string {
  const cwd = options.cwd ?? process.cwd()
  const moduleDir = options.moduleDir ?? __dirname
  const candidates = [
    cwd,
    resolve(cwd, '..'),
    resolve(moduleDir, '..', '..'),
    resolve(moduleDir, '..', '..', '..'),
  ]
  const checked = new Set<string>()
  for (const candidate of candidates) {
    const root = resolve(candidate)
    if (checked.has(root)) continue
    checked.add(root)
    if (existsSync(resolve(root, requiredRelativePath))) return root
  }
  throw new Error(
    `MORTRA repository root not found for ${requiredRelativePath}; checked ${[...checked].join(', ')}`,
  )
}

export function pythonBackendEnvironment(root: string): NodeJS.ProcessEnv {
  const pythonPath = [root, process.env.PYTHONPATH]
    .filter((value): value is string => Boolean(value))
    .join(delimiter)
  return {
    ...process.env,
    PYTHONPATH: pythonPath,
    PYTHONUTF8: '1',
    PYTHONIOENCODING: 'utf-8',
  }
}
