"""Job fit scoring module using OpenAI to evaluate job-profile match."""

import json
import os
import re
from pathlib import Path
from typing import Any

import psycopg2
import yaml
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv(Path(__file__).parent.parent / ".env")


def load_scoring_profile() -> dict:
    """Load the scoring profile configuration."""
    profile_path = Path(__file__).parent.parent / "profile" / "scoring_profile.yaml"
    with open(profile_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_config() -> dict:
    """Load the main configuration."""
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def apply_hard_filters(job: dict, config: dict) -> tuple[bool, str]:
    """
    Apply exclusion rules from config BEFORE calling OpenAI.
    
    Args:
        job: Job dictionary with title, description, salary_min, salary_max
        config: Configuration dictionary with exclusion rules
        
    Returns:
        Tuple of (should_skip: bool, reason: str)
    """
    exclusions = config.get("exclusions", {})
    scoring = config.get("scoring", {})
    
    title = (job.get("title") or "").lower()
    description = (job.get("description") or "").lower()
    
    # Check for experience requirements (3+ years)
    # Match patterns like "3 years", "3+ years", "4 years", "5+ years", etc.
    exp_patterns = [
        r'\b([3-9]|\d{2,})\+?\s*years?\s+(of\s+)?experience',
        r'\bminimum\s+([3-9]|\d{2,})\s*years?',
        r'\bat\s+least\s+([3-9]|\d{2,})\s*years?',
    ]
    
    for pattern in exp_patterns:
        match = re.search(pattern, description, re.IGNORECASE)
        if match:
            years = match.group(1)
            if int(years) >= 3:
                return True, f"Requires {years}+ years of experience"
    
    # Check title keywords
    title_keywords = exclusions.get("title_keywords", [])
    for keyword in title_keywords:
        if keyword.lower() in title:
            return True, f"Title contains excluded keyword: '{keyword}'"
    
    # Check description keywords
    desc_keywords = exclusions.get("description_keywords", [])
    for keyword in desc_keywords:
        if keyword.lower() in description:
            return True, f"Description contains excluded keyword: '{keyword}'"
    
    # Check salary floor
    salary_floor = scoring.get("salary_floor", 0)
    salary_max = job.get("salary_max")
    
    if salary_max is not None and salary_max > 0 and salary_max < salary_floor:
        return True, f"Salary ({salary_max}) below floor ({salary_floor})"
    
    return False, ""


def score_job(job: dict, profile: dict, client: OpenAI) -> dict:
    """
    Score a single job against the profile using OpenAI.
    
    Args:
        job: Job dictionary with title, company, description
        profile: Scoring profile dictionary
        client: OpenAI client instance
        
    Returns:
        Dictionary with fit_score, fit_summary, and keyword_matches
    """
    # Truncate description to 1200 chars to keep prompt under 1500 tokens
    description = (job.get("description") or "")[:1200]
    
    # Build prompt
    must_have = profile.get("must_have_keywords", [])
    nice_to_have = profile.get("nice_to_have_keywords", [])
    target_roles = profile.get("target_roles", [])
    industries = profile.get("industries", [])
    strengths = profile.get("core_strengths", [])
    
    prompt = f"""Score this job for fit against my profile. Return JSON only, no other text.

MY PROFILE:
Target roles: {', '.join(target_roles)}
Industries: {', '.join(industries)}
Must-have keywords (ANY of): {', '.join(must_have)}
Nice-to-have keywords: {', '.join(nice_to_have)}
Core strengths: {'; '.join(strengths)}

SCORING PRIORITY:
- Strongly prioritize forward deployed engineer style roles (customer-facing technical delivery, field engineering, deployment in production environments).
- De-prioritize generic roles that do not involve deployment ownership or applied engineering impact.

JOB:
Title: {job.get('title', 'Unknown')}
Company: {job.get('company', 'Unknown')}
Location: {job.get('location', 'Not specified')}

Description:
{description}

Return this exact JSON structure:
{{
    "fit_score": <float 0.0 to 1.0>,
    "fit_summary": "<one paragraph, max 80 words explaining fit>",
    "keyword_matches": {{
        "matched": ["<keywords from my must-have/nice-to-have that appear in job>"],
        "missing": ["<important keywords from my profile not in job>"]
    }}
}}"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a job fit scoring assistant. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.3,
        )
        
        content = response.choices[0].message.content.strip()
        
        # Try to extract JSON from the response
        # Sometimes the model wraps it in ```json blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        result = json.loads(content)
        
        # Validate required fields
        if "fit_score" not in result:
            result["fit_score"] = 0.5
        if "fit_summary" not in result:
            result["fit_summary"] = "Unable to generate summary"
        if "keyword_matches" not in result:
            result["keyword_matches"] = {"matched": [], "missing": []}
        
        # Ensure fit_score is in valid range
        result["fit_score"] = max(0.0, min(1.0, float(result["fit_score"])))
        
        return result
        
    except json.JSONDecodeError as e:
        print(f"JSON parse error for job '{job.get('title', 'unknown')}': {e}")
        return {
            "fit_score": 0.5,
            "fit_summary": "Error parsing AI response",
            "keyword_matches": {"matched": [], "missing": []}
        }
    except Exception as e:
        print(f"Scoring error for job '{job.get('title', 'unknown')}': {e}")
        return {
            "fit_score": 0.5,
            "fit_summary": f"Error during scoring: {str(e)}",
            "keyword_matches": {"matched": [], "missing": []}
        }


def score_pending_jobs(conn, profile: dict, client: OpenAI) -> int:
    """
    Score all jobs in job_status where fit_score IS NULL.
    
    Args:
        conn: Database connection
        profile: Scoring profile dictionary
        client: OpenAI client instance
        
    Returns:
        Number of jobs scored
    """
    config = load_config()
    scored_count = 0
    skipped_count = 0
    
    with conn.cursor() as cur:
        # Get all unscored jobs
        cur.execute("""
            SELECT j.id, j.title, j.company, j.location, j.description,
                   j.salary_min, j.salary_max
            FROM jobs j
            JOIN job_status js ON js.job_id = j.id
            WHERE js.fit_score IS NULL
              AND j.is_duplicate = FALSE
        """)
        
        jobs = cur.fetchall()
        columns = ["id", "title", "company", "location", "description", "salary_min", "salary_max"]
    
    print(f"Found {len(jobs)} unscored jobs")
    
    for job_row in jobs:
        job = dict(zip(columns, job_row))
        job_id = job["id"]
        
        # Apply hard filters first
        should_skip, reason = apply_hard_filters(job, config)
        
        if should_skip:
            print(f"  Skipping '{job['title']}' at {job['company']}: {reason}")
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE job_status
                    SET fit_score = 0.0, fit_summary = %s, status = 'rejected'
                    WHERE job_id = %s
                """, (f"Auto-rejected: {reason}", job_id))
                conn.commit()
            skipped_count += 1
            continue
        
        # Score with OpenAI
        print(f"  Scoring: '{job['title']}' at {job['company']}...")
        result = score_job(job, profile, client)
        
        # Update database
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE job_status
                SET fit_score = %s, fit_summary = %s, keyword_matches = %s
                WHERE job_id = %s
            """, (
                result["fit_score"],
                result["fit_summary"],
                json.dumps(result["keyword_matches"]),
                job_id
            ))
            conn.commit()
        
        scored_count += 1
        print(f"    Score: {result['fit_score']:.2f}")
    
    return scored_count


def main() -> None:
    """Main entry point for running scoring standalone."""
    print("=" * 60)
    print("Job Pipeline - Fit Scoring")
    print("=" * 60)
    
    # Check for API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not found in environment")
        return
    
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not found in environment")
        return
    
    # Load profile
    profile = load_scoring_profile()
    print(f"\nLoaded scoring profile")
    print(f"  Target roles: {len(profile.get('target_roles', []))}")
    print(f"  Must-have keywords: {len(profile.get('must_have_keywords', []))}")
    print()
    
    # Create OpenAI client
    client = OpenAI(api_key=api_key)
    
    # Connect and score
    conn = psycopg2.connect(db_url)
    
    try:
        scored = score_pending_jobs(conn, profile, client)
        print(f"\nScoring complete: {scored} jobs scored")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
