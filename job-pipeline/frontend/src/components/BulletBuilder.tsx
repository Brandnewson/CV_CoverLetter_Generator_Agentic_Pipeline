import { useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { BulletSlot } from '@/components/BulletSlot'
import type {
  CVSelectionPlan,
  Section,
  BulletSlot as BulletSlotType,
  DragBulletPayload,
  KeywordCoverageItem,
} from '@/types'

interface BulletBuilderProps {
  plan: CVSelectionPlan | undefined
  isLoading: boolean
  onApproveSlot: (slotIndex: number, section: Section) => void
  onUnapproveSlot: (slotIndex: number) => void
  onRephraseSlot: (slotIndex: number, section: Section, subsection: string) => void
  onRestoreBullet: (slotIndex: number, historyIndex: number) => void
  onApproveAll: () => void
  isRephrasing: boolean
  rephrasingSlotIndex: number | null
  canRephrase: boolean
  onDropSuggestion: (slotIndex: number, payload: DragBulletPayload) => void
}

interface GroupedSlots {
  section: Section
  sectionLabel: string
  subsections: {
    name: string
    slots: BulletSlotType[]
  }[]
}

function groupSlotsBySection(
  workExperienceSlots: BulletSlotType[],
  technicalProjectSlots: BulletSlotType[],
  projectsToHide: string[]
): GroupedSlots[] {
  const groups: GroupedSlots[] = []

  // Group work experience
  if (workExperienceSlots.length > 0) {
    const subsectionMap = new Map<string, BulletSlotType[]>()
    workExperienceSlots.forEach((slot) => {
      const existing = subsectionMap.get(slot.subsection) ?? []
      existing.push(slot)
      subsectionMap.set(slot.subsection, existing)
    })
    groups.push({
      section: 'work_experience',
      sectionLabel: 'Work Experience',
      subsections: Array.from(subsectionMap.entries()).map(([name, slots]) => ({
        name,
        slots: slots.sort((a, b) => a.slot_index - b.slot_index),
      })),
    })
  }

  // Group technical projects
  if (technicalProjectSlots.length > 0) {
    const subsectionMap = new Map<string, BulletSlotType[]>()
    technicalProjectSlots.forEach((slot) => {
      const existing = subsectionMap.get(slot.subsection) ?? []
      existing.push(slot)
      subsectionMap.set(slot.subsection, existing)
    })
    groups.push({
      section: 'technical_projects',
      sectionLabel: 'Technical Projects',
      subsections: Array.from(subsectionMap.entries()).map(([name, slots]) => ({
        name,
        slots: slots.sort((a, b) => a.slot_index - b.slot_index),
        isHidden: projectsToHide.includes(name),
      })),
    })
  }

  return groups
}

export function BulletBuilder({
  plan,
  isLoading,
  onApproveSlot,
  onUnapproveSlot,
  onRephraseSlot,
  onRestoreBullet,
  onApproveAll,
  isRephrasing,
  rephrasingSlotIndex,
  canRephrase,
  onDropSuggestion,
}: BulletBuilderProps) {
  const [hiddenProjects, setHiddenProjects] = useState<Set<string>>(new Set())

  const groups = useMemo(() => {
    if (!plan) return []
    return groupSlotsBySection(
      plan.work_experience_slots,
      plan.technical_project_slots,
      plan.projects_to_hide
    )
  }, [plan])

  // Calculate accepted count (only slots with candidates)
  const slotsWithCandidates = useMemo(() => {
    if (!plan) return []
    return [...plan.work_experience_slots, ...plan.technical_project_slots].filter(
      (s) => s.current_candidate !== null
    )
  }, [plan])

  const acceptedCount = slotsWithCandidates.filter((s) => s.is_approved).length
  const totalSlots = slotsWithCandidates.length

  // Keyword coverage stats
  const coverageStats = useMemo(() => {
    if (!plan?.keyword_bucket_coverage) return null
    const allItems: KeywordCoverageItem[] = [
      ...(plan.keyword_bucket_coverage.technologies ?? []),
      ...(plan.keyword_bucket_coverage.skills ?? []),
      ...(plan.keyword_bucket_coverage.abilities ?? []),
    ]
    if (allItems.length === 0) return null
    const total = allItems.length
    const hit = allItems.filter((item) => item.status === 'hit').length
    const percent = Math.round((hit / total) * 100)
    return { hit, total, percent }
  }, [plan])

  const toggleProjectVisibility = (projectName: string) => {
    setHiddenProjects((prev) => {
      const next = new Set(prev)
      if (next.has(projectName)) {
        next.delete(projectName)
      } else {
        next.add(projectName)
      }
      return next
    })
  }

  if (isLoading) {
    return (
      <div className="h-full overflow-y-auto bg-bg-base">
        <div className="sticky top-0 z-10 bg-bg-surface border-b border-border-subtle px-4 py-2 flex justify-between items-center">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-6 w-20" />
        </div>
        <div className="p-4 space-y-3">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="relative h-full flex flex-col">
      {/* Scrollable content */}
      <div className={`flex-1 overflow-y-auto bg-bg-base ${coverageStats ? 'pb-16' : ''}`}>
      {/* Sticky header */}
      <div className="sticky top-0 z-10 bg-bg-surface border-b border-border-subtle px-4 py-2 flex justify-between items-center">
        <span className="text-xs text-text-secondary">
          {acceptedCount} / {totalSlots} slots accepted
        </span>
        <Button
          variant="ghost"
          size="sm"
          className="text-xs h-6"
          onClick={onApproveAll}
        >
          Accept All
        </Button>
      </div>

      {/* Grouped sections */}
      <div className="p-4 space-y-6">
        {groups.map((group) => (
          <div key={group.section}>
            {/* Section header */}
            <h2 className="text-xs uppercase tracking-wider text-text-muted py-2">
              {group.sectionLabel}
            </h2>

            {/* Subsections */}
            <div className="space-y-4">
              {group.subsections.map((subsection) => {
                const isHidden =
                  group.section === 'technical_projects' &&
                  hiddenProjects.has(subsection.name)

                return (
                  <div key={subsection.name}>
                    {/* Subsection header */}
                    <div className="flex items-center gap-2 py-1 mb-2">
                      <h3 className="text-xs font-medium text-text-secondary">
                        {subsection.name}
                      </h3>
                      {group.section === 'technical_projects' && (
                        <button
                          onClick={() => toggleProjectVisibility(subsection.name)}
                          className="text-[10px] border border-border-default rounded px-2 py-0.5 text-text-muted hover:text-text-primary hover:border-border-strong"
                        >
                          {isHidden ? 'SHOW' : 'HIDE'}
                        </button>
                      )}
                    </div>

                    {/* Slots */}
                    <div
                      className={`space-y-2 ${isHidden ? 'opacity-40' : ''}`}
                    >
                      {subsection.slots.map((slot) => (
                        <BulletSlot
                          key={slot.slot_index}
                          slot={slot}
                          onApprove={onApproveSlot}
                          onUnapprove={onUnapproveSlot}
                          onRephrase={onRephraseSlot}
                          onRestore={onRestoreBullet}
                          isRephrasing={
                            isRephrasing && rephrasingSlotIndex === slot.slot_index
                          }
                          canRephrase={canRephrase}
                          onDropSuggestion={onDropSuggestion}
                        />
                      ))}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        ))}

        {groups.length === 0 && (
          <p className="text-xs text-text-muted text-center py-8">
            No slots to display
          </p>
        )}
      </div>
      </div>{/* end scrollable content */}

      {/* Floating keyword coverage bar */}
      {coverageStats && (
        <div className="absolute bottom-0 left-0 right-0 z-20 px-4 pb-3 pt-1 pointer-events-none">
          <div className="rounded-lg border border-border-default bg-bg-surface/90 backdrop-blur-sm px-4 py-3 shadow-2xl">
            {/* Label row */}
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] uppercase tracking-wider text-text-muted font-mono">
                Keyword coverage
              </span>
              <span
                className="text-[11px] font-mono font-semibold"
                style={{ color: coverageStats.percent >= 80 ? 'var(--status-ok)' : coverageStats.percent >= 50 ? 'var(--status-warn)' : 'var(--status-error)' }}
              >
                {coverageStats.hit} / {coverageStats.total} &nbsp;·&nbsp; {coverageStats.percent}%
              </span>
            </div>
            {/* Bar track */}
            <div className="h-1.5 w-full rounded-full bg-bg-elevated overflow-hidden">
              <div
                className="h-full rounded-full transition-[width] duration-700 ease-out"
                style={{
                  width: `${coverageStats.percent}%`,
                  backgroundColor:
                    coverageStats.percent >= 80
                      ? 'var(--status-ok)'
                      : coverageStats.percent >= 50
                      ? 'var(--status-warn)'
                      : 'var(--status-error)',
                }}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
