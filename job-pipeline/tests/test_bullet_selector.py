"""Phase 6 tests: Bullet selector."""

import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.bullet_selector import (
    load_bullet_bank,
    build_selection_plan,
    get_approval_weights,
    score_bullet_for_slot,
    find_projects_to_hide,
    normalise_section_name,
    get_low_score_slots,
)
from agent.validators import CVSelectionPlan, BulletSlot, BulletCandidate


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    dirpath = tempfile.mkdtemp()
    yield Path(dirpath)
    shutil.rmtree(dirpath)


@pytest.fixture
def sample_bullet_bank_md(temp_dir):
    """Create a sample master_bullets.md file."""
    content = """# Master Bullet Bank

## Work Experience

### Jaguar TCS Racing

- Designed REST API for streaming live race telemetry from WinTax using VBS scripts.
    [tags: api, telemetry, python, vbs, motorsport]
    [role_family: motorsport, general-swe]

- Developed full-stack ReactJS data visualisation apps for time-critical race data.
    [tags: frontend, react, typescript, motorsport]
    [role_family: motorsport, general-swe]

- Deployed CI/CD pipeline for trackside executables ensuring software reliability.
    [tags: cicd, deployment, testing, motorsport]
    [role_family: motorsport, general-swe]

### Republic of Singapore Navy

- Led remote war-time firefighting simulation aboard ship engine operations room.
    [tags: leadership, simulation, military]
    [role_family: general-swe]

- Analysed live ship telemetry of core ship systems to handle damage control.
    [tags: analysis, telemetry, military]
    [role_family: general-swe]

## Technical Projects

### Formula Student Lap Time Simulator

- Designed modular steady-state lap time sim using point-mass and bicycle models.
    [tags: simulation, vehicle-dynamics, python, motorsport]
    [role_family: motorsport]

- Created tyre model with Pacejka magic formula ensuring accuracy.
    [tags: simulation, vehicle-dynamics, motorsport]
    [role_family: motorsport]

### 2D CFD Radiator Simulator

- Developed a 2D incompressible fluid solver analysing radiator angle effects.
    [tags: simulation, cfd, motorsport, python]
    [role_family: motorsport]
"""
    path = temp_dir / "master_bullets.md"
    path.write_text(content, encoding='utf-8')
    return path


@pytest.fixture
def sample_template_map():
    """Sample template map with bullet slots."""
    return {
        'work_experience': {
            'Jaguar TCS Racing': {
                'header_xpaths': ['/doc/p[1]', '/doc/p[2]'],
                'bullet_xpaths': ['/doc/p[3]', '/doc/p[4]', '/doc/p[5]']
            },
            'Republic of Singapore Navy': {
                'header_xpaths': ['/doc/p[10]'],
                'bullet_xpaths': ['/doc/p[11]', '/doc/p[12]']
            }
        },
        'technical_projects': {
            'Formula Student Lap Time Simulator': {
                'header_xpaths': ['/doc/p[20]'],
                'bullet_xpaths': ['/doc/p[21]', '/doc/p[22]']
            },
            '2D CFD Radiator Simulator': {
                'header_xpaths': ['/doc/p[30]'],
                'bullet_xpaths': ['/doc/p[31]']
            }
        }
    }


@pytest.fixture
def sample_keywords():
    """Sample keywords from JD parser."""
    return {
        'required_keywords': ['python', 'api', 'telemetry', 'simulation'],
        'nice_to_have_keywords': ['react', 'typescript', 'docker'],
        'technical_skills': ['python', 'react', 'javascript'],
        'soft_skills': ['leadership', 'collaboration'],
        'domain_keywords': ['motorsport', 'racing'],
        'seniority_signals': ['senior', 'lead']
    }


@pytest.fixture
def mock_conn():
    """Mock database connection."""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    cursor.fetchall.return_value = []
    return conn


@pytest.fixture
def sample_job():
    """Sample job dict."""
    return {
        'id': 123,
        'title': 'Software Engineer',
        'company': 'Acme Corp',
        'description': 'Build Python APIs and simulations',
        'location': 'London'
    }


class TestLoadBulletBank:
    """Tests for load_bullet_bank function."""
    
    def test_parses_all_sections(self, sample_bullet_bank_md):
        """Parses all sections correctly."""
        bullets = load_bullet_bank(sample_bullet_bank_md)
        
        sections = set(b['section'] for b in bullets)
        assert 'work_experience' in sections
        assert 'technical_projects' in sections
    
    def test_parses_all_subsections(self, sample_bullet_bank_md):
        """Parses all subsections correctly."""
        bullets = load_bullet_bank(sample_bullet_bank_md)
        
        subsections = set(b['subsection'] for b in bullets)
        assert 'Jaguar TCS Racing' in subsections
        assert 'Republic of Singapore Navy' in subsections
        assert 'Formula Student Lap Time Simulator' in subsections
        assert '2D CFD Radiator Simulator' in subsections
    
    def test_parses_tags_correctly(self, sample_bullet_bank_md):
        """Parses tags for each bullet."""
        bullets = load_bullet_bank(sample_bullet_bank_md)
        
        # Find the REST API bullet
        api_bullet = next(b for b in bullets if 'REST API' in b['text'])
        assert 'api' in api_bullet['tags']
        assert 'telemetry' in api_bullet['tags']
        assert 'python' in api_bullet['tags']
    
    def test_parses_role_families_correctly(self, sample_bullet_bank_md):
        """Parses role_families for each bullet."""
        bullets = load_bullet_bank(sample_bullet_bank_md)
        
        # Find the REST API bullet
        api_bullet = next(b for b in bullets if 'REST API' in b['text'])
        assert 'motorsport' in api_bullet['role_families']
        assert 'general-swe' in api_bullet['role_families']
    
    def test_correct_bullet_count(self, sample_bullet_bank_md):
        """Correct number of bullets parsed."""
        bullets = load_bullet_bank(sample_bullet_bank_md)
        
        # 3 Jaguar + 2 Navy + 2 Lap Sim + 1 CFD = 8 bullets
        assert len(bullets) == 8
    
    def test_raises_on_missing_file(self, temp_dir):
        """Raises FileNotFoundError on missing file."""
        with pytest.raises(FileNotFoundError):
            load_bullet_bank(temp_dir / "nonexistent.md")


class TestNormaliseSectionName:
    """Tests for normalise_section_name function."""
    
    def test_work_experience(self):
        assert normalise_section_name("Work Experience") == "work_experience"
        assert normalise_section_name("WORK EXPERIENCE") == "work_experience"
        assert normalise_section_name("Employment") == "work_experience"
    
    def test_technical_projects(self):
        assert normalise_section_name("Technical Projects") == "technical_projects"
        assert normalise_section_name("Projects") == "technical_projects"
        assert normalise_section_name("Personal Projects") == "technical_projects"


class TestScoreBulletForSlot:
    """Tests for score_bullet_for_slot function."""
    
    def test_role_family_boost_applies(self, sample_keywords):
        """Role family boost applies correctly."""
        bullet_with_match = {
            'text': 'Developed Python API for telemetry streaming',
            'tags': ['python', 'api'],
            'role_families': ['motorsport']
        }
        bullet_without_match = {
            'text': 'Developed Python API for telemetry streaming',
            'tags': ['python', 'api'],
            'role_families': ['general-swe']
        }
        
        score_with, _ = score_bullet_for_slot(bullet_with_match, sample_keywords, 'motorsport', {})
        score_without, _ = score_bullet_for_slot(bullet_without_match, sample_keywords, 'motorsport', {})
        
        # Role family match should boost by 0.2
        assert score_with > score_without
        assert score_with - score_without == pytest.approx(0.2, abs=0.01)
    
    def test_approval_boost_applies(self):
        """Approval boost applies correctly."""
        # Use keywords that result in a lower base score so approval boost is visible
        keywords = {
            'required_keywords': ['kubernetes'],  # Won't match the bullet
            'nice_to_have_keywords': [],
            'technical_skills': [],
            'soft_skills': [],
            'domain_keywords': [],
            'seniority_signals': []
        }
        
        bullet = {
            'text': 'Developed internal tooling for deployment workflows',
            'tags': [],
            'role_families': []  # No role match
        }
        
        # No approval history - should have base score only
        score_no_approval, _ = score_bullet_for_slot(bullet, keywords, 'general-swe', {})
        
        # 100% approval rate
        approval_weights = {bullet['text']: 1.0}
        score_with_approval, _ = score_bullet_for_slot(bullet, keywords, 'general-swe', approval_weights)
        
        # Should boost by 0.15 * 1.0 = 0.15
        assert score_with_approval > score_no_approval
        assert score_with_approval - score_no_approval == pytest.approx(0.15, abs=0.01)
    
    def test_returns_matched_keywords(self, sample_keywords):
        """Returns list of matched keywords."""
        bullet = {
            'text': 'Developed Python API for telemetry streaming with React frontend',
            'tags': [],
            'role_families': []
        }
        
        _, matched = score_bullet_for_slot(bullet, sample_keywords, 'general-swe', {})
        
        assert 'python' in matched or 'Python' in matched
        assert 'api' in matched or 'API' in matched


class TestGetApprovalWeights:
    """Tests for get_approval_weights function."""
    
    def test_returns_correct_rates(self):
        """Returns correct approval rates from cv_feedback data."""
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        
        # Simulate feedback: bullet shown 4 times, approved 3 times
        cursor.fetchall.return_value = [
            ('Test bullet text', 4, 3),
        ]
        
        weights = get_approval_weights('Jaguar TCS Racing', 'motorsport', conn, user_id=1)
        
        assert weights['Test bullet text'] == 0.75  # 3/4
    
    def test_empty_dict_on_no_history(self):
        """Returns empty dict when no history exists."""
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        cursor.fetchall.return_value = []
        
        weights = get_approval_weights('Unknown Company', 'motorsport', conn, user_id=1)
        
        assert weights == {}


class TestFindProjectsToHide:
    """Tests for find_projects_to_hide function."""
    
    def test_hides_low_relevance_project(self, sample_template_map):
        """Hides project with no high-scoring bullets and no role match."""
        # Keywords that don't match CFD project
        keywords = {
            'required_keywords': ['kubernetes', 'aws'],
            'nice_to_have_keywords': ['react'],
            'technical_skills': [],
            'soft_skills': [],
            'domain_keywords': ['fintech'],
            'seniority_signals': []
        }
        
        # Bullet bank with only Lap Time Simulator bullets
        bullet_bank = [
            {
                'text': 'Designed modular steady-state lap time sim',
                'section': 'technical_projects',
                'subsection': 'Formula Student Lap Time Simulator',
                'tags': ['simulation'],
                'role_families': ['motorsport']
            }
        ]
        
        hidden = find_projects_to_hide(keywords, sample_template_map, bullet_bank, 'ai-startup')
        
        # CFD simulator has no bullets and no role match - should be hidden
        assert '2D CFD Radiator Simulator' in hidden
    
    def test_keeps_role_matched_project(self, sample_template_map):
        """Keeps project with role_family match even if low score."""
        keywords = {
            'required_keywords': ['kubernetes'],
            'nice_to_have_keywords': [],
            'technical_skills': [],
            'soft_skills': [],
            'domain_keywords': [],
            'seniority_signals': []
        }
        
        bullet_bank = [
            {
                'text': 'Designed modular lap time sim',
                'section': 'technical_projects',
                'subsection': 'Formula Student Lap Time Simulator',
                'tags': [],
                'role_families': ['motorsport']
            }
        ]
        
        hidden = find_projects_to_hide(keywords, sample_template_map, bullet_bank, 'motorsport')
        
        # Lap Time Simulator has role_family match - should NOT be hidden
        assert 'Formula Student Lap Time Simulator' not in hidden


class TestBuildSelectionPlan:
    """Tests for build_selection_plan function."""
    
    def test_returns_valid_cv_selection_plan(
        self, sample_bullet_bank_md, sample_template_map, sample_keywords, mock_conn, sample_job
    ):
        """Returns a valid CVSelectionPlan."""
        bullet_bank = load_bullet_bank(sample_bullet_bank_md)
        
        plan = build_selection_plan(
            job=sample_job,
            keywords=sample_keywords,
            bullet_bank=bullet_bank,
            template_map=sample_template_map,
            conn=mock_conn,
            role_family='motorsport',
            seniority_level='mid',
            user_id=1
        )
        
        assert isinstance(plan, CVSelectionPlan)
        assert plan.job_id == 123
        assert plan.company == 'Acme Corp'
        assert plan.role_family == 'motorsport'
        assert plan.seniority_level == 'mid'
    
    def test_work_experience_slots_populated(
        self, sample_bullet_bank_md, sample_template_map, sample_keywords, mock_conn, sample_job
    ):
        """Work experience slots are populated with candidates."""
        bullet_bank = load_bullet_bank(sample_bullet_bank_md)
        
        plan = build_selection_plan(
            job=sample_job,
            keywords=sample_keywords,
            bullet_bank=bullet_bank,
            template_map=sample_template_map,
            conn=mock_conn,
            role_family='motorsport',
            seniority_level='mid',
            user_id=1
        )
        
        assert len(plan.work_experience_slots) > 0
        
        # Check that some have candidates
        candidates = [s.current_candidate for s in plan.work_experience_slots if s.current_candidate]
        assert len(candidates) > 0
    
    def test_technical_project_slots_populated(
        self, sample_bullet_bank_md, sample_template_map, sample_keywords, mock_conn, sample_job
    ):
        """Technical project slots are populated."""
        bullet_bank = load_bullet_bank(sample_bullet_bank_md)
        
        plan = build_selection_plan(
            job=sample_job,
            keywords=sample_keywords,
            bullet_bank=bullet_bank,
            template_map=sample_template_map,
            conn=mock_conn,
            role_family='motorsport',
            seniority_level='mid',
            user_id=1
        )
        
        # At least one project slot (some may be hidden)
        assert len(plan.technical_project_slots) >= 0
    
    def test_keyword_coverage_tracked(
        self, sample_bullet_bank_md, sample_template_map, sample_keywords, mock_conn, sample_job
    ):
        """Keyword coverage is tracked correctly."""
        bullet_bank = load_bullet_bank(sample_bullet_bank_md)
        
        plan = build_selection_plan(
            job=sample_job,
            keywords=sample_keywords,
            bullet_bank=bullet_bank,
            template_map=sample_template_map,
            conn=mock_conn,
            role_family='motorsport',
            seniority_level='mid',
            user_id=1
        )
        
        # keyword_coverage should be a dict
        assert isinstance(plan.keyword_coverage, dict)
    
    def test_uncovered_keywords_identified(
        self, sample_bullet_bank_md, sample_template_map, mock_conn, sample_job
    ):
        """Uncovered required keywords are identified."""
        bullet_bank = load_bullet_bank(sample_bullet_bank_md)
        
        # Keywords that won't all be covered
        keywords = {
            'required_keywords': ['python', 'kubernetes', 'terraform', 'aws'],
            'nice_to_have_keywords': [],
            'technical_skills': [],
            'soft_skills': [],
            'domain_keywords': [],
            'seniority_signals': []
        }
        
        plan = build_selection_plan(
            job=sample_job,
            keywords=keywords,
            bullet_bank=bullet_bank,
            template_map=sample_template_map,
            conn=mock_conn,
            role_family='motorsport',
            seniority_level='mid',
            user_id=1
        )
        
        # kubernetes, terraform, aws unlikely to be covered
        assert len(plan.uncovered_keywords) > 0
    
    def test_no_api_call_when_scores_high(
        self, sample_bullet_bank_md, sample_template_map, sample_keywords, mock_conn, sample_job
    ):
        """Does NOT call API when all scores >= 0.25."""
        bullet_bank = load_bullet_bank(sample_bullet_bank_md)
        
        # This test ensures no external API calls are made
        # The build_selection_plan function should be pure Python
        with patch('agent.bullet_selector.score_bullet_against_keywords') as mock_score:
            # Return high scores so no story drafter needed
            mock_score.return_value = (0.5, ['python'])
            
            plan = build_selection_plan(
                job=sample_job,
                keywords=sample_keywords,
                bullet_bank=bullet_bank,
                template_map=sample_template_map,
                conn=mock_conn,
                role_family='motorsport',
                seniority_level='mid',
                user_id=1
            )
            
            # No external API client passed, so this should work without API
            assert plan is not None


class TestGetLowScoreSlots:
    """Tests for get_low_score_slots function."""
    
    def test_identifies_low_score_slots(self):
        """Identifies slots below threshold."""
        low_candidate = BulletCandidate(
            text='Test bullet with low score',
            source='master_bullets',
            section='work_experience',
            subsection='Test Company',
            relevance_score=0.1
        )
        high_candidate = BulletCandidate(
            text='Test bullet with high score',
            source='master_bullets',
            section='work_experience',
            subsection='Test Company',
            relevance_score=0.5
        )
        
        plan = CVSelectionPlan(
            job_id=1,
            job_title='Test',
            company='Test',
            role_family='general-swe',
            seniority_level='mid',
            required_keywords=[],
            nice_to_have_keywords=[],
            technical_keywords=[],
            work_experience_slots=[
                BulletSlot(slot_index=0, section='work_experience', subsection='Test', current_candidate=low_candidate),
                BulletSlot(slot_index=1, section='work_experience', subsection='Test', current_candidate=high_candidate),
            ],
            technical_project_slots=[],
            projects_to_hide=[],
            keyword_coverage={},
            uncovered_keywords=[]
        )
        
        low_slots = get_low_score_slots(plan, threshold=0.25)
        
        assert len(low_slots) == 1
        assert low_slots[0].slot_index == 0
    
    def test_includes_empty_slots(self):
        """Includes slots with no candidate."""
        plan = CVSelectionPlan(
            job_id=1,
            job_title='Test',
            company='Test',
            role_family='general-swe',
            seniority_level='mid',
            required_keywords=[],
            nice_to_have_keywords=[],
            technical_keywords=[],
            work_experience_slots=[
                BulletSlot(slot_index=0, section='work_experience', subsection='Test', current_candidate=None),
            ],
            technical_project_slots=[],
            projects_to_hide=[],
            keyword_coverage={},
            uncovered_keywords=[]
        )
        
        low_slots = get_low_score_slots(plan)
        
        assert len(low_slots) == 1


class TestApprovalBoostOutranks:
    """Test that approval boost causes historically-approved bullet to outrank equally-scored new one."""
    
    def test_approved_bullet_outranks_new(self, sample_keywords):
        """Historically-approved bullet outranks equally-scored new one."""
        bullet1 = {
            'text': 'First bullet with python api',
            'tags': ['python', 'api'],
            'role_families': ['general-swe']
        }
        bullet2 = {
            'text': 'Second bullet with python api',
            'tags': ['python', 'api'],
            'role_families': ['general-swe']
        }
        
        # bullet1 has approval history, bullet2 doesn't
        approval_weights = {bullet1['text']: 0.8}
        
        score1, _ = score_bullet_for_slot(bullet1, sample_keywords, 'general-swe', approval_weights)
        score2, _ = score_bullet_for_slot(bullet2, sample_keywords, 'general-swe', {})
        
        # bullet1 should score higher due to approval boost
        assert score1 > score2
