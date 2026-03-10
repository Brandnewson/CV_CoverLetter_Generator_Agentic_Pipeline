import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import type { CVSelectionPlan } from '@/types'

export function usePlan(jobId: number | undefined) {
  return useQuery<CVSelectionPlan>({
    queryKey: ['plan', jobId],
    queryFn: async () => {
      if (!jobId) throw new Error('No job ID')
      const response = await axios.get(`/api/plan/${jobId}`)
      return response.data
    },
    enabled: !!jobId,
    staleTime: Infinity, // Plan doesn't change unless user navigates away
  })
}
