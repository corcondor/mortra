import type { MetadataRoute } from 'next'

export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: '*', allow: '/' },
    sitemap: 'https://mortra.ai/sitemap.xml',
    host: 'https://mortra.ai',
  }
}
