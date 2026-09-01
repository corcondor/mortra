import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  reactStrictMode: true,
  outputFileTracingIncludes: {
    '/api/mathos-generate': ['./worker/backend/sympy_fusion.py'],
  },
  experimental: {
    proxyTimeout: 300_000,
  },
  async rewrites() {
    const localSolveUrl = process.env.MORTRA_LOCAL_SOLVE_URL
    if (!localSolveUrl) return []
    return [
      {
        source: '/api/solve',
        destination: `${localSolveUrl.replace(/\/$/, '')}/api/solve`,
      },
    ]
  },
  // KaTeX fonts
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'X-Content-Type-Options', value: 'nosniff' },
        ],
      },
    ]
  },
}

export default nextConfig
