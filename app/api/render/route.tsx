import { NextRequest, NextResponse } from 'next/server'
import { ImageResponse } from 'next/og'

export const runtime = 'edge'

const WIDTH = 1600
const HEIGHT = 2000

function asText(value: unknown) {
  return typeof value === 'string' ? value : ''
}

function compact(value: string) {
  return value.replace(/\s+/g, ' ').trim()
}

function clamp(value: string, max: number) {
  const text = compact(value)
  return text.length > max ? `${text.slice(0, max - 3)}...` : text
}

const COMMAND_REPLACEMENTS: Record<string, string> = {
  alpha: 'alpha',
  beta: 'beta',
  gamma: 'gamma',
  delta: 'delta',
  epsilon: 'epsilon',
  varepsilon: 'epsilon',
  zeta: 'zeta',
  eta: 'eta',
  theta: 'theta',
  vartheta: 'theta',
  lambda: 'lambda',
  mu: 'mu',
  nu: 'nu',
  xi: 'xi',
  pi: 'pi',
  rho: 'rho',
  sigma: 'sigma',
  tau: 'tau',
  phi: 'phi',
  varphi: 'phi',
  chi: 'chi',
  psi: 'psi',
  omega: 'omega',
  Gamma: 'Gamma',
  Delta: 'Delta',
  Theta: 'Theta',
  Lambda: 'Lambda',
  Xi: 'Xi',
  Pi: 'Pi',
  Sigma: 'Sigma',
  Phi: 'Phi',
  Psi: 'Psi',
  Omega: 'Omega',
  infty: 'infinity',
  cdot: '*',
  times: '*',
  div: '/',
  pm: '+-',
  mp: '-+',
  le: '<=',
  leq: '<=',
  ge: '>=',
  geq: '>=',
  neq: '!=',
  ne: '!=',
  approx: '~=',
  sim: '~',
  equiv: '==',
  propto: 'propto',
  in: 'in',
  notin: 'notin',
  subset: 'subset',
  subseteq: 'subseteq',
  superset: 'superset',
  supseteq: 'supseteq',
  cap: 'cap',
  cup: 'cup',
  emptyset: 'emptyset',
  forall: 'forall',
  exists: 'exists',
  neg: 'not',
  land: 'and',
  lor: 'or',
  to: '->',
  rightarrow: '->',
  leftarrow: '<-',
  leftrightarrow: '<->',
  mapsto: '|->',
  implies: '=>',
  iff: '<=>',
  sum: 'sum',
  prod: 'prod',
  int: 'int',
  lim: 'lim',
  sin: 'sin',
  cos: 'cos',
  tan: 'tan',
  log: 'log',
  ln: 'ln',
  exp: 'exp',
  max: 'max',
  min: 'min',
  gcd: 'gcd',
  lcm: 'lcm',
  mod: 'mod',
  pmod: 'mod',
}

const BLACKBOARD: Record<string, string> = {
  N: 'N',
  Z: 'Z',
  Q: 'Q',
  R: 'R',
  C: 'C',
}

function readGroup(text: string, start: number, open = '{', close = '}') {
  let i = start
  while (text[i] === ' ') i++
  if (text[i] !== open) return null

  let depth = 0
  for (let pos = i; pos < text.length; pos++) {
    if (text[pos] === open) depth++
    if (text[pos] === close) depth--
    if (depth === 0) {
      return { value: text.slice(i + 1, pos), end: pos + 1 }
    }
  }

  return null
}

function replaceTwoArgCommand(text: string, commands: string[], format: (a: string, b: string) => string) {
  let out = ''
  let i = 0
  while (i < text.length) {
    const command = commands.find(name => text.startsWith(`\\${name}`, i))
    if (!command) {
      out += text[i]
      i++
      continue
    }

    const first = readGroup(text, i + command.length + 1)
    const second = first ? readGroup(text, first.end) : null
    if (!first || !second) {
      out += text[i]
      i++
      continue
    }

    out += format(formatTeXReadable(first.value), formatTeXReadable(second.value))
    i = second.end
  }
  return out
}

function replaceOneArgCommand(text: string, commands: string[], format: (a: string) => string) {
  let out = ''
  let i = 0
  while (i < text.length) {
    const command = commands.find(name => text.startsWith(`\\${name}`, i))
    if (!command) {
      out += text[i]
      i++
      continue
    }

    const group = readGroup(text, i + command.length + 1)
    if (!group) {
      out += text[i]
      i++
      continue
    }

    out += format(formatTeXReadable(group.value))
    i = group.end
  }
  return out
}

function replaceSqrt(text: string) {
  let out = ''
  let i = 0
  while (i < text.length) {
    if (!text.startsWith('\\sqrt', i)) {
      out += text[i]
      i++
      continue
    }

    let pos = i + '\\sqrt'.length
    const root = readGroup(text, pos, '[', ']')
    if (root) pos = root.end
    const radicand = readGroup(text, pos)
    if (!radicand) {
      out += text[i]
      i++
      continue
    }

    const rootText = root ? formatTeXReadable(root.value) : ''
    const radicandText = formatTeXReadable(radicand.value)
    out += rootText ? `root(${rootText}, ${radicandText})` : `sqrt(${radicandText})`
    i = radicand.end
  }
  return out
}

function toScript(value: string, fallbackPrefix: string) {
  const text = formatTeXReadable(value).trim()
  if (!text) return ''
  return `${fallbackPrefix}${text.length === 1 ? text : `(${text})`}`
}

function replaceScripts(text: string) {
  return text
    .replace(/\^\{([^{}]+)\}/g, (_, value: string) => toScript(value, '^'))
    .replace(/_\{([^{}]+)\}/g, (_, value: string) => toScript(value, '_'))
    .replace(/\^([A-Za-z0-9+\-=()])/g, (_, value: string) => toScript(value, '^'))
    .replace(/_([A-Za-z0-9+\-=()])/g, (_, value: string) => toScript(value, '_'))
}

function problemFontSize(text: string) {
  const length = text.length
  if (length <= 220) return 58
  if (length <= 420) return 50
  if (length <= 700) return 42
  if (length <= 1050) return 34
  return 28
}

function answerFontSize(text: string) {
  const length = text.length
  if (length <= 120) return 38
  if (length <= 260) return 32
  return 27
}

function mathSafe(value: string) {
  return formatTeXReadable(value)
    .replace(/\$\$([\s\S]*?)\$\$/g, '$1')
    .replace(/\$((?:[^$\\]|\\.)*?)\$/g, '$1')
    .replace(/\\\[([\s\S]*?)\\\]/g, '$1')
    .replace(/\\\(([\s\S]*?)\\\)/g, '$1')
}

function formatTeXReadable(value: string): string {
  let text = value
    .replace(/\$\$([\s\S]*?)\$\$/g, '$1')
    .replace(/\$((?:[^$\\]|\\.)*?)\$/g, '$1')
    .replace(/\\\[([\s\S]*?)\\\]/g, '$1')
    .replace(/\\\(([\s\S]*?)\\\)/g, '$1')
    .replace(/\\left\s*/g, '')
    .replace(/\\right\s*/g, '')
    .replace(/\\,/g, ' ')
    .replace(/\\;/g, ' ')
    .replace(/\\qquad/g, ' ')
    .replace(/\\quad/g, ' ')
    .replace(/\\\\(?=[A-Za-z])/g, '\\')
    .replace(/\\\\/g, '\n')

  text = replaceTwoArgCommand(text, ['frac', 'dfrac', 'tfrac'], (a, b) => `(${a})/(${b})`)
  text = replaceTwoArgCommand(text, ['binom', 'dbinom', 'tbinom'], (a, b) => `C(${a}, ${b})`)
  text = replaceSqrt(text)
  text = replaceOneArgCommand(text, ['pmod'], value => `(mod ${value})`)
  text = replaceOneArgCommand(text, ['mathbb'], value => BLACKBOARD[value] ?? value)
  text = replaceOneArgCommand(text, ['mathcal', 'mathbf', 'mathit'], value => value)
  text = replaceOneArgCommand(text, ['operatorname', 'mathrm', 'text'], value => value)
  text = replaceOneArgCommand(text, ['overline'], value => `overline(${value})`)
  text = replaceOneArgCommand(text, ['vec'], value => `vec(${value})`)
  text = replaceOneArgCommand(text, ['bar'], value => `bar(${value})`)
  text = replaceOneArgCommand(text, ['hat'], value => `hat(${value})`)

  for (const [command, replacement] of Object.entries(COMMAND_REPLACEMENTS)) {
    text = text.replace(new RegExp(`\\\\${command}\\b`, 'g'), replacement)
  }

  text = replaceScripts(text)
  return text
    .replace(/[{}]/g, '')
    .replace(/\\([A-Za-z]+)/g, '$1')
    .replace(/[ \t]{2,}/g, ' ')
    .trim()
}

export async function POST(req: NextRequest) {
  const { statement, answer, topic, score } = await req.json().catch(() => ({}))
  const statementText = mathSafe(asText(statement))

  if (!statementText) {
    return NextResponse.json(
      { ok: false, error: 'statement required', code: 'STATEMENT_REQUIRED' },
      { status: 400 },
    )
  }

  const topicText = clamp(asText(topic) || '数学', 28)
  const scoreText = Number.isFinite(Number(score)) ? Number(score).toFixed(1) : '0.0'
  const answerText = mathSafe(asText(answer))
  const problemSize = problemFontSize(statementText)
  const answerSize = answerFontSize(answerText)
  const displayStatement = clamp(statementText, 1800)
  const displayAnswer = clamp(answerText, 520)
  const wasClamped = compact(statementText).length > compact(displayStatement).length

  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          background: '#f7fafc',
          color: '#111827',
          padding: 58,
          border: '1px solid #d7dee8',
          fontFamily: 'sans-serif',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            width: '100%',
            marginBottom: 30,
            color: '#667085',
            fontSize: 34,
            fontWeight: 700,
          }}
        >
          <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
            <span style={{ color: '#0a84ff' }}>Sakumon Station</span>
            <span>{topicText}</span>
          </div>
          <span>score {scoreText}</span>
        </div>

        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            flex: 1,
            width: '100%',
            padding: '64px 72px',
            background: '#ffffff',
            border: '1px solid #e5e7eb',
            borderRadius: 34,
            boxShadow: '0 18px 48px rgba(15, 23, 42, 0.14)',
          }}
        >
          <div
            style={{
              fontSize: problemSize,
              lineHeight: 1.62,
              fontWeight: 700,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}
          >
            {displayStatement}
          </div>

          {answerText && (
            <div
              style={{
                marginTop: 44,
                paddingTop: 32,
                borderTop: '3px solid #d1fae5',
                color: '#047857',
                fontSize: answerSize,
                lineHeight: 1.5,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
            >
              {displayAnswer}
            </div>
          )}

          {wasClamped && (
            <div
              style={{
                marginTop: 28,
                color: '#b45309',
                fontSize: 24,
                lineHeight: 1.4,
              }}
            >
              問題文が非常に長いため、画像表示は要約されています。
            </div>
          )}
        </div>
      </div>
    ),
    {
      width: WIDTH,
      height: HEIGHT,
      headers: {
        'Cache-Control': 'no-store',
      },
    },
  )
}
