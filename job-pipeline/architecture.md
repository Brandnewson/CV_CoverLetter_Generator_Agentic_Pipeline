# Architecture

## System overview

This project has two connected pipelines:

1. Discovery pipeline: find, deduplicate, and score jobs.
2. CV pipeline: take queued jobs and generate tailored DOCX CVs.

## End-to-end flow

```mermaid
flowchart TD
    A[run_search.py] --> B[(jobs + job_status)]
    B --> C[review.py mark queued]
    C --> D[cv_builder_ui.py Flask API]
    D --> E[/api/jobs/queued]
    D --> F[/api/plan/{job_id}]
    F --> G[jd_parser classify + keyword extraction]
    F --> H[bullet_selector build selection plan]
    H --> I[(cv_feedback weights)]
    D --> J[/api/rephrase]
    J --> K[bullet_rephraser]
    D --> L[/api/approve/{job_id}]
    L --> M[cv_renderer render DOCX]
    M --> N[(output/cv_{job_id}_{company}.docx)]
    D --> O[/api/cv/{job_id}/download]
    O --> N
```

## Main components

### Discovery

- `discovery/run_search.py`: source scraping + initial inserts.
- `discovery/dedup.py`: duplicate detection.
- `discovery/scorer.py`: OpenAI fit scoring + summary.

### Queueing

- `dashboard/review.py`: terminal shortlist and queue action.
- DB status transition: `new -> queued`.

### CV Builder (runtime)

- `dashboard/cv_builder_ui.py`: Flask API + page serving.
- `dashboard/templates/cv_builder.html`: UI with three panels (job info, builder, preview).

### CV logic

- `agent/jd_parser.py`: role family, seniority, keyword extraction.
- `agent/bullet_selector.py`: loads bullet bank and builds slot candidates.
- `agent/bullet_rephraser.py`: rephrase endpoint behavior.
- `agent/cv_renderer.py`: writes final DOCX from template + selections.
- `agent/template_extractor.py`: generates template map from CV template.

## Data stores

- PostgreSQL (primary): `jobs`, `job_status`, `cv_sessions`, `cv_feedback`, etc.
- File assets (profile): template docx, template map, bullet bank.
- Output files: generated CVs under `output/`.

## Profile asset resolution

Runtime prefers user-scoped files first, then root fallback.

Order used:

- Bullet bank:
  - `profile/users/{DEFAULT_USER_ID}/master_bullets.md`
  - `profile/master_bullets.md`
- Template DOCX:
  - `profile/users/{DEFAULT_USER_ID}/cv_template.docx`
  - `profile/users/{DEFAULT_USER_ID}/master_cv_template.docx`
  - `profile/cv_template.docx`
- Template map:
  - `profile/users/{DEFAULT_USER_ID}/template_map.json`
  - `profile/template_map.json`

## Status model

Primary statuses in `job_status`:

- `new`: discovered and scored.
- `queued`: selected for CV generation.
- `cv_generated`: optional production-style post-render status.

Testing mode:

- `KEEP_JOB_QUEUED_AFTER_RENDER=true` keeps jobs reusable after `/api/approve`.

## API contract (post-queue)

- `GET /api/jobs/queued`: list queued jobs.
- `GET /api/plan/{job_id}`: build and return `CVSelectionPlan`.
- `POST /api/rephrase`: regenerate one slot candidate.
- `POST /api/approve/{job_id}`: render DOCX from approved bullets.
- `GET /api/cv/{job_id}/download`: download generated file.

## Operational checks

### Minimal

1. Queue exists: `/api/jobs/queued` returns non-empty list.
2. Plan exists: `/api/plan/{job_id}` returns non-zero slots.
3. Render works: `/api/approve/{job_id}` returns success + filename.
4. Download works: `/api/cv/{job_id}/download` returns DOCX mime type.

### Scripted

Use:

- `scripts/e2e_cv_smoke.py`

This script validates assets, DB, queued jobs, plan generation, and optional render/download.

## Tests

All test files live in `tests/` and map directly to their module:

| Test file | Module under test |
|-----------|-------------------|
| `test_schema.py` | DB schema |
| `test_validators.py` | `agent/validators.py` |
| `test_jd_parser.py` | `agent/jd_parser.py` |
| `test_template_extractor.py` | `agent/template_extractor.py` |
| `test_bullet_selector.py` | `agent/bullet_selector.py` |
| `test_story_drafter.py` | `agent/story_drafter.py` |
| `test_bullet_rephraser.py` | `agent/bullet_rephraser.py` |
| `test_cv_renderer.py` | `agent/cv_renderer.py` |
| `test_style_updater.py` | `agent/style_updater.py` |
| `test_web_ui.py` | Flask routes |
| `test_search.py` | `discovery/run_search.py` |
| `test_scorer.py` | `discovery/scorer.py` |
| `test_dedup.py` | `discovery/dedup.py` |

## Known sharp edges

- If `template_map.json` has zero bullet slots, the builder UI appears empty even when the backend is healthy.
- If `CLAUDE_MODEL` is not valid for your Anthropic key, `/api/plan` or `/api/rephrase` returns 500.
- The web API (`dashboard/cv_builder_ui.py`) is the only active CV generation path.
