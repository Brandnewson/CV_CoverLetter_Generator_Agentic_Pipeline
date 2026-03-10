import { cn } from '@/lib/utils'

export type KeywordVariant = 'required' | 'nice-to-have' | 'hit' | 'uncovered'

interface KeywordTagProps {
  keyword: string
  variant: KeywordVariant
  className?: string
}

const variantStyles: Record<KeywordVariant, string> = {
  required: 'bg-accent-subtle text-accent-color border-accent-border',
  'nice-to-have': 'bg-transparent text-text-muted border-border-default',
  hit: 'bg-accent-subtle text-accent-color border-accent-border',
  uncovered: 'bg-transparent text-status-warn border-status-warn',
}

export function KeywordTag({ keyword, variant, className }: KeywordTagProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center text-[10px] px-1.5 py-0.5 rounded-sm font-mono border',
        variantStyles[variant],
        className
      )}
    >
      {keyword}
    </span>
  )
}
