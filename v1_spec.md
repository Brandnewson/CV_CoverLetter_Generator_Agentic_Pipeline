# Job Application Pipeline — V1 Technical Spec

## What this system does

A two-stage pipeline that runs daily, finds jobs matching your profile, and on demand generates tailored CV and cover letter DOCX files ready for your review.

**Stage 1 (automated):** JobSpy cron script → deduplication → PostgreSQL → ranked shortlist  
**Stage 2 (on demand):** You pick a job → Claude Code agent reads your profile + the job → produces two DOCX files → you review and apply manually

You are in the loop at two points: approving which jobs to generate documents for, and reviewing the output before sending.

---

## Folder structure

```
job-pipeline/
├── discovery/
│   ├── run_search.py          # Daily JobSpy script (run via cron)
│   ├── config.yaml            # Your search preferences
│   └── dedup.py               # Deduplication logic
│
├── profile/
│   ├── master_bullets.md      # Your bullet bank, tagged by theme
│   ├── experience.md          # Full experience timeline
│   ├── skills.md              # Skills taxonomy
│   ├── cv_rules.md            # Hard rules for CV (what never changes)
│   ├── cover_letter_rules.md  # Tone, style, length preferences
│   └── samples/               # Your existing tailored CVs + cover letters
│       ├── cv_strategy_role.docx
│       ├── cv_simulation_role.docx
│       └── ...
│
├── agent/
│   ├── CLAUDE.md              # Claude Code agent instructions
│   ├── generate_pack.py       # Entry point: takes job_id, calls agent
│   └── prompts/
│       ├── cv_prompt.md
│       └── cover_letter_prompt.md
│
├── output/
│   └── {company}_{role}_{date}/
│       ├── cv.docx
│       ├── cover_letter.docx
│       └── job_snapshot.json  # The job data used at generation time
│
├── db/
│   └── schema.sql
│
└── dashboard/
    └── review.py              # Simple CLI review tool (or later: web UI)
```

---

## PostgreSQL schema

Three tables. Keep it simple for V1.

```sql
-- All discovered jobs, deduplicated
CREATE TABLE jobs (
    id              SERIAL PRIMARY KEY,
    source          TEXT NOT NULL,              -- 'linkedin', 'indeed', 'glassdoor', etc.
    external_id     TEXT,                       -- JobSpy's internal ID where available
    company         TEXT NOT NULL,
    title           TEXT NOT NULL,
    location        TEXT,
    remote_type     TEXT,                       -- 'remote', 'hybrid', 'onsite'
    salary_min      INTEGER,
    salary_max      INTEGER,
    currency        TEXT DEFAULT 'GBP',
    job_url         TEXT NOT NULL,
    description     TEXT,
    date_posted     DATE,
    date_discovered TIMESTAMPTZ DEFAULT NOW(),
    is_duplicate    BOOLEAN DEFAULT FALSE,
    duplicate_of    INTEGER REFERENCES jobs(id),
    UNIQUE (company, title, date_posted)        -- core dedup constraint
);

-- Your scoring + decisions per job
CREATE TABLE job_status (
    id              SERIAL PRIMARY KEY,
    job_id          INTEGER REFERENCES jobs(id) UNIQUE,
    fit_score       FLOAT,                      -- 0.0 to 1.0
    fit_summary     TEXT,                       -- One paragraph explanation
    status          TEXT DEFAULT 'new',         -- 'new', 'queued', 'generated', 'applied', 'rejected', 'no_response', 'interview'
    status_updated  TIMESTAMPTZ DEFAULT NOW(),
    notes           TEXT
);

-- Each generated application pack
CREATE TABLE application_packs (
    id              SERIAL PRIMARY KEY,
    job_id          INTEGER REFERENCES jobs(id),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    cv_path         TEXT,
    cover_letter_path TEXT,
    job_snapshot    JSONB,                      -- Snapshot of job data used at generation time
    bullets_used    JSONB,                      -- Which bullets were selected
    user_edits      TEXT,                       -- Free text notes on what you changed
    outcome         TEXT                        -- 'sent', 'abandoned'
);
```

The `UNIQUE (company, title, date_posted)` constraint on `jobs` does most of the deduplication work automatically. The `duplicate_of` field is for fuzzy duplicates you catch after the fact.

---

## Discovery script (run_search.py)

Runs daily via cron. Searches JobSpy, deduplicates, scores fit, and inserts new jobs.

```python
# discovery/run_search.py
import yaml
from jobspy import scrape_jobs
import psycopg2
from anthropic import Anthropic
import json
from datetime import date

# Load config
with open("config.yaml") as f:
    config = yaml.safe_load(f)

# 1. Scrape
jobs = scrape_jobs(
    site_name=["linkedin", "indeed", "glassdoor", "google"],
    search_term=config["search_term"],
    location=config["location"],
    results_wanted=config["results_wanted"],
    hours_old=25,                  # Slightly over 24h to avoid gaps at boundary
    country_indeed="UK",
    is_remote=config.get("remote_only", False),
    job_type=config.get("job_type"),
)

# 2. Connect to DB
conn = psycopg2.connect(config["db_url"])
cur = conn.cursor()

new_jobs = []

for _, row in jobs.iterrows():
    try:
        cur.execute("""
            INSERT INTO jobs (source, external_id, company, title, location,
                              remote_type, salary_min, salary_max, job_url,
                              description, date_posted)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (company, title, date_posted) DO NOTHING
            RETURNING id
        """, (
            row.get("site"),
            str(row.get("id", "")),
            row.get("company"),
            row.get("title"),
            row.get("location"),
            row.get("is_remote") and "remote" or "onsite",
            row.get("min_amount"),
            row.get("max_amount"),
            row.get("job_url"),
            row.get("description"),
            row.get("date_posted") or date.today(),
        ))
        result = cur.fetchone()
        if result:
            new_jobs.append({"id": result[0], "description": row.get("description", ""), 
                             "title": row.get("title"), "company": row.get("company")})
    except Exception as e:
        print(f"Insert error: {e}")

conn.commit()

# 3. Score new jobs with Claude
if new_jobs:
    client = Anthropic()
    with open("../profile/master_bullets.md") as f:
        profile = f.read()

    for job in new_jobs:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=400,
            messages=[{
                "role": "user",
                "content": f"""Score this job for fit against my profile. 
Return JSON only: {{"score": 0.0-1.0, "summary": "one paragraph"}}

MY PROFILE:
{profile[:2000]}

JOB: {job['title']} at {job['company']}
{job['description'][:1500]}"""
            }]
        )
        
        try:
            result = json.loads(response.content[0].text)
            cur.execute("""
                INSERT INTO job_status (job_id, fit_score, fit_summary)
                VALUES (%s, %s, %s)
                ON CONFLICT (job_id) DO NOTHING
            """, (job["id"], result["score"], result["summary"]))
        except Exception as e:
            print(f"Scoring error for job {job['id']}: {e}")

conn.commit()
cur.close()
conn.close()

print(f"Done. {len(new_jobs)} new jobs added and scored.")
```

### config.yaml

```yaml
db_url: "postgresql://localhost/job_pipeline"
search_term: "race strategy software engineer motorsport"
location: "United Kingdom"
results_wanted: 50
remote_only: false
job_type: "fulltime"

# Scoring weights (used in prompts)
must_have:
  - motorsport
  - strategy
  - Python
  - simulation

nice_to_have:
  - F1
  - race engineering
  - optimisation
  - C++

excluded:
  - junior
  - internship
```

---

## Cron setup

On Mac/Linux, add this to crontab (`crontab -e`):

```
0 8 * * * cd /path/to/job-pipeline && python discovery/run_search.py >> logs/discovery.log 2>&1
```

Runs at 8am daily. Adjust to your timezone.

---

## Manual input shortcut

For specific companies or niche sites that JobSpy misses, a simple script to insert directly:

```python
# discovery/manual_add.py
# Usage: python manual_add.py --url "https://..." --company "Mercedes AMG" --title "Strategy Engineer"
import argparse, psycopg2, yaml

parser = argparse.ArgumentParser()
parser.add_argument("--url", required=True)
parser.add_argument("--company", required=True)
parser.add_argument("--title", required=True)
parser.add_argument("--description", default="")
parser.add_argument("--location", default="")
args = parser.parse_args()

with open("config.yaml") as f:
    config = yaml.safe_load(f)

conn = psycopg2.connect(config["db_url"])
cur = conn.cursor()
cur.execute("""
    INSERT INTO jobs (source, company, title, location, job_url, description)
    VALUES ('manual', %s, %s, %s, %s, %s)
    ON CONFLICT DO NOTHING RETURNING id
""", (args.company, args.title, args.location, args.url, args.description))
conn.commit()
print(f"Added: {args.title} at {args.company}")
```

---

## Review CLI (dashboard/review.py)

Simple terminal view of today's top jobs:

```python
# dashboard/review.py
import psycopg2, yaml

with open("config.yaml") as f:
    config = yaml.safe_load(f)

conn = psycopg2.connect(config["db_url"])
cur = conn.cursor()

cur.execute("""
    SELECT j.id, j.company, j.title, j.location, j.job_url,
           js.fit_score, js.fit_summary
    FROM jobs j
    JOIN job_status js ON js.job_id = j.id
    WHERE js.status = 'new'
      AND j.date_discovered > NOW() - INTERVAL '48 hours'
    ORDER BY js.fit_score DESC
    LIMIT 20
""")

rows = cur.fetchall()
print(f"\n{'='*60}")
print(f"TOP {len(rows)} NEW JOBS")
print(f"{'='*60}\n")

for row in rows:
    job_id, company, title, location, url, score, summary = row
    print(f"[{job_id}] {company} — {title}")
    print(f"     Score: {score:.2f} | {location}")
    print(f"     {summary[:120]}...")
    print(f"     {url}")
    print()

job_id_input = input("Enter job ID to generate pack (or q to quit): ").strip()
if job_id_input.lower() != 'q':
    import subprocess
    subprocess.run(["python", "agent/generate_pack.py", "--job-id", job_id_input])
```

---

## Claude Code agent (CLAUDE.md)

This is the instruction file Claude Code reads when generating application packs. Place it at `agent/CLAUDE.md`.

```markdown
# Job Application Pack Generator

You are a specialist CV and cover letter generator for a specific person.
Your job is to produce two DOCX files: a tailored CV and a tailored cover letter.

## Your inputs
- A job_id passed as an argument
- The job posting fetched from the database
- The user's profile files in ../profile/

## Your rules

### Truthfulness (most important)
- Every bullet point or claim must trace back to ../profile/master_bullets.md or ../profile/experience.md
- Never invent metrics, tools, employers, or dates
- If you are not confident a claim is supported, leave it out

### CV rules
- Read ../profile/cv_rules.md before generating anything
- Use the closest sample in ../profile/samples/ as your layout template
- Swap content, never change section order or typography
- Select 6-8 bullets from master_bullets.md that best match the job requirements
- Lightly adapt wording to the job, do not rewrite entirely
- Generate the output using python-docx (see generate_pack.py)

### Cover letter rules
- Read ../profile/cover_letter_rules.md before generating
- Structure: why this role → why this company → why me specifically → one concrete evidence point → closing
- Max one page
- Tone: confident, specific, not generic

### Output
- Write cv.docx and cover_letter.docx to output/{company}_{title}_{date}/
- Write job_snapshot.json alongside them
- Update job_status in the database to 'generated'
- Print a summary of which bullets you used and why

## How to run
python agent/generate_pack.py --job-id 42
```

---

## Agent entry point (agent/generate_pack.py)

```python
# agent/generate_pack.py
# This is what Claude Code executes. It fetches the job, loads the profile,
# calls Claude to select/adapt bullets, then renders DOCX files.

import argparse
import psycopg2
import yaml
import json
import os
from datetime import date
from anthropic import Anthropic
from docx import Document  # python-docx for rendering

parser = argparse.ArgumentParser()
parser.add_argument("--job-id", required=True, type=int)
args = parser.parse_args()

with open("config.yaml") as f:
    config = yaml.safe_load(f)

conn = psycopg2.connect(config["db_url"])
cur = conn.cursor()

# Fetch job
cur.execute("SELECT * FROM jobs WHERE id = %s", (args.job_id,))
job = dict(zip([d[0] for d in cur.description], cur.fetchone()))

# Load profile
with open("../profile/master_bullets.md") as f:
    bullets = f.read()
with open("../profile/experience.md") as f:
    experience = f.read()
with open("../profile/cv_rules.md") as f:
    cv_rules = f.read()
with open("../profile/cover_letter_rules.md") as f:
    cl_rules = f.read()

client = Anthropic()

# Step 1: Select and adapt bullets
bullet_response = client.messages.create(
    model="claude-opus-4-5",
    max_tokens=2000,
    messages=[{
        "role": "user",
        "content": f"""Select and lightly adapt 6-8 bullets from the library below for this job.
Return JSON only: {{"selected_bullets": [...], "reasoning": "..."}}

CV RULES:
{cv_rules}

JOB:
{job['title']} at {job['company']}
{job['description'][:2000]}

BULLET LIBRARY:
{bullets}"""
    }]
)

bullet_data = json.loads(bullet_response.content[0].text)

# Step 2: Generate cover letter text
cl_response = client.messages.create(
    model="claude-opus-4-5",
    max_tokens=1000,
    messages=[{
        "role": "user",
        "content": f"""Write a cover letter for this job following the rules below.
Return only the letter text, no preamble.

COVER LETTER RULES:
{cl_rules}

JOB:
{job['title']} at {job['company']}
{job['description'][:2000]}

MY EXPERIENCE:
{experience[:2000]}

BEST BULLETS TO REFERENCE:
{json.dumps(bullet_data['selected_bullets'])}"""
    }]
)

cover_letter_text = cl_response.content[0].text

# Step 3: Render DOCX files
output_dir = f"../output/{job['company']}_{job['title']}_{date.today()}"
os.makedirs(output_dir, exist_ok=True)

# CV — uses python-docx; template-based rendering to be built out
# For now: writes bullets into a simple structured document
cv_doc = Document()
cv_doc.add_heading(job['title'] + " Application", 0)
for bullet in bullet_data["selected_bullets"]:
    cv_doc.add_paragraph(bullet, style="List Bullet")
cv_doc.save(f"{output_dir}/cv.docx")

# Cover letter
cl_doc = Document()
for para in cover_letter_text.split("\n\n"):
    cl_doc.add_paragraph(para)
cl_doc.save(f"{output_dir}/cover_letter.docx")

# Step 4: Save snapshot + update DB
with open(f"{output_dir}/job_snapshot.json", "w") as f:
    json.dump({"job": job, "bullets_used": bullet_data}, f, indent=2, default=str)

cur.execute("UPDATE job_status SET status = 'generated' WHERE job_id = %s", (job["id"],))
conn.commit()

print(f"\nPack generated: {output_dir}")
print(f"Bullets used: {bullet_data['reasoning']}")
```

---

## Profile files to write before building anything

These are the most important part of the project. Before you write a line of code, create these:

### profile/master_bullets.md

Your bullet bank, every achievement you've ever written, tagged:

```markdown
## Strategy
- Developed real-time pit stop decision model reducing average lap time loss by 0.3s [motorsport, strategy, python]
- Built optimisation tool for tyre degradation modelling across 6 compounds [simulation, python]

## Software
- Designed and shipped REST API handling 50k daily requests [python, backend]

## Data / Analysis
- Built automated race data pipeline ingesting telemetry from 3 sources [data engineering, python]
```

### profile/cv_rules.md

Hard constraints for the agent:

```markdown
- Never change section order: Summary → Experience → Projects → Education → Skills
- Never claim tools I have not used: Java, Rust, MATLAB (unless added here)
- Summary must be 2-3 sentences maximum
- Maximum 2 pages
- Do not add a photo or address
- Company names and dates are fixed, never adjust them
```

### profile/cover_letter_rules.md

```markdown
- Maximum 1 page, 4 paragraphs
- Tone: direct, evidence-led, not enthusiastic-sounding
- Always mention one specific thing about the company (from the job description)
- Do not start with "I am writing to apply for..."
- Close with availability and a specific ask
```

---

## What V1 deliberately excludes

- No auto-submission
- No form-filling
- No web scraping beyond JobSpy
- No multi-agent orchestration (single agent, sequential)
- No web dashboard (CLI review is enough)
- No email/Telegram integration
- No fine-tuned models

These are all Phase 2+. Get the pipeline reliable first.

---

## Phased build order

### Phase 1 — Discovery (1–2 days)
- Set up Postgres and schema
- Write and test run_search.py with your config
- Run manually for 2–3 days, verify results are sensible
- Set up cron

### Phase 2 — Profile (1 day)
- Write master_bullets.md from your existing CVs
- Write cv_rules.md and cover_letter_rules.md
- Place your sample DOCX files in profile/samples/

### Phase 3 — Agent scaffold (1–2 days)
- Write CLAUDE.md
- Write generate_pack.py skeleton
- Test with a real job_id
- Verify DOCX output opens correctly

### Phase 4 — DOCX quality (1–2 days)
- Move from simple python-docx scaffolding to template-based rendering
  (unpack your best sample DOCX, swap content blocks, repack)
- This is where the DOCX skill referenced in the codebase becomes useful

### Phase 5 — Review loop (ongoing)
- After each application, note in job_status what you changed
- Tune your config.yaml search terms and scoring prompts
- The edits you make are your training data

---

## Learning goals this project covers

Since this is also practice for agentic workflows:

| Concept | Where you'll encounter it |
|---|---|
| Tool use / function calling | Scoring step in run_search.py |
| Structured output (JSON mode) | Bullet selection in generate_pack.py |
| Context window management | Profile truncation at 2000 chars |
| Agent instruction design | CLAUDE.md |
| Human-in-the-loop | review.py + manual approval |
| State management | PostgreSQL as agent memory |
| Prompt chaining | score → select bullets → write letter |

The single-agent, sequential design is intentional here — it makes each step visible and debuggable, which is more instructive than a multi-agent system where failures are harder to trace.
