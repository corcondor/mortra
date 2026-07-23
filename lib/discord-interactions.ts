import { createPublicKey, verify } from 'node:crypto'

const ED25519_SPKI_PREFIX = Buffer.from('302a300506032b6570032100', 'hex')

export const DISCORD_INTERACTION = {
  ping: 1,
  applicationCommand: 2,
  messageComponent: 3,
} as const

export const DISCORD_RESPONSE = {
  pong: 1,
  channelMessage: 4,
  deferredChannelMessage: 5,
} as const

export type DiscordOption = {
  name: string
  type: number
  value?: string | number | boolean
  options?: DiscordOption[]
}

export type DiscordInteraction = {
  id: string
  application_id: string
  type: number
  token: string
  guild_id?: string
  channel_id?: string
  member?: { user?: { id: string } }
  user?: { id: string }
  data?: {
    name?: string
    custom_id?: string
    options?: DiscordOption[]
  }
}

export function verifyDiscordRequest(
  rawBody: string,
  signature: string | null,
  timestamp: string | null,
  publicKeyHex: string | undefined,
): boolean {
  if (!signature || !timestamp || !publicKeyHex) return false
  if (!/^[0-9a-f]{64}$/i.test(publicKeyHex)) return false
  if (!/^[0-9a-f]{128}$/i.test(signature)) return false

  try {
    const publicKey = createPublicKey({
      key: Buffer.concat([
        ED25519_SPKI_PREFIX,
        Buffer.from(publicKeyHex, 'hex'),
      ]),
      format: 'der',
      type: 'spki',
    })
    return verify(
      null,
      Buffer.from(timestamp + rawBody),
      publicKey,
      Buffer.from(signature, 'hex'),
    )
  } catch {
    return false
  }
}

export function interactionUserId(interaction: DiscordInteraction): string {
  return interaction.member?.user?.id ?? interaction.user?.id ?? ''
}

export function stringOption(
  interaction: DiscordInteraction,
  optionName: string,
): string | undefined {
  const pending = [...(interaction.data?.options ?? [])]
  while (pending.length > 0) {
    const option = pending.shift()!
    if (option.name === optionName && typeof option.value === 'string') {
      return option.value.trim() || undefined
    }
    pending.push(...(option.options ?? []))
  }
  return undefined
}

export function isAllowedDiscordUser(userId: string): boolean {
  const configured = process.env.DISCORD_MATHOS_ALLOWED_USER_IDS
    ?.split(',')
    .map((value) => value.trim())
    .filter(Boolean)

  return !configured?.length || configured.includes(userId)
}

export function deferredResponse(ephemeral = false) {
  return {
    type: DISCORD_RESPONSE.deferredChannelMessage,
    data: ephemeral ? { flags: 64 } : {},
  }
}

export function immediateMessage(content: string, ephemeral = true) {
  return {
    type: DISCORD_RESPONSE.channelMessage,
    data: {
      content,
      ...(ephemeral ? { flags: 64 } : {}),
    },
  }
}

export async function sendDiscordFollowup(
  interaction: DiscordInteraction,
  data: Record<string, unknown>,
): Promise<void> {
  const response = await fetch(
    `https://discord.com/api/v10/webhooks/${interaction.application_id}/${interaction.token}`,
    {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(data),
    },
  )

  if (!response.ok) {
    const detail = await response.text()
    throw new Error(`Discord follow-up failed (${response.status}): ${detail}`)
  }
}
