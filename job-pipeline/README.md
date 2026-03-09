# Job Pipeline - Stage 1: Job Aggregator

A personal job application pipeline that aggregates jobs from multiple sources, deduplicates results, scores them against your profile using AI, and presents a ranked shortlist for review.

## Features

- **Multi-source job search**: Scrapes LinkedIn, Indeed, Glassdoor, and Google Jobs using JobSpy
- **Smart deduplication**: Removes duplicate listings across sources using fuzzy matching
- **AI-powered scoring**: Uses OpenAI GPT-4o mini to evaluate job fit against your profile
- **Hard filters**: Automatically excludes jobs that don't meet your criteria (salary, seniority, keywords)
- **Interactive review**: Terminal-based dashboard for reviewing and queuing jobs
- **Scheduled runs**: Can run automatically on a schedule using Windows Task Scheduler

## Prerequisites

- Python 3.11+
- PostgreSQL (installed and running locally)
- UV package manager (recommended) or pip
- OpenAI API key

## Quick Start

### 1. Set up the environment

```powershell
# Navigate to the project directory
cd job-pipeline

# Create virtual environment and install dependencies with UV
uv venv
uv sync

# Or with pip
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configure environment variables

```powershell
# Copy the example environment file
Copy-Item .env.example .env

# Edit .env with your values
notepad .env
```

Set the following in `.env`:
- `DATABASE_URL`: Your PostgreSQL connection string (default: `postgresql://localhost/job_pipeline`)
- `OPENAI_API_KEY`: Your OpenAI API key

### 3. Set up the database

```powershell
# Make sure PostgreSQL is running, then:
python setup_db.py
```

This creates the `job_pipeline` database and all required tables.

### 4. Customize your profile

Edit the following files in the `profile/` directory:

- `scoring_profile.yaml`: Your target roles, industries, keywords, and core strengths
- `master_bullets.md`: Your achievement bullets (placeholder - fill in your actual achievements)
- `experience.md`: Your work history (placeholder - fill in your actual experience)

### 5. Run the pipeline

```powershell
# Run the job search
python discovery/run_search.py

# Review the results
python dashboard/review.py
```

## Project Structure

```
job-pipeline/
├── discovery/
│   ├── run_search.py      # Job search using JobSpy
│   ├── dedup.py           # Fuzzy deduplication
│   ├── scorer.py          # AI-powered job scoring
│   └── config.yaml        # Search configuration
├── profile/
│   ├── scoring_profile.yaml  # Your profile for scoring
│   ├── master_bullets.md     # Achievement bullets
│   └── experience.md         # Work history
├── db/
│   └── schema.sql         # Database schema
├── tests/                 # Test suite
├── dashboard/
│   └── review.py          # Terminal review interface
├── setup_db.py            # Database setup script
├── scheduler.py           # Background scheduler
└── task_scheduler.xml     # Windows Task Scheduler config
```

## Running Tests

```powershell
# Run all tests (excluding slow/live API tests)
pytest tests/ -m "not slow"

# Run all tests including live API calls
pytest tests/

# Run with coverage
pytest tests/ --cov=discovery --cov-report=term-missing
```

## Scheduling Automatic Runs

### Option 1: Python scheduler (run in background)

```powershell
# Start the scheduler (runs daily at 08:00)
python scheduler.py
```

Keep this terminal window open, or run it as a background process.

### Option 2: Windows Task Scheduler (recommended for persistence)

```powershell
# Register the task
schtasks /Create /TN "JobPipeline" /XML task_scheduler.xml

# View the task
schtasks /Query /TN "JobPipeline"

# Run manually
schtasks /Run /TN "JobPipeline"

# Delete the task
schtasks /Delete /TN "JobPipeline" /F
```

**Note**: Before using the Task Scheduler XML, edit `task_scheduler.xml` to set the correct paths for your system.

## Configuration

### Search Configuration (`discovery/config.yaml`)

```yaml
search:
  site_name:
    - linkedin
    - indeed
    - glassdoor
    - google
  search_terms:
    - "AI engineer startup"
    - "software engineer"
  location: "United Kingdom"
  results_wanted: 30
  hours_old: 25

exclusions:
  title_keywords:
    - junior
    - intern
  
scoring:
  salary_floor: 40000
```

### Scoring Profile (`profile/scoring_profile.yaml`)

This file defines how jobs are evaluated. Key sections:

- `target_roles`: Job titles you're interested in
- `industries`: Industries you want to work in
- `must_have_keywords`: Keywords that MUST appear (any of them)
- `nice_to_have_keywords`: Keywords that improve the score
- `hard_exclusions`: Keywords that automatically reject a job
- `core_strengths`: Your strengths for matching

## Database Schema

The pipeline uses four PostgreSQL tables:

- `jobs`: All discovered jobs with deduplication
- `job_status`: Scoring and status tracking per job
- `application_packs`: Generated CV/cover letter packages (Stage 2)
- `search_runs`: Logging of search runs for debugging

## Troubleshooting

### "DATABASE_URL not found"
Make sure you've created a `.env` file from `.env.example` and set your database URL.

### "Could not connect to database"
Ensure PostgreSQL is running and the connection string is correct.

### "OPENAI_API_KEY not found"
Set your OpenAI API key in the `.env` file.

### No jobs found
- Check your search terms in `config.yaml`
- Try increasing `hours_old` to search further back
- Verify your internet connection

### Scoring errors
- Check your OpenAI API key is valid
- Ensure you have sufficient API credits

## Next Steps (Stage 2)

Stage 2 will add:
- CV generation from your bullet bank
- Cover letter generation
- DOCX template-based rendering
- Application tracking

This is intentionally excluded from Stage 1 to keep the pipeline focused and testable.

## License

Personal use only.
