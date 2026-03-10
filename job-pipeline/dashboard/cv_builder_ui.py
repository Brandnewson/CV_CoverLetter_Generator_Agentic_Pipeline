"""CV Builder Web UI - Flask application for building CVs."""

import os
from datetime import datetime, timezone
from pathlib import Path

import anthropic
import psycopg2
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, send_file, url_for
from flask_cors import CORS

from agent.bullet_rephraser import rephrase_bullet
from agent.bullet_selector import build_selection_plan, load_bullet_bank
from agent.cv_renderer import render_cv
from agent.jd_parser import classify_role_family, classify_seniority
from agent.story_drafter import approve_bullet_for_bank
from agent.template_extractor import load_template_map
from agent.validators import UserSelections

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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5051, debug=True)
