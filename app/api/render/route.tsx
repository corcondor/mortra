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
  return value
    .replace(/\$\$([\s\S]*?)\$\$/g, '$1')
    .replace(/\$((?:[^$\\]|\\.)*?)\$/g, '$1')
    .replace(/\\\[([\s\S]*?)\\\]/g, '$1')
    .replace(/\\\(([\s\S]*?)\\\)/g, '$1')
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
