/**
 * SNS用アイコンを、証明168手から書き出す。
 * 円形に切り抜かれる媒体（X / Instagram / YouTube）は、
 * グリッドが内接円に収まるよう pad を上げた版を使う。
 */
import sharp from 'sharp'
import { writeFileSync } from 'node:fs'

const COLOR = { construct:'#ff9d2e', theorem:'#ff5fb0', algebra:'#ffffff', close:'#4dffa0', numeric:'#4fc3ff' }
const H = { close:1, algebra:0.78, theorem:0.62, construct:0.42, numeric:0.24 }
const kind = r => r==='r04'?'close' : r==='ar'?'algebra' : /^r\d+$/.test(r)?'theorem'
                : r==='Numerical check'?'numeric' : 'construct'

const counts = [['By construction',17],['Numerical check',42],['ignore',35],['ar',36],
  ['by reflexivity',5],['r63',7],['r53',7],['r82',6],['r13',4],['r72',2],['r28',2],
  ['r56',1],['r55',1],['r62',1],['r52',1]]
const bag = []; counts.forEach(([r,n]) => { for (let i=0;i<n;i++) bag.push(r) })
let seed = 20110811
const rnd = () => (seed = (seed*1103515245+12345) & 0x7fffffff) / 0x7fffffff
const SEQ = []; while (bag.length) SEQ.push(bag.splice(Math.floor(rnd()*bag.length),1)[0])
SEQ.push('r04') // 最後は必ず円を閉じた一手

function svg({ cols, pad, radius }) {
  const gap = 1.6, rows = Math.ceil(SEQ.length/cols), inner = 100 - pad*2
  const cw = (inner - gap*(cols-1))/cols, rh = (inner - gap*(rows-1))/rows
  const bars = SEQ.map((rule,i) => {
    const k = kind(rule), h = rh*H[k]
    const x = pad + (i%cols)*(cw+gap)
    const y = pad + Math.floor(i/cols)*(rh+gap) + (rh-h)
    return `<rect x="${x.toFixed(2)}" y="${y.toFixed(2)}" width="${cw.toFixed(2)}" height="${h.toFixed(2)}" fill="${COLOR[k]}" rx="0.8"/>`
  }).join('')
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect width="100" height="100" rx="${radius}" fill="#0b0f13"/>${bars}</svg>`
}

const square = svg({ cols:13, pad:9,  radius:4 })
const round  = svg({ cols:11, pad:16, radius:0 })
writeFileSync('brand/mortra-mark-square.svg', square)
writeFileSync('brand/mortra-mark-round.svg',  round)

const jobs = [
  ['brand/icon-x-400.png',          round,  400],
  ['brand/icon-instagram-320.png',  round,  320],
  ['brand/icon-youtube-800.png',    round,  800],
  ['brand/icon-github-460.png',     square, 460],
  ['brand/icon-master-1024.png',    square, 1024],
]
for (const [out, src, size] of jobs) {
  await sharp(Buffer.from(src)).resize(size, size).png({ compressionLevel: 9 }).toFile(out)
  console.log(`  ${out.padEnd(34)} ${size}x${size}`)
}
