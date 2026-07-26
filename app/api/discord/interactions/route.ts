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
  helpEmbed,
  mathOSDiscordStats,
  mathosProblemComponents,
  problemEmbed,
  recordDiscordRating,
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
      components: mathosProblemComponents(problem.shortId),
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

async function completeRating(
  interaction: DiscordInteraction,
  shortId: string,
  dimension: string,
  rating: number,
) {
  try {
    await recordDiscordRating(
      shortId,
      dimension,
      rating,
      interactionUserId(interaction),
    )
    const label = dimension === 'diff' ? '難易度' : '新規性'
    await sendDiscordFollowup(interaction, {
      content: `#${shortId} の${label}を ${rating}/5 で評価しました。ありがとう！`,
      flags: 64,
    })
  } catch (error) {
    await sendDiscordFollowup(interaction, {
      content:
        error instanceof Error
          ? `評価の記録に失敗: ${error.message}`
          : '評価を記録できませんでした。',
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
    const stats = await mathOSDiscordStats(interactionUserId(interaction))
    await sendDiscordFollowup(interaction, {
      embeds: [
        {
          title: 'MathOS 作問状況',
          color: 0x0f766e,
          fields: [
            {
              name: '検証済み構造',
              value: String(stats.verifiedPool),
              inline: true,
            },
            {
              name: '配信済み構造',
              value: String(stats.delivered),
              inline: true,
            },
            {
              name: '未配信構造',
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
      case 'help':
        return json({
          type: 4,
          data: {
            embeds: [helpEmbed()],
            flags: 64,
          },
        })
      default:
        return json(immediateMessage('未対応のMathOSコマンドです。'))
    }
  }

  if (interaction.type === DISCORD_INTERACTION.messageComponent) {
    const customId = interaction.data?.custom_id ?? ''
    if (customId.startsWith('mathos_answer:')) {
      const problemId = customId.slice('mathos_answer:'.length)
      after(() => completeAnswer(interaction, problemId))
      return json(deferredResponse(true))
    }
    if (customId.startsWith('mathos_rate:')) {
      const [, shortId, dimension, ratingStr] = customId.split(':')
      const rating = Number(ratingStr)
      after(() => completeRating(interaction, shortId, dimension, rating))
      return json(deferredResponse(true))
    }
  }

  return json(immediateMessage('未対応のDiscord Interactionです。'))
}
