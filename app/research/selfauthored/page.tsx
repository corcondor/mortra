'use client'

import { useMemo, useState } from 'react'
import Link from 'next/link'
import analysis from '@/data/mathos/selfauthored-analysis.json'
import motifReport from '@/data/mathos/motif-guided-problems.json'
import { MathText } from '@/components/MathText'

type RecordItem = (typeof analysis.records)[number]
type AnswerNode = NonNullable<RecordItem['answer_graph']>['nodes'][number]

const NODE_Y: Record<string, number> = {
  premise: 48,
  lemma: 116,
  definition_or_derivation: 184,
  explanation: 252,
  conclusion: 320,
}

function SemanticFlow({ record }: { record: RecordItem }) {
  const columns = [
    { title: '対象', items: record.objects.map(item => `${item.name}: ${item.sort}`), color: '#175cd3' },
    { title: '射', items: record.morphisms.map(item => item.name), color: '#6941c6' },
    { title: '制約', items: record.constraints.map(item => item.expression), color: '#b54708' },
    { title: '問い', items: record.queries.map(item => `${item.kind}: ${item.target}`), color: '#067647' },
  ]
  return (
    <div className="grid gap-0 overflow-x-auto pb-2 sm:grid-cols-4">
      {columns.map((column, columnIndex) => (
        <div key={column.title} className="relative min-w-48 border-l border-[#d8dee9] px-4 py-3 first:border-l-0">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-xs font-medium" style={{ color: column.color }}>{column.title}</h3>
            <span className="text-xs tabular-nums text-[#98a2b3]">{column.items.length}</span>
          </div>
          <div className="space-y-2">
            {column.items.slice(0, 8).map((item, index) => (
              <div key={`${item}-${index}`} className="border-l-2 bg-white px-3 py-2 text-[11px] leading-5 text-[#344054]" style={{ borderColor: column.color }}>
                {item}
              </div>
            ))}
            {!column.items.length && <p className="py-2 text-xs text-[#d92d20]">抽出なし</p>}
            {column.items.length > 8 && <p className="text-xs text-[#667085]">ほか {column.items.length - 8}件</p>}
          </div>
          {columnIndex < columns.length - 1 && <span className="absolute -right-2 top-8 z-10 hidden bg-[#f7f9fc] px-1 text-[#98a2b3] sm:block">→</span>}
        </div>
      ))}
    </div>
  )
}

function nodePosition(node: AnswerNode, answerNodes: AnswerNode[], premiseNodes: AnswerNode[]) {
  if (node.kind === 'premise') {
    const index = premiseNodes.findIndex(item => item.id === node.id)
    return { x: 52, y: 48 + index * Math.min(38, 260 / Math.max(1, premiseNodes.length)) }
  }
  const index = answerNodes.findIndex(item => item.id === node.id)
  const baseY = NODE_Y[node.kind] ?? 252
  return {
    x: 132 + index / Math.max(1, answerNodes.length - 1) * 850,
    y: baseY + (index % 3 - 1) * 10,
  }
}

function AnswerDependencyGraph({ record }: { record: RecordItem }) {
  const graph = record.answer_graph
  if (!graph) return <p className="py-8 text-sm text-[#667085]">このTeXには対応する解答本文がありません。</p>
  const premiseNodes = graph.nodes.filter(node => node.kind === 'premise')
  const allAnswerNodes = graph.nodes.filter(node => node.kind !== 'premise')
  const answerNodes = allAnswerNodes.slice(0, 72)
  const shownIds = new Set([...premiseNodes, ...answerNodes].map(node => node.id))
  const shownEdges = graph.edges.filter(edge => shownIds.has(edge.source) && shownIds.has(edge.target))
  const colors: Record<string, string> = {
    premise: '#175cd3', lemma: '#6941c6', definition_or_derivation: '#b54708', explanation: '#98a2b3', conclusion: '#067647',
  }
  return (
    <div>
      <svg viewBox="0 0 1040 370" className="block w-full border-y border-[#d8dee9] bg-white" role="img" aria-label="解答の変数定義と接続語から抽出した依存グラフ">
        <title>問題{record.ordinal} 解答依存グラフ</title>
        {[48, 116, 184, 252, 320].map(y => <line key={y} x1="24" x2="1016" y1={y} y2={y} stroke="#eaecf0" />)}
        {shownEdges.map((edge, index) => {
          const source = graph.nodes.find(node => node.id === edge.source)!
          const target = graph.nodes.find(node => node.id === edge.target)!
          const a = nodePosition(source, answerNodes, premiseNodes)
          const b = nodePosition(target, answerNodes, premiseNodes)
          return <line key={`${edge.source}-${edge.target}-${index}`} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={edge.kind === 'logical_consequence' ? '#d92d20' : '#c6ccd5'} strokeWidth="1" opacity="0.75" />
        })}
        {[...premiseNodes, ...answerNodes].map(node => {
          const point = nodePosition(node, answerNodes, premiseNodes)
          return (
            <circle key={node.id} cx={point.x} cy={point.y} r={node.kind === 'conclusion' ? 5 : 3.5} fill={colors[node.kind] ?? '#98a2b3'}>
              <title>{node.id}: {node.text}</title>
            </circle>
          )
        })}
        <text x="18" y="20" fontSize="11" fill="#667085">前提</text>
        <text x="1000" y="354" textAnchor="end" fontSize="11" fill="#667085">論証の進行 →</text>
      </svg>
      <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-xs text-[#475467]">
        {Object.entries(colors).map(([kind, color]) => <span key={kind}><i className="mr-1.5 inline-block h-2 w-2 rounded-full" style={{ background: color }} />{kind}</span>)}
      </div>
      <div className="mt-4 grid gap-3 text-xs text-[#475467] sm:grid-cols-5">
        <p>論証単位 <strong>{graph.metrics.argument_units}</strong></p>
        <p>依存辺 <strong>{graph.metrics.dependency_edges}</strong></p>
        <p>合流節点 <strong>{graph.metrics.merge_nodes}</strong></p>
        <p>最長経路 <strong>{graph.metrics.longest_dependency_path}</strong></p>
        <p>辺回収率 <strong>{(graph.metrics.linked_answer_unit_rate * 100).toFixed(1)}%</strong></p>
      </div>
      {allAnswerNodes.length > answerNodes.length && <p className="mt-2 text-xs text-[#b54708]">表示は先頭72節点。集計値は全{allAnswerNodes.length}節点。</p>}
    </div>
  )
}

export default function SelfAuthoredResearchPage() {
  const defaultIndex = Math.max(0, analysis.records.findIndex(record => record.ordinal === 7))
  const [selected, setSelected] = useState(defaultIndex)
  const [answerOnly, setAnswerOnly] = useState(false)
  const records = useMemo(() => answerOnly ? analysis.records.filter(record => record.answer_available) : analysis.records, [answerOnly])
  const record = analysis.records[selected] ?? analysis.records[0]
  const summary = analysis.summary
  const generated = motifReport.problems[0]

  return (
    <main className="h-screen overflow-y-auto bg-[#f7f9fc] text-[#14213d]">
      <div className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-7 lg:py-12">
        <header className="border-b border-[#d8dee9] pb-6">
          <div className="flex flex-wrap items-start justify-between gap-5">
            <div>
              <h1 className="text-3xl font-medium sm:text-4xl">全問題.tex 構造監査</h1>
              <p className="mt-3 max-w-3xl text-sm leading-7 text-[#475467]">自作81問を、構文IR・型付き意味グラフ・LiftCertificate・解答依存に分解した実測結果です。解析できなかった関係は補完せず、そのまま欠落として表示します。</p>
            </div>
            <Link href="/research/difficulty" className="border border-[#98a2b3] bg-white px-3 py-2 text-xs">全体監査へ</Link>
          </div>
        </header>

        <section className="grid gap-5 border-b border-[#d8dee9] py-6 sm:grid-cols-3 lg:grid-cols-6">
          {[ 
            ['問題', summary.problems], ['type checked', summary.semantic_type_checked], ['Lift', summary.with_lift_certificate],
            ['解答付き', summary.answers_attached], ['潜在射', summary.latent_morphism_occurrences], ['依存辺', summary.answer_dependency_edges],
          ].map(([label, value]) => <div key={label}><p className="text-xs text-[#667085]">{label}</p><p className="mt-1 text-3xl font-medium tabular-nums">{value}</p></div>)}
        </section>

        <section className="border-b border-[#d8dee9] py-7">
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
            <div><h2 className="text-lg font-medium">問題一覧</h2><p className="mt-1 text-xs text-[#667085]">行を選ぶと下のグラフが切り替わります</p></div>
            <label className="flex items-center gap-2 text-xs text-[#475467]"><input type="checkbox" checked={answerOnly} onChange={event => setAnswerOnly(event.target.checked)} />解答付き11問のみ</label>
          </div>
          <div className="max-h-80 overflow-auto border-y border-[#d8dee9] bg-white">
            <table className="w-full min-w-[760px] border-collapse text-left text-xs">
              <thead className="sticky top-0 bg-[#f2f4f7] text-[#667085]"><tr><th className="px-3 py-2">#</th><th>分野</th><th>状態</th><th>対象</th><th>射</th><th>制約</th><th>Lift</th><th>解答</th></tr></thead>
              <tbody>
                {records.map(item => (
                  <tr key={item.ordinal} onClick={() => setSelected(analysis.records.findIndex(source => source.ordinal === item.ordinal))} className="cursor-pointer border-t border-[#eaecf0] hover:bg-[#f9fafb]" style={{ background: record.ordinal === item.ordinal ? '#eff4ff' : undefined }}>
                    <td className="px-3 py-2 font-medium">{item.ordinal}</td><td>{item.domain}</td><td className={item.semantic_status === 'type_checked' ? 'text-[#067647]' : 'text-[#d92d20]'}>{item.semantic_status}</td><td>{item.objects.length}</td><td>{item.morphisms.length}</td><td>{item.constraints.length}</td><td>{item.lift_certificates.length}</td><td>{item.answer_available ? 'あり' : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="border-b border-[#d8dee9] py-8">
          <div className="mb-5 flex flex-wrap items-baseline justify-between gap-3"><h2 className="text-xl font-medium">問題{record.ordinal}</h2><p className="text-xs text-[#667085]">{record.domain} · {record.semantic_status} · Lift {record.lift_certificates.length}</p></div>
          <div className="mb-7 max-w-4xl text-sm leading-8 text-[#344054]"><MathText text={record.statement_tex} /></div>
          <SemanticFlow record={record} />
          {record.answer_semantic_delta && (
            <div className="mt-5 border-t border-[#d8dee9] pt-4">
              <p className="text-xs font-medium text-[#344054]">解答で初めて現れた数学的操作</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {record.answer_semantic_delta.latent_morphisms.map(name => (
                  <span key={name} className="border border-[#b2ccff] bg-[#eff4ff] px-2 py-1 text-[11px] text-[#1849a9]">{name}</span>
                ))}
                {!record.answer_semantic_delta.latent_morphisms.length && <span className="text-xs text-[#667085]">差分抽出なし</span>}
              </div>
            </div>
          )}
          {!!record.warnings.length && <div className="mt-4 border-l-2 border-[#d92d20] pl-3 text-xs leading-6 text-[#7a271a]">{record.warnings.join(' / ')}</div>}
        </section>

        <section className="py-8">
          <div className="mb-5"><h2 className="text-lg font-medium">解答の依存グラフ</h2><p className="mt-1 text-xs text-[#667085]">変数定義の参照と「よって・したがって」等の接続語から抽出。論理的正しさの形式証明ではありません。</p></div>
          <AnswerDependencyGraph record={record} />
        </section>

        <section className="border-t border-[#d8dee9] py-8">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs font-medium text-[#067647]">MOTIF-GUIDED GENERATION</p>
              <h2 className="mt-2 text-2xl font-medium">修正後に生成した検証済み候補</h2>
              <p className="mt-2 max-w-3xl text-sm leading-7 text-[#475467]">自作解答から回収した「表現変換・分岐・合流」を採用条件にした最初の候補です。数値差し替えではなく、二次方程式を格子領域へ移し、面積と制限平均の2観測へ分岐させています。</p>
            </div>
            <div className="grid grid-cols-3 gap-4 text-center text-xs">
              <div><p className="text-[#667085]">節点</p><strong className="mt-1 block text-xl">{generated.proof_graph_certificate.node_count}</strong></div>
              <div><p className="text-[#667085]">合流</p><strong className="mt-1 block text-xl">{generated.proof_graph_certificate.merge_count}</strong></div>
              <div><p className="text-[#667085]">終端</p><strong className="mt-1 block text-xl">{generated.proof_graph_certificate.terminal_count}</strong></div>
            </div>
          </div>

          <div className="mt-6 border-y border-[#d8dee9] bg-white px-4 py-5 text-sm leading-8 text-[#344054]">
            <MathText text={generated.statement_tex} />
          </div>

          <div className="mt-5 overflow-x-auto pb-2">
            <div className="flex min-w-max items-center">
              {generated.lift_certificate.morphism_chain.map((name, index) => (
                <div key={name} className="flex items-center">
                  <div className="w-40 border-l-2 border-[#6941c6] bg-white px-3 py-3 text-xs text-[#344054]">{name}</div>
                  {index < generated.lift_certificate.morphism_chain.length - 1 && <span className="px-2 text-[#98a2b3]">→</span>}
                </div>
              ))}
            </div>
          </div>

          <div className="mt-5 grid gap-4 border-t border-[#d8dee9] pt-5 text-sm sm:grid-cols-4">
            <div><p className="text-xs text-[#667085]">厳密解</p><p className="mt-1 font-medium">{generated.answer_exact.join(' , ')}</p></div>
            <div><p className="text-xs text-[#667085]">独立数値確認 n=1000</p><p className="mt-1 font-medium">{generated.verification.finite_check.proportion.toFixed(6)} / {generated.verification.finite_check.restricted_average.toFixed(6)}</p></div>
            <div><p className="text-xs text-[#667085]">証明DAG</p><p className="mt-1 font-medium text-[#067647]">{generated.proof_graph_certificate.reason}</p></div>
            <div><p className="text-xs text-[#667085]">通常パーサへの再入力</p><p className="mt-1 font-medium text-[#067647]">{generated.verification.semantic_chain_check.passed ? '7 / 7 射を再抽出' : '失敗'}</p></div>
          </div>
        </section>
      </div>
    </main>
  )
}
