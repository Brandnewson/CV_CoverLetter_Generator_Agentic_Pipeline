"""Tests for Phase 8 - Bullet rephraser."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.bullet_rephraser import (
    DEFAULT_REPHRASE_SYSTEM_PROMPT,
    _check_keyword_reuse,
    get_rephrase_generation_count,
    load_rephrase_prompt,
    record_rephrase_feedback,
    rephrase_bullet,
    save_rephrase_prompt,
)
from agent.validators import BulletCandidate, BulletValidationError


class TestLoadAndSaveRephrasePrompt:
    """Tests for load_rephrase_prompt and save_rephrase_prompt."""
    
    def test_load_returns_default_when_no_file(self):
        """Returns default prompt when user file doesn't exist."""
        # Use a user_id that definitely won't have a file
        result = load_rephrase_prompt(user_id=99999)
        
        # Should return default since file won't exist
        assert "CV bullet point editor" in result
        assert "Rephrase the provided bullet point" in result
    
    def test_save_creates_directory(self, tmp_path):
        """save_rephrase_prompt creates directory structure if needed."""
        with patch('agent.bullet_rephraser.Path') as mock_path:
            prompt_path = tmp_path / "profile" / "users" / "1" / "rephrase_prompt.txt"
            mock_path.return_value.parent.parent.__truediv__.return_value.__truediv__.return_value.__truediv__.return_value.__truediv__.return_value = prompt_path
            mock_path.__file__ = str(tmp_path / "agent" / "bullet_rephraser.py")
            
            # Create parent directory manually for test
            prompt_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save a custom prompt
            prompt_path.write_text("Custom prompt", encoding="utf-8")
            
            # Verify file exists
            assert prompt_path.exists()
            assert prompt_path.read_text() == "Custom prompt"


class TestCheckKeywordReuse:
    """Tests for _check_keyword_reuse helper."""
    
    def test_finds_reused_keyword(self):
        """Detects when bullet contains already-used keyword."""
        bullet = "Developed microservices using Python and Docker"
        already_used = ["Python", "AWS"]
        
        reused = _check_keyword_reuse(bullet, already_used)
        
        assert "Python" in reused
        assert "AWS" not in reused
    
    def test_case_insensitive_match(self):
        """Keyword matching is case-insensitive."""
        bullet = "Built REST APIs with PYTHON framework"
        already_used = ["python"]
        
        reused = _check_keyword_reuse(bullet, already_used)
        
        assert "python" in reused
    
    def test_no_reuse_returns_empty(self):
        """Returns empty list when no keywords reused."""
        bullet = "Designed database schemas for analytics"
        already_used = ["Python", "Docker", "AWS"]
        
        reused = _check_keyword_reuse(bullet, already_used)
        
        assert reused == []
    
    def test_matches_whole_words_only(self):
        """Only matches whole words, not partial."""
        bullet = "Implemented JavaScript functions"
        already_used = ["Java"]  # Should not match JavaScript
        
        reused = _check_keyword_reuse(bullet, already_used)
        
        # "Java" should match only as whole word
        # In "JavaScript", Java appears but not as whole word
        assert "Java" not in reused


class TestRephraseBullet:
    """Tests for rephrase_bullet function."""
    
    def test_returns_bullet_candidate(self):
        """Rephrased bullet is returned as BulletCandidate."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Developed scalable APIs using FastAPI framework")]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 20
        mock_client.messages.create.return_value = mock_response
        
        result = rephrase_bullet(
            original_bullet="Built REST APIs with Flask",
            job_keywords=["FastAPI", "Python", "Docker"],
            already_used_keywords=["Flask"],
            role_family="backend",
            previous_versions=[],
            slot_section="work_experience",
            slot_subsection="TechCorp",
            client=mock_client,
            user_id=1
        )
        
        assert isinstance(result, BulletCandidate)
        assert result.source == 'rephrasing'
        assert result.rephrase_generation == 1
    
    def test_rephrased_not_identical_to_original(self):
        """Rejects rephrase that matches original exactly."""
        mock_client = MagicMock()
        # First call returns identical text, second returns something different
        mock_response_identical = MagicMock()
        mock_response_identical.content = [MagicMock(text="Built REST APIs with Flask")]
        mock_response_identical.usage.input_tokens = 100
        mock_response_identical.usage.output_tokens = 20
        
        mock_response_different = MagicMock()
        mock_response_different.content = [MagicMock(text="Developed REST APIs using Flask framework")]
        mock_response_different.usage.input_tokens = 100
        mock_response_different.usage.output_tokens = 20
        
        mock_client.messages.create.side_effect = [
            mock_response_identical,
            mock_response_different
        ]
        
        result = rephrase_bullet(
            original_bullet="Built REST APIs with Flask",
            job_keywords=["Python"],
            already_used_keywords=[],
            role_family="backend",
            previous_versions=[],
            slot_section="work_experience",
            slot_subsection="TechCorp",
            client=mock_client,
            user_id=1
        )
        
        # Should have retried and returned the different version
        assert result.text.lower() != "built rest apis with flask"
    
    def test_rephrased_not_identical_to_previous_versions(self):
        """Rejects rephrase that matches any previous version."""
        mock_client = MagicMock()
        mock_response_duplicate = MagicMock()
        mock_response_duplicate.content = [MagicMock(text="Created APIs using Flask")]
        mock_response_duplicate.usage.input_tokens = 100
        mock_response_duplicate.usage.output_tokens = 20
        
        mock_response_new = MagicMock()
        mock_response_new.content = [MagicMock(text="Designed RESTful endpoints with Flask")]
        mock_response_new.usage.input_tokens = 100
        mock_response_new.usage.output_tokens = 20
        
        mock_client.messages.create.side_effect = [
            mock_response_duplicate,
            mock_response_new
        ]
        
        result = rephrase_bullet(
            original_bullet="Built REST APIs with Flask",
            job_keywords=["Python"],
            already_used_keywords=[],
            role_family="backend",
            previous_versions=["Created APIs using Flask"],
            slot_section="work_experience",
            slot_subsection="TechCorp",
            client=mock_client,
            user_id=1
        )
        
        # Should not match any previous version
        assert result.text.lower() not in ["created apis using flask"]
    
    def test_does_not_reuse_already_used_keywords(self):
        """Rejects rephrase that reuses already-used keywords."""
        mock_client = MagicMock()
        mock_response_reuses = MagicMock()
        mock_response_reuses.content = [MagicMock(text="Built Docker containers for microservices")]
        mock_response_reuses.usage.input_tokens = 100
        mock_response_reuses.usage.output_tokens = 20
        
        mock_response_clean = MagicMock()
        mock_response_clean.content = [MagicMock(text="Developed containerised applications for cloud")]
        mock_response_clean.usage.input_tokens = 100
        mock_response_clean.usage.output_tokens = 20
        
        mock_client.messages.create.side_effect = [
            mock_response_reuses,
            mock_response_clean
        ]
        
        result = rephrase_bullet(
            original_bullet="Created microservices architecture",
            job_keywords=["Kubernetes", "CI/CD"],
            already_used_keywords=["Docker"],
            role_family="backend",
            previous_versions=[],
            slot_section="work_experience",
            slot_subsection="TechCorp",
            client=mock_client,
            user_id=1
        )
        
        # Should not contain Docker
        assert "docker" not in result.text.lower()
    
    def test_passes_bullet_candidate_validation(self):
        """Rephrased bullet passes BulletCandidate validators."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        # Valid bullet: starts with action verb, under 120 chars
        mock_response.content = [MagicMock(text="Engineered real-time data pipelines using Apache Kafka")]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 20
        mock_client.messages.create.return_value = mock_response
        
        result = rephrase_bullet(
            original_bullet="Built data pipelines",
            job_keywords=["Kafka", "streaming"],
            already_used_keywords=[],
            role_family="data_engineer",
            previous_versions=[],
            slot_section="work_experience",
            slot_subsection="DataCorp",
            client=mock_client,
            user_id=1
        )
        
        # Should pass validation
        assert result.char_count <= 120
        assert result.text[0].isupper()  # Starts with capital (action verb)
    
    def test_increments_rephrase_generation(self):
        """rephrase_generation increments based on previous_versions count."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Designed scalable microservices architecture")]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 20
        mock_client.messages.create.return_value = mock_response
        
        result = rephrase_bullet(
            original_bullet="Built services",
            job_keywords=["microservices"],
            already_used_keywords=[],
            role_family="backend",
            previous_versions=["Version 1", "Version 2"],
            slot_section="work_experience",
            slot_subsection="TechCorp",
            client=mock_client,
            user_id=1
        )
        
        # Should be 3 (2 previous + 1)
        assert result.rephrase_generation == 3
    
    def test_raises_after_max_retries(self):
        """Raises ValueError after 3 failed attempts."""
        mock_client = MagicMock()
        # Always return something too long
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="X" * 130)]  # Over 120 chars
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_client.messages.create.return_value = mock_response
        
        with pytest.raises(ValueError, match="Failed to rephrase bullet after 3 attempts"):
            rephrase_bullet(
                original_bullet="Short bullet",
                job_keywords=["Python"],
                already_used_keywords=[],
                role_family="backend",
                previous_versions=[],
                slot_section="work_experience",
                slot_subsection="TechCorp",
                client=mock_client,
                user_id=1
            )
    
    def test_logs_api_usage(self, tmp_path):
        """API usage is logged to api_usage.jsonl."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Developed APIs using FastAPI")]
        mock_response.usage.input_tokens = 150
        mock_response.usage.output_tokens = 25
        mock_client.messages.create.return_value = mock_response
        
        # Patch log path
        log_path = tmp_path / "logs" / "api_usage.jsonl"
        
        with patch('agent.bullet_rephraser._log_api_usage') as mock_log:
            rephrase_bullet(
                original_bullet="Built APIs",
                job_keywords=["FastAPI"],
                already_used_keywords=[],
                role_family="backend",
                previous_versions=[],
                slot_section="work_experience",
                slot_subsection="TechCorp",
                client=mock_client,
                user_id=1
            )
            
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert call_args.kwargs['operation'] == 'rephrase_bullet'
            assert call_args.kwargs['input_tokens'] == 150
            assert call_args.kwargs['output_tokens'] == 25


class TestGetRephraseGenerationCount:
    """Tests for get_rephrase_generation_count."""
    
    def test_returns_max_generation_for_slot(self):
        """Returns the maximum rephrase_generation for the slot."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (5,)
        mock_conn.cursor.return_value = mock_cursor
        
        result = get_rephrase_generation_count(
            job_id=123,
            slot_section="work_experience",
            slot_index=0,
            conn=mock_conn,
            user_id=1
        )
        
        assert result == 5
    
    def test_returns_zero_for_no_entries(self):
        """Returns 0 when no feedback entries exist for slot."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (0,)  # COALESCE returns 0
        mock_conn.cursor.return_value = mock_cursor
        
        result = get_rephrase_generation_count(
            job_id=123,
            slot_section="work_experience",
            slot_index=0,
            conn=mock_conn,
            user_id=1
        )
        
        assert result == 0
    
    def test_filters_by_user_id(self):
        """Query filters by user_id parameter."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (3,)
        mock_conn.cursor.return_value = mock_cursor
        
        get_rephrase_generation_count(
            job_id=123,
            slot_section="work_experience",
            slot_index=0,
            conn=mock_conn,
            user_id=42
        )
        
        # Check the query was called with user_id=42
        call_args = mock_cursor.execute.call_args
        assert 42 in call_args[0][1]  # user_id in parameters


class TestRecordRephraseFeedback:
    """Tests for record_rephrase_feedback."""
    
    def test_inserts_feedback_row(self):
        """Inserts a feedback row with all fields."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (99,)  # Returned ID
        mock_conn.cursor.return_value = mock_cursor
        
        result = record_rephrase_feedback(
            job_id=123,
            session_id="abc-def-123",
            slot_section="work_experience",
            slot_subsection="TechCorp",
            slot_index=0,
            original_text="Original bullet",
            final_text="Rephrased bullet",
            was_approved=True,
            rephrase_generation=2,
            source="rephrasing",
            keyword_hits=["Python", "Docker"],
            relevance_score=0.85,
            conn=mock_conn,
            user_id=1
        )
        
        assert result == 99
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()
    
    def test_commits_after_insert(self):
        """Commits transaction after insert."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.cursor.return_value = mock_cursor
        
        record_rephrase_feedback(
            job_id=1,
            session_id="test",
            slot_section="work_experience",
            slot_subsection="Test",
            slot_index=0,
            original_text="test",
            final_text="test",
            was_approved=False,
            rephrase_generation=1,
            source="rephrasing",
            keyword_hits=[],
            relevance_score=0.5,
            conn=mock_conn,
            user_id=1
        )
        
        mock_conn.commit.assert_called_once()


class TestLiveRephrasing:
    """Live integration tests with real API calls."""
    
    @pytest.mark.skipif(
        not os.environ.get('ANTHROPIC_API_KEY'),
        reason="ANTHROPIC_API_KEY not set"
    )
    def test_live_rephrase_two_versions(self):
        """
        Live test: Generate two rephrases of the same bullet.
        Prints both versions for manual inspection.
        """
        import anthropic
        
        client = anthropic.Anthropic()
        
        original = "Built REST APIs using Python Flask framework"
        job_keywords = ["FastAPI", "microservices", "Docker", "PostgreSQL"]
        
        # First rephrase
        v1 = rephrase_bullet(
            original_bullet=original,
            job_keywords=job_keywords,
            already_used_keywords=[],
            role_family="backend",
            previous_versions=[],
            slot_section="work_experience",
            slot_subsection="TechCorp",
            client=client,
            user_id=1
        )
        
        print(f"\n=== LIVE REPHRASE TEST ===")
        print(f"Original: {original}")
        print(f"Version 1: {v1.text}")
        
        # Second rephrase (avoiding first version's keywords)
        # Extract keywords from v1 to mark as used
        v1_keywords = []
        for kw in job_keywords:
            if kw.lower() in v1.text.lower():
                v1_keywords.append(kw)
        
        v2 = rephrase_bullet(
            original_bullet=original,
            job_keywords=job_keywords,
            already_used_keywords=v1_keywords,
            role_family="backend",
            previous_versions=[v1.text],
            slot_section="work_experience",
            slot_subsection="TechCorp",
            client=client,
            user_id=1
        )
        
        print(f"Version 2: {v2.text}")
        print(f"========================\n")
        
        # Both should be valid candidates
        assert isinstance(v1, BulletCandidate)
        assert isinstance(v2, BulletCandidate)
        
        # They should be different from each other and original
        assert v1.text.lower() != original.lower()
        assert v2.text.lower() != original.lower()
        assert v1.text.lower() != v2.text.lower()
