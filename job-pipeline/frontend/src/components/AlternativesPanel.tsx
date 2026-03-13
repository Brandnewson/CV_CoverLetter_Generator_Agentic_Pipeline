import { useMemo, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useAddUserBullets, useRefreshPlan } from '@/hooks/useAddBullets'
import type { CVSelectionPlan, DragBulletPayload, Section, SuggestedBullet, SuggestionsResponse, UserBulletInput } from '@/types'

const DRAG_BULLET_MIME = 'application/x-cv-bullet'

interface AlternativesPanelProps {
  plan: CVSelectionPlan | undefined
  jobId: number
  isUnlocked: boolean
  suggestions: SuggestionsResponse | undefined
  isLoading: boolean
  isRefreshing: boolean
  error: string | null
}

function BulletCard({
  text,
  source,
  keywords,
  overSoftLimit,
}: {
  text: string
  source: DragBulletPayload['source']
  keywords: string[]
  overSoftLimit: boolean
}) {
  const payload: DragBulletPayload = {
    text,
    source,
    keywords_targeted: keywords,
  }

  return (
    <button
      type="button"
      draggable
      onDragStart={(event) => {
        const encoded = JSON.stringify(payload)
        event.dataTransfer.setData(DRAG_BULLET_MIME, encoded)
        event.dataTransfer.setData('text/plain', text)
        event.dataTransfer.effectAllowed = 'move'
      }}
      className="w-full text-left rounded-md border border-border-default bg-bg-base px-2.5 py-2 cursor-grab active:cursor-grabbing active:opacity-50 hover:opacity-80 hover:border-dashed hover:border-accent-border transition-opacity duration-100"
      title="Drag into a middle slot to replace that bullet"
    >
      <p className="text-xs text-text-primary font-mono leading-relaxed">{text}</p>
      <div className="mt-2 flex items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-1">
          {keywords.slice(0, 3).map((keyword) => (
            <Badge
              key={`${text}-${keyword}`}
              variant="outline"
              className="text-[9px] h-4 px-1 bg-accent-subtle text-accent-color border-accent-border"
            >
              {keyword}
            </Badge>
          ))}
        </div>
        <span className={`text-[10px] font-mono ${overSoftLimit ? 'text-status-warn' : 'text-text-muted'}`}>
          {text.length}ch
        </span>
      </div>
    </button>
  )
}

function SkeletonBulletCard() {
  return (
    <div className="rounded-md border border-border-default bg-bg-base px-2.5 py-2 space-y-2 animate-pulse">
      <div className="h-3 w-full rounded bg-bg-elevated" />
      <div className="h-3 w-3/4 rounded bg-bg-elevated" />
      <div className="flex items-center gap-1 mt-1">
        <div className="h-4 w-12 rounded bg-bg-elevated" />
        <div className="h-4 w-10 rounded bg-bg-elevated" />
      </div>
    </div>
  )
}

function SkeletonSection({ label }: { label: string }) {
  return (
    <Card className="p-3 border-border-default bg-bg-base space-y-3">
      <p className="text-[10px] uppercase tracking-wider text-text-muted">{label}</p>
      <div className="space-y-2">
        <SkeletonBulletCard />
        <SkeletonBulletCard />
        <SkeletonBulletCard />
      </div>
    </Card>
  )
}

export function AlternativesPanel({ plan, jobId, isUnlocked, suggestions, isLoading, isRefreshing, error }: AlternativesPanelProps) {
  const [draftText, setDraftText] = useState('')
  const [selectedKey, setSelectedKey] = useState('')
  const [pendingBullets, setPendingBullets] = useState<UserBulletInput[]>([])
  const [mode, setMode] = useState<'existing' | 'new_project'>('existing')
  const [newProjectName, setNewProjectName] = useState('')

  const addBullets = useAddUserBullets(jobId)
  const refreshPlan = useRefreshPlan(jobId)

  const subsectionOptions = useMemo(() => {
    if (!plan) return [] as { key: string; section: Section; subsection: string }[]

    const options: { key: string; section: Section; subsection: string }[] = []
    const seen = new Set<string>()
    const allSlots = [...plan.work_experience_slots, ...plan.technical_project_slots]
    for (const slot of allSlots) {
      const key = `${slot.section}::${slot.subsection}`
      if (seen.has(key)) continue
      seen.add(key)
      options.push({ key, section: slot.section, subsection: slot.subsection })
    }
    return options
  }, [plan])

  const selectedOption = subsectionOptions.find((option) => option.key === selectedKey) ?? subsectionOptions[0]

  const existingSlotTexts = useMemo(() => {
    if (!plan) return new Set<string>()
    const set = new Set<string>()
    const allSlots = [...plan.work_experience_slots, ...plan.technical_project_slots]
    for (const slot of allSlots) {
      if (slot.current_candidate?.text) {
        set.add(slot.current_candidate.text.trim().toLowerCase())
      }
    }
    return set
  }, [plan])

  const addPendingBullet = () => {
    const text = draftText.trim()
    if (!text) return

    if (mode === 'existing') {
      if (!selectedOption) return
      setPendingBullets((prev) => [
        {
          text,
          section: selectedOption.section,
          subsection: selectedOption.subsection,
        },
        ...prev,
      ])
    } else {
      const projectName = newProjectName.trim()
      if (!projectName) return
      setPendingBullets((prev) => [
        {
          text,
          section: 'technical_projects',
          subsection: projectName,
        },
        ...prev,
      ])
    }
    setDraftText('')
  }

  const handleRefreshCv = async () => {
    if (!pendingBullets.length || !jobId) return
    await addBullets.mutateAsync(pendingBullets)
    await refreshPlan.mutateAsync()
    setPendingBullets([])
  }

  const isRefreshingCv = addBullets.isPending || refreshPlan.isPending

  const groups = useMemo(() => {
    if (!suggestions) return []
    const mergeBullets = (subsection: { suggestions: SuggestedBullet[]; existing_matches?: SuggestedBullet[] }) => {
      const merged = [...(subsection.existing_matches ?? []), ...subsection.suggestions]
      const dedup = new Map<string, SuggestedBullet>()
      for (const bullet of merged) {
        const key = bullet.text.trim().toLowerCase()
        if (!key || existingSlotTexts.has(key)) continue
        if (!dedup.has(key)) dedup.set(key, bullet)
      }
      return Array.from(dedup.values())
    }

    return [
      {
        sectionLabel: 'Work Experience',
        items: suggestions.sections.work_experience.map((subsection) => ({
          ...subsection,
          displayBullets: mergeBullets(subsection),
        })),
      },
      {
        sectionLabel: 'Technical Projects',
        items: suggestions.sections.technical_projects.map((subsection) => ({
          ...subsection,
          displayBullets: mergeBullets(subsection),
        })),
      },
    ]
  }, [suggestions, existingSlotTexts])

  const keywordPool = useMemo(() => {
    if (!plan) return []
    return [...(plan.required_keywords ?? []), ...(plan.nice_to_have_keywords ?? [])].map((k) => k.toLowerCase())
  }, [plan])

  const hitCount = (text: string) => {
    const lower = text.toLowerCase()
    const hits = keywordPool.filter((keyword) => keyword && lower.includes(keyword))
    return new Set(hits).size
  }

  return (
    <div className="h-full p-4 bg-bg-surface border-l border-border-subtle overflow-y-auto">
      <h2 className="text-xs tracking-wider text-text-muted uppercase mb-4">Right Panel</h2>

      {!isUnlocked && (
        <Card className="border-dashed border-border-subtle bg-transparent p-4">
          <p className="text-xs text-text-muted text-center">
            Confirm job details first. Then add new bullets and refresh CV placement.
          </p>
        </Card>
      )}

      {isUnlocked && (
        <div className="space-y-4">
          <Card className="p-3 border-border-default bg-bg-base space-y-3">
            <div className="space-y-1">
              <p className="text-[10px] uppercase tracking-wider text-text-muted">Add Bullet Points</p>
              <p className="text-xs text-text-secondary font-medium">
                {plan?.job_title ?? 'Current role'}
                {plan?.company ? ` · ${plan.company}` : ''}
              </p>
            </div>

            {/* Mode toggle */}
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => {
                  setMode('existing')
                  setNewProjectName('')
                }}
                className={`flex-1 text-xs h-7 rounded-md border transition-colors ${
                  mode === 'existing'
                    ? 'bg-accent-color text-white border-accent-color'
                    : 'bg-bg-surface text-text-primary border-border-default hover:border-accent-border'
                }`}
              >
                Existing
              </button>
              <button
                type="button"
                onClick={() => {
                  setMode('new_project')
                  setSelectedKey('')
                }}
                className={`flex-1 text-xs h-7 rounded-md border transition-colors ${
                  mode === 'new_project'
                    ? 'bg-accent-color text-white border-accent-color'
                    : 'bg-bg-surface text-text-primary border-border-default hover:border-accent-border'
                }`}
              >
                New Project
              </button>
            </div>

            <div className="space-y-2">
              {mode === 'existing' ? (
                <select
                  value={selectedOption?.key ?? ''}
                  onChange={(event) => setSelectedKey(event.target.value)}
                  className="w-full rounded-md border border-border-default bg-bg-surface px-2 py-1.5 text-xs text-text-primary outline-none focus:border-accent-border"
                >
                  {subsectionOptions.length === 0 && <option value="">No subsections loaded</option>}
                  {subsectionOptions.map((option) => (
                    <option key={option.key} value={option.key}>
                      {option.section === 'work_experience' ? 'Work Experience' : 'Technical Projects'} · {option.subsection}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  type="text"
                  value={newProjectName}
                  onChange={(event) => setNewProjectName(event.target.value)}
                  placeholder="e.g., AI Chat Dashboard, Mobile App"
                  className="w-full rounded-md border border-border-default bg-bg-surface px-2 py-1.5 text-xs text-text-primary outline-none focus:border-accent-border"
                />
              )}

              <div className="space-y-2">
              <textarea
                value={draftText}
                onChange={(event) => setDraftText(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && event.ctrlKey) {
                    event.preventDefault()
                    addPendingBullet()
                  }
                }}
                placeholder="Type a bullet point here. Press Ctrl+Enter or click Add to add it to the list. Bullets will be rephased when placed in your CV."
                className="w-full h-24 rounded-md border border-border-default bg-bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-border resize-none"
              />
              <Button
                type="button"
                onClick={addPendingBullet}
                disabled={!draftText.trim() || (mode === 'existing' ? !selectedOption : !newProjectName.trim())}
                className="w-full bg-accent-color hover:bg-accent-hover text-white text-xs"
              >
                Add to List
              </Button>
            </div>
            </div>

            {pendingBullets.length > 0 && (
              <div className="space-y-2 pt-1">
                <p className="text-[10px] uppercase tracking-wider text-text-muted">
                  Pending bullets ({pendingBullets.length})
                </p>
                {pendingBullets.map((bullet, index) => (
                  <div key={`${bullet.section}-${bullet.subsection}-${index}`} className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-text-secondary">
                        {bullet.section === 'work_experience' ? 'Work Experience' : 'Technical Projects'} · {bullet.subsection}
                      </span>
                      <button
                        type="button"
                        onClick={() => setPendingBullets((prev) => prev.filter((_, i) => i !== index))}
                        className="text-[10px] text-text-muted hover:text-text-primary"
                      >
                        Remove
                      </button>
                    </div>
                    <BulletCard
                      text={bullet.text}
                      source="story_draft"
                      keywords={[]}
                      overSoftLimit={bullet.text.length > 110}
                    />
                    <p className="text-[10px] text-text-muted">Keyword hits: {hitCount(bullet.text)}</p>
                  </div>
                ))}
              </div>
            )}

            <Button
              type="button"
              onClick={handleRefreshCv}
              disabled={!pendingBullets.length || isRefreshingCv}
              className="w-full bg-accent-color hover:bg-accent-hover text-white"
            >
              {isRefreshingCv ? (
                <>
                  <Loader2 className="mr-2 h-3 w-3 animate-spin" />
                  {addBullets.isPending ? 'Saving points…' : 'Updating suggestions…'}
                </>
              ) : (
                'Enter Points in Bank'
              )}
            </Button>
          </Card>

          <div className="flex items-center gap-2">
            <div className="h-px flex-1 bg-border-subtle" />
            <span className="text-[10px] uppercase tracking-wider text-text-muted">Good fits</span>
            <div className="h-px flex-1 bg-border-subtle" />
          </div>

          {isLoading && (
            <div className="space-y-4">
              <SkeletonSection label="Work Experience" />
              <SkeletonSection label="Technical Projects" />
            </div>
          )}

          {error && (
            <Card className="p-4 border-status-error/50 bg-status-error/5">
              <p className="text-xs text-status-error">{error}</p>
            </Card>
          )}

          {!isLoading && !error && (
            <div className="relative space-y-4">
              {/* Overlay spinner while background refetch is in-flight */}
              {isRefreshing && (
                <div className="absolute inset-0 z-10 flex items-start justify-center pt-8 rounded-md bg-bg-surface/60">
                  <div className="flex items-center gap-1.5 rounded-full bg-bg-elevated border border-border-default px-3 py-1.5 shadow-sm">
                    <Loader2 className="h-3 w-3 animate-spin text-accent-color" />
                    <span className="text-[10px] text-text-secondary">Refreshing…</span>
                  </div>
                </div>
              )}
              <div className={isRefreshing ? 'opacity-40 pointer-events-none' : undefined}>
                {groups.map((group) => (
                  <Card key={group.sectionLabel} className="p-3 border-border-default bg-bg-base space-y-3 mb-4 last:mb-0">
                    <p className="text-[10px] uppercase tracking-wider text-text-muted">{group.sectionLabel}</p>
                    {group.items.length === 0 && (
                      <p className="text-xs text-text-muted">No subsections found.</p>
                    )}
                    {group.items.map((subsection) => (
                      <div key={subsection.subsection} className="space-y-2">
                        <div className="flex items-center justify-between">
                          <p className="text-xs text-text-secondary font-medium">{subsection.subsection}</p>
                          <span className="text-[10px] font-mono text-text-muted">
                            {subsection.displayBullets.length}/{subsection.target_suggestion_count}
                          </span>
                        </div>
                        <div className="space-y-2">
                          {subsection.displayBullets.map((suggestion, idx) => (
                            <BulletCard
                              key={`${subsection.subsection}-${idx}-${suggestion.text}`}
                              text={suggestion.text}
                              source="story_draft"
                              keywords={suggestion.keywords_targeted}
                              overSoftLimit={suggestion.over_soft_limit}
                            />
                          ))}
                          {subsection.displayBullets.length === 0 && (
                            <p className="text-[11px] text-text-muted">No additional matches for this subsection.</p>
                          )}
                        </div>
                      </div>
                    ))}
                  </Card>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
