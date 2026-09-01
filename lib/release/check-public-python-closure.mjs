import { existsSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..')
const entrypoint = resolve(repositoryRoot, 'api', 'solve.py')
const visited = new Set()
const missing = new Set()

function localModulePath(moduleName, sourceFile) {
  if (moduleName.startsWith('math_os_prototype.')) {
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
    ...source.matchAll(/^\s*import\s+(math_os_prototype(?:\.[A-Za-z_][A-Za-z0-9_]*)+)/gm),
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

if (!existsSync(entrypoint)) throw new Error('Public Python endpoint api/solve.py is missing')
inspect(entrypoint)
if (missing.size > 0) {
  throw new Error(`Public Python dependency closure is incomplete:\n${[...missing].sort().join('\n')}`)
}
console.log(`Public Python dependency closure verified: ${visited.size} local modules`)
