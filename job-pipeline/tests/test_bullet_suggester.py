"""Tests for right-panel bullet suggestion generator."""

import json

from agent.bullet_suggester import (
    _target_count,
    _is_near_duplicate,
    _score_and_filter_suggestions,
    build_section_request_payload,
    parse_suggestion_response,
)


def test_target_count_bounds_three_to_five():
    assert _target_count(0) == 3
    assert _target_count(1) == 3
    assert _target_count(4) == 3
    assert _target_count(6) == 3
    assert _target_count(8) == 4
    assert _target_count(9) == 4
    assert _target_count(10) == 5
    assert _target_count(20) == 5


def test_build_section_payload_contains_targets():
    payload = build_section_request_payload(
        section="work_experience",
        slots_by_subsection={
            "Jaguar TCS Racing": ["A", "B", "C", "D", "E", "F", "G", "H", "I"],
            "Republic Navy": ["A", "B", "C", "D"],
        },
        stories={"Jaguar TCS Racing": "Built race tooling."},
        uncovered_keywords=["kubernetes", "python"],
        profile_context="Long profile context",
    )

    assert payload["section"] == "work_experience"
    assert payload["uncovered_keywords"] == ["kubernetes", "python"]
    assert len(payload["subsections"]) == 2

    jaguar = next(item for item in payload["subsections"] if item["subsection"] == "Jaguar TCS Racing")
    navy = next(item for item in payload["subsections"] if item["subsection"] == "Republic Navy")

    assert jaguar["existing_slot_count"] == 9
    assert jaguar["target_suggestion_count"] == 4
    assert navy["existing_slot_count"] == 4
    assert navy["target_suggestion_count"] == 3


def test_parse_suggestion_response_filters_invalid_entries():
    raw = {
        "Jaguar TCS Racing": [
            {
                "text": "Built race strategy tooling in Python for live telemetry analysis.",
                "keywords_targeted": ["python", "telemetry"],
            },
            {
                "text": "I am passionate about racing and dynamic environments.",
                "keywords_targeted": ["racing"],
            },
            "Delivered simulator dashboards for tyre-energy insights.",
            123,
        ]
    }

    parsed = parse_suggestion_response(json.dumps(raw))
    assert "Jaguar TCS Racing" in parsed
    assert len(parsed["Jaguar TCS Racing"]) == 2

    first = parsed["Jaguar TCS Racing"][0]
    assert first["char_count"] == len(first["text"])
    assert first["over_hard_limit"] is False
    assert first["keywords_targeted"] == ["python", "telemetry"]


# ---------------------------------------------------------------------------
# Deterministic scoring / dedup / quality gate
# ---------------------------------------------------------------------------

def test_deterministic_scoring_overrides_model_keywords():
    """Model-declared keywords are replaced by deterministic hit detection."""
    suggestions = [
        {
            "text": "Developed real-time telemetry pipelines in Python for race strategy analysis.",
            "keywords_targeted": ["aws", "kubernetes"],  # wrong model keywords
            "char_count": 74,
            "over_soft_limit": False,
            "over_hard_limit": False,
            "warnings": [],
        }
    ]
    keywords_dict = {
        "required_keywords": ["python"],
        "nice_to_have_keywords": ["telemetry", "aws"],
    }
    result = _score_and_filter_suggestions(
        suggestions=suggestions,
        existing_bullets=[],
        keywords_dict=keywords_dict,
    )
    assert len(result) == 1
    # 'python' and 'telemetry' appear in text; 'aws' does NOT.
    assert "python" in result[0]["keywords_targeted"]
    assert "telemetry" in result[0]["keywords_targeted"]
    assert "aws" not in result[0]["keywords_targeted"]


def test_balanced_gate_keeps_top_by_score_when_all_below_threshold():
    """When all bullets score below the threshold, top-_MIN_KEEP are kept."""
    suggestions = [
        {
            "text": "Attended a meeting and took notes on the discussion.",
            "keywords_targeted": [],
            "char_count": 51,
            "over_soft_limit": False,
            "over_hard_limit": False,
            "warnings": [],
        },
        {
            "text": "Wrote a brief summary document for the team.",
            "keywords_targeted": [],
            "char_count": 44,
            "over_soft_limit": False,
            "over_hard_limit": False,
            "warnings": [],
        },
        {
            "text": "Created placeholder slides for the quarterly review.",
            "keywords_targeted": [],
            "char_count": 52,
            "over_soft_limit": False,
            "over_hard_limit": False,
            "warnings": [],
        },
    ]
    keywords_dict = {
        "required_keywords": ["machine learning"],
        "nice_to_have_keywords": ["deep learning"],
    }
    result = _score_and_filter_suggestions(
        suggestions=suggestions,
        existing_bullets=[],
        keywords_dict=keywords_dict,
    )
    # Below threshold but we must keep at least _MIN_KEEP (2) bullets.
    assert len(result) >= 2


def test_dedup_removes_near_duplicate_of_existing():
    """Near-duplicate of an existing slot bullet is filtered out."""
    existing = [
        "Designed real-time telemetry systems in Python for strategy tooling.",
    ]
    suggestions = [
        {
            # Very similar to existing — should be filtered
            "text": "Designed real-time telemetry system in Python for strategy tooling.",
            "keywords_targeted": ["python"],
            "char_count": 66,
            "over_soft_limit": False,
            "over_hard_limit": False,
            "warnings": [],
        },
        {
            # Genuinely different — should survive
            "text": "Built CI/CD pipeline to automate race simulation deployments.",
            "keywords_targeted": [],
            "char_count": 59,
            "over_soft_limit": False,
            "over_hard_limit": False,
            "warnings": [],
        },
    ]
    keywords_dict: dict = {}
    result = _score_and_filter_suggestions(
        suggestions=suggestions,
        existing_bullets=existing,
        keywords_dict=keywords_dict,
    )
    texts = [r["text"] for r in result]
    assert "Built CI/CD pipeline to automate race simulation deployments." in texts
    assert not any("Designed real-time telemetry" in t for t in texts)


def test_near_duplicate_detection_exact():
    assert _is_near_duplicate(
        "Developed Python tooling for live telemetry.",
        ["Developed Python tooling for live telemetry."],
    ) is True


def test_near_duplicate_detection_different():
    assert _is_near_duplicate(
        "Deployed Kubernetes clusters on AWS for production workloads.",
        ["Built CI/CD pipelines using GitHub Actions and Docker containers."],
    ) is False


def test_build_section_payload_includes_priority_keywords():
    """priority_keywords should be uncovered first, then required, deduplicated."""
    payload = build_section_request_payload(
        section="work_experience",
        slots_by_subsection={"Acme Corp": ["A", "B"]},
        stories={},
        uncovered_keywords=["kubernetes", "docker"],
        profile_context="Short profile",
        required_keywords=["python", "kubernetes"],  # kubernetes already in uncovered
    )
    pk = payload["priority_keywords"]
    assert pk.index("kubernetes") < pk.index("python"), "uncovered should precede required"
    # no duplicates
    assert len(pk) == len(set(pk))
