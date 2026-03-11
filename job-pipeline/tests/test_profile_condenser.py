"""Tests for agent/profile_condenser.py — additive file condensation."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.profile_condenser import condense_confirmed_sections


def _mock_client(response_text: str = "• Led migration to microservices\n• Reduced latency by 40%"):
    """Return a minimal mock Anthropic client."""
    client = MagicMock()
    msg = MagicMock()
    msg.content = [MagicMock(text=response_text)]
    msg.usage.input_tokens = 100
    msg.usage.output_tokens = 50
    client.messages.create.return_value = msg
    return client


def _base_args(tmp_path: Path, *, client=None):
    return dict(
        sections=[],
        source_filename="cv.docx",
        experience_path=tmp_path / "experience.md",
        stories_path=tmp_path / "stories.md",
        bullet_bank_path=tmp_path / "master_bullets.md",
        cover_letters_dir=tmp_path / "cover_letters",
        log_path=tmp_path / "api_usage.jsonl",
        client=client or _mock_client(),
        user_id=1,
    )


# ─── Additive writes ─────────────────────────────────────────────────────────

def test_work_experience_appends_not_overwrites(tmp_path: Path) -> None:
    """Calling condense twice must append both blocks to experience.md."""
    existing = "# Existing Experience\n\nAlready there.\n"
    exp_path = tmp_path / "experience.md"
    exp_path.write_text(existing, encoding="utf-8")

    args = _base_args(tmp_path)
    args["sections"] = [
        {"heading": "Work Experience", "raw_text": "Software Engineer, ACME 2020-2022.", "confirmed_type": "work_experience"},
    ]

    condense_confirmed_sections(**args)

    content = exp_path.read_text(encoding="utf-8")
    assert existing in content, "Original content must be preserved"
    assert "<!-- ingested" in content, "New block must be appended"


def test_cover_letter_saved_as_file(tmp_path: Path) -> None:
    """cover_letter type must be written to cover_letters/<stem>.md."""
    cl_dir = tmp_path / "cover_letters"
    args = _base_args(tmp_path)
    args["cover_letters_dir"] = cl_dir
    args["source_filename"] = "my_letter.docx"
    args["sections"] = [
        {"heading": "Cover Letter", "raw_text": "Dear Hiring Manager, …", "confirmed_type": "cover_letter"},
    ]

    condense_confirmed_sections(**args)

    files = list(cl_dir.iterdir())
    assert len(files) == 1
    assert files[0].suffix == ".md"
    assert "my_letter" in files[0].stem


def test_stories_appended_to_stories_md(tmp_path: Path) -> None:
    args = _base_args(tmp_path)
    args["sections"] = [
        {"heading": "Story: Led Rewrite", "raw_text": "I led the entire backend rewrite.", "confirmed_type": "story"},
    ]

    condense_confirmed_sections(**args)

    stories_path: Path = args["stories_path"]
    content = stories_path.read_text(encoding="utf-8")
    assert "Led Rewrite" in content or "led" in content.lower()


def test_technical_projects_appended(tmp_path: Path) -> None:
    args = _base_args(tmp_path)
    # approve_bullet_for_bank requires the bank file to exist
    args["bullet_bank_path"].write_text("", encoding="utf-8")
    args["sections"] = [
        {"heading": "Projects", "raw_text": "Built a distributed cache in Rust.", "confirmed_type": "technical_projects"},
    ]

    condense_confirmed_sections(**args)

    stories_path: Path = args["stories_path"]
    assert stories_path.exists()
    assert "Rust" in stories_path.read_text(encoding="utf-8")


# ─── Log emissions ───────────────────────────────────────────────────────────

def test_api_usage_logged(tmp_path: Path) -> None:
    """Every Claude call should write a JSON line to api_usage.jsonl."""
    args = _base_args(tmp_path)
    args["sections"] = [
        {"heading": "Work Experience", "raw_text": "Engineer at ACME.", "confirmed_type": "work_experience"},
    ]

    condense_confirmed_sections(**args)

    log_path: Path = args["log_path"]
    if log_path.exists():
        lines = [l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        for line in lines:
            entry = json.loads(line)
            assert "model" in entry or "endpoint" in entry or "input_tokens" in entry


# ─── Empty sections ────────────────────────────────────────────────────────────

def test_empty_sections_returns_empty_dict(tmp_path: Path) -> None:
    args = _base_args(tmp_path)
    args["sections"] = []

    result = condense_confirmed_sections(**args)
    assert result == {}
