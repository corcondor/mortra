'use client'
import { useState } from 'react'

interface Props {
  accessToken: string | null
  used: number
  limit: number
  onClose: () => void
}

export function UpgradeModal({ accessToken, used, limit, onClose }: Props) {
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState<string | null>(null)

  const handleUpgrade = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/billing/checkout', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        },
      })
      const data = await res.json()
      if (data.url) {
        window.location.href = data.url
      } else {
        setError(data.error ?? '決済画面を開けませんでした')
        setLoading(false)
      }
    } catch (e) {
      setError(String(e))
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center px-4">
      <div className="glass rounded-2xl p-8 max-w-sm w-full space-y-5 border border-white/10">

        {/* Header */}
        <div className="text-center space-y-1">
          <div className="text-3xl">🚀</div>
          <h2 className="text-[20px] font-bold text-white/90">無料枠を使い切りました</h2>
          <p className="text-[13px] text-white/40">
            今月の生成回数: <span className="text-apple-pink font-semibold">{used}/{limit}</span>
          </p>
        </div>

        {/* Plan comparison */}
        <div className="space-y-2">
          <div className="rounded-xl border border-white/10 p-3.5 opacity-50">
            <div className="flex justify-between items-center">
              <span className="text-[13px] font-semibold text-white/70">無料プラン</span>
              <span className="text-[12px] text-white/40">¥0 / 月</span>
            </div>
            <p className="text-[11px] text-white/30 mt-1">月10回まで生成可能</p>
          </div>

          <div className="rounded-xl border border-apple-blue/40 bg-apple-blue/8 p-3.5">
            <div className="flex justify-between items-center">
              <span className="text-[13px] font-semibold text-apple-blue">プレミアム</span>
              <span className="text-[12px] text-white/60">月額プラン</span>
            </div>
            <ul className="mt-1.5 space-y-0.5">
              {[
                '生成回数 無制限',
                '全問題へのアクセス',
                '優先サポート',
              ].map(f => (
                <li key={f} className="text-[11px] text-white/50 flex items-center gap-1.5">
                  <span className="text-apple-blue text-[10px]">✓</span> {f}
                </li>
              ))}
            </ul>
          </div>
        </div>

        {error && (
          <p className="text-[11px] text-apple-pink text-center">{error}</p>
        )}

        <div className="flex flex-col gap-2">
          <button
            onClick={handleUpgrade}
            disabled={loading}
            className="w-full py-3 bg-apple-blue text-white rounded-xl text-[14px] font-semibold
                       hover:bg-apple-blue/80 transition-colors disabled:opacity-50"
          >
            {loading ? '決済画面に移動中…' : 'プレミアムにアップグレード'}
          </button>
          <button
            onClick={onClose}
            className="w-full py-2 text-[12px] text-white/30 hover:text-white/60 transition-colors"
          >
            後で
          </button>
        </div>

        <p className="text-[10px] text-white/20 text-center">
          Visa・MasterCard・クレジットカード対応（Stripe で決済）
        </p>
      </div>
    </div>
  )
}
