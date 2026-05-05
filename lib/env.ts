/** Vercel 本番環境かどうか（Python スクリプトが使えない） */
export const IS_VERCEL = process.env.VERCEL === '1'

export const LOCAL_ONLY_RESPONSE = () =>
  Response.json(
    { error: 'この機能はローカル環境（localhost:3002）でのみ使用できます。' },
    { status: 503 },
  )
