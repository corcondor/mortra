import { ImageResponse } from 'next/og'

export const alt = 'MORTRA: finite primitives, infinite mathematics'
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
        <div style={{ width: 44, height: 44, border: '1px solid #ff9d2e', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#ff9d2e' }}>M</div>
        <b>MORTRA</b>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        <div style={{ display: 'flex', flexDirection: 'column', fontSize: 72, lineHeight: 1.04, fontWeight: 700 }}>
          <span>Finite primitives.</span><span>Infinite mathematics.</span>
        </div>
        <div style={{ color: '#aeb8c0', fontSize: 27 }}>問題文から証明書まで、数学を実行可能に。</div>
      </div>
      <div style={{ display: 'flex', gap: 34, fontSize: 21 }}>
        <span style={{ color: '#ff9d2e' }}>Audited geometry 89 / 89</span>
        <span style={{ color: '#ff5fb0' }}>Replayed identities 357 / 357</span>
        <span style={{ color: '#4dffa0' }}>Replayable certificates</span>
      </div>
    </div>,
    size,
  )
}
