"""CV Builder Web UI - Flask application for building CVs."""

import os
from datetime import datetime, timezone
from pathlib import Path

import anthropic
import psycopg2
import yaml
from psycopg2.extras import Json
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, send_file, url_for
from flask_cors import CORS
from pydantic import BaseModel, Field
from werkzeug.utils import secure_filename

from agent.bullet_rephraser import rephrase_bullet
from agent.bullet_selector import build_selection_plan, load_bullet_bank
from agent.bullet_suggester import generate_suggestions_for_section
from agent.cv_parser import extract_sections, sections_to_json
from agent.cv_renderer import render_cv
from agent.jd_parser import classify_role_family, classify_seniority, score_bullet_against_keywords
from agent.profile_condenser import condense_confirmed_sections
from agent.story_drafter import approve_bullet_for_bank
from agent.template_extractor import load_template_map
from agent.validators import UserSelections
from discovery.config_writer import read_config_yaml, write_config_yaml
from discovery.enrichment import (
    normalize_company_description_text,
    normalize_job_description_markdown,
)

# Load environment
load_dotenv(Path(__file__).parent.parent / ".env")

app = Flask(__name__)
CORS(app)

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL")
BASE_DIR = Path(__file__).parent.parent
PROFILE_DIR = BASE_DIR / "profile"
DEFAULT_USER_ID = int(os.getenv("DEFAULT_USER_ID", "1"))
USER_PROFILE_DIR = PROFILE_DIR / "users" / str(DEFAULT_USER_ID)
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def parse_bool_env(name: str, default: bool) -> bool:
    """Parse boolean environment variable with sensible truthy values."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def unique_destination_path(dest_dir: Path, filename: str) -> Path:
    """Return a non-colliding path for filename inside dest_dir.

    If `filename` already exists, append " (N)" before extension.
    Examples:
      cv.pdf -> cv (1).pdf -> cv (2).pdf
    """
    candidate = dest_dir / filename
    if not candidate.exists():
        return candidate

    base = Path(filename).stem
    suffix = Path(filename).suffix
    index = 1
    while True:
        next_name = f"{base} ({index}){suffix}"
        candidate = dest_dir / next_name
        if not candidate.exists():
            return candidate
        index += 1


# Keep job status as queued after render so same job_id can be rerun in testing.
KEEP_JOB_QUEUED_AFTER_RENDER = parse_bool_env("KEEP_JOB_QUEUED_AFTER_RENDER", True)

def resolve_profile_asset(candidates: list[Path]) -> Path:
    """Return first existing path from candidates, else first candidate."""
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


# Template and bullet bank paths (prefer user-scoped assets)
TEMPLATE_PATH = resolve_profile_asset([
    USER_PROFILE_DIR / "cv_template.docx",
    USER_PROFILE_DIR / "master_cv_template.docx",
    PROFILE_DIR / "cv_template.docx",
])
TEMPLATE_MAP_PATH = resolve_profile_asset([
    USER_PROFILE_DIR / "template_map.json",
    PROFILE_DIR / "template_map.json",
])
BULLET_BANK_PATH = resolve_profile_asset([
    USER_PROFILE_DIR / "master_bullets.md",
    PROFILE_DIR / "master_bullets.md",
])
STORIES_PATH = resolve_profile_asset([
    USER_PROFILE_DIR / "stories.md",
    PROFILE_DIR / "stories.md",
])
EXPERIENCE_PATH = resolve_profile_asset([
    USER_PROFILE_DIR / "experience.md",
    PROFILE_DIR / "experience.md",
])

# Profile upload directories (created on demand)
UPLOADS_DIR = USER_PROFILE_DIR / "uploads"
COVER_LETTERS_DIR = USER_PROFILE_DIR / "cover_letters"
LOG_PATH = BASE_DIR / "logs" / "api_usage.jsonl"
DISCOVERY_CONFIG_PATH = BASE_DIR / "discovery" / "config.yaml"

_ALLOWED_UPLOAD_TYPES = {"cv", "cover_letter", "story", "project_context"}
_ALLOWED_EXTENSIONS = {".docx", ".pdf", ".md", ".txt"}


class PreferencesModel(BaseModel):
    search_terms: list[str] = Field(default_factory=list)
    role_families: list[str] = Field(default_factory=list)
    location: str = "London, UK"
    country_indeed: str = "UK"
    results_wanted: int = 30
    hours_old: int = 25
    salary_floor: int = 40000
    currency: str = "GBP"
    excluded_title_keywords: list[str] = Field(default_factory=list)
    excluded_desc_keywords: list[str] = Field(default_factory=list)


def get_db_connection():
    """Get a database connection."""
    return psycopg2.connect(DATABASE_URL)


def get_job_by_id(conn, job_id: int) -> dict | None:
    """Fetch job details from database."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 
                j.id, j.title, j.company, j.location, j.description,
                j.job_description_raw, j.company_description_raw, j.enrichment_keywords,
                j.salary_min, j.salary_max, j.job_url, j.source,
                j.date_posted,
                js.status, js.fit_score, js.fit_summary, js.keyword_matches
            FROM jobs j
            JOIN job_status js ON js.job_id = j.id
            WHERE j.id = %s
        """, (job_id,))
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "title": row[1],
            "company": row[2],
            "location": row[3],
            "description": row[4] or "",
            "job_description_raw": row[5] or "",
            "company_description_raw": row[6] or "",
            "enrichment_keywords": row[7] or {},
            "salary_min": row[8],
            "salary_max": row[9],
            "job_url": row[10],
            "source": row[11],
            "date_posted": row[12].isoformat() if row[12] else None,
            "status": row[13],
            "fit_score": row[14],
            "fit_summary": row[15],
            "keyword_matches": row[16] or {}
        }


def get_queued_jobs(conn) -> list[dict]:
    """Fetch all jobs with status='queued'."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT j.id, j.title, j.company, js.fit_score
            FROM jobs j
            JOIN job_status js ON js.job_id = j.id
            WHERE js.status = 'queued'
              AND NULLIF(BTRIM(COALESCE(j.job_description_raw, '')), '') IS NOT NULL
              AND j.enrichment_keywords IS NOT NULL
              AND jsonb_typeof(j.enrichment_keywords) = 'object'
            ORDER BY js.fit_score DESC
        """)
        jobs = []
        for row in cur.fetchall():
            jobs.append({
                "id": row[0],
                "title": row[1],
                "company": row[2],
                "fit_score": row[3]
            })
        return jobs


def get_latest_queued_job_id(conn) -> int | None:
    """Get the ID of the most recently queued job."""
    jobs = get_queued_jobs(conn)
    if jobs:
        return jobs[0]["id"]
    return None


def normalize_keyword_list(values) -> list[str]:
    """Normalize keyword inputs into a de-duplicated list of strings."""
    if values is None:
        return []

    if isinstance(values, str):
        items = []
        for line in values.splitlines():
            parts = [part.strip() for part in line.split(",")]
            items.extend(parts)
    elif isinstance(values, list):
        items = [str(value).strip() for value in values]
    else:
        raise ValueError("Keyword fields must be arrays or newline/comma separated text")

    cleaned = [item for item in items if item]
    deduped = list(dict.fromkeys(cleaned))
    return deduped


def update_job_enrichment(
    conn,
    job_id: int,
    job_description_raw: str,
    company_description_raw: str,
    enrichment_keywords: dict,
) -> bool:
    """Update enrichment fields for a single job."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE jobs
            SET description = %s,
                job_description_raw = %s,
                company_description_raw = %s,
                enrichment_keywords = %s
            WHERE id = %s
            """,
            (
                job_description_raw,
                job_description_raw,
                company_description_raw,
                Json(enrichment_keywords),
                job_id,
            ),
        )
        updated = cur.rowcount > 0
    return updated


def build_plan_for_job(conn, job: dict, user_id: int = 1):
    """Build a CVSelectionPlan for a job."""
    job_description = (job.get("job_description_raw") or "").strip()
    enrichment_keywords = job.get("enrichment_keywords") or {}

    technologies = enrichment_keywords.get("technologies", [])
    skills = enrichment_keywords.get("skills", [])
    abilities = enrichment_keywords.get("abilities", [])

    keywords = {
        "required_keywords": technologies,
        "nice_to_have_keywords": abilities,
        "technical_skills": technologies,
        "soft_skills": skills,
        "domain_keywords": abilities,
        "seniority_signals": [],
        "technologies": technologies,
        "skills": skills,
        "abilities": abilities,
    }

    # Classify the job
    role_family = classify_role_family(job["title"], job_description)
    seniority_level = classify_seniority(job["title"], job_description)
    
    # Load resources
    bullet_bank = load_bullet_bank(BULLET_BANK_PATH)
    template_map = load_template_map(TEMPLATE_MAP_PATH)
    
    # Build selection plan
    plan = build_selection_plan(
        job=job,
        keywords=keywords,
        bullet_bank=bullet_bank,
        template_map=template_map,
        conn=conn,
        role_family=role_family,
        seniority_level=seniority_level,
        user_id=user_id,
        hide_projects=False,
    )
    
    return plan, keywords


# Store active sessions (in production, use Redis or DB)
active_plans = {}
active_keywords = {}
active_suggestions = {}


def get_profile_context_text() -> str:
    """Load user profile context used for suggestion generation prompts."""
    chunks: list[str] = []

    if EXPERIENCE_PATH.exists():
        chunks.append(EXPERIENCE_PATH.read_text(encoding="utf-8"))

    if BULLET_BANK_PATH.exists():
        chunks.append(BULLET_BANK_PATH.read_text(encoding="utf-8"))

    return "\n\n".join(chunk for chunk in chunks if chunk).strip()


def build_slots_map_by_subsection(slots) -> dict[str, list[str]]:
    """Map subsection -> existing current candidate bullet texts."""
    grouped: dict[str, list[str]] = {}
    for slot in slots:
        grouped.setdefault(slot.subsection, [])
        if slot.current_candidate:
            grouped[slot.subsection].append(slot.current_candidate.text)
    return grouped


def add_existing_bank_matches_to_suggestions(
    section_key: str,
    section_suggestions: list[dict],
    section_slots,
    bullet_bank: list[dict],
    keywords: dict,
) -> list[dict]:
    """Attach top-scoring existing bullet-bank matches per subsection.

    These are bullets already in the bank that are not currently placed in the slot set.
    """
    current_by_subsection: dict[str, set[str]] = {}
    for slot in section_slots:
        current_by_subsection.setdefault(slot.subsection, set())
        if slot.current_candidate:
            current_by_subsection[slot.subsection].add(slot.current_candidate.text.strip().lower())

    for subsection_entry in section_suggestions:
        subsection_name = subsection_entry.get("subsection", "")
        current_texts = current_by_subsection.get(subsection_name, set())

        matching_bank = [
            bullet for bullet in bullet_bank
            if bullet.get("section") == section_key and bullet.get("subsection") == subsection_name
        ]

        scored = []
        for bullet in matching_bank:
            text = (bullet.get("text") or "").strip()
            if not text:
                continue
            if text.lower() in current_texts:
                continue
            score, hits = score_bullet_against_keywords(text, keywords)
            scored.append((score, text, hits))

        scored.sort(key=lambda row: row[0], reverse=True)
        
        # Use a balanced quality gate: show all above 0.10, fill to minimum if fewer
        existing_matches = []
        above_threshold = []
        for score, text, hits in scored:
            if score >= 0.10:
                above_threshold.append((score, text, hits))
        
        # Use all above threshold, up to 5
        for score, text, hits in above_threshold[:5]:
            existing_matches.append({
                "text": text,
                "keywords_targeted": hits,
                "char_count": len(text),
                "over_soft_limit": len(text) > 110,
                "over_hard_limit": len(text) > 120,
                "warnings": [],
            })

        subsection_entry["existing_matches"] = existing_matches

    return section_suggestions


@app.route("/")
def index():
    """Redirect to the latest queued job."""
    try:
        conn = get_db_connection()
        job_id = get_latest_queued_job_id(conn)
        conn.close()
        if job_id:
            return redirect(url_for("build_cv", job_id=job_id))
        return render_template("cv_builder.html", error="No queued jobs found")
    except Exception as e:
        return render_template("cv_builder.html", error=str(e))


@app.route("/build/<int:job_id>")
def build_cv(job_id: int):
    """Serve the CV builder page."""
    return render_template("cv_builder.html", job_id=job_id)


@app.route("/api/plan/<int:job_id>")
def get_plan(job_id: int):
    """Return CVSelectionPlan as JSON."""
    try:
        conn = get_db_connection()
        job = get_job_by_id(conn, job_id)
        
        if not job:
            conn.close()
            return jsonify({"error": f"Job {job_id} not found"}), 404
        
        plan, keywords = build_plan_for_job(conn, job)
        conn.close()
        
        # Cache for session
        active_plans[job_id] = plan
        active_keywords[job_id] = keywords
        
        # Convert plan to JSON-serializable format
        plan_dict = plan.model_dump()
        plan_dict["job"] = job
        
        return jsonify(plan_dict)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/rephrase", methods=["POST"])
def rephrase():
    """Generate a rephrased bullet."""
    try:
        data = request.json
        job_id = data.get("job_id")
        slot_index = data.get("slot_index")
        section = data.get("section")
        subsection = data.get("subsection")
        
        if job_id not in active_plans:
            return jsonify({"error": "Plan not loaded. Call /api/plan first"}), 400
        
        plan = active_plans[job_id]
        keywords = active_keywords.get(job_id, {})
        
        # Find the slot
        all_slots = plan.work_experience_slots + plan.technical_project_slots
        slot = next((s for s in all_slots if s.slot_index == slot_index), None)
        
        if not slot:
            return jsonify({"error": f"Slot {slot_index} not found"}), 404
        
        if not slot.current_candidate:
            return jsonify({"error": "No current candidate to rephrase"}), 400
        
        # Get already used keywords in this CV
        already_used = []
        for s in all_slots:
            if s.current_candidate and s.slot_index != slot_index:
                already_used.extend(s.current_candidate.keyword_hits)
        already_used = list(set(already_used))
        
        # Get previous versions from rephrase history
        previous_versions = [slot.current_candidate.text]
        previous_versions.extend([b.text for b in slot.rephrase_history])
        
        # Build job keywords list
        job_keywords = (
            keywords.get("required_keywords", []) +
            keywords.get("nice_to_have_keywords", []) +
            keywords.get("technical_skills", [])
        )
        
        # Call rephraser
        client = anthropic.Anthropic()
        new_bullet = rephrase_bullet(
            original_bullet=slot.current_candidate.text,
            job_keywords=job_keywords,
            already_used_keywords=already_used,
            role_family=plan.role_family,
            previous_versions=previous_versions,
            slot_section=section,
            slot_subsection=subsection,
            client=client,
            user_id=plan.user_id
        )
        
        # Update slot history
        slot.rephrase_history.append(slot.current_candidate)
        slot.current_candidate = new_bullet
        
        return jsonify(new_bullet.model_dump())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/suggestions/<int:job_id>")
def get_suggestions(job_id: int):
    """Generate or return cached right-panel bullet suggestions for a job."""
    try:
        if job_id in active_suggestions:
            return jsonify(active_suggestions[job_id])

        conn = get_db_connection()
        job = get_job_by_id(conn, job_id)

        if not job:
            conn.close()
            return jsonify({"error": f"Job {job_id} not found"}), 404

        plan = active_plans.get(job_id)
        keywords = active_keywords.get(job_id)
        if plan is None or keywords is None:
            plan, keywords = build_plan_for_job(conn, job)
            active_plans[job_id] = plan
            active_keywords[job_id] = keywords

        conn.close()

        uncovered_keywords = plan.uncovered_keywords or []
        required_keywords = (keywords or {}).get("required_keywords", [])
        profile_context = get_profile_context_text()

        work_slots_map = build_slots_map_by_subsection(plan.work_experience_slots)
        project_slots_map = build_slots_map_by_subsection(plan.technical_project_slots)

        client = anthropic.Anthropic()
        work_suggestions = generate_suggestions_for_section(
            section="work_experience",
            slots_by_subsection=work_slots_map,
            uncovered_keywords=uncovered_keywords,
            required_keywords=required_keywords,
            stories_path=STORIES_PATH,
            profile_context=profile_context,
            client=client,
            user_id=plan.user_id,
        )

        # Technical projects: skip LLM generation entirely to avoid hallucinations.
        # Instead build empty stubs from the plan slots so bank matches can be
        # attached by add_existing_bank_matches_to_suggestions below.
        bullet_bank = load_bullet_bank(BULLET_BANK_PATH)

        # Collect subsections already in the plan
        plan_project_subsections: dict[str, list[str]] = {}
        for slot in plan.technical_project_slots:
            plan_project_subsections.setdefault(slot.subsection, [])
            if slot.current_candidate:
                plan_project_subsections[slot.subsection].append(slot.current_candidate.text)

        # Also include any new subsections the user has added to the bank but
        # that aren't in the plan yet (new projects created via the right panel)
        for bullet in bullet_bank:
            if bullet.get("section") == "technical_projects":
                sub = bullet.get("subsection", "")
                if sub and sub not in plan_project_subsections:
                    plan_project_subsections[sub] = []

        project_suggestions = [
            {
                "subsection": sub,
                "suggestions": [],
                "target_suggestion_count": 3,
                "existing_bullets": existing,
            }
            for sub, existing in plan_project_subsections.items()
        ]
        work_suggestions = add_existing_bank_matches_to_suggestions(
            section_key="work_experience",
            section_suggestions=work_suggestions,
            section_slots=plan.work_experience_slots,
            bullet_bank=bullet_bank,
            keywords=keywords,
        )
        project_suggestions = add_existing_bank_matches_to_suggestions(
            section_key="technical_projects",
            section_suggestions=project_suggestions,
            section_slots=plan.technical_project_slots,
            bullet_bank=bullet_bank,
            keywords=keywords,
        )

        payload = {
            "job_id": job_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "focus_keywords": uncovered_keywords,
            "sections": {
                "work_experience": work_suggestions,
                "technical_projects": project_suggestions,
            },
        }

        active_suggestions[job_id] = payload
        return jsonify(payload)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/bullets/add", methods=["POST"])
def add_user_bullets():
    """Persist user-provided bullets to bank with keyword-derived score metadata."""
    try:
        data = request.json or {}
        job_id = data.get("job_id")
        bullets = data.get("bullets", [])

        if not isinstance(job_id, int):
            return jsonify({"error": "job_id must be an integer"}), 400
        if not isinstance(bullets, list) or not bullets:
            return jsonify({"error": "bullets must be a non-empty array"}), 400

        conn = get_db_connection()
        try:
            job = get_job_by_id(conn, job_id)
            if not job:
                return jsonify({"error": f"Job {job_id} not found"}), 404

            plan = active_plans.get(job_id)
            keywords = active_keywords.get(job_id)
            if plan is None or keywords is None:
                plan, keywords = build_plan_for_job(conn, job)
                active_plans[job_id] = plan
                active_keywords[job_id] = keywords
        finally:
            conn.close()

        saved = []
        for item in bullets:
            text = str(item.get("text", "")).strip()
            section = str(item.get("section", "")).strip()
            subsection = str(item.get("subsection", "")).strip()

            if not text or section not in {"work_experience", "technical_projects"} or not subsection:
                continue

            score, keyword_hits = score_bullet_against_keywords(text, keywords)
            was_new = approve_bullet_for_bank(
                bullet_text=text,
                section=section,
                subsection=subsection,
                tags=keyword_hits,
                role_families=[str(plan.role_family)],
                bank_path=BULLET_BANK_PATH,
            )

            saved.append({
                "text": text,
                "source": "story_draft",
                "section": section,
                "subsection": subsection,
                "tags": keyword_hits,
                "role_families": [str(plan.role_family)],
                "relevance_score": score,
                "char_count": len(text),
                "over_soft_limit": len(text) > 110,
                "keyword_hits": keyword_hits,
                "rephrase_generation": 0,
                "warnings": [],
                "was_new": was_new,
            })

        active_suggestions.pop(job_id, None)
        return jsonify({"saved": saved})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/plan/<int:job_id>/refresh", methods=["POST"])
def refresh_plan(job_id: int):
    """Rebuild and return the plan using latest bullet bank and current keywords."""
    try:
        conn = get_db_connection()
        job = get_job_by_id(conn, job_id)
        if not job:
            conn.close()
            return jsonify({"error": f"Job {job_id} not found"}), 404

        keywords = active_keywords.get(job_id)
        if keywords is None:
            _, keywords = build_plan_for_job(conn, job)

        role_family = classify_role_family(job["title"], job.get("job_description_raw") or job["description"])
        seniority_level = classify_seniority(job["title"], job.get("job_description_raw") or job["description"])
        bullet_bank = load_bullet_bank(BULLET_BANK_PATH)
        template_map = load_template_map(TEMPLATE_MAP_PATH)

        plan = build_selection_plan(
            job=job,
            keywords=keywords,
            bullet_bank=bullet_bank,
            template_map=template_map,
            conn=conn,
            role_family=role_family,
            seniority_level=seniority_level,
            user_id=DEFAULT_USER_ID,
            hide_projects=False,
        )
        conn.close()

        active_plans[job_id] = plan
        active_keywords[job_id] = keywords
        active_suggestions.pop(job_id, None)

        plan_dict = plan.model_dump()
        plan_dict["job"] = job
        return jsonify(plan_dict)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/jobs/<int:job_id>/enrichment", methods=["PATCH"])
def update_enrichment(job_id: int):
    """Persist user-edited enrichment fields for a job."""
    try:
        data = request.json or {}

        job_description_raw = normalize_job_description_markdown(data.get("job_description_raw"))
        company_description_raw = normalize_company_description_text(data.get("company_description_raw"))

        raw_keywords = data.get("enrichment_keywords") or {}
        if not isinstance(raw_keywords, dict):
            return jsonify({"error": "enrichment_keywords must be an object"}), 400

        try:
            enrichment_keywords = {
                "technologies": normalize_keyword_list(raw_keywords.get("technologies", [])),
                "skills": normalize_keyword_list(raw_keywords.get("skills", [])),
                "abilities": normalize_keyword_list(raw_keywords.get("abilities", [])),
            }
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        conn = get_db_connection()
        updated = update_job_enrichment(
            conn=conn,
            job_id=job_id,
            job_description_raw=job_description_raw,
            company_description_raw=company_description_raw,
            enrichment_keywords=enrichment_keywords,
        )

        if not updated:
            conn.close()
            return jsonify({"error": f"Job {job_id} not found"}), 404

        conn.commit()

        job = get_job_by_id(conn, job_id)
        conn.close()

        active_plans.pop(job_id, None)
        active_keywords.pop(job_id, None)
        active_suggestions.pop(job_id, None)

        return jsonify({"status": "saved", "job": job})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/approve/<int:job_id>", methods=["POST"])
def approve(job_id: int):
    """Approve selections and trigger CV render."""
    try:
        data = request.json
        
        # Parse UserSelections from the request
        selections = UserSelections(
            job_id=job_id,
            user_id=data.get("user_id", 1),
            approved_bullets=data.get("approved_bullets", []),
            hidden_projects=data.get("hidden_projects", []),
            session_timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        # Get job info
        conn = get_db_connection()
        job = get_job_by_id(conn, job_id)
        conn.close()
        
        if not job:
            return jsonify({"error": f"Job {job_id} not found"}), 404
        
        # Define output path
        safe_company = "".join(c if c.isalnum() else "_" for c in job["company"])
        output_filename = f"cv_{job_id}_{safe_company}.docx"
        output_path = OUTPUT_DIR / output_filename
        
        # Render CV
        result_path = render_cv(
            template_path=TEMPLATE_PATH,
            template_map_path=TEMPLATE_MAP_PATH,
            selections=selections,
            job=job,
            output_path=output_path
        )
        
        # Update job status
        # In test/dev flows we keep status as queued so same job_id can be rerun repeatedly.
        new_status = "queued" if KEEP_JOB_QUEUED_AFTER_RENDER else "cv_generated"
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE job_status
                SET status = %s, status_updated = NOW()
                WHERE job_id = %s
            """, (new_status, job_id))
            conn.commit()
        conn.close()
        
        return jsonify({
            "cv_path": str(result_path),
            "filename": output_filename,
            "status": "success"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/cv/<int:job_id>/download")
def download_cv(job_id: int):
    """Download the generated CV DOCX."""
    try:
        conn = get_db_connection()
        job = get_job_by_id(conn, job_id)
        conn.close()
        
        if not job:
            return jsonify({"error": f"Job {job_id} not found"}), 404
        
        safe_company = "".join(c if c.isalnum() else "_" for c in job["company"])
        output_filename = f"cv_{job_id}_{safe_company}.docx"
        output_path = OUTPUT_DIR / output_filename
        
        if not output_path.exists():
            return jsonify({"error": "CV not yet generated"}), 404
        
        return send_file(
            output_path,
            as_attachment=True,
            download_name=output_filename,
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/jobs/queued")
def list_queued_jobs():
    """List all jobs with status='queued'."""
    try:
        conn = get_db_connection()
        jobs = get_queued_jobs(conn)
        conn.close()
        return jsonify({"jobs": jobs})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/bullets/add-to-bank", methods=["POST"])
def add_to_bank():
    """Add an approved bullet to the master_bullets.md bank."""
    try:
        data = request.json
        
        bullet_text = data.get("text")
        section = data.get("section")
        subsection = data.get("subsection")
        tags = data.get("tags", [])
        role_families = data.get("role_families", [])
        
        if not bullet_text or not section or not subsection:
            return jsonify({"error": "Missing required fields"}), 400
        
        added = approve_bullet_for_bank(
            bullet_text=bullet_text,
            section=section,
            subsection=subsection,
            tags=tags,
            role_families=role_families,
            bank_path=BULLET_BANK_PATH
        )
        
        if added:
            return jsonify({"status": "added", "text": bullet_text})
        else:
            return jsonify({"status": "duplicate", "text": bullet_text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ──────────────────────────────────────────────────────────────────────────
# Job search preferences
# ──────────────────────────────────────────────────────────────────────────

@app.route("/api/preferences", methods=["GET"])
def get_preferences():
    """Return the current job search preferences.

    Falls back to parsing discovery/config.yaml if no DB row exists yet.
    """
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT search_terms, role_families, location, country_indeed, "
                "results_wanted, hours_old, salary_floor, currency, "
                "excluded_title_keywords, excluded_desc_keywords "
                "FROM user_preferences WHERE user_id = %s",
                (DEFAULT_USER_ID,),
            )
            row = cur.fetchone()
        conn.close()

        if row:
            return jsonify({
                "search_terms": row[0] or [],
                "role_families": row[1] or [],
                "location": row[2],
                "country_indeed": row[3],
                "results_wanted": row[4],
                "hours_old": row[5],
                "salary_floor": row[6],
                "currency": row[7],
                "excluded_title_keywords": row[8] or [],
                "excluded_desc_keywords": row[9] or [],
            })

        # No DB row yet — fall back to config.yaml
        prefs = read_config_yaml(DISCOVERY_CONFIG_PATH)
        return jsonify(prefs)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/preferences", methods=["POST"])
def save_preferences():
    """Upsert user preferences to DB and regenerate discovery/config.yaml."""
    try:
        prefs = PreferencesModel.model_validate(request.json or {})
        data = prefs.model_dump()

        conn = get_db_connection()
        with conn.cursor() as cur:
            # Ensure users row exists
            cur.execute(
                "INSERT INTO users (id) VALUES (%s) ON CONFLICT (id) DO NOTHING",
                (DEFAULT_USER_ID,),
            )
            cur.execute(
                """
                INSERT INTO user_preferences (
                    user_id, search_terms, role_families, location, country_indeed,
                    results_wanted, hours_old, salary_floor, currency,
                    excluded_title_keywords, excluded_desc_keywords, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                )
                ON CONFLICT (user_id) DO UPDATE SET
                    search_terms             = EXCLUDED.search_terms,
                    role_families            = EXCLUDED.role_families,
                    location                 = EXCLUDED.location,
                    country_indeed           = EXCLUDED.country_indeed,
                    results_wanted           = EXCLUDED.results_wanted,
                    hours_old                = EXCLUDED.hours_old,
                    salary_floor             = EXCLUDED.salary_floor,
                    currency                 = EXCLUDED.currency,
                    excluded_title_keywords  = EXCLUDED.excluded_title_keywords,
                    excluded_desc_keywords   = EXCLUDED.excluded_desc_keywords,
                    updated_at               = NOW()
                """,
                (
                    DEFAULT_USER_ID,
                    Json(data["search_terms"]),
                    Json(data["role_families"]),
                    data["location"],
                    data["country_indeed"],
                    data["results_wanted"],
                    data["hours_old"],
                    data["salary_floor"],
                    data["currency"],
                    Json(data["excluded_title_keywords"]),
                    Json(data["excluded_desc_keywords"]),
                ),
            )
        conn.commit()
        conn.close()

        # Regenerate config.yaml from the saved row
        write_config_yaml(data, DISCOVERY_CONFIG_PATH)

        return jsonify({"status": "saved"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ──────────────────────────────────────────────────────────────────────────
# Profile document uploads
# ──────────────────────────────────────────────────────────────────────────

@app.route("/api/profile/uploads", methods=["GET"])
def list_profile_uploads():
    """Return all uploaded documents grouped by upload_type."""
    result: dict[str, list[dict]] = {t: [] for t in _ALLOWED_UPLOAD_TYPES}
    for upload_type in _ALLOWED_UPLOAD_TYPES:
        type_dir = UPLOADS_DIR / upload_type
        if not type_dir.exists():
            continue
        for f in sorted(type_dir.iterdir()):
            if f.is_file():
                result[upload_type].append({
                    "filename": f.name,
                    "size_bytes": f.stat().st_size,
                    "modified_at": datetime.fromtimestamp(
                        f.stat().st_mtime, tz=timezone.utc
                    ).isoformat(),
                })
    return jsonify(result)


@app.route("/api/profile/upload", methods=["POST"])
def upload_profile_file():
    """Accept a file upload and save to profile/users/<id>/uploads/<type>/."""
    upload_type = request.form.get("upload_type", "")
    if upload_type not in _ALLOWED_UPLOAD_TYPES:
        return jsonify({"error": f"upload_type must be one of {sorted(_ALLOWED_UPLOAD_TYPES)}"}), 400

    if "file" not in request.files:
        return jsonify({"error": "No file part in request"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "Empty filename"}), 400

    filename = secure_filename(file.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in _ALLOWED_EXTENSIONS:
        return jsonify({"error": f"Unsupported file type {suffix!r}"}), 400

    dest_dir = UPLOADS_DIR / upload_type
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = unique_destination_path(dest_dir, filename)
    file.save(str(dest))

    return jsonify({
        "status": "uploaded",
        "filename": dest.name,
        "upload_type": upload_type,
        "size_bytes": dest.stat().st_size,
    })


@app.route("/api/profile/uploads/<upload_type>/<filename>", methods=["DELETE"])
def delete_profile_upload(upload_type: str, filename: str):
    """Remove a previously uploaded file."""
    if upload_type not in _ALLOWED_UPLOAD_TYPES:
        return jsonify({"error": "Invalid upload_type"}), 400
    safe = secure_filename(filename)
    path = UPLOADS_DIR / upload_type / safe
    if not path.exists():
        return jsonify({"error": "File not found"}), 404
    path.unlink()
    return jsonify({"status": "deleted", "filename": safe})


@app.route("/api/profile/parse", methods=["POST"])
def parse_profile_upload():
    """Run heuristic section detection on a previously uploaded file.

    Body: {"filename": "cv.docx", "upload_type": "cv"}
    Returns: list of RawSection dicts for the UI reviewer.
    """
    try:
        data = request.json or {}
        filename = secure_filename(data.get("filename", ""))
        upload_type = data.get("upload_type", "cv")

        if not filename:
            return jsonify({"error": "filename is required"}), 400

        file_path = UPLOADS_DIR / upload_type / filename
        if not file_path.exists():
            return jsonify({"error": f"File not found: {filename}"}), 404

        sections = extract_sections(file_path)
        return jsonify({"sections": sections_to_json(sections)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/profile/confirm", methods=["POST"])
def confirm_profile_sections():
    """Condense confirmed sections into the profile markdown files.

    Body:
        {
            "sections": [{"heading", "raw_text", "confirmed_type"}, ...],
            "source_filename": "my_cv.docx"
        }
    Returns: {"updated_files": {"experience.md": ["..."], ...}}
    """
    try:
        data = request.json or {}
        sections = data.get("sections", [])
        source_filename = data.get("source_filename", "upload")

        if not sections:
            return jsonify({"error": "sections list is empty"}), 400

        client = anthropic.Anthropic()
        updated = condense_confirmed_sections(
            sections=sections,
            source_filename=source_filename,
            experience_path=EXPERIENCE_PATH,
            stories_path=STORIES_PATH,
            bullet_bank_path=BULLET_BANK_PATH,
            cover_letters_dir=COVER_LETTERS_DIR,
            log_path=LOG_PATH,
            client=client,
            user_id=DEFAULT_USER_ID,
        )
        active_suggestions.clear()
        return jsonify({"updated_files": updated})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5051, debug=True)
