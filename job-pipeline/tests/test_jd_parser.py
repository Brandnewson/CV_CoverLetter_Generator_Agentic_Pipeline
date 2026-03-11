"""Phase 4 tests - JD parser for role classification and keyword extraction."""

import pytest
from unittest.mock import Mock, MagicMock
from agent.config import get_claude_model
from agent.jd_parser import (
    classify_role_family,
    classify_seniority,
    extract_keywords,
    score_bullet_against_keywords,
    ROLE_FAMILIES,
    SENIORITY_RULES,
)


class TestClassifyRoleFamily:
    """Test role family classification."""
    
    def test_motorsport_from_title(self):
        """Should detect motorsport from F1-related title."""
        result = classify_role_family(
            "Software Engineer - Formula 1 Strategy",
            "Building race strategy software."
        )
        assert result == "motorsport"
    
    def test_motorsport_from_description(self):
        """Should detect motorsport from telemetry keywords."""
        result = classify_role_family(
            "Software Engineer",
            "Work on telemetry systems and vehicle dynamics simulation."
        )
        assert result == "motorsport"
    
    def test_ai_startup_from_llm_keywords(self):
        """Should detect ai-startup from LLM keywords."""
        result = classify_role_family(
            "ML Engineer",
            "Building large language model applications with RAG and embeddings."
        )
        assert result == "ai-startup"
    
    def test_ai_startup_from_ml_keywords(self):
        """Should detect ai-startup from machine learning keywords."""
        result = classify_role_family(
            "AI Engineer",
            "Deep learning and neural network development for inference optimization."
        )
        assert result == "ai-startup"
    
    def test_forward_deployed_from_title(self):
        """Should detect forward-deployed-swe from title."""
        result = classify_role_family(
            "Forward Deployed Engineer",
            "Work directly with customers to implement solutions."
        )
        assert result == "forward-deployed-swe"
    
    def test_forward_deployed_from_description(self):
        """Should detect forward-deployed-swe from description."""
        result = classify_role_family(
            "Solutions Engineer",
            "Customer engineering and professional services role."
        )
        assert result == "forward-deployed-swe"
    
    def test_general_swe_fallback(self):
        """Should fallback to general-swe when no specific keywords match."""
        result = classify_role_family(
            "Software Engineer",
            "Build web applications using Python and React."
        )
        assert result == "general-swe"
    
    def test_highest_score_wins(self):
        """When multiple families match, highest score should win."""
        result = classify_role_family(
            "AI Engineer",
            "Machine learning, deep learning, LLM, RAG, embeddings, fine-tuning, inference."
        )
        assert result == "ai-startup"  # More AI keywords than any other
    
    def test_case_insensitive(self):
        """Matching should be case-insensitive."""
        result = classify_role_family(
            "SOFTWARE ENGINEER - FORMULA 1",
            "Working on F1 TELEMETRY systems"
        )
        assert result == "motorsport"


class TestClassifySeniority:
    """Test seniority level classification."""
    
    def test_junior_from_title(self):
        """Should detect junior from title."""
        result = classify_seniority("Junior Software Engineer", "Building software.")
        assert result == "junior"
    
    def test_graduate_means_junior(self):
        """Graduate role should be classified as junior."""
        result = classify_seniority("Graduate Engineer", "Entry level position.")
        assert result == "junior"
    
    def test_senior_from_title(self):
        """Should detect senior from title."""
        result = classify_seniority("Senior Software Engineer", "Leading projects.")
        assert result == "senior"
    
    def test_lead_means_senior(self):
        """Lead role should be classified as senior."""
        result = classify_seniority("Lead Engineer", "Managing team.")
        assert result == "senior"
    
    def test_principal_means_senior(self):
        """Principal role should be classified as senior."""
        result = classify_seniority("Principal Engineer", "Technical leadership.")
        assert result == "senior"
    
    def test_staff_means_senior(self):
        """Staff engineer should be classified as senior."""
        result = classify_seniority("Staff Software Engineer", "Senior IC role.")
        assert result == "senior"
    
    def test_associate_means_junior_mid(self):
        """Associate should be classified as junior-mid."""
        result = classify_seniority("Associate Software Engineer", "Early career role.")
        assert result == "junior-mid"
    
    def test_mid_level_explicit(self):
        """Explicit mid-level should be detected."""
        result = classify_seniority("Mid-level Engineer", "Some experience required.")
        assert result == "mid"
    
    def test_default_to_mid(self):
        """Should default to mid when ambiguous."""
        result = classify_seniority("Software Engineer", "Build great software.")
        assert result == "mid"
    
    def test_title_takes_priority(self):
        """Title should take priority over description."""
        result = classify_seniority(
            "Junior Engineer",
            "Looking for a senior experienced candidate with 10+ years."
        )
        assert result == "junior"  # Title wins
    
    def test_intern_means_junior(self):
        """Intern should be classified as junior."""
        result = classify_seniority("Software Engineering Intern", "Summer placement.")
        assert result == "junior"
    
    def test_case_insensitive(self):
        """Matching should be case-insensitive."""
        result = classify_seniority("SENIOR SOFTWARE ENGINEER", "Building systems.")
        assert result == "senior"


class TestScoreBulletAgainstKeywords:
    """Test bullet scoring against keywords."""
    
    def test_perfect_match_required_keyword(self):
        """Bullet with required keyword should score well."""
        keywords = {
            "required_keywords": ["python"],
            "nice_to_have_keywords": [],
            "technical_skills": [],
            "soft_skills": [],
            "domain_keywords": [],
            "seniority_signals": []
        }
        score, matched = score_bullet_against_keywords(
            "Built REST API using Python and FastAPI", keywords
        )
        assert score > 0
        assert "python" in matched
    
    def test_multiple_keyword_hits(self):
        """Multiple keyword hits should increase score."""
        keywords = {
            "required_keywords": ["python", "api"],
            "nice_to_have_keywords": ["docker"],
            "technical_skills": ["fastapi"],
            "soft_skills": [],
            "domain_keywords": [],
            "seniority_signals": []
        }
        score, matched = score_bullet_against_keywords(
            "Built REST API using Python and FastAPI, deployed with Docker", keywords
        )
        assert score > 0.5
        assert len(matched) >= 3
    
    def test_no_match_scores_zero(self):
        """No matching keywords should score 0."""
        keywords = {
            "required_keywords": ["java", "spring"],
            "nice_to_have_keywords": ["kotlin"],
            "technical_skills": [],
            "soft_skills": [],
            "domain_keywords": [],
            "seniority_signals": []
        }
        score, matched = score_bullet_against_keywords(
            "Built REST API using Python and FastAPI", keywords
        )
        assert score == 0
        assert matched == []
    
    def test_case_insensitive_matching(self):
        """Matching should be case-insensitive."""
        keywords = {
            "required_keywords": ["Python", "API"],
            "nice_to_have_keywords": [],
            "technical_skills": [],
            "soft_skills": [],
            "domain_keywords": [],
            "seniority_signals": []
        }
        score, matched = score_bullet_against_keywords(
            "built rest api using python", keywords
        )
        assert score > 0
        assert len(matched) == 2
    
    def test_required_weighted_higher_than_nice_to_have(self):
        """Required keywords should have higher weight than nice-to-have."""
        keywords_required = {
            "required_keywords": ["python"],
            "nice_to_have_keywords": [],
            "technical_skills": [],
            "soft_skills": [],
            "domain_keywords": [],
            "seniority_signals": []
        }
        keywords_nice = {
            "required_keywords": [],
            "nice_to_have_keywords": ["python"],
            "technical_skills": [],
            "soft_skills": [],
            "domain_keywords": [],
            "seniority_signals": []
        }
        score_req, _ = score_bullet_against_keywords("Built with python", keywords_required)
        score_nice, _ = score_bullet_against_keywords("Built with python", keywords_nice)
        assert score_req > score_nice
    
    def test_empty_keywords_returns_zero(self):
        """Empty keywords dict should return 0 score."""
        score, matched = score_bullet_against_keywords(
            "Built REST API using Python",
            {}
        )
        assert score == 0
        assert matched == []
    
    def test_score_normalised_to_one(self):
        """Score should be normalised to max 1.0."""
        keywords = {
            "required_keywords": ["a", "b", "c", "d", "e"],
            "nice_to_have_keywords": [],
            "technical_skills": [],
            "soft_skills": [],
            "domain_keywords": [],
            "seniority_signals": []
        }
        score, matched = score_bullet_against_keywords(
            "a b c d e", keywords
        )
        assert score <= 1.0

    def test_alias_matching_ci_cd(self):
        """Alias matching should map continuous integration terms to ci/cd keyword."""
        keywords = {
            "required_keywords": ["ci/cd"],
            "nice_to_have_keywords": [],
            "technical_skills": [],
            "soft_skills": [],
            "domain_keywords": [],
            "seniority_signals": []
        }
        score, matched = score_bullet_against_keywords(
            "Implemented continuous integration workflows and release automation", keywords
        )
        assert score > 0
        assert "ci/cd" in matched

    def test_alias_matching_nodejs(self):
        """Alias matching should map nodejs token to node.js keyword."""
        keywords = {
            "required_keywords": ["node.js"],
            "nice_to_have_keywords": [],
            "technical_skills": [],
            "soft_skills": [],
            "domain_keywords": [],
            "seniority_signals": []
        }
        score, matched = score_bullet_against_keywords(
            "Built backend services with nodejs and TypeScript", keywords
        )
        assert score > 0
        assert "node.js" in matched


class TestExtractKeywords:
    """Test keyword extraction with mocked API."""
    
    def test_extracts_keywords_from_response(self):
        """Should parse keywords from API response."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock(text='{"required_keywords": ["python", "api"], "nice_to_have_keywords": ["docker"], "technical_skills": ["fastapi"], "soft_skills": [], "domain_keywords": [], "seniority_signals": []}')]
        mock_response.usage = Mock(input_tokens=100, output_tokens=50)
        mock_client.messages.create.return_value = mock_response
        
        result = extract_keywords(
            "We need a Python developer to build APIs with FastAPI. Docker is a plus.",
            "general-swe",
            mock_client
        )
        
        assert "python" in result["required_keywords"]
        assert "docker" in result["nice_to_have_keywords"]
        assert mock_client.messages.create.called
    
    def test_handles_markdown_code_blocks(self):
        """Should handle responses wrapped in markdown code blocks."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock(text='```json\n{"required_keywords": ["python"], "nice_to_have_keywords": [], "technical_skills": [], "soft_skills": [], "domain_keywords": [], "seniority_signals": []}\n```')]
        mock_response.usage = Mock(input_tokens=100, output_tokens=50)
        mock_client.messages.create.return_value = mock_response
        
        result = extract_keywords("Python developer needed", "general-swe", mock_client)
        
        assert "python" in result["required_keywords"]
    
    def test_handles_invalid_json(self):
        """Should return empty structure on invalid JSON."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock(text='This is not valid JSON')]
        mock_response.usage = Mock(input_tokens=100, output_tokens=50)
        mock_client.messages.create.return_value = mock_response
        
        result = extract_keywords("Python developer", "general-swe", mock_client)
        
        assert result["required_keywords"] == []
        assert "nice_to_have_keywords" in result
    
    def test_fills_missing_keys(self):
        """Should fill in missing keys with empty lists."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock(text='{"required_keywords": ["python"]}')]
        mock_response.usage = Mock(input_tokens=100, output_tokens=50)
        mock_client.messages.create.return_value = mock_response
        
        result = extract_keywords("Python developer", "general-swe", mock_client)
        
        assert result["required_keywords"] == ["python"]
        assert result["nice_to_have_keywords"] == []
        assert result["technical_skills"] == []
        assert result["soft_skills"] == []
        assert result["domain_keywords"] == []
        assert result["seniority_signals"] == []
    
    def test_uses_correct_model(self):
        """Should use configured Claude model."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = [Mock(text='{"required_keywords": [], "nice_to_have_keywords": [], "technical_skills": [], "soft_skills": [], "domain_keywords": [], "seniority_signals": []}')]
        mock_response.usage = Mock(input_tokens=100, output_tokens=50)
        mock_client.messages.create.return_value = mock_response
        
        extract_keywords("Test description", "general-swe", mock_client)
        
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == get_claude_model()


class TestRoleFamilyKeywords:
    """Test that role family keyword lists are comprehensive."""
    
    def test_motorsport_keywords_present(self):
        """Motorsport should have F1/racing keywords."""
        keywords = ROLE_FAMILIES["motorsport"]
        assert "formula 1" in keywords or "f1" in keywords
        assert "telemetry" in keywords
        assert "vehicle dynamics" in keywords
    
    def test_ai_startup_keywords_present(self):
        """AI startup should have ML/LLM keywords."""
        keywords = ROLE_FAMILIES["ai-startup"]
        assert "machine learning" in keywords
        assert "llm" in keywords or "large language model" in keywords
        assert "rag" in keywords or "embeddings" in keywords
    
    def test_forward_deployed_keywords_present(self):
        """Forward deployed should have customer-facing keywords."""
        keywords = ROLE_FAMILIES["forward-deployed-swe"]
        assert "forward deployed" in keywords
        assert "solutions engineer" in keywords or "customer engineering" in keywords
    
    def test_general_swe_is_empty(self):
        """General SWE should have empty keywords (fallback)."""
        assert ROLE_FAMILIES["general-swe"] == []


class TestSeniorityKeywords:
    """Test that seniority keyword lists are correct."""
    
    def test_junior_includes_graduate(self):
        """Junior should include graduate and intern."""
        keywords = SENIORITY_RULES["junior"]
        assert "junior" in keywords
        assert "graduate" in keywords
        assert "intern" in keywords
    
    def test_senior_includes_lead(self):
        """Senior should include lead, principal, staff."""
        keywords = SENIORITY_RULES["senior"]
        assert "senior" in keywords
        assert "lead" in keywords
        assert "principal" in keywords
        assert "staff" in keywords
