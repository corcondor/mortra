import type { MetadataRoute } from 'next'

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date()
  return [
    { url: 'https://mortra.ai/', lastModified, changeFrequency: 'weekly', priority: 1 },
    { url: 'https://mortra.ai/ja', lastModified, changeFrequency: 'weekly', priority: 1 },
    { url: 'https://mortra.ai/mortra', lastModified, changeFrequency: 'weekly', priority: 0.9 },
    { url: 'https://mortra.ai/research', lastModified, changeFrequency: 'weekly', priority: 0.8 },
    { url: 'https://mortra.ai/ja/research', lastModified, changeFrequency: 'weekly', priority: 0.8 },
    { url: 'https://mortra.ai/research/engineering-geometry', lastModified, changeFrequency: 'monthly', priority: 0.75 },
    { url: 'https://mortra.ai/ja/research/engineering-geometry', lastModified, changeFrequency: 'monthly', priority: 0.75 },
  ]
}
