import type { MetadataRoute } from 'next'

export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: '*', allow: '/' },
    sitemap: 'https://sakumon-web.vercel.app/sitemap.xml',
    host: 'https://sakumon-web.vercel.app',
  }
}
