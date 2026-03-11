// Types mirroring backend Pydantic models

export type BulletSource = 'master_bullets' | 'story_draft' | 'rephrasing'
export type Section = 'work_experience' | 'technical_projects'
export type RoleFamily = 'motorsport' | 'ai-startup' | 'forward-deployed-swe' | 'general-swe'
export type SeniorityLevel = 'junior' | 'junior-mid' | 'mid' | 'senior'

export interface BulletCandidate {
  text: string
  source: BulletSource
  section: Section
  subsection: string
  tags: string[]
  role_families: string[]
  relevance_score: number
  char_count: number
  over_soft_limit: boolean // > 110 chars
  keyword_hits: string[]
  rephrase_generation: number
  warnings?: string[]
}

export interface BulletSlot {
  slot_index: number
  section: Section
  subsection: string
  current_candidate: BulletCandidate | null
  rephrase_history: BulletCandidate[]
  is_approved: boolean
}

export interface CVSelectionPlan {
  job_id: number
  user_id: number
  job_title: string
  company: string
  role_family: RoleFamily
  seniority_level: SeniorityLevel
  required_keywords: string[]
  nice_to_have_keywords: string[]
  technical_keywords: string[]
  work_experience_slots: BulletSlot[]
  technical_project_slots: BulletSlot[]
  projects_to_hide: string[]
  keyword_coverage: Record<string, number[]>
  uncovered_keywords: string[]
  // Joined from API response
  job?: Job
}

export interface Job {
  id: number
  title: string
  company: string
  location: string
  description: string
  job_description_raw: string
  company_description_raw: string
  enrichment_keywords: EnrichmentKeywords
  salary_min: number | null
  salary_max: number | null
  job_url: string
  source: string
  date_posted: string | null
  status: string
  fit_score: number
  fit_summary: string
  keyword_matches?: {
    matched?: string[]
    missing?: string[]
  }
}

export interface QueuedJob {
  id: number
  title: string
  company: string
  fit_score: number
}

export interface UserSelections {
  job_id: number
  user_id: number
  approved_bullets: ApprovedBullet[]
  hidden_projects: string[]
  session_timestamp: string
}

export interface ApprovedBullet {
  slot_index: number
  section: Section
  subsection: string
  text: string
  source: BulletSource
  rephrase_generation: number
}

export interface ApproveResponse {
  cv_path: string
  filename: string
  status: string
}

export interface RephraseRequest {
  job_id: number
  slot_index: number
  section: Section
  subsection: string
}

export interface EnrichmentKeywords {
  technologies: string[]
  skills: string[]
  abilities: string[]
}

export interface EnrichmentDraft {
  job_description_raw: string
  company_description_raw: string
  enrichment_keywords: EnrichmentKeywords
}

export interface SaveEnrichmentResponse {
  status: 'saved'
  job: Job
}
