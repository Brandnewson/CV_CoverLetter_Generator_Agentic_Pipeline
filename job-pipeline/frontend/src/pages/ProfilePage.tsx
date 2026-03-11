import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  useProfileUploads,
  useUploadFile,
  useDeleteUpload,
  useParseCV,
  useConfirmSections,
} from '@/hooks/useProfile'
import { useQueuedJobs } from '@/hooks/useQueuedJobs'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { TopBar } from '@/components/TopBar'
import { Loader2, Upload, Trash2, FileText, ChevronDown } from 'lucide-react'
import type { UploadType, SectionType, RawSection, ConfirmedSection } from '@/types'

const SECTION_TYPES: SectionType[] = [
  'work_experience',
  'technical_projects',
  'education',
  'skills',
  'summary',
  'cover_letter',
  'other',
]

const SECTION_LABELS: Record<SectionType, string> = {
  work_experience: 'Work Experience',
  technical_projects: 'Technical Projects',
  education: 'Education',
  skills: 'Skills',
  summary: 'Summary / Objective',
  cover_letter: 'Cover Letter',
  other: 'Other',
}

function confidenceColor(c: number) {
  if (c >= 0.9) return 'bg-green-500'
  if (c >= 0.6) return 'bg-yellow-500'
  return 'bg-red-400'
}

// ─── Section card ─────────────────────────────────────────────────────────────
function SectionCard({
  section,
  onChange,
  onRemove,
}: {
  section: ConfirmedSection & { confidence?: number; warnings?: string[] }
  onChange: (s: ConfirmedSection) => void
  onRemove: () => void
}) {
  const [expanded, setExpanded] = useState(false)
  return (
    <div className="rounded-lg border border-border-default bg-bg-elevated p-3 space-y-2">
      <div className="flex items-center gap-2">
        <span
          title={`Confidence ${Math.round((section.confidence ?? 0) * 100)}%`}
          className={`h-2 w-2 rounded-full flex-shrink-0 ${confidenceColor(section.confidence ?? 0)}`}
        />
        <input
          className="flex-1 bg-transparent border-none text-sm font-medium text-text-primary focus:outline-none"
          value={section.heading}
          onChange={(e) => onChange({ ...section, heading: e.target.value })}
        />
        <select
          className="bg-bg-surface border border-border-default rounded px-2 py-0.5 text-xs text-text-secondary focus:outline-none focus:border-accent-border"
          value={section.confirmed_type}
          onChange={(e) => onChange({ ...section, confirmed_type: e.target.value as SectionType })}
        >
          {SECTION_TYPES.map((t) => (
            <option key={t} value={t}>{SECTION_LABELS[t]}</option>
          ))}
        </select>
        <button
          onClick={() => setExpanded((x) => !x)}
          className="text-text-muted hover:text-text-secondary"
          title="Toggle preview"
        >
          <ChevronDown className={`h-3.5 w-3.5 transition-transform ${expanded ? 'rotate-180' : ''}`} />
        </button>
        <button
          onClick={onRemove}
          className="text-text-muted hover:text-red-400"
          title="Remove section"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
      {section.warnings && section.warnings.length > 0 && (
        <p className="text-[11px] text-yellow-500">{section.warnings.join(' · ')}</p>
      )}
      {expanded && (
        <pre className="text-[11px] text-text-muted bg-bg-surface rounded p-2 overflow-x-auto whitespace-pre-wrap max-h-40">
          {section.raw_text.slice(0, 800)}
          {section.raw_text.length > 800 ? '\n…' : ''}
        </pre>
      )}
    </div>
  )
}

// ─── Upload zone ──────────────────────────────────────────────────────────────
function UploadZone({
  label,
  files,
  onUploadFiles,
  onDelete,
  onParse,
  isParsing,
}: {
  label: string
  files: { filename: string; size_bytes: number; modified_at: string }[]
  onUploadFiles: (files: File[]) => void
  onDelete: (filename: string) => void
  onParse?: (filename: string) => void
  isParsing?: boolean
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [isDragOver, setIsDragOver] = useState(false)

  return (
    <div
      className={`relative overflow-hidden rounded-lg border bg-bg-elevated p-4 space-y-3 transition-colors ${isDragOver ? 'border-accent-border' : 'border-border-default'}`}
      onDragOver={(e) => {
        e.preventDefault()
        setIsDragOver(true)
      }}
      onDragEnter={(e) => {
        e.preventDefault()
        setIsDragOver(true)
      }}
      onDragLeave={() => setIsDragOver(false)}
      onDrop={(e) => {
        e.preventDefault()
        setIsDragOver(false)
        const dropped = Array.from(e.dataTransfer.files ?? [])
        if (dropped.length > 0) {
          onUploadFiles(dropped)
        }
      }}
    >
      {isDragOver && (
        <div className="pointer-events-none absolute inset-0 bg-accent-subtle/35 animate-pulse" />
      )}
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-text-primary uppercase tracking-wider">{label}</span>
        <Button
          variant="outline"
          size="sm"
          className="text-xs gap-1.5"
          onClick={() => inputRef.current?.click()}
        >
          <Upload className="h-3 w-3" />
          Upload
        </Button>
        <input
          ref={inputRef}
          type="file"
          className="hidden"
          multiple
          accept=".pdf,.docx,.md,.txt"
          onChange={(e) => {
            const selected = Array.from(e.target.files ?? [])
            if (selected.length > 0) onUploadFiles(selected)
            e.target.value = ''
          }}
        />
      </div>

      {files.length === 0 ? (
        <p className="text-[11px] text-text-muted text-center py-3 border border-dashed border-border-subtle rounded-md">
          No files uploaded yet
        </p>
      ) : (
        <ul className="space-y-1.5">
          {files.map((f) => (
            <li key={f.filename} className="flex items-center gap-2">
              <FileText className="h-3.5 w-3.5 text-text-muted flex-shrink-0" />
              <span className="flex-1 text-xs text-text-secondary truncate" title={f.filename}>
                {f.filename}
              </span>
              <span className="text-[10px] text-text-muted">
                {(f.size_bytes / 1024).toFixed(1)} KB
              </span>
              {onParse && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-[10px] h-6 px-2 text-accent-color hover:text-accent-hover"
                  onClick={() => onParse(f.filename)}
                  disabled={isParsing}
                >
                  {isParsing ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Parse'}
                </Button>
              )}
              <button
                onClick={() => onDelete(f.filename)}
                className="text-text-muted hover:text-red-400 flex-shrink-0"
              >
                <Trash2 className="h-3 w-3" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────
export function ProfilePage() {
  const navigate = useNavigate()
  const { data: uploads, isLoading: uploadsLoading } = useProfileUploads()
  const { data: queuedJobs = [] } = useQueuedJobs()
  const uploadFile = useUploadFile()
  const deleteUpload = useDeleteUpload()
  const parseCV = useParseCV()
  const confirmSections = useConfirmSections()

  const [sections, setSections] = useState<
    (ConfirmedSection & { confidence?: number; warnings?: string[] })[]
  >([])
  const [parsedFilename, setParsedFilename] = useState<string | null>(null)
  const [confirmResult, setConfirmResult] = useState<Record<string, string[]> | null>(null)

  const handleParse = (filename: string) => {
    setParsedFilename(filename)
    setConfirmResult(null)
    parseCV.mutate(filename, {
      onSuccess: (data) => {
        setSections(
          data.sections.map((s: RawSection) => ({
            heading: s.heading,
            raw_text: s.raw_text,
            confirmed_type: s.detected_type,
            confidence: s.confidence,
            warnings: s.warnings,
          }))
        )
      },
    })
  }

  const handleConfirm = () => {
    if (!parsedFilename) return
    const payload = sections.map((s) => ({
      heading: s.heading,
      raw_text: s.raw_text,
      confirmed_type: s.confirmed_type,
    }))
    confirmSections.mutate(
      { filename: parsedFilename, sections: payload },
      {
        onSuccess: (data) => {
          setConfirmResult(data.updated_files)
          setSections([])
          setParsedFilename(null)
        },
      }
    )
  }

  const safeUploads = uploads ?? { cv: [], cover_letter: [], story: [], project_context: [] }
  const hasRequiredUploads = safeUploads.cv.length > 0 && safeUploads.cover_letter.length > 0
  const isUploading = uploadFile.isPending

  const handleConfirmProfile = () => {
    const targetJobId = queuedJobs[0]?.id ?? 1
    navigate(`/build/${targetJobId}`)
  }

  const ZONES: { type: UploadType; label: string }[] = [
    { type: 'cv', label: 'CV / Résumé' },
    { type: 'cover_letter', label: 'Cover Letters' },
    { type: 'story', label: 'Stories' },
    { type: 'project_context', label: 'Projects & Context' },
  ]

  return (
    <div className="min-h-screen bg-bg-base text-text-primary">
      <TopBar
        plan={undefined}
        isLoading={false}
        acceptedCount={0}
        totalSlots={0}
        onGenerateCV={() => undefined}
        isGenerating={false}
        menuOnly
      />

      <main className="max-w-2xl mx-auto px-6 py-10 space-y-12">

        {/* Section A — Upload zones */}
        <section className="space-y-4">
          <div>
            <h2 className="text-sm font-semibold text-text-primary">Document Uploads</h2>
            <p className="text-xs text-text-muted mt-0.5">
              Upload your CV (PDF or DOCX) to extract and review sections. Other documents are stored as-is.
            </p>
          </div>
          {uploadsLoading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-5 w-5 animate-spin text-text-muted" />
            </div>
          ) : (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                {ZONES.map(({ type, label }) => (
                  <UploadZone
                    key={type}
                    label={label}
                    files={safeUploads[type] ?? []}
                    onUploadFiles={(files) => {
                      void Promise.all(files.map((file) => uploadFile.mutateAsync({ file, uploadType: type })))
                    }}
                    onDelete={(fn) => deleteUpload.mutate({ uploadType: type, filename: fn })}
                    onParse={type === 'cv' ? handleParse : undefined}
                    isParsing={parseCV.isPending}
                  />
                ))}
              </div>
              <p className="text-sm font-medium text-text-secondary text-center">
                Drag and drop one or more files into any box, or click Upload.
              </p>
              <div className="flex items-center justify-end gap-3">
                {!hasRequiredUploads && (
                  <span className="text-xs text-text-muted">
                    Upload at least one CV and one cover letter to continue.
                  </span>
                )}
                <Button
                  onClick={handleConfirmProfile}
                  disabled={!hasRequiredUploads || isUploading}
                  className="bg-accent-color hover:bg-accent-hover text-white"
                >
                  Confirm profile
                </Button>
              </div>
            </div>
          )}
        </section>

        {/* Section B — Section reviewer */}
        {sections.length > 0 && (
          <section className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-sm font-semibold text-text-primary">Review Extracted Sections</h2>
                <p className="text-xs text-text-muted mt-0.5">
                  Confirm or correct the detected type for each section, then condense into your profile.
                </p>
              </div>
              <Badge variant="secondary" className="bg-bg-elevated border-border-default text-text-secondary text-[10px]">
                {sections.length} sections
              </Badge>
            </div>

            {parseCV.isError && (
              <p className="text-xs text-red-400 bg-red-900/20 border border-red-800/30 rounded px-3 py-2">
                Parse failed — check backend logs.
              </p>
            )}

            <div className="space-y-2.5">
              {sections.map((s, i) => (
                <SectionCard
                  key={i}
                  section={s}
                  onChange={(updated) =>
                    setSections((prev) => prev.map((x, idx) => (idx === i ? { ...updated } : x)))
                  }
                  onRemove={() => setSections((prev) => prev.filter((_, idx) => idx !== i))}
                />
              ))}
            </div>

            <div className="flex items-center gap-3 pt-1">
              <Button
                onClick={handleConfirm}
                disabled={confirmSections.isPending || sections.length === 0}
                className="bg-accent-color hover:bg-accent-hover text-white"
              >
                {confirmSections.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                    Condensing…
                  </>
                ) : (
                  'Confirm & Condense'
                )}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="text-xs text-text-muted"
                onClick={() => { setSections([]); setParsedFilename(null) }}
              >
                Discard
              </Button>
            </div>
          </section>
        )}

        {/* Section C — Confirm result */}
        {confirmResult && (
          <section className="space-y-4">
            <h2 className="text-sm font-semibold text-text-primary">Condensation Complete</h2>
            <div className="space-y-2">
              {Object.entries(confirmResult).map(([file, changes]) => (
                <div key={file} className="rounded-lg border border-border-default bg-bg-elevated p-3 space-y-1">
                  <p className="text-xs font-mono text-accent-color">{file}</p>
                  <ul className="space-y-0.5">
                    {changes.map((c, i) => (
                      <li key={i} className="text-[11px] text-text-secondary">· {c}</li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </section>
        )}
      </main>
    </div>
  )
}
