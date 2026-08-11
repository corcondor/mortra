/**
 * Slice B — A₃/FCC → Design World、および revision の伝播。
 *
 * 「一つを直したら全部更新」が本当に起きるかを確かめる。
 * 別々に生成していたら、直しても他は変わらない。
 *
 *   npx tsx scripts/slice-b-revision.mts
 */
import { seedFromLattice, buildDesignWorld, auditDesignWorld } from '../lib/mortra/vision/design-world.js'
import { buildIntegratedKernel } from '../lib/mortra/kernel/adapters.js'
import { transportPath } from '../lib/mortra/kernel/semantic-kernel.js'

let pass = 0, fail = 0
const check = (n: string, ok: boolean, d = '') => {
  ok ? pass++ : fail++
  console.log(`${ok ? '  ok  ' : '  NG  '} ${n}${ok || !d ? '' : '   ' + d}`)
}

console.log('\n■ 同じ意味核から六種類が出る')
const seed = seedFromLattice('fcc')
const before = buildDesignWorld(seed, 'p6m')
check('六種類できる', before.length === 6, before.map(a => a.kind).join(', '))
check('全部が同じ seed を参照', before.every(a => a.references.includes(seed.id)), String(seed.id))
check('整合の問題なし', auditDesignWorld(before).length === 0)

console.log('\n■ revision の伝播 — 群を変えると全成果物が変わる')
{
  const after = buildDesignWorld(seed, 'p4m')
  const changed = before.filter((b, i) => b.svg !== after[i].svg)
  check('群の変更が全成果物に伝播する', changed.length === before.length,
    `${changed.length}/${before.length} が変化`)
  // 意味の同一性は保たれる。参照する seed は同じ
  check('伝播しても意味核の参照は同じ',
    after.every(a => a.references.includes(seed.id)))
}

console.log('\n■ revision の伝播 — 格子を変えると全成果物が変わる')
{
  const bcc = seedFromLattice('bcc')
  const after = buildDesignWorld(bcc, 'p6m')
  const changed = before.filter((b, i) => b.svg !== after[i].svg)
  check('格子の変更が全成果物に伝播する', changed.length === before.length,
    `${changed.length}/${before.length} が変化`)
  check('参照先が新しい seed になる',
    after.every(a => a.references.includes(bcc.id) && !a.references.includes(seed.id)))
}

console.log('\n■ certified と design_interpretation が分かれている')
{
  const poster = before.find(a => a.kind === 'poster')!
  const certified = poster.claims.filter(c => c.status === 'certified')
  const heuristic = poster.claims.filter(c => c.status === 'design_heuristic')
  check('certified に根拠がある', certified.every(c => !!c.evidence), `${certified.length} 件`)
  check('design_heuristic に出所がある', heuristic.every(c => !!c.derivedFrom), `${heuristic.length} 件`)
  check('両方が存在する（片方に潰していない）', certified.length > 0 && heuristic.length > 0)
}

console.log('\n■ 共有 kernel を使っている（design 専用の群実装がない）')
{
  const k = buildIntegratedKernel()
  const orbitMorphisms = [...k.morphisms.values()].filter(m => m.name === 'GroupActionToOrbitPattern')
  check('意匠が射として核に登録されている', orbitMorphisms.length > 0, `${orbitMorphisms.length} 本`)
  const pattern = [...k.objects.values()].find(o => o.label?.includes('pattern'))
  if (pattern) {
    const path = transportPath(k, pattern.id)
    check('意匠から格子まで射で辿れる', path.length > 0, path.map(m => m.name).join(' → '))
  }
  const latticeObjects = [...k.objects.values()].filter(o => o.sort === 'Lattice')
  check('格子は一箇所から来ている', latticeObjects.every(
    o => o.provenance.source.includes('lattice.ts') || o.provenance.source === 'dual()'),
    latticeObjects.map(o => o.provenance.source).join(', ').slice(0, 60))
}

console.log(`\n${'─'.repeat(60)}`)
console.log(`Slice B ${pass}/${pass + fail}`)
process.exit(fail ? 1 : 0)
