import { runAutonomousSynthesis } from './autonomous-synthesis.ts'
const parents = [
  { id: 'p1', statement: '三角形 ABC において AB=7, BC=5, CA=3 とする。cos A を求めよ。', answer: '11/14', solution: '余弦定理を用いる' },
  { id: 'p2', statement: '三角形 ABC の外接円半径 R を求めよ。', answer: 'R', solution: '正弦定理を用いる' },
]
const r = runAutonomousSynthesis(parents as never, 4)
console.log('列挙 terms       :', r.enumeration.terms.length)
console.log('到達 goals       :', r.enumeration.goals.length)
console.log('生成 cards       :', r.cards.length)
console.log('strategy attempts:')
for (const a of r.attempts) console.log(`  ${a.strategy_id}: applicable=${a.applicable} cards=${a.cards}\n    ${a.reason}`)
