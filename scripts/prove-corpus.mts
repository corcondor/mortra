/**
 * 形式化済みの問題を Proof Scene コンパイラに通し、証明が本当に閉じるか測る。
 * 出るのは「解けた気がする」ではなく、規則名つきの導出列。
 *
 *   npx tsx scripts/prove-corpus.mts
 */
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { compileScene, formulaOf, type Fact, type Pt } from '../lib/proof-scene.js'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

type Raw = {
  id: string; title: string; text: string; status: string
  predicates: { name: string; args: string[] }[]
  goal: { name: string; args: string[] } | null
  coordinates: Record<string, [number, number]>
}

/** 形式化器は中点を coll + cong の二本で出す。人が読む単位に束ね直す */
function toFacts(raw: Raw): { premises: Fact[]; goal: Fact | null } {
  const P = raw.predicates
  const used = new Set<number>()
  const premises: Fact[] = []

  P.forEach((c, i) => {
    if (c.name !== 'cong' || used.has(i)) return
    const [a, m1, m2, b] = c.args
    if (m1 !== m2) return
    const j = P.findIndex((o, k) => !used.has(k) && o.name === 'coll'
      && new Set(o.args).size === 3 && o.args.includes(m1) && o.args.includes(a) && o.args.includes(b))
    if (j < 0) return
    used.add(i); used.add(j)
    premises.push({ pred: 'midp', args: [m1, a, b] })
  })
  P.forEach((c, i) => {
    if (used.has(i)) return
    if (['perp', 'para', 'coll', 'cong'].includes(c.name)) {
      premises.push({ pred: c.name as Fact['pred'], args: c.args })
    }
  })

  const goal = raw.goal && ['perp', 'para', 'coll', 'cong'].includes(raw.goal.name)
    ? { pred: raw.goal.name as Fact['pred'], args: raw.goal.args }
    : null
  return { premises, goal }
}

const corpus: Raw[] = JSON.parse(
  await readFile(path.join(ROOT, 'data', 'formalized-geometry.json'), 'utf8'),
)

let proved = 0
const ruleUse = new Map<string, string[]>()

for (const raw of corpus) {
  if (raw.status !== 'formalized') {
    console.log(`\n■ ${raw.title} — 形式化できていない (${raw.status})`)
    continue
  }
  const { premises, goal } = toFacts(raw)
  if (!goal) { console.log(`\n■ ${raw.title} — 目標がとれない`); continue }

  const points: Record<string, Pt> = {}
  for (const [k, v] of Object.entries(raw.coordinates)) points[k] = { x: v[0], y: v[1] }

  const scene = compileScene({
    title: raw.title, statement: raw.text, premises, goal, points,
  })
  if (scene.proved) proved++

  console.log(`\n■ ${raw.title}   ${scene.proved ? '証明済み' : '未証明'}`)
  console.log(`  ${raw.text}`)
  for (const b of scene.beats) {
    const tag = b.role === 'given' ? '与' : b.role === 'goal' ? '∴' : '⇒'
    console.log(`   ${tag} ${formulaOf(b.claim).padEnd(26)} ${b.rule ?? ''}`)
  }
  scene.rulesUsed.forEach(r => ruleUse.set(r, [...(ruleUse.get(r) ?? []), raw.id]))
}

console.log(`\n${'─'.repeat(60)}`)
console.log(`証明 ${proved}/${corpus.filter(c => c.status === 'formalized').length}`)
console.log('\n規則が効いた問題数（1問専用なら暗記、複数なら語彙）:')
for (const [rule, ids] of [...ruleUse].sort((a, b) => b[1].length - a[1].length)) {
  console.log(`  ${rule.padEnd(20)} ${ids.length}問  ${ids.join(', ')}`)
}
