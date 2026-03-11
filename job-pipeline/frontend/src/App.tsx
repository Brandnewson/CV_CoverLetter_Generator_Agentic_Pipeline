import { useEffect, useMemo, useRef, useState } from 'react'
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
import type { EnrichmentDraft, Job, Section } from '@/types'

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
  const [isEnrichmentConfirmed, setIsEnrichmentConfirmed] = useState(false)
  const [draftSyncVersion, setDraftSyncVersion] = useState(0)
  const initializedJobIdRef = useRef<number | null>(null)

  const isDraftDirty = useMemo(() => {
    return JSON.stringify(draft) !== JSON.stringify(savedDraft)
  }, [draft, savedDraft])

  const toDraft = (job: Job): EnrichmentDraft => ({
    job_description_raw: job.job_description_raw ?? '',
    company_description_raw: job.company_description_raw ?? '',
    enrichment_keywords: {
      technologies: job.enrichment_keywords?.technologies ?? [],
      skills: job.enrichment_keywords?.skills ?? [],
      abilities: job.enrichment_keywords?.abilities ?? [],
    },
  })

  useEffect(() => {
    if (!plan?.job) return
    const loadedJobId = plan.job.id
    const nextDraft = toDraft(plan.job)

    if (initializedJobIdRef.current === loadedJobId) {
      if (!isDraftDirty && !saveEnrichment.isPending) {
        setDraft(nextDraft)
        setSavedDraft(nextDraft)
      }
      return
    }

    initializedJobIdRef.current = loadedJobId
    setDraft(nextDraft)
    setSavedDraft(nextDraft)
    setDraftSyncVersion((version) => version + 1)
    setSaveError(null)
    setIsEnrichmentConfirmed(false)
  }, [plan?.job, isDraftDirty, saveEnrichment.isPending])

  const isInEnrichmentStage = !isEnrichmentConfirmed || isDraftDirty || saveEnrichment.isPending
  const canRephrase = isEnrichmentConfirmed && !isDraftDirty && !saveEnrichment.isPending

  const handleChangeDraft = (nextDraft: EnrichmentDraft) => {
    setDraft(nextDraft)
    if (JSON.stringify(nextDraft) !== JSON.stringify(savedDraft)) {
      setIsEnrichmentConfirmed(false)
    }
  }

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
    if (!jobId) return
    try {
      setSaveError(null)
      const result = await saveEnrichment.mutateAsync(draft)
      const normalizedDraft = toDraft(result.job)
      setDraft(normalizedDraft)
      setSavedDraft(normalizedDraft)
      setDraftSyncVersion((version) => version + 1)
      setIsEnrichmentConfirmed(true)
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
        focusLeftPanel={isInEnrichmentStage}
        overlayContent={
          isInEnrichmentStage ? (
            <>
              <p className="text-sm font-semibold text-text-primary">
                {saveEnrichment.isPending ? 'Confirming job details…' : 'Confirm job details to continue'}
              </p>
              <p className="mt-2 text-xs leading-relaxed text-text-secondary">
                Review the job description, company description, and keyword fields in the left panel first. When they look correct, confirm the job details to unlock rephrasing and bullet selection.
              </p>
            </>
          ) : undefined
        }
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
            onChangeDraft={handleChangeDraft}
            onSaveDraft={handleSaveDraft}
            isSavingDraft={saveEnrichment.isPending}
            isDraftDirty={isDraftDirty}
            saveError={saveError}
            isEnrichmentConfirmed={isEnrichmentConfirmed}
            draftSyncVersion={draftSyncVersion}
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
