import { useMemo, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import type { DragBulletPayload, SuggestionsResponse } from '@/types'

const DRAG_BULLET_MIME = 'application/x-cv-bullet'

interface AlternativesPanelProps {
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

function CustomBulletComposer() {
  const [text, setText] = useState('')
  const [customBullets, setCustomBullets] = useState<string[]>([])

  const charCount = text.length
  const isOverHardLimit = charCount > 120
  const ratio = Math.min(100, Math.round((charCount / 120) * 100))
  const barColor = isOverHardLimit
    ? 'bg-status-error'
    : charCount > 110
    ? 'bg-status-warn'
    : 'bg-status-ok'

  const addCustomBullet = () => {
    const value = text.trim()
    if (!value || value.length > 120) return
    setCustomBullets((prev) => [value, ...prev])
    setText('')
  }

  return (
    <Card className="p-3 border-border-default bg-bg-base space-y-2">
      <p className="text-[10px] uppercase tracking-wider text-text-muted">Write Your Own</p>
      <textarea
        value={text}
        onChange={(event) => setText(event.target.value)}
        rows={3}
        placeholder="Write a new bullet line…"
        className="w-full resize-none rounded-md border border-border-default bg-bg-surface px-2 py-1.5 text-xs text-text-primary outline-none focus:border-accent-border"
      />
      <div className="space-y-1">
        <div className="h-1.5 w-full rounded-full bg-bg-elevated overflow-hidden">
          <div className={`h-full transition-[width] duration-200 ${barColor}`} style={{ width: `${ratio}%` }} />
        </div>
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-text-muted">Soft 110 / Hard 120</span>
          <span className={`text-[10px] font-mono ${isOverHardLimit ? 'text-status-error' : charCount > 110 ? 'text-status-warn' : 'text-status-ok'}`}>
            {charCount}/120
          </span>
        </div>
      </div>
      <button
        type="button"
        onClick={addCustomBullet}
        disabled={!text.trim() || isOverHardLimit}
        className="h-7 px-2 rounded-md text-[10px] border border-border-default text-text-primary disabled:opacity-40 disabled:cursor-not-allowed hover:border-accent-border"
      >
        Add custom bullet
      </button>

      {customBullets.length > 0 && (
        <div className="space-y-2 pt-1">
          <p className="text-[10px] uppercase tracking-wider text-text-muted">Custom bullets</p>
          {customBullets.map((bullet, index) => (
            <BulletCard
              key={`${bullet}-${index}`}
              text={bullet}
              source="story_draft"
              keywords={[]}
              overSoftLimit={bullet.length > 110}
            />
          ))}
        </div>
      )}
    </Card>
  )
}

export function AlternativesPanel({ isUnlocked, suggestions, isLoading, isRefreshing, error }: AlternativesPanelProps) {
  const groups = useMemo(() => {
    if (!suggestions) return []
    return [
      {
        sectionLabel: 'Work Experience',
        items: suggestions.sections.work_experience,
      },
      {
        sectionLabel: 'Technical Projects',
        items: suggestions.sections.technical_projects,
      },
    ]
  }, [suggestions])

  return (
    <div className="h-full p-4 bg-bg-surface border-l border-border-subtle overflow-y-auto">
      <h2 className="text-xs tracking-wider text-text-muted uppercase mb-4">Alternatives</h2>

      {!isUnlocked && (
        <Card className="border-dashed border-border-subtle bg-transparent p-4">
          <p className="text-xs text-text-muted text-center">
            Confirm job details first. Suggested bullets will be generated from your stories and profile.
          </p>
        </Card>
      )}

      {isUnlocked && (
        <div className="space-y-4">
          <CustomBulletComposer />

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
                            {subsection.suggestions.length}/{subsection.target_suggestion_count}
                          </span>
                        </div>
                        <div className="space-y-2">
                          {subsection.suggestions.map((suggestion, idx) => (
                            <BulletCard
                              key={`${subsection.subsection}-${idx}-${suggestion.text}`}
                              text={suggestion.text}
                              source="story_draft"
                              keywords={suggestion.keywords_targeted}
                              overSoftLimit={suggestion.over_soft_limit}
                            />
                          ))}
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
