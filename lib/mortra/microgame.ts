export type Cell = [number, number]
export type GameState = [number, number, number, number, number, number, number, number]
export type Game = {
  width: number; height: number; walls: Cell[]; hazards: Cell[]
  start_pos: Cell; goal_pos: Cell; key_pos: Cell | null; door_pos: Cell | null
  switch_pos: Cell | null; gate_pos: Cell | null; block_pos: Cell | null
  teleport_a: Cell | null; teleport_b: Cell | null; rules: { hazard_reset?: boolean }
}
export const at = (cell: Cell | null, x: number, y: number) => !!cell && cell[0] === x && cell[1] === y
export const initialState = (g: Game): GameState => [g.start_pos[0], g.start_pos[1], 0, 0, 0, 0, ...(g.block_pos ?? [-1, -1]) as Cell]
export const isGoal = (g: Game, s: GameState) => at(g.goal_pos, s[0], s[1])

// Manual interaction only. Recorded play is read directly from Python's states.
// Branch order intentionally mirrors MicroGame.step, including overlapping tiles.
export function stepGame(g: Game, state: GameState, action: number): GameState {
  if (!Number.isInteger(action) || action < 0 || action > 4) throw new Error('Invalid action')
  let [px, py, key, door, sw, gate, bx, by] = state
  const has = (cells: Cell[], x: number, y: number) => cells.some(c => at(c, x, y))
  const [dx, dy] = [[0, -1], [0, 1], [-1, 0], [1, 0], [0, 0]][action]
  if (action < 4) {
    let nx = px + dx, ny = py + dy
    if (nx < 0 || nx >= g.width || ny < 0 || ny >= g.height || has(g.walls, nx, ny)) { nx = px; ny = py }
    else if (at(g.door_pos, nx, ny) && !door) {
      if (key) door = 1
      else { nx = px; ny = py }
    } else if (at(g.gate_pos, nx, ny) && !gate) { nx = px; ny = py }
    else if (g.block_pos && nx === bx && ny === by) {
      const xx = bx + dx, yy = by + dy
      if (xx > 0 && xx < g.width - 1 && yy > 0 && yy < g.height - 1 && !has(g.walls, xx, yy)
          && (!at(g.door_pos, xx, yy) || door) && (!at(g.gate_pos, xx, yy) || gate) && !has(g.hazards, xx, yy)) { bx = xx; by = yy }
      else { nx = px; ny = py }
    } else if (has(g.hazards, nx, ny)) {
      if (g.rules.hazard_reset ?? true) [nx, ny] = g.start_pos
      else { nx = px; ny = py }
    } else if (at(g.teleport_a, nx, ny) && g.teleport_b) [nx, ny] = g.teleport_b
    else if (at(g.teleport_b, nx, ny) && g.teleport_a) [nx, ny] = g.teleport_a
    px = nx; py = ny
    if (at(g.key_pos, px, py)) key = 1
    if (at(g.switch_pos, px, py)) { sw = 1 - sw; gate = sw }
  } else {
    for (const [x, y] of [[0, 0], [0, -1], [0, 1], [-1, 0], [1, 0]]) {
      if (at(g.key_pos, px + x, py + y)) key = 1
      if (at(g.switch_pos, px + x, py + y)) { sw = 1 - sw; gate = sw }
      if (at(g.door_pos, px + x, py + y) && key) door = 1
    }
  }
  return [px, py, key, door, sw, gate, bx, by]
}

export type Replay = { trial: number; actions: number[]; states: GameState[]; reached_goal: boolean }
export type Metrics = {
  trials: number; successes: number; random_successes: number; mean_actions_to_goal: number
  state_coverage: number; edge_coverage: number; unique_successful_trajectories: number
}
export type Experiment = {
  metadata: {
    experiment_id: string; version: number; commit_sha: string; source_sha256: string
    generated_at: string; python: string; dependencies: Record<string, string>; limitations: string[]
    config: { generation_seed: number; mutation_seed: number; random_player_seed: number; trials: number; exploration_steps: number; max_play_steps: number; design_iterations: number; q: number }
  }
  initial: Game; final: Game; control: Game
  replays: Record<'initial' | 'final', Record<'mortra' | 'random', Replay>>
  timeline: { iteration: number; accepted: boolean; critique: string; mutation: string; decision_reason?: string; game: Game; metrics: Metrics; candidate_metrics: Metrics | null }[]
  metrics: { initial_metrics: Metrics; final_designer_metrics: Metrics; final_control_metrics: Metrics; accepted_designer_count: number; accepted_control_count: number }
}
