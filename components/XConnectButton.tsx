'use client'
import { useState, useEffect } from 'react'

interface Props {
  accessToken: string | null
}

interface XStatus {
  connected:  boolean
  x_username?: string
}

export function XConnectButton({ accessToken }: Props) {
  const [status,      setStatus]      = useState<XStatus | null>(null)
  const [connecting,  setConnecting]  = useState(false)
  const [disconnecting, setDisconnecting] = useState(false)

  const authHeaders = (): Record<string, string> =>
    accessToken ? { Authorization: `Bearer ${accessToken}` } : {}

  const fetchStatus = async () => {
    const res = await fetch('/api/x/status', { headers: authHeaders() })
    if (res.ok) setStatus(await res.json())
  }

  useEffect(() => {
    if (accessToken) fetchStatus()
    // URL パラメータで接続成功を検出
    const params = new URLSearchParams(window.location.search)
    if (params.get('x_connected') === '1') {
      fetchStatus()
      window.history.replaceState({}, '', window.location.pathname)
    }
    if (params.get('x_error')) {
      alert(`X接続エラー: ${params.get('x_error')}`)
      window.history.replaceState({}, '', window.location.pathname)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken])

  const handleConnect = async () => {
    setConnecting(true)
    try {
      const res = await fetch('/api/x/connect', { headers: authHeaders() })
      if (!res.ok) {
        const data = await res.json()
        alert(`エラー: ${data.error}`)
        return
      }
      const { redirectUrl } = await res.json()
      window.location.href = redirectUrl
    } finally {
      setConnecting(false)
    }
  }

  const handleDisconnect = async () => {
    if (!confirm('Xアカウントの接続を解除しますか？')) return
    setDisconnecting(true)
    await fetch('/api/x/disconnect', { method: 'POST', headers: authHeaders() })
    setStatus({ connected: false })
    setDisconnecting(false)
  }

  if (!accessToken) return null

  if (status?.connected) {
    return (
      <div className="flex items-center gap-2">
        <span className="text-[11px] text-[#667085]">
          𝕏 <span className="font-medium text-[#344054]">@{status.x_username}</span> で投稿
        </span>
        <button
          onClick={handleDisconnect}
          disabled={disconnecting}
          className="text-[10px] text-[#98a2b3] transition-colors hover:text-[#475467]"
        >
          {disconnecting ? '…' : '解除'}
        </button>
      </div>
    )
  }

  return (
    <button
      onClick={handleConnect}
      disabled={connecting}
      className="flex items-center gap-1.5 rounded border border-[#d0d5dd] px-3 py-1.5 text-[12px] text-[#667085]
                 transition-all hover:border-[#98a2b3] hover:text-[#344054]
                 transition-all disabled:opacity-40"
    >
      <span>𝕏</span>
      <span>{connecting ? '接続中…' : 'Xアカウントを接続'}</span>
    </button>
  )
}
