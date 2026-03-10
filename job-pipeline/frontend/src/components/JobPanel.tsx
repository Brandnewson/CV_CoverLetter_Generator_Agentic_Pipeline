import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { KeywordTag } from '@/components/KeywordTag'
import { ExternalLink } from 'lucide-react'
import type { CVSelectionPlan, QueuedJob, Job } from '@/types'

interface JobPanelProps {
  plan: CVSelectionPlan | undefined
  job: Job | undefined
  isLoading: boolean
  queuedJobs: QueuedJob[]
  currentJobId: number
  onSelectJob: (jobId: number) => void
}

function FitScoreBar({ score }: { score: number }) {
  // Score is 0-100
  const percentage = Math.min(100, Math.max(0, score))
  const color =
    percentage >= 70
      ? 'bg-status-ok'
      : percentage >= 40
      ? 'bg-status-warn'
      : 'bg-status-error'

  return (
    <div className="w-full h-[3px] bg-bg-elevated rounded-full overflow-hidden">
      <div
        className={`h-full ${color} transition-all duration-150`}
        style={{ width: `${percentage}%` }}
      />
    </div>
  )
}

function HighlightedDescription({
  text,
  keywords,
}: {
  text: string
  keywords: string[]
}) {
  if (!keywords.length) {
    return <span>{text}</span>
  }

  // Create a regex that matches any keyword (case-insensitive, word boundaries)
  const escapedKeywords = keywords.map((k) =>
    k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  )
  const pattern = new RegExp(`\\b(${escapedKeywords.join('|')})\\b`, 'gi')

  const parts = text.split(pattern)

  return (
    <>
      {parts.map((part, i) => {
        const isKeyword = keywords.some(
          (k) => k.toLowerCase() === part.toLowerCase()
        )
        if (isKeyword) {
          return (
            <mark
              key={i}
              className="bg-accent-subtle text-accent-color rounded-sm px-0.5"
            >
              {part}
            </mark>
          )
        }
        return <span key={i}>{part}</span>
      })}
    </>
  )
}

export function JobPanel({
  plan,
  job,
  isLoading,
  queuedJobs,
  currentJobId,
  onSelectJob,
}: JobPanelProps) {
  if (isLoading) {
    return (
      <div className="h-full p-4 space-y-4 overflow-y-auto bg-bg-surface">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-5 w-full" />
        <Skeleton className="h-3 w-48" />
        <Skeleton className="h-[3px] w-full" />
        <div className="space-y-2 mt-4">
          <Skeleton className="h-3 w-16" />
          <div className="flex flex-wrap gap-1">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-5 w-16" />
            ))}
          </div>
        </div>
        <Skeleton className="h-32 w-full" />
      </div>
    )
  }

  const dbMatchedKeywords = job?.keyword_matches?.matched ?? []
  const requiredKeywords =
    (plan?.required_keywords?.length ?? 0) > 0
      ? plan?.required_keywords ?? []
      : dbMatchedKeywords
  const niceToHaveKeywords = plan?.nice_to_have_keywords ?? []
  const technicalKeywords = plan?.technical_keywords ?? []

  const allKeywords = [
    ...requiredKeywords,
    ...niceToHaveKeywords,
    ...technicalKeywords,
  ]

  const descriptionText = (job?.description ?? '').trim()

  const postedDate = job?.date_posted
    ? new Date(`${job.date_posted}T00:00:00`).toLocaleDateString('en-GB', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
      })
    : null

  return (
    <div className="h-full p-4 overflow-y-auto bg-bg-surface">
      {/* Job metadata block */}
      {job && (
        <div className="space-y-1">
          <p className="text-xs text-text-muted uppercase tracking-wider">
            {job.company}
          </p>
          <h1 className="text-base font-semibold text-text-primary">
            {job.title}
          </h1>
          <p className="text-xs text-text-secondary">{job.location}</p>
          {postedDate && (
            <p className="text-xs text-text-muted">Posted: {postedDate}</p>
          )}

          {plan && (
            <div className="flex items-center gap-2 mt-2">
              <Badge
                variant="secondary"
                className="bg-accent-subtle text-accent-color border-accent-border text-[10px]"
              >
                {plan.role_family}
              </Badge>
              <Badge
                variant="secondary"
                className="bg-bg-elevated text-text-secondary border-border-default text-[10px]"
              >
                {plan.seniority_level}
              </Badge>
            </div>
          )}

          <div className="mt-3">
            <FitScoreBar score={job.fit_score} />
          </div>

          {job.job_url && (
            <a
              href={job.job_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-text-muted hover:text-text-primary mt-2"
            >
              View posting
              <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </div>
      )}

      <Separator className="my-4 bg-border-subtle" />

      {/* Keywords section */}
      {plan && (
        <div className="space-y-3">
          {/* Required keywords */}
          <div>
            <p className="text-xs tracking-wider text-text-muted uppercase mb-2">
              Required
            </p>
            <div className="flex flex-wrap gap-1">
              {requiredKeywords.map((kw) => {
                const isUncovered = (plan?.uncovered_keywords ?? []).includes(kw)
                return (
                  <KeywordTag
                    key={kw}
                    keyword={kw}
                    variant={isUncovered ? 'uncovered' : 'required'}
                  />
                )
              })}
              {requiredKeywords.length === 0 && (
                <p className="text-xs text-text-muted">No required keywords found in DB for this job.</p>
              )}
            </div>
          </div>

          {/* Nice to have keywords */}
          {niceToHaveKeywords.length > 0 && (
            <div>
              <p className="text-xs tracking-wider text-text-muted uppercase mb-2">
                Nice to Have
              </p>
              <div className="flex flex-wrap gap-1">
                {niceToHaveKeywords.map((kw) => (
                  <KeywordTag key={kw} keyword={kw} variant="nice-to-have" />
                ))}
              </div>
            </div>
          )}

          {/* Technical keywords */}
          {technicalKeywords.length > 0 && (
            <div>
              <p className="text-xs tracking-wider text-text-muted uppercase mb-2">
                Technical
              </p>
              <div className="flex flex-wrap gap-1">
                {technicalKeywords.map((kw) => {
                  const isUncovered = (plan?.uncovered_keywords ?? []).includes(kw)
                  return (
                    <KeywordTag
                      key={kw}
                      keyword={kw}
                      variant={isUncovered ? 'uncovered' : 'required'}
                    />
                  )
                })}
              </div>
            </div>
          )}
        </div>
      )}

      <Separator className="my-4 bg-border-subtle" />

      {/* Job description */}
      {job && (
        <div>
          <p className="text-xs tracking-wider text-text-muted uppercase mb-2">
            Description
          </p>
          <div className="text-xs text-text-secondary leading-relaxed whitespace-pre-wrap">
            {descriptionText ? (
              <HighlightedDescription
                text={descriptionText}
                keywords={allKeywords}
              />
            ) : (
              <span className="text-text-muted">No description available in PostgreSQL for this posting.</span>
            )}
          </div>
        </div>
      )}

      <Separator className="my-4 bg-border-subtle" />

      {/* Queued jobs list */}
      <div>
        <p className="text-xs tracking-wider text-text-muted uppercase mb-2">
          Other Jobs
        </p>
        <div className="space-y-1">
          {queuedJobs.map((qJob) => (
            <button
              key={qJob.id}
              onClick={() => onSelectJob(qJob.id)}
              className={`w-full text-left px-2 py-1.5 rounded text-xs transition-colors ${
                qJob.id === currentJobId
                  ? 'bg-bg-elevated text-text-primary'
                  : 'text-text-secondary hover:bg-bg-elevated hover:text-text-primary'
              }`}
            >
              <span className="text-text-muted">{qJob.company}</span>
              <span className="mx-1">—</span>
              <span>{qJob.title}</span>
              <span className="mx-1">—</span>
              <span className="text-text-muted">{qJob.fit_score}</span>
            </button>
          ))}
          {queuedJobs.length === 0 && (
            <p className="text-xs text-text-muted">No other jobs in queue</p>
          )}
        </div>
      </div>
    </div>
  )
}
