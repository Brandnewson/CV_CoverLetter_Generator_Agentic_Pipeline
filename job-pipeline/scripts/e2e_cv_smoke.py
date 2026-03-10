"""End-to-end smoke checker for Stage 2 CV pipeline.

Validates flow from queued job to plan generation, optional rephrase,
optional approve/render, and optional DOCX download.

Usage:
  uv run python scripts/e2e_cv_smoke.py
  uv run python scripts/e2e_cv_smoke.py --job-id 7 --approve --rephrase --download
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import psycopg2
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def get_default_user_id() -> int:
    raw = os.getenv("DEFAULT_USER_ID", "1")
    try:
        return int(raw)
    except ValueError:
        return 1


def resolve_profile_asset(candidates: list[Path]) -> Path:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def get_profile_asset_paths() -> dict[str, Path]:
    user_id = get_default_user_id()
    profile_dir = PROJECT_ROOT / "profile"
    user_dir = profile_dir / "users" / str(user_id)

    return {
        "bullet_bank": resolve_profile_asset([
            user_dir / "master_bullets.md",
            profile_dir / "master_bullets.md",
        ]),
        "template": resolve_profile_asset([
            user_dir / "cv_template.docx",
            user_dir / "master_cv_template.docx",
            profile_dir / "cv_template.docx",
        ]),
        "template_map": resolve_profile_asset([
            user_dir / "template_map.json",
            profile_dir / "template_map.json",
        ]),
    }


def _print_pass(message: str) -> None:
    print(f"[PASS] {message}")


def _print_fail(message: str) -> None:
    print(f"[FAIL] {message}")


def _print_info(message: str) -> None:
    print(f"[INFO] {message}")


def http_get_json(url: str, timeout: int) -> dict[str, Any]:
    try:
        with urlopen(url, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body)
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"GET {url} failed ({error.code}): {body}") from error
    except URLError as error:
        raise RuntimeError(f"GET {url} failed: {error}") from error


def http_post_json(url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body)
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"POST {url} failed ({error.code}): {body}") from error
    except URLError as error:
        raise RuntimeError(f"POST {url} failed: {error}") from error


def http_get_raw(url: str, timeout: int) -> tuple[bytes, str]:
    try:
        with urlopen(url, timeout=timeout) as response:
            content_type = response.headers.get("Content-Type", "")
            return response.read(), content_type
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"GET {url} failed ({error.code}): {body}") from error
    except URLError as error:
        raise RuntimeError(f"GET {url} failed: {error}") from error


def assert_required_files() -> None:
    assets = get_profile_asset_paths()
    for file_path in assets.values():
        if not file_path.exists():
            raise RuntimeError(f"Missing required file: {file_path}")
    _print_pass(
        "Profile assets present "
        f"(bullet bank: {assets['bullet_bank'].name}, template: {assets['template'].name}, map: {assets['template_map'].name})"
    )


def db_preflight() -> int:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL missing in environment")

    with psycopg2.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM job_status WHERE status = 'queued'")
            queued_count = cur.fetchone()[0]

    _print_pass(f"Database reachable; queued jobs in DB: {queued_count}")
    return queued_count


def pick_job_id(base_url: str, timeout: int, requested_job_id: int | None) -> int:
    queued = http_get_json(f"{base_url}/api/jobs/queued", timeout)
    jobs = queued.get("jobs", [])

    if not isinstance(jobs, list):
        raise RuntimeError("/api/jobs/queued returned invalid payload")

    _print_pass(f"API reachable; /api/jobs/queued returned {len(jobs)} job(s)")

    if requested_job_id is not None:
        if not any(job.get("id") == requested_job_id for job in jobs):
            raise RuntimeError(f"Requested job_id={requested_job_id} not present in queued list")
        return requested_job_id

    if not jobs:
        raise RuntimeError("No queued jobs found. Queue at least one job via dashboard/review.py")

    return int(jobs[0]["id"])


def extract_approved_bullets(plan: dict[str, Any]) -> list[dict[str, Any]]:
    slots = plan.get("work_experience_slots", []) + plan.get("technical_project_slots", [])
    approved: list[dict[str, Any]] = []
    for slot in slots:
        candidate = slot.get("current_candidate")
        if not candidate:
            continue
        approved.append(
            {
                "slot_index": slot.get("slot_index"),
                "section": slot.get("section"),
                "subsection": slot.get("subsection"),
                "text": candidate.get("text"),
                "source": candidate.get("source", "master_bullets"),
                "rephrase_generation": candidate.get("rephrase_generation", 0),
            }
        )
    return approved


def assert_template_map_has_slots() -> int:
    map_path = get_profile_asset_paths()["template_map"]
    with open(map_path, "r", encoding="utf-8") as file_handle:
        template_map = json.load(file_handle)

    work_sections = template_map.get("work_experience", {})
    project_sections = template_map.get("technical_projects", {})

    total_slots = 0
    for section_data in list(work_sections.values()) + list(project_sections.values()):
        total_slots += len(section_data.get("bullet_xpaths", []))

    if total_slots == 0:
        raise RuntimeError(
            "template_map.json contains 0 bullet slots. Frontend will render empty builder. "
            "Regenerate template map from a CV template containing detectable bullet lines."
        )

    _print_pass(f"Template map contains {total_slots} bullet slot(s)")
    return total_slots


def run(args: argparse.Namespace) -> int:
    load_dotenv(PROJECT_ROOT / ".env")

    _print_info(f"Using base URL: {args.base_url}")
    _print_info(f"Using Claude model: {os.getenv('CLAUDE_MODEL', '<default>')}")

    assert_required_files()
    assert_template_map_has_slots()
    db_preflight()

    job_id = pick_job_id(args.base_url, args.timeout, args.job_id)
    _print_info(f"Selected job_id={job_id}")

    plan = http_get_json(f"{args.base_url}/api/plan/{job_id}", args.timeout)

    required_keys = [
        "job_id",
        "job_title",
        "company",
        "work_experience_slots",
        "technical_project_slots",
        "projects_to_hide",
    ]
    for key in required_keys:
        if key not in plan:
            raise RuntimeError(f"Plan payload missing key: {key}")

    total_slots = len(plan.get("work_experience_slots", [])) + len(plan.get("technical_project_slots", []))
    if total_slots == 0 and not args.allow_zero_slots:
        raise RuntimeError(
            "Plan generated with 0 slots. This means template extraction/mapping did not find bullet zones. "
            "Use --allow-zero-slots only if you intentionally want to skip this check."
        )

    _print_pass(f"Plan generated for job {plan.get('job_id')} with {total_slots} slot(s)")

    if args.rephrase and total_slots > 0:
        first_slot = (plan.get("work_experience_slots", []) + plan.get("technical_project_slots", []))[0]
        rephrase_payload = {
            "job_id": job_id,
            "slot_index": first_slot.get("slot_index"),
            "section": first_slot.get("section"),
            "subsection": first_slot.get("subsection"),
        }
        rephrased = http_post_json(f"{args.base_url}/api/rephrase", rephrase_payload, args.timeout)
        if "text" not in rephrased:
            raise RuntimeError("Rephrase response missing 'text'")
        _print_pass("Rephrase endpoint returned a bullet candidate")

    if args.approve:
        approved_bullets = extract_approved_bullets(plan)
        approve_payload = {
            "user_id": int(plan.get("user_id", 1)),
            "approved_bullets": approved_bullets,
            "hidden_projects": plan.get("projects_to_hide", []),
        }
        approve_response = http_post_json(f"{args.base_url}/api/approve/{job_id}", approve_payload, args.timeout)

        if approve_response.get("status") != "success":
            raise RuntimeError(f"Approve failed: {approve_response}")

        _print_pass(f"Approve/render succeeded: {approve_response.get('filename')}")

        if args.download:
            content, content_type = http_get_raw(f"{args.base_url}/api/cv/{job_id}/download", args.timeout)
            if "officedocument.wordprocessingml.document" not in content_type:
                raise RuntimeError(f"Unexpected download content-type: {content_type}")
            if len(content) < 100:
                raise RuntimeError("Downloaded DOCX appears too small/corrupt")
            _print_pass("Download endpoint returned DOCX payload")

    print("\nSmoke check completed successfully.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="End-to-end smoke checker for CV pipeline")
    parser.add_argument("--base-url", default="http://127.0.0.1:5051", help="Running Flask base URL")
    parser.add_argument("--job-id", type=int, default=None, help="Queued job id to test")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout seconds")
    parser.add_argument("--rephrase", action="store_true", help="Test /api/rephrase on first slot")
    parser.add_argument("--approve", action="store_true", help="Test /api/approve and render")
    parser.add_argument("--download", action="store_true", help="With --approve, also test /api/cv/{job_id}/download")
    parser.add_argument(
        "--allow-zero-slots",
        action="store_true",
        help="Allow smoke check to pass even when plan has zero slots",
    )
    return parser.parse_args()


if __name__ == "__main__":
    try:
        raise SystemExit(run(parse_args()))
    except Exception as error:
        _print_fail(str(error))
        raise SystemExit(1)
