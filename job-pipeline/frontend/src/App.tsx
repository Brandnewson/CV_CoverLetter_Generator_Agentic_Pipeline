import { useEffect, useMemo, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { usePlan } from '@/hooks/usePlan'
import { useQueuedJobs } from '@/hooks/useQueuedJobs'
import { useApproveSlot, useUnapproveSlot, useRephrase, useRestoreBullet } from '@/hooks/useRephrase'
import { useApproveCV } from '@/hooks/useApproveCV'
import { useSaveEnrichment } from '@/hooks/useSaveEnrichment'
import { TopBar } from '@/components/TopBar'
import { JobPanel } from '@/components/JobPanel'
import { BulletBuilder } from '@/components/BulletBuilder'
import { AlternativesPanel } from '@/components/AlternativesPanel'
import { ResizableColumns } from '@/components/ResizableColumns'
import type { EnrichmentDraft, Section } from '@/types'

const EMPTY_DRAFT: EnrichmentDraft = {
  job_description_raw: '',
  company_description_raw: '',
  enrichment_keywords: {
    technologies: [],
    skills: [],
    abilities: [],
  },
}

export default function App() {
  const { jobId: jobIdParam } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  const jobId = jobIdParam ? parseInt(jobIdParam, 10) : undefined

  const { data: plan, isLoading: isPlanLoading } = usePlan(jobId)
  const { data: queuedJobs = [] } = useQueuedJobs()
  
  const approveSlot = useApproveSlot(jobId ?? 0)
  const unapproveSlot = useUnapproveSlot(jobId ?? 0)
  const rephrase = useRephrase(jobId ?? 0)
  const restoreBullet = useRestoreBullet(jobId ?? 0)
  const approveCV = useApproveCV(jobId ?? 0)
  const saveEnrichment = useSaveEnrichment(jobId ?? 0)

  const [rephrasingSlotIndex, setRephrasingSlotIndex] = useState<number | null>(null)
  const [draft, setDraft] = useState<EnrichmentDraft>(EMPTY_DRAFT)
  const [savedDraft, setSavedDraft] = useState<EnrichmentDraft>(EMPTY_DRAFT)
  const [saveError, setSaveError] = useState<string | null>(null)

  useEffect(() => {
    if (!plan?.job) return
    const nextDraft: EnrichmentDraft = {
      job_description_raw: plan.job.job_description_raw ?? '',
      company_description_raw: plan.job.company_description_raw ?? '',
      enrichment_keywords: {
        technologies: plan.job.enrichment_keywords?.technologies ?? [],
        skills: plan.job.enrichment_keywords?.skills ?? [],
        abilities: plan.job.enrichment_keywords?.abilities ?? [],
      },
    }
    setDraft(nextDraft)
    setSavedDraft(nextDraft)
    setSaveError(null)
  }, [plan?.job])

  const isDraftDirty = useMemo(() => {
    return JSON.stringify(draft) !== JSON.stringify(savedDraft)
  }, [draft, savedDraft])

  const canRephrase = !isDraftDirty && !saveEnrichment.isPending

  // Calculate accepted count
  const allSlots = plan 
    ? [...plan.work_experience_slots, ...plan.technical_project_slots]
    : []
  const slotsWithCandidates = allSlots.filter(s => s.current_candidate !== null)
  const acceptedCount = slotsWithCandidates.filter(s => s.is_approved).length
  const totalSlots = slotsWithCandidates.length

  const handleApproveSlot = (slotIndex: number, section: Section) => {
    approveSlot.mutate({ slotIndex, section })
  }

  const handleUnapproveSlot = (slotIndex: number) => {
    unapproveSlot.mutate({ slotIndex })
  }

  const handleRephraseSlot = async (slotIndex: number, section: Section, subsection: string) => {
    if (!jobId || !canRephrase) return
    setRephrasingSlotIndex(slotIndex)
    try {
      await rephrase.mutateAsync({
        job_id: jobId,
        slot_index: slotIndex,
        section,
        subsection,
      })
    } finally {
      setRephrasingSlotIndex(null)
    }
  }

  const handleSaveDraft = async () => {
    if (!jobId || !isDraftDirty) return
    try {
      setSaveError(null)
      await saveEnrichment.mutateAsync(draft)
      setSavedDraft(draft)
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : 'Failed to save enrichment')
    }
  }

  const handleRestoreBullet = (slotIndex: number, historyIndex: number) => {
    restoreBullet.mutate({ slotIndex, historyIndex })
  }

  const handleApproveAll = () => {
    slotsWithCandidates.forEach(slot => {
      if (!slot.is_approved) {
        approveSlot.mutate({ slotIndex: slot.slot_index, section: slot.section })
      }
    })
  }

  const handleGenerateCV = async () => {
    if (!plan) return
    try {
      await approveCV.mutateAsync({ plan })
      // Download after successful generation
      if (jobId) {
        window.open(`/api/cv/${jobId}/download`, '_blank')
      }
    } catch (error) {
      console.error('Failed to generate CV:', error)
    }
  }

  const handleSelectJob = (newJobId: number) => {
    navigate(`/build/${newJobId}`)
  }

  return (
    <div className="h-screen flex flex-col bg-bg-base">
      <TopBar
        plan={plan}
        isLoading={isPlanLoading}
        acceptedCount={acceptedCount}
        totalSlots={totalSlots}
        onGenerateCV={handleGenerateCV}
        isGenerating={approveCV.isPending}
      />

      <ResizableColumns
        initialLeftWidth={280}
        initialRightWidth={240}
        minLeftWidth={200}
        minRightWidth={160}
        minCenterWidth={480}
        left={
          <JobPanel
            plan={plan}
            job={plan?.job}
            isLoading={isPlanLoading}
            queuedJobs={queuedJobs}
            currentJobId={jobId ?? 0}
            onSelectJob={handleSelectJob}
            draft={draft}
            onChangeDraft={setDraft}
            onSaveDraft={handleSaveDraft}
            isSavingDraft={saveEnrichment.isPending}
            isDraftDirty={isDraftDirty}
            saveError={saveError}
          />
        }
        center={
          <BulletBuilder
            plan={plan}
            isLoading={isPlanLoading}
            onApproveSlot={handleApproveSlot}
            onUnapproveSlot={handleUnapproveSlot}
            onRephraseSlot={handleRephraseSlot}
            onRestoreBullet={handleRestoreBullet}
            onApproveAll={handleApproveAll}
            isRephrasing={rephrase.isPending}
            rephrasingSlotIndex={rephrasingSlotIndex}
            canRephrase={canRephrase}
          />
        }
        right={
          <AlternativesPanel />
        }
      />
    </div>
  )
}
