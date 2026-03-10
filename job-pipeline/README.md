# Job Pipeline

Job discovery + scoring + CV generation pipeline.

## What this does

- Aggregates jobs from multiple sources.
- Deduplicates and scores jobs against your profile.
- Lets you queue jobs for CV generation.
- Builds tailored CVs from your template and bullet bank in a web UI.

## Core runtime path

1. Search jobs: `discovery/run_search.py`
2. Review and queue: `dashboard/review.py`
3. Build CVs (web): `dashboard/cv_builder_ui.py`

The post-queue flow is API-driven:

- `GET /api/jobs/queued`
- `GET /api/plan/<job_id>`
- `POST /api/rephrase`
- `POST /api/approve/<job_id>`
- `GET /api/cv/<job_id>/download`

## Setup

```powershell
cd job-pipeline
uv sync
uv run python setup_db.py
```

Frontend setup (one-time):

```powershell
cd job-pipeline/frontend
pnpm install
```

Create `.env` from `.env.example` and set:

- `DATABASE_URL`
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `CLAUDE_MODEL` (example: `claude-haiku-4-5-20251001`)

## Profile files (user-scoped)

The runtime now prefers user-scoped assets under `profile/users/1/` with fallback to `profile/`.

Required:

- `profile/users/1/master_bullets.md`
- `profile/users/1/master_cv_template.docx` (or `cv_template.docx`)
- `profile/users/1/template_map.json`

## Run

```powershell
cd job-pipeline

# 1) discovery + scoring
uv run python discovery/run_search.py

# 2) queue jobs interactively
uv run python dashboard/review.py

# 3) start CV Builder UI
uv run python dashboard/cv_builder_ui.py
```

Open `http://127.0.0.1:5051/`.

### Frontend (React) dev server

Run this in a separate terminal:

```powershell
cd job-pipeline/frontend
pnpm run dev
```

Then open the Vite URL shown in terminal (usually `http://localhost:5173`, but it may auto-increment to `5174+` if ports are busy).

Important:

- The frontend proxies `/api/*` to `http://localhost:5051` via `vite.config.ts`.
- Keep `uv run python dashboard/cv_builder_ui.py` running, or the frontend will show proxy `ECONNREFUSED` errors.

### Frontend production build

```powershell
cd job-pipeline/frontend
pnpm run build
pnpm run preview
```

## Fast verification

With the UI backend running:

```powershell
cd job-pipeline

# full smoke check (queue -> plan -> render -> download)
uv run python scripts/e2e_cv_smoke.py --approve --download
```

## Testing same job repeatedly

For local testing, the same `job_id` can be generated repeatedly.

- Controlled by `KEEP_JOB_QUEUED_AFTER_RENDER` (default `true`).
- When `true`, approve/render keeps status as `queued` instead of moving to `cv_generated`.

## Tests

```powershell
cd job-pipeline
uv run pytest tests/ -v
```

Test files map one-to-one to their modules:

| File | Tests |
|------|-------|
| `test_schema.py` | DB schema columns/tables |
| `test_validators.py` | `agent/validators.py` — bullet/slot types |
| `test_jd_parser.py` | `agent/jd_parser.py` — keyword extraction |
| `test_template_extractor.py` | `agent/template_extractor.py` |
| `test_bullet_selector.py` | `agent/bullet_selector.py` |
| `test_story_drafter.py` | `agent/story_drafter.py` |
| `test_bullet_rephraser.py` | `agent/bullet_rephraser.py` |
| `test_cv_renderer.py` | `agent/cv_renderer.py` |
| `test_style_updater.py` | `agent/style_updater.py` |
| `test_web_ui.py` | `dashboard/cv_builder_ui.py` Flask routes |
| `test_search.py` | `discovery/run_search.py` |
| `test_scorer.py` | `discovery/scorer.py` |
| `test_dedup.py` | `discovery/dedup.py` |

## Common failure points

- Model 404 from Anthropic: `CLAUDE_MODEL` is not available to your key.
- Empty builder UI: template map has zero bullet slots.
- Plan API 500: missing profile assets or DB schema mismatch.
- Frontend `/api` errors in browser console: backend is not running on `127.0.0.1:5051`.
- Vite import resolution errors after branch switches: stop all old dev servers, then rerun `pnpm run dev`.

## Docs

- Architecture and flow: `architecture.md`
- Schema: `db/schema.sql`

## License

Personal use only.
