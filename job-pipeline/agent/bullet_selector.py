"""Bullet selector - selects best bullets from bank for each CV slot."""

import re
from pathlib import Path
from typing import Optional

from agent.validators import BulletCandidate, BulletSlot, CVSelectionPlan
from agent.jd_parser import score_bullet_against_keywords


def load_bullet_bank(bank_path: Path) -> list[dict]:
    """
    Parse master_bullets.md.
    Each entry: {text, section, subsection, tags, role_families}
    
    Format expected:
    ## Work Experience
    ### Company Name
    - Bullet text here
        [tags: tag1, tag2]
        [role_family: fam1, fam2]
    """
    if not bank_path.exists():
        raise FileNotFoundError(f"Bullet bank not found: {bank_path}")
    
    content = bank_path.read_text(encoding='utf-8')
    bullets = []
    
    current_section = None
    current_subsection = None
    current_bullet_text = None
    current_tags = []
    current_role_families = []
    
    # Patterns
    section_pattern = re.compile(r'^## (.+)$')
    subsection_pattern = re.compile(r'^### (.+)$')
    bullet_pattern = re.compile(r'^- (.+)$')
    tags_pattern = re.compile(r'^\s*\[tags:\s*(.+)\]$')
    role_family_pattern = re.compile(r'^\s*\[role_family:\s*(.+)\]$')
    
    def save_current_bullet():
        nonlocal current_bullet_text, current_tags, current_role_families
        if current_bullet_text and current_section and current_subsection:
            bullets.append({
                'text': current_bullet_text,
                'section': normalise_section_name(current_section),
                'subsection': current_subsection,
                'tags': current_tags,
                'role_families': current_role_families
            })
        current_bullet_text = None
        current_tags = []
        current_role_families = []
    
    for line in content.split('\n'):
        line = line.rstrip()
        
        # Check for section header
        section_match = section_pattern.match(line)
        if section_match:
            save_current_bullet()
            current_section = section_match.group(1).strip()
            current_subsection = None
            continue
        
        # Check for subsection header
        subsection_match = subsection_pattern.match(line)
        if subsection_match:
            save_current_bullet()
            current_subsection = subsection_match.group(1).strip()
            continue
        
        # Check for bullet
        bullet_match = bullet_pattern.match(line)
        if bullet_match:
            save_current_bullet()
            current_bullet_text = bullet_match.group(1).strip()
            continue
        
        # Check for tags
        tags_match = tags_pattern.match(line)
        if tags_match and current_bullet_text:
            current_tags = [t.strip() for t in tags_match.group(1).split(',')]
            continue
        
        # Check for role_family
        role_family_match = role_family_pattern.match(line)
        if role_family_match and current_bullet_text:
            current_role_families = [rf.strip() for rf in role_family_match.group(1).split(',')]
            continue
    
    # Don't forget the last bullet
    save_current_bullet()
    
    return bullets


def normalise_section_name(section: str) -> str:
    """Convert section header to normalised form."""
    section_lower = section.lower().strip()
    if 'work experience' in section_lower or 'employment' in section_lower:
        return 'work_experience'
    elif 'technical project' in section_lower or 'project' in section_lower:
        return 'technical_projects'
    return section_lower.replace(' ', '_')


def get_approval_weights(
    subsection: str,
    role_family: str,
    conn,
    user_id: int = 1
) -> dict[str, float]:
    """
    Query cv_feedback for this user and subsection.
    Return {bullet_text: approval_rate} where
    approval_rate = times was_approved=TRUE / times shown (any generation).
    Empty dict if no history.
    """
    _ = role_family  # reserved for future role-aware filtering

    cur = conn.cursor()
    cur.execute("""
        SELECT 
            COALESCE(final_text, original_text) AS bullet_text,
            COUNT(*) as total_shown,
            SUM(CASE WHEN was_approved THEN 1 ELSE 0 END) as times_approved
        FROM cv_feedback
        WHERE user_id = %s 
          AND slot_subsection = %s
          AND COALESCE(final_text, original_text) IS NOT NULL
        GROUP BY COALESCE(final_text, original_text)
    """, (user_id, subsection))
    
    rows = cur.fetchall()
    cur.close()
    
    weights = {}
    for bullet_text, total_shown, times_approved in rows:
        if total_shown > 0:
            weights[bullet_text] = times_approved / total_shown
    
    return weights


def score_bullet_for_slot(
    bullet: dict,
    keywords: dict,
    role_family: str,
    approval_weights: dict[str, float]
) -> tuple[float, list[str]]:
    """
    Score a bullet for a slot, applying all boosts.
    
    Returns (final_score, matched_keywords)
    
    Scoring:
    1. Base score from keyword matching (0.0-1.0)
    2. Role family boost: +0.2 if bullet's role_families includes job's role_family
    3. Approval boost: +0.15 * approval_rate (0.0-1.0) for historical approvals
    
    Final score capped at 1.0
    """
    # Base keyword score
    base_score, matched = score_bullet_against_keywords(bullet['text'], keywords)
    
    # Role family boost
    role_boost = 0.0
    if role_family in bullet.get('role_families', []):
        role_boost = 0.2
    
    # Approval boost
    approval_boost = 0.0
    approval_rate = approval_weights.get(bullet['text'], 0.0)
    if approval_rate > 0:
        approval_boost = 0.15 * approval_rate
    
    final_score = min(1.0, base_score + role_boost + approval_boost)
    return round(final_score, 3), matched


def find_projects_to_hide(
    keywords: dict,
    template_map: dict,
    bullet_bank: list[dict],
    role_family: str
) -> list[str]:
    """
    Hide a project if: no bullets score above 0.1 AND no role_family match.
    Return list of project names to hide.
    """
    projects_to_hide = []
    
    # Get all technical projects from template_map
    tech_projects = template_map.get('technical_projects', {})
    
    for project_name in tech_projects.keys():
        # Find bullets for this project
        project_bullets = [b for b in bullet_bank 
                          if b['section'] == 'technical_projects' 
                          and b['subsection'] == project_name]
        
        if not project_bullets:
            # No bullets for this project - hide it
            projects_to_hide.append(project_name)
            continue
        
        # Check if any bullet scores above 0.1 OR has role_family match
        has_good_score = False
        has_role_match = False
        
        for bullet in project_bullets:
            score, _ = score_bullet_against_keywords(bullet['text'], keywords)
            if score > 0.1:
                has_good_score = True
                break
            if role_family in bullet.get('role_families', []):
                has_role_match = True
        
        if not has_good_score and not has_role_match:
            projects_to_hide.append(project_name)
    
    return projects_to_hide


def build_selection_plan(
    job: dict,
    keywords: dict,
    bullet_bank: list[dict],
    template_map: dict,
    conn,
    role_family: str,
    seniority_level: str,
    user_id: int = 1
) -> CVSelectionPlan:
    """
    Build selection plan for CV generation.
    
    For each bullet slot in template_map:
    1. Filter bank to bullets matching the slot's subsection
    2. Score each against keywords using score_bullet_against_keywords()
    3. Boost score by role_family match: +0.2 if bullet's role_families includes job's role_family
    4. Boost score by historical approval rate (query get_approval_weights())
    5. Select highest-scoring bullet as current_candidate
    6. If top score < 0.25 for any slot: flag for story_drafter
    
    API only called if story_drafter needed.
    Pure Python selection otherwise — zero API cost.
    
    Identify uncovered_keywords: required keywords not hit by any selected bullet.
    """
    work_experience_slots = []
    technical_project_slots = []
    all_matched_keywords = []
    slot_index = 0
    
    # Find projects to hide
    projects_to_hide = find_projects_to_hide(keywords, template_map, bullet_bank, role_family)
    
    # Process work experience section
    work_exp = template_map.get('work_experience', {})
    for subsection_name, subsection_data in work_exp.items():
        # Get approval weights for this subsection
        approval_weights = get_approval_weights(subsection_name, role_family, conn, user_id)
        
        # Get bullets for this subsection
        subsection_bullets = [b for b in bullet_bank 
                             if b['section'] == 'work_experience' 
                             and b['subsection'] == subsection_name]
        
        # Score all bullets
        scored_bullets = []
        for bullet in subsection_bullets:
            score, matched = score_bullet_for_slot(bullet, keywords, role_family, approval_weights)
            scored_bullets.append((bullet, score, matched))
        
        # Sort by score descending
        scored_bullets.sort(key=lambda x: x[1], reverse=True)
        
        # Create slots for each bullet position in template
        bullet_xpaths = subsection_data.get('bullet_xpaths', [])
        for i in range(len(bullet_xpaths)):
            if i < len(scored_bullets):
                bullet, score, matched = scored_bullets[i]
                all_matched_keywords.extend(matched)
                
                candidate = BulletCandidate(
                    text=bullet['text'],
                    source='master_bullets',
                    section='work_experience',
                    subsection=subsection_name,
                    tags=bullet.get('tags', []),
                    role_families=bullet.get('role_families', []),
                    relevance_score=score,
                    keyword_hits=matched
                )
                
                slot = BulletSlot(
                    slot_index=slot_index,
                    section='work_experience',
                    subsection=subsection_name,
                    current_candidate=candidate,
                    is_approved=False
                )
            else:
                # No more bullets available - create empty slot
                slot = BulletSlot(
                    slot_index=slot_index,
                    section='work_experience',
                    subsection=subsection_name,
                    current_candidate=None,
                    is_approved=False
                )
            
            work_experience_slots.append(slot)
            slot_index += 1
    
    # Process technical projects section (excluding hidden projects)
    tech_projects = template_map.get('technical_projects', {})
    for subsection_name, subsection_data in tech_projects.items():
        if subsection_name in projects_to_hide:
            continue
        
        # Get approval weights for this subsection
        approval_weights = get_approval_weights(subsection_name, role_family, conn, user_id)
        
        # Get bullets for this subsection
        subsection_bullets = [b for b in bullet_bank 
                             if b['section'] == 'technical_projects' 
                             and b['subsection'] == subsection_name]
        
        # Score all bullets
        scored_bullets = []
        for bullet in subsection_bullets:
            score, matched = score_bullet_for_slot(bullet, keywords, role_family, approval_weights)
            scored_bullets.append((bullet, score, matched))
        
        # Sort by score descending
        scored_bullets.sort(key=lambda x: x[1], reverse=True)
        
        # Create slots for each bullet position in template
        bullet_xpaths = subsection_data.get('bullet_xpaths', [])
        for i in range(len(bullet_xpaths)):
            if i < len(scored_bullets):
                bullet, score, matched = scored_bullets[i]
                all_matched_keywords.extend(matched)
                
                candidate = BulletCandidate(
                    text=bullet['text'],
                    source='master_bullets',
                    section='technical_projects',
                    subsection=subsection_name,
                    tags=bullet.get('tags', []),
                    role_families=bullet.get('role_families', []),
                    relevance_score=score,
                    keyword_hits=matched
                )
                
                slot = BulletSlot(
                    slot_index=slot_index,
                    section='technical_projects',
                    subsection=subsection_name,
                    current_candidate=candidate,
                    is_approved=False
                )
            else:
                # No more bullets available - create empty slot
                slot = BulletSlot(
                    slot_index=slot_index,
                    section='technical_projects',
                    subsection=subsection_name,
                    current_candidate=None,
                    is_approved=False
                )
            
            technical_project_slots.append(slot)
            slot_index += 1
    
    # Calculate keyword coverage
    keyword_coverage = {}
    for kw in set(all_matched_keywords):
        covering_slots = []
        for slot in work_experience_slots + technical_project_slots:
            if slot.current_candidate and kw in slot.current_candidate.keyword_hits:
                covering_slots.append(slot.slot_index)
        keyword_coverage[kw] = covering_slots
    
    # Find uncovered required keywords
    required = set(keywords.get('required_keywords', []))
    covered = set(all_matched_keywords)
    uncovered = list(required - covered)
    
    return CVSelectionPlan(
        job_id=job.get('id', 0),
        user_id=user_id,
        job_title=job.get('title', ''),
        company=job.get('company', ''),
        role_family=role_family,
        seniority_level=seniority_level,
        required_keywords=keywords.get('required_keywords', []),
        nice_to_have_keywords=keywords.get('nice_to_have_keywords', []),
        technical_keywords=keywords.get('technical_skills', []),
        work_experience_slots=work_experience_slots,
        technical_project_slots=technical_project_slots,
        projects_to_hide=projects_to_hide,
        keyword_coverage=keyword_coverage,
        uncovered_keywords=uncovered
    )


def get_low_score_slots(plan: CVSelectionPlan, threshold: float = 0.25) -> list[BulletSlot]:
    """
    Return slots where current_candidate score < threshold.
    These are candidates for story_drafter.
    """
    low_slots = []
    all_slots = plan.work_experience_slots + plan.technical_project_slots
    
    for slot in all_slots:
        if slot.current_candidate is None:
            low_slots.append(slot)
        elif slot.current_candidate.relevance_score < threshold:
            low_slots.append(slot)
    
    return low_slots
