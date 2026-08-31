import { mkdir, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'

import { chromium } from 'playwright-core'

const baseUrl = process.argv[2] ?? 'http://127.0.0.1:3020/ja'
const outputDirectory = resolve(
  process.argv[3] ?? 'artifacts/test-results/difficult-problem-generation-ui-20260901',
)
const executablePath = process.env.CHROME_PATH ??
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'

await mkdir(outputDirectory, { recursive: true })

const browser = await chromium.launch({
  executablePath,
  headless: true,
  args: ['--disable-dev-shm-usage'],
})

async function verifyViewport(name, viewport) {
  const context = await browser.newContext({ viewport })
  const page = await context.newPage()
  const runtimeErrors = []
  page.on('console', message => {
    if (message.type() === 'error') runtimeErrors.push(message.text())
  })
  page.on('pageerror', error => runtimeErrors.push(error.message))

  await page.goto(baseUrl, { waitUntil: 'domcontentloaded', timeout: 60_000 })
  await page.getByLabel('問題Aを全問題.texから選択').selectOption('fullproblem-034')
  await page.getByLabel('問題Bを全問題.texから選択').selectOption('fullproblem-090')
  await page.getByRole('button', { name: '融合問題を生成', exact: true }).click()
  await page.getByText('生成完了', { exact: true }).waitFor({ timeout: 60_000 })

  const requiredTexts = [
    { text: 'Pell方程式', exact: false },
    { text: '親問題への依存', exact: false },
    { text: '2件の親問題を最終目標まで逆追跡しました。', exact: true },
    { text: '未使用の条件は0件です。', exact: true },
  ]
  const visible = {}
  for (const requirement of requiredTexts) {
    const locator = page.getByText(requirement.text, { exact: requirement.exact })
    visible[requirement.text] = await locator.count() > 0
  }

  const layout = await page.evaluate(() => ({
    viewportWidth: window.innerWidth,
    documentWidth: document.documentElement.scrollWidth,
    bodyWidth: document.body.scrollWidth,
  }))
  const generatedDiagram = page.getByRole('img', {
    name: 'Pell方程式の解をべき和の指数にする',
    exact: true,
  })
  const diagramLayout = await generatedDiagram.evaluate(element => {
    const host = element.getBoundingClientRect()
    const states = [...element.querySelectorAll('svg circle')].map(node => {
      const rect = node.getBoundingClientRect()
      return { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom }
    })
    return {
      stateCount: states.length,
      allStatesWithinBounds: states.every(state =>
        state.left >= host.left - 1
        && state.right <= host.right + 1
        && state.top >= host.top - 1
        && state.bottom <= host.bottom + 1,
      ),
    }
  })
  const screenshotPath = resolve(outputDirectory, `${name}.png`)
  await page.screenshot({ path: screenshotPath, fullPage: true })
  const artifactScreenshotPath = resolve(outputDirectory, `${name}-generated-problem.png`)
  await page
    .getByText('生成監査', { exact: true })
    .locator('xpath=ancestor::article[1]')
    .screenshot({ path: artifactScreenshotPath })
  const diagramScreenshotPath = resolve(outputDirectory, `${name}-generated-diagram.png`)
  await generatedDiagram.screenshot({ path: diagramScreenshotPath })
  await context.close()

  return {
    name,
    viewport,
    screenshotPath,
    artifactScreenshotPath,
    diagramScreenshotPath,
    visible,
    noHorizontalOverflow:
      layout.documentWidth <= layout.viewportWidth && layout.bodyWidth <= layout.viewportWidth,
    layout,
    diagramLayout,
    runtimeErrors,
  }
}

try {
  const results = [
    await verifyViewport('desktop', { width: 1440, height: 1000 }),
    await verifyViewport('mobile', { width: 390, height: 844 }),
  ]
  const passed = results.every(result =>
    Object.values(result.visible).every(Boolean)
    && result.noHorizontalOverflow
    && result.diagramLayout.stateCount >= 2
    && result.diagramLayout.allStatesWithinBounds
    && result.runtimeErrors.length === 0,
  )
  const report = { schema: 1, measuredAt: new Date().toISOString(), baseUrl, passed, results }
  await writeFile(resolve(outputDirectory, 'report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  process.stdout.write(`${JSON.stringify(report, null, 2)}\n`)
  if (!passed) process.exitCode = 1
} finally {
  await browser.close()
}
