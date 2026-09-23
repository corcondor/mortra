import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import ts from 'typescript'

const source = await readFile(new URL('../lib/mortra/microgame.ts', import.meta.url), 'utf8')
const js = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText
const { stepGame, initialState, isGoal } = await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`)
const fixture = JSON.parse(await readFile(new URL('../reports/self_game_design_v2/browser_transition_fixture.json', import.meta.url), 'utf8'))
for (const [index, { game, cases }] of fixture.entries()) {
  test(`Manual Web transitions match Python: game ${index}, ${cases.length * 5} transitions`, () => {
    for (const { state, outputs } of cases) for (let action = 0; action < 5; action++) {
      assert.deepEqual(stepGame(game, state, action), outputs[action])
    }
  })
}
const experiment = JSON.parse(await readFile(new URL('../web/public/mortra/runs/self-game-design-v2-20260923/experiment.json', import.meta.url), 'utf8'))
for (const phase of ['initial', 'final']) for (const player of ['mortra', 'random']) {
  test(`Complete recorded ${phase}/${player} replay matches manual Web rules`, () => {
    const game = experiment[phase], replay = experiment.replays[phase][player]
    let state = initialState(game)
    assert.deepEqual(state, replay.states[0])
    replay.actions.forEach((action, i) => { state = stepGame(game, state, action); assert.deepEqual(state, replay.states[i + 1]) })
    assert.equal(isGoal(game, state), replay.reached_goal)
  })
}
