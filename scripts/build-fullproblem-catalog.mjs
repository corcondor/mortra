import { createHash } from 'node:crypto'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'

function argument(name) {
  const index = process.argv.indexOf(name)
  return index >= 0 ? process.argv[index + 1] : undefined
}

function extractItemboxProblems(source) {
  const answerBoundary = source.indexOf('\\fbox{解答編}')
  const problemSection = answerBoundary >= 0 ? source.slice(0, answerBoundary) : source
  return Array.from(problemSection.matchAll(
    /\\begin\{itembox\}\[l\]\{([^{}]+)\}([\s\S]*?)\\end\{itembox\}/g,
  )).map((match, index) => ({
    ordinal: index + 1,
    label: match[1].trim(),
    statement: match[2].trim(),
  }))
}

function section(source, title, nextTitles) {
  const marker = `\\section*{${title}}`
  const start = source.indexOf(marker)
  if (start < 0) return ''
  const bodyStart = start + marker.length
  const ends = nextTitles
    .map(next => source.indexOf(`\\section*{${next}}`, bodyStart))
    .filter(index => index >= 0)
  const end = ends.length ? Math.min(...ends) : source.indexOf('\\end{document}', bodyStart)
  return source.slice(bodyStart, end >= 0 ? end : source.length).trim()
}

const texPath = argument('--tex')
const summaryPath = argument('--summary')
const outputPath = argument('--out')
if (!texPath || !summaryPath || !outputPath) {
  throw new Error('usage: node scripts/build-fullproblem-catalog.mjs --tex <全問題.tex> --summary <summary.json> --out <catalog.json>')
}

const resolvedTex = resolve(texPath)
const source = await readFile(resolvedTex, 'utf8')
const summary = JSON.parse(await readFile(resolve(summaryPath), 'utf8'))
const problems = extractItemboxProblems(source)
const records = new Map((summary.records ?? []).map(record => [Number(record.ordinal), record]))
const entries = []

for (const problem of problems) {
  const record = records.get(problem.ordinal)
  const verified = record?.status === 'verified' && record.answer_tex && record.tex
  let solutionTex = null
  if (verified) {
    const caseSource = await readFile(resolve(String(record.tex)), 'utf8')
    solutionTex = section(caseSource, '解答', ['証明の経路', '検証記録']) || null
  }
  entries.push({
    id: `fullproblem-${String(problem.ordinal).padStart(3, '0')}`,
    ordinal: problem.ordinal,
    label: problem.label,
    statement: problem.statement,
    status: verified ? 'verified' : 'unresolved',
    familyId: verified ? String(record.family_id) : null,
    answerTex: verified ? String(record.answer_tex) : null,
    solutionTex,
    certificate: verified ? {
      verified: true,
      id: `mortra-fullproblem-proof-${String(problem.ordinal).padStart(3, '0')}`,
      method: String(record.family_id),
    } : null,
  })
}

const catalog = {
  schema: 1,
  sourceLabel: '全問題.tex',
  sourceSha256: createHash('sha256').update(source).digest('hex'),
  problemCount: entries.length,
  verifiedCount: entries.filter(entry => entry.status === 'verified').length,
  entries,
}
await mkdir(dirname(resolve(outputPath)), { recursive: true })
await writeFile(resolve(outputPath), `${JSON.stringify(catalog, null, 2)}\n`, 'utf8')
process.stdout.write(JSON.stringify({
  output: resolve(outputPath),
  problemCount: catalog.problemCount,
  verifiedCount: catalog.verifiedCount,
}, null, 2))
