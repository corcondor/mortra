import { NextResponse } from 'next/server'
import {
  FALLBACK_COMMITS,
  RESEARCH_REPOSITORY,
  type ResearchCommit,
} from '@/lib/mortra/research-data'

export const revalidate = 60

type GitHubCommit = {
  sha?: string
  html_url?: string
  commit?: {
    message?: string
    author?: { name?: string; date?: string }
  }
  author?: { login?: string } | null
}

function normalizeCommit(commit: GitHubCommit): ResearchCommit | null {
  if (!commit.sha || !commit.html_url || !commit.commit?.message || !commit.commit.author?.date) return null
  return {
    sha: commit.sha.slice(0, 7),
    message: commit.commit.message.split('\n')[0],
    url: commit.html_url,
    date: commit.commit.author.date,
    author: commit.author?.login ?? commit.commit.author.name ?? 'MORTRA',
  }
}

export async function GET() {
  const headers: HeadersInit = {
    Accept: 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28',
    'User-Agent': 'mortra-research-stream',
  }
  if (process.env.GITHUB_TOKEN) headers.Authorization = `Bearer ${process.env.GITHUB_TOKEN}`

  try {
    const query = new URLSearchParams({
      sha: RESEARCH_REPOSITORY.branch,
      per_page: '8',
    })
    const response = await fetch(
      `https://api.github.com/repos/${RESEARCH_REPOSITORY.owner}/${RESEARCH_REPOSITORY.repo}/commits?${query}`,
      {
        headers,
        next: { revalidate: 60 },
        signal: AbortSignal.timeout(6500),
      },
    )

    if (!response.ok) throw new Error(`GitHub returned ${response.status}`)
    const payload = await response.json() as GitHubCommit[]
    const commits = payload.map(normalizeCommit).filter((item): item is ResearchCommit => item !== null)
    if (commits.length === 0) throw new Error('GitHub returned no usable commits')

    return NextResponse.json(
      {
        branch: RESEARCH_REPOSITORY.branch,
        repository: RESEARCH_REPOSITORY.url,
        fetchedAt: new Date().toISOString(),
        source: 'github',
        commits,
      },
      { headers: { 'Cache-Control': 'public, s-maxage=60, stale-while-revalidate=300' } },
    )
  } catch {
    return NextResponse.json(
      {
        branch: RESEARCH_REPOSITORY.branch,
        repository: RESEARCH_REPOSITORY.url,
        fetchedAt: new Date().toISOString(),
        source: 'fallback',
        commits: FALLBACK_COMMITS,
      },
      { headers: { 'Cache-Control': 'public, s-maxage=30, stale-while-revalidate=300' } },
    )
  }
}
