import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { Badge } from '@/components/ui/badge'
import { Check, ArrowRight, Loader2, Undo } from 'lucide-react'
import type { BulletSlot as BulletSlotType, Section, BulletSource } from '@/types'

interface BulletSlotProps {
  slot: BulletSlotType
  onApprove: (slotIndex: number, section: Section) => void
  onUnapprove: (slotIndex: number) => void
  onRephrase: (slotIndex: number, section: Section, subsection: string) => void
  onRestore: (slotIndex: number, historyIndex: number) => void
  isRephrasing: boolean
}

function CharCount({ count }: { count: number }) {
  const color =
    count > 120
      ? 'text-status-error'
      : count > 110
      ? 'text-status-warn'
      : count < 90
      ? 'text-status-warn'
      : 'text-text-muted'
  return <span className={`font-mono text-[10px] ${color}`}>{count}ch</span>
}

function SourceBadge({ source }: { source: BulletSource }) {
  const styles: Record<BulletSource, string> = {
    master_bullets: 'bg-source-bank/20 text-source-bank border-source-bank/30',
    story_draft: 'bg-source-draft/20 text-source-draft border-source-draft/30',
    rephrasing: 'bg-source-rephrase/20 text-source-rephrase border-source-rephrase/30',
  }
  const labels: Record<BulletSource, string> = {
    master_bullets: 'bank',
    story_draft: 'draft',
    rephrasing: 'rephrase',
  }
  return (
    <Badge
      variant="outline"
      className={`text-[9px] px-1 py-0 h-4 ${styles[source]}`}
    >
      {labels[source]}
    </Badge>
  )
}

export function BulletSlot({
  slot,
  onApprove,
  onUnapprove,
  onRephrase,
  onRestore,
  isRephrasing,
}: BulletSlotProps) {
  const [showHistory, setShowHistory] = useState(false)
  const { current_candidate, is_approved, rephrase_history, slot_index, section, subsection } = slot

  if (!current_candidate) {
    return (
      <Card className="p-2 bg-bg-elevated border-border-subtle opacity-50">
        <p className="text-xs text-text-muted italic">No bullet available for this slot</p>
      </Card>
    )
  }

  // Accepted (compact) state
  if (is_approved) {
    return (
      <Card className="border-l-2 border-l-status-ok border-border-subtle bg-bg-surface transition-opacity duration-150">
        <Tooltip>
          <TooltipTrigger>
            <div className="p-2 cursor-default text-left w-full">
              <div className="flex items-start gap-2">
                <Check className="h-3 w-3 text-status-ok flex-shrink-0 mt-0.5" />
                <p className="text-xs font-mono text-text-primary truncate flex-1">
                  {current_candidate.text}
                </p>
              </div>
              <div className="flex items-center justify-between mt-1 pl-5">
                <div className="flex items-center gap-1.5">
                  <SourceBadge source={current_candidate.source} />
                  {current_candidate.keyword_hits.slice(0, 2).map((kw) => (
                    <Badge
                      key={kw}
                      variant="outline"
                      className="text-[9px] px-1 py-0 h-4 bg-accent-subtle text-accent-color border-accent-border"
                    >
                      {kw}
                    </Badge>
                  ))}
                  <CharCount count={current_candidate.char_count} />
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    onUnapprove(slot_index)
                  }}
                  className="text-[10px] text-text-muted hover:text-text-primary"
                >
                  undo
                </button>
              </div>
            </div>
          </TooltipTrigger>
          <TooltipContent side="top" className="max-w-md">
            <p className="text-xs font-mono">{current_candidate.text}</p>
          </TooltipContent>
        </Tooltip>
      </Card>
    )
  }

  // Pending (expanded) state
  return (
    <Card className="border-border-default bg-bg-surface">
      <div className="p-3">
        <p className="text-xs font-mono text-text-primary leading-relaxed">
          {current_candidate.text}
        </p>

        <div className="flex items-center justify-between mt-2">
          <div className="flex items-center gap-1.5 flex-wrap">
            <SourceBadge source={current_candidate.source} />
            {current_candidate.keyword_hits.map((kw) => (
              <Badge
                key={kw}
                variant="outline"
                className="text-[9px] px-1 py-0 h-4 bg-accent-subtle text-accent-color border-accent-border"
              >
                {kw}
              </Badge>
            ))}
            <CharCount count={current_candidate.char_count} />
          </div>

          <div className="flex items-center gap-1">
            <Button
              size="sm"
              variant="outline"
              className="h-6 px-2 text-[10px] border-border-default text-text-secondary hover:text-text-primary hover:bg-bg-elevated"
              onClick={() => onRephrase(slot_index, section, subsection)}
              disabled={isRephrasing}
            >
              {isRephrasing ? (
                <Loader2 className="h-3 w-3 animate-spin mr-1" />
              ) : (
                <ArrowRight className="h-3 w-3 mr-1" />
              )}
              Rephrase
            </Button>
            <Button
              size="sm"
              className="h-6 px-2 text-[10px] bg-accent-color hover:bg-accent-hover text-white"
              onClick={() => onApprove(slot_index, section)}
            >
              Accept
            </Button>
          </div>
        </div>

        {/* Rephrase history */}
        {rephrase_history.length > 0 && (
          <div className="mt-2 pt-2 border-t border-border-subtle">
            <button
              onClick={() => setShowHistory(!showHistory)}
              className="text-[10px] text-text-muted hover:text-text-primary"
            >
              {showHistory ? 'Hide' : `${rephrase_history.length} previous version${rephrase_history.length > 1 ? 's' : ''}`}
            </button>
            {showHistory && (
              <div className="mt-2 space-y-1">
                {rephrase_history.map((bullet, idx) => (
                  <div
                    key={idx}
                    className="flex items-start justify-between gap-2 p-1.5 bg-bg-elevated rounded text-xs"
                  >
                    <p className="font-mono text-text-muted truncate flex-1">
                      {bullet.text}
                    </p>
                    <button
                      onClick={() => onRestore(slot_index, idx)}
                      className="text-[10px] text-text-muted hover:text-text-primary flex items-center gap-0.5 flex-shrink-0"
                    >
                      <Undo className="h-3 w-3" />
                      restore
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </Card>
  )
}
