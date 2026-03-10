"""Phase 7 tests: Story drafter."""

import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.story_drafter import (
    draft_bullet_from_story,
    approve_bullet_for_bank,
    load_stories,
    find_relevant_story,
    extract_numbers_from_text,
    get_story_excerpt,
)
from agent.validators import BulletSlot, BulletCandidate, BulletValidationError


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    dirpath = tempfile.mkdtemp()
    yield Path(dirpath)
    shutil.rmtree(dirpath)


@pytest.fixture
def sample_stories_md(temp_dir):
    """Create a sample stories.md file."""
    content = """# Experience Stories

## Jaguar TCS Racing

During the season I built a tool that let strategists model energy regeneration decay
across different brake bias settings. Used in real race weekends for in-lap decisions.
Built in Python with a Flask frontend. Main challenge was making it fast enough to run
live during a session with minimal latency. The tool reduced analysis time by 50% and
was used in 12 races.

## Republic of Singapore Navy

Trained on Singapore Navy's largest marine vessel. Led firefighting simulations.
Contributed to 50 mission debriefs. Handled damage control under pressure.

## Formula Student Lap Time Simulator

Designed a modular lap time simulation using point-mass and bicycle models.
Created tyre model with Pacejka magic formula. Achieved 95% correlation with real data.
"""
    path = temp_dir / "stories.md"
    path.write_text(content, encoding='utf-8')
    return path


@pytest.fixture
def sample_bullet_bank_md(temp_dir):
    """Create a sample master_bullets.md file."""
    content = """# Master Bullet Bank

## Work Experience

### Jaguar TCS Racing

- Designed REST API for streaming live race telemetry from WinTax using VBS scripts.
    [tags: api, telemetry, python, vbs, motorsport]
    [role_family: motorsport, general-swe]

### Republic of Singapore Navy

- Led remote war-time firefighting simulation aboard ship engine operations room.
    [tags: leadership, simulation, military]
    [role_family: general-swe]

## Technical Projects

### Formula Student Lap Time Simulator

- Designed modular steady-state lap time sim using point-mass and bicycle models.
    [tags: simulation, vehicle-dynamics, python, motorsport]
    [role_family: motorsport]
"""
    path = temp_dir / "master_bullets.md"
    path.write_text(content, encoding='utf-8')
    return path


@pytest.fixture
def sample_keywords():
    """Sample keywords from JD parser."""
    return {
        'required_keywords': ['python', 'api', 'data'],
        'nice_to_have_keywords': ['flask', 'react'],
        'technical_skills': ['python'],
        'soft_skills': [],
        'domain_keywords': ['motorsport'],
        'seniority_signals': []
    }


@pytest.fixture
def sample_gap_slot():
    """Sample gap slot needing a drafted bullet."""
    return BulletSlot(
        slot_index=0,
        section='work_experience',
        subsection='Jaguar TCS Racing',
        current_candidate=None,
        is_approved=False
    )


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client."""
    client = MagicMock()
    response = MagicMock()
    response.content = [MagicMock(text="Built Python API for real-time energy analysis tool with Flask frontend.")]
    response.usage.input_tokens = 100
    response.usage.output_tokens = 20
    client.messages.create.return_value = response
    return client


class TestLoadStories:
    """Tests for load_stories function."""
    
    def test_loads_all_sections(self, sample_stories_md):
        """Loads all story sections."""
        stories = load_stories(sample_stories_md)
        
        assert 'Jaguar TCS Racing' in stories
        assert 'Republic of Singapore Navy' in stories
        assert 'Formula Student Lap Time Simulator' in stories
    
    def test_returns_empty_dict_for_missing_file(self, temp_dir):
        """Returns empty dict when file doesn't exist."""
        stories = load_stories(temp_dir / "nonexistent.md")
        assert stories == {}
    
    def test_story_content_correct(self, sample_stories_md):
        """Story content is correctly parsed."""
        stories = load_stories(sample_stories_md)
        
        jaguar_story = stories['Jaguar TCS Racing']
        assert 'energy regeneration' in jaguar_story
        assert 'Flask frontend' in jaguar_story


class TestFindRelevantStory:
    """Tests for find_relevant_story function."""
    
    def test_exact_match(self, sample_stories_md):
        """Finds story with exact match."""
        stories = load_stories(sample_stories_md)
        story = find_relevant_story('Jaguar TCS Racing', stories)
        
        assert story is not None
        assert 'energy regeneration' in story
    
    def test_case_insensitive_match(self, sample_stories_md):
        """Finds story with case-insensitive match."""
        stories = load_stories(sample_stories_md)
        story = find_relevant_story('jaguar tcs racing', stories)
        
        assert story is not None
    
    def test_partial_match(self, sample_stories_md):
        """Finds story with partial match."""
        stories = load_stories(sample_stories_md)
        story = find_relevant_story('Jaguar', stories)
        
        assert story is not None
    
    def test_returns_none_for_no_match(self, sample_stories_md):
        """Returns None when no match found."""
        stories = load_stories(sample_stories_md)
        story = find_relevant_story('Unknown Company', stories)
        
        assert story is None


class TestExtractNumbersFromText:
    """Tests for extract_numbers_from_text function."""
    
    def test_extracts_percentages(self):
        """Extracts percentage values."""
        numbers = extract_numbers_from_text("Improved performance by 50%")
        assert '50%' in numbers
    
    def test_extracts_plain_numbers(self):
        """Extracts plain numbers."""
        numbers = extract_numbers_from_text("Used in 12 races")
        assert '12' in numbers
    
    def test_extracts_money(self):
        """Extracts money amounts."""
        numbers = extract_numbers_from_text("Saved £10,000 annually")
        assert '£10,000' in numbers


class TestDraftBulletFromStory:
    """Tests for draft_bullet_from_story function."""
    
    def test_drafted_bullet_passes_validation(
        self, sample_stories_md, sample_keywords, sample_gap_slot, mock_anthropic_client
    ):
        """Drafted bullet passes BulletCandidate validation."""
        candidate = draft_bullet_from_story(
            gap_slot=sample_gap_slot,
            stories_path=sample_stories_md,
            keywords=sample_keywords,
            role_family='motorsport',
            client=mock_anthropic_client,
            user_id=1
        )
        
        assert isinstance(candidate, BulletCandidate)
        assert candidate.source == 'story_draft'
        assert candidate.section == 'work_experience'
        assert candidate.subsection == 'Jaguar TCS Racing'
        assert len(candidate.text) <= 120  # Hard limit
    
    def test_draft_does_not_invent_numbers(
        self, sample_stories_md, sample_keywords, sample_gap_slot
    ):
        """Draft does not invent numbers not in the story text."""
        client = MagicMock()
        # First response has invented number, second is valid
        responses = [
            MagicMock(
                content=[MagicMock(text="Reduced latency by 99% using custom Python tool.")],
                usage=MagicMock(input_tokens=100, output_tokens=20)
            ),
            MagicMock(
                content=[MagicMock(text="Built Python tool for real-time energy analysis with Flask.")],
                usage=MagicMock(input_tokens=100, output_tokens=20)
            )
        ]
        client.messages.create.side_effect = responses
        
        candidate = draft_bullet_from_story(
            gap_slot=sample_gap_slot,
            stories_path=sample_stories_md,
            keywords=sample_keywords,
            role_family='motorsport',
            client=client,
            user_id=1
        )
        
        # Should have retried and used the second response
        assert '99%' not in candidate.text
    
    def test_raises_on_missing_story(
        self, temp_dir, sample_keywords, sample_gap_slot, mock_anthropic_client
    ):
        """Raises ValueError when no story found for subsection."""
        # Create empty stories file
        empty_stories = temp_dir / "stories.md"
        empty_stories.write_text("# Stories\n\n## Other Company\nSome text.")
        
        with pytest.raises(ValueError, match="No story found"):
            draft_bullet_from_story(
                gap_slot=sample_gap_slot,
                stories_path=empty_stories,
                keywords=sample_keywords,
                role_family='motorsport',
                client=mock_anthropic_client,
                user_id=1
            )
    
    def test_retries_on_validation_failure(
        self, sample_stories_md, sample_keywords, sample_gap_slot
    ):
        """Retries up to 3 times on validation failure."""
        client = MagicMock()
        # All responses are too long (>120 chars)
        long_text = "A" * 130
        response = MagicMock(
            content=[MagicMock(text=long_text)],
            usage=MagicMock(input_tokens=100, output_tokens=20)
        )
        client.messages.create.return_value = response
        
        with pytest.raises(ValueError, match="Failed to draft bullet after 3 attempts"):
            draft_bullet_from_story(
                gap_slot=sample_gap_slot,
                stories_path=sample_stories_md,
                keywords=sample_keywords,
                role_family='motorsport',
                client=client,
                user_id=1
            )
        
        # Should have been called 3 times
        assert client.messages.create.call_count == 3


class TestApproveBulletForBank:
    """Tests for approve_bullet_for_bank function."""
    
    def test_appends_to_correct_section(self, sample_bullet_bank_md):
        """Appends bullet to correct section."""
        result = approve_bullet_for_bank(
            bullet_text="Built Python tool for energy analysis during race weekends.",
            section="work_experience",
            subsection="Jaguar TCS Racing",
            tags=["python", "analysis", "motorsport"],
            role_families=["motorsport"],
            bank_path=sample_bullet_bank_md
        )
        
        assert result is True
        
        # Verify it was added
        content = sample_bullet_bank_md.read_text()
        assert "Built Python tool for energy analysis" in content
        assert "[tags: python, analysis, motorsport]" in content
    
    def test_rejects_duplicates(self, sample_bullet_bank_md):
        """Rejects duplicate bullets."""
        # This bullet already exists in the sample
        result = approve_bullet_for_bank(
            bullet_text="Designed REST API for streaming live race telemetry from WinTax using VBS scripts.",
            section="work_experience",
            subsection="Jaguar TCS Racing",
            tags=["api"],
            role_families=["motorsport"],
            bank_path=sample_bullet_bank_md
        )
        
        assert result is False
    
    def test_rejects_case_insensitive_duplicates(self, sample_bullet_bank_md):
        """Rejects duplicates regardless of case."""
        result = approve_bullet_for_bank(
            bullet_text="DESIGNED REST API FOR STREAMING LIVE RACE TELEMETRY FROM WINTAX USING VBS SCRIPTS.",
            section="work_experience",
            subsection="Jaguar TCS Racing",
            tags=["api"],
            role_families=["motorsport"],
            bank_path=sample_bullet_bank_md
        )
        
        assert result is False
    
    def test_raises_on_missing_bank(self, temp_dir):
        """Raises FileNotFoundError when bank file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            approve_bullet_for_bank(
                bullet_text="Test bullet",
                section="work_experience",
                subsection="Test Company",
                tags=[],
                role_families=[],
                bank_path=temp_dir / "nonexistent.md"
            )
    
    def test_adds_to_technical_projects(self, sample_bullet_bank_md):
        """Can add to technical projects section."""
        result = approve_bullet_for_bank(
            bullet_text="Implemented vehicle dynamics model for lap time prediction.",
            section="technical_projects",
            subsection="Formula Student Lap Time Simulator",
            tags=["simulation", "python"],
            role_families=["motorsport"],
            bank_path=sample_bullet_bank_md
        )
        
        assert result is True
        
        content = sample_bullet_bank_md.read_text()
        assert "Implemented vehicle dynamics model" in content


class TestGetStoryExcerpt:
    """Tests for get_story_excerpt function."""
    
    def test_returns_full_story_if_short(self, sample_stories_md):
        """Returns full story if under max_chars."""
        excerpt = get_story_excerpt('Republic of Singapore Navy', sample_stories_md)
        
        assert excerpt is not None
        assert '...' not in excerpt
    
    def test_truncates_long_story(self, sample_stories_md):
        """Truncates long stories."""
        excerpt = get_story_excerpt('Jaguar TCS Racing', sample_stories_md, max_chars=100)
        
        assert excerpt is not None
        assert len(excerpt) <= 104  # 100 + "..."
        assert excerpt.endswith('...')
    
    def test_returns_none_for_missing_story(self, sample_stories_md):
        """Returns None when story not found."""
        excerpt = get_story_excerpt('Unknown Company', sample_stories_md)
        
        assert excerpt is None


class TestIntegrationDraftAndApprove:
    """Integration tests for drafting and approving bullets."""
    
    def test_draft_and_approve_workflow(
        self, sample_stories_md, sample_bullet_bank_md, sample_keywords, sample_gap_slot, mock_anthropic_client
    ):
        """Full workflow: draft a bullet and approve it to the bank."""
        # Draft a bullet
        candidate = draft_bullet_from_story(
            gap_slot=sample_gap_slot,
            stories_path=sample_stories_md,
            keywords=sample_keywords,
            role_family='motorsport',
            client=mock_anthropic_client,
            user_id=1
        )
        
        # Approve it to the bank
        result = approve_bullet_for_bank(
            bullet_text=candidate.text,
            section=candidate.section,
            subsection=candidate.subsection,
            tags=['python', 'api', 'motorsport'],
            role_families=candidate.role_families,
            bank_path=sample_bullet_bank_md
        )
        
        assert result is True
        
        # Verify it's in the bank
        content = sample_bullet_bank_md.read_text()
        assert candidate.text in content
