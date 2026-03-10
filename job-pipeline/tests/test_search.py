"""Tests for job search functionality."""

import sys
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import psycopg2
from dotenv import load_dotenv
import os

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from discovery.run_search import normalise_job, insert_jobs, run_search, load_config
from discovery.enrichment import (
    extract_technologies_deterministic,
    build_enrichment,
    ENRICHMENT_VERSION,
)

# Load environment
load_dotenv(PROJECT_ROOT / ".env")


def get_test_db_url() -> str:
    """Get the test database URL."""
    base_url = os.getenv("DATABASE_URL", "postgresql://localhost/job_pipeline")
    if "job_pipeline_test" not in base_url:
        base_url = base_url.replace("/job_pipeline", "/job_pipeline_test")
    return base_url


class TestNormaliseJob:
    """Tests for the normalise_job function."""
    
    def test_maps_all_expected_columns(self):
        """normalise_job maps all expected columns correctly."""
        mock_row = MagicMock()
        mock_row.get = MagicMock(side_effect=lambda k, d=None: {
            "site": "linkedin",
            "id": "job123",
            "company": "Test Corp",
            "title": "Software Engineer",
            "location": "London, UK",
            "is_remote": True,
            "min_amount": 50000,
            "max_amount": 70000,
            "currency": "GBP",
            "job_url": "https://linkedin.com/job/123",
            "description": "Great job opportunity",
            "date_posted": date(2026, 3, 1),
        }.get(k, d))
        
        result = normalise_job(mock_row, "test search")
        
        assert result["source"] == "linkedin"
        assert result["external_id"] == "job123"
        assert result["company"] == "Test Corp"
        assert result["title"] == "Software Engineer"
        assert result["location"] == "London, UK"
        assert result["remote_type"] == "remote"
        assert result["salary_min"] == 50000
        assert result["salary_max"] == 70000
        assert result["job_url"] == "https://linkedin.com/job/123"
        assert result["description"] == "Great job opportunity"
        assert result["job_description_raw"] == "Great job opportunity"
        assert result["company_description_raw"] == ""
        assert result["search_term"] == "test search"
    
    def test_handles_missing_values(self):
        """normalise_job handles missing/None values without raising."""
        mock_row = MagicMock()
        mock_row.get = MagicMock(return_value=None)
        
        # Should not raise
        result = normalise_job(mock_row)
        
        assert result["company"] == "Unknown Company"
        assert result["title"] == "Unknown Title"
        assert result["source"] == "unknown"
        assert result["salary_min"] is None
        assert result["salary_max"] is None
    
    def test_handles_nan_values(self):
        """normalise_job handles pandas NaN values."""
        import pandas as pd
        
        mock_row = MagicMock()
        mock_row.get = MagicMock(side_effect=lambda k, d=None: {
            "site": "indeed",
            "company": "Company",
            "title": "Title",
            "job_url": "https://test.com",
            "min_amount": float('nan'),  # NaN value
            "max_amount": pd.NA,  # Pandas NA
        }.get(k, d))
        
        result = normalise_job(mock_row)
        
        # NaN should be converted to None
        assert result["salary_min"] is None
    
    def test_handles_string_salary(self):
        """normalise_job handles salary as string."""
        mock_row = MagicMock()
        mock_row.get = MagicMock(side_effect=lambda k, d=None: {
            "site": "glassdoor",
            "company": "Company",
            "title": "Title",
            "job_url": "https://test.com",
            "min_amount": "45000",
            "max_amount": "65000.50",
        }.get(k, d))
        
        result = normalise_job(mock_row)
        
        assert result["salary_min"] == 45000
        assert result["salary_max"] == 65000
    
    def test_remote_type_mapping(self):
        """normalise_job maps remote types correctly."""
        test_cases = [
            (True, "remote"),
            (False, "onsite"),
            ("true", "remote"),
            ("false", "onsite"),
            ("hybrid", "hybrid"),
            (None, "onsite"),
        ]
        
        for input_val, expected in test_cases:
            mock_row = MagicMock()
            mock_row.get = MagicMock(side_effect=lambda k, d=None: {
                "company": "Test",
                "title": "Title",
                "job_url": "https://test.com",
                "is_remote": input_val,
            }.get(k, d))
            
            result = normalise_job(mock_row)
            assert result["remote_type"] == expected, f"Failed for input {input_val}"


@pytest.fixture
def test_db():
    """Provide a test database connection."""
    from setup_db import create_database_if_not_exists, run_schema
    
    db_url = get_test_db_url()
    
    try:
        create_database_if_not_exists(db_url)
    except Exception:
        pass
    
    run_schema(db_url)
    conn = psycopg2.connect(db_url)
    
    yield conn
    
    conn.close()


@pytest.fixture
def clean_search_db(test_db):
    """Provide clean tables for search tests."""
    with test_db.cursor() as cur:
        cur.execute("DELETE FROM job_status")
        cur.execute("DELETE FROM jobs")
    test_db.commit()
    return test_db


class TestInsertJobs:
    """Tests for the insert_jobs function."""
    
    def test_inserts_batch_of_jobs(self, clean_search_db):
        """insert_jobs inserts a batch of mock jobs into the database."""
        conn = clean_search_db
        
        mock_jobs = [
            {
                "source": "linkedin",
                "external_id": "1",
                "company": "Company A",
                "title": "Engineer",
                "location": "London",
                "remote_type": "hybrid",
                "salary_min": 50000,
                "salary_max": 70000,
                "currency": "GBP",
                "job_url": "https://linkedin.com/1",
                "description": "Job A with Python and AWS requirements",
                "job_description_raw": "Job A with Python and AWS requirements",
                "company_description_raw": "",
                "date_posted": date.today(),
                "search_term": "test",
            },
            {
                "source": "indeed",
                "external_id": "2",
                "company": "Company B",
                "title": "Developer",
                "location": "Manchester",
                "remote_type": "remote",
                "salary_min": 40000,
                "salary_max": 60000,
                "currency": "GBP",
                "job_url": "https://indeed.com/2",
                "description": "Job B with React and TypeScript",
                "job_description_raw": "Job B with React and TypeScript",
                "company_description_raw": "",
                "date_posted": date.today(),
                "search_term": "test",
            },
        ]
        
        attempted, inserted = insert_jobs(mock_jobs, conn, "test")
        
        assert attempted == 2
        assert inserted == 2
        
        # Verify in database
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM jobs")
            count = cur.fetchone()[0]
        
        assert count == 2
    
    def test_idempotent_on_duplicates(self, clean_search_db):
        """insert_jobs allows duplicate insertion (unique constraint removed)."""
        conn = clean_search_db
        
        job = {
            "source": "linkedin",
            "external_id": "dup1",
            "company": "DupeCo",
            "title": "Engineer",
            "location": "London",
            "remote_type": "onsite",
            "salary_min": None,
            "salary_max": None,
            "currency": "GBP",
            "job_url": "https://linkedin.com/dup",
            "description": "Duplicate test with Python experience",
            "job_description_raw": "Duplicate test with Python experience",
            "company_description_raw": "",
            "date_posted": date.today(),
            "search_term": "test",
        }
        
        # Insert once
        attempted1, inserted1 = insert_jobs([job], conn, "test")
        assert inserted1 == 1
        
        # Insert again - duplicates are now allowed
        attempted2, inserted2 = insert_jobs([job], conn, "test")
        assert inserted2 == 1  # Changed: duplicates now insert
        
        # Verify two entries in database (duplicates allowed)
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM jobs WHERE company = 'DupeCo'")
            count = cur.fetchone()[0]
        
        assert count == 2  # Changed: now 2 because duplicates allowed
    
    def test_allows_duplicates_after_constraint_removal(self, clean_search_db):
        """After removing unique constraint, duplicates are allowed."""
        conn = clean_search_db
        
        # Same company + title + date = was duplicate, now allowed
        job1 = {
            "source": "linkedin",
            "external_id": "1",
            "company": "TestCo",
            "title": "Software Engineer",
            "date_posted": date(2026, 3, 1),
            "job_url": "https://linkedin.com/1",
            "location": None,
            "remote_type": None,
            "salary_min": None,
            "salary_max": None,
            "currency": "GBP",
            "description": "Test job",
            "job_description_raw": "Test job",
            "company_description_raw": "",
            "search_term": "test",
        }
        
        job2 = {
            **job1,
            "source": "indeed",
            "external_id": "2",
            "job_url": "https://indeed.com/2",
            "job_description_raw": "",
            "company_description_raw": "",
        }
        
        insert_jobs([job1], conn, "test")
        _, inserted = insert_jobs([job2], conn, "test")
        
        # Duplicates are now allowed (unique constraint removed)
        assert inserted == 1


class TestEnrichment:
    """Tests for the enrichment module."""
    
    def test_extract_technologies_deterministic(self):
        """extract_technologies_deterministic correctly identifies tech keywords."""
        text = "We need someone with Python, React, and AWS experience. Must know Docker and Kubernetes."
        
        technologies = extract_technologies_deterministic(text)
        
        assert "python" in technologies
        assert "react" in technologies
        assert "aws" in technologies
        assert "docker" in technologies
        assert "kubernetes" in technologies
    
    def test_extract_technologies_case_insensitive(self):
        """Technology extraction is case-insensitive."""
        text = "PYTHON, JavaScript, and typescript required"
        
        technologies = extract_technologies_deterministic(text)
        
        assert "python" in technologies
        assert "javascript" in technologies
        assert "typescript" in technologies
    
    def test_extract_technologies_empty_text(self):
        """Empty text returns empty list."""
        technologies = extract_technologies_deterministic("")
        assert technologies == []
    
    @pytest.mark.slow
    def test_build_enrichment_returns_correct_structure(self):
        """build_enrichment returns proper structure with version and timestamp."""
        text = "Looking for a Python developer with strong communication skills and ability to work in a team."
        
        enrichment = build_enrichment(text)
        
        assert "technologies" in enrichment
        assert "skills" in enrichment
        assert "abilities" in enrichment
        assert "version" in enrichment
        assert "enriched_at" in enrichment
        assert enrichment["version"] == ENRICHMENT_VERSION
        assert "python" in enrichment["technologies"]


class TestLiveSearch:
    """Tests that run against real JobSpy API."""
    
    @pytest.mark.slow
    def test_live_search_linkedin(self):
        """Test LinkedIn search returns results."""
        config = {
            "search": {
                "site_name": ["linkedin"],
                "location": "London, UK",
                "results_wanted": 3,
                "hours_old": 72,
                "linkedin_fetch_description": True,
            }
        }
        
        jobs = run_search(config, "software engineer")
        
        print(f"\\nLinkedIn search returned {len(jobs)} jobs")
        for job in jobs[:2]:
            print(f"  - {job['source']}: {job['company']} - {job['title']}")
        
        assert len(jobs) >= 1, "LinkedIn should return at least 1 result"
        assert jobs[0]["source"] == "linkedin"
        assert jobs[0]["company"]
        assert jobs[0]["title"]
    
    @pytest.mark.slow
    def test_live_search_indeed(self):
        """Test Indeed search returns results."""
        config = {
            "search": {
                "site_name": ["indeed"],
                "location": "London, UK",
                "results_wanted": 3,
                "hours_old": 72,
                "country_indeed": "UK",
            }
        }
        
        jobs = run_search(config, "software engineer")
        
        print(f"\\nIndeed search returned {len(jobs)} jobs")
        for job in jobs[:2]:
            print(f"  - {job['source']}: {job['company']} - {job['title']}")
        
        assert len(jobs) >= 1, "Indeed should return at least 1 result"
        assert jobs[0]["source"] == "indeed"
    
    @pytest.mark.slow
    def test_live_search_glassdoor(self):
        """Test Glassdoor search returns results."""
        config = {
            "search": {
                "site_name": ["glassdoor"],
                "location": "London, UK",  # City-level location for Glassdoor
                "results_wanted": 3,
                "hours_old": 72,
            }
        }
        
        jobs = run_search(config, "software engineer")
        
        print(f"\\nGlassdoor search returned {len(jobs)} jobs")
        for job in jobs[:2]:
            print(f"  - {job['source']}: {job['company']} - {job['title']}")
        
        # Glassdoor may not always return results due to rate limiting
        if len(jobs) >= 1:
            assert jobs[0]["source"] == "glassdoor"
    
    @pytest.mark.slow  
    def test_live_search_google(self):
        """Test Google Jobs search returns results."""
        config = {
            "search": {
                "site_name": ["google"],
                "location": "London, UK",
                "results_wanted": 3,
                "hours_old": 72,
            }
        }
        
        jobs = run_search(config, "software engineer")
        
        print(f"\\nGoogle search returned {len(jobs)} jobs")
        for job in jobs[:2]:
            print(f"  - {job['source']}: {job['company']} - {job['title']}")
        
        # Google Jobs may not always return results
        if len(jobs) >= 1:
            assert jobs[0]["source"] == "google"
    
    @pytest.mark.slow
    def test_live_search_all_sources(self):
        """Test aggregation from all sources."""
        config = {
            "search": {
                "site_name": ["linkedin", "indeed", "glassdoor", "google"],
                "location": "London, UK",
                "results_wanted": 5,
                "hours_old": 72,
                "country_indeed": "UK",
                "linkedin_fetch_description": True,
            }
        }
        
        jobs = run_search(config, "software engineer")
        
        print(f"\\nAll sources search returned {len(jobs)} jobs")
        sources_found = set()
        for job in jobs:
            sources_found.add(job["source"])
            print(f"  - {job['source']}: {job['company']} - {job['title']}")
        
        print(f"\\nSources found: {sources_found}")
        
        assert len(jobs) >= 1, "Should return at least 1 job from any source"
        
        # Verify job structure
        first_job = jobs[0]
        assert first_job["company"], "Job should have company"
        assert first_job["title"], "Job should have title"
        assert first_job["job_url"], "Job should have URL"
        assert "job_description_raw" in first_job, "Job should have job_description_raw"
        assert "company_description_raw" in first_job, "Job should have company_description_raw"
