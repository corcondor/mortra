import { cp, readdir, readFile } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import path from 'node:path'

const root = path.resolve('web/public/mortra/runs')
for (const entry of await readdir(root, { withFileTypes: true })) {
  if (!entry.isDirectory()) continue
  const dir = path.join(root, entry.name)
  const manifest = JSON.parse(await readFile(path.join(dir, 'manifest.json'), 'utf8'))
  for (const [name, expected] of Object.entries(manifest)) {
    const actual = createHash('sha256').update(await readFile(path.join(dir, name))).digest('hex')
    if (actual !== expected) throw new Error(`Experiment artifact changed: ${entry.name}/${name}`)
  }
  await cp(dir, path.resolve('public/mortra/runs', entry.name), { recursive: true })
  console.log(`Verified and synchronized recorded experiment: ${entry.name}`)
}
