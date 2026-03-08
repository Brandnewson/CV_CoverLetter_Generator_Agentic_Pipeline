-- Job Pipeline Database Schema
-- Run with: psql -d job_pipeline -f schema.sql

-- All discovered jobs, deduplicated
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

-- Your scoring + decisions per job
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

-- Each generated application pack
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

-- Search run logging
CREATE TABLE IF NOT EXISTS search_runs (
    id              SERIAL PRIMARY KEY,
    run_at          TIMESTAMPTZ DEFAULT NOW(),
    search_term     TEXT,
    source          TEXT,
    jobs_found      INTEGER,
    jobs_new        INTEGER,
    duration_secs   FLOAT
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company);
CREATE INDEX IF NOT EXISTS idx_jobs_date_discovered ON jobs(date_discovered);
CREATE INDEX IF NOT EXISTS idx_jobs_is_duplicate ON jobs(is_duplicate);
CREATE INDEX IF NOT EXISTS idx_job_status_status ON job_status(status);
CREATE INDEX IF NOT EXISTS idx_job_status_fit_score ON job_status(fit_score);
