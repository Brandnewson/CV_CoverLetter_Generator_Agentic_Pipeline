import { useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { BulletSlot } from '@/components/BulletSlot'
import type { CVSelectionPlan, Section, BulletSlot as BulletSlotType } from '@/types'

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
    <div className="h-full overflow-y-auto bg-bg-base">
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
    </div>
  )
}
