'use client'

import { ExternalLink, GitCommitHorizontal, Pause, Play, RefreshCw } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import type { Lang } from '@/lib/mortra/i18n'
import { FALLBACK_COMMITS, type ResearchCommit } from '@/lib/mortra/research-data'
import styles from '@/app/research/research.module.css'

type StreamPayload = {
  branch: string
  repository: string
  fetchedAt: string
  source: 'github' | 'fallback'
  commits: ResearchCommit[]
}

function relativeTime(value: string, lang: Lang) {
  const delta = Date.now() - new Date(value).getTime()
  const minutes = Math.max(0, Math.floor(delta / 60_000))
  if (minutes < 1) return lang === 'ja' ? 'たった今' : 'now'
  if (minutes < 60) return lang === 'ja' ? `${minutes}分前` : `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return lang === 'ja' ? `${hours}時間前` : `${hours}h ago`
  const days = Math.floor(hours / 24)
  return lang === 'ja' ? `${days}日前` : `${days}d ago`
}

export function LiveResearchStream({ lang }: { lang: Lang }) {
  const [payload, setPayload] = useState<StreamPayload>({
    branch: 'release/mortra-1-beta',
    repository: 'https://github.com/corcondor/mortra',
    fetchedAt: new Date(0).toISOString(),
    source: 'fallback',
    commits: FALLBACK_COMMITS,
  })
  const [paused, setPaused] = useState(false)
  const [refreshing, setRefreshing] = useState(false)

  const refresh = useCallback(async () => {
    setRefreshing(true)
    try {
      const response = await fetch('/api/research-stream', { cache: 'no-store' })
      if (!response.ok) return
      setPayload(await response.json() as StreamPayload)
    } finally {
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  useEffect(() => {
    if (paused) return
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') void refresh()
    }, 60_000)
    return () => window.clearInterval(timer)
  }, [paused, refresh])

  const text = lang === 'ja'
    ? { sync: '60秒同期', branch: '公開ブランチ', pause: '自動同期を停止', play: '自動同期を再開', refresh: '今すぐ同期' }
    : { sync: '60s sync', branch: 'public branch', pause: 'Pause automatic sync', play: 'Resume automatic sync', refresh: 'Sync now' }

  return (
    <section className={styles.activityPanel} aria-label={lang === 'ja' ? 'GitHub研究活動' : 'GitHub research activity'}>
      <header className={styles.panelHeader}>
        <div>
          <span className={styles.liveIndicator}><i />LIVE REPOSITORY</span>
          <strong>{text.sync}</strong>
        </div>
        <div className={styles.iconControls}>
          <button type="button" onClick={() => setPaused(value => !value)} title={paused ? text.play : text.pause} aria-label={paused ? text.play : text.pause}>
            {paused ? <Play size={14} fill="currentColor" /> : <Pause size={14} />}
          </button>
          <button type="button" onClick={() => void refresh()} title={text.refresh} aria-label={text.refresh} disabled={refreshing}>
            <RefreshCw className={refreshing ? styles.spinning : undefined} size={14} />
          </button>
        </div>
      </header>

      <div className={styles.branchLine}>
        <span>{text.branch}</span>
        <code>{payload.branch}</code>
      </div>

      <ol className={styles.commitList}>
        {payload.commits.slice(0, 6).map((commit, index) => (
          <li key={`${commit.sha}-${commit.date}`}>
            <span className={styles.commitRail} aria-hidden="true">
              <GitCommitHorizontal size={14} />
              {index < Math.min(5, payload.commits.length - 1) && <i />}
            </span>
            <a href={commit.url} target="_blank" rel="noreferrer">
              <strong>{commit.message}</strong>
              <span><code>{commit.sha}</code>{relativeTime(commit.date, lang)} · {commit.author}</span>
            </a>
          </li>
        ))}
      </ol>

      <a className={styles.panelFooterLink} href={payload.repository} target="_blank" rel="noreferrer">
        GitHub <ExternalLink size={12} aria-hidden="true" />
      </a>
    </section>
  )
}
