"""Generate new CV bullet suggestions from user profile context and uncovered keywords."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent.config import get_claude_model
from agent.jd_parser import score_bullet_against_keywords
from agent.story_drafter import load_stories
from agent.validators import SOFT_CHAR_LIMIT, HARD_CHAR_LIMIT, validate_bullet_text

# Minimum deterministic keyword score for a suggestion to pass the quality gate.
_SCORE_THRESHOLD = 0.15
# Always keep at least this many suggestions per subsection (even if below threshold).
_MIN_KEEP = 2
# Jaccard similarity threshold above which a candidate is considered a near-duplicate.
_DEDUP_THRESHOLD = 0.60


SUGGESTION_SYSTEM_PROMPT = """
You are a CV bullet generator focused on creating NEW, ATS-friendly bullets.

Rules:
- Output valid JSON only.
- Use British English.
- Use facts from provided profile context only; do not invent tools, metrics, or achievements.
- Start bullets with strong action verbs.
- Keep each bullet concise and <= 120 characters.
- Prioritise uncovered keywords when naturally supported by the context.
- Avoid these words/phrases: passionate, leveraged, utilised, spearheaded, fast-paced, dynamic.
- Generate NEW lines, not minor rewrites of provided existing bullets.
""".strip()


def _log_api_usage(
    operation: str,
    input_tokens: int,
    output_tokens: int,
    user_id: int = 1
) -> None:
    """Log API usage to logs/api_usage.jsonl."""
    log_path = Path(__file__).parent.parent / "logs" / "api_usage.jsonl"
    log_path.parent.mkdir(exist_ok=True)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "operation": operation,
        "model": "claude-haiku-4-5",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _strip_markdown_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
    return cleaned.strip()


def _compact_text(value: str, max_chars: int) -> str:
    value = (value or "").strip()
    if len(value) <= max_chars:
        return value
    return value[:max_chars].rstrip() + "…"


def _normalize_text(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _jaccard_similarity(a: str, b: str) -> float:
    set_a = set(a.split())
    set_b = set(b.split())
    if not set_a and not set_b:
        return 1.0
    union = set_a | set_b
    return len(set_a & set_b) / len(union) if union else 0.0


def _is_near_duplicate(candidate: str, existing: list[str]) -> bool:
    """Return True if candidate is too similar (≥ 60% Jaccard) to any existing bullet."""
    norm = _normalize_text(candidate)
    return any(
        _jaccard_similarity(norm, _normalize_text(ex)) >= _DEDUP_THRESHOLD
        for ex in existing
    )


def _score_and_filter_suggestions(
    suggestions: list[dict[str, Any]],
    existing_bullets: list[str],
    keywords_dict: dict[str, list[str]],
) -> list[dict[str, Any]]:
    """Post-process suggestions after LLM parse:

    1. Recompute ``keywords_targeted`` deterministically (alias-aware).
    2. Remove near-duplicates of existing slot bullets.
    3. Apply balanced quality gate: keep all above threshold; if fewer than
       ``_MIN_KEEP`` survive, fill up to ``_MIN_KEEP`` with the highest-scored
       candidates regardless of threshold.
    """
    # 1. deterministic scoring
    scored: list[tuple[float, dict[str, Any]]] = []
    for item in suggestions:
        score, matched = score_bullet_against_keywords(item["text"], keywords_dict)
        updated = dict(item)
        updated["keywords_targeted"] = matched
        scored.append((score, updated))

    # 2. novelty filter
    scored = [
        (s, item) for s, item in scored
        if not _is_near_duplicate(item["text"], existing_bullets)
    ]

    # 3. balanced quality gate
    above = [(s, item) for s, item in scored if s >= _SCORE_THRESHOLD]
    if len(above) >= _MIN_KEEP:
        return [item for _, item in above]

    # below threshold — return top-N by score so the panel is never empty
    top = sorted(scored, key=lambda x: x[0], reverse=True)
    return [item for _, item in top[:max(_MIN_KEEP, len(above))]]


def _target_count(existing_count: int) -> int:
    """3-5 suggestions per subsection, biased by existing slot count."""
    if existing_count <= 0:
        return 3
    return max(3, min(5, round(existing_count / 2)))


def build_section_request_payload(
    section: str,
    slots_by_subsection: dict[str, list[str]],
    stories: dict[str, str],
    uncovered_keywords: list[str],
    profile_context: str,
    required_keywords: list[str] | None = None,
) -> dict[str, Any]:
    payload_subsections: list[dict[str, Any]] = []

    for subsection, existing_bullets in slots_by_subsection.items():
        target = _target_count(len(existing_bullets))
        story = stories.get(subsection, "")
        payload_subsections.append(
            {
                "subsection": subsection,
                "existing_slot_count": len(existing_bullets),
                "target_suggestion_count": target,
                "existing_bullets": existing_bullets,
                "story_excerpt": _compact_text(story, 1800),
            }
        )

    # Uncovered keywords come first (highest priority), then required.
    priority_keywords = list(dict.fromkeys(
        (uncovered_keywords or [])[:12] + (required_keywords or [])[:12]
    ))[:20]

    return {
        "section": section,
        "priority_keywords": priority_keywords,
        "uncovered_keywords": uncovered_keywords[:20],
        "required_keywords": (required_keywords or [])[:20],
        "profile_context": _compact_text(profile_context, 2200),
        "subsections": payload_subsections,
    }


def parse_suggestion_response(response_text: str) -> dict[str, list[dict[str, Any]]]:
    """Parse model JSON into {subsection: [suggestion,...]} safely."""
    cleaned = _strip_markdown_fences(response_text)
    parsed = json.loads(cleaned)

    if not isinstance(parsed, dict):
        raise ValueError("Suggestion response is not a JSON object")

    output: dict[str, list[dict[str, Any]]] = {}
    for subsection, suggestions in parsed.items():
        if not isinstance(subsection, str):
            continue
        if not isinstance(suggestions, list):
            continue
        items: list[dict[str, Any]] = []
        for suggestion in suggestions:
            if isinstance(suggestion, str):
                text = suggestion.strip()
                targeted = []
            elif isinstance(suggestion, dict):
                text = str(suggestion.get("text", "")).strip()
                targeted = suggestion.get("keywords_targeted", [])
                if not isinstance(targeted, list):
                    targeted = []
                targeted = [str(item).strip().lower() for item in targeted if str(item).strip()]
            else:
                continue

            if not text:
                continue

            is_valid, _, warnings = validate_bullet_text(text)
            if not is_valid:
                continue

            items.append(
                {
                    "text": text,
                    "keywords_targeted": list(dict.fromkeys(targeted)),
                    "char_count": len(text),
                    "over_soft_limit": len(text) > SOFT_CHAR_LIMIT,
                    "over_hard_limit": len(text) > HARD_CHAR_LIMIT,
                    "warnings": warnings,
                }
            )

        output[subsection] = items

    return output


def generate_suggestions_for_section(
    *,
    section: str,
    slots_by_subsection: dict[str, list[str]],
    uncovered_keywords: list[str],
    stories_path: Path,
    profile_context: str,
    client,
    required_keywords: list[str] | None = None,
    user_id: int = 1,
) -> list[dict[str, Any]]:
    """Generate 3-5 suggestion bullets per subsection in one model call for the whole section."""
    if not slots_by_subsection:
        return []

    stories = load_stories(stories_path)
    request_payload = build_section_request_payload(
        section=section,
        slots_by_subsection=slots_by_subsection,
        stories=stories,
        uncovered_keywords=uncovered_keywords,
        required_keywords=required_keywords,
        profile_context=profile_context,
    )

    user_prompt = (
        "Generate new bullet suggestions for this CV section.\n"
        "Return JSON object keyed by subsection name.\n"
        "Each subsection value must be a list of objects with keys: text, keywords_targeted.\n"
        "Prioritise the keywords listed under 'priority_keywords' first. "
        "Generate genuinely NEW lines using facts from story_excerpt and profile_context — "
        "do NOT paraphrase the existing_bullets.\n"
        "Respect each subsection's target_suggestion_count.\n\n"
        f"{json.dumps(request_payload, ensure_ascii=False)}"
    )

    response = client.messages.create(
        model=get_claude_model(),
        max_tokens=2200,
        system=SUGGESTION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    _log_api_usage(
        operation="generate_suggestions",
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        user_id=user_id,
    )

    parsed = parse_suggestion_response(response.content[0].text)

    # Build keywords dict for deterministic scoring (required > uncovered as nice-to-have).
    keywords_dict: dict[str, list[str]] = {
        "required_keywords": required_keywords or [],
        "nice_to_have_keywords": uncovered_keywords or [],
    }

    section_suggestions: list[dict[str, Any]] = []
    for subsection, existing_bullets in slots_by_subsection.items():
        target_count = _target_count(len(existing_bullets))
        raw_suggestions = parsed.get(subsection, [])

        filtered = _score_and_filter_suggestions(
            suggestions=raw_suggestions,
            existing_bullets=existing_bullets,
            keywords_dict=keywords_dict,
        )
        section_suggestions.append(
            {
                "subsection": subsection,
                "existing_slot_count": len(existing_bullets),
                "target_suggestion_count": target_count,
                "suggestions": filtered[:target_count],
            }
        )

    return section_suggestions
