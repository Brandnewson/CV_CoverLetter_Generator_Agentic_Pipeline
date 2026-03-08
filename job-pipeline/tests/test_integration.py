"""End-to-end integration tests for the job pipeline."""

import sys
import os
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
        pass
    
    # Run schema
    run_schema(db_url)
    
    # Create connection
    conn = psycopg2.connect(db_url)
    
    yield conn
    
    conn.close()


@pytest.fixture
def clean_integration_db(test_db):
    """Provide clean tables for integration tests."""
    with test_db.cursor() as cur:
        cur.execute("DELETE FROM application_packs")
        cur.execute("DELETE FROM search_runs")
        cur.execute("DELETE FROM job_status")
        cur.execute("DELETE FROM jobs")
    test_db.commit()
    return test_db


class TestFullPipeline:
    """End-to-end integration tests."""
    
    @pytest.mark.slow
    def test_full_pipeline(self, clean_integration_db):
        """
        End-to-end test:
        1. Run a real JobSpy search (results_wanted=5, hours_old=72, one term only)
        2. Insert into test DB
        3. Run deduplication
        4. Score with OpenAI (real API call)
        5. Query ranked shortlist
        6. Assert: at least 1 job returned, scored, with fit_score > 0
        7. Print the full shortlist table
        """
        from discovery.run_search import run_search, insert_jobs
        from discovery.dedup import run_deduplication
        from discovery.scorer import score_pending_jobs, load_scoring_profile
        from openai import OpenAI
        
        conn = clean_integration_db
        
        # Check for API key
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            pytest.skip("OPENAI_API_KEY not set - skipping live integration test")
        
        print("\n" + "=" * 60)
        print("FULL PIPELINE INTEGRATION TEST")
        print("=" * 60)
        
        # Step 1: Run JobSpy search
        print("\n[1/5] Running JobSpy search...")
        config = {
            "search": {
                "site_name": ["indeed"],
                "location": "United Kingdom",
                "results_wanted": 5,
                "hours_old": 72,
                "country_indeed": "UK",
            },
            "exclusions": {
                "title_keywords": ["junior", "graduate", "intern"],
                "description_keywords": ["unpaid"],
            },
            "scoring": {
                "salary_floor": 40000,
            }
        }
        
        jobs = run_search(config, "AI engineer")
        print(f"     Found {len(jobs)} jobs")
        assert len(jobs) >= 1, "Search should return at least 1 job"
        
        # Step 2: Insert into database
        print("\n[2/5] Inserting into database...")
        attempted, inserted = insert_jobs(jobs, conn, "AI engineer")
        print(f"     Attempted: {attempted}, Inserted: {inserted}")
        assert inserted >= 1, "Should insert at least 1 new job"
        
        # Step 3: Run deduplication
        print("\n[3/5] Running deduplication...")
        from discovery.dedup import run_deduplication
        pairs_found, pairs_marked = run_deduplication(conn)
        print(f"     Pairs found: {pairs_found}, Marked: {pairs_marked}")
        
        # Step 4: Score with OpenAI
        print("\n[4/5] Scoring jobs with OpenAI...")
        profile = load_scoring_profile()
        client = OpenAI(api_key=api_key)
        scored = score_pending_jobs(conn, profile, client)
        print(f"     Scored: {scored} jobs")
        
        # Step 5: Query ranked shortlist
        print("\n[5/5] Querying ranked shortlist...")
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    j.id,
                    j.company,
                    j.title,
                    j.location,
                    j.source,
                    js.fit_score,
                    js.fit_summary
                FROM jobs j
                JOIN job_status js ON js.job_id = j.id
                WHERE j.is_duplicate = FALSE
                  AND js.fit_score IS NOT NULL
                ORDER BY js.fit_score DESC
            """)
            
            results = cur.fetchall()
        
        # Print results as table
        print("\n" + "-" * 80)
        print("RANKED SHORTLIST")
        print("-" * 80)
        print(f"{'ID':<5} {'Score':<6} {'Company':<25} {'Title':<30}")
        print("-" * 80)
        
        for row in results:
            job_id, company, title, location, source, score, summary = row
            print(f"{job_id:<5} {score:.2f}  {company[:24]:<25} {title[:29]:<30}")
            if summary:
                print(f"      Summary: {summary[:70]}...")
        
        print("-" * 80)
        
        # Assertions
        assert len(results) >= 1, "Should have at least 1 scored job"
        
        # Check that at least one job has fit_score > 0
        scores = [r[5] for r in results]
        assert any(s > 0 for s in scores), "At least one job should have fit_score > 0"
        
        print("\n✓ Full pipeline test PASSED!")
        print("=" * 60)


class TestComponentIntegration:
    """Tests for component interactions."""
    
    def test_search_to_dedup_integration(self, clean_integration_db):
        """Test that search results flow correctly into deduplication."""
        from discovery.run_search import insert_jobs
        from discovery.dedup import find_fuzzy_duplicates
        
        conn = clean_integration_db
        
        # Insert some test jobs that should trigger dedup
        test_jobs = [
            {
                "source": "linkedin",
                "external_id": "1",
                "company": "AI Corp",
                "title": "Senior AI Engineer",
                "location": "London",
                "remote_type": "hybrid",
                "salary_min": 70000,
                "salary_max": 90000,
                "currency": "GBP",
                "job_url": "https://linkedin.com/job/1",
                "description": "Build AI systems",
                "date_posted": date.today(),
                "search_term": "AI engineer",
            },
            {
                "source": "indeed",
                "external_id": "2",
                "company": "AI Corp",  # Same company
                "title": "Senior AI Engineer - Python",  # Similar title
                "location": "London",
                "remote_type": "hybrid",
                "salary_min": 70000,
                "salary_max": 90000,
                "currency": "GBP",
                "job_url": "https://indeed.com/job/2",
                "description": "Build AI systems using Python",
                "date_posted": date.today(),  # Same date
                "search_term": "AI engineer",
            },
        ]
        
        # Insert
        attempted, inserted = insert_jobs(test_jobs, conn, "AI engineer")
        assert inserted == 2
        
        # Find duplicates
        pairs = find_fuzzy_duplicates(conn)
        
        # These should be flagged as potential duplicates
        assert len(pairs) >= 1, "Similar jobs from same company should be flagged"
    
    def test_filter_before_score(self, clean_integration_db):
        """Test that hard filters prevent unnecessary API calls."""
        from discovery.scorer import apply_hard_filters, load_config
        
        config = {
            "exclusions": {
                "title_keywords": ["junior", "intern"],
                "description_keywords": [],
            },
            "scoring": {
                "salary_floor": 40000,
            }
        }
        
        jobs = [
            {"title": "Junior Engineer", "description": "", "salary_max": 50000},  # Should skip
            {"title": "Senior Engineer", "description": "", "salary_max": 30000},  # Should skip
            {"title": "AI Engineer", "description": "", "salary_max": 80000},  # Should pass
            {"title": "Software Engineer", "description": "", "salary_max": None},  # Should pass
        ]
        
        passed = []
        skipped = []
        
        for job in jobs:
            should_skip, reason = apply_hard_filters(job, config)
            if should_skip:
                skipped.append((job["title"], reason))
            else:
                passed.append(job["title"])
        
        assert len(skipped) == 2, "Should skip 2 jobs"
        assert len(passed) == 2, "Should pass 2 jobs"
        assert "Junior Engineer" in [s[0] for s in skipped]
        assert "Senior Engineer" in [s[0] for s in skipped]
