'use client'

import Link from 'next/link'
import { useEffect, useState, type ReactNode } from 'react'
import { ArrowUp, ArrowDown, ArrowLeft, ArrowRight, ArrowUpRight, Check, ChevronDown, Download, Flag, Github, Hand, KeyRound, Menu, Pause, Play, RotateCcw, SkipBack, StepForward, X } from 'lucide-react'
import { getWorldCopy, type Lang } from '@/lib/mortra/i18n'
import { initialState, isGoal, stepGame, type Experiment, type Game, type Metrics } from '@/lib/mortra/microgame'
import { MicroGameBoard } from './MicroGameBoard'
import styles from './WorldExperiment.module.css'

const RUN = '/mortra/runs/self-game-design-v2-20260923'
const STAGES = ['Generate', 'Explore', 'Learn transitions', 'Play', 'Evaluate', 'Edit', 'Re-test']
const FLOW = ['Observation', 'State / transition structure', 'Fixed-field reasoning', 'Action', 'Evaluation / environment edit']

function IconButton({ label, children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { label: string; children: ReactNode }) {
  return <button type="button" className={styles.iconButton} aria-label={label} title={label} {...props}>{children}</button>
}

function ManualGame({ game, lang }: { game: Game; lang: Lang }) {
  const t = getWorldCopy(lang)
  const [state, setState] = useState(() => initialState(game))
  const [moves, setMoves] = useState(0)
  const won = isGoal(game, state)
  const act = (action: number) => {
    if (won) return
    setState(s => stepGame(game, s, action)); setMoves(n => n + 1)
  }
  const reset = () => { setState(initialState(game)); setMoves(0) }
  return <div className={styles.gameTool}>
    <div className={styles.gameStatus}><span>{won ? <><Flag size={16} /> {t.goal}</> : <>{moves} {t.moves}</>}</span><span>{state[2] ? <><KeyRound size={16} /> {lang === 'ja' ? '鍵あり' : 'Key held'}</> : ''}</span><IconButton label={t.reset} onClick={reset}><RotateCcw size={18} /></IconButton></div>
    <div tabIndex={0} className={styles.playSurface} role="group" aria-label={lang === 'ja' ? '手動ゲーム' : 'Manual game'} onKeyDown={e => {
      if (e.target !== e.currentTarget) return
      const action = ({ ArrowUp: 0, ArrowDown: 1, ArrowLeft: 2, ArrowRight: 3, w: 0, s: 1, a: 2, d: 3, ' ': 4, Enter: 4 } as Record<string, number>)[e.key]
      if (action !== undefined) { e.preventDefault(); act(action) }
    }}><MicroGameBoard game={game} state={state} label={lang === 'ja' ? '手動プレイの盤面' : 'Manual play board'} /></div>
    <div className={styles.dpad}>
      <IconButton label="Move up" onClick={() => act(0)} disabled={won}><ArrowUp /></IconButton>
      <IconButton label="Move left" onClick={() => act(2)} disabled={won}><ArrowLeft /></IconButton>
      <IconButton label={t.interact} onClick={() => act(4)} disabled={won}><Hand size={20} /></IconButton>
      <IconButton label="Move right" onClick={() => act(3)} disabled={won}><ArrowRight /></IconButton>
      <IconButton label="Move down" onClick={() => act(1)} disabled={won}><ArrowDown /></IconButton>
    </div>
  </div>
}

function RecordedGame({ data, lang }: { data: Experiment; lang: Lang }) {
  const [phase, setPhase] = useState<'initial' | 'final'>('final')
  const [player, setPlayer] = useState<'mortra' | 'random'>('mortra')
  const [index, setIndex] = useState(0)
  const [playing, setPlaying] = useState(false)
  const t = getWorldCopy(lang), replay = data.replays[phase][player]
  const change = (nextPhase: typeof phase, nextPlayer: typeof player) => { setPlaying(false); setIndex(0); setPhase(nextPhase); setPlayer(nextPlayer) }
  useEffect(() => {
    if (!playing) return
    const timer = window.setInterval(() => setIndex(i => {
      if (i >= replay.actions.length) { setPlaying(false); return i }
      return i + 1
    }), 300)
    return () => window.clearInterval(timer)
  }, [playing, replay])
  return <div className={styles.gameTool}>
    <p className={styles.recorded}><span />Recorded MORTRA experiment</p>
    <div className={styles.replaySelects}>
      <label>{lang === 'ja' ? '盤面' : 'World'}<select aria-label="Replay world" value={phase} onChange={e => change(e.target.value as typeof phase, player)}><option value="initial">{t.initial}</option><option value="final">{t.final}</option></select></label>
      <label>{lang === 'ja' ? 'プレイヤー' : 'Player'}<select aria-label="Replay player" value={player} onChange={e => change(phase, e.target.value as typeof player)}><option value="mortra">MORTRA</option><option value="random">Random baseline</option></select></label>
    </div>
    <MicroGameBoard game={data[phase]} state={replay.states[index]} trail={replay.states.slice(0, index + 1)} label="Recorded play board" />
    <div className={styles.transport}>
      <IconButton label="Restart replay" onClick={() => { setIndex(0); setPlaying(false) }}><SkipBack size={18} /></IconButton>
      <IconButton label={playing ? 'Pause replay' : 'Play replay'} onClick={() => { if (index === replay.actions.length) setIndex(0); setPlaying(!playing) }}>{playing ? <Pause size={20} /> : <Play size={20} />}</IconButton>
      <IconButton label="Next recorded step" disabled={index >= replay.actions.length} onClick={() => { setPlaying(false); setIndex(i => i + 1) }}><StepForward size={19} /></IconButton>
      <output aria-live="polite">{index} / {replay.actions.length}</output>
    </div>
    <input className={styles.scrubber} type="range" aria-label="Recorded step" min={0} max={replay.actions.length} value={index} onChange={e => { setPlaying(false); setIndex(Number(e.target.value)) }} />
    <p className={styles.note}>Trial {replay.trial + 1} / {data.metadata.config.trials} · {index === replay.actions.length ? (replay.reached_goal ? t.goal : (lang === 'ja' ? '制限内に到達せず' : 'Goal not reached within budget')) : (lang === 'ja' ? 'Python実行記録' : 'Python execution record')}</p>
  </div>
}

function Provenance({ data, trials }: { data: Experiment; trials: number }) {
  const m = data.metadata
  return <details className={styles.provenance}><summary>Experiment / seed / SHA / trials</summary><dl>
    <dt>Experiment ID</dt><dd>{m.experiment_id}</dd><dt>Generation seed</dt><dd>{m.config.generation_seed}</dd><dt>Mutation seed</dt><dd>{m.config.mutation_seed}</dd><dt>Random player seed</dt><dd>{m.config.random_player_seed}</dd><dt>Commit SHA</dt><dd><code>{m.commit_sha}</code></dd><dt>Trials</dt><dd>{trials} per player, per layout</dd>
  </dl></details>
}

function MetricRecord({ name, metrics, data, lang }: { name: string; metrics: Metrics; data: Experiment; lang: Lang }) {
  const rows = [
    ['MORTRA', `${metrics.successes} / ${metrics.trials}`],
    ['Random baseline', `${metrics.random_successes} / ${metrics.trials}`],
    [lang === 'ja' ? '成功時の平均行動数' : 'Mean actions on success', String(metrics.mean_actions_to_goal)],
    [lang === 'ja' ? '観測した状態数' : 'Observed states', String(metrics.state_coverage)],
    [lang === 'ja' ? '成功軌跡の種類' : 'Unique successful trajectories', String(metrics.unique_successful_trajectories)],
  ]
  return <article className={styles.metricRecord}><h3>{name}</h3>{rows.map(([label, value]) => <div className={styles.metric} key={label}><p>{label}</p><strong>{value}</strong><Provenance data={data} trials={metrics.trials} /></div>)}</article>
}

export function MortraProductPage({ lang = 'en' }: { lang?: Lang }) {
  const t = getWorldCopy(lang), ja = lang === 'ja', research = ja ? '/ja/research' : '/research'
  const [data, setData] = useState<Experiment | null>(null), [error, setError] = useState(false), [attempt, setAttempt] = useState(0)
  const [phase, setPhase] = useState<'initial' | 'final'>('final'), [menu, setMenu] = useState(false)
  useEffect(() => {
    const controller = new AbortController()
    setError(false)
    fetch(`${RUN}/experiment.json`, { signal: controller.signal }).then(r => { if (!r.ok) throw new Error('Experiment unavailable'); return r.json() }).then(d => {
      if (d.metadata?.version !== 2 || !d.replays?.final?.mortra?.states?.length) throw new Error('Invalid experiment')
      setData(d)
    }).catch(e => { if (e.name !== 'AbortError') setError(true) })
    return () => controller.abort()
  }, [attempt])
  return <main className={styles.page} lang={lang}>
    <a className={styles.skip} href="#play">{t.navPlay}</a>
    <header className={styles.header}>
      <Link href={ja ? '/ja' : '/'} className={styles.brand}><img src="/brand/mortra-incidence-mark.svg" width={28} height={28} alt="" />MORTRA</Link>
      <nav className={styles.desktopNav} aria-label="Main"><a href="#play">{t.navPlay}</a><a href="#replay">{t.navRecord}</a><Link href={research}>{t.navResearch}</Link><Link href={ja ? '/' : '/ja'} hrefLang={ja ? 'en' : 'ja'}>{ja ? 'EN' : '日本語'}</Link></nav>
      <button className={styles.menuButton} aria-label={menu ? 'Close menu' : 'Open menu'} aria-expanded={menu} onClick={() => setMenu(!menu)}>{menu ? <X /> : <Menu />}</button>
    </header>
    {menu && <nav className={styles.mobileNav} aria-label="Mobile"><a href="#play" onClick={() => setMenu(false)}>{t.navPlay}</a><a href="#replay" onClick={() => setMenu(false)}>{t.navRecord}</a><Link href={research}>{t.navResearch}</Link><Link href={ja ? '/' : '/ja'}>{ja ? 'English' : '日本語'}</Link></nav>}
    <section className={styles.hero} aria-labelledby="mortra-title">
      <p className={styles.eyebrow}>WORLDS / ACTIONS / EVIDENCE</p>
      <h1 id="mortra-title">MORTRA</h1>
      <p className={styles.tagline}>Builds worlds. Learns them.<br />Plays them. Changes them.</p>
      <p className={styles.subcopy}>{t.meta.description}</p>
      <a className={styles.primaryLink} href="#play">{t.navPlay}<ArrowDown size={18} /></a>
      <span className={styles.heroFoot}>SELF-GAME-DESIGN / V2</span>
    </section>
    <section id="play" className={styles.section}>
      <p className={styles.eyebrow}>01 / PLAY THE GAME MANUALLY</p><h2>{t.play}</h2>
      {data ? <><div className={styles.segment} role="group" aria-label="Manual world">{(['initial', 'final'] as const).map(p => <button key={p} aria-pressed={phase === p} onClick={() => setPhase(p)}>{t[p]}</button>)}</div><ManualGame key={phase} game={data[phase]} lang={lang} /></> : <div className={styles.loading} role="status">{error ? <>{t.error}<button onClick={() => setAttempt(a => a + 1)}>{t.retry}</button></> : t.pending}</div>}
    </section>
    <section id="replay" className={`${styles.section} ${styles.tinted}`}>
      <p className={styles.eyebrow}>02 / RECORDED PLAY</p><h2>{t.replay}</h2>
      {data && <RecordedGame data={data} lang={lang} />}
    </section>
    <section id="compare" className={styles.section}>
      <p className={styles.eyebrow}>03 / INITIAL VS FINAL</p><h2>{t.compare}</h2>
      {data && <div className={styles.comparison}>{(['initial', 'final'] as const).map(p => <figure key={p}><figcaption>{t[p]}<span>{p === 'initial' ? 'G0' : `G${data.metadata.config.design_iterations}`}</span></figcaption><MicroGameBoard game={data[p]} state={initialState(data[p])} label={`${p} game layout`} /></figure>)}<p className={styles.note}>{ja ? '採用された編集' : 'Accepted edits'}: {data.metrics.accepted_designer_count} / {data.metadata.config.design_iterations}</p></div>}
    </section>
    <section id="timeline" className={`${styles.section} ${styles.tinted}`}>
      <p className={styles.eyebrow}>04 / AUTONOMOUS EDIT TIMELINE</p><h2>{t.timeline}</h2>
      <ol className={styles.stages}>{STAGES.map((stage, i) => <li key={stage}><span>{String(i + 1).padStart(2, '0')}</span>{stage}</li>)}</ol>
      {data && <div className={styles.timeline}>{data.timeline.map(entry => <details key={entry.iteration} className={styles.edit}><summary><span className={styles.iteration}>{String(entry.iteration).padStart(2, '0')}</span><span>{entry.mutation}</span><span className={styles.verdict} data-accepted={entry.accepted}>{entry.iteration === 0 ? 'G0' : entry.accepted ? t.accepted : t.rejected}</span><ChevronDown size={16} /></summary><div><p>{entry.decision_reason ?? 'Fresh generation, seed 101'}</p><p>Critique: {entry.critique}</p>{entry.candidate_metrics && <p>Candidate: MORTRA {entry.candidate_metrics.successes}/{entry.candidate_metrics.trials} · Random {entry.candidate_metrics.random_successes}/{entry.candidate_metrics.trials}</p>}</div></details>)}</div>}
    </section>
    <section id="how" className={styles.section}><p className={styles.eyebrow}>05 / HOW MORTRA WORKS</p><h2>{t.how}</h2><ol className={styles.flow}>{FLOW.map((item, i) => <li key={item}><span>{item}</span>{i < FLOW.length - 1 && <ArrowDown size={22} aria-hidden="true" />}</li>)}</ol><p className={styles.note}>{ja ? '観測した遷移から構造を作り、固定場の値を行動へ読み出します。評価ごとに構造を学び直します。' : 'Observed transitions form the structure. Fixed-field values guide actions. The structure is learned afresh for each evaluation.'}</p></section>
    <section id="experiments" className={`${styles.section} ${styles.tinted}`}><p className={styles.eyebrow}>06 / VERIFIED EXPERIMENTS</p><h2>{t.verified}</h2>
      {data && <div className={styles.evidence}><p className={styles.note}>{t.limits}</p><MetricRecord name={t.initial} metrics={data.metrics.initial_metrics} data={data} lang={lang} /><MetricRecord name={t.final} metrics={data.metrics.final_designer_metrics} data={data} lang={lang} /><MetricRecord name={ja ? 'ランダム編集の比較条件' : 'Random-mutation control'} metrics={data.metrics.final_control_metrics} data={data} lang={lang} />
        <details className={styles.metadata}><summary>Experiment metadata</summary><dl><dt>ID</dt><dd>{data.metadata.experiment_id}</dd><dt>UTC</dt><dd>{data.metadata.generated_at}</dd><dt>Commit SHA</dt><dd><code>{data.metadata.commit_sha}</code></dd><dt>Python</dt><dd>{data.metadata.python}</dd><dt>Dependencies</dt><dd>{Object.entries(data.metadata.dependencies).map(([k, v]) => `${k} ${v}`).join(', ')}</dd><dt>Exploration</dt><dd>{data.metadata.config.exploration_steps} actions / evaluation</dd><dt>Trial budget</dt><dd>{data.metadata.config.max_play_steps} actions / trial</dd><dt>Limitations</dt><dd>{data.metadata.limitations.map(s => <p key={s}>{s}</p>)}</dd></dl></details>
        <a className={styles.download} href={`${RUN}/experiment.json`} download><Download size={18} /> Experiment JSON</a>
      </div>}
    </section>
    <section id="research" className={styles.section}><p className={styles.eyebrow}>07 / RESEARCH</p><h2>{t.research}</h2><div className={styles.researchLinks}>{[
      ['Mathematics / Geometry', `${research}#geometry-basis`], ['State Construction', `${research}#state-construction`], ['Cross-domain experiments', `${research}#cross-domain`], ['Path-field / geometric-optics research', `${research}#path-field`], ['Archived earlier work', `${research}/archive`],
    ].map(([label, href]) => <Link key={href} href={href}>{label}<ArrowUpRight size={19} /></Link>)}</div></section>
    <footer className={styles.footer}><Link href={ja ? '/ja' : '/'}>MORTRA</Link><div><a href="https://github.com/corcondor/mortra"><Github size={17} />GitHub</a><a href="https://x.com/MORTRA_AI">X / MORTRA_AI</a><Link href={research}>{t.navResearch}</Link></div><small>© {new Date().getFullYear()} MORTRA</small></footer>
  </main>
}
