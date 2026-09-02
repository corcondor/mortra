import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { homedir } from 'node:os'
import { dirname, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

import katex from 'katex'

const require = createRequire(import.meta.url)

function loadChromium() {
  try {
    return require('playwright-core').chromium
  } catch {
    const bundledPlaywright = resolve(
      homedir(),
      '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core',
    )
    return require(bundledPlaywright).chromium
  }
}

const chromium = loadChromium()

function argument(name) {
  const index = process.argv.indexOf(name)
  return index >= 0 ? process.argv[index + 1] : undefined
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
}

function math(tex, displayMode = false) {
  try {
    return katex.renderToString(tex, { displayMode, throwOnError: true, strict: false })
  } catch {
    return `<code>${escapeHtml(tex)}</code>`
  }
}

function mixedTex(value) {
  const source = String(value)
  const pattern = /\\\[([\s\S]*?)\\\]|\\\(([\s\S]*?)\\\)/g
  let cursor = 0
  let html = ''
  for (const match of source.matchAll(pattern)) {
    const index = match.index ?? 0
    html += escapeHtml(source.slice(cursor, index)).replaceAll('\n', '<br>')
    html += math(match[1] ?? match[2], Boolean(match[1]))
    cursor = index + match[0].length
  }
  html += escapeHtml(source.slice(cursor)).replaceAll('\n', '<br>')
  return html
}

function inlineContent(value) {
  const source = String(value)
  if (!/\\[A-Za-z]+|[_^]/.test(source) || /\\\(|\\\[/.test(source)) return mixedTex(source)
  return math(source)
}

function record(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {}
}

function stringList(value) {
  return Array.isArray(value) ? value.filter(item => typeof item === 'string' && item.trim()) : []
}

function diagramFor(card) {
  const source = record(card.diagram)
  const nodes = stringList(source.nodes)
  return {
    title: typeof source.title === 'string' && source.title.trim()
      ? source.title.trim()
      : '数学構造を一つの問いへ写す',
    caption: typeof source.caption === 'string' ? source.caption.trim() : '',
    nodes: nodes.length >= 3 ? nodes : stringList(card.morphismChain),
  }
}

function domainLabel(domain) {
  const known = {
    algebraic_geometry: 'ALGEBRA / ELIMINATION',
    complex_algebra: 'COMPLEX ALGEBRA / ORBITS',
    geometry: 'GEOMETRY / CONSTRUCTION',
    number_theory: 'NUMBER THEORY / STRUCTURE',
    probability: 'PROBABILITY / EXPECTATION',
    calculus: 'CALCULUS / ANALYSIS',
  }
  return known[domain] ?? String(domain || 'MATHEMATICS').replaceAll('_', ' / ').toUpperCase()
}

function graphNode(label, index, className = '') {
  return `<div class="graph-node ${className}"><span>${String(index + 1).padStart(2, '0')}</span><div>${inlineContent(label)}</div></div>`
}

function morphismDiagram(card) {
  const diagram = diagramFor(card)
  const sources = diagram.nodes.slice(0, 2)
  const flow = diagram.nodes.slice(2)
  return `<div class="diagram-heading"><span>EXECUTABLE DIAGRAM</span><b>${escapeHtml(diagram.title)}</b></div>
    <div class="graph-canvas" role="img" aria-label="${escapeHtml(diagram.title)}">
      <div class="source-bank">${sources.map((node, index) => graphNode(node, index, 'source-node')).join('')}</div>
      <div class="merge-rail" aria-hidden="true"><i></i><i></i><strong>→</strong></div>
      <div class="flow-bank">${flow.map((node, index) => graphNode(node, index + sources.length, 'flow-node')).join('')}</div>
    </div>
    ${diagram.caption ? `<p class="diagram-caption">${mixedTex(diagram.caption)}</p>` : ''}`
}

function roadmapFor(card) {
  const explicit = stringList(card.proofRoadmap)
  return explicit.length ? explicit : stringList(card.morphismChain)
}

function shell({ card, kind, orientation, katexCss, generatedDate }) {
  const isProblem = kind === 'problem'
  const isPortrait = orientation === 'portrait'
  const dimensions = isPortrait ? { width: 1080, height: 1350 } : { width: 1600, height: 900 }
  const diagram = diagramFor(card)
  const roadmap = roadmapFor(card)
  const titleClass = diagram.title.length > 24 ? 'long-title' : ''
  const statementClass = card.statement.length > 260 ? 'dense-copy' : card.statement.length > 175 ? 'medium-copy' : ''
  const solutionClass = card.solution.length > 320 ? 'dense-solution' : ''
  const answerMath = math(card.answer, true)
  const roadmapRows = roadmap.map((step, index) => `<div class="proof-row"><span>${String(index + 1).padStart(2, '0')}</span><p>${mixedTex(step)}</p></div>`).join('')
  const content = isProblem
    ? `<main class="problem-layout">
        <section class="statement ${statementClass}">
          <p class="section-label">${escapeHtml(domainLabel(card.domain))}</p>
          <h1 class="${titleClass}">${escapeHtml(diagram.title)}</h1>
          <div class="problem-text">${mixedTex(card.statement)}</div>
        </section>
        <section class="diagram">${morphismDiagram(card)}</section>
      </main>`
    : `<main class="solution-layout">
        <section class="solution-summary ${solutionClass}">
          <p class="section-label">EXACT ANSWER / REPLAYABLE PROOF</p>
          <h1>答えと証明経路</h1>
          <div class="answer">${answerMath}</div>
          <div class="solution-text">${mixedTex(card.solution)}</div>
        </section>
        <section class="proof"><div class="proof-heading"><span>PROOF ROADMAP</span><b>${roadmap.length} steps</b></div>
          <div class="proof-grid">${roadmapRows}</div>
          <div class="verification"><span>VERIFIED</span>${escapeHtml(card.verificationMethod ?? 'exact symbolic replay')}</div>
        </section>
      </main>`
  return `<!doctype html><html lang="ja"><head><meta charset="utf-8"><style>${katexCss}
    :root{color-scheme:dark}*{box-sizing:border-box}html,body{margin:0;width:${dimensions.width}px;height:${dimensions.height}px;overflow:hidden;background:#040608;color:#f5f7f8}
    body{font-family:"Yu Gothic UI","Yu Gothic","Hiragino Kaku Gothic ProN",sans-serif;letter-spacing:0}
    .frame{position:relative;width:100%;height:100%;padding:${isPortrait ? '64px 64px 56px' : '48px 70px 42px'};background:#040608}
    .frame:before{content:"";position:absolute;inset:18px;border:1px solid #2b343a;pointer-events:none}
    header{display:flex;align-items:center;justify-content:space-between;height:56px;border-bottom:1px solid #2b343a;padding-bottom:20px}
    .brand{display:flex;align-items:center;gap:14px;font-weight:700;font-size:24px}.mark{width:35px;height:35px;border:1px solid #6ee7f2;display:grid;place-items:center;color:#6ee7f2;font-family:Georgia,serif;font-size:19px}
    .serial{font-family:Consolas,monospace;color:#8c9aa3;font-size:15px}.serial strong{color:#6ee7f2;font-weight:500}
    main{position:relative;height:calc(100% - 116px)}
    .problem-layout{display:grid;grid-template-columns:${isPortrait ? '1fr' : '0.88fr 1.12fr'};grid-template-rows:${isPortrait ? '0.84fr 1.16fr' : '1fr'};gap:${isPortrait ? '12px' : '54px'};align-items:center}
    .statement{align-self:center}.section-label{font-family:Consolas,monospace;color:#6ee7f2;font-size:${isPortrait ? '16px' : '14px'};margin:0 0 22px}
    h1{font-size:${isPortrait ? '54px' : '55px'};line-height:1.2;margin:0 0 ${isPortrait ? '30px' : '28px'};font-weight:680;letter-spacing:0;max-width:14em}.long-title{font-size:${isPortrait ? '45px' : '46px'}}
    .problem-text{font-size:${isPortrait ? '28px' : '24px'};line-height:1.86;color:#d8dfe3}.medium-copy .problem-text{font-size:${isPortrait ? '25px' : '21px'}}.dense-copy .problem-text{font-size:${isPortrait ? '22px' : '19px'}}.problem-text .katex{font-size:1.03em}.problem-text .katex-display{margin:.65em 0}
    .diagram{min-height:${isPortrait ? '500px' : '590px'};display:flex;flex-direction:column;justify-content:center;border-left:${isPortrait ? '0' : '1px solid #202a30'};padding-left:${isPortrait ? '0' : '42px'}}
    .diagram-heading{display:flex;justify-content:space-between;gap:22px;align-items:baseline;border-bottom:1px solid #2b343a;padding:0 0 18px;margin-bottom:22px}.diagram-heading span,.proof-heading span{font:13px Consolas,monospace;color:#6ee7f2}.diagram-heading b{font-size:${isPortrait ? '20px' : '17px'};font-weight:560;color:#d8dfe3;text-align:right}
    .graph-canvas{display:grid;grid-template-columns:${isPortrait ? '1fr 46px 2.25fr' : '0.82fr 50px 2.2fr'};gap:14px;align-items:center;min-height:${isPortrait ? '330px' : '390px'}}.source-bank{display:grid;gap:16px}.flow-bank{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.graph-node{position:relative;min-height:${isPortrait ? '92px' : '98px'};border:1px solid #34434b;background:#071015;padding:18px 16px;display:flex;flex-direction:column;justify-content:center;gap:9px;overflow:hidden}.graph-node>span{font:12px Consolas,monospace;color:#6ee7f2}.graph-node>div{font-size:${isPortrait ? '18px' : '17px'};line-height:1.38;color:#eef3f5}.source-node{border-color:#5d7882}.flow-node:last-child{border-color:#98f2aa}.merge-rail{height:100%;position:relative;display:grid;place-items:center;color:#6ee7f2;font:25px Consolas,monospace}.merge-rail i{position:absolute;left:0;width:52%;height:1px;background:#46616b}.merge-rail i:first-child{top:30%;transform:rotate(28deg);transform-origin:left}.merge-rail i:nth-child(2){bottom:30%;transform:rotate(-28deg);transform-origin:left}.merge-rail strong{font-weight:400}.diagram-caption{font-size:${isPortrait ? '17px' : '16px'};line-height:1.65;color:#8fa0a8;border-top:1px solid #202a30;margin:22px 0 0;padding-top:17px}
    .solution-layout{display:grid;grid-template-columns:${isPortrait ? '1fr' : '0.92fr 1.08fr'};grid-template-rows:${isPortrait ? '0.9fr 1.1fr' : '1fr'};gap:${isPortrait ? '24px' : '62px'};align-items:center}.solution-summary{align-self:center}
    .answer{border-top:1px solid #6ee7f2;border-bottom:1px solid #2b343a;padding:${isPortrait ? '24px 0' : '24px 0'};font-size:${isPortrait ? '21px' : '18px'};overflow:hidden}.answer .katex-display{margin:0;text-align:left}.solution-text{font-size:${isPortrait ? '19px' : '16px'};line-height:1.72;color:#b9c4c9;margin-top:22px}.dense-solution .solution-text{font-size:${isPortrait ? '17px' : '14px'}}.solution-text .katex-display{margin:.45em 0;text-align:left}
    .proof{border-top:1px solid #2b343a}.proof-heading{display:flex;justify-content:space-between;padding:18px 0;border-bottom:1px solid #2b343a}.proof-heading b{font:13px Consolas,monospace;color:#8c9aa3;font-weight:400}.proof-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));column-gap:24px}.proof-row{display:grid;grid-template-columns:40px 1fr;gap:10px;padding:${isPortrait ? '16px 0' : '17px 0'};border-bottom:1px solid #202a30;min-height:${isPortrait ? '74px' : '80px'}}.proof-row>span{font:13px Consolas,monospace;color:#6ee7f2}.proof-row p{font-size:${isPortrait ? '17px' : '15px'};line-height:1.5;color:#c4cdd1;margin:0}.verification{margin-top:18px;font-size:${isPortrait ? '15px' : '13px'};line-height:1.5;color:#84939a}.verification span{color:#98f2aa;font:12px Consolas,monospace;margin-right:16px}
    footer{position:absolute;left:${isPortrait ? '64px' : '70px'};right:${isPortrait ? '64px' : '70px'};bottom:${isPortrait ? '46px' : '34px'};display:flex;justify-content:space-between;align-items:center;color:#8c9aa3;font:14px Consolas,monospace}footer strong{color:#98f2aa;font-weight:500}
  </style></head><body><div class="frame">
    <header><div class="brand"><span class="mark">M</span>MORTRA</div><div class="serial"><strong>GENERATED + VERIFIED</strong> / ${escapeHtml(generatedDate)}</div></header>
    ${content}
    <footer><span>NO STORED ANSWER · NO LLM IN GENERATION</span><strong>mortra.ai</strong></footer>
  </div></body></html>`
}

const reportPath = resolve(argument('--report') ?? 'artifacts/benchmarks/runtime-structural-probes-20260903.json')
const requestedCaseId = argument('--case')
const requestedFamily = argument('--family')
const outputDirectory = resolve(argument('--out') ?? 'artifacts/social/mortra-generated-problem-20260903')
const report = JSON.parse(await readFile(reportPath, 'utf8'))
const eligible = report.cases
  .flatMap(probe => probe.cards.map(card => ({ ...card, caseId: probe.id })))
  .filter(card => card.hasDiagram
    && card.exactBackend
    && card.independentCheck
    && card.completeParentProof
    && !card.registeredCompositeUsed)
  .filter(card => !requestedCaseId || card.caseId === requestedCaseId)
  .filter(card => !requestedFamily || card.family === requestedFamily)
  .sort((left, right) => right.difficulty - left.difficulty || left.id.localeCompare(right.id))
const card = eligible[0]
if (!card) throw new Error(`no eligible card found for ${requestedCaseId ?? '*'} / ${requestedFamily ?? '*'}`)
if (!card.exactBackend || !card.independentCheck || !card.completeParentProof || card.registeredCompositeUsed) {
  throw new Error('the selected card is not eligible for publication')
}

await mkdir(outputDirectory, { recursive: true })
const katexCssPath = resolve('node_modules/katex/dist/katex.min.css')
let katexCss = await readFile(katexCssPath, 'utf8')
const katexBase = pathToFileURL(dirname(katexCssPath)).href.replace(/\/$/, '')
katexCss = katexCss.replaceAll('url(fonts/', `url(${katexBase}/fonts/`)
const executablePath = process.env.CHROME_PATH ?? 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
const browser = await chromium.launch({ executablePath, headless: true, args: ['--disable-dev-shm-usage'] })
const outputs = []
const generatedDate = new Intl.DateTimeFormat('sv-SE', {
  timeZone: 'Asia/Tokyo',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
}).format(new Date()).replaceAll('-', '.')

try {
  for (const target of [
    { name: 'instagram-problem.png', kind: 'problem', orientation: 'portrait', width: 1080, height: 1350 },
    { name: 'instagram-solution.png', kind: 'solution', orientation: 'portrait', width: 1080, height: 1350 },
    { name: 'x-problem.png', kind: 'problem', orientation: 'landscape', width: 1600, height: 900 },
    { name: 'x-solution.png', kind: 'solution', orientation: 'landscape', width: 1600, height: 900 },
  ]) {
    const context = await browser.newContext({ viewport: { width: target.width, height: target.height } })
    const page = await context.newPage()
    const runtimeErrors = []
    page.on('pageerror', error => runtimeErrors.push(error.message))
    await page.setContent(shell({ card, kind: target.kind, orientation: target.orientation, katexCss, generatedDate }), {
      waitUntil: 'domcontentloaded',
      timeout: 15_000,
    })
    await page.waitForTimeout(750)
    const overflow = await page.evaluate(() => ({
      width: document.documentElement.scrollWidth,
      height: document.documentElement.scrollHeight,
      replacementCharacters: (document.body.innerText.match(/\uFFFD/g) ?? []).length,
    }))
    if (runtimeErrors.length || overflow.width !== target.width || overflow.height !== target.height || overflow.replacementCharacters) {
      throw new Error(`${target.name} failed layout audit: ${JSON.stringify({ runtimeErrors, overflow })}`)
    }
    const outputPath = resolve(outputDirectory, target.name)
    await page.screenshot({ path: outputPath })
    outputs.push({ path: outputPath, width: target.width, height: target.height, ...overflow })
    await context.close()
  }
} finally {
  await browser.close()
}

const manifest = {
  schema: 1,
  generatedAt: new Date().toISOString(),
  sourceReport: reportPath,
  caseId: card.caseId,
  family: card.family,
  cardId: card.id,
  exactBackend: card.exactBackend,
  independentCheck: card.independentCheck,
  completeParentProof: card.completeParentProof,
  registeredCompositeUsed: card.registeredCompositeUsed,
  statement: card.statement,
  answer: card.answer,
  domain: card.domain,
  morphismChain: card.morphismChain,
  diagram: card.diagram,
  proofRoadmap: card.proofRoadmap,
  outputs,
}
await writeFile(resolve(outputDirectory, 'manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`, 'utf8')
console.log(JSON.stringify(manifest, null, 2))
