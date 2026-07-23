const applicationId = process.env.DISCORD_APPLICATION_ID
const token = process.env.DISCORD_TOKEN
if (!applicationId || !token) {
  throw new Error('DISCORD_APPLICATION_ID and DISCORD_TOKEN are required')
}

const userInstall = process.env.DISCORD_USER_INSTALL === 'true'
const common = {
  integration_types: userInstall ? [0, 1] : [0],
  contexts: userInstall ? [0, 1, 2] : [0, 1],
}

const commands = [
  {
    ...common,
    name: 'sakumon',
    description: 'MathOSで未配信の検証済み数学問題を生成します',
    options: [
      {
        type: 3,
        name: 'domain',
        description: '分野。空欄ならおまかせ',
        required: false,
        choices: [
          { name: '整数・数論', value: 'number_theory' },
          { name: '代数', value: 'algebra' },
          { name: '幾何', value: 'geometry' },
          { name: '確率', value: 'probability' },
          { name: '解析', value: 'analysis' },
          { name: '線形代数', value: 'linear_algebra' },
          { name: '組合せ', value: 'combinatorics' },
          { name: '複素数', value: 'complex' },
        ],
      },
    ],
  },
  {
    ...common,
    name: 'mathos_answer',
    description: '配信済みMathOS問題の解答を表示します',
    options: [
      {
        type: 3,
        name: 'problem_id',
        description: '問題に表示された10文字のID',
        required: true,
        min_length: 10,
        max_length: 10,
      },
    ],
  },
  {
    ...common,
    name: 'mathos_status',
    description: 'MathOSの検証済み問題数と配信状況を表示します',
  },
]

const response = await fetch(
  `https://discord.com/api/v10/applications/${applicationId}/commands`,
  {
    method: 'PUT',
    headers: {
      authorization: `Bot ${token}`,
      'content-type': 'application/json',
    },
    body: JSON.stringify(commands),
  },
)

if (!response.ok) {
  throw new Error(
    `Discord command registration failed (${response.status}): ${await response.text()}`,
  )
}

const registered = await response.json()
console.log(`Registered ${registered.length} global Discord commands.`)
