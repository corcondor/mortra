import { createHash } from 'node:crypto'
import { mkdir, writeFile } from 'node:fs/promises'
import { createClient } from '@supabase/supabase-js'

const url = process.env.NEXT_PUBLIC_SUPABASE_URL
const serviceKey = process.env.SUPABASE_SERVICE_KEY
if (!url || !serviceKey) throw new Error('Supabase credentials are required')

const supabase = createClient(url, serviceKey, {
  auth: { persistSession: false, autoRefreshToken: false },
})
const { data, error } = await supabase
  .from('generation_jobs')
  .select('id,status,parents,result,error,created_at')
  .in('status', ['failed', 'done'])
  .order('created_at', { ascending: false })
  .limit(1000)
if (error) throw error

const canonicalSignature = (parents) => (parents ?? [])
  .flatMap((profile) => profile?.allParentScaffold ? [profile] : [])
  .flatMap((profile) => profile.parentAnchorSets ?? [])
  .map((entry) => ({ parentId: entry.parentId, anchors: [...(entry.anchors ?? [])].sort() }))
  .sort((left, right) => left.parentId.localeCompare(right.parentId))

const groups = new Map()
for (const row of data ?? []) {
  const pending = (row.result?.structures ?? []).filter((structure) => structure.status === 'pending')
  if (!pending.length) continue
  const signature = canonicalSignature(row.parents)
  if (signature.length < 2) continue
  const signatureJson = JSON.stringify(signature)
  const key = createHash('sha256').update(signatureJson).digest('hex').slice(0, 12)
  const group = groups.get(key) ?? {
    gap_id: key,
    occurrences: 0,
    latest_at: row.created_at,
    parent_signatures: signature,
    rejection_counts: {},
    job_ids: [],
  }
  group.occurrences += 1
  group.job_ids.push(row.id)
  for (const [reason, count] of Object.entries(row.result?.rejectionCounts ?? {})) {
    group.rejection_counts[reason] = (group.rejection_counts[reason] ?? 0) + Number(count || 0)
  }
  groups.set(key, group)
}

const gaps = [...groups.values()].sort((left, right) =>
  right.occurrences - left.occurrences || right.latest_at.localeCompare(left.latest_at),
)
const payload = {
  generated_at: new Date().toISOString(),
  policy: 'cluster unsupported all-parent fusion signatures; never promote without an executable fusion contract',
  gap_count: gaps.length,
  gaps,
}

await mkdir(new URL('../data/mathos/', import.meta.url), { recursive: true })
await mkdir(new URL('../docs/', import.meta.url), { recursive: true })
await writeFile(new URL('../data/mathos/fusion-gaps.json', import.meta.url), JSON.stringify(payload, null, 2) + '\n')

const lines = [
  '# MathOS 融合構造ギャップ',
  '',
  `生成時刻: ${payload.generated_at}`,
  '',
  `未対応の全親構造クラスタ: ${gaps.length}件`,
  '',
  '同じ構造署名の失敗をまとめ、頻度順に実行契約の追加対象とする。問題本文や数値では分岐しない。',
  '',
  '| gap | 回数 | 親の構造署名 | 主な棄却理由 |',
  '|---|---:|---|---|',
  ...gaps.slice(0, 100).map((gap) => {
    const parents = gap.parent_signatures.map((parent) => parent.anchors.join('+')).join(' × ')
    const reasons = Object.entries(gap.rejection_counts)
      .sort((left, right) => right[1] - left[1])
      .slice(0, 3)
      .map(([reason, count]) => `${reason}:${count}`)
      .join(', ')
    return `| ${gap.gap_id} | ${gap.occurrences} | ${parents} | ${reasons || '-'} |`
  }),
  '',
]
await writeFile(new URL('../docs/fusion-gaps.md', import.meta.url), lines.join('\n'))
console.log(`fusion gaps: ${gaps.length}`)
