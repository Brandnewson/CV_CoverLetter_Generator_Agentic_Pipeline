"""Debug bullet mapping for CV Builder.

Checks three things:
1) template_map bullet_xpaths point to valid bullet-like paragraphs in the DOCX.
2) template_map subsection names match master_bullets subsection names (exact + normalized).
3) optional live /api/plan coverage for a queued job.

Usage:
  uv run python scripts/debug_bullet_mapping.py
  uv run python scripts/debug_bullet_mapping.py --user-id 1 --job-id 2
"""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from dotenv import load_dotenv
from lxml import etree

from agent.bullet_selector import load_bullet_bank
from agent.template_extractor import NAMESPACES, unpack_docx, get_paragraph_text


def info(message: str) -> None:
    print(f"[INFO] {message}")


def ok(message: str) -> None:
    print(f"[PASS] {message}")


def warn(message: str) -> None:
    print(f"[WARN] {message}")


def fail(message: str) -> None:
    print(f"[FAIL] {message}")


def resolve_first(paths: list[Path]) -> Path:
    for path in paths:
        if path.exists():
            return path
    return paths[0]


def normalize_subsection_name(name: str) -> str:
    text = name.lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\.?\s*\d{4}\b", "", text)
    text = re.sub(r"\b\d{4}\b", "", text)
    text = re.sub(r"\b(present|current)\b", "", text)
    text = re.sub(r"[|,–—\-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_bullet_like(para: etree._Element, text: str) -> bool:
    has_numpr = bool(para.findall('.//w:pPr/w:numPr', NAMESPACES))
    stripped = (text or "").strip()
    starts_with_glyph = bool(re.match(r"^[▪▫●•◦\-]\s*", stripped))
    return has_numpr or starts_with_glyph


def load_paths(user_id: int) -> dict[str, Path]:
    root = Path(__file__).resolve().parent.parent
    profile = root / "profile"
    user_profile = profile / "users" / str(user_id)

    return {
        "root": root,
        "bullet_bank": resolve_first([
            user_profile / "master_bullets.md",
            profile / "master_bullets.md",
        ]),
        "template_docx": resolve_first([
            user_profile / "cv_template.docx",
            user_profile / "master_cv_template.docx",
            profile / "cv_template.docx",
        ]),
        "template_map": resolve_first([
            user_profile / "template_map.json",
            profile / "template_map.json",
        ]),
    }


def check_template_map_targets(template_docx: Path, template_map: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    temp_dir = Path(tempfile.mkdtemp(prefix="debug_template_"))
    try:
        doc_xml_path = unpack_docx(template_docx, temp_dir)
        root = etree.parse(str(doc_xml_path)).getroot()

        for section in ("work_experience", "technical_projects"):
            for subsection, data in template_map.get(section, {}).items():
                for idx, xpath in enumerate(data.get("bullet_xpaths", []), start=1):
                    try:
                        nodes = root.xpath(xpath, namespaces=NAMESPACES)
                    except Exception as error:
                        issues.append(f"{section}/{subsection} slot {idx}: invalid XPath ({error})")
                        continue

                    if not nodes:
                        issues.append(f"{section}/{subsection} slot {idx}: XPath matched 0 nodes")
                        continue

                    para = nodes[0]
                    text = get_paragraph_text(para)
                    if not is_bullet_like(para, text):
                        issues.append(
                            f"{section}/{subsection} slot {idx}: target not bullet-like -> '{text[:100]}'"
                        )
    finally:
        try:
            import shutil
            shutil.rmtree(temp_dir)
        except Exception:
            pass

    return issues


def check_subsection_coverage(template_map: dict[str, Any], bullet_bank_path: Path) -> dict[str, Any]:
    bullets = load_bullet_bank(bullet_bank_path)

    bank_by_section: dict[str, set[str]] = {
        "work_experience": set(),
        "technical_projects": set(),
    }
    bank_norm_by_section: dict[str, dict[str, list[str]]] = {
        "work_experience": {},
        "technical_projects": {},
    }

    for bullet in bullets:
        section = bullet.get("section")
        subsection = bullet.get("subsection")
        if section not in bank_by_section or not subsection:
            continue
        bank_by_section[section].add(subsection)
        normalized = normalize_subsection_name(subsection)
        bank_norm_by_section[section].setdefault(normalized, []).append(subsection)

    summary: dict[str, Any] = {"missing_exact": [], "matched_normalized": []}

    for section in ("work_experience", "technical_projects"):
        for subsection, data in template_map.get(section, {}).items():
            slot_count = len(data.get("bullet_xpaths", []))
            if subsection in bank_by_section[section]:
                continue

            normalized = normalize_subsection_name(subsection)
            candidates = bank_norm_by_section[section].get(normalized, [])
            if candidates:
                summary["matched_normalized"].append({
                    "section": section,
                    "template_subsection": subsection,
                    "bank_candidates": sorted(set(candidates)),
                    "slot_count": slot_count,
                })
            else:
                summary["missing_exact"].append({
                    "section": section,
                    "template_subsection": subsection,
                    "slot_count": slot_count,
                })

    return summary


def fetch_plan(base_url: str, job_id: int, timeout: int) -> dict[str, Any]:
    url = f"{base_url}/api/plan/{job_id}"
    try:
        with urlopen(url, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"GET {url} failed ({error.code}): {body}") from error
    except URLError as error:
        raise RuntimeError(f"GET {url} failed: {error}") from error


def analyze_plan_slots(plan: dict[str, Any]) -> tuple[int, int]:
    slots = plan.get("work_experience_slots", []) + plan.get("technical_project_slots", [])
    total = len(slots)
    with_candidate = sum(1 for slot in slots if slot.get("current_candidate"))
    return total, with_candidate


def main() -> int:
    parser = argparse.ArgumentParser(description="Debug template map and bullet bank mapping")
    parser.add_argument("--user-id", type=int, default=1)
    parser.add_argument("--job-id", type=int, default=None, help="Optional job_id to validate live /api/plan coverage")
    parser.add_argument("--base-url", default="http://127.0.0.1:5051")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")

    paths = load_paths(args.user_id)
    info(f"bullet_bank: {paths['bullet_bank']}")
    info(f"template_docx: {paths['template_docx']}")
    info(f"template_map: {paths['template_map']}")

    for key in ("bullet_bank", "template_docx", "template_map"):
        if not paths[key].exists():
            fail(f"Missing required file: {paths[key]}")
            return 1

    with open(paths["template_map"], "r", encoding="utf-8") as file_handle:
        template_map = json.load(file_handle)

    work_slots = sum(len(v.get("bullet_xpaths", [])) for v in template_map.get("work_experience", {}).values())
    project_slots = sum(len(v.get("bullet_xpaths", [])) for v in template_map.get("technical_projects", {}).values())
    total_slots = work_slots + project_slots
    ok(f"template_map slots -> work: {work_slots}, projects: {project_slots}, total: {total_slots}")

    issues = check_template_map_targets(paths["template_docx"], template_map)
    if issues:
        warn(f"Found {len(issues)} suspicious template targets:")
        for issue in issues[:20]:
            print(f"  - {issue}")
        if len(issues) > 20:
            print(f"  ... and {len(issues)-20} more")
    else:
        ok("All mapped bullet_xpaths point to bullet-like paragraphs")

    coverage = check_subsection_coverage(template_map, paths["bullet_bank"])

    missing = coverage["missing_exact"]
    normalized = coverage["matched_normalized"]

    if missing:
        warn(f"{len(missing)} template subsections have no matching bullet bank subsection (exact/normalized):")
        for item in missing[:20]:
            print(f"  - [{item['section']}] {item['template_subsection']} ({item['slot_count']} slot(s))")
        if len(missing) > 20:
            print(f"  ... and {len(missing)-20} more")
    else:
        ok("Every template subsection has a matching bullet bank subsection")

    if normalized:
        warn(f"{len(normalized)} subsection(s) would match if names were normalized:")
        for item in normalized[:20]:
            print(
                f"  - [{item['section']}] template='{item['template_subsection']}' -> bank={item['bank_candidates']}"
            )

    if args.job_id is not None:
        try:
            plan = fetch_plan(args.base_url, args.job_id, args.timeout)
            total, with_candidate = analyze_plan_slots(plan)
            ok(f"/api/plan/{args.job_id} -> slots with candidates: {with_candidate}/{total}")
            if total > 0 and with_candidate == 0:
                warn("Plan has slots but no candidates. This usually means subsection name mismatch with bullet bank.")
        except Exception as error:
            fail(str(error))
            return 1

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
