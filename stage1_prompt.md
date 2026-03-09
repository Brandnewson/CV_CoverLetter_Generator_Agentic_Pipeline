# Claude Code Prompt — Stage 1: Job Aggregator

Paste everything below this line into Claude Code (Opus).

---

## Context

I am building a personal job application pipeline on Windows. The V1 spec is attached. This session covers **Stage 1 only**: a working job aggregator that runs a search, deduplicates results, scores fit against my profile, stores everything in PostgreSQL, and prints a ranked shortlist I can review.

By the end of this session, running `python discovery/run_search.py` should produce a ranked list of jobs scored against my profile, with all data persisted to Postgres. Every step must have a passing test before we move on.

Do not touch Stage 2 (CV/cover letter generation) in this session.

---

## My environment

- OS: Windows (use `\` for paths, never assume bash — use `pathlib.Path` throughout)
- Python: assume Python 3.11+ is installed
- Package manager: UV
- PostgreSQL: assume it is installed locally; database name will be `job_pipeline`
- I will run commands in PowerShell
- Do NOT use cron — use Windows Task Scheduler XML at the end, or a simple `schedule` library fallback
- Virtual environment: create one at `job-pipeline/venv` and use it for all installs

---

## My profile (use this for scoring jobs)

**Target roles:** Forward deployed software engineer, AI engineer, agentic systems engineer, systems architect, data engineer, software engineer

**Industries:** AI startups, robotics, deep-tech engineering software, industrial AI, simulation platforms, autonomous systems

**Locations:** London (preferred), New York, Paris, Any major European tech hub (acceptable), willing to relocate within UK or EU

**Must-have keywords in job (any of):** AI, machine learning, simulation, robotics, optimisation, distributed systems, agentic systems, data pipelines, inference, model deployment

**Nice-to-have keywords:** reinforcement learning, physics simulation, digital twins, autonomy, robotics perception, LLMs, control systems, Kubernetes, cloud infrastructure

**Hard exclusions — skip any job matching these:** junior, graduate scheme, internship, unpaid, sales, marketing

**Salary floor:** £40,000 (skip if stated salary is below this; include if salary not stated)

**Seniority:** Mid to senior. Skip anything titled "junior" or "graduate".

**My core strengths (for fit scoring):**
- Building engineering software tools for real-time operational decision making
- Developing data pipelines and telemetry processing systems
- Full-stack engineering for technical users (React + backend APIs)
- Deploying and managing containerised engineering applications in cloud environments
- Collaborating across software, data science, and engineering teams to operationalise ML/AI systems
---

## Search configuration

Use these JobSpy parameters as defaults:

```python
site_name       = ["linkedin", "indeed", "glassdoor", "google"]
search_terms    = [
    "forward deployed software engineer",
    "AI engineer startup",
    "simulation software engineer",
    "robotics software engineer",
    "machine learning infrastructure engineer",
    "agentic systems engineer",
    "software engineer",
]
location        = "United Kingdom"
results_wanted  = 30   # per search term
hours_old       = 25
country_indeed  = "UK"
```

Run all four search terms and merge results before deduplication.

---

## What to build — in this exact order

Work through the following phases sequentially. After each phase, pause and show me:
1. What was built
2. The test results (all must pass before continuing)
3. A sample of real output where applicable

Do not proceed to the next phase until I confirm.

### Phase 1 — Project scaffold and dependencies

Create the following structure:

```
job-pipeline/
├── discovery/
│   ├── __init__.py
│   ├── run_search.py
│   ├── dedup.py
│   ├── scorer.py
│   └── config.yaml
├── profile/
│   ├── master_bullets.md       ← placeholder, I will fill this in
│   ├── experience.md           ← placeholder, I will fill this in
│   └── scoring_profile.yaml   ← built from my profile above
├── db/
│   └── schema.sql
├── tests/
│   ├── __init__.py
│   ├── test_dedup.py
│   ├── test_scorer.py
│   ├── test_db.py
│   └── test_search.py
├── dashboard/
│   └── review.py
├── requirements.txt
├── setup_db.py
└── README.md
```

Install into venv:
```
jobspy
psycopg2-binary

pyyaml
pytest
pytest-cov
python-dotenv
schedule
tabulate
```

Create a `.env.example`:
```
DATABASE_URL=postgresql://localhost/job_pipeline
OPENAI_API_KEY=your_key_here
```

**Phase 1 tests (tests/test_scaffold.py):**
- All required files exist
- All imports resolve without error
- `.env.example` exists and contains required keys
- `uv sync` downloads all required packages

Show me the tree output after this phase.

---

### Phase 2 — Database setup

Write `db/schema.sql` using the schema below exactly. Then write `setup_db.py` which:
1. Reads `DATABASE_URL` from `.env`
2. Creates the database if it does not exist
3. Runs the schema
4. Prints confirmation of each table created

```sql
CREATE TABLE IF NOT EXISTS jobs (
    id              SERIAL PRIMARY KEY,
    source          TEXT NOT NULL,
    external_id     TEXT,
    company         TEXT NOT NULL,
    title           TEXT NOT NULL,
    location        TEXT,
    remote_type     TEXT,
    salary_min      INTEGER,
    salary_max      INTEGER,
    currency        TEXT DEFAULT 'GBP',
    job_url         TEXT NOT NULL,
    description     TEXT,
    date_posted     DATE,
    date_discovered TIMESTAMPTZ DEFAULT NOW(),
    is_duplicate    BOOLEAN DEFAULT FALSE,
    duplicate_of    INTEGER REFERENCES jobs(id),
    search_term     TEXT,
    UNIQUE (company, title, date_posted)
);

CREATE TABLE IF NOT EXISTS job_status (
    id              SERIAL PRIMARY KEY,
    job_id          INTEGER REFERENCES jobs(id) UNIQUE,
    fit_score       FLOAT,
    fit_summary     TEXT,
    keyword_matches JSONB,
    status          TEXT DEFAULT 'new',
    status_updated  TIMESTAMPTZ DEFAULT NOW(),
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS application_packs (
    id                  SERIAL PRIMARY KEY,
    job_id              INTEGER REFERENCES jobs(id),
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    cv_path             TEXT,
    cover_letter_path   TEXT,
    job_snapshot        JSONB,
    bullets_used        JSONB,
    user_edits          TEXT,
    outcome             TEXT
);

CREATE TABLE IF NOT EXISTS search_runs (
    id              SERIAL PRIMARY KEY,
    run_at          TIMESTAMPTZ DEFAULT NOW(),
    search_term     TEXT,
    source          TEXT,
    jobs_found      INTEGER,
    jobs_new        INTEGER,
    duration_secs   FLOAT
);
```

**Phase 2 tests (tests/test_db.py):**
- `setup_db.py` runs without error
- All four tables exist after running it
- Schema is idempotent (running twice does not error)
- A test row can be inserted into `jobs` and retrieved

---

### Phase 3 — JobSpy search wrapper

Write `discovery/run_search.py` as a module with a clean function interface:

```python
def run_search(config: dict, search_term: str) -> list[dict]:
    """Run JobSpy for one search term. Return list of normalised job dicts."""

def normalise_job(raw_row) -> dict:
    """Convert a JobSpy DataFrame row to the canonical job dict matching the DB schema."""

def insert_jobs(jobs: list[dict], conn, search_term: str) -> tuple[int, int]:
    """Insert jobs, return (total_attempted, new_inserted). Uses ON CONFLICT DO NOTHING."""
```

The main block should:
1. Load config from `config.yaml` and `.env`
2. Run all search terms from config
3. Insert all results
4. Log a row to `search_runs` with count and duration
5. Print a summary: `Searched 4 terms — 87 found, 23 new`

Important Windows note: use `pathlib.Path` for all file paths. No hardcoded `/` separators.

**Phase 3 tests (tests/test_search.py):**
- `normalise_job` maps all expected JobSpy columns correctly (test with a mock row)
- `normalise_job` handles missing/None values without raising
- `insert_jobs` inserts a batch of mock jobs into a test DB
- `insert_jobs` does not error on duplicate insertion (idempotency)
- The deduplication constraint (company + title + date_posted) works correctly

For the live search test: run one real search with `results_wanted=5` and `hours_old=72`. Assert that at least 1 result is returned and has non-null `company`, `title`, and `job_url`. Print the result so I can see it.

---

### Phase 4 — Deduplication

Write `discovery/dedup.py`. Because the same job appears across multiple sources (LinkedIn + Indeed + Google), we need fuzzy deduplication beyond the DB unique constraint.

```python
def find_fuzzy_duplicates(conn) -> list[tuple[int, int]]:
    """
    Find pairs of jobs that are likely duplicates using:
    1. Same company + very similar title (>85% string similarity)
    2. Posted within 3 days of each other
    Return list of (keep_id, duplicate_id) pairs.
    """

def mark_duplicates(conn, pairs: list[tuple[int, int]]) -> int:
    """Mark the duplicate_id jobs as is_duplicate=True, set duplicate_of. Return count marked."""
```

Use `difflib.SequenceMatcher` for title similarity — no extra dependencies needed.

**Phase 4 tests (tests/test_dedup.py):**
- Two jobs with identical company and 90% similar title are flagged as duplicates
- Two jobs with same company but completely different titles are NOT flagged
- Two jobs with same title but different companies are NOT flagged
- `mark_duplicates` correctly sets `is_duplicate=True` and `duplicate_of` in DB
- Running dedup twice does not double-mark anything

---

### Phase 5 — Fit scoring

Write `discovery/scorer.py`. This scores each unscored job in `job_status` against the profile.

```python
def score_job(job: dict, profile: dict, client: ChatGPT) -> dict:
    """
    Score a single job. Returns:
    {
        "fit_score": 0.0–1.0,
        "fit_summary": "One paragraph, max 80 words",
        "keyword_matches": {"matched": [...], "missing": [...]}
    }
    Use chatGPT-4o mini. Prompt must request JSON only.
    """

def score_pending_jobs(conn, profile: dict, client: ChatGPT) -> int:
    """Score all jobs in job_status where fit_score IS NULL. Return count scored."""

def apply_hard_filters(job: dict, config: dict) -> tuple[bool, str]:
    """
    Apply exclusion rules from config BEFORE calling Claude.
    Returns (should_skip: bool, reason: str).
    Rules: excluded keywords, salary floor, seniority exclusions.
    """
```

Important: run `apply_hard_filters` first. Only call OpenAI API for jobs that pass. This saves API cost.

The scoring prompt must:
- Be under 1500 tokens total (truncate job description at 1200 chars)
- Request JSON output only, no preamble
- Include must-have and nice-to-have keywords from `scoring_profile.yaml`
- Ask for a score, a short summary, and matched/missing keywords

**Phase 5 tests (tests/test_scorer.py):**
- `apply_hard_filters` correctly rejects a job titled "Junior Strategy Engineer"
- `apply_hard_filters` correctly rejects a job with salary_max=30000
- `apply_hard_filters` correctly rejects a job with "sales" in the title
- `apply_hard_filters` passes a job with no exclusion triggers
- `score_job` returns a dict with all three required keys
- `score_job` returns `fit_score` between 0.0 and 1.0
- `score_job` returns `fit_summary` under 100 words
- Run one live scoring call with a realistic fake job dict and print the result

---

### Phase 6 — Review dashboard

Write `dashboard/review.py`. This is a terminal script that shows today's ranked shortlist.

It must:
1. Query top 20 jobs by `fit_score DESC` where `status = 'new'` and `date_discovered > NOW() - 48h`
2. Print a formatted table using `tabulate` with columns: ID | Score | Company | Title | Location | Source | URL (truncated to 40 chars)
3. Print the fit summary for each job (indented, below the row)
4. After the table, prompt: `Enter job ID to mark as queued (or q to quit):`
5. On valid ID entry, update `job_status.status` to `'queued'` and confirm

**Phase 6 tests (tests/test_db.py — add to existing file):**
- Dashboard query returns results ordered by fit_score DESC
- Marking a job as 'queued' updates the status correctly
- Invalid job ID entry does not crash

---

### Phase 7 — Scheduler (Windows)

Since this is Windows, do not use cron. Instead:

1. Write a `scheduler.py` in the root that uses the `schedule` library to run `run_search.py` daily at 08:00.

```python
# scheduler.py — run this once, keep it running in background
import schedule, time, subprocess, sys
from pathlib import Path

def job():
    print("Running daily job search...")
    subprocess.run([sys.executable, Path("discovery/run_search.py")], check=True)

schedule.every().day.at("08:00").do(job)

print("Scheduler running. Press Ctrl+C to stop.")
while True:
    schedule.run_pending()
    time.sleep(60)
```

2. Also generate a Windows Task Scheduler XML file (`task_scheduler.xml`) so I can register it as a proper background task that survives reboots:

```xml
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" ...>
  <!-- Fill in: run python scheduler.py at startup, in the project directory -->
</Task>
```

Include instructions in `README.md` for registering the task with:
```powershell
schtasks /Create /TN "JobPipeline" /XML task_scheduler.xml
```

---

### Phase 8 — Full integration test

Write `tests/test_integration.py`:

```python
def test_full_pipeline():
    """
    End-to-end test:
    1. Run a real JobSpy search (results_wanted=5, hours_old=72, one term only)
    2. Insert into test DB
    3. Run deduplication
    4. Score with Claude (real API call)
    5. Query ranked shortlist
    6. Assert: at least 1 job returned, scored, with fit_score > 0
    7. Print the full shortlist table
    """
```

This test uses a separate test database (`job_pipeline_test`) to avoid polluting real data.

After this test passes, run the full pipeline for real:
```powershell
python discovery/run_search.py
python dashboard/review.py
```

Show me the output.

---

## Code quality rules — follow throughout

- Type hints on all function signatures
- Docstrings on all public functions
- All DB connections use context managers (`with conn:`)
- All API calls wrapped in try/except with meaningful error messages
- All config loaded from `config.yaml` + `.env`, never hardcoded
- `pathlib.Path` for all file paths — no string concatenation for paths
- Print progress to stdout at each major step so I can see what is happening

---

## Definition of done for this session

The following must all be true:

- [ ] `pytest tests/` runs with 0 failures
- [ ] `python setup_db.py` creates all four tables cleanly
- [ ] `python discovery/run_search.py` completes without error and prints a job count
- [ ] `python dashboard/review.py` shows a formatted ranked table of real jobs
- [ ] At least one job has a non-null `fit_score` and `fit_summary` in the database
- [ ] `scheduler.py` runs and confirms it is waiting for the next scheduled run

When all of these pass, Stage 1 is complete.
