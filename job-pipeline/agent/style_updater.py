"""Style updater - updates CLAUDE.md with approved examples and distilled rules."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from agent.config import get_claude_model


STYLE_DISTILLATION_PROMPT = """Based on these approved CV bullets, describe in 5 bullet points the writing patterns this person prefers.

Be specific about:
- Verb choices (past/present tense, specific action verbs used)
- Sentence structure (where technology names appear, how achievements are framed)
- Keyword placement (beginning, middle, end)
- Length preference (typical character counts)
- Any patterns in quantification or metric usage

Approved bullets:
{bullets}

Output exactly 5 bullet points describing the writing style patterns. Start each with "- "."""


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
        "output_tokens": output_tokens
    }
    
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def collect_approved_bullets(
    job_id: int,
    conn,
    user_id: int = 1
) -> list[dict]:
    """
    Query cv_feedback for was_approved=TRUE for this job_id and user_id.
    Return list of {text, section, subsection, role_family, rephrase_generation}.
    """
    cursor = conn.cursor()
    
    # Join with cv_sessions to get role_family
    cursor.execute("""
        SELECT 
            cf.final_text as text,
            cf.slot_section as section,
            cf.slot_subsection as subsection,
            cs.role_family,
            cf.rephrase_generation
        FROM cv_feedback cf
        JOIN cv_sessions cs ON cf.session_id = cs.id
        WHERE cf.job_id = %s
          AND cf.user_id = %s
          AND cf.was_approved = TRUE
          AND cf.final_text IS NOT NULL
        ORDER BY cf.created_at DESC
    """, (job_id, user_id))
    
    rows = cursor.fetchall()
    
    return [
        {
            "text": row[0],
            "section": row[1],
            "subsection": row[2],
            "role_family": row[3],
            "rephrase_generation": row[4]
        }
        for row in rows
    ]


def collect_all_historical_bullets(
    conn,
    user_id: int = 1,
    role_family: str = None
) -> list[dict]:
    """
    Query all historical approved bullets for a user, optionally filtered by role_family.
    Returns list of {text, section, subsection, role_family, rephrase_generation}.
    """
    cursor = conn.cursor()
    
    if role_family:
        cursor.execute("""
            SELECT 
                cf.final_text as text,
                cf.slot_section as section,
                cf.slot_subsection as subsection,
                cs.role_family,
                cf.rephrase_generation
            FROM cv_feedback cf
            JOIN cv_sessions cs ON cf.session_id = cs.id
            WHERE cf.user_id = %s
              AND cs.role_family = %s
              AND cf.was_approved = TRUE
              AND cf.final_text IS NOT NULL
            ORDER BY cf.created_at DESC
        """, (user_id, role_family))
    else:
        cursor.execute("""
            SELECT 
                cf.final_text as text,
                cf.slot_section as section,
                cf.slot_subsection as subsection,
                cs.role_family,
                cf.rephrase_generation
            FROM cv_feedback cf
            JOIN cv_sessions cs ON cf.session_id = cs.id
            WHERE cf.user_id = %s
              AND cf.was_approved = TRUE
              AND cf.final_text IS NOT NULL
            ORDER BY cf.created_at DESC
        """, (user_id,))
    
    rows = cursor.fetchall()
    
    return [
        {
            "text": row[0],
            "section": row[1],
            "subsection": row[2],
            "role_family": row[3],
            "rephrase_generation": row[4]
        }
        for row in rows
    ]


def parse_claude_md_section(claude_md_path: Path, section_header: str) -> str:
    """
    Extract content between a ## header and the next ## header.
    Returns empty string if section not found.
    """
    if not claude_md_path.exists():
        return ""
    
    content = claude_md_path.read_text(encoding="utf-8")
    
    # Find section start
    pattern = rf'^## {re.escape(section_header)}\s*$'
    match = re.search(pattern, content, re.MULTILINE)
    
    if not match:
        return ""
    
    start_pos = match.end()
    
    # Find next ## header or end of file
    next_header = re.search(r'^## ', content[start_pos:], re.MULTILINE)
    
    if next_header:
        end_pos = start_pos + next_header.start()
    else:
        end_pos = len(content)
    
    return content[start_pos:end_pos].strip()


def replace_claude_md_section(
    claude_md_path: Path,
    section_header: str,
    new_content: str
) -> None:
    """
    Replace section content in CLAUDE.md. Preserve all other sections.
    Creates file with section if it doesn't exist.
    """
    if not claude_md_path.exists():
        # Create new file with just this section
        claude_md_path.parent.mkdir(parents=True, exist_ok=True)
        claude_md_path.write_text(f"## {section_header}\n{new_content}\n", encoding="utf-8")
        return
    
    content = claude_md_path.read_text(encoding="utf-8")
    
    # Find section start
    pattern = rf'^(## {re.escape(section_header)})\s*$'
    match = re.search(pattern, content, re.MULTILINE)
    
    if not match:
        # Section doesn't exist - append it
        content = content.rstrip() + f"\n\n## {section_header}\n{new_content}\n"
        claude_md_path.write_text(content, encoding="utf-8")
        return
    
    section_start = match.start()
    header_end = match.end()
    
    # Find next ## header or end of file
    next_header = re.search(r'^## ', content[header_end:], re.MULTILINE)
    
    if next_header:
        section_end = header_end + next_header.start()
    else:
        section_end = len(content)
    
    # Replace section content (keep the header)
    new_section = f"## {section_header}\n{new_content}\n"
    content = content[:section_start] + new_section + content[section_end:]
    
    claude_md_path.write_text(content, encoding="utf-8")


def _format_approved_examples(bullets: list[dict], max_examples: int = 5) -> str:
    """Format approved bullets as markdown list."""
    # Take most recent, deduplicate by text
    seen = set()
    unique_bullets = []
    for b in bullets:
        text = b.get("text", "").strip()
        if text and text not in seen:
            seen.add(text)
            unique_bullets.append(text)
            if len(unique_bullets) >= max_examples:
                break
    
    if not unique_bullets:
        return "<!-- AUTO-UPDATED after each session. Do not edit manually. -->\n"
    
    lines = ["<!-- AUTO-UPDATED after each session. Do not edit manually. -->"]
    for text in unique_bullets:
        lines.append(f"- {text}")
    
    return "\n".join(lines)


def distill_style_rules(
    all_bullets: list[dict],
    client,
    user_id: int = 1
) -> str:
    """
    Call Haiku to distill writing style rules from approved bullets.
    Returns the style rules as markdown bullet points.
    """
    if not all_bullets:
        return "<!-- AUTO-UPDATED after each session. Do not edit manually. -->\n<!-- No approved bullets yet -->"
    
    # Format bullets for the prompt
    bullet_texts = [b.get("text", "") for b in all_bullets if b.get("text")]
    if not bullet_texts:
        return "<!-- AUTO-UPDATED after each session. Do not edit manually. -->\n<!-- No approved bullets yet -->"
    
    # Limit to recent 50 bullets for context window
    bullet_texts = bullet_texts[:50]
    bullets_formatted = "\n".join(f"- {text}" for text in bullet_texts)
    
    prompt = STYLE_DISTILLATION_PROMPT.format(bullets=bullets_formatted)
    
    response = client.messages.create(
        model=get_claude_model(),
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )
    
    # Log API usage
    _log_api_usage(
        operation="distill_style_rules",
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        user_id=user_id
    )
    
    style_rules = response.content[0].text.strip()
    
    return f"<!-- AUTO-UPDATED after each session. Do not edit manually. -->\n{style_rules}"


def update_rephrase_prompt(
    style_rules: str,
    user_id: int = 1
) -> None:
    """
    Update the rephrase_prompt.txt with distilled style rules.
    Appends style rules as additional constraints.
    """
    from agent.bullet_rephraser import DEFAULT_REPHRASE_SYSTEM_PROMPT, save_rephrase_prompt
    
    # Extract just the bullet points from style rules (skip the comment)
    rules_lines = [
        line for line in style_rules.split('\n')
        if line.strip() and not line.strip().startswith('<!--')
    ]
    
    if not rules_lines:
        return
    
    # Append style rules to the default prompt
    additional_rules = "\n\nDistilled style preferences (learned from past approvals):\n" + "\n".join(rules_lines)
    
    updated_prompt = DEFAULT_REPHRASE_SYSTEM_PROMPT + additional_rules
    save_rephrase_prompt(updated_prompt, user_id)


def update_claude_md(
    claude_md_path: Path,
    approved_bullets: list[dict],
    all_historical_bullets: list[dict],
    role_family: str,
    client,
    user_id: int = 1
) -> None:
    """
    Updates two sections of CLAUDE.md:
    
    1. Approved Examples ({role_family})
       The 5 most recent approved bullets for this role_family.
       Appended after each session. Older examples rotated out (keep last 5 per family).
    
    2. Distilled Style Rules
       Call Haiku once per session with all historical approved bullets.
       Describes writing patterns the person prefers.
    
    Also updates profile/users/{user_id}/rephrase_prompt.txt by appending
    the distilled rules as additional constraints.
    """
    # Filter bullets by role_family for the examples section
    role_bullets = [b for b in approved_bullets if b.get("role_family") == role_family]
    
    # Get existing examples for this role_family
    section_header = f"Approved Examples ({role_family})"
    existing_content = parse_claude_md_section(claude_md_path, section_header)
    
    # Parse existing examples
    existing_examples = []
    for line in existing_content.split('\n'):
        if line.strip().startswith('- '):
            existing_examples.append({"text": line.strip()[2:]})
    
    # Combine: new bullets first, then existing (for deduplication order)
    combined = role_bullets + existing_examples
    
    # Format and replace the approved examples section
    new_examples_content = _format_approved_examples(combined)
    replace_claude_md_section(claude_md_path, section_header, new_examples_content)
    
    # Distill style rules from ALL historical bullets (not filtered by role_family)
    style_rules = distill_style_rules(all_historical_bullets, client, user_id)
    replace_claude_md_section(claude_md_path, "Distilled Style Rules", style_rules)
    
    # Update rephrase prompt with distilled rules
    update_rephrase_prompt(style_rules, user_id)
