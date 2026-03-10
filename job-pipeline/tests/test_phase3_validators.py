"""Phase 3 tests - Pydantic validators for CV generation."""

import pytest
from pydantic import ValidationError
from agent.validators import (
    BulletCandidate,
    BulletSlot,
    CVSelectionPlan,
    UserSelections,
    BulletValidationError,
    validate_bullet_text,
    BANNED_PHRASES,
    ACTION_VERBS,
    HARD_CHAR_LIMIT,
    SOFT_CHAR_LIMIT,
)


class TestBulletCandidate:
    """Test BulletCandidate model and validators."""
    
    def test_valid_bullet_creates_successfully(self):
        """Valid bullet should create without errors."""
        bullet = BulletCandidate(
            text="Developed REST API serving 1M requests/day using Python and FastAPI",
            source="master_bullets",
            section="work_experience",
            subsection="Acme Corp",
            tags=["python", "api"],
            role_families=["general-swe"],
            relevance_score=0.8,
            keyword_hits=["python", "api"]
        )
        assert bullet.text == "Developed REST API serving 1M requests/day using Python and FastAPI"
        assert bullet.char_count == 67
        assert bullet.over_soft_limit is False
        assert bullet.warnings == []
    
    def test_char_count_computed_on_init(self):
        """char_count should be automatically computed."""
        bullet = BulletCandidate(
            text="Built microservices architecture",
            source="master_bullets",
            section="work_experience",
            subsection="Test Corp"
        )
        assert bullet.char_count == 32
    
    def test_over_soft_limit_computed(self):
        """over_soft_limit should be True when char_count > 110."""
        # 111 characters
        text = "A" * 111
        bullet = BulletCandidate(
            text=text,
            source="master_bullets",
            section="work_experience",
            subsection="Test Corp"
        )
        assert bullet.char_count == 111
        assert bullet.over_soft_limit is True
        assert any("over" in w.lower() for w in bullet.warnings)
    
    def test_rejects_over_120_chars(self):
        """Bullet over 120 chars should raise ValidationError."""
        text = "A" * 121
        with pytest.raises(ValidationError) as exc_info:
            BulletCandidate(
                text=text,
                source="master_bullets",
                section="work_experience",
                subsection="Test Corp"
            )
        assert "120" in str(exc_info.value)
    
    def test_rejects_starting_with_i(self):
        """Bullet starting with 'I ' should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            BulletCandidate(
                text="I developed a new feature for the team",
                source="master_bullets",
                section="work_experience",
                subsection="Test Corp"
            )
        assert "start with 'I'" in str(exc_info.value)
    
    def test_allows_words_starting_with_i(self):
        """Words starting with I (but not 'I ') should be allowed."""
        bullet = BulletCandidate(
            text="Implemented new authentication system using OAuth2",
            source="master_bullets",
            section="work_experience",
            subsection="Test Corp"
        )
        assert bullet.text.startswith("Implemented")
    
    def test_rejects_banned_phrases(self):
        """Bullet with banned phrase should raise ValidationError."""
        for phrase in BANNED_PHRASES[:3]:  # Test a few
            with pytest.raises(ValidationError) as exc_info:
                BulletCandidate(
                    text=f"Worked in a {phrase} environment building software",
                    source="master_bullets",
                    section="work_experience",
                    subsection="Test Corp"
                )
            assert "banned phrase" in str(exc_info.value).lower()
    
    def test_warns_on_no_action_verb(self):
        """Bullet not starting with action verb should add warning."""
        bullet = BulletCandidate(
            text="The system was redesigned for better performance",
            source="master_bullets",
            section="work_experience",
            subsection="Test Corp"
        )
        assert any("action verb" in w.lower() for w in bullet.warnings)
    
    def test_no_warning_on_action_verb(self):
        """Bullet starting with action verb should not warn."""
        bullet = BulletCandidate(
            text="Designed and implemented new caching layer",
            source="master_bullets",
            section="work_experience",
            subsection="Test Corp"
        )
        assert not any("action verb" in w.lower() for w in bullet.warnings)
    
    def test_rejects_invalid_source(self):
        """Invalid source should raise error."""
        with pytest.raises(ValidationError):
            BulletCandidate(
                text="Built new feature",
                source="invalid_source",
                section="work_experience",
                subsection="Test Corp"
            )
    
    def test_rejects_invalid_section(self):
        """Invalid section should raise error."""
        with pytest.raises(ValidationError):
            BulletCandidate(
                text="Built new feature",
                source="master_bullets",
                section="invalid_section",
                subsection="Test Corp"
            )
    
    def test_rejects_invalid_relevance_score(self):
        """Relevance score outside 0-1 should raise error."""
        with pytest.raises(ValidationError):
            BulletCandidate(
                text="Built new feature",
                source="master_bullets",
                section="work_experience",
                subsection="Test Corp",
                relevance_score=1.5
            )
    
    def test_rejects_empty_text(self):
        """Empty text should raise error."""
        with pytest.raises(ValidationError):
            BulletCandidate(
                text="",
                source="master_bullets",
                section="work_experience",
                subsection="Test Corp"
            )
    
    def test_strips_whitespace(self):
        """Text should be stripped of leading/trailing whitespace."""
        bullet = BulletCandidate(
            text="  Built new feature  ",
            source="master_bullets",
            section="work_experience",
            subsection="Test Corp"
        )
        assert bullet.text == "Built new feature"
        assert bullet.char_count == 17


class TestBulletSlot:
    """Test BulletSlot model."""
    
    def test_creates_empty_slot(self):
        """Should create slot without candidate."""
        slot = BulletSlot(
            slot_index=0,
            section="work_experience",
            subsection="Acme Corp"
        )
        assert slot.current_candidate is None
        assert slot.rephrase_history == []
        assert slot.is_approved is False
    
    def test_creates_slot_with_candidate(self):
        """Should create slot with candidate."""
        bullet = BulletCandidate(
            text="Built new feature",
            source="master_bullets",
            section="work_experience",
            subsection="Acme Corp"
        )
        slot = BulletSlot(
            slot_index=0,
            section="work_experience",
            subsection="Acme Corp",
            current_candidate=bullet
        )
        assert slot.current_candidate is not None
        assert slot.current_candidate.text == "Built new feature"
    
    def test_rejects_invalid_section(self):
        """Invalid section should raise error."""
        with pytest.raises(ValueError):
            BulletSlot(
                slot_index=0,
                section="invalid",
                subsection="Test"
            )


class TestCVSelectionPlan:
    """Test CVSelectionPlan model."""
    
    def test_creates_valid_plan(self):
        """Should create valid selection plan."""
        plan = CVSelectionPlan(
            job_id=1,
            job_title="Software Engineer",
            company="Acme Corp",
            role_family="general-swe",
            seniority_level="mid",
            required_keywords=["python", "api"],
            nice_to_have_keywords=["kubernetes"],
            technical_keywords=["docker"],
            work_experience_slots=[],
            technical_project_slots=[],
            projects_to_hide=[],
            keyword_coverage={},
            uncovered_keywords=[]
        )
        assert plan.job_id == 1
        assert plan.user_id == 1  # default
        assert plan.role_family == "general-swe"
    
    def test_rejects_invalid_role_family(self):
        """Invalid role family should raise error."""
        with pytest.raises(ValueError):
            CVSelectionPlan(
                job_id=1,
                job_title="Software Engineer",
                company="Acme Corp",
                role_family="invalid-family",
                seniority_level="mid",
                required_keywords=[],
                nice_to_have_keywords=[],
                technical_keywords=[],
                work_experience_slots=[],
                technical_project_slots=[],
                projects_to_hide=[],
                keyword_coverage={},
                uncovered_keywords=[]
            )
    
    def test_rejects_invalid_seniority(self):
        """Invalid seniority level should raise error."""
        with pytest.raises(ValueError):
            CVSelectionPlan(
                job_id=1,
                job_title="Software Engineer",
                company="Acme Corp",
                role_family="general-swe",
                seniority_level="executive",
                required_keywords=[],
                nice_to_have_keywords=[],
                technical_keywords=[],
                work_experience_slots=[],
                technical_project_slots=[],
                projects_to_hide=[],
                keyword_coverage={},
                uncovered_keywords=[]
            )


class TestValidateBulletText:
    """Test the standalone validate_bullet_text function."""
    
    def test_valid_text_returns_true(self):
        """Valid text should return is_valid=True."""
        is_valid, error, warnings = validate_bullet_text("Built new feature using Python")
        assert is_valid is True
        assert error == ""
    
    def test_empty_text_returns_false(self):
        """Empty text should return is_valid=False."""
        is_valid, error, warnings = validate_bullet_text("")
        assert is_valid is False
        assert "empty" in error.lower()
    
    def test_over_limit_returns_false(self):
        """Text over 120 chars should return is_valid=False."""
        is_valid, error, warnings = validate_bullet_text("A" * 121)
        assert is_valid is False
        assert "120" in error
    
    def test_starts_with_i_returns_false(self):
        """Text starting with 'I ' should return is_valid=False."""
        is_valid, error, warnings = validate_bullet_text("I built a new feature")
        assert is_valid is False
        assert "I" in error
    
    def test_banned_phrase_returns_false(self):
        """Text with banned phrase should return is_valid=False."""
        is_valid, error, warnings = validate_bullet_text("Worked in a fast-paced environment")
        assert is_valid is False
        assert "banned" in error.lower()
    
    def test_soft_limit_returns_warning(self):
        """Text over 110 chars should return warning but is_valid=True."""
        text = "A" * 115
        is_valid, error, warnings = validate_bullet_text(text)
        assert is_valid is True
        assert any("110" in w or "115" in w for w in warnings)
    
    def test_no_action_verb_returns_warning(self):
        """Text without action verb should return warning but is_valid=True."""
        is_valid, error, warnings = validate_bullet_text("The system was redesigned")
        assert is_valid is True
        assert any("action verb" in w.lower() for w in warnings)


class TestActionVerbs:
    """Test action verb list is comprehensive."""
    
    def test_common_past_verbs_included(self):
        """Common past tense verbs should be in the list."""
        common = ["developed", "built", "designed", "implemented", "created", "led", "managed"]
        for verb in common:
            assert verb in ACTION_VERBS, f"Missing common verb: {verb}"
    
    def test_common_present_verbs_included(self):
        """Common present tense verbs should be in the list."""
        common = ["develop", "build", "design", "implement", "create", "lead", "manage"]
        for verb in common:
            assert verb in ACTION_VERBS, f"Missing common verb: {verb}"
    
    def test_british_spellings_included(self):
        """British spellings should be in the list."""
        british = ["optimised", "organised", "analysed", "realised"]
        for verb in british:
            assert verb in ACTION_VERBS, f"Missing British spelling: {verb}"


class TestBannedPhrases:
    """Test banned phrases list."""
    
    def test_all_banned_phrases_lowercase(self):
        """All banned phrases should be lowercase for case-insensitive matching."""
        for phrase in BANNED_PHRASES:
            assert phrase == phrase.lower(), f"Banned phrase not lowercase: {phrase}"
    
    def test_core_banned_phrases_present(self):
        """Core banned phrases from spec should be present."""
        required = ["fast-paced environment", "passion for", "team player", "spearheaded"]
        for phrase in required:
            assert phrase in BANNED_PHRASES, f"Missing required banned phrase: {phrase}"
