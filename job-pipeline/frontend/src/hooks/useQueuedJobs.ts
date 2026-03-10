import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import type { QueuedJob } from '@/types'

export function useQueuedJobs() {
  return useQuery<QueuedJob[]>({
    queryKey: ['queuedJobs'],
    queryFn: async () => {
      const response = await axios.get('/api/jobs/queued')
      return response.data.jobs
    },
    staleTime: 30000, // 30 seconds
  })
}
