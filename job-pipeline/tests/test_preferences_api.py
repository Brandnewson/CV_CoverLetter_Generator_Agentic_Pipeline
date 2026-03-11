"""Tests for preferences API routes — GET /api/preferences, POST /api/preferences."""
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Import the Flask app
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dashboard.cv_builder_ui import app


@pytest.fixture()
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


SAMPLE_PREFS = {
    "search_terms": ["software engineer", "ML engineer"],
    "role_families": ["ai-startup", "general-swe"],
    "location": "London",
    "country_indeed": "uk",
    "results_wanted": 50,
    "hours_old": 72,
    "salary_floor": 70000,
    "currency": "GBP",
    "excluded_title_keywords": ["senior", "manager"],
    "excluded_desc_keywords": [],
}

SAMPLE_CONFIG_YAML = {
    "search_terms": ["software engineer"],
    "role_families": ["general-swe"],
    "location": "London",
    "country_indeed": "uk",
    "results_wanted": 30,
    "hours_old": 48,
    "salary_floor": 0,
    "currency": "GBP",
    "excluded_title_keywords": [],
    "excluded_desc_keywords": [],
}


# ─── GET /api/preferences ─────────────────────────────────────────────────────

def test_get_preferences_db_row(client) -> None:
    """When a DB row exists, returns it as JSON."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    # cursor() used as context manager
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    # fetchone returns a tuple in column order
    mock_cursor.fetchone.return_value = (
        ["software engineer", "ML engineer"],  # search_terms
        ["ai-startup", "general-swe"],          # role_families
        "London",                               # location
        "uk",                                   # country_indeed
        50,                                     # results_wanted
        72,                                     # hours_old
        70000,                                  # salary_floor
        "GBP",                                  # currency
        ["senior", "manager"],                  # excluded_title_keywords
        [],                                     # excluded_desc_keywords
    )
    with patch("dashboard.cv_builder_ui.get_db_connection", return_value=mock_conn):
        res = client.get("/api/preferences")
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data["location"] == "London"


def test_get_preferences_fallback_to_config_yaml(client) -> None:
    """When no DB row, falls back to config.yaml via read_config_yaml."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_cursor.fetchone.return_value = None  # no DB row
    with (
        patch("dashboard.cv_builder_ui.get_db_connection", return_value=mock_conn),
        patch("dashboard.cv_builder_ui.read_config_yaml", return_value=SAMPLE_CONFIG_YAML),
    ):
        res = client.get("/api/preferences")
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data["results_wanted"] == 30  # from config.yaml fallback


# ─── POST /api/preferences ────────────────────────────────────────────────────

def test_post_preferences_saves_to_db(client) -> None:
    """POST with valid payload returns 200 and 'saved'."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    with (
        patch("dashboard.cv_builder_ui.get_db_connection", return_value=mock_conn),
        patch("dashboard.cv_builder_ui.write_config_yaml") as mock_write,
    ):
        res = client.post(
            "/api/preferences",
            data=json.dumps(SAMPLE_PREFS),
            content_type="application/json",
        )
    assert res.status_code == 200
    data = json.loads(res.data)
    assert data.get("status") == "saved"
    mock_write.assert_called_once()


def test_post_preferences_invalid_payload(client) -> None:
    """POST with unparseable JSON returns a 4xx or 5xx error."""
    res = client.post(
        "/api/preferences",
        data="not-json",
        content_type="application/json",
    )
    # Flask may return 400 for bad JSON; route exception handler returns 500
    assert res.status_code >= 400


def test_post_preferences_config_yaml_updated(client) -> None:
    """After POST, write_config_yaml must be called with the DISCOVERY_CONFIG_PATH."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    fake_path = Path("/fake/config.yaml")
    with (
        patch("dashboard.cv_builder_ui.get_db_connection", return_value=mock_conn),
        patch("dashboard.cv_builder_ui.write_config_yaml") as mock_write,
        patch("dashboard.cv_builder_ui.DISCOVERY_CONFIG_PATH", fake_path),
    ):
        client.post(
            "/api/preferences",
            data=json.dumps(SAMPLE_PREFS),
            content_type="application/json",
        )
    assert mock_write.call_count >= 1
    # extract the path argument however it was passed
    call_args = mock_write.call_args
    positional = call_args.args
    kwargs = call_args.kwargs
    path_arg = kwargs.get("path") or (positional[1] if len(positional) > 1 else None)
    assert path_arg == fake_path
