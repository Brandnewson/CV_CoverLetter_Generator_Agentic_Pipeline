"""Inspect DOCX paragraph rows and XPaths for template mapping.

Usage examples:
  uv run python scripts/inspect_template_rows.py
  uv run python scripts/inspect_template_rows.py --contains "Jaguar"
  uv run python scripts/inspect_template_rows.py --contains "lap time" --limit 20
"""

from __future__ import annotations

import argparse
import re
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from lxml import etree

from agent.template_extractor import NAMESPACES, get_element_xpath, get_paragraph_text, unpack_docx


def resolve_first(paths: list[Path]) -> Path:
    for path in paths:
        if path.exists():
            return path
    return paths[0]


def load_template_docx(user_id: int) -> Path:
    root = Path(__file__).resolve().parent.parent
    profile = root / "profile"
    user_profile = profile / "users" / str(user_id)

    return resolve_first([
        user_profile / "cv_template.docx",
        user_profile / "master_cv_template.docx",
        profile / "cv_template.docx",
    ])


def inspect_rows(docx_path: Path, contains: str | None, limit: int) -> int:
    temp_dir = Path(tempfile.mkdtemp(prefix="inspect_rows_"))
    try:
        doc_xml = unpack_docx(docx_path, temp_dir)
        root = etree.parse(str(doc_xml)).getroot()
        paragraphs = root.findall('.//w:p', NAMESPACES)

        print(f"Template: {docx_path}")
        print(f"Paragraph count: {len(paragraphs)}")
        print("-" * 120)
        print("row | numPr | style         | xpath                               | text")
        print("-" * 120)

        count = 0
        pattern = re.compile(re.escape(contains), re.IGNORECASE) if contains else None

        for index, para in enumerate(paragraphs, start=1):
            text = get_paragraph_text(para).strip()
            if not text:
                continue

            if pattern and not pattern.search(text):
                continue

            has_numpr = bool(para.findall('.//w:pPr/w:numPr', NAMESPACES))
            style_node = para.find('.//w:pPr/w:pStyle', NAMESPACES)
            style_name = style_node.get(f"{{{NAMESPACES['w']}}}val") if style_node is not None else ""
            xpath = get_element_xpath(para, root)

            print(f"{index:>3} | {int(has_numpr):>5} | {style_name:<13} | {xpath:<35} | {text[:120]}")
            count += 1

            if count >= limit:
                break

        print("-" * 120)
        print(f"Displayed rows: {count}")
        return 0
    finally:
        try:
            import shutil
            shutil.rmtree(temp_dir)
        except Exception:
            pass


def main() -> int:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")

    parser = argparse.ArgumentParser(description="Inspect DOCX paragraph row to XPath mapping")
    parser.add_argument("--user-id", type=int, default=1)
    parser.add_argument("--contains", type=str, default=None, help="Filter rows by case-insensitive text")
    parser.add_argument("--limit", type=int, default=200, help="Max rows to print")
    args = parser.parse_args()

    docx_path = load_template_docx(args.user_id)
    if not docx_path.exists():
        print(f"ERROR: template docx not found: {docx_path}")
        return 1

    return inspect_rows(docx_path, args.contains, args.limit)


if __name__ == "__main__":
    raise SystemExit(main())
