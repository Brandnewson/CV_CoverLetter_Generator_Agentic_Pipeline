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
                "description": "Job A",
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
                "description": "Job B",
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
        """insert_jobs does not error on duplicate insertion."""
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
            "description": "Duplicate test",
            "date_posted": date.today(),
            "search_term": "test",
        }
        
        # Insert once
        attempted1, inserted1 = insert_jobs([job], conn, "test")
        assert inserted1 == 1
        
        # Insert again - should not error, should not insert
        attempted2, inserted2 = insert_jobs([job], conn, "test")
        assert inserted2 == 0
        
        # Verify only one in database
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM jobs WHERE company = 'DupeCo'")
            count = cur.fetchone()[0]
        
        assert count == 1
    
    def test_dedup_constraint_works(self, clean_search_db):
        """The (company, title, date_posted) constraint prevents duplicates correctly."""
        conn = clean_search_db
        
        # Same company + title + date = duplicate
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
            "description": "",
            "search_term": "test",
        }
        
        job2 = {
            **job1,
            "source": "indeed",
            "external_id": "2",
            "job_url": "https://indeed.com/2",
        }
        
        insert_jobs([job1], conn, "test")
        _, inserted = insert_jobs([job2], conn, "test")
        
        assert inserted == 0


class TestLiveSearch:
    """Tests that run against real JobSpy API."""
    
    @pytest.mark.slow
    def test_live_search_returns_results(self):
        """Run one real search with minimal results to verify connectivity."""
        config = {
            "search": {
                "site_name": ["indeed"],  # Just one source for speed
                "location": "United Kingdom",
                "results_wanted": 5,
                "hours_old": 72,
                "country_indeed": "UK",
            }
        }
        
        jobs = run_search(config, "software engineer")
        
        # Print results for visibility
        print(f"\n\nLive search returned {len(jobs)} jobs:")
        for job in jobs[:3]:
            print(f"  - {job['company']}: {job['title']}")
            print(f"    URL: {job['job_url'][:60]}...")
        
        # Assert at least 1 result with required fields
        assert len(jobs) >= 1, "Live search should return at least 1 result"
        
        first_job = jobs[0]
        assert first_job["company"], "Job should have company"
        assert first_job["title"], "Job should have title"
        assert first_job["job_url"], "Job should have URL"
