import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import type { CVSelectionPlan, EnrichmentDraft, SaveEnrichmentResponse } from '@/types'

export function useSaveEnrichment(jobId: number) {
  const queryClient = useQueryClient()

  return useMutation<SaveEnrichmentResponse, Error, EnrichmentDraft>({
    mutationFn: async (body) => {
      const response = await axios.patch(`/api/jobs/${jobId}/enrichment`, body)
      return response.data
    },
    onSuccess: (result) => {
      queryClient.setQueryData<CVSelectionPlan>(['plan', jobId], (old) => {
        if (!old) return old
        return {
          ...old,
          job: result.job,
        }
      })
      queryClient.invalidateQueries({ queryKey: ['plan', jobId] })
    },
  })
}
