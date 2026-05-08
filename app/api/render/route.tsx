import { NextRequest, NextResponse } from 'next/server'
import { ImageResponse } from 'next/og'

export const runtime = 'edge'

const WIDTH = 1200
const HEIGHT = 675

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
            fontSize: 28,
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
            padding: '42px 48px',
            background: '#ffffff',
            border: '1px solid #e5e7eb',
            borderRadius: 28,
            boxShadow: '0 18px 48px rgba(15, 23, 42, 0.14)',
          }}
        >
          <div
            style={{
              fontSize: 42,
              lineHeight: 1.55,
              fontWeight: 700,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}
          >
            {clamp(statementText, 360)}
          </div>

          {answerText && (
            <div
              style={{
                marginTop: 34,
                paddingTop: 26,
                borderTop: '3px solid #d1fae5',
                color: '#047857',
                fontSize: 30,
                lineHeight: 1.45,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
            >
              {clamp(answerText, 150)}
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
