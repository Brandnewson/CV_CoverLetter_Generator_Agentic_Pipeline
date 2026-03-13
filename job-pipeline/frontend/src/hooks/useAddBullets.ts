import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import type { AddBulletsResponse, CVSelectionPlan, UserBulletInput } from '@/types'

export function useAddUserBullets(jobId: number) {
  const queryClient = useQueryClient()

  return useMutation<AddBulletsResponse, Error, UserBulletInput[]>({
    mutationFn: async (bullets) => {
      const response = await axios.post('/api/bullets/add', {
        job_id: jobId,
        bullets,
      })
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['suggestions', jobId] })
    },
  })
}

export function useRefreshPlan(jobId: number) {
  const queryClient = useQueryClient()

  return useMutation<CVSelectionPlan, Error, void>({
    mutationFn: async () => {
      const response = await axios.post(`/api/plan/${jobId}/refresh`)
      return response.data
    },
    onSuccess: (data) => {
      queryClient.setQueryData(['plan', jobId], data)
      queryClient.invalidateQueries({ queryKey: ['suggestions', jobId] })
    },
  })
}
