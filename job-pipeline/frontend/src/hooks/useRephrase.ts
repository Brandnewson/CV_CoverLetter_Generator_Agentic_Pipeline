import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import type { BulletCandidate, CVSelectionPlan, RephraseRequest, Section } from '@/types'

export function useRephrase(jobId: number) {
  const queryClient = useQueryClient()

  return useMutation<BulletCandidate, Error, RephraseRequest>({
    mutationFn: async (body) => {
      const response = await axios.post('/api/rephrase', body)
      return response.data
    },
    onSuccess: (newCandidate, vars) => {
      // Optimistically update the plan in cache
      queryClient.setQueryData<CVSelectionPlan>(['plan', jobId], (old) => {
        if (!old) return old

        const updateSlots = (slots: typeof old.work_experience_slots) =>
          slots.map((slot) => {
            if (slot.slot_index === vars.slot_index) {
              return {
                ...slot,
                rephrase_history: slot.current_candidate
                  ? [...slot.rephrase_history, slot.current_candidate]
                  : slot.rephrase_history,
                current_candidate: newCandidate,
                is_approved: false, // Reset approval on rephrase
              }
            }
            return slot
          })

        return {
          ...old,
          work_experience_slots: updateSlots(old.work_experience_slots),
          technical_project_slots: updateSlots(old.technical_project_slots),
        }
      })
    },
  })
}

export function useApproveSlot(jobId: number) {
  const queryClient = useQueryClient()

  return useMutation<void, Error, { slotIndex: number; section: Section }>({
    mutationFn: async () => {
      // This is a local-only mutation - approval is tracked in state
      // The actual approval is sent when generating the CV
    },
    onMutate: async ({ slotIndex }) => {
      // Optimistically update the cache
      queryClient.setQueryData<CVSelectionPlan>(['plan', jobId], (old) => {
        if (!old) return old

        const updateSlots = (slots: typeof old.work_experience_slots) =>
          slots.map((slot) =>
            slot.slot_index === slotIndex
              ? { ...slot, is_approved: true }
              : slot
          )

        return {
          ...old,
          work_experience_slots: updateSlots(old.work_experience_slots),
          technical_project_slots: updateSlots(old.technical_project_slots),
        }
      })
    },
  })
}

export function useUnapproveSlot(jobId: number) {
  const queryClient = useQueryClient()

  return useMutation<void, Error, { slotIndex: number }>({
    mutationFn: async () => {},
    onMutate: async ({ slotIndex }) => {
      queryClient.setQueryData<CVSelectionPlan>(['plan', jobId], (old) => {
        if (!old) return old

        const updateSlots = (slots: typeof old.work_experience_slots) =>
          slots.map((slot) =>
            slot.slot_index === slotIndex
              ? { ...slot, is_approved: false }
              : slot
          )

        return {
          ...old,
          work_experience_slots: updateSlots(old.work_experience_slots),
          technical_project_slots: updateSlots(old.technical_project_slots),
        }
      })
    },
  })
}

export function useRestoreBullet(jobId: number) {
  const queryClient = useQueryClient()

  return useMutation<void, Error, { slotIndex: number; historyIndex: number }>({
    mutationFn: async () => {},
    onMutate: async ({ slotIndex, historyIndex }) => {
      queryClient.setQueryData<CVSelectionPlan>(['plan', jobId], (old) => {
        if (!old) return old

        const updateSlots = (slots: typeof old.work_experience_slots) =>
          slots.map((slot) => {
            if (slot.slot_index === slotIndex) {
              const restoredBullet = slot.rephrase_history[historyIndex]
              if (!restoredBullet) return slot

              // Put current candidate into history and restore selected one
              const newHistory = [...slot.rephrase_history]
              newHistory.splice(historyIndex, 1)
              if (slot.current_candidate) {
                newHistory.push(slot.current_candidate)
              }

              return {
                ...slot,
                current_candidate: restoredBullet,
                rephrase_history: newHistory,
                is_approved: false,
              }
            }
            return slot
          })

        return {
          ...old,
          work_experience_slots: updateSlots(old.work_experience_slots),
          technical_project_slots: updateSlots(old.technical_project_slots),
        }
      })
    },
  })
}

export function useReplaceSlotCandidate(jobId: number) {
  const queryClient = useQueryClient()

  return useMutation<
    void,
    Error,
    { slotIndex: number; text: string; source: BulletCandidate['source']; keywords: string[] }
  >({
    mutationFn: async () => {},
    onMutate: async ({ slotIndex, text, source, keywords }) => {
      queryClient.setQueryData<CVSelectionPlan>(['plan', jobId], (old) => {
        if (!old) return old

        const makeCandidate = (slot: (typeof old.work_experience_slots)[number]): BulletCandidate => ({
          text,
          source,
          section: slot.section,
          subsection: slot.subsection,
          tags: [],
          role_families: [],
          relevance_score: 0.6,
          char_count: text.length,
          over_soft_limit: text.length > 110,
          keyword_hits: keywords,
          rephrase_generation: 0,
          warnings: text.length > 110 ? [`Over 110 characters (${text.length})`] : [],
        })

        const updateSlots = (slots: typeof old.work_experience_slots) =>
          slots.map((slot) => {
            if (slot.slot_index !== slotIndex) return slot
            const nextCandidate = makeCandidate(slot)
            return {
              ...slot,
              rephrase_history: slot.current_candidate
                ? [...slot.rephrase_history, slot.current_candidate]
                : slot.rephrase_history,
              current_candidate: nextCandidate,
              is_approved: false,
            }
          })

        return {
          ...old,
          work_experience_slots: updateSlots(old.work_experience_slots),
          technical_project_slots: updateSlots(old.technical_project_slots),
        }
      })
    },
  })
}
