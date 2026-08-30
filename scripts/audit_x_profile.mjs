import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)))
const endpoint = 'https://api.twitter.com/1.1/account/verify_credentials.json'
const query = { include_entities: 'false', skip_status: 'true' }

function loadEnvFile(file) {
  if (!fs.existsSync(file)) return
  for (const line of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
    const match = /^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$/.exec(line)
    if (!match) continue
    const value = match[2].trim().replace(/^["']|["']$/g, '')
    if (value && !process.env[match[1]]) process.env[match[1]] = value
  }
}

function credentials() {
  loadEnvFile(path.join(root, '.env.local'))
  let config = null
  const configPath = process.env.X_CONFIG_PATH?.trim()
  if (configPath && fs.existsSync(configPath)) {
    try { config = JSON.parse(fs.readFileSync(configPath, 'utf8')) } catch { config = null }
  }
  const values = {
    apiKey: process.env.X_API_KEY?.trim() || config?.consumer_key || '',
    apiSecret: process.env.X_API_SECRET?.trim() || config?.consumer_secret || '',
    accessToken: process.env.X_ACCESS_TOKEN?.trim() || config?.access_token || '',
    accessTokenSecret: process.env.X_ACCESS_TOKEN_SECRET?.trim() || config?.access_token_secret || '',
  }
  const missing = Object.entries(values).filter(([, value]) => !value).map(([key]) => key)
  if (missing.length) throw new Error(`X credentials missing: ${missing.join(', ')}`)
  return values
}

const percent = (value) => encodeURIComponent(value)
  .replace(/[!'()*]/g, (character) => `%${character.charCodeAt(0).toString(16).toUpperCase()}`)

function authorizationHeader(method, url, params, creds) {
  const oauth = {
    oauth_consumer_key: creds.apiKey,
    oauth_nonce: crypto.randomBytes(16).toString('hex'),
    oauth_signature_method: 'HMAC-SHA1',
    oauth_timestamp: Math.floor(Date.now() / 1000).toString(),
    oauth_token: creds.accessToken,
    oauth_version: '1.0',
  }
  const normalized = Object.entries({ ...oauth, ...params })
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, value]) => `${percent(key)}=${percent(value)}`)
    .join('&')
  const base = [method, url, normalized].map(percent).join('&')
  const signingKey = `${percent(creds.apiSecret)}&${percent(creds.accessTokenSecret)}`
  const signature = crypto.createHmac('sha1', signingKey).update(base).digest('base64')
  return 'OAuth ' + Object.entries({ ...oauth, oauth_signature: signature })
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, value]) => `${percent(key)}="${percent(value)}"`)
    .join(', ')
}

async function download(url, file) {
  if (!url) return null
  const response = await fetch(url)
  if (!response.ok) throw new Error(`profile asset download failed: ${response.status}`)
  fs.writeFileSync(file, Buffer.from(await response.arrayBuffer()))
  return path.relative(root, file).replaceAll('\\', '/')
}

const creds = credentials()
const search = new URLSearchParams(query)
const response = await fetch(`${endpoint}?${search}`, {
  headers: { Authorization: authorizationHeader('GET', endpoint, query, creds) },
})
const payload = await response.json().catch(() => null)
if (!response.ok) throw new Error(`X profile audit failed (${response.status}): ${JSON.stringify(payload)}`)

const outputDir = path.join(root, 'brand', 'social')
fs.mkdirSync(outputDir, { recursive: true })
const avatarUrl = payload.profile_image_url_https?.replace('_normal.', '_400x400.') || null
const bannerUrl = payload.profile_banner_url ? `${payload.profile_banner_url}/1500x500` : null
const snapshot = {
  audited_at: new Date().toISOString(),
  id: payload.id_str,
  name: payload.name,
  username: payload.screen_name,
  description: payload.description,
  location: payload.location,
  url: payload.entities?.url?.urls?.[0]?.expanded_url || payload.url || null,
  followers: payload.followers_count,
  following: payload.friends_count,
  posts: payload.statuses_count,
  created_at: payload.created_at,
  profile_image_url: avatarUrl,
  profile_banner_url: bannerUrl,
}
snapshot.local_avatar = await download(avatarUrl, path.join(outputDir, 'current-x-avatar.jpg'))
snapshot.local_banner = await download(bannerUrl, path.join(outputDir, 'current-x-header.jpg'))

const outputPath = path.join(outputDir, 'current-x-profile.json')
fs.writeFileSync(outputPath, `${JSON.stringify(snapshot, null, 2)}\n`)
console.log(JSON.stringify({
  name: snapshot.name,
  username: snapshot.username,
  description: snapshot.description,
  url: snapshot.url,
  followers: snapshot.followers,
  following: snapshot.following,
  posts: snapshot.posts,
  avatar: snapshot.local_avatar,
  banner: snapshot.local_banner,
}, null, 2))
