"""Story drafter - drafts new bullets from stories when bank doesn't have a match."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from agent.config import get_claude_model
from agent.validators import BulletCandidate, BulletSlot, BulletValidationError


DRAFT_SYSTEM_PROMPT = """
You are a CV bullet point writer. Draft a bullet from the provided experience notes.

Rules:
- Start with a strong action verb (past tense for past roles, present for current)
- British English spelling
- Concise, direct, no pompous language
- Include at least one keyword from the provided required keywords
- Maximum 110 characters including spaces
- Draw only on facts in the experience notes — do not invent metrics or tools
- Do not use: passionate, leveraged, utilised, spearheaded, fast-paced, dynamic
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


def load_stories(stories_path: Path) -> dict[str, str]:
    """
    Load stories.md and parse into sections.
    Returns {subsection_name: story_text}
    """
    if not stories_path.exists():
        return {}
    
    content = stories_path.read_text(encoding='utf-8')
    stories = {}
    
    current_subsection = None
    current_text = []
    
    for line in content.split('\n'):
        # Check for subsection header (## Name)
        if line.startswith('## '):
            # Save previous subsection
            if current_subsection and current_text:
                stories[current_subsection] = '\n'.join(current_text).strip()
            
            current_subsection = line[3:].strip()
            current_text = []
        elif current_subsection:
            current_text.append(line)
    
    # Save last subsection
    if current_subsection and current_text:
        stories[current_subsection] = '\n'.join(current_text).strip()
    
    return stories


def find_relevant_story(subsection: str, stories: dict[str, str]) -> Optional[str]:
    """
    Find the most relevant story section for a given subsection.
    Tries exact match first, then fuzzy matching.
    """
    # Exact match
    if subsection in stories:
        return stories[subsection]
    
    # Case-insensitive match
    subsection_lower = subsection.lower()
    for name, text in stories.items():
        if name.lower() == subsection_lower:
            return text
    
    # Partial match
    for name, text in stories.items():
        if subsection_lower in name.lower() or name.lower() in subsection_lower:
            return text
    
    return None


def extract_numbers_from_text(text: str) -> set[str]:
    """Extract all numbers/metrics from text for validation."""
    # Find standalone numbers, percentages, money amounts
    patterns = [
        r'\d+%',          # percentages
        r'£[\d,]+',       # money
        r'\$[\d,]+',      # dollars
        r'\b\d{1,3}(?:,\d{3})*\b',  # numbers with commas
        r'\b\d+\b',       # plain numbers
    ]
    
    numbers = set()
    for pattern in patterns:
        for match in re.findall(pattern, text):
            numbers.add(match)
    
    return numbers


def draft_bullet_from_story(
    gap_slot: BulletSlot,
    stories_path: Path,
    keywords: dict,
    role_family: str,
    client,
    user_id: int = 1
) -> BulletCandidate:
    """
    Find relevant story section for slot's subsection.
    Call Haiku with story excerpt + required keywords + system prompt.
    Validate with BulletCandidate. Retry up to 3x.
    Returns candidate with source='story_draft'.
    """
    # Load stories
    stories = load_stories(stories_path)
    
    # Find relevant story
    story_text = find_relevant_story(gap_slot.subsection, stories)
    if not story_text:
        raise ValueError(f"No story found for subsection: {gap_slot.subsection}")
    
    # Truncate story if too long (keep under 1500 chars for token efficiency)
    if len(story_text) > 1500:
        story_text = story_text[:1500] + "..."
    
    # Get required keywords for the prompt
    required_kws = keywords.get('required_keywords', [])[:5]  # Top 5
    nice_to_have_kws = keywords.get('nice_to_have_keywords', [])[:3]  # Top 3
    all_target_kws = required_kws + nice_to_have_kws
    
    # Numbers in story - for validation
    story_numbers = extract_numbers_from_text(story_text)
    
    # Build user prompt
    user_prompt = f"""Experience notes for {gap_slot.subsection}:
{story_text}

Target keywords to include (pick at least one): {', '.join(all_target_kws) if all_target_kws else 'None specified'}

Role context: {role_family}

Write ONE bullet point. Output ONLY the bullet text, nothing else."""

    max_retries = 3
    last_error = None
    
    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model=get_claude_model(),
                max_tokens=150,
                system=DRAFT_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}]
            )
            
            # Log API usage
            _log_api_usage(
                operation="draft_bullet",
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                user_id=user_id
            )
            
            # Extract bullet text
            bullet_text = response.content[0].text.strip()
            
            # Remove leading bullet characters if present
            bullet_text = re.sub(r'^[-•▪◦]\s*', '', bullet_text)
            
            # Validate numbers aren't invented
            bullet_numbers = extract_numbers_from_text(bullet_text)
            invented_numbers = bullet_numbers - story_numbers
            if invented_numbers:
                raise BulletValidationError(
                    f"Bullet contains invented numbers not in story: {invented_numbers}"
                )
            
            # Create and validate BulletCandidate
            candidate = BulletCandidate(
                text=bullet_text,
                source='story_draft',
                section=gap_slot.section,
                subsection=gap_slot.subsection,
                tags=[],  # Will be filled when approved
                role_families=[role_family],
                relevance_score=0.5,  # Default score for drafts
                rephrase_generation=0
            )
            
            return candidate
            
        except BulletValidationError as e:
            last_error = e
            # Add feedback to prompt for retry
            user_prompt += f"\n\nPrevious attempt failed: {str(e)}. Try again."
            continue
        except Exception as e:
            last_error = e
            continue
    
    # All retries failed
    raise ValueError(f"Failed to draft bullet after {max_retries} attempts: {last_error}")


def approve_bullet_for_bank(
    bullet_text: str,
    section: str,
    subsection: str,
    tags: list[str],
    role_families: list[str],
    bank_path: Path
) -> bool:
    """
    Append bullet to correct section in master_bullets.md.
    Do not add if already present.
    Returns True if added, False if duplicate.
    """
    if not bank_path.exists():
        raise FileNotFoundError(f"Bullet bank not found: {bank_path}")
    
    content = bank_path.read_text(encoding='utf-8')
    
    # Check if bullet already exists (case-insensitive)
    if bullet_text.lower() in content.lower():
        return False
    
    # Format the new bullet entry
    tags_str = ', '.join(tags) if tags else 'general'
    role_families_str = ', '.join(role_families) if role_families else 'general-swe'
    
    new_entry = f"""
- {bullet_text}
    [tags: {tags_str}]
    [role_family: {role_families_str}]
"""
    
    # Find the correct section and subsection to insert into
    lines = content.split('\n')
    new_lines = []
    
    # Normalise section name for matching
    section_header = "Work Experience" if section == "work_experience" else "Technical Projects"
    subsection_header = f"### {subsection}"
    
    found_section = False
    found_subsection = False
    inserted = False
    
    i = 0
    while i < len(lines):
        line = lines[i]
        new_lines.append(line)
        
        # Check for section header
        if line.strip().startswith('## ') and section_header.lower() in line.lower():
            found_section = True
        
        # Check for subsection header within the correct section
        if found_section and line.strip().startswith('### '):
            if subsection.lower() in line.lower():
                found_subsection = True
            elif found_subsection and not inserted:
                # We've moved past our subsection, insert before this new subsection
                new_lines.insert(-1, new_entry.rstrip())
                inserted = True
                found_subsection = False
        
        # If at next section header, insert before it
        if found_subsection and line.strip().startswith('## ') and not inserted:
            new_lines.insert(-1, new_entry.rstrip())
            inserted = True
        
        i += 1
    
    # If we found the subsection but reached end of file, append there
    if found_subsection and not inserted:
        new_lines.append(new_entry.rstrip())
        inserted = True
    
    # If subsection doesn't exist, create it at end of section
    if found_section and not found_subsection and not inserted:
        # Find end of section (next ## or end of file)
        for j in range(len(new_lines) - 1, -1, -1):
            if new_lines[j].strip().startswith('## ') and section_header.lower() not in new_lines[j].lower():
                # Insert before this section
                new_lines.insert(j, f"\n{subsection_header}\n{new_entry.rstrip()}")
                inserted = True
                break
        
        if not inserted:
            # Append at end
            new_lines.append(f"\n{subsection_header}\n{new_entry.rstrip()}")
            inserted = True
    
    if inserted:
        bank_path.write_text('\n'.join(new_lines), encoding='utf-8')
        return True
    
    return False


def get_story_excerpt(subsection: str, stories_path: Path, max_chars: int = 1000) -> Optional[str]:
    """
    Get a truncated story excerpt for a subsection.
    Useful for displaying context to users.
    """
    stories = load_stories(stories_path)
    story = find_relevant_story(subsection, stories)
    
    if not story:
        return None
    
    if len(story) <= max_chars:
        return story
    
    return story[:max_chars] + "..."
