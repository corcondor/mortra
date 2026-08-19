import { ImageResponse } from 'next/og'

export const alt = 'MORTRA-1: mathematics in motion'
export const size = { width: 1200, height: 630 }
export const contentType = 'image/png'

export default function Image() {
  return new ImageResponse(
    <div
      style={{
        width: '100%', height: '100%', display: 'flex', flexDirection: 'column',
        justifyContent: 'space-between', background: '#030506', color: '#f4f7f8',
        padding: '64px 72px', fontFamily: 'sans-serif',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 18, fontSize: 24 }}>
        <div style={{ width: 44, height: 44, border: '1px solid #31c7df', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#31c7df' }}>M</div>
        <b>MORTRA-1</b>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        <div style={{ display: 'flex', flexDirection: 'column', fontSize: 78, lineHeight: 1.04, fontWeight: 700 }}>
          <span>Mathematics,</span><span>in motion.</span>
        </div>
        <div style={{ color: '#aeb8c0', fontSize: 27 }}>問題・図・解答・証明過程を、同じ数学構造から。</div>
      </div>
      <div style={{ display: 'flex', gap: 34, color: '#31c7df', fontSize: 21 }}>
        <span>IMO geometry 25 / 30</span><span>Symbolic reasoning</span><span>Public beta</span>
      </div>
    </div>,
    size,
  )
}
