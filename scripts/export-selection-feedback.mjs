import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { createClient } from '@supabase/supabase-js'

const source = new URL('../data/mathos/continuous_verified_problem_batch1.json', import.meta.url)
const output = new URL('../data/mathos/selection-feedback.json', import.meta.url)
const reportOutput = new URL('../docs/selection-feedback.md', import.meta.url)
const pool = JSON.parse(await readFile(source, 'utf8'))

const url = process.env.NEXT_PUBLIC_SUPABASE_URL
const serviceKey = process.env.SUPABASE_SERVICE_KEY
if (!url || !serviceKey) {
  throw new Error('NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_KEY are required')
}

const supabase = createClient(url, serviceKey, {
  auth: { persistSession: false, autoRefreshToken: false },
})

const { data: problemRows, error: problemError } = await supabase
  .from('problems')
  .select('id,meta,statement')
  .like('meta', '%"candidateId"%')
if (problemError) throw problemError

const ids = (problemRows ?? []).map((row) => row.id)
const ratings = []
for (let offset = 0; offset < ids.length; offset += 200) {
  const { data, error } = await supabase
    .from('ratings')
    .select('problem_id,status,updated_at,note')
    .in('problem_id', ids.slice(offset, offset + 200))
    .in('status', ['selected', 'rejected'])
  if (error) throw error
  ratings.push(...(data ?? []))
}

const problemById = new Map((problemRows ?? []).map((row) => [row.id, row]))
const currentByStructure = new Map(
  (pool.problems ?? []).map((problem) => [problem.structure_key, problem]),
)
const groups = new Map()
const diagnostics = []

for (const rating of ratings) {
  const row = problemById.get(rating.problem_id)
  let meta = {}
  try { meta = row?.meta ? JSON.parse(row.meta) : {} } catch { /* ignore malformed history */ }
  const structureKey = meta.structureKey
  if (!structureKey) continue
  let note = {}
  try { note = rating.note ? JSON.parse(rating.note) : {} } catch { /* retain unspecified feedback */ }
  const repairReasons = Array.isArray(note?.curation_feedback?.reasons)
    ? note.curation_feedback.reasons.filter((reason) => typeof reason === 'string')
    : []
  diagnostics.push({
    selected: rating.status === 'selected',
    scalar_bridge: meta.verificationMethod === 'composed_closure_with_traceback',
    morphism_count: (meta.morphismChain ?? []).length,
    statement_length: row?.statement?.length ?? 0,
    repair_reasons: repairReasons,
  })
  const group = groups.get(structureKey) ?? {
    structure_key: structureKey,
    statuses: [],
    repair_reasons: [],
    row_count: 0,
  }
  group.statuses.push(rating.status)
  group.repair_reasons.push(...repairReasons)
  group.row_count += 1
  groups.set(structureKey, group)
}

const structures = [...groups.values()].map((group) => {
  const statuses = [...new Set(group.statuses)]
  const problem = currentByStructure.get(group.structure_key)
  const graph = problem?.proof_graph_certificate ?? {}
  const lift = problem?.lift_certificate ?? {}
  return {
    structure_key: group.structure_key,
    label: statuses.length === 1 ? statuses[0] : 'conflict',
    disposition: statuses.includes('selected') ? 'retain' : 'repair',
    repair_reasons: [...new Set(group.repair_reasons)],
    vote_rows: group.row_count,
    features: {
      interaction_verified: graph.interaction_verified === true,
      proof_node_count: graph.node_count ?? 0,
      proof_edge_count: graph.edge_count ?? 0,
      proof_merge_count: graph.merge_count ?? 0,
      morphism_count: (lift.morphism_chain ?? []).length,
      constraint_count: (lift.constraint_skeleton ?? []).length,
      has_query_signature: Boolean(lift.query_signature),
      active_in_current_pool: Boolean(problem),
    },
  }
})

const count = (label) => structures.filter((row) => row.label === label).length
const rawCount = (status) => ratings.filter((row) => row.status === status).length
const median = (values) => {
  const sorted = [...values].sort((a, b) => a - b)
  if (!sorted.length) return null
  const middle = Math.floor(sorted.length / 2)
  return sorted.length % 2
    ? sorted[middle]
    : (sorted[middle - 1] + sorted[middle]) / 2
}
const auc = (score) => {
  const positive = diagnostics.filter((row) => row.selected)
  const negative = diagnostics.filter((row) => !row.selected)
  let wins = 0
  let pairs = 0
  for (const left of positive) {
    for (const right of negative) {
      const a = score(left)
      const b = score(right)
      wins += a > b ? 1 : a === b ? 0.5 : 0
      pairs += 1
    }
  }
  return pairs ? Number((wins / pairs).toFixed(3)) : null
}
const scalarBridge = diagnostics.filter((row) => row.scalar_bridge)
const selectedDiagnostics = diagnostics.filter((row) => row.selected)
const rejectedDiagnostics = diagnostics.filter((row) => !row.selected)
const repairReasonCounts = rejectedDiagnostics.reduce((counts, row) => {
  const reasons = row.repair_reasons.length ? row.repair_reasons : ['unspecified']
  for (const reason of reasons) counts[reason] = (counts[reason] ?? 0) + 1
  return counts
}, {})
const payload = {
  generated_at: new Date().toISOString(),
  unit: 'structure_key',
  policy: {
    purpose: 'calibrate abstract repair operators, never memorize statements',
    allowed_features: [
      'proof DAG connectivity',
      'typed morphism count and composition',
      'constraint interaction',
      'query signature',
      'backend and verification contracts',
    ],
    forbidden_features: [
      'problem ID',
      'family ID as a label shortcut',
      'surface tokens or exact wording',
      'numeric parameters',
      'answers',
    ],
    rejected_semantics: 'repair signal, never automatic deletion of the mathematical structure',
    conflicts: 'retain and exclude from binary calibration until re-rated',
    split: 'hold out entire structure and morphism-chain clusters',
  },
  summary: {
    raw_vote_rows: ratings.length,
    raw_selected: rawCount('selected'),
    raw_rejected: rawCount('rejected'),
    unique_structures: structures.length,
    selected_structures: count('selected'),
    rejected_structures: count('rejected'),
    conflicting_structures: count('conflict'),
    current_pool_structures_with_votes: structures.filter(
      (row) => row.features.active_in_current_pool,
    ).length,
    duplicate_vote_rows_collapsed: ratings.length - structures.length,
    scalar_bridge_rows: scalarBridge.length,
    scalar_bridge_selected: scalarBridge.filter((row) => row.selected).length,
    scalar_bridge_rejected: scalarBridge.filter((row) => !row.selected).length,
    selected_morphism_median: median(
      selectedDiagnostics.map((row) => row.morphism_count),
    ),
    rejected_morphism_median: median(
      rejectedDiagnostics.map((row) => row.morphism_count),
    ),
    selected_statement_length_median: median(
      selectedDiagnostics.map((row) => row.statement_length),
    ),
    rejected_statement_length_median: median(
      rejectedDiagnostics.map((row) => row.statement_length),
    ),
    repair_reason_counts: repairReasonCounts,
    auc: {
      reject_scalar_bridge: auc((row) => row.scalar_bridge ? 0 : 1),
      morphism_count: auc((row) => row.morphism_count),
      shorter_statement: auc((row) => -row.statement_length),
    },
  },
  structures,
}

const lines = [
  '# MathOS 選択・スキップ投票監査',
  '',
  `生成時刻: ${payload.generated_at}`,
  '',
  '## 集計',
  '',
  `- 生の投票行: ${payload.summary.raw_vote_rows}`,
  `- 選択: ${payload.summary.raw_selected}`,
  `- スキップ: ${payload.summary.raw_rejected}`,
  `- 構造署名でまとめた件数: ${payload.summary.unique_structures}`,
  `- 競合票のある構造: ${payload.summary.conflicting_structures}`,
  `- 重複行として構造単位へ畳み込んだ票: ${payload.summary.duplicate_vote_rows_collapsed}`,
  '',
  '## 観測結果',
  '',
  `- 無関係な数値接続: ${payload.summary.scalar_bridge_rows}問中、選択${payload.summary.scalar_bridge_selected}・スキップ${payload.summary.scalar_bridge_rejected}`,
  `- 射の個数中央値: 選択${payload.summary.selected_morphism_median}、スキップ${payload.summary.rejected_morphism_median}`,
  `- 問題文長中央値: 選択${payload.summary.selected_statement_length_median}、スキップ${payload.summary.rejected_statement_length_median}`,
  `- 修復理由: ${JSON.stringify(payload.summary.repair_reason_counts)}`,
  `- 識別AUC: 数値接続除外${payload.summary.auc.reject_scalar_bridge}、射の個数${payload.summary.auc.morphism_count}、短さ${payload.summary.auc.shorter_statement}`,
  '',
  '## 学習契約',
  '',
  '- スキップは構造の削除票ではなく、現状の問題表現に対する修復信号として扱う。',
  '- 問題文、答え、数値、問題ID、族名を特徴量にしない。',
  '- 証明DAGの合流、型付き射、制約相互作用、query、検証契約だけを使う。',
  '- 同じ構造の重複票は一票にまとめ、選択とスキップが競合した構造は較正から外す。',
  '- 評価時は同じ射列の問題をdevとheld-outへ分散させない。',
  '',
]

await mkdir(new URL('../data/mathos/', import.meta.url), { recursive: true })
await mkdir(new URL('../docs/', import.meta.url), { recursive: true })
await writeFile(output, JSON.stringify(payload, null, 2) + '\n')
await writeFile(reportOutput, lines.join('\n'))
console.log(JSON.stringify(payload.summary, null, 2))
