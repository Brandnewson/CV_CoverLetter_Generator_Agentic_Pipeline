import { useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { KeywordTag } from '@/components/KeywordTag'
import { ExternalLink } from 'lucide-react'
import { normalizeCompanyDescriptionText, normalizeJobDescriptionMarkdown } from '@/lib/jobText'
import type { CVSelectionPlan, QueuedJob, Job, EnrichmentDraft } from '@/types'

interface JobPanelProps {
  plan: CVSelectionPlan | undefined
  job: Job | undefined
  isLoading: boolean
  queuedJobs: QueuedJob[]
  currentJobId: number
  onSelectJob: (jobId: number) => void
  draft: EnrichmentDraft
  onChangeDraft: (draft: EnrichmentDraft) => void
  onSaveDraft: () => void
  isSavingDraft: boolean
  isDraftDirty: boolean
  saveError?: string | null
  isEnrichmentConfirmed: boolean
  draftSyncVersion: number
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
  draft,
  onChangeDraft,
  onSaveDraft,
  isSavingDraft,
  isDraftDirty,
  saveError,
  isEnrichmentConfirmed,
  draftSyncVersion,
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

  const technologies = draft.enrichment_keywords.technologies
  const skills = draft.enrichment_keywords.skills
  const abilities = draft.enrichment_keywords.abilities

  const [technologyText, setTechnologyText] = useState('')
  const [skillsText, setSkillsText] = useState('')
  const [abilitiesText, setAbilitiesText] = useState('')

  useEffect(() => {
    setTechnologyText(technologies.join('\n'))
    setSkillsText(skills.join('\n'))
    setAbilitiesText(abilities.join('\n'))
  }, [draftSyncVersion])

  const allKeywords = [...technologies, ...skills, ...abilities]

  const companyDescriptionText = normalizeCompanyDescriptionText(draft.company_description_raw)
  const jobDescriptionText = normalizeJobDescriptionMarkdown(draft.job_description_raw)

  const updateKeywords = (
    field: 'technologies' | 'skills' | 'abilities',
    value: string
  ) => {
    onChangeDraft({
      ...draft,
      enrichment_keywords: {
        ...draft.enrichment_keywords,
        [field]: value
          .split(/\n|,/)
          .map((item) => item.trim())
          .filter(Boolean),
      },
    })
  }

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

      {/* Discovery Keywords section */}
      {job && (
        <div className="space-y-3">
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs tracking-wider text-text-muted uppercase">
              Enrichment
            </p>
            <Button
              size="default"
              variant={isEnrichmentConfirmed && !isDraftDirty ? 'secondary' : 'default'}
              className={
                isEnrichmentConfirmed && !isDraftDirty
                  ? 'h-9 px-4 text-xs bg-accent-color/20 text-text-secondary hover:bg-accent-color/25 border border-accent-border/40'
                  : 'h-9 px-4 text-xs bg-accent-color hover:bg-accent-hover text-white'
              }
              onClick={onSaveDraft}
              disabled={isSavingDraft}
            >
              {isSavingDraft ? 'Confirming...' : 'Confirm job details'}
            </Button>
          </div>
          {saveError && (
            <p className="text-[10px] text-status-error">{saveError}</p>
          )}
          {!saveError && !isEnrichmentConfirmed && !isDraftDirty && (
            <p className="text-[10px] text-status-info">This is the default first stage. Confirm the job details to move on.</p>
          )}
          {!saveError && isDraftDirty && (
            <p className="text-[10px] text-status-warn">Changes detected. Confirm job details to continue.</p>
          )}
          {!saveError && isEnrichmentConfirmed && !isDraftDirty && (
            <p className="text-[10px] text-status-ok">Job details confirmed. Rephraser and bullet selection are unlocked.</p>
          )}

          <div>
            <p className="text-xs tracking-wider text-text-muted uppercase mb-2">
              Keywords
            </p>
            <textarea
              value={technologyText}
              onChange={(e) => {
                setTechnologyText(e.target.value)
                updateKeywords('technologies', e.target.value)
              }}
              className="w-full min-h-16 rounded border border-border-default bg-bg-elevated px-2 py-1 text-xs text-text-primary"
              placeholder="One keyword per line or comma-separated"
            />
            <div className="flex flex-wrap gap-1">
              {technologies.map((kw) => (
                <KeywordTag key={`tech-${kw}`} keyword={kw} variant="required" />
              ))}
            </div>
          </div>

          <div>
            <p className="text-xs tracking-wider text-text-muted uppercase mb-2">
              Skills
            </p>
            <textarea
              value={skillsText}
              onChange={(e) => {
                setSkillsText(e.target.value)
                updateKeywords('skills', e.target.value)
              }}
              className="w-full min-h-16 rounded border border-border-default bg-bg-elevated px-2 py-1 text-xs text-text-primary mb-2"
              placeholder="One skill per line or comma-separated"
            />
            <div className="flex flex-wrap gap-1">
              {skills.map((kw) => (
                <KeywordTag key={`skill-${kw}`} keyword={kw} variant="nice-to-have" />
              ))}
            </div>
          </div>

          <div>
            <p className="text-xs tracking-wider text-text-muted uppercase mb-2">
              Abilities
            </p>
            <textarea
              value={abilitiesText}
              onChange={(e) => {
                setAbilitiesText(e.target.value)
                updateKeywords('abilities', e.target.value)
              }}
              className="w-full min-h-16 rounded border border-border-default bg-bg-elevated px-2 py-1 text-xs text-text-primary mb-2"
              placeholder="One ability per line or comma-separated"
            />
            <div className="flex flex-wrap gap-1">
              {abilities.map((kw) => (
                <KeywordTag key={`ability-${kw}`} keyword={kw} variant="required" />
              ))}
            </div>
          </div>
        </div>
      )}

      <Separator className="my-4 bg-border-subtle" />

      {/* Company description */}
      {job && (
        <div>
          <p className="text-xs tracking-wider text-text-muted uppercase mb-2">
            Company Description
          </p>
          <textarea
            value={draft.company_description_raw}
            onChange={(e) =>
              onChangeDraft({
                ...draft,
                company_description_raw: e.target.value,
              })
            }
            className="w-full min-h-24 rounded border border-border-default bg-bg-elevated px-2 py-1 text-xs text-text-primary mb-2"
            placeholder="Paste company description"
          />
          <div className="text-xs text-text-secondary leading-relaxed whitespace-pre-wrap">
            {companyDescriptionText ? (
              <HighlightedDescription
                text={companyDescriptionText}
                keywords={allKeywords}
              />
            ) : (
              <span className="text-text-muted">No company description captured during discovery.</span>
            )}
          </div>
        </div>
      )}

      <Separator className="my-4 bg-border-subtle" />

      {/* Job description */}
      {job && (
        <div>
          <p className="text-xs tracking-wider text-text-muted uppercase mb-2">
            Job Description
          </p>
          <textarea
            value={draft.job_description_raw}
            onChange={(e) =>
              onChangeDraft({
                ...draft,
                job_description_raw: e.target.value,
              })
            }
            className="w-full min-h-32 rounded border border-border-default bg-bg-elevated px-2 py-1 text-xs text-text-primary mb-2"
            placeholder="Paste full job description"
          />
          <div className="rounded border border-border-subtle bg-bg-elevated/40 p-3 text-xs text-text-secondary leading-relaxed">
            {jobDescriptionText ? (
              <div className="markdown-preview">
                <ReactMarkdown
                  components={{
                    p: ({ children }) => <p className="my-2 text-text-secondary">{children}</p>,
                    ul: ({ children }) => <ul className="my-2 list-disc pl-5 text-text-secondary">{children}</ul>,
                    ol: ({ children }) => <ol className="my-2 list-decimal pl-5 text-text-secondary">{children}</ol>,
                    li: ({ children }) => <li className="my-0.5">{children}</li>,
                    h1: ({ children }) => <h1 className="my-2 text-sm font-semibold text-text-primary">{children}</h1>,
                    h2: ({ children }) => <h2 className="my-2 text-sm font-semibold text-text-primary">{children}</h2>,
                    h3: ({ children }) => <h3 className="my-2 text-xs font-semibold uppercase tracking-wide text-text-primary">{children}</h3>,
                    strong: ({ children }) => <strong className="font-semibold text-text-primary">{children}</strong>,
                  }}
                >
                  {jobDescriptionText}
                </ReactMarkdown>
              </div>
            ) : (
              <span className="text-text-muted">No job description captured during discovery.</span>
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
