'use client'

import { Box, DoorClosed, DoorOpen, Flag, KeyRound, ToggleLeft, ToggleRight, TriangleAlert } from 'lucide-react'
import { at, type Game, type GameState } from '@/lib/mortra/microgame'
import styles from './WorldExperiment.module.css'

export function MicroGameBoard({ game, state, trail = [], label }: { game: Game; state: GameState; trail?: GameState[]; label: string }) {
  const cells = []
  for (let y = 0; y < game.height; y++) for (let x = 0; x < game.width; x++) {
    const wall = game.walls.some(c => at(c, x, y))
    cells.push(<rect key={`${x},${y}`} x={x * 40 + 2} y={y * 40 + 2} width={36} height={36} rx={3} fill={wall ? '#282d30' : '#eff1ef'} />)
  }
  const icon = (cell: [number, number] | null, content: React.ReactNode) => cell && <g transform={`translate(${cell[0] * 40 + 9} ${cell[1] * 40 + 9})`}>{content}</g>
  return <svg className={styles.board} viewBox={`0 0 ${game.width * 40} ${game.height * 40}`} role="img" aria-label={label} data-state={JSON.stringify(state)}>
    <title>{label}</title>
    {cells}
    {game.hazards.map(([x, y]) => <g key={`h${x},${y}`} transform={`translate(${x * 40 + 8} ${y * 40 + 8})`}><TriangleAlert size={24} fill="#ffd3ce" stroke="#b93c30" /></g>)}
    {icon(game.start_pos, <circle cx={11} cy={11} r={7} fill="none" stroke="#7e8783" strokeDasharray="3 2" />)}
    {icon(game.goal_pos, <Flag size={22} fill="#96d9b5" stroke="#176747" />)}
    {!state[2] && icon(game.key_pos, <KeyRound size={22} stroke="#986400" />)}
    {icon(game.door_pos, state[3] ? <DoorOpen size={22} stroke="#966d10" /> : <DoorClosed size={22} stroke="#966d10" />)}
    {icon(game.switch_pos, state[4] ? <ToggleRight size={22} stroke="#196c4b" /> : <ToggleLeft size={22} stroke="#626b66" />)}
    {icon(game.gate_pos, <g stroke={state[5] ? '#88aaa0' : '#b43f69'} strokeWidth={3}><path d={state[5] ? 'M2 3V20M20 3V20' : 'M3 3V20M11 3V20M19 3V20M2 7H20'} /></g>)}
    {[game.teleport_a, game.teleport_b].map((cell, i) => cell && <g key={`t${i}`} transform={`translate(${cell[0] * 40 + 20} ${cell[1] * 40 + 20})`}><circle r={12} fill="#dae8ff" stroke="#416abe" strokeWidth={2} /><circle r={5} fill="none" stroke="#416abe" /></g>)}
    {game.block_pos && icon([state[6], state[7]], <Box size={22} fill="#ced3d0" stroke="#58645e" />)}
    {trail.length > 1 && <polyline points={trail.map(s => `${s[0] * 40 + 20},${s[1] * 40 + 20}`).join(' ')} fill="none" stroke="#277d60" strokeOpacity={0.6} strokeWidth={3} strokeLinejoin="round" />}
    <circle cx={state[0] * 40 + 20} cy={state[1] * 40 + 20} r={13} fill="#79d2ae" stroke="#174c39" strokeWidth={2} />
    <circle cx={state[0] * 40 + 24} cy={state[1] * 40 + 17} r={2} fill="#174c39" />
  </svg>
}
