"""Phase 2 tests - Database schema for CV generation."""

import os
import uuid
import pytest
import psycopg2
from dotenv import load_dotenv

load_dotenv()


@pytest.fixture
def db_conn():
    """Create database connection for testing."""
    conn = psycopg2.connect(os.getenv('DATABASE_URL'))
    conn.autocommit = True
    yield conn
    conn.close()


class TestDatabaseSchema:
    """Test Phase 2 database schema."""
    
    def test_cv_sessions_table_exists(self, db_conn):
        """cv_sessions table should exist."""
        cur = db_conn.cursor()
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'cv_sessions'
            )
        """)
        assert cur.fetchone()[0] is True
        cur.close()
    
    def test_cv_feedback_table_exists(self, db_conn):
        """cv_feedback table should exist."""
        cur = db_conn.cursor()
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'cv_feedback'
            )
        """)
        assert cur.fetchone()[0] is True
        cur.close()
    
    def test_jobs_has_user_id(self, db_conn):
        """jobs table should have user_id column."""
        cur = db_conn.cursor()
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = 'jobs' AND column_name = 'user_id'
            )
        """)
        assert cur.fetchone()[0] is True
        cur.close()
    
    def test_job_status_has_user_id(self, db_conn):
        """job_status table should have user_id column."""
        cur = db_conn.cursor()
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = 'job_status' AND column_name = 'user_id'
            )
        """)
        assert cur.fetchone()[0] is True
        cur.close()
    
    def test_application_packs_has_user_id(self, db_conn):
        """application_packs table should have user_id column."""
        cur = db_conn.cursor()
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = 'application_packs' AND column_name = 'user_id'
            )
        """)
        assert cur.fetchone()[0] is True
        cur.close()
    
    def test_cv_sessions_columns(self, db_conn):
        """cv_sessions should have all required columns."""
        cur = db_conn.cursor()
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'cv_sessions'
        """)
        columns = {r[0] for r in cur.fetchall()}
        required = {
            'id', 'user_id', 'job_id', 'role_family', 'seniority_level',
            'required_keywords', 'nice_to_have_keywords', 'technical_keywords',
            'selection_plan', 'hidden_projects', 'status', 'created_at', 'completed_at'
        }
        assert required.issubset(columns), f"Missing: {required - columns}"
        cur.close()
    
    def test_cv_feedback_columns(self, db_conn):
        """cv_feedback should have all required columns."""
        cur = db_conn.cursor()
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'cv_feedback'
        """)
        columns = {r[0] for r in cur.fetchall()}
        required = {
            'id', 'user_id', 'job_id', 'session_id', 'slot_section',
            'slot_subsection', 'slot_index', 'original_text', 'final_text',
            'was_approved', 'rephrase_generation', 'source', 'keyword_hits',
            'relevance_score', 'created_at'
        }
        assert required.issubset(columns), f"Missing: {required - columns}"
        cur.close()
    
    def test_cv_sessions_uuid_default(self, db_conn):
        """cv_sessions.id should auto-generate UUID."""
        cur = db_conn.cursor()
        # Insert without specifying id
        cur.execute("""
            INSERT INTO cv_sessions (user_id, status)
            VALUES (1, 'test')
            RETURNING id
        """)
        session_id = cur.fetchone()[0]
        assert session_id is not None
        # psycopg2 returns UUID as string, validate it's a valid UUID format
        parsed = uuid.UUID(str(session_id))
        assert parsed is not None
        # Clean up
        cur.execute("DELETE FROM cv_sessions WHERE id = %s", (session_id,))
        cur.close()
    
    def test_user_id_defaults_to_1(self, db_conn):
        """user_id columns should default to 1."""
        cur = db_conn.cursor()
        
        # Check cv_sessions default
        cur.execute("""
            SELECT column_default FROM information_schema.columns
            WHERE table_name = 'cv_sessions' AND column_name = 'user_id'
        """)
        assert cur.fetchone()[0] == '1'
        
        # Check cv_feedback default
        cur.execute("""
            SELECT column_default FROM information_schema.columns
            WHERE table_name = 'cv_feedback' AND column_name = 'user_id'
        """)
        assert cur.fetchone()[0] == '1'
        
        cur.close()


class TestIndexes:
    """Test that indexes were created."""
    
    def test_cv_sessions_indexes(self, db_conn):
        """cv_sessions should have indexes on user_id, job_id, status."""
        cur = db_conn.cursor()
        cur.execute("""
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'cv_sessions'
        """)
        indexes = {r[0] for r in cur.fetchall()}
        assert 'idx_cv_sessions_user_id' in indexes
        assert 'idx_cv_sessions_job_id' in indexes
        assert 'idx_cv_sessions_status' in indexes
        cur.close()
    
    def test_cv_feedback_indexes(self, db_conn):
        """cv_feedback should have indexes on user_id, job_id, session_id."""
        cur = db_conn.cursor()
        cur.execute("""
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'cv_feedback'
        """)
        indexes = {r[0] for r in cur.fetchall()}
        assert 'idx_cv_feedback_user_id' in indexes
        assert 'idx_cv_feedback_job_id' in indexes
        assert 'idx_cv_feedback_session_id' in indexes
        assert 'idx_cv_feedback_approved' in indexes
        cur.close()
