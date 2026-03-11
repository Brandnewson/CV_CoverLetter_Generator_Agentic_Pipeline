import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import type { UserPreferences } from '@/types'

export function usePreferences() {
  return useQuery<UserPreferences>({
    queryKey: ['preferences'],
    queryFn: async () => {
      const res = await axios.get('/api/preferences')
      return res.data
    },
    staleTime: 30_000,
  })
}

export function useSavePreferences() {
  const queryClient = useQueryClient()
  return useMutation<{ status: string }, Error, UserPreferences>({
    mutationFn: async (prefs) => {
      const res = await axios.post('/api/preferences', prefs)
      return res.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['preferences'] })
    },
  })
}
