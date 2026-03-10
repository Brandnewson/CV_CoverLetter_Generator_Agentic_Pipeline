"""Bullet rephraser - generates alternative phrasings with different keyword emphasis."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from agent.config import get_claude_model
from agent.validators import BulletCandidate, BulletValidationError


DEFAULT_REPHRASE_SYSTEM_PROMPT = """
You are a CV bullet point editor for a {role_family} software engineering role.

Rephrase the provided bullet point. Rules:
- Start with a strong action verb (past tense for past roles, present for current)
- Use British English spelling
- Write concise, simple, straight-to-the-point sentences
- Include one technology or keyword from the job description that is not already in
  the 'already used keywords' list
- Do not duplicate any keyword from the 'already used keywords' list
- Must be between 90 and 112 characters including spaces — target 100–110 to maximise keyword density without overflowing the CV line; bullets under 90 characters waste space
- Do not invent metrics, tools, or experiences not in the original bullet
- Do not reproduce any previous version exactly

Banned words: passionate, leveraged, utilised, spearheaded, fast-paced, dynamic, synerg
"""


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


def load_rephrase_prompt(user_id: int = 1) -> str:
    """
    Load rephrase prompt from profile/users/{user_id}/rephrase_prompt.txt.
    Falls back to DEFAULT_REPHRASE_SYSTEM_PROMPT if file doesn't exist.
    """
    prompt_path = Path(__file__).parent.parent / "profile" / "users" / str(user_id) / "rephrase_prompt.txt"
    
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    
    return DEFAULT_REPHRASE_SYSTEM_PROMPT


def save_rephrase_prompt(prompt: str, user_id: int = 1) -> None:
    """
    Save rephrase prompt to profile/users/{user_id}/rephrase_prompt.txt.
    Creates directory if needed.
    """
    prompt_path = Path(__file__).parent.parent / "profile" / "users" / str(user_id) / "rephrase_prompt.txt"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt, encoding="utf-8")


def _check_keyword_reuse(bullet_text: str, already_used_keywords: list[str]) -> list[str]:
    """
    Check if bullet contains any already-used keywords.
    Returns list of reused keywords found.
    """
    bullet_lower = bullet_text.lower()
    reused = []
    for kw in already_used_keywords:
        # Match as whole word or part of compound
        if re.search(rf'\b{re.escape(kw.lower())}\b', bullet_lower):
            reused.append(kw)
    return reused


def rephrase_bullet(
    original_bullet: str,
    job_keywords: list[str],
    already_used_keywords: list[str],
    role_family: str,
    previous_versions: list[str],
    slot_section: str,
    slot_subsection: str,
    client,
    user_id: int = 1
) -> BulletCandidate:
    """
    Generate a rephrasing of original_bullet.
    Constraints passed to the model:
    - job_keywords: prioritise including one of these not yet covered
    - already_used_keywords: do not repeat these
    - previous_versions: do not reproduce any of these
    - role_family: context for tone calibration
    Validate output with BulletCandidate before returning.
    Retry up to 3 times on validation failure.
    Log tokens to logs/api_usage.jsonl with user_id.
    Returns candidate with source='rephrasing'.
    """
    # Load customizable prompt
    system_prompt = load_rephrase_prompt(user_id).format(role_family=role_family)
    
    # Find keywords not yet used
    available_keywords = [kw for kw in job_keywords if kw.lower() not in [u.lower() for u in already_used_keywords]]
    
    # Build user prompt
    user_prompt = f"""Original bullet:
{original_bullet}

Job keywords to consider including (prioritise one from this list): {', '.join(available_keywords[:10]) if available_keywords else 'None available'}

Already used keywords (DO NOT USE THESE): {', '.join(already_used_keywords) if already_used_keywords else 'None'}

Previous versions (DO NOT REPRODUCE ANY OF THESE):
{chr(10).join('- ' + v for v in previous_versions) if previous_versions else 'None'}

Rephrase the bullet. Output ONLY the new bullet text, nothing else."""

    max_retries = 3
    last_error = None
    
    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model=get_claude_model(),
                max_tokens=150,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )
            
            # Log API usage
            _log_api_usage(
                operation="rephrase_bullet",
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                user_id=user_id
            )
            
            # Extract bullet text
            bullet_text = response.content[0].text.strip()
            
            # Remove leading bullet characters if present
            bullet_text = re.sub(r'^[-•▪◦]\s*', '', bullet_text)
            
            # Check not identical to original
            if bullet_text.lower() == original_bullet.lower():
                raise BulletValidationError("Rephrased bullet is identical to original")
            
            # Check not identical to any previous version
            for prev in previous_versions:
                if bullet_text.lower() == prev.lower():
                    raise BulletValidationError(f"Rephrased bullet is identical to previous version: {prev[:30]}...")
            
            # Check no reuse of already-used keywords
            reused = _check_keyword_reuse(bullet_text, already_used_keywords)
            if reused:
                raise BulletValidationError(f"Rephrased bullet reuses already-used keywords: {reused}")
            
            # Create and validate BulletCandidate (validates length, banned phrases, etc.)
            candidate = BulletCandidate(
                text=bullet_text,
                source='rephrasing',
                section=slot_section,
                subsection=slot_subsection,
                tags=[],
                role_families=[role_family],
                relevance_score=0.5,  # Default score for rephrasings
                rephrase_generation=len(previous_versions) + 1
            )
            
            return candidate
            
        except BulletValidationError as e:
            last_error = e
            # Add feedback to prompt for retry
            user_prompt += f"\n\nPrevious attempt failed: {str(e)}. Try again with a different approach."
            continue
        except Exception as e:
            last_error = e
            continue
    
    # All retries failed
    raise ValueError(f"Failed to rephrase bullet after {max_retries} attempts: {last_error}")


def get_rephrase_generation_count(
    job_id: int,
    slot_section: str,
    slot_index: int,
    conn,
    user_id: int = 1
) -> int:
    """
    Query cv_feedback to find how many rephrases have been generated
    for this slot so far. Used to set rephrase_generation on new rows.
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COALESCE(MAX(rephrase_generation), 0) as max_gen
        FROM cv_feedback
        WHERE job_id = %s
          AND slot_section = %s
          AND slot_index = %s
          AND user_id = %s
    """, (job_id, slot_section, slot_index, user_id))
    
    result = cursor.fetchone()
    return result[0] if result else 0


def record_rephrase_feedback(
    job_id: int,
    session_id: str,
    slot_section: str,
    slot_subsection: str,
    slot_index: int,
    original_text: str,
    final_text: str,
    was_approved: bool,
    rephrase_generation: int,
    source: str,
    keyword_hits: list[str],
    relevance_score: float,
    conn,
    user_id: int = 1
) -> int:
    """
    Record a rephrase feedback entry in cv_feedback table.
    Returns the inserted row id.
    """
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO cv_feedback (
            user_id, job_id, session_id, slot_section, slot_subsection,
            slot_index, original_text, final_text, was_approved,
            rephrase_generation, source, keyword_hits, relevance_score
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (
        user_id, job_id, session_id, slot_section, slot_subsection,
        slot_index, original_text, final_text, was_approved,
        rephrase_generation, source, json.dumps(keyword_hits), relevance_score
    ))
    
    row_id = cursor.fetchone()[0]
    conn.commit()
    return row_id
