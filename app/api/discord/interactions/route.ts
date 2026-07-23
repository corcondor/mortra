import { after, NextRequest, NextResponse } from 'next/server'
import {
  deferredResponse,
  DISCORD_INTERACTION,
  DiscordInteraction,
  immediateMessage,
  interactionUserId,
  isAllowedDiscordUser,
  sendDiscordFollowup,
  stringOption,
  verifyDiscordRequest,
} from '@/lib/discord-interactions'
import {
  canonicalDomain,
  deliverMathOSProblem,
  findMathOSSolution,
  mathOSDiscordStats,
  problemEmbed,
  solutionEmbed,
} from '@/lib/mathos-discord'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

function json(body: unknown, status = 200) {
  return NextResponse.json(body, { status })
}

async function completeSakumon(interaction: DiscordInteraction) {
  try {
    const problem = await deliverMathOSProblem({
      interactionId: interaction.id,
      userId: interactionUserId(interaction),
      channelId: interaction.channel_id,
      guildId: interaction.guild_id,
      domain: canonicalDomain(stringOption(interaction, 'domain')),
    })
    await sendDiscordFollowup(interaction, {
      embeds: [problemEmbed(problem)],
      components: [
        {
          type: 1,
          components: [
            {
              type: 2,
              style: 2,
              label: '解答を見る',
              custom_id: `mathos_answer:${problem.shortId}`,
            },
          ],
        },
      ],
    })
  } catch (error) {
    await sendDiscordFollowup(interaction, {
      content:
        error instanceof Error
          ? `MathOSエラー: ${error.message}`
          : 'MathOSで問題を取得できませんでした。',
      flags: 64,
    })
  }
}

async function completeAnswer(
  interaction: DiscordInteraction,
  requestedId?: string,
) {
  try {
    const problemId =
      requestedId ?? stringOption(interaction, 'problem_id') ?? ''
    const problem = await findMathOSSolution(problemId)
    if (!problem) {
      await sendDiscordFollowup(interaction, {
        content: '配信済み問題の10文字IDを確認してください。',
        flags: 64,
      })
      return
    }
    await sendDiscordFollowup(interaction, {
      embeds: [solutionEmbed(problem)],
      flags: 64,
    })
  } catch (error) {
    await sendDiscordFollowup(interaction, {
      content:
        error instanceof Error
          ? `MathOSエラー: ${error.message}`
          : '解答を取得できませんでした。',
      flags: 64,
    })
  }
}

async function completeStatus(interaction: DiscordInteraction) {
  try {
    const stats = await mathOSDiscordStats()
    await sendDiscordFollowup(interaction, {
      embeds: [
        {
          title: 'MathOS 作問状況',
          color: 0x0f766e,
          fields: [
            {
              name: '検証済み候補',
              value: String(stats.verifiedPool),
              inline: true,
            },
            {
              name: '配信済み',
              value: String(stats.delivered),
              inline: true,
            },
            {
              name: '未配信',
              value: String(stats.remaining),
              inline: true,
            },
            {
              name: '配信記録',
              value: stats.persistent ? 'DB接続中' : '内蔵プール',
              inline: true,
            },
          ],
        },
      ],
      flags: 64,
    })
  } catch (error) {
    await sendDiscordFollowup(interaction, {
      content:
        error instanceof Error
          ? `MathOSエラー: ${error.message}`
          : '作問状況を取得できませんでした。',
      flags: 64,
    })
  }
}

export async function POST(request: NextRequest) {
  const rawBody = await request.text()
  const verified = verifyDiscordRequest(
    rawBody,
    request.headers.get('x-signature-ed25519'),
    request.headers.get('x-signature-timestamp'),
    process.env.DISCORD_PUBLIC_KEY,
  )
  if (!verified) return json({ error: 'invalid request signature' }, 401)

  let interaction: DiscordInteraction
  try {
    interaction = JSON.parse(rawBody) as DiscordInteraction
  } catch {
    return json({ error: 'invalid JSON' }, 400)
  }

  if (interaction.type === DISCORD_INTERACTION.ping) {
    return json({ type: 1 })
  }

  const userId = interactionUserId(interaction)
  if (!userId || !isAllowedDiscordUser(userId)) {
    return json(immediateMessage('このMathOS作問機能を使う権限がありません。'))
  }

  if (interaction.type === DISCORD_INTERACTION.applicationCommand) {
    switch (interaction.data?.name) {
      case 'sakumon':
        after(() => completeSakumon(interaction))
        return json(deferredResponse())
      case 'mathos_answer':
        after(() => completeAnswer(interaction))
        return json(deferredResponse(true))
      case 'mathos_status':
        after(() => completeStatus(interaction))
        return json(deferredResponse(true))
      default:
        return json(immediateMessage('未対応のMathOSコマンドです。'))
    }
  }

  if (
    interaction.type === DISCORD_INTERACTION.messageComponent &&
    interaction.data?.custom_id?.startsWith('mathos_answer:')
  ) {
    const problemId = interaction.data.custom_id.slice('mathos_answer:'.length)
    after(() => completeAnswer(interaction, problemId))
    return json(deferredResponse(true))
  }

  return json(immediateMessage('未対応のDiscord Interactionです。'))
}
