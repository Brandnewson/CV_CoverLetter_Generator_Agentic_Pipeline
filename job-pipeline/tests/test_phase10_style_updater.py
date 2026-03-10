"""Tests for Phase 10 - Style updater."""

import json
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.style_updater import (
    _format_approved_examples,
    collect_all_historical_bullets,
    collect_approved_bullets,
    distill_style_rules,
    parse_claude_md_section,
    replace_claude_md_section,
    update_claude_md,
    update_rephrase_prompt,
)


class TestCollectApprovedBullets:
    """Tests for collect_approved_bullets function."""
    
    def test_returns_approved_bullets(self):
        """Returns bullets where was_approved=TRUE."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("Built REST APIs using Python", "work_experience", "TechCorp", "backend", 1),
            ("Deployed microservices on K8s", "work_experience", "TechCorp", "backend", 0),
        ]
        mock_conn.cursor.return_value = mock_cursor
        
        result = collect_approved_bullets(job_id=123, conn=mock_conn, user_id=1)
        
        assert len(result) == 2
        assert result[0]["text"] == "Built REST APIs using Python"
        assert result[0]["role_family"] == "backend"
        assert result[1]["rephrase_generation"] == 0
    
    def test_returns_empty_for_no_approvals(self):
        """Returns empty list when no approved bullets."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor
        
        result = collect_approved_bullets(job_id=123, conn=mock_conn, user_id=1)
        
        assert result == []
    
    def test_filters_by_job_and_user(self):
        """Query filters by job_id and user_id."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor
        
        collect_approved_bullets(job_id=456, conn=mock_conn, user_id=42)
        
        # Check the query was called with correct parameters
        call_args = mock_cursor.execute.call_args
        assert 456 in call_args[0][1]  # job_id
        assert 42 in call_args[0][1]   # user_id


class TestParseCLAUDEMdSection:
    """Tests for parse_claude_md_section function."""
    
    def test_extracts_section_content(self, tmp_path):
        """Extracts content between ## header and next ## header."""
        md_file = tmp_path / "CLAUDE.md"
        md_file.write_text("""# Main Header

## Section One
Content for section one
More content here

## Section Two
Different content
""")
        
        result = parse_claude_md_section(md_file, "Section One")
        
        assert "Content for section one" in result
        assert "More content here" in result
        assert "Different content" not in result
    
    def test_extracts_last_section(self, tmp_path):
        """Extracts content from last section (no following header)."""
        md_file = tmp_path / "CLAUDE.md"
        md_file.write_text("""# Main Header

## First Section
Some stuff

## Last Section
Final content here
""")
        
        result = parse_claude_md_section(md_file, "Last Section")
        
        assert "Final content here" in result
    
    def test_returns_empty_for_missing_section(self, tmp_path):
        """Returns empty string if section not found."""
        md_file = tmp_path / "CLAUDE.md"
        md_file.write_text("## Existing Section\nContent\n")
        
        result = parse_claude_md_section(md_file, "Nonexistent Section")
        
        assert result == ""
    
    def test_returns_empty_for_missing_file(self, tmp_path):
        """Returns empty string if file doesn't exist."""
        result = parse_claude_md_section(tmp_path / "missing.md", "Any Section")
        
        assert result == ""


class TestReplaceCLAUDEMdSection:
    """Tests for replace_claude_md_section function."""
    
    def test_replaces_section_content(self, tmp_path):
        """Replaces content in existing section."""
        md_file = tmp_path / "CLAUDE.md"
        md_file.write_text("""## Section One
Old content

## Section Two
Keep this
""")
        
        replace_claude_md_section(md_file, "Section One", "New content here")
        
        content = md_file.read_text()
        assert "New content here" in content
        assert "Old content" not in content
        assert "Keep this" in content
    
    def test_preserves_other_sections(self, tmp_path):
        """Other sections are not modified."""
        md_file = tmp_path / "CLAUDE.md"
        md_file.write_text("""## First
First content

## Second
Second content

## Third
Third content
""")
        
        replace_claude_md_section(md_file, "Second", "REPLACED")
        
        content = md_file.read_text()
        assert "First content" in content
        assert "REPLACED" in content
        assert "Second content" not in content
        assert "Third content" in content
    
    def test_appends_new_section(self, tmp_path):
        """Appends section if it doesn't exist."""
        md_file = tmp_path / "CLAUDE.md"
        md_file.write_text("## Existing\nContent\n")
        
        replace_claude_md_section(md_file, "New Section", "New content")
        
        content = md_file.read_text()
        assert "## New Section" in content
        assert "New content" in content
        assert "## Existing" in content
    
    def test_creates_file_if_missing(self, tmp_path):
        """Creates file with section if it doesn't exist."""
        md_file = tmp_path / "subdir" / "CLAUDE.md"
        
        replace_claude_md_section(md_file, "Section", "Content")
        
        assert md_file.exists()
        content = md_file.read_text()
        assert "## Section" in content
        assert "Content" in content


class TestFormatApprovedExamples:
    """Tests for _format_approved_examples helper."""
    
    def test_formats_bullets_as_list(self):
        """Formats bullets as markdown list."""
        bullets = [
            {"text": "First bullet"},
            {"text": "Second bullet"},
        ]
        
        result = _format_approved_examples(bullets)
        
        assert "- First bullet" in result
        assert "- Second bullet" in result
    
    def test_limits_to_max_examples(self):
        """Limits output to max_examples."""
        bullets = [{"text": f"Bullet {i}"} for i in range(10)]
        
        result = _format_approved_examples(bullets, max_examples=3)
        
        assert result.count("- Bullet") == 3
    
    def test_deduplicates_bullets(self):
        """Removes duplicate bullet texts."""
        bullets = [
            {"text": "Same text"},
            {"text": "Same text"},
            {"text": "Different text"},
        ]
        
        result = _format_approved_examples(bullets)
        
        assert result.count("- Same text") == 1
        assert "- Different text" in result
    
    def test_returns_comment_only_for_empty(self):
        """Returns just comment for empty input."""
        result = _format_approved_examples([])
        
        assert "AUTO-UPDATED" in result
        # No bullet list items (lines starting with "- ")
        lines = result.split('\n')
        assert not any(line.strip().startswith('- ') for line in lines)


class TestDistillStyleRules:
    """Tests for distill_style_rules function."""
    
    def test_calls_haiku_with_bullets(self):
        """Calls Haiku with formatted bullets."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="- Rule 1\n- Rule 2\n- Rule 3\n- Rule 4\n- Rule 5")]
        mock_response.usage.input_tokens = 200
        mock_response.usage.output_tokens = 100
        mock_client.messages.create.return_value = mock_response
        
        bullets = [
            {"text": "Built APIs using Python"},
            {"text": "Deployed services on AWS"},
        ]
        
        result = distill_style_rules(bullets, mock_client, user_id=1)
        
        assert "Rule 1" in result
        mock_client.messages.create.assert_called_once()
    
    def test_returns_placeholder_for_empty_bullets(self):
        """Returns placeholder when no bullets provided."""
        mock_client = MagicMock()
        
        result = distill_style_rules([], mock_client, user_id=1)
        
        assert "No approved bullets yet" in result
        mock_client.messages.create.assert_not_called()
    
    def test_limits_bullets_for_context(self):
        """Limits bullets to avoid context overflow."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="- Rules here")]
        mock_response.usage.input_tokens = 200
        mock_response.usage.output_tokens = 50
        mock_client.messages.create.return_value = mock_response
        
        # 100 bullets
        bullets = [{"text": f"Bullet {i}"} for i in range(100)]
        
        distill_style_rules(bullets, mock_client, user_id=1)
        
        # Should have called with limited bullets (check prompt contains limited count)
        call_args = mock_client.messages.create.call_args
        prompt = call_args.kwargs["messages"][0]["content"]
        # Should have max ~50 bullets
        assert prompt.count("- Bullet") <= 50


class TestUpdateCLAUDEMd:
    """Tests for update_claude_md function."""
    
    def test_updates_approved_examples_section(self, tmp_path):
        """Updates the approved examples section for role_family."""
        md_file = tmp_path / "CLAUDE.md"
        md_file.write_text("""## Approved Examples (motorsport)
<!-- AUTO-UPDATED after each session. Do not edit manually. -->

## Distilled Style Rules
<!-- AUTO-UPDATED after each session. Do not edit manually. -->
""")
        
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="- Style rule 1\n- Style rule 2")]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_client.messages.create.return_value = mock_response
        
        approved = [{"text": "New bullet", "role_family": "motorsport"}]
        historical = approved
        
        with patch('agent.style_updater.update_rephrase_prompt'):
            update_claude_md(md_file, approved, historical, "motorsport", mock_client, user_id=1)
        
        content = md_file.read_text()
        assert "- New bullet" in content
    
    def test_does_not_duplicate_examples(self, tmp_path):
        """Running twice does not duplicate examples."""
        md_file = tmp_path / "CLAUDE.md"
        md_file.write_text("""## Approved Examples (motorsport)
<!-- AUTO-UPDATED after each session. Do not edit manually. -->
- Existing bullet

## Distilled Style Rules
<!-- AUTO-UPDATED after each session. Do not edit manually. -->
""")
        
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="- Rules")]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_client.messages.create.return_value = mock_response
        
        approved = [{"text": "Existing bullet", "role_family": "motorsport"}]
        
        with patch('agent.style_updater.update_rephrase_prompt'):
            update_claude_md(md_file, approved, approved, "motorsport", mock_client)
            update_claude_md(md_file, approved, approved, "motorsport", mock_client)
        
        content = md_file.read_text()
        assert content.count("- Existing bullet") == 1
    
    def test_updates_distilled_style_rules(self, tmp_path):
        """Updates the Distilled Style Rules section."""
        md_file = tmp_path / "CLAUDE.md"
        md_file.write_text("""## Distilled Style Rules
<!-- AUTO-UPDATED after each session. Do not edit manually. -->
Old rules here
""")
        
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="- New rule 1\n- New rule 2")]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_client.messages.create.return_value = mock_response
        
        with patch('agent.style_updater.update_rephrase_prompt'):
            update_claude_md(
                md_file, 
                [{"text": "Bullet", "role_family": "motorsport"}],
                [{"text": "Bullet"}],
                "motorsport",
                mock_client
            )
        
        content = md_file.read_text()
        assert "New rule 1" in content
        assert "Old rules here" not in content


class TestUpdateRephrasePrompt:
    """Tests for update_rephrase_prompt function."""
    
    def test_appends_style_rules_to_prompt(self, tmp_path):
        """Appends distilled rules to rephrase prompt."""
        style_rules = """<!-- AUTO-UPDATED after each session. Do not edit manually. -->
- Prefers past-tense verbs
- Avoids adjectives"""
        
        with patch('agent.bullet_rephraser.save_rephrase_prompt') as mock_save:
            update_rephrase_prompt(style_rules, user_id=1)
            
            mock_save.assert_called_once()
            saved_prompt = mock_save.call_args[0][0]
            assert "Prefers past-tense verbs" in saved_prompt
            assert "Distilled style preferences" in saved_prompt


class TestCollectAllHistoricalBullets:
    """Tests for collect_all_historical_bullets function."""
    
    def test_returns_all_user_bullets(self):
        """Returns all approved bullets for user."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("Bullet 1", "work_experience", "Company", "motorsport", 0),
            ("Bullet 2", "technical_projects", "Project", "ai-startup", 1),
        ]
        mock_conn.cursor.return_value = mock_cursor
        
        result = collect_all_historical_bullets(mock_conn, user_id=1)
        
        assert len(result) == 2
    
    def test_filters_by_role_family(self):
        """Filters by role_family when provided."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("Motorsport bullet", "work_experience", "Team", "motorsport", 0),
        ]
        mock_conn.cursor.return_value = mock_cursor
        
        collect_all_historical_bullets(mock_conn, user_id=1, role_family="motorsport")
        
        # Check role_family was in query params
        call_args = mock_cursor.execute.call_args
        assert "motorsport" in call_args[0][1]


class TestLiveStyleUpdate:
    """Live integration tests."""
    
    @pytest.mark.skipif(
        not os.environ.get('ANTHROPIC_API_KEY'),
        reason="ANTHROPIC_API_KEY not set"
    )
    def test_live_style_distillation(self, tmp_path):
        """Live test: distill style rules from sample bullets."""
        import anthropic
        
        client = anthropic.Anthropic()
        
        bullets = [
            {"text": "Developed real-time telemetry processing pipeline using Python and Apache Kafka"},
            {"text": "Architected microservices infrastructure reducing deployment time by 40%"},
            {"text": "Built REST APIs with FastAPI serving 10,000 requests per second"},
            {"text": "Implemented CI/CD pipelines automating testing and deployment workflows"},
            {"text": "Designed PostgreSQL database schema for high-throughput data ingestion"},
        ]
        
        result = distill_style_rules(bullets, client, user_id=1)
        
        print(f"\n=== LIVE STYLE DISTILLATION ===")
        print(result)
        print(f"===============================\n")
        
        # Should contain style rules
        assert "- " in result
        assert len(result) > 100  # Has substantive content
