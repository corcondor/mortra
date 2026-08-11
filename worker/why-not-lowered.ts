import { readFileSync } from 'node:fs'
import { lowerLinearPredicateStatement } from './src/linear-predicate-lowerer'
type Row = { id: string; statement: string; benchmark?: string }
const rows: Row[] = readFileSync(process.argv[2], 'utf8').split(/\r?\n/).filter(Boolean).map(l => JSON.parse(l))
const by = new Map<string, number>()
const samples = new Map<string, string>()
for (const r of rows) {
  let s = 'exception'
  try {
    const res = lowerLinearPredicateStatement(r.statement, 'additive') as { status: string; detail?: string }
    s = res.status
    if (!samples.has(s)) samples.set(s, `${res.detail ?? ''} || ${r.statement.slice(0, 90)}`)
  } catch (e) { if (!samples.has(s)) samples.set(s, String(e).slice(0, 80)) }
  by.set(s, (by.get(s) ?? 0) + 1)
}
console.log(`\n実行への lowering が ${rows.length} 問でどうなるか\n`)
;[...by].sort((a, b) => b[1] - a[1]).forEach(([k, v]) =>
  console.log(`  ${k.padEnd(20)} ${String(v).padStart(5)}  ${(100*v/rows.length).toFixed(1)}%`))
console.log('\n各状態の実例:')
for (const [k, v] of samples) console.log(`  [${k}] ${v.replace(/\s+/g,' ').slice(0,130)}`)
