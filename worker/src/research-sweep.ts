import { createClient } from '@supabase/supabase-js'
import { processJob } from './process-job'
import { isAutonomousResearchDue } from './autonomous-synthesis'

const url = process.env.SUPABASE_URL
const key = process.env.SUPABASE_SERVICE_ROLE_KEY

if (!url || !key) {
  console.error('SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required')
  process.exit(1)
}

const supabase = createClient(url, key)

type SearchState = {
  continuing?: boolean
  next_attempt_at?: string | null
}

type ResearchJobRow = {
  id: string
  search_state?: SearchState | null
}

const PAGE_SIZE = 20
const MAX_PAGES = 5
const MAX_DUE_JOBS = 5

async function main() {
  const now = Date.now()
  const due: ResearchJobRow[] = []

  // `result` contains the complete search trace and can be very large. Fetching
  // 100 full envelopes caused Postgres statement timeouts once the research
  // queue grew. Project only searchState and scan in bounded pages instead.
  for (let page = 0; page < MAX_PAGES && due.length < MAX_DUE_JOBS; page++) {
    const from = page * PAGE_SIZE
    const { data, error } = await supabase
      .from('generation_jobs')
      .select('id,search_state:result->searchState,updated_at')
      .eq('mode', 'mathos_discovery')
      .eq('status', 'processing')
      .order('updated_at', { ascending: true })
      .range(from, from + PAGE_SIZE - 1)
    if (error) throw error

    const rows = (data ?? []) as ResearchJobRow[]
    for (const row of rows) {
      if (isAutonomousResearchDue(row.search_state, new Date(now))) due.push(row)
      if (due.length >= MAX_DUE_JOBS) break
    }
    if (rows.length < PAGE_SIZE) break
  }
  if (!due.length) {
    console.log('No autonomous research job is due.')
    return
  }
  for (const job of due) {
    console.log(`Resuming autonomous research job ${job.id}`)
    await processJob(String(job.id))
  }
}

main().then(() => process.exit(0)).catch(error => {
  console.error(error)
  process.exit(1)
})
