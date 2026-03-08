"""Tests for database setup and operations."""

import os
import sys
from datetime import date
from pathlib import Path

import pytest
import psycopg2
from dotenv import load_dotenv

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load environment
load_dotenv(PROJECT_ROOT / ".env")


def get_test_db_url() -> str:
    """Get the test database URL."""
    base_url = os.getenv("DATABASE_URL", "postgresql://localhost/job_pipeline")
    # Use test database
    if "job_pipeline_test" not in base_url:
        base_url = base_url.replace("/job_pipeline", "/job_pipeline_test")
    return base_url


@pytest.fixture(scope="module")
def test_db():
    """Create and provide a test database connection."""
    from setup_db import create_database_if_not_exists, run_schema
    
    db_url = get_test_db_url()
    
    # Create test database
    try:
        create_database_if_not_exists(db_url)
    except Exception:
        pass  # Database might already exist
    
    # Run schema
    run_schema(db_url)
    
    # Create connection
    conn = psycopg2.connect(db_url)
    
    yield conn
    
    # Cleanup
    conn.close()


@pytest.fixture
def clean_db(test_db):
    """Provide a clean database for each test by clearing tables."""
    with test_db.cursor() as cur:
        cur.execute("DELETE FROM application_packs")
        cur.execute("DELETE FROM job_status")
        cur.execute("DELETE FROM jobs")
        cur.execute("DELETE FROM search_runs")
    test_db.commit()
    return test_db


class TestDatabaseSetup:
    """Tests for database setup functionality."""
    
    def test_setup_db_runs_without_error(self, test_db):
        """setup_db.py should run without errors."""
        # If we got a test_db fixture, setup already succeeded
        assert test_db is not None
    
    def test_all_tables_exist(self, test_db):
        """All four required tables must exist."""
        with test_db.cursor() as cur:
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
            """)
            tables = {row[0] for row in cur.fetchall()}
        
        required_tables = {"jobs", "job_status", "application_packs", "search_runs"}
        assert required_tables.issubset(tables), \
            f"Missing tables: {required_tables - tables}"
    
    def test_schema_idempotent(self, test_db):
        """Running schema twice should not error."""
        from setup_db import run_schema
        
        db_url = get_test_db_url()
        
        # Run schema again - should not error
        tables = run_schema(db_url)
        assert "jobs" in tables
    
    def test_can_insert_and_retrieve_job(self, clean_db):
        """A test row can be inserted and retrieved from jobs table."""
        conn = clean_db
        
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO jobs (source, company, title, job_url, date_posted)
                VALUES ('test', 'Test Company', 'Test Title', 'https://test.com', %s)
                RETURNING id
            """, (date.today(),))
            
            job_id = cur.fetchone()[0]
            conn.commit()
            
            # Retrieve
            cur.execute("SELECT company, title FROM jobs WHERE id = %s", (job_id,))
            row = cur.fetchone()
        
        assert row is not None
        assert row[0] == "Test Company"
        assert row[1] == "Test Title"


class TestJobOperations:
    """Tests for job-related database operations."""
    
    def test_unique_constraint_prevents_duplicates(self, clean_db):
        """The unique constraint on (company, title, date_posted) works."""
        conn = clean_db
        today = date.today()
        
        with conn.cursor() as cur:
            # Insert first job
            cur.execute("""
                INSERT INTO jobs (source, company, title, job_url, date_posted)
                VALUES ('linkedin', 'DupeCo', 'Engineer', 'https://url1.com', %s)
            """, (today,))
            conn.commit()
            
            # Try to insert duplicate - should not raise but return nothing
            cur.execute("""
                INSERT INTO jobs (source, company, title, job_url, date_posted)
                VALUES ('indeed', 'DupeCo', 'Engineer', 'https://url2.com', %s)
                ON CONFLICT (company, title, date_posted) DO NOTHING
                RETURNING id
            """, (today,))
            
            result = cur.fetchone()
        
        assert result is None, "Duplicate was inserted when it should have been blocked"
    
    def test_job_status_updates(self, clean_db):
        """Job status can be updated correctly."""
        conn = clean_db
        
        with conn.cursor() as cur:
            # Insert job
            cur.execute("""
                INSERT INTO jobs (source, company, title, job_url, date_posted)
                VALUES ('test', 'StatusCo', 'StatusJob', 'https://status.com', %s)
                RETURNING id
            """, (date.today(),))
            job_id = cur.fetchone()[0]
            
            # Insert job_status
            cur.execute("""
                INSERT INTO job_status (job_id, status)
                VALUES (%s, 'new')
            """, (job_id,))
            conn.commit()
            
            # Update to queued
            cur.execute("""
                UPDATE job_status SET status = 'queued' WHERE job_id = %s
                RETURNING status
            """, (job_id,))
            
            new_status = cur.fetchone()[0]
            conn.commit()
        
        assert new_status == "queued"
    
    def test_dashboard_query_returns_ordered(self, clean_db):
        """Dashboard query returns results ordered by fit_score DESC."""
        conn = clean_db
        
        with conn.cursor() as cur:
            # Insert multiple jobs with different scores
            for i, (company, score) in enumerate([
                ("LowScore Co", 0.3),
                ("HighScore Co", 0.9),
                ("MidScore Co", 0.6),
            ]):
                cur.execute("""
                    INSERT INTO jobs (source, company, title, job_url, date_posted)
                    VALUES ('test', %s, 'Engineer', %s, %s)
                    RETURNING id
                """, (company, f"https://{company.replace(' ', '')}.com", date.today()))
                job_id = cur.fetchone()[0]
                
                cur.execute("""
                    INSERT INTO job_status (job_id, fit_score, status)
                    VALUES (%s, %s, 'new')
                """, (job_id, score))
            
            conn.commit()
            
            # Query like dashboard does
            cur.execute("""
                SELECT j.company, js.fit_score
                FROM jobs j
                JOIN job_status js ON js.job_id = j.id
                WHERE js.status = 'new'
                ORDER BY js.fit_score DESC
            """)
            
            results = cur.fetchall()
        
        assert len(results) == 3
        assert results[0][0] == "HighScore Co"
        assert results[1][0] == "MidScore Co"
        assert results[2][0] == "LowScore Co"
    
    def test_invalid_job_id_does_not_crash(self, clean_db):
        """Updating with invalid job ID should not crash."""
        conn = clean_db
        
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE job_status SET status = 'queued' WHERE job_id = 99999
                RETURNING job_id
            """)
            result = cur.fetchone()
        
        assert result is None
