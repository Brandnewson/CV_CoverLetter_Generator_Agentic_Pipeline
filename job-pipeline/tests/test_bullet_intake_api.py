"""Tests for bullet intake and plan refresh APIs."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import dashboard.cv_builder_ui as ui


@pytest.fixture()
def client():
    ui.app.config["TESTING"] = True
    with ui.app.test_client() as c:
        yield c


def test_add_user_bullets_scores_and_saves(client):
    job_id = 42
    ui.active_plans[job_id] = SimpleNamespace(role_family="general-swe", user_id=1)
    ui.active_keywords[job_id] = {
        "required_keywords": ["python", "sql"],
        "nice_to_have_keywords": ["docker"],
        "technical_skills": ["python"],
        "soft_skills": [],
        "domain_keywords": [],
        "seniority_signals": [],
    }

    try:
        mock_conn = MagicMock()
        with (
            patch("dashboard.cv_builder_ui.get_db_connection", return_value=mock_conn),
            patch("dashboard.cv_builder_ui.get_job_by_id", return_value={"id": job_id, "title": "SWE", "description": "", "job_description_raw": ""}),
            patch("dashboard.cv_builder_ui.approve_bullet_for_bank", side_effect=[True, False]),
        ):
            res = client.post(
                "/api/bullets/add",
                json={
                    "job_id": job_id,
                    "bullets": [
                        {
                            "text": "Built Python services and optimised SQL queries for internal tooling.",
                            "section": "work_experience",
                            "subsection": "Acme",
                        },
                        {
                            "text": "Built Python services and optimised SQL queries for internal tooling.",
                            "section": "work_experience",
                            "subsection": "Acme",
                        },
                    ],
                },
            )

        assert res.status_code == 200
        payload = res.get_json()
        assert len(payload["saved"]) == 2
        assert payload["saved"][0]["relevance_score"] > 0
        assert payload["saved"][0]["was_new"] is True
        assert payload["saved"][1]["was_new"] is False
    finally:
        ui.active_plans.pop(job_id, None)
        ui.active_keywords.pop(job_id, None)


def test_refresh_plan_rebuilds_cache_and_clears_suggestions(client):
    job_id = 99
    ui.active_keywords[job_id] = {
        "required_keywords": ["python"],
        "nice_to_have_keywords": [],
        "technical_skills": [],
        "soft_skills": [],
        "domain_keywords": [],
        "seniority_signals": [],
    }
    ui.active_suggestions[job_id] = {"stale": True}

    class FakePlan:
        def model_dump(self):
            return {
                "job_id": job_id,
                "user_id": 1,
                "job_title": "Engineer",
                "company": "Acme",
                "role_family": "general-swe",
                "seniority_level": "mid",
                "required_keywords": ["python"],
                "nice_to_have_keywords": [],
                "technical_keywords": [],
                "work_experience_slots": [],
                "technical_project_slots": [],
                "projects_to_hide": [],
                "keyword_coverage": {},
                "uncovered_keywords": [],
                "keyword_bucket_coverage": {"technologies": [], "skills": [], "abilities": []},
            }

    fake_job = {
        "id": job_id,
        "title": "Software Engineer",
        "company": "Acme",
        "description": "Python backend",
        "job_description_raw": "Python backend",
    }

    mock_conn = MagicMock()

    try:
        with (
            patch("dashboard.cv_builder_ui.get_db_connection", return_value=mock_conn),
            patch("dashboard.cv_builder_ui.get_job_by_id", return_value=fake_job),
            patch("dashboard.cv_builder_ui.classify_role_family", return_value="general-swe"),
            patch("dashboard.cv_builder_ui.classify_seniority", return_value="mid"),
            patch("dashboard.cv_builder_ui.load_bullet_bank", return_value=[]),
            patch("dashboard.cv_builder_ui.load_template_map", return_value={}),
            patch("dashboard.cv_builder_ui.build_selection_plan", return_value=FakePlan()),
        ):
            res = client.post(f"/api/plan/{job_id}/refresh")

        assert res.status_code == 200
        assert job_id in ui.active_plans
        assert job_id not in ui.active_suggestions
        payload = res.get_json()
        assert payload["job"]["id"] == job_id
    finally:
        ui.active_plans.pop(job_id, None)
        ui.active_keywords.pop(job_id, None)
        ui.active_suggestions.pop(job_id, None)
