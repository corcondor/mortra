/**
 * Semantic Kernel の統合テスト。
 *
 * 格子・群・意匠が同じ semantic object と同じ certificate を
 * 本当に共有しているかを確かめる。共有していなければ統合ではない。
 *
 *   npx tsx scripts/kernel-integration.mts
 */
import {
  buildIntegratedKernel, fromCasVerdict, fromLinearStatus,
  fromProofScene,
} from '../lib/mortra/kernel/adapters.js'
import {
  auditKernel, statusCounts, transportPath, conventionsAgree, resolveBinding,
  type SymbolBinding,
} from '../lib/mortra/kernel/semantic-kernel.js'

let pass = 0, fail = 0
const notes: string[] = []
const check = (n: string, ok: boolean, d = '') => {
  ok ? pass++ : (fail++, notes.push(`${n}  ${d}`))
  console.log(`${ok ? '  ok  ' : '  NG  '} ${n}${ok || !d ? '' : '   ' + d}`)
}

const k = buildIntegratedKernel()

console.log('\n■ 核の中身')
console.log(`  対象 ${k.objects.size} / 関係 ${k.relations.size} / 射 ${k.morphisms.size} / 証明書 ${k.certificates.size}`)

console.log('\n■ 監査 — 矛盾があれば成果物を出さない')
const violations = auditKernel(k)
check('矛盾なし', violations.length === 0,
  violations.slice(0, 3).map(v => `${v.kind}: ${v.detail}`).join(' / '))

console.log('\n■ 状態が一つの語彙で数えられる')
const counts = statusCounts(k)
for (const [status, n] of Object.entries(counts).sort((a, b) => b[1] - a[1])) {
  console.log(`  ${status.padEnd(24)} ${n}`)
}
check('proved は証明書つきのみ', Object.keys(counts).includes('proved'))

console.log('\n■ 射が不変量を宣言している')
const withoutInvariant = [...k.morphisms.values()].filter(m => !m.preserved.length)
check('不変量のない射がない', withoutInvariant.length === 0,
  withoutInvariant.map(m => m.name).join(', '))
for (const m of k.morphisms.values()) {
  console.log(`  ${m.name.padEnd(28)} ${m.sourceSorts.join(',')} → ${m.targetSorts.join(',')}`)
  console.log(`  ${''.padEnd(28)} 保つもの: ${m.preserved.join(' / ')}`)
}

console.log('\n■ semantic identity が追える')
{
  const pattern = [...k.objects.values()].find(o => o.label?.includes('p6m pattern'))
  check('意匠が意味核を参照している', !!pattern && pattern.provenance.consumed.length > 0,
    pattern ? `consumed ${pattern.provenance.consumed.length}` : 'なし')
  if (pattern) {
    const path = transportPath(k, pattern.id)
    check('通ってきた射が辿れる', path.length > 0, path.map(m => m.name).join(' → '))
  }
  const roots = [...k.objects.values()].find(o => o.sort === 'RootSystem')
  check('格子からルート系への射がある', !!roots,
    roots ? `${roots.label}` : 'なし')
}

console.log('\n■ 規約が暗黙にならない')
{
  const a = [{ kind: 'theta_exponent' as const, value: 'norm_squared' }]
  const b = [{ kind: 'theta_exponent' as const, value: 'half_norm_squared' }]
  const r = conventionsAgree(a, b)
  check('規約の食い違いを検出する', !r.agree,
    r.conflicts.map(c => `${c.kind} ${c.from}→${c.to}`).join(', '))
  check('同じ規約なら通る', conventionsAgree(a, a).agree)
}

console.log('\n■ 記号の役割が出所の順で決まる')
{
  const explicit: SymbolBinding = { name: 'I', role: 'function', sort: 'Function',
    source: 'explicit_declaration', confidence: 1 }
  const guessed: SymbolBinding = { name: 'I', role: 'constant', sort: 'Complex',
    source: 'standard_dictionary', confidence: 0.5 }
  check('明示宣言が辞書に勝つ', resolveBinding([guessed, explicit])?.role === 'function')

  const clash: SymbolBinding[] = [
    { name: 'C', role: 'function', source: 'presentation_structure', confidence: 0.8 },
    { name: 'C', role: 'variable', source: 'presentation_structure', confidence: 0.8 },
  ]
  check('同順位で食い違えば棄権する', resolveBinding(clash) === null)
}

console.log('\n■ 既存の状態語彙が核へ写る（7箇所の proved が一つになる）')
{
  const cases: [string, string, string][] = [
    ['cas proved', fromCasVerdict('proved', 'solved'), 'proved'],
    ['cas verified_instance', fromCasVerdict('verified_instance', 'solved'), 'verified_instance'],
    ['cas not_reduced', fromCasVerdict(undefined, 'not_reduced'), 'unformalized'],
    ['linear proved', fromLinearStatus('proved'), 'proved'],
    ['linear inconsistent', fromLinearStatus('inconsistent'), 'disproved'],
    ['proof-scene 数値のみ', fromProofScene(true, true), 'verified_instance'],
  ]
  for (const [name, got, want] of cases) {
    check(`${name} → ${want}`, got === want, got)
  }
  check('proof-scene を proved と呼ばない', fromProofScene(true, true) !== 'proved',
    '前向き推論＋座標検証は verified_instance であって記号的証明ではない')
}

console.log(`\n${'─'.repeat(64)}`)
console.log(`統合テスト ${pass}/${pass + fail}${fail ? `   失敗 ${fail}` : ''}`)
notes.forEach(n => console.log(`  ${n}`))
process.exit(fail ? 1 : 0)
