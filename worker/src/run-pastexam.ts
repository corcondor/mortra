/**
 * 8大学の過去問 5,369 問を全部、汎用核に通す。
 *
 * 部分集合を選んで測るのはやめる。選んだ時点で数字の意味が薄れる。
 * 出すのは段階ごとの通過数。どこで落ちているかが分かる形にする。
 *
 *   問いが取れた      → 何を求められているか型が付いた
 *   核が扱える        → 構造が型付きで読めた
 *   目標に到達        → 型の上で経路がある
 *   実行が証明された   → 実際に計算し、証明書が出た
 *
 *   npx tsx src/run-pastexam.ts artifacts/pastexam-5369.jsonl artifacts/pastexam-run.json
 */
import { readFileSync, writeFileSync } from 'node:fs'
import { evaluateBenchmarkRequest } from './benchmark-bridge'

type Row = { id: string; statement: string; benchmark?: string; answer?: string }

const input = process.argv[2]
const output = process.argv[3]
if (!input) {
  console.error('usage: run-pastexam.ts <input.jsonl> [output.json]')
  process.exit(1)
}

const rows: Row[] = readFileSync(input, 'utf8')
  .split(/\r?\n/)
  .filter(Boolean)
  .map(line => JSON.parse(line) as Row)

type Outcome = {
  id: string
  benchmark: string
  status: string
  execution_status: string
  execution_proof: string
  goal_count: number
  states: number
  root_sorts: string[]
  query_sorts: string[]
}

const outcomes: Outcome[] = []
const started = process.hrtime.bigint()

for (let i = 0; i < rows.length; i++) {
  const row = rows[i]
  if (i % 100 === 0) {
    const secs = Number(process.hrtime.bigint() - started) / 1e9
    process.stderr.write(`\r${i}/${rows.length}  ${secs.toFixed(0)}s`)
  }
  try {
    // 探索は打ち切る。全問を現実的な時間で通すことを優先する
    const r = evaluateBenchmarkRequest({
      id: row.id,
      statement: row.statement,
      compact: true,
      max_depth: 5,
      max_states: 1500,
    }) as Record<string, unknown>
    outcomes.push({
      id: row.id,
      benchmark: row.benchmark ?? '?',
      status: String(r.status),
      execution_status: String((r.execution as { status?: string } | undefined)?.status ?? 'none'),
      execution_proof: String(r.execution_proof_status ?? 'none'),
      goal_count: Number(r.goal_count ?? 0),
      states: Number(r.states_explored ?? 0),
      root_sorts: (r.root_sorts as string[]) ?? [],
      query_sorts: (r.query_sorts as string[]) ?? [],
    })
  } catch (error) {
    outcomes.push({
      id: row.id, benchmark: row.benchmark ?? '?', status: 'error',
      execution_status: 'error', execution_proof: 'none',
      goal_count: 0, states: 0, root_sorts: [], query_sorts: [],
      })
    void error
  }
}
process.stderr.write('\r')

const count = (pred: (o: Outcome) => boolean) => outcomes.filter(pred).length
const n = outcomes.length
const pct = (k: number) => `${k}/${n} = ${(100 * k / n).toFixed(1)}%`

console.log(`\n8大学 ${n} 問を全件、汎用核に通した\n`)
console.log(`  問いの型が取れた    ${pct(count(o => o.query_sorts.length > 0))}`)
console.log(`  目標に到達          ${pct(count(o => o.status === 'goal_reached'))}`)
console.log(`  実行が下りた        ${pct(count(o => o.execution_status === 'lowered'))}`)
console.log(`  実行が証明された    ${pct(count(o => o.execution_proof === 'certified'))}`)
console.log(`  例外                ${count(o => o.status === 'error')}`)

console.log('\n段階別の内訳（status）:')
const byStatus = new Map<string, number>()
outcomes.forEach(o => byStatus.set(o.status, (byStatus.get(o.status) ?? 0) + 1))
;[...byStatus].sort((a, b) => b[1] - a[1]).forEach(([k, v]) => console.log(`  ${k.padEnd(22)} ${v}`))

console.log('\n大学別（目標到達 / 全問）:')
const univs = [...new Set(outcomes.map(o => o.benchmark))].sort()
for (const u of univs) {
  const sub = outcomes.filter(o => o.benchmark === u)
  const reached = sub.filter(o => o.status === 'goal_reached').length
  const certified = sub.filter(o => o.execution_proof === 'certified').length
  console.log(`  ${u.padEnd(14)} 到達 ${String(reached).padStart(4)}/${String(sub.length).padStart(4)}`
    + `  証明つき実行 ${certified}`)
}

if (output) {
  writeFileSync(output, JSON.stringify({ total: n, outcomes }, null, 2), 'utf8')
  console.log(`\n→ ${output}`)
}
