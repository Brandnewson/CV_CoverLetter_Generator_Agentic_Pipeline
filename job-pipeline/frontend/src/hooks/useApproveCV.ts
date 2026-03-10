import { useMutation } from '@tanstack/react-query'
import axios from 'axios'
import type { ApproveResponse, CVSelectionPlan } from '@/types'

interface ApprovePayload {
  plan: CVSelectionPlan
}

export function useApproveCV(jobId: number) {
  return useMutation<ApproveResponse, Error, ApprovePayload>({
    mutationFn: async ({ plan }) => {
      // Collect approved bullets from all slots
      const allSlots = [...plan.work_experience_slots, ...plan.technical_project_slots]
      const approvedBullets = allSlots
        .filter((slot) => slot.is_approved && slot.current_candidate)
        .map((slot) => ({
          slot_index: slot.slot_index,
          section: slot.section,
          subsection: slot.subsection,
          text: slot.current_candidate!.text,
          source: slot.current_candidate!.source,
          rephrase_generation: slot.current_candidate!.rephrase_generation,
        }))

      const response = await axios.post(`/api/approve/${jobId}`, {
        user_id: plan.user_id,
        approved_bullets: approvedBullets,
        hidden_projects: plan.projects_to_hide,
        session_timestamp: new Date().toISOString(),
      })
      return response.data
    },
  })
}

export function useDownloadCV(jobId: number) {
  return useMutation<void, Error, void>({
    mutationFn: async () => {
      // Trigger download by opening the URL
      window.open(`/api/cv/${jobId}/download`, '_blank')
    },
  })
}
