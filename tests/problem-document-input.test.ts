import assert from 'node:assert/strict'
import test from 'node:test'

import {
  MAX_PROBLEM_DOCUMENT_BYTES,
  extractPrimaryProblemText,
  mergeRecognizedProblemLines,
  normalizeRecognizedProblemText,
  pdfTextNeedsFormulaOcr,
  problemDocumentKind,
  validateProblemDocument,
} from '../lib/mortra/problem-document-input'
import { proposeFormulaFallbackBoxes } from '../lib/mortra/problem-formula-ocr'

test('recognized Japanese and TeX text is normalized without changing mathematical structure', () => {
  const text = normalizeRecognizedProblemText('  実数ｘについて、￥frac{ｘ^2}{２}を求めよ。\r\n\r\n\r\n\r\n')
  assert.equal(text, '実数xについて、\\frac{x^2}{2}を求めよ。')
})

test('spaced trigonometric operator names are normalized to standard LaTeX commands', () => {
  const text = normalizeRecognizedProblemText(
    '$\\operatorname{c o s}x+\\operatorname{s i n}x+\\operatorname{t a n}x$',
  )
  assert.equal(text, '$\\cos x+\\sin x+\\tan x$')
})

test('document kind accepts supported MIME types and extensions', () => {
  assert.equal(problemDocumentKind({ name: 'problem.PNG', type: '', size: 10 }), 'image')
  assert.equal(problemDocumentKind({ name: 'problem.bin', type: 'image/webp', size: 10 }), 'image')
  assert.equal(problemDocumentKind({ name: 'problem.PDF', type: '', size: 10 }), 'pdf')
})

test('document validation rejects unsupported, empty and oversized files', () => {
  assert.throws(
    () => validateProblemDocument({ name: 'problem.txt', type: 'text/plain', size: 10 }),
    /PNG、JPEG、WebP、PDF/,
  )
  assert.throws(
    () => validateProblemDocument({ name: 'problem.png', type: 'image/png', size: 0 }),
    /空のファイル/,
  )
  assert.throws(
    () => validateProblemDocument({ name: 'problem.pdf', type: 'application/pdf', size: MAX_PROBLEM_DOCUMENT_BYTES + 1 }),
    /15MB以内/,
  )
})

test('math-heavy PDF text is rendered for formula OCR instead of being flattened', () => {
  assert.equal(pdfTextNeedsFormulaOcr('問題文だけを読み取る。'), false)
  assert.equal(pdfTextNeedsFormulaOcr('∫ π 2 0 { cos x + sin x } dx < 2'), true)
  assert.equal(pdfTextNeedsFormulaOcr('x = 1, y = 2, x + y = 3'), true)
})

test('worked PDF pages contribute only their first displayed problem', () => {
  const result = extractPrimaryProblemText([
    'corcondor',
    '$$\\int_0^1 f(x)\\,dx<2$$',
    '$$I=\\int_0^1 f(x)\\,dx$$',
    '$$I^2\\leq\\int_0^1 f(x)^2\\,dx$$',
  ].join('\n'))

  assert.equal(result.trimmed, true)
  assert.equal(result.text, '$$\\int_0^1 f(x)\\,dx<2$$')
})

test('small uppercase point expressions are proposed for formula recognition', () => {
  const proposals = proposeFormulaFallbackBoxes([
    { text: '内', confidence: 99, bbox: { x0: 0, y0: 0, x1: 20, y1: 30 } },
    { text: 'O', confidence: 90, bbox: { x0: 40, y0: 0, x1: 60, y1: 30 } },
    { text: 'F', confidence: 54, bbox: { x0: 61, y0: 0, x1: 84, y1: 30 } },
  ], 200, 100)

  assert.equal(proposals.length, 1)
  assert.ok(proposals[0].x0 < 40)
  assert.ok(proposals[0].x1 > 84)
})

test('replacement characters are rejected instead of silently submitted', () => {
  assert.throws(
    () => normalizeRecognizedProblemText('x = 1\ufffd2 を求めよ。'),
    /復元できない/,
  )
})

test('split subscripts, ellipses and repeated denominator variables are repaired structurally', () => {
  const text = normalizeRecognizedProblemText([
    '各内角が、ある整数 p $_{1},~p_{2},~\\bullet \\bullet,~p_{6}$ を用いて、',
    '$\\frac{p_{1}} {q}\\pi,\\frac{p_{2}} {q}\\pi$ と表せるよう。な正の整数gの最小値を求めよ。',
  ].join('\n'))

  assert.equal(
    text,
    '各内角が、ある整数 $p_{1},~p_{2},~\\cdots ,~p_{6}$ を用いて、\n$\\frac{p_{1}} {q}\\pi,\\frac{p_{2}} {q}\\pi$ と表せるような正の整数qの最小値を求めよ。',
  )
})

test('geometry center labels constrain confusable OCR symbols in short formulas', () => {
  const text = normalizeRecognizedProblemText(
    '直角三角形の外心をO,内心を1とする. $\\mathrm{o l^{2}}$ の小数部分を求めよ.',
  )

  assert.equal(text, '直角三角形の外心をO,内心をIとする. $OI^{2}$ の小数部分を求めよ.')
})

test('recognized formulas replace formula OCR while preserving surrounding Japanese', () => {
  const text = mergeRecognizedProblemLines([
    {
      text: '3次関数y=f(x)と単位円x2+y2=1が交わる。',
      confidence: 92,
      bbox: { x0: 0, y0: 0, x1: 360, y1: 40 },
      symbols: [
        { text: '3次関数', confidence: 99, bbox: { x0: 0, y0: 0, x1: 70, y1: 40 } },
        { text: 'y=f(x)', confidence: 80, bbox: { x0: 72, y0: 0, x1: 130, y1: 40 } },
        { text: 'と単位円', confidence: 99, bbox: { x0: 132, y0: 0, x1: 210, y1: 40 } },
        { text: 'x2+y2=1', confidence: 72, bbox: { x0: 212, y0: 0, x1: 300, y1: 40 } },
        { text: 'が', confidence: 99, bbox: { x0: 302, y0: 0, x1: 322, y1: 40 } },
        { text: '交わる。', confidence: 99, bbox: { x0: 324, y0: 0, x1: 360, y1: 40 } },
      ],
    },
  ], '', [
    {
      type: 'embedding',
      box: { x0: 70, y0: 0, x1: 131, y1: 40 },
      latex: 'y=f(x)',
      detectionConfidence: 0.95,
      recognitionConfidence: 0.99,
    },
    {
      type: 'embedding',
      box: { x0: 210, y0: 0, x1: 310, y1: 40 },
      latex: 'x^2+y^2=1',
      detectionConfidence: 0.94,
      recognitionConfidence: 0.99,
    },
  ])

  assert.equal(text, '3次関数 $y=f(x)$ と単位円 $x^2+y^2=1$ が交わる。')
})

test('isolated formulas retain display structure and reading order', () => {
  const text = mergeRecognizedProblemLines([
    {
      text: '次を求めよ。',
      confidence: 99,
      bbox: { x0: 0, y0: 0, x1: 100, y1: 30 },
      symbols: [
        { text: '次を求めよ。', confidence: 99, bbox: { x0: 0, y0: 0, x1: 100, y1: 30 } },
      ],
    },
  ], '次を求めよ。', [
    {
      type: 'isolated',
      box: { x0: 30, y0: 50, x1: 260, y1: 100 },
      latex: '\\lim_{n\\to\\infty} a_n',
      detectionConfidence: 0.91,
      recognitionConfidence: 0.98,
    },
  ])

  assert.equal(text, '次を求めよ。\n$$\n\\lim_{n\\to\\infty} a_n\n$$')
})
