"""Tests for job fit scoring functionality."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import psycopg2
from dotenv import load_dotenv
import os
import json

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from discovery.scorer import apply_hard_filters, score_job, load_scoring_profile

# Load environment
load_dotenv(PROJECT_ROOT / ".env")


class TestApplyHardFilters:
    """Tests for the hard filter function."""
    
    @pytest.fixture
    def config(self):
        """Provide test configuration."""
        return {
            "exclusions": {
                "title_keywords": ["junior", "graduate", "intern", "internship", "sales", "marketing"],
                "description_keywords": ["unpaid", "graduate scheme"],
            },
            "scoring": {
                "salary_floor": 40000,
            }
        }
    
    def test_rejects_junior_title(self, config):
        """apply_hard_filters correctly rejects a job titled 'Junior Strategy Engineer'."""
        job = {
            "title": "Junior Strategy Engineer",
            "description": "Great opportunity...",
            "salary_min": 50000,
            "salary_max": 60000,
        }
        
        should_skip, reason = apply_hard_filters(job, config)
        
        assert should_skip is True
        assert "junior" in reason.lower()
    
    def test_rejects_low_salary(self, config):
        """apply_hard_filters correctly rejects a job with salary_max=30000."""
        job = {
            "title": "Software Engineer",
            "description": "Great opportunity...",
            "salary_min": 25000,
            "salary_max": 30000,
        }
        
        should_skip, reason = apply_hard_filters(job, config)
        
        assert should_skip is True
        assert "salary" in reason.lower()
    
    def test_rejects_sales_title(self, config):
        """apply_hard_filters correctly rejects a job with 'sales' in the title."""
        job = {
            "title": "Sales Engineer",
            "description": "Join our team...",
            "salary_min": None,
            "salary_max": None,
        }
        
        should_skip, reason = apply_hard_filters(job, config)
        
        assert should_skip is True
        assert "sales" in reason.lower()
    
    def test_rejects_unpaid_description(self, config):
        """apply_hard_filters rejects jobs with 'unpaid' in description."""
        job = {
            "title": "Software Engineer",
            "description": "This is an unpaid internship opportunity.",
            "salary_min": None,
            "salary_max": None,
        }
        
        should_skip, reason = apply_hard_filters(job, config)
        
        assert should_skip is True
        assert "unpaid" in reason.lower()
    
    def test_passes_valid_job(self, config):
        """apply_hard_filters passes a job with no exclusion triggers."""
        job = {
            "title": "Senior Software Engineer",
            "description": "Join our AI team to build cutting-edge robotics systems.",
            "salary_min": 60000,
            "salary_max": 80000,
        }
        
        should_skip, reason = apply_hard_filters(job, config)
        
        assert should_skip is False
        assert reason == ""
    
    def test_passes_job_with_no_salary(self, config):
        """apply_hard_filters passes jobs with no salary stated."""
        job = {
            "title": "Machine Learning Engineer",
            "description": "Exciting opportunity in AI.",
            "salary_min": None,
            "salary_max": None,
        }
        
        should_skip, reason = apply_hard_filters(job, config)
        
        assert should_skip is False
    
    def test_case_insensitive_title(self, config):
        """Filtering should be case-insensitive."""
        job = {
            "title": "JUNIOR Developer",
            "description": "Entry level position",
            "salary_min": 35000,
            "salary_max": 45000,
        }
        
        should_skip, reason = apply_hard_filters(job, config)
        
        assert should_skip is True
    
    def test_rejects_3plus_years_experience(self, config):
        """apply_hard_filters rejects jobs requiring 3+ years of experience."""
        job = {
            "title": "Software Engineer",
            "description": "We're looking for someone with 3+ years of experience in Python.",
            "salary_min": 50000,
            "salary_max": 70000,
        }
        
        should_skip, reason = apply_hard_filters(job, config)
        
        assert should_skip is True
        assert "experience" in reason.lower()
    
    def test_rejects_5_years_experience(self, config):
        """apply_hard_filters rejects jobs requiring 5 years experience."""
        job = {
            "title": "AI Engineer",
            "description": "Requirements: Minimum 5 years experience in machine learning.",
            "salary_min": None,
            "salary_max": None,
        }
        
        should_skip, reason = apply_hard_filters(job, config)
        
        assert should_skip is True
        assert "5" in reason
    
    def test_passes_1_year_experience(self, config):
        """apply_hard_filters passes jobs requiring only 1 year experience."""
        job = {
            "title": "Software Engineer",
            "description": "Looking for candidates with 1 year of experience.",
            "salary_min": 45000,
            "salary_max": 60000,
        }
        
        should_skip, reason = apply_hard_filters(job, config)
        
        assert should_skip is False
    
    def test_passes_2_years_experience(self, config):
        """apply_hard_filters passes jobs requiring 2 years experience."""
        job = {
            "title": "Machine Learning Engineer",
            "description": "At least 2 years of relevant experience required.",
            "salary_min": None,
            "salary_max": None,
        }
        
        should_skip, reason = apply_hard_filters(job, config)
        
        assert should_skip is False


class TestScoreJob:
    """Tests for the score_job function."""
    
    @pytest.fixture
    def mock_profile(self):
        """Provide a mock scoring profile."""
        return {
            "target_roles": ["Software Engineer", "AI Engineer"],
            "industries": ["AI startups", "Robotics"],
            "must_have_keywords": ["AI", "machine learning", "Python"],
            "nice_to_have_keywords": ["Kubernetes", "distributed systems"],
            "core_strengths": ["Building AI systems", "Data pipelines"],
        }
    
    @pytest.fixture
    def mock_openai_client(self):
        """Provide a mock OpenAI client."""
        client = MagicMock()
        
        # Mock response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "fit_score": 0.85,
            "fit_summary": "Strong match for AI engineering role with Python and ML requirements.",
            "keyword_matches": {
                "matched": ["AI", "machine learning", "Python"],
                "missing": ["Kubernetes"]
            }
        })
        
        client.chat.completions.create.return_value = mock_response
        return client
    
    def test_returns_required_keys(self, mock_profile, mock_openai_client):
        """score_job returns a dict with all three required keys."""
        job = {
            "title": "AI Engineer",
            "company": "Tech Startup",
            "location": "London",
            "description": "Build AI systems using Python and machine learning.",
        }
        
        result = score_job(job, mock_profile, mock_openai_client)
        
        assert "fit_score" in result
        assert "fit_summary" in result
        assert "keyword_matches" in result
    
    def test_fit_score_in_range(self, mock_profile, mock_openai_client):
        """score_job returns fit_score between 0.0 and 1.0."""
        job = {
            "title": "AI Engineer",
            "company": "Tech Startup",
            "location": "London",
            "description": "Build AI systems.",
        }
        
        result = score_job(job, mock_profile, mock_openai_client)
        
        assert 0.0 <= result["fit_score"] <= 1.0
    
    def test_fit_summary_reasonable_length(self, mock_profile, mock_openai_client):
        """score_job returns fit_summary under 100 words."""
        job = {
            "title": "AI Engineer",
            "company": "Tech Startup",
            "location": "London",
            "description": "Build AI systems.",
        }
        
        result = score_job(job, mock_profile, mock_openai_client)
        
        word_count = len(result["fit_summary"].split())
        assert word_count < 100
    
    def test_handles_api_error_gracefully(self, mock_profile):
        """score_job handles API errors without crashing."""
        client = MagicMock()
        client.chat.completions.create.side_effect = Exception("API Error")
        
        job = {
            "title": "Engineer",
            "company": "Company",
            "description": "Job description",
        }
        
        # Should not raise
        result = score_job(job, mock_profile, client)
        
        assert "fit_score" in result
        assert result["fit_score"] == 0.5  # Default on error


class TestLiveScoring:
    """Tests that run against real OpenAI API."""
    
    @pytest.mark.slow
    def test_live_scoring_call(self):
        """Run one live scoring call with a realistic fake job dict."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            pytest.skip("OPENAI_API_KEY not set")
        
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        profile = load_scoring_profile()
        
        job = {
            "title": "AI Engineer",
            "company": "DeepMind",
            "location": "London, UK",
            "description": """
            We are looking for an AI Engineer to join our team working on 
            cutting-edge machine learning systems. You will work on developing
            and deploying ML models using Python and PyTorch. Experience with
            distributed systems and Kubernetes is a plus. The role involves
            building data pipelines for training and inference.
            """,
        }
        
        result = score_job(job, profile, client)
        
        print(f"\n\nLive scoring result:")
        print(f"  Score: {result['fit_score']:.2f}")
        print(f"  Summary: {result['fit_summary']}")
        print(f"  Matched: {result['keyword_matches'].get('matched', [])}")
        print(f"  Missing: {result['keyword_matches'].get('missing', [])}")
        
        assert 0.0 <= result["fit_score"] <= 1.0
        assert len(result["fit_summary"]) > 0
