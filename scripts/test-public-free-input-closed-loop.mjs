import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'

import { chromium } from 'playwright-core'

const baseUrl = process.argv[2] ?? 'https://mortra.ai/ja'
const outputDirectory = resolve(
  process.argv[3] ?? 'artifacts/test-results/public-free-input-closed-loop-20260901',
)
const executablePath = process.env.CHROME_PATH
  ?? 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
const caseFilter = process.env.MORTRA_CASES
  ? new Set(process.env.MORTRA_CASES.split(',').map(value => value.trim()).filter(Boolean))
  : null
const caseFile = process.env.MORTRA_CASE_FILE
  ? resolve(process.env.MORTRA_CASE_FILE)
  : null
const viewport = process.env.MORTRA_VIEWPORT === 'mobile'
  ? { width: 390, height: 844 }
  : { width: 1440, height: 1000 }

const builtInCases = [
  {
    id: 'auto-a-single',
    mode: 'auto',
    expected: 'resolved',
    a: '実数 x, y が 2x+y=11, x-y=1 を満たすとき、x+3y を求めよ。',
  },
  {
    id: 'auto-b-single',
    mode: 'auto',
    expected: 'resolved',
    b: '方程式 x^2-3x-7=0 の二つの根を α, β とするとき、α^3+β^3 を求めよ。',
  },
  {
    id: 'auto-two-fusion',
    mode: 'auto',
    expected: 'resolved',
    a: '方程式 $x^2-5x+6=0$ を解け。',
    b: '方程式 $y^2-y-1=0$ の根を考える。',
  },
  {
    id: 'linear-single',
    mode: 'solve',
    expected: 'resolved',
    a: '実数 x, y が 2x+y=11, x-y=1 を満たすとき、x+3y を求めよ。',
  },
  {
    id: 'polynomial-single',
    mode: 'solve',
    expected: 'resolved',
    a: '方程式 x^2-3x-7=0 の二つの根を α, β とするとき、α^3+β^3 を求めよ。',
  },
  {
    id: 'calculus-draw',
    mode: 'draw',
    expected: 'resolved',
    requireDiagramWhenResolved: true,
    a: '関数 f(x)=x^3-3x の増減、極大値、極小値を求め、グラフの概形を描け。',
  },
  {
    id: 'geometry-draw',
    mode: 'draw',
    expected: 'resolved',
    requireDiagramWhenResolved: true,
    a: '座標平面上の三角形 A(0,0), B(6,0), C(2,4) の外心と内心を求め、解答に必要な補助線を含む図を描け。',
  },
  {
    id: 'linear-fusion',
    mode: 'fusion',
    expected: 'resolved',
    a: '実数 x, y が 2x+y=11, x-y=1 を満たす。',
    b: '実数 u, v が 3u-v=7, u+2v=8 を満たす。',
  },
  {
    id: 'polynomial-fusion',
    mode: 'fusion',
    expected: 'resolved',
    a: '実数 α は α^2-3α-7=0 を満たす。',
    b: '実数 β は β^3+2β-5=0 を満たす。',
  },
  {
    id: 'probability-state',
    mode: 'draw',
    expected: 'resolved',
    requireDiagramWhenResolved: true,
    a: '公平な硬貨を繰り返し投げ、表が2回連続した時点で終了する。終了までの投数の期待値を求め、状態遷移図を用いて説明せよ。',
  },
  {
    id: 'hard-integral-inequality',
    mode: 'solve',
    expected: 'resolved',
    a: 'I=\\int_0^{\\pi/2}\\{\\cos(\\cos x+\\sin x)+\\sin(\\cos x+\\sin x)\\}\\,dx とする。0<I<2 を証明せよ。',
  },
]

const cases = caseFile
  ? JSON.parse(await readFile(caseFile, 'utf8'))
  : builtInCases
if (!Array.isArray(cases) || cases.some(testCase => (
  typeof testCase?.id !== 'string'
  || !['auto', 'solve', 'fusion', 'draw'].includes(testCase?.mode)
  || (typeof testCase?.a !== 'string' && typeof testCase?.b !== 'string')
  || (testCase.mode === 'fusion' && typeof testCase?.b !== 'string')
))) {
  throw new TypeError('MORTRA_CASE_FILE must contain an array of valid auto, solve, fusion, or draw cases')
}

const selectedCases = caseFilter ? cases.filter(testCase => caseFilter.has(testCase.id)) : cases
const replacementCharacter = /\uFFFD/
const mojibakePattern = /(?:Ã.|â.|縺.|繝.|譁.|蜿.|莨.)/

await mkdir(outputDirectory, { recursive: true })

const browser = await chromium.launch({
  executablePath,
  headless: true,
  args: ['--disable-dev-shm-usage'],
})

function commandFor(mode) {
  if (mode === 'auto') return null
  if (mode === 'draw') return '/draw'
  if (mode === 'solve') return '/solve'
  return '/combine'
}

function buttonFor(testCase) {
  const { mode } = testCase
  if (mode === 'auto') return testCase.a?.trim() && testCase.b?.trim() ? '融合問題を生成' : '問題を解く'
  if (mode === 'draw') return '解いて図を作る'
  if (mode === 'solve') return '問題を解く'
  return '融合問題を生成'
}

async function waitForOutcome(page, timeoutMs = 150_000) {
  const startedAt = Date.now()
  while (Date.now() - startedAt < timeoutMs) {
    const snapshot = await page.locator('body').innerText().catch(() => '')
    const artifactCount = await page.locator('article[data-artifact-kind]').count().catch(() => 0)
    const jobId = await page.evaluate(() => window.localStorage.getItem('mortra-public-active-job'))
    if (artifactCount > 0 && (snapshot.includes('解答完了') || snapshot.includes('生成完了'))) {
      return { outcome: 'resolved', snapshot, jobId: null }
    }
    if (jobId || snapshot.includes('長時間の探索へ移行しました')) {
      return { outcome: 'queued', snapshot, jobId }
    }
    const phaseCodes = await page.locator('section[aria-label="生成の進行状況"] code').allTextContents().catch(() => [])
    if (phaseCodes.includes('error')) return { outcome: 'error', snapshot, jobId: null }
    await page.waitForTimeout(1000)
  }
  return {
    outcome: 'timeout',
    snapshot: await page.locator('body').innerText().catch(() => ''),
    jobId: await page.evaluate(() => window.localStorage.getItem('mortra-public-active-job')),
  }
}

async function runCase(testCase) {
  const context = await browser.newContext({ viewport })
  const page = await context.newPage()
  const consoleErrors = []
  const apiResponses = []
  page.on('console', message => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })
  page.on('pageerror', error => consoleErrors.push(error.message))
  page.on('response', response => {
    const url = response.url()
    if (url.includes('/api/solve') || url.includes('/api/mathos-generate') || url.includes('/api/research-start') || url.includes('/api/job-status')) {
      apiResponses.push({ url, status: response.status() })
    }
  })

  const startedAt = Date.now()
  await page.goto(baseUrl, { waitUntil: 'domcontentloaded', timeout: 180_000 })
  const pageIdentity = { url: page.url(), title: await page.title() }

  const requestedCommand = commandFor(testCase.mode)
  if (requestedCommand) {
    const command = page.getByRole('textbox', { name: 'コマンド', exact: true })
    await command.fill(requestedCommand)
    await command.press('Enter')
  }
  if (typeof testCase.a === 'string') await page.locator('#mortra-parent-a').fill(testCase.a)
  if (typeof testCase.b === 'string') await page.locator('#mortra-parent-b').fill(testCase.b)

  const inputRoundTrip = {
    a: typeof testCase.a !== 'string' || await page.locator('#mortra-parent-a').inputValue() === testCase.a,
    b: typeof testCase.b !== 'string' || await page.locator('#mortra-parent-b').inputValue() === testCase.b,
  }

  await page.getByRole('button', { name: buttonFor(testCase), exact: true }).click()
  const outcomeState = await waitForOutcome(page)

  let reconnectedAfterReload = null
  if (outcomeState.outcome === 'queued') {
    const queuedJob = outcomeState.jobId
    await page.reload({ waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(2500)
    const reloadedText = await page.locator('body').innerText()
    const storedAfterReload = await page.evaluate(() => window.localStorage.getItem('mortra-public-active-job'))
    reconnectedAfterReload = Boolean(
      queuedJob
      && storedAfterReload === queuedJob
      && (reloadedText.includes('再接続しました') || reloadedText.includes('探索中') || reloadedText.includes('再開準備中'))
    )
  }

  const bodyText = await page.locator('body').innerText()
  const transcript = await page.locator('[role="log"]').innerText().catch(() => '')
  const phaseCodes = await page.locator('section[aria-label="生成の進行状況"] code').allTextContents().catch(() => [])
  const artifact = page.locator('article[data-artifact-kind]').first()
  const artifactExists = await artifact.count() > 0
  const artifactText = artifactExists ? await artifact.innerText() : ''
  const diagramLabels = artifactExists
    ? await artifact.locator('[role="img"]').evaluateAll(elements => elements.map(element => element.getAttribute('aria-label') ?? ''))
    : []
  const visualStepCount = artifactExists
    ? await artifact.getByRole('button', { name: /^手順 [0-9]+:/ }).count()
    : 0
  const rawMathMarkup = artifactExists
    ? await artifact.evaluate(root => {
      const pattern = /(?:\\(?:sqrt|infty|frac|pi|to|cdot|left|right|operatorname)\b|[_^]\{[^}\n]+\})/
      const matches = new Set()
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
      let node = walker.nextNode()
      while (node) {
        const parent = node.parentElement
        const text = node.textContent?.trim() ?? ''
        if (parent && !parent.closest('.katex, script, style, textarea') && pattern.test(text)) {
          matches.add(text)
        }
        node = walker.nextNode()
      }
      return [...matches]
    })
    : []
  let finalVisualStepSelected = false
  if (artifactExists && visualStepCount > 1) {
    await artifact.getByRole('button', { name: /^手順 [0-9]+:/ }).nth(visualStepCount - 1).click()
    await page.waitForTimeout(250)
    finalVisualStepSelected = true
  }
  const generatedCounter = bodyText.match(/生成した問題\s+(\d+)\s*\/\s*(\d+)/)
  const generatedCount = generatedCounter ? Number(generatedCounter[2]) : (artifactExists ? 1 : 0)
  const verification = {
    verifiedLabel: artifactText.includes('検証済み'),
    hasStatement: artifactText.includes('問題文'),
    hasAnswer: artifactText.includes('答え') && !artifactText.includes('未確定'),
    hasSolution: artifactText.includes('解答・図の読み方') && !artifactText.includes('証明と反例検査が完了するまで'),
    hasCertificate: artifactText.includes('VERIFY'),
    diagramCount: diagramLabels.length,
    diagramLabels,
    visualStepCount,
  }
  const encoding = {
    inputRoundTrip,
    replacementCharacter: replacementCharacter.test(bodyText),
    probableMojibake: mojibakePattern.test(bodyText),
    undefinedLiteral: /\bundefined\b/.test(artifactText),
    rawMathMarkup,
  }
  const horizontalOverflow = await page.evaluate(() => (
    document.documentElement.scrollWidth > document.documentElement.clientWidth + 1
  ))

  const screenshotPath = resolve(outputDirectory, `${testCase.id}.png`)
  if (artifactExists) {
    await artifact.screenshot({
      path: screenshotPath,
      animations: 'disabled',
      timeout: 120_000,
    })
  } else {
    await page.screenshot({
      path: screenshotPath,
      animations: 'disabled',
      timeout: 120_000,
    })
  }

  const outcomeAccepted = testCase.expected === 'resolved'
    ? outcomeState.outcome === 'resolved'
    : ['resolved', 'queued'].includes(outcomeState.outcome)
  const expectedResearchFallback = (
    testCase.expected === 'queued'
    && outcomeState.outcome === 'queued'
    && apiResponses.some(response => response.url.includes('/api/solve') && response.status === 422)
    && apiResponses.some(response => response.url.includes('/api/research-start') && response.status === 202)
  )
  const unexpectedConsoleErrors = consoleErrors.filter(message => !(
    expectedResearchFallback
    && message.includes('Failed to load resource')
    && message.includes('status of 422')
  ))
  const resolvedChecks = outcomeState.outcome !== 'resolved' || (
    verification.verifiedLabel
    && verification.hasStatement
    && verification.hasAnswer
    && verification.hasSolution
    && verification.hasCertificate
    && (!testCase.requireDiagramWhenResolved || verification.diagramCount > 0)
  )
  const expectedTaskMode = testCase.mode === 'fusion'
    || (testCase.mode === 'auto' && Boolean(testCase.a?.trim() && testCase.b?.trim()))
    ? 'fusion'
    : 'solve'
  const routeCorrect = expectedTaskMode === 'fusion'
    ? apiResponses.some(response => response.url.includes('/api/mathos-generate'))
    : apiResponses.some(response => response.url.includes('/api/solve'))
  const passed = Boolean(
    pageIdentity.url.startsWith(baseUrl)
    && pageIdentity.title.includes('MORTRA')
    && inputRoundTrip.a
    && inputRoundTrip.b
    && !encoding.replacementCharacter
    && !encoding.probableMojibake
    && !encoding.undefinedLiteral
    && encoding.rawMathMarkup.length === 0
    && !horizontalOverflow
    && unexpectedConsoleErrors.length === 0
    && outcomeAccepted
    && resolvedChecks
    && routeCorrect
    && (outcomeState.outcome !== 'queued' || reconnectedAfterReload === true)
  )

  await context.close()
  return {
    id: testCase.id,
    mode: testCase.mode,
    expected: testCase.expected,
    passed,
    durationMs: Date.now() - startedAt,
    outcome: outcomeState.outcome,
    jobId: outcomeState.jobId,
    reconnectedAfterReload,
    generatedCount,
    pageIdentity,
    encoding,
    verification,
    finalVisualStepSelected,
    horizontalOverflow,
    phaseCodes,
    transcript,
    bodyTail: bodyText.slice(-2000),
    apiResponses,
    routeCorrect,
    consoleErrors,
    unexpectedConsoleErrors,
    screenshotPath,
  }
}

try {
  const results = []
  for (const testCase of selectedCases) {
    process.stdout.write(`[mortra-qa] ${testCase.id}\n`)
    results.push(await runCase(testCase))
  }
  const report = {
    schema: 1,
    measuredAt: new Date().toISOString(),
    baseUrl,
    viewport,
    passed: results.every(result => result.passed),
    summary: {
      cases: results.length,
      passed: results.filter(result => result.passed).length,
      resolved: results.filter(result => result.outcome === 'resolved').length,
      queued: results.filter(result => result.outcome === 'queued').length,
      failed: results.filter(result => !result.passed).map(result => result.id),
    },
    results,
  }
  await writeFile(resolve(outputDirectory, 'report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  process.stdout.write(`${JSON.stringify(report, null, 2)}\n`)
  if (!report.passed) process.exitCode = 1
} finally {
  await browser.close()
}
