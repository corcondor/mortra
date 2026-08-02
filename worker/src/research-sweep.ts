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

async function main() {
  const { data, error } = await supabase
    .from('generation_jobs')
    .select('id,result,updated_at')
    .eq('mode', 'mathos_discovery')
    .eq('status', 'processing')
    .order('updated_at', { ascending: true })
    .limit(100)
  if (error) throw error

  const now = Date.now()
  const due = (data ?? []).filter(row => {
    const result = row.result as { searchState?: SearchState } | null
    const state = result?.searchState
    return isAutonomousResearchDue(state, new Date(now))
  }).slice(0, 5)
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
