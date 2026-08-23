import type { MetadataRoute } from 'next'

export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: '*', allow: '/' },
    sitemap: 'https://mortra.vercel.app/sitemap.xml',
    host: 'https://mortra.vercel.app',
  }
}
