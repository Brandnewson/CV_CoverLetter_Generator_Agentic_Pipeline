"""Phase 11 tests: Web UI."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.validators import BulletCandidate, BulletSlot, CVSelectionPlan, UserSelections


# Mock the things we need before importing
@pytest.fixture
def mock_env(tmp_path):
    """Set up mock environment."""
    env = {
        "DATABASE_URL": "postgresql://test@localhost/test"
    }
    with patch.dict("os.environ", env):
        yield tmp_path


@pytest.fixture
def mock_profile_dir(tmp_path):
    """Create mock profile directory with required files."""
    profile_dir = tmp_path / "profile"
    profile_dir.mkdir()
    
    # Create template_map.json
    template_map = {
        "work_experience": {
            "Test Company": {
                "title_stack": ["Test Company", "Software Engineer"],
                "bullet_xpaths": ["//body[1]", "//body[2]"]
            }
        },
        "technical_projects": {
            "Test Project": {
                "title_stack": ["Test Project"],
                "bullet_xpaths": ["//body[3]"]
            }
        }
    }
    (profile_dir / "template_map.json").write_text(json.dumps(template_map))
    
    # Create master_bullets.md
    bullets = """## Work Experience
### Test Company
- Built a test system using Python
    [tags: python, testing]
    [role_family: general-swe]

## Technical Projects
### Test Project
- Created a demo application with React
    [tags: react, frontend]
    [role_family: general-swe]
"""
    (profile_dir / "master_bullets.md").write_text(bullets)
    
    # Create cv_template.docx (minimal)
    # We won't actually test DOCX generation fully
    
    return profile_dir


@pytest.fixture
def sample_plan():
    """Create a sample CVSelectionPlan for testing."""
    work_slot = BulletSlot(
        slot_index=0,
        section="work_experience",
        subsection="Test Company",
        current_candidate=BulletCandidate(
            text="Built a test system using Python",
            source="master_bullets",
            section="work_experience",
            subsection="Test Company",
            tags=["python", "testing"],
            role_families=["general-swe"],
            relevance_score=0.6,
            keyword_hits=["python"]
        ),
        is_approved=False
    )
    
    project_slot = BulletSlot(
        slot_index=1,
        section="technical_projects",
        subsection="Test Project",
        current_candidate=BulletCandidate(
            text="Created a demo application with React",
            source="master_bullets",
            section="technical_projects",
            subsection="Test Project",
            tags=["react", "frontend"],
            role_families=["general-swe"],
            relevance_score=0.5,
            keyword_hits=["react"]
        ),
        is_approved=False
    )
    
    return CVSelectionPlan(
        job_id=1,
        user_id=1,
        job_title="Software Engineer",
        company="Test Corp",
        role_family="general-swe",
        seniority_level="mid",
        required_keywords=["python", "react"],
        nice_to_have_keywords=["typescript"],
        technical_keywords=["python", "react", "javascript"],
        work_experience_slots=[work_slot],
        technical_project_slots=[project_slot],
        projects_to_hide=[],
        keyword_coverage={"python": [0], "react": [1]},
        uncovered_keywords=[]
    )


@pytest.fixture
def sample_job():
    """Create a sample job dict."""
    return {
        "id": 1,
        "title": "Software Engineer",
        "company": "Test Corp",
        "location": "London",
        "description": "We need a Python developer with React experience.",
        "salary_min": 50000,
        "salary_max": 70000,
        "job_url": "https://example.com/job/1",
        "source": "test",
        "status": "queued",
        "fit_score": 0.85,
        "fit_summary": "Good match for Python and React skills"
    }


class TestFlaskApp:
    """Test Flask app initialization and basic routes."""
    
    def test_app_imports_without_error(self):
        """Flask app module can be imported."""
        # This tests that the module is syntactically correct
        # We mock the database connection to avoid connection errors
        with patch("psycopg2.connect"):
            with patch.dict("os.environ", {"DATABASE_URL": "postgresql://test@localhost/test"}):
                from dashboard import cv_builder_ui
                assert cv_builder_ui.app is not None
    
    def test_app_has_required_routes(self):
        """App has all required routes."""
        with patch("psycopg2.connect"):
            with patch.dict("os.environ", {"DATABASE_URL": "postgresql://test@localhost/test"}):
                from dashboard import cv_builder_ui
                
                # Get all registered routes
                routes = {rule.rule for rule in cv_builder_ui.app.url_map.iter_rules()}
                
                # Check required routes
                assert "/" in routes
                assert "/build/<int:job_id>" in routes
                assert "/api/plan/<int:job_id>" in routes
                assert "/api/rephrase" in routes
                assert "/api/jobs/<int:job_id>/enrichment" in routes
                assert "/api/approve/<int:job_id>" in routes
                assert "/api/cv/<int:job_id>/download" in routes
                assert "/api/jobs/queued" in routes
                assert "/api/bullets/add-to-bank" in routes


class TestAPIEndpoints:
    """Test API endpoint responses."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        with patch("psycopg2.connect"):
            with patch.dict("os.environ", {"DATABASE_URL": "postgresql://test@localhost/test"}):
                from dashboard import cv_builder_ui
                cv_builder_ui.app.config["TESTING"] = True
                with cv_builder_ui.app.test_client() as client:
                    yield client
    
    def test_index_redirects_to_build(self, client):
        """GET / redirects to /build/<job_id> when queued jobs exist."""
        with patch("dashboard.cv_builder_ui.get_db_connection") as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [(1, "Test Job", "Test Co", 0.9)]
            mock_conn.return_value.__enter__ = MagicMock(return_value=mock_conn.return_value)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)
            mock_conn.return_value.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
            mock_conn.return_value.cursor.return_value.__exit__ = MagicMock(return_value=False)
            
            response = client.get("/", follow_redirects=False)
            # Should redirect or render template
            assert response.status_code in [200, 302, 308]
    
    def test_build_renders_template(self, client):
        """GET /build/<job_id> renders cv_builder.html."""
        response = client.get("/build/1")
        assert response.status_code == 200
        assert b"CV Builder" in response.data
    
    def test_get_plan_returns_json(self, client, sample_plan, sample_job):
        """GET /api/plan/<job_id> returns valid CVSelectionPlan JSON."""
        with patch("dashboard.cv_builder_ui.get_db_connection") as mock_conn:
            with patch("dashboard.cv_builder_ui.get_job_by_id") as mock_get_job:
                with patch("dashboard.cv_builder_ui.build_plan_for_job") as mock_build:
                    mock_get_job.return_value = sample_job
                    mock_build.return_value = (sample_plan, {
                        "required_keywords": ["python"],
                        "nice_to_have_keywords": [],
                        "technical_skills": ["python"]
                    })
                    mock_conn.return_value.close = MagicMock()
                    
                    response = client.get("/api/plan/1")
                    
                    assert response.status_code == 200
                    data = response.get_json()
                    assert "job_id" in data
                    assert "work_experience_slots" in data
                    assert "technical_project_slots" in data
                    assert data["job_id"] == 1
    
    def test_get_plan_job_not_found(self, client):
        """GET /api/plan/<job_id> returns 404 for unknown job."""
        with patch("dashboard.cv_builder_ui.get_db_connection") as mock_conn:
            with patch("dashboard.cv_builder_ui.get_job_by_id") as mock_get_job:
                mock_get_job.return_value = None
                mock_conn.return_value.close = MagicMock()
                
                response = client.get("/api/plan/999")
                
                assert response.status_code == 404
                data = response.get_json()
                assert "error" in data
    
    def test_rephrase_returns_bullet_candidate(self, client, sample_plan):
        """POST /api/rephrase returns valid BulletCandidate JSON."""
        from dashboard import cv_builder_ui
        
        # Set up active plan
        cv_builder_ui.active_plans[1] = sample_plan
        cv_builder_ui.active_keywords[1] = {
            "required_keywords": ["python"],
            "nice_to_have_keywords": [],
            "technical_skills": ["python"]
        }
        
        with patch("dashboard.cv_builder_ui.rephrase_bullet") as mock_rephrase:
            mock_rephrase.return_value = BulletCandidate(
                text="Developed a testing framework in Python",
                source="rephrasing",
                section="work_experience",
                subsection="Test Company",
                relevance_score=0.7,
                keyword_hits=["python", "testing"],
                rephrase_generation=1
            )
            
            response = client.post(
                "/api/rephrase",
                json={
                    "job_id": 1,
                    "slot_index": 0,
                    "section": "work_experience",
                    "subsection": "Test Company"
                }
            )
            
            assert response.status_code == 200
            data = response.get_json()
            assert "text" in data
            assert "source" in data
            assert data["source"] == "rephrasing"
    
    def test_rephrase_without_plan_returns_error(self, client):
        """POST /api/rephrase returns error when plan not loaded."""
        from dashboard import cv_builder_ui
        cv_builder_ui.active_plans.clear()
        
        response = client.post(
            "/api/rephrase",
            json={
                "job_id": 999,
                "slot_index": 0,
                "section": "work_experience",
                "subsection": "Test Company"
            }
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_update_enrichment_saves_job_fields(self, client, sample_job):
        """PATCH /api/jobs/<job_id>/enrichment persists edited fields."""
        from dashboard import cv_builder_ui

        cv_builder_ui.active_plans[1] = "cached"
        cv_builder_ui.active_keywords[1] = {"required_keywords": ["python"]}

        with patch("dashboard.cv_builder_ui.get_db_connection") as mock_conn:
            with patch("dashboard.cv_builder_ui.update_job_enrichment") as mock_update:
                with patch("dashboard.cv_builder_ui.get_job_by_id") as mock_get_job:
                    mock_update.return_value = True
                    mock_get_job.return_value = sample_job
                    mock_conn.return_value.commit = MagicMock()
                    mock_conn.return_value.close = MagicMock()

                    response = client.patch(
                        "/api/jobs/1/enrichment",
                        json={
                            "job_description_raw": "Updated JD",
                            "company_description_raw": "Updated company",
                            "enrichment_keywords": {
                                "technologies": ["python", "react"],
                                "skills": ["communication"],
                                "abilities": ["ownership"],
                            },
                        },
                    )

                    assert response.status_code == 200
                    data = response.get_json()
                    assert data["status"] == "saved"
                    assert "job" in data
                    assert 1 not in cv_builder_ui.active_plans
                    assert 1 not in cv_builder_ui.active_keywords

    def test_update_enrichment_invalid_keywords_shape(self, client):
        """PATCH /api/jobs/<job_id>/enrichment validates keyword payload type."""
        response = client.patch(
            "/api/jobs/1/enrichment",
            json={
                "job_description_raw": "Updated JD",
                "company_description_raw": "Updated company",
                "enrichment_keywords": ["python", "react"],
            },
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
    
    def test_approve_triggers_render(self, client, sample_job):
        """POST /api/approve triggers CV render and returns cv_path."""
        with patch("dashboard.cv_builder_ui.get_db_connection") as mock_conn:
            with patch("dashboard.cv_builder_ui.get_job_by_id") as mock_get_job:
                with patch("dashboard.cv_builder_ui.render_cv") as mock_render:
                    mock_get_job.return_value = sample_job
                    mock_render.return_value = Path("/tmp/cv_1_Test_Corp.docx")
                    
                    mock_cursor = MagicMock()
                    mock_conn.return_value.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
                    mock_conn.return_value.cursor.return_value.__exit__ = MagicMock(return_value=False)
                    mock_conn.return_value.commit = MagicMock()
                    mock_conn.return_value.close = MagicMock()
                    
                    response = client.post(
                        "/api/approve/1",
                        json={
                            "user_id": 1,
                            "approved_bullets": [
                                {
                                    "slot_index": 0,
                                    "section": "work_experience",
                                    "subsection": "Test Company",
                                    "text": "Built a test system using Python",
                                    "source": "master_bullets",
                                    "rephrase_generation": 0
                                }
                            ],
                            "hidden_projects": []
                        }
                    )
                    
                    assert response.status_code == 200
                    data = response.get_json()
                    assert "cv_path" in data
                    assert "status" in data
                    assert data["status"] == "success"
    
    def test_queued_jobs_returns_list(self, client):
        """GET /api/jobs/queued returns list of queued jobs."""
        with patch("dashboard.cv_builder_ui.get_db_connection") as mock_conn:
            with patch("dashboard.cv_builder_ui.get_queued_jobs") as mock_queued:
                mock_queued.return_value = [
                    {"id": 1, "title": "Job 1", "company": "Co 1", "fit_score": 0.9},
                    {"id": 2, "title": "Job 2", "company": "Co 2", "fit_score": 0.8}
                ]
                mock_conn.return_value.close = MagicMock()
                
                response = client.get("/api/jobs/queued")
                
                assert response.status_code == 200
                data = response.get_json()
                assert "jobs" in data
                assert len(data["jobs"]) == 2
    
    def test_add_to_bank_appends_bullet(self, client, tmp_path):
        """POST /api/bullets/add-to-bank appends to master_bullets.md."""
        with patch("dashboard.cv_builder_ui.approve_bullet_for_bank") as mock_approve:
            mock_approve.return_value = True
            
            response = client.post(
                "/api/bullets/add-to-bank",
                json={
                    "text": "New bullet text here",
                    "section": "work_experience",
                    "subsection": "Test Company",
                    "tags": ["new", "bullet"],
                    "role_families": ["general-swe"]
                }
            )
            
            assert response.status_code == 200
            data = response.get_json()
            assert data["status"] == "added"
    
    def test_add_to_bank_duplicate_returns_duplicate(self, client):
        """POST /api/bullets/add-to-bank returns duplicate status for existing bullet."""
        with patch("dashboard.cv_builder_ui.approve_bullet_for_bank") as mock_approve:
            mock_approve.return_value = False
            
            response = client.post(
                "/api/bullets/add-to-bank",
                json={
                    "text": "Existing bullet text",
                    "section": "work_experience",
                    "subsection": "Test Company",
                    "tags": [],
                    "role_families": []
                }
            )
            
            assert response.status_code == 200
            data = response.get_json()
            assert data["status"] == "duplicate"
    
    def test_add_to_bank_missing_fields_returns_error(self, client):
        """POST /api/bullets/add-to-bank returns 400 for missing fields."""
        response = client.post(
            "/api/bullets/add-to-bank",
            json={
                "text": "Missing section and subsection"
            }
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data


class TestDownload:
    """Test CV download functionality."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        with patch("psycopg2.connect"):
            with patch.dict("os.environ", {"DATABASE_URL": "postgresql://test@localhost/test"}):
                from dashboard import cv_builder_ui
                cv_builder_ui.app.config["TESTING"] = True
                with cv_builder_ui.app.test_client() as client:
                    yield client
    
    def test_download_cv_returns_docx(self, client, sample_job, tmp_path):
        """GET /api/cv/<job_id>/download returns DOCX file."""
        from dashboard import cv_builder_ui
        
        # Create a test output file
        cv_builder_ui.OUTPUT_DIR = tmp_path
        output_file = tmp_path / "cv_1_Test_Corp.docx"
        output_file.write_bytes(b"PK\x03\x04test docx content")  # Minimal ZIP header
        
        with patch("dashboard.cv_builder_ui.get_db_connection") as mock_conn:
            with patch("dashboard.cv_builder_ui.get_job_by_id") as mock_get_job:
                mock_get_job.return_value = sample_job
                mock_conn.return_value.close = MagicMock()
                
                response = client.get("/api/cv/1/download")
                
                assert response.status_code == 200
                assert response.content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    
    def test_download_cv_not_generated(self, client, sample_job, tmp_path):
        """GET /api/cv/<job_id>/download returns 404 when CV not yet generated."""
        from dashboard import cv_builder_ui
        cv_builder_ui.OUTPUT_DIR = tmp_path  # Empty dir
        
        with patch("dashboard.cv_builder_ui.get_db_connection") as mock_conn:
            with patch("dashboard.cv_builder_ui.get_job_by_id") as mock_get_job:
                mock_get_job.return_value = sample_job
                mock_conn.return_value.close = MagicMock()
                
                response = client.get("/api/cv/1/download")
                
                assert response.status_code == 404


class TestHTMLTemplate:
    """Test the HTML template structure."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        with patch("psycopg2.connect"):
            with patch.dict("os.environ", {"DATABASE_URL": "postgresql://test@localhost/test"}):
                from dashboard import cv_builder_ui
                cv_builder_ui.app.config["TESTING"] = True
                with cv_builder_ui.app.test_client() as client:
                    yield client
    
    def test_template_has_three_panels(self, client):
        """Template has left, center, and right panels."""
        response = client.get("/build/1")
        html = response.data.decode("utf-8")
        
        assert "left-panel" in html
        assert "center-panel" in html
        assert "right-panel" in html
    
    def test_template_has_dark_theme(self, client):
        """Template uses dark theme colors."""
        response = client.get("/build/1")
        html = response.data.decode("utf-8")
        
        # Check for GitHub dark colors
        assert "#0d1117" in html  # Primary bg
        assert "#00d4ff" in html  # Accent cyan
    
    def test_template_has_required_sections(self, client):
        """Template has all required UI sections."""
        response = client.get("/build/1")
        html = response.data.decode("utf-8")
        
        assert "Job Information" in html
        assert "Bullet Builder" in html
        assert "Live Preview" in html
        assert "Queued Jobs" in html
    
    def test_template_has_generate_button(self, client):
        """Template has Generate CV button."""
        response = client.get("/build/1")
        html = response.data.decode("utf-8")
        
        assert "Generate CV" in html
        assert "generate-btn" in html
