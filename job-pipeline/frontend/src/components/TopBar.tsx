import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Loader2 } from 'lucide-react'
import type { CVSelectionPlan, RoleFamily, SeniorityLevel } from '@/types'

interface TopBarProps {
  plan: CVSelectionPlan | undefined
  isLoading: boolean
  acceptedCount: number
  totalSlots: number
  onGenerateCV: () => void
  isGenerating: boolean
}

const roleFamilyLabels: Record<RoleFamily, string> = {
  'motorsport': 'Motorsport',
  'ai-startup': 'AI/ML Startup',
  'forward-deployed-swe': 'Forward Deployed',
  'general-swe': 'General SWE',
}

const seniorityLabels: Record<SeniorityLevel, string> = {
  'junior': 'Junior',
  'junior-mid': 'Junior-Mid',
  'mid': 'Mid',
  'senior': 'Senior',
}

export function TopBar({
  plan,
  isLoading,
  acceptedCount,
  totalSlots,
  onGenerateCV,
  isGenerating,
}: TopBarProps) {
  const canGenerate = acceptedCount === totalSlots && totalSlots > 0

  return (
    <header className="h-12 border-b border-border-subtle flex items-center px-4 bg-bg-surface">
      {/* Left: App name */}
      <div className="flex-shrink-0">
        <span className="font-mono text-xs tracking-[0.2em] text-text-muted">
          CV BUILDER
        </span>
      </div>

      {/* Center: Job info */}
      <div className="flex-1 flex items-center justify-center gap-3">
        {isLoading ? (
          <div className="h-4 w-48 bg-bg-elevated rounded animate-pulse" />
        ) : plan ? (
          <>
            <span className="text-sm font-medium text-text-primary">
              {plan.job_title} at {plan.company}
            </span>
            <Badge
              variant="secondary"
              className="bg-accent-subtle text-accent-color border-accent-border text-[10px]"
            >
              {roleFamilyLabels[plan.role_family]}
            </Badge>
            <Badge
              variant="secondary"
              className="bg-bg-elevated text-text-secondary border-border-default text-[10px]"
            >
              {seniorityLabels[plan.seniority_level]}
            </Badge>
          </>
        ) : null}
      </div>

      {/* Right: Counter + Generate button */}
      <div className="flex-shrink-0 flex items-center gap-4">
        <span className="text-xs text-text-secondary">
          {acceptedCount} / {totalSlots}
        </span>
        <Button
          size="sm"
          disabled={!canGenerate || isGenerating}
          onClick={onGenerateCV}
          className="bg-accent-color hover:bg-accent-hover text-white disabled:opacity-50"
        >
          {isGenerating ? (
            <>
              <Loader2 className="mr-2 h-3 w-3 animate-spin" />
              Generating...
            </>
          ) : (
            'Generate CV'
          )}
        </Button>
      </div>
    </header>
  )
}
