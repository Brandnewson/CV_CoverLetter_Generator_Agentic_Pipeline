import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import type { SuggestionsResponse } from '@/types'

export function useSuggestions(jobId: number | undefined, enabled: boolean) {
  const query = useQuery<SuggestionsResponse>({
    queryKey: ['suggestions', jobId],
    queryFn: async () => {
      if (!jobId) throw new Error('No job ID')
      const response = await axios.get(`/api/suggestions/${jobId}`)
      return response.data
    },
    enabled: !!jobId && enabled,
    // Always treat cached data as stale so a re-enable (e.g. after enrichment save)
    // triggers a fresh network request to pick up new backend-generated suggestions.
    staleTime: 0,
  })

  return {
    data: query.data,
    isLoading: query.isLoading,
    /** True while a background refetch is in-flight (data may already be present). */
    isRefreshing: query.isFetching && !query.isLoading,
    error: query.error,
  }
}
