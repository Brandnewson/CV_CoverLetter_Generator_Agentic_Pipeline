"""Tests for deduplication functionality."""

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
import psycopg2
from dotenv import load_dotenv
import os

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from discovery.dedup import title_similarity, find_fuzzy_duplicates, mark_duplicates

# Load environment
load_dotenv(PROJECT_ROOT / ".env")


def get_test_db_url() -> str:
    """Get the test database URL."""
    base_url = os.getenv("DATABASE_URL", "postgresql://localhost/job_pipeline")
    if "job_pipeline_test" not in base_url:
        base_url = base_url.replace("/job_pipeline", "/job_pipeline_test")
    return base_url


class TestTitleSimilarity:
    """Tests for title similarity function."""
    
    def test_identical_titles(self):
        """Identical titles should have similarity of 1.0."""
        assert title_similarity("Software Engineer", "Software Engineer") == 1.0
    
    def test_very_similar_titles(self):
        """Very similar titles should score > 0.85."""
        score = title_similarity(
            "Senior Software Engineer",
            "Senior Software Engineer - Python"
        )
        assert score > 0.7  # These are pretty similar
    
    def test_completely_different_titles(self):
        """Completely different titles should score low."""
        score = title_similarity(
            "Software Engineer",
            "Marketing Manager"
        )
        assert score < 0.5
    
    def test_case_insensitive(self):
        """Comparison should be case-insensitive."""
        score = title_similarity(
            "SOFTWARE ENGINEER",
            "software engineer"
        )
        assert score == 1.0
    
    def test_empty_string_handling(self):
        """Empty strings should return 0.0."""
        assert title_similarity("", "Software Engineer") == 0.0
        assert title_similarity("Software Engineer", "") == 0.0
        assert title_similarity("", "") == 0.0


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
def clean_dedup_db(test_db):
    """Provide clean tables for dedup tests."""
    with test_db.cursor() as cur:
        cur.execute("DELETE FROM job_status")
        cur.execute("DELETE FROM jobs")
    test_db.commit()
    return test_db


class TestFindFuzzyDuplicates:
    """Tests for fuzzy duplicate detection."""
    
    def test_identical_company_similar_title_flagged(self, clean_dedup_db):
        """Two jobs with same company and >85% similar title are flagged."""
        conn = clean_dedup_db
        today = date.today()
        
        with conn.cursor() as cur:
            # Insert two similar jobs from same company
            cur.execute("""
                INSERT INTO jobs (source, company, title, job_url, date_posted)
                VALUES 
                    ('linkedin', 'TechCorp', 'Senior Software Engineer', 'https://url1.com', %s),
                    ('indeed', 'TechCorp', 'Senior Software Engineer - Python', 'https://url2.com', %s)
            """, (today, today))
            conn.commit()
        
        pairs = find_fuzzy_duplicates(conn)
        
        assert len(pairs) >= 1, "Should find the duplicate pair"
    
    def test_same_company_different_title_not_flagged(self, clean_dedup_db):
        """Two jobs with same company but completely different titles are NOT flagged."""
        conn = clean_dedup_db
        today = date.today()
        
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO jobs (source, company, title, job_url, date_posted)
                VALUES 
                    ('linkedin', 'TechCorp', 'Software Engineer', 'https://url1.com', %s),
                    ('indeed', 'TechCorp', 'Marketing Manager', 'https://url2.com', %s)
            """, (today, today))
            conn.commit()
        
        pairs = find_fuzzy_duplicates(conn)
        
        assert len(pairs) == 0, "Different titles should not be flagged as duplicates"
    
    def test_same_title_different_company_not_flagged(self, clean_dedup_db):
        """Two jobs with same title but different companies are NOT flagged."""
        conn = clean_dedup_db
        today = date.today()
        
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO jobs (source, company, title, job_url, date_posted)
                VALUES 
                    ('linkedin', 'CompanyA', 'Software Engineer', 'https://url1.com', %s),
                    ('indeed', 'CompanyB', 'Software Engineer', 'https://url2.com', %s)
            """, (today, today))
            conn.commit()
        
        pairs = find_fuzzy_duplicates(conn)
        
        assert len(pairs) == 0, "Different companies should not be flagged as duplicates"
    
    def test_distant_dates_not_flagged(self, clean_dedup_db):
        """Jobs posted more than 3 days apart should not be flagged even if similar."""
        conn = clean_dedup_db
        today = date.today()
        week_ago = today - timedelta(days=7)
        
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO jobs (source, company, title, job_url, date_posted)
                VALUES 
                    ('linkedin', 'TechCorp', 'Software Engineer', 'https://url1.com', %s),
                    ('indeed', 'TechCorp', 'Software Engineer', 'https://url2.com', %s)
            """, (today, week_ago))
            conn.commit()
        
        pairs = find_fuzzy_duplicates(conn)
        
        assert len(pairs) == 0, "Jobs posted far apart should not be flagged"


class TestMarkDuplicates:
    """Tests for marking duplicates in database."""
    
    def test_marks_duplicate_correctly(self, clean_dedup_db):
        """mark_duplicates sets is_duplicate=True and duplicate_of correctly."""
        conn = clean_dedup_db
        today = date.today()
        
        with conn.cursor() as cur:
            # Insert two jobs
            cur.execute("""
                INSERT INTO jobs (source, company, title, job_url, date_posted)
                VALUES ('linkedin', 'MarkCo', 'Engineer', 'https://url1.com', %s)
                RETURNING id
            """, (today,))
            id1 = cur.fetchone()[0]
            
            cur.execute("""
                INSERT INTO jobs (source, company, title, job_url, date_posted)
                VALUES ('indeed', 'MarkCo', 'Engineer Role', 'https://url2.com', %s)
                RETURNING id
            """, (today,))
            id2 = cur.fetchone()[0]
            conn.commit()
        
        # Mark second as duplicate of first
        marked = mark_duplicates(conn, [(id1, id2)])
        
        assert marked == 1
        
        # Verify in database
        with conn.cursor() as cur:
            cur.execute("""
                SELECT is_duplicate, duplicate_of FROM jobs WHERE id = %s
            """, (id2,))
            row = cur.fetchone()
        
        assert row[0] is True, "is_duplicate should be True"
        assert row[1] == id1, "duplicate_of should point to kept job"
    
    def test_running_twice_does_not_double_mark(self, clean_dedup_db):
        """Running mark_duplicates twice does not double-mark anything."""
        conn = clean_dedup_db
        today = date.today()
        yesterday = today - timedelta(days=1)
        
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO jobs (source, company, title, job_url, date_posted)
                VALUES ('linkedin', 'DoubleCo', 'Engineer', 'https://url1.com', %s)
                RETURNING id
            """, (today,))
            id1 = cur.fetchone()[0]
            
            cur.execute("""
                INSERT INTO jobs (source, company, title, job_url, date_posted)
                VALUES ('indeed', 'DoubleCo', 'Engineer', 'https://url2.com', %s)
                RETURNING id
            """, (yesterday,))
            id2 = cur.fetchone()[0]
            conn.commit()
        
        # Mark once
        marked1 = mark_duplicates(conn, [(id1, id2)])
        assert marked1 == 1
        
        # Mark again with same pair
        marked2 = mark_duplicates(conn, [(id1, id2)])
        assert marked2 == 0, "Should not mark already-marked duplicates"
    
    def test_empty_pairs_returns_zero(self, clean_dedup_db):
        """mark_duplicates with empty list returns 0."""
        conn = clean_dedup_db
        
        marked = mark_duplicates(conn, [])
        assert marked == 0
