"""Normalize template_map subsection keys to match bullet-bank subsection headings.

Usage:
  uv run python scripts/normalize_template_map_keys.py --user-id 1
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from agent.bullet_selector import load_bullet_bank


MONTHS_PATTERN = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\.?(?:\s+\d{4})"


def resolve_first(paths: list[Path]) -> Path:
    for path in paths:
        if path.exists():
            return path
    return paths[0]


def normalize_name(text: str) -> str:
    value = text.strip().lower()

    # Remove stack suffix after pipe, e.g. "Project | Python, Rust"
    value = value.split("|", 1)[0]

    # Remove date ranges and standalone years
    value = re.sub(rf"{MONTHS_PATTERN}\s*[–—\-]\s*{MONTHS_PATTERN}", "", value)
    value = re.sub(rf"{MONTHS_PATTERN}", "", value)
    value = re.sub(r"\b\d{4}\b", "", value)

    # Remove common punctuation noise
    value = re.sub(r"[–—\-,:]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def build_section_heading_map(bullet_bank_path: Path) -> dict[str, dict[str, list[str]]]:
    bullets = load_bullet_bank(bullet_bank_path)
    by_section: dict[str, set[str]] = {
        "work_experience": set(),
        "technical_projects": set(),
    }

    for bullet in bullets:
        section = bullet.get("section")
        subsection = bullet.get("subsection")
        if section in by_section and subsection:
            by_section[section].add(subsection)

    normalized: dict[str, dict[str, list[str]]] = {
        "work_experience": {},
        "technical_projects": {},
    }

    for section, headings in by_section.items():
        for heading in sorted(headings):
            key = normalize_name(heading)
            normalized[section].setdefault(key, []).append(heading)

    return normalized


def resolve_paths(user_id: int) -> tuple[Path, Path]:
    root = Path(__file__).resolve().parent.parent
    profile = root / "profile"
    user_profile = profile / "users" / str(user_id)

    template_map_path = resolve_first([
        user_profile / "template_map.json",
        profile / "template_map.json",
    ])

    bullet_bank_path = resolve_first([
        user_profile / "master_bullets.md",
        profile / "master_bullets.md",
    ])

    return template_map_path, bullet_bank_path


def choose_heading(section: str, template_name: str, normalized_map: dict[str, dict[str, list[str]]]) -> str | None:
    section_map = normalized_map.get(section, {})
    key = normalize_name(template_name)
    matches = section_map.get(key, [])

    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        # Prefer exact case-insensitive match among candidates
        for candidate in matches:
            if candidate.lower() == template_name.lower():
                return candidate
        return sorted(matches)[0]

    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize template_map keys to bullet bank headings")
    parser.add_argument("--user-id", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    template_map_path, bullet_bank_path = resolve_paths(args.user_id)

    if not template_map_path.exists():
        print(f"ERROR: template map not found: {template_map_path}")
        return 1
    if not bullet_bank_path.exists():
        print(f"ERROR: bullet bank not found: {bullet_bank_path}")
        return 1

    with open(template_map_path, "r", encoding="utf-8") as file_handle:
        template_map = json.load(file_handle)

    normalized_map = build_section_heading_map(bullet_bank_path)

    updated_map = {
        "work_experience": {},
        "technical_projects": {},
    }

    changes: list[str] = []
    unresolved: list[str] = []

    for section in ("work_experience", "technical_projects"):
        for subsection, data in template_map.get(section, {}).items():
            replacement = choose_heading(section, subsection, normalized_map)
            final_name = replacement or subsection

            # Merge if multiple template keys map to same final heading
            if final_name in updated_map[section]:
                existing = updated_map[section][final_name]
                existing_headers = existing.get("header_xpaths", [])
                existing_bullets = existing.get("bullet_xpaths", [])
                existing["header_xpaths"] = list(dict.fromkeys(existing_headers + data.get("header_xpaths", [])))
                existing["bullet_xpaths"] = list(dict.fromkeys(existing_bullets + data.get("bullet_xpaths", [])))
            else:
                updated_map[section][final_name] = {
                    "header_xpaths": data.get("header_xpaths", []),
                    "bullet_xpaths": data.get("bullet_xpaths", []),
                }

            if replacement and replacement != subsection:
                changes.append(f"[{section}] '{subsection}' -> '{replacement}'")
            elif not replacement and subsection not in normalized_map.get(section, {}):
                unresolved.append(f"[{section}] {subsection}")

    result = {
        "work_experience": updated_map["work_experience"],
        "technical_projects": updated_map["technical_projects"],
    }

    print(f"Template map: {template_map_path}")
    print(f"Bullet bank:  {bullet_bank_path}")
    print()
    print(f"Renamed keys: {len(changes)}")
    for row in changes:
        print(f"  - {row}")

    if unresolved:
        print(f"\nUnresolved keys: {len(unresolved)}")
        for row in unresolved:
            print(f"  - {row}")

    if args.dry_run:
        print("\nDry run only. No files written.")
        return 0

    backup_path = template_map_path.with_suffix(".json.bak")
    backup_path.write_text(json.dumps(template_map, indent=2, ensure_ascii=False), encoding="utf-8")
    template_map_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nBackup written: {backup_path}")
    print("Normalized template map saved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
