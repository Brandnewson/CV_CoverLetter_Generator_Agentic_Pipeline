"""Tests for agent/cv_parser.py — heuristic section extraction."""
import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.cv_parser import (
    _classify_heading,
    extract_docx_sections,
    sections_to_json,
)


# ─── Heading classifier ───────────────────────────────────────────────────────

@pytest.mark.parametrize("text,expected_type", [
    ("Work Experience", "work_experience"),
    ("PROFESSIONAL EXPERIENCE", "work_experience"),
    ("Employment History", "work_experience"),
    ("Technical Projects", "technical_projects"),
    ("Projects", "technical_projects"),
    ("Education", "education"),
    ("TECHNICAL SKILLS", "skills"),
    ("Skills & Technologies", "skills"),
    ("Professional Summary", "summary"),
    ("Cover Letter", "cover_letter"),
    ("Random gibberish heading", "other"),
])
def test_classify_heading(text: str, expected_type: str) -> None:
    detected_type, confidence = _classify_heading(text)
    assert detected_type == expected_type, f"'{text}' → expected {expected_type}, got {detected_type}"
    assert 0.0 < confidence <= 1.0


def test_classify_heading_fullmatch_confidence() -> None:
    """Full-match patterns should score higher than substring matches."""
    _, full_conf = _classify_heading("Work Experience")
    _, search_conf = _classify_heading("My Work Experience Section")
    # Both may be the same type but full match should be >= search
    assert full_conf >= search_conf


# ─── DOCX extraction ─────────────────────────────────────────────────────────

def _make_paragraph(text: str, style_name: str = "Normal", bold: bool = False):
    """Create a minimal paragraph mock for python-docx."""
    para = MagicMock()
    para.text = text
    para.style.name = style_name
    run = MagicMock()
    run.bold = bold
    para.runs = [run] if text else []
    return para


def test_extract_docx_heading_style(tmp_path: Path) -> None:
    """Paragraphs with Heading 1/2 style are detected as section headings."""
    paragraphs = [
        _make_paragraph("Work Experience", style_name="Heading 1"),
        _make_paragraph("Worked at ACME Corp as SWE, 2020-2022."),
        _make_paragraph("Education", style_name="Heading 2"),
        _make_paragraph("BSc Computer Science, University of Bath, 2020."),
    ]

    dummy_path = tmp_path / "cv.docx"
    dummy_path.write_bytes(b"PK\x03\x04" + b"\x00" * 100)  # fake docx bytes

    with patch("docx.Document") as mock_doc:
        mock_doc.return_value.paragraphs = paragraphs
        sections = extract_docx_sections(dummy_path)

    types = [s.detected_type for s in sections]
    assert "work_experience" in types
    assert "education" in types


def test_extract_docx_bold_heading(tmp_path: Path) -> None:
    """Bold ALL-CAPS short paragraphs are treated as headings."""
    paragraphs = [
        _make_paragraph("SKILLS", style_name="Normal", bold=True),
        _make_paragraph("Python, TypeScript, SQL"),
    ]

    dummy_path = tmp_path / "cv.docx"
    dummy_path.write_bytes(b"PK\x03\x04" + b"\x00" * 100)

    with patch("docx.Document") as mock_doc:
        mock_doc.return_value.paragraphs = paragraphs
        sections = extract_docx_sections(dummy_path)

    assert any(s.detected_type == "skills" for s in sections)


def test_extract_docx_no_headings_returns_other(tmp_path: Path) -> None:
    """If no headings are detected, the parser groups all text under an implicit section.

    The important guarantee is that:
    - At least one section is returned (no crash, no empty list)
    - All body text is preserved inside section raw_text
    """
    paragraphs = [
        _make_paragraph("I worked at ACME."),
        _make_paragraph("I also studied at Bath."),
    ]

    dummy_path = tmp_path / "cv.docx"
    dummy_path.write_bytes(b"PK\x03\x04" + b"\x00" * 100)

    with patch("docx.Document") as mock_doc:
        mock_doc.return_value.paragraphs = paragraphs
        sections = extract_docx_sections(dummy_path)

    assert len(sections) >= 1
    all_text = " ".join(s.raw_text for s in sections)
    assert "ACME" in all_text
    assert "Bath" in all_text


# ─── sections_to_json ─────────────────────────────────────────────────────────

def test_sections_to_json_serializable(tmp_path: Path) -> None:
    """sections_to_json produces plain dicts with no dataclass instances."""
    import json
    paragraphs = [
        _make_paragraph("Work Experience", style_name="Heading 1"),
        _make_paragraph("Some job."),
    ]
    dummy_path = tmp_path / "cv.docx"
    dummy_path.write_bytes(b"PK\x03\x04" + b"\x00" * 100)

    with patch("docx.Document") as mock_doc:
        mock_doc.return_value.paragraphs = paragraphs
        sections = extract_docx_sections(dummy_path)

    result = sections_to_json(sections)
    assert isinstance(result, list)
    # must be JSON-serialisable
    json.dumps(result)
    # each element has required keys
    for item in result:
        assert {"heading", "raw_text", "detected_type", "confidence", "warnings"}.issubset(item.keys())
