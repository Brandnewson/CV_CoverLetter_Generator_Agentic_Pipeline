"""Condense confirmed CV sections into the user's profile markdown files.

Called after the user confirms section layout in the Profile UI.
All writes are ADDITIVE — existing content is never overwritten.
Each new block is prefixed with a timestamped comment so additions are
traceable and re-runnable.

Processing per section type
───────────────────────────
work_experience  → Claude Haiku extracts clean technical facts
                   → appended to experience.md
                   → bullet-like lines also fed to approve_bullet_for_bank()

technical_projects → bullet-like lines → approve_bullet_for_bank()
                     → raw text appended to stories.md

education / skills / summary → raw text appended to experience.md

cover_letter     → saved as a separate markdown file under cover_letters/

story / project_context → raw text appended to stories.md (no LLM step;
                           preserve the user's voice)
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent.config import get_claude_model
from agent.story_drafter import approve_bullet_for_bank


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BULLET_LINE_RE = re.compile(
    r"^[-•*–]\s+.{20,}",  # starts with a bullet character, at min 20 chars
)
_ACTION_VERB_RE = re.compile(
    r"^(Built|Developed|Designed|Implemented|Led|Managed|Created|Delivered|"
    r"Optimised|Automated|Deployed|Architected|Authored|Collaborated|Improved|"
    r"Reduced|Increased|Migrated|Integrated|Analysed|Researched|Mentored|"
    r"Streamlined|Launched|Scaled|Engineered|Shipped|Refactored)\b",
    re.IGNORECASE,
)

_TIMESTAMP_FMT = "%Y-%m-%d %H:%M UTC"


def _timestamp_comment() -> str:
    return f"<!-- ingested {datetime.now(timezone.utc).strftime(_TIMESTAMP_FMT)} -->"


def _looks_like_bullet(line: str) -> bool:
    stripped = line.strip()
    return bool(_BULLET_LINE_RE.match(stripped) or _ACTION_VERB_RE.match(stripped))


def _append_to_file(path: Path, header: str, content: str) -> None:
    """Append *content* with a section header and timestamp comment."""
    path.parent.mkdir(parents=True, exist_ok=True)
    block = f"\n\n{_timestamp_comment()}\n## {header}\n\n{content.strip()}\n"
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(block)


def _log_api_usage(
    operation: str,
    input_tokens: int,
    output_tokens: int,
    log_path: Path,
    user_id: int = 1,
) -> None:
    import json

    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "operation": operation,
        "model": "claude-haiku-4-5",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


# ---------------------------------------------------------------------------
# Condensation LLM call
# ---------------------------------------------------------------------------

_CONDENSE_SYSTEM = """You are a precise technical CV analyser.
Given raw CV text for a role at a company, extract the key technical facts as
concise prose paragraphs. Focus on:
- Technologies and tools used
- What was built or achieved (quantified where possible)
- Scale, impact, method
Write in third-person present perfect (e.g. "Built X using Y"). British English.
Output plain text paragraphs only — no headings, no bullet points, no markdown."""


def _condense_work_experience(
    raw_text: str,
    heading: str,
    client,
    log_path: Path,
    user_id: int = 1,
) -> str:
    """Call Claude Haiku to condense raw work-experience text into technical facts."""
    prompt = (
        f"CV section heading: {heading}\n\n"
        f"Raw text:\n{raw_text[:4000]}\n\n"
        "Condense this into factual technical prose paragraphs."
    )
    response = client.messages.create(
        model=get_claude_model(),
        max_tokens=600,
        system=_CONDENSE_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    _log_api_usage(
        "condense_cv_section",
        response.usage.input_tokens,
        response.usage.output_tokens,
        log_path,
        user_id,
    )
    return response.content[0].text.strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def condense_confirmed_sections(
    *,
    sections: list[dict[str, Any]],
    source_filename: str,
    experience_path: Path,
    stories_path: Path,
    bullet_bank_path: Path,
    cover_letters_dir: Path,
    log_path: Path,
    client,
    user_id: int = 1,
) -> dict[str, list[str]]:
    """Process confirmed sections and update profile markdown files.

    Args:
        sections: List of ``{heading, raw_text, confirmed_type}`` dicts from UI.
        source_filename: Original upload filename (for attribution).
        experience_path: Path to ``experience.md``.
        stories_path: Path to ``stories.md``.
        bullet_bank_path: Path to ``master_bullets.md``.
        cover_letters_dir: Directory for individual cover letter .md files.
        log_path: Path to ``logs/api_usage.jsonl``.
        client: anthropic.Anthropic() instance.
        user_id: Integer user ID for logging.

    Returns:
        ``{filename: [change description, ...]}`` mapping of updated files.
    """
    updated: dict[str, list[str]] = {}

    def _note(path: Path, msg: str) -> None:
        key = path.name
        updated.setdefault(key, []).append(msg)

    for section in sections:
        heading: str = section.get("heading", "Section")
        raw_text: str = section.get("raw_text", "").strip()
        stype: str = section.get("confirmed_type", "other")

        if not raw_text:
            continue

        # ── work experience ──────────────────────────────────────────────
        if stype == "work_experience":
            condensed = _condense_work_experience(
                raw_text, heading, client, log_path, user_id
            )
            _append_to_file(
                experience_path,
                f"{heading} (from {source_filename})",
                condensed,
            )
            _note(experience_path, f"Appended condensed work experience for '{heading}'")

            # Also extract bullet-like lines for the bank
            added_count = 0
            for line in raw_text.splitlines():
                line = line.strip()
                if _looks_like_bullet(line) and 30 <= len(line) <= 160:
                    clean = re.sub(r"^[-•*–]\s+", "", line)
                    ok = approve_bullet_for_bank(
                        bullet_text=clean,
                        section="work_experience",
                        subsection=heading,
                        tags=[],
                        role_families=[],
                        bank_path=bullet_bank_path,
                    )
                    if ok:
                        added_count += 1
            if added_count:
                _note(bullet_bank_path, f"Added {added_count} bullets from '{heading}'")

        # ── technical projects ───────────────────────────────────────────
        elif stype == "technical_projects":
            _append_to_file(
                stories_path,
                f"{heading} (from {source_filename})",
                raw_text,
            )
            _note(stories_path, f"Appended raw project text for '{heading}'")

            added_count = 0
            for line in raw_text.splitlines():
                line = line.strip()
                if _looks_like_bullet(line) and 30 <= len(line) <= 160:
                    clean = re.sub(r"^[-•*–]\s+", "", line)
                    ok = approve_bullet_for_bank(
                        bullet_text=clean,
                        section="technical_projects",
                        subsection=heading,
                        tags=[],
                        role_families=[],
                        bank_path=bullet_bank_path,
                    )
                    if ok:
                        added_count += 1
            if added_count:
                _note(bullet_bank_path, f"Added {added_count} project bullets from '{heading}'")

        # ── education / skills / summary ─────────────────────────────────
        elif stype in ("education", "skills", "summary"):
            _append_to_file(
                experience_path,
                f"{heading} (from {source_filename})",
                raw_text,
            )
            _note(experience_path, f"Appended {stype} section for '{heading}'")

        # ── cover letter ─────────────────────────────────────────────────
        elif stype == "cover_letter":
            cover_letters_dir.mkdir(parents=True, exist_ok=True)
            stem = Path(source_filename).stem
            out_path = cover_letters_dir / f"{stem}.md"
            out_path.write_text(
                f"# Cover Letter — {source_filename}\n\n"
                f"{_timestamp_comment()}\n\n{raw_text}\n",
                encoding="utf-8",
            )
            _note(out_path, "Saved cover letter")

        # ── story / project_context / other ─────────────────────────────
        else:
            _append_to_file(
                stories_path,
                f"{heading} (from {source_filename})",
                raw_text,
            )
            _note(stories_path, f"Appended '{heading}' as story context")

    return updated
