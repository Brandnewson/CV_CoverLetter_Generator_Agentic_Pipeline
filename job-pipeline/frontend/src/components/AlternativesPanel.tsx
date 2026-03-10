import { Card } from '@/components/ui/card'

export function AlternativesPanel() {
  return (
    <div className="h-full p-4 bg-bg-surface border-l border-border-subtle">
      <h2 className="text-xs tracking-wider text-text-muted uppercase mb-4">
        Alternatives
      </h2>
      <Card className="border-dashed border-border-subtle bg-transparent p-4">
        <p className="text-xs text-text-muted text-center">
          Contextual bullet alternatives generated from your stories and profile will appear here.
        </p>
      </Card>
    </div>
  )
}
