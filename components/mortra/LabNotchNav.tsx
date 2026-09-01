'use client'

import Image from 'next/image'
import Link from 'next/link'
import { Activity, Github, Languages, Play } from 'lucide-react'
import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { getCopy, type Lang } from '@/lib/mortra/i18n'
import styles from './labNotchNav.module.css'

type LabNotchNavProps = {
  lang: Lang
  active?: 'home' | 'research'
  alternateHref?: string
}

export function LabNotchNav({ lang, active = 'home', alternateHref }: LabNotchNavProps) {
  const copy = getCopy(lang)
  const [expanded, setExpanded] = useState(false)
  const hoverRef = useRef(false)
  const focusRef = useRef(false)
  const closeTimerRef = useRef<number | null>(null)
  const lastScrollYRef = useRef(0)
  const home = lang === 'ja' ? '/ja' : '/'
  const research = lang === 'ja' ? '/ja/research' : '/research'

  const clearCloseTimer = () => {
    if (closeTimerRef.current !== null) window.clearTimeout(closeTimerRef.current)
    closeTimerRef.current = null
  }

  const scheduleClose = (delay = 520) => {
    clearCloseTimer()
    closeTimerRef.current = window.setTimeout(() => {
      if (!hoverRef.current && !focusRef.current) setExpanded(false)
    }, delay)
  }

  useEffect(() => {
    const coarse = window.matchMedia('(pointer: coarse)')
    if (coarse.matches) {
      lastScrollYRef.current = window.scrollY
      setExpanded(window.scrollY <= 24)

      const onScroll = () => {
        const nextY = window.scrollY
        const delta = nextY - lastScrollYRef.current

        if (nextY <= 24) setExpanded(true)
        else if (delta > 4) setExpanded(false)
        else if (delta < -12) setExpanded(true)

        lastScrollYRef.current = nextY
      }

      window.addEventListener('scroll', onScroll, { passive: true })
      return () => window.removeEventListener('scroll', onScroll)
    }

    const onPointerMove = (event: PointerEvent) => {
      const nearTop = event.clientY <= 108
      const nearCenter = Math.abs(event.clientX - window.innerWidth / 2) <= Math.min(460, window.innerWidth * 0.44)
      if (nearTop && nearCenter) {
        clearCloseTimer()
        setExpanded(true)
      } else if (event.clientY > 174 && !hoverRef.current && !focusRef.current) {
        scheduleClose(260)
      }
    }

    window.addEventListener('pointermove', onPointerMove, { passive: true })
    return () => {
      clearCloseTimer()
      window.removeEventListener('pointermove', onPointerMove)
    }
  }, [])

  const onGlassPointerMove = (event: React.PointerEvent<HTMLElement>) => {
    const rect = event.currentTarget.getBoundingClientRect()
    event.currentTarget.style.setProperty('--glass-x', `${event.clientX - rect.left}px`)
    event.currentTarget.style.setProperty('--glass-y', `${event.clientY - rect.top}px`)
  }

  const labels = lang === 'ja'
    ? { home: '概要', lab: '研究', live: 'LIVE', github: 'GitHubを開く', primary: '主要ナビゲーション' }
    : { home: 'Overview', lab: 'Research', live: 'LIVE', github: 'Open GitHub', primary: 'Primary navigation' }

  return (
    <header className={styles.header} data-expanded={expanded ? 'true' : 'false'}>
      <div
        className={styles.notch}
        onPointerEnter={() => {
          hoverRef.current = true
          clearCloseTimer()
          setExpanded(true)
        }}
        onPointerLeave={() => {
          hoverRef.current = false
          scheduleClose()
        }}
        onPointerMove={onGlassPointerMove}
        onFocusCapture={() => {
          focusRef.current = true
          clearCloseTimer()
          setExpanded(true)
        }}
        onBlurCapture={event => {
          if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
            focusRef.current = false
            scheduleClose()
          }
        }}
        style={{ '--glass-x': '50%', '--glass-y': '0px' } as CSSProperties}
      >
        <div className={styles.specular} aria-hidden="true" />
        <Link className={styles.brand} href={home} aria-label="MORTRA home">
          <span className={styles.mark}>
            <Image src="/brand/mortra-incidence-mark.svg" alt="" width={30} height={30} priority />
          </span>
          <span className={styles.brandName}>MORTRA</span>
          <span className={styles.model}>1</span>
        </Link>

        <span className={styles.liveState} title={lang === 'ja' ? '公開研究画面' : 'Public research surface'}>
          <Activity size={12} aria-hidden="true" />
          <span>{active === 'research' ? labels.live : 'MODEL 1'}</span>
        </span>

        <nav className={styles.links} aria-label={labels.primary}>
          <Link data-active={active === 'home'} href={home}>{labels.home}</Link>
          <Link data-active={active === 'research'} href={research}>{labels.lab}</Link>
          <a href={`${home}#results`}>{copy.nav.results}</a>
          <a href={`${home}#architecture`}>{copy.nav.architecture}</a>
          <a
            className={styles.iconLink}
            href="https://github.com/corcondor/mortra"
            target="_blank"
            rel="noreferrer"
            aria-label={labels.github}
            title="GitHub"
          >
            <Github size={15} aria-hidden="true" />
          </a>
          <a className={styles.tryLink} href={`${home}#try`}>
            <Play size={12} fill="currentColor" aria-hidden="true" />
            <span>{copy.nav.try}</span>
          </a>
          <Link
            className={styles.languageLink}
            href={alternateHref ?? (active === 'research'
              ? (lang === 'ja' ? '/research' : '/ja/research')
              : copy.langToggle.href)}
            hrefLang={lang === 'ja' ? 'en' : 'ja'}
            aria-label={copy.langToggle.to}
            title={copy.langToggle.to}
          >
            <Languages size={14} aria-hidden="true" />
          </Link>
        </nav>
      </div>
    </header>
  )
}
