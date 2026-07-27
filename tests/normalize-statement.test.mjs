/**
 * lib/utils.ts の normalizeStatement を実データ相当の入力で検証する。
 *
 * 過去問 .tex 由来の問題文は小問を \begin{description}\item[(1)] で書いており、
 * 数式の外なので KaTeX に渡らず生のまま画面に残っていた（一覧上位600問のうち
 * 381問が該当）。ここではその代表例が消えることを確認する。
 *
 * tsc で lib/utils.ts を JS へ落としてから読み込む。
 */
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import test from 'node:test'
import { fileURLToPath, pathToFileURL } from 'node:url'

const repoRoot = dirname(dirname(fileURLToPath(import.meta.url)))

const outDir = mkdtempSync(join(tmpdir(), 'sakumon-utils-'))
const source = readFileSync(new URL('../lib/utils.ts', import.meta.url), 'utf8')
// 型だけの import を落として単独でコンパイルできるようにする
const standalone = source.replace(/^import[^\n]*\n/gm, '')
const entry = join(outDir, 'utils.ts')
writeFileSync(entry, standalone, 'utf8')
// npx は Windows で .cmd を spawn できないので tsc を直接 node で走らせる
execFileSync(
  process.execPath,
  [
    join(repoRoot, 'node_modules', 'typescript', 'bin', 'tsc'),
    entry,
    '--target', 'es2021',
    '--module', 'esnext',
    '--moduleResolution', 'bundler',
    '--skipLibCheck',
  ],
  { cwd: repoRoot, stdio: 'pipe' },
)
const compiled = join(outDir, 'utils.js')
const { normalizeStatement } = await import(pathToFileURL(compiled).href)

test('description 環境の小問ラベルが日本語の見出しになる', () => {
  const input =
    'とする。\n\\begin{description}\n\\item[(1)] $a$ を求めよ。\n' +
    '\\item[(2)] $b$ を求めよ。\n\\end{description}'
  const out = normalizeStatement(input)
  assert.ok(!out.includes('\\item'), '\\item が残っている')
  assert.ok(!out.includes('\\begin{description}'), '環境が残っている')
  assert.ok(out.includes('(1) '), '(1) が出ていない')
  assert.ok(out.includes('(2) '), '(2) が出ていない')
})

test('数式の中身は書き換えない', () => {
  const input = '\\[ \\begin{pmatrix} 1 & a \\\\ 0 & 1 \\end{pmatrix} \\]'
  assert.equal(normalizeStatement(input), input)
})

test('\\ding は10進でも16進でも丸数字になる', () => {
  assert.equal(normalizeStatement('\\ding{172}'), '①')
  assert.equal(normalizeStatement('\\ding{"AC}'), '①')
  assert.equal(normalizeStatement('\\ding{"AE}'), '③')
})

test('版面指示と文字列 \\n が消える', () => {
  const out = normalizeStatement('\\noindent A\\medskip\\nB\\hspace{1zw}C')
  assert.ok(!out.includes('\\noindent'))
  assert.ok(!out.includes('\\medskip'))
  assert.ok(!out.includes('\\hspace'))
  assert.ok(!/\\n(?![A-Za-z])/.test(out))
})

test('ルビは親文字だけ残る', () => {
  assert.equal(normalizeStatement('\\ruby{正三角形}{せいさんかくけい}'), '正三角形')
})
