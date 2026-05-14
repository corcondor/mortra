import crypto from 'crypto'

export function percent(value: string) {
  return encodeURIComponent(value)
    .replace(/[!'()*]/g, c => `%${c.charCodeAt(0).toString(16).toUpperCase()}`)
}

export function buildOAuthHeader(
  method: 'GET' | 'POST',
  url: string,
  consumerKey: string,
  consumerSecret: string,
  extraParams: Record<string, string> = {},
  tokenSecret = '',
) {
  const oauth: Record<string, string> = {
    oauth_consumer_key:     consumerKey,
    oauth_nonce:            crypto.randomBytes(16).toString('hex'),
    oauth_signature_method: 'HMAC-SHA1',
    oauth_timestamp:        Math.floor(Date.now() / 1000).toString(),
    oauth_version:          '1.0',
    ...extraParams,
  }

  const normalized = Object.entries(oauth)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([k, v]) => `${percent(k)}=${percent(v)}`)
    .join('&')

  const base       = [method, url, normalized].map(percent).join('&')
  const signingKey = `${percent(consumerSecret)}&${percent(tokenSecret)}`
  const signature  = crypto.createHmac('sha1', signingKey).update(base).digest('base64')

  return 'OAuth ' + Object.entries({ ...oauth, oauth_signature: signature })
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([k, v]) => `${percent(k)}="${percent(v)}"`)
    .join(', ')
}
