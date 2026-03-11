import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import type { ProfileUploads, ParseResult, ConfirmResult, ConfirmedSection, UploadType } from '@/types'

export function useProfileUploads() {
  return useQuery<ProfileUploads>({
    queryKey: ['profile', 'uploads'],
    queryFn: async () => {
      const res = await axios.get('/api/profile/uploads')
      return res.data
    },
    staleTime: 10_000,
  })
}

export function useUploadFile() {
  const queryClient = useQueryClient()
  return useMutation<void, Error, { file: File; uploadType: UploadType }>({
    mutationFn: async ({ file, uploadType }) => {
      const form = new FormData()
      form.append('file', file)
      form.append('upload_type', uploadType)
      await axios.post('/api/profile/upload', form)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profile', 'uploads'] })
    },
  })
}

export function useDeleteUpload() {
  const queryClient = useQueryClient()
  return useMutation<void, Error, { uploadType: UploadType; filename: string }>({
    mutationFn: async ({ uploadType, filename }) => {
      await axios.delete(`/api/profile/uploads/${uploadType}/${encodeURIComponent(filename)}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profile', 'uploads'] })
    },
  })
}

export function useParseCV() {
  return useMutation<ParseResult, Error, string>({
    mutationFn: async (filename) => {
      const res = await axios.post('/api/profile/parse', { filename })
      return res.data
    },
  })
}

export function useConfirmSections() {
  const queryClient = useQueryClient()
  return useMutation<ConfirmResult, Error, { filename: string; sections: ConfirmedSection[] }>({
    mutationFn: async ({ filename, sections }) => {
      const res = await axios.post('/api/profile/confirm', { source_filename: filename, sections })
      return res.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['suggestions'] })
      queryClient.invalidateQueries({ queryKey: ['profile', 'uploads'] })
    },
  })
}
