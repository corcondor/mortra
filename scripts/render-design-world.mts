/**
 * 一つの意味核から六種類の意匠を書き出す。
 *
 * 単発の SVG 生成ではないことを、実物で示す。
 * すべて同じ A₃/FCC の semantic object を参照している。
 *
 *   npx tsx scripts/render-design-world.mts
 */
import { writeFile, mkdir } from 'node:fs/promises'
import { seedFromLattice, buildDesignWorld, auditDesignWorld } from '../lib/mortra/vision/design-world.js'

const OUT = 'export/design-world'
await mkdir(OUT, { recursive: true })

let made = 0
const rows: string[] = []
const problems: string[] = []

for (const key of ['fcc', 'bcc'] as const) {
  const seed = seedFromLattice(key)
  for (const group of ['p6m', 'p4m'] as const) {
    const artifacts = buildDesignWorld(seed, group)
    problems.push(...auditDesignWorld(artifacts).map(p => `${key}/${group} ${p}`))
    for (const a of artifacts) {
      await writeFile(`${OUT}/${key}-${group}-${a.kind}.svg`, a.svg, 'utf8')
      made++
      const certified = a.claims.filter(c => c.status === 'certified').length
      const heuristic = a.claims.filter(c => c.status === 'design_heuristic').length
      const rejected = a.claims.filter(c => c.status === 'rejected').length
      rows.push(`  ${key}/${group.padEnd(4)} ${a.kind.padEnd(12)} ${a.width}×${a.height}`
        + `  certified ${certified}  design_heuristic ${heuristic}`
        + `${rejected ? `  rejected ${rejected}` : ''}`
        + `  対称性 ${a.symmetryVerified ? '検証済み' : '未検証'}`)
    }
  }
}

console.log('\n一つの意味核から生成した意匠\n')
rows.forEach(r => console.log(r))

// 主張の内訳を一つ出す
const sample = buildDesignWorld(seedFromLattice('fcc'), 'p6m')[2]
console.log(`\n主張の内訳（${sample.kind}）:`)
for (const c of sample.claims) {
  const tag = c.status === 'certified' ? 'certified       '
    : c.status === 'design_heuristic' ? 'design_heuristic' : 'rejected        '
  console.log(`  [${tag}] ${c.statement}`)
  console.log(`                      ${c.evidence ?? c.derivedFrom ?? ''}`)
}

console.log(`\n書き出し ${made} 枚 → ${OUT}/`)
console.log(`整合の問題 ${problems.length} 件${problems.length ? ':' : ''}`)
problems.forEach(p => console.log(`  ${p}`))
process.exit(problems.length ? 1 : 0)
