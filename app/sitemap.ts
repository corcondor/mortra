import type { MetadataRoute } from 'next'

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date()
  return [
    { url: 'https://sakumon-web.vercel.app/', lastModified, changeFrequency: 'weekly', priority: 1 },
    { url: 'https://sakumon-web.vercel.app/mortra', lastModified, changeFrequency: 'weekly', priority: 0.9 },
    { url: 'https://sakumon-web.vercel.app/research', lastModified, changeFrequency: 'weekly', priority: 0.8 },
  ]
}
