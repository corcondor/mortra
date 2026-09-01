import { existsSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..')
const entrypoints = [
  resolve(repositoryRoot, 'api', 'solve.py'),
  resolve(repositoryRoot, 'worker', 'backend', 'exact_expression_ir.py'),
  resolve(repositoryRoot, 'worker', 'backend', 'exact_problem_solver_bridge.py'),
]
const visited = new Set()
const missing = new Set()
const untracked = new Set()

function localModulePath(moduleName, sourceFile) {
  if (
    moduleName.startsWith('math_os_prototype.')
    || moduleName.startsWith('worker.')
    || moduleName.startsWith('api.')
  ) {
    return resolve(repositoryRoot, ...moduleName.split('.'))
  }
  if (!moduleName.startsWith('.')) return null
  const dots = moduleName.match(/^\.+/)?.[0].length ?? 0
  const suffix = moduleName.slice(dots)
  let base = dirname(sourceFile)
  for (let level = 1; level < dots; level += 1) base = dirname(base)
  return suffix ? resolve(base, ...suffix.split('.')) : base
}

function sourcePath(moduleBase) {
  const file = `${moduleBase}.py`
  if (existsSync(file)) return file
  const packageFile = resolve(moduleBase, '__init__.py')
  return existsSync(packageFile) ? packageFile : null
}

function inspect(file) {
  const normalized = resolve(file)
  if (visited.has(normalized)) return
  visited.add(normalized)
  const source = readFileSync(normalized, 'utf8')
  const imports = [
    ...source.matchAll(/^\s*from\s+([.A-Za-z_][.A-Za-z0-9_]*)\s+import\s+/gm),
    ...source.matchAll(/^\s*import\s+((?:math_os_prototype|worker|api)(?:\.[A-Za-z_][A-Za-z0-9_]*)+)/gm),
  ]
  for (const match of imports) {
    const moduleName = match[1]
    const moduleBase = localModulePath(moduleName, normalized)
    if (!moduleBase) continue
    const dependency = sourcePath(moduleBase)
    if (!dependency) {
      missing.add(`${moduleName} imported by ${normalized.slice(repositoryRoot.length + 1)}`)
      continue
    }
    inspect(dependency)
  }
}

for (const entrypoint of entrypoints) {
  if (!existsSync(entrypoint)) {
    missing.add(`required Python entrypoint ${entrypoint.slice(repositoryRoot.length + 1)}`)
    continue
  }
  inspect(entrypoint)
}
if (missing.size > 0) {
  throw new Error(`Public Python dependency closure is incomplete:\n${[...missing].sort().join('\n')}`)
}

if (existsSync(resolve(repositoryRoot, '.git'))) {
  for (const file of visited) {
    const relative = file.slice(repositoryRoot.length + 1).replaceAll('\\', '/')
    const result = spawnSync('git', ['ls-files', '--error-unmatch', '--', relative], {
      cwd: repositoryRoot,
      encoding: 'utf8',
      windowsHide: true,
    })
    if (result.status !== 0) untracked.add(relative)
  }
}
if (untracked.size > 0) {
  throw new Error(`Python runtime closure contains untracked files:\n${[...untracked].sort().join('\n')}`)
}

console.log(`Public and worker Python dependency closure verified: ${visited.size} local modules`)
