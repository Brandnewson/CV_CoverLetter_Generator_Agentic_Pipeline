"""Template extractor - one-time tool to map bullet zones in DOCX template."""

import argparse
import json
import re
import shutil
import zipfile
from pathlib import Path
from typing import Optional

from lxml import etree


# DOCX XML namespaces
NAMESPACES = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
}

# Bullet characters to look for
BULLET_CHARS = ['▪', '▫', '●', '•', '◦', '-', '\u25aa', '\u25a0', '\u25ab', '\u25cf', '\u2022']


def unpack_docx(docx_path: Path, output_dir: Path) -> Path:
    """Unpack DOCX ZIP. Return path to word/document.xml."""
    if not docx_path.exists():
        raise FileNotFoundError(f"DOCX not found: {docx_path}")
    
    # Clean output directory if it exists
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    
    # DOCX is a ZIP file
    with zipfile.ZipFile(docx_path, 'r') as zf:
        zf.extractall(output_dir)
    
    doc_xml_path = output_dir / "word" / "document.xml"
    if not doc_xml_path.exists():
        raise FileNotFoundError(f"document.xml not found in DOCX: {docx_path}")
    
    return doc_xml_path


def get_paragraph_text(para_element: etree._Element) -> str:
    """Extract all text content from a paragraph element."""
    texts = []
    for text_elem in para_element.iter('{%s}t' % NAMESPACES['w']):
        if text_elem.text:
            texts.append(text_elem.text)
    return ''.join(texts)


def get_element_xpath(element: etree._Element, root: etree._Element) -> str:
    """Generate a reproducible XPath for an element."""
    tree = element.getroottree()
    return tree.getpath(element)


def has_word_list_numbering(para_element: Optional[etree._Element]) -> bool:
    """Check whether paragraph uses Word numbering/bullet metadata (w:numPr)."""
    if para_element is None:
        return False
    return bool(para_element.findall('.//w:pPr/w:numPr', NAMESPACES))


def is_bullet_paragraph(text: str, para_element: Optional[etree._Element] = None) -> bool:
    """Check if paragraph is a bullet (visible bullet char or Word list metadata)."""
    if has_word_list_numbering(para_element):
        return True

    stripped = text.strip()
    if not stripped:
        return False
    return any(stripped.startswith(char) for char in BULLET_CHARS)


def is_section_header(text: str) -> Optional[str]:
    """Check if text is a section header. Returns normalised section name or None."""
    text_lower = text.lower().strip()
    if not text_lower:
        return None

    # Section headers are typically short standalone lines.
    if len(text_lower) > 60:
        return None

    normalized = re.sub(r'\s+', ' ', text_lower).strip(' :|-')

    if normalized in {'work experience', 'employment', 'professional experience'}:
        return 'work_experience'
    elif normalized in {'technical projects', 'technical project', 'projects', 'personal projects', 'personal project'}:
        return 'technical_projects'
    elif normalized in {'education'}:
        return 'education'
    elif normalized in {'additional experience'}:
        return 'additional_experience'
    elif normalized in {'skills', 'technical skills', 'technical skills, soft skills & certifications', 'certifications & awards'}:
        return 'skills'
    
    return None


def detect_subsection_title(text: str, paragraphs_context: list) -> bool:
    """
    Heuristic to detect if a paragraph is a subsection title (company/project name).
    Typically: non-bullet, bold or larger font, or standalone short line before bullets.
    """
    stripped = text.strip()
    if not stripped:
        return False
    
    # Not a bullet line
    if is_bullet_paragraph(text):
        return False
    
    # Reasonably short (company/project names usually <100 chars)
    if len(stripped) > 100:
        return False
    
    # Not a section header
    if is_section_header(text):
        return False
    
    return True


def find_bullet_nodes(doc_xml_path: Path) -> dict:
    """
    Parse with lxml. Find all <w:p> containing bullet characters.
    Group by: section → subsection → bullets in document order.
    
    Return structure:
    {
        "work_experience": {
            "Company Name": {
                "header_xpaths": [...],  # company, title, stack lines
                "bullet_xpaths": [...]
            }
        },
        "technical_projects": {
            "Project Name": {
                "header_xpaths": [...],
                "bullet_xpaths": [...]
            }
        }
    }
    """
    tree = etree.parse(str(doc_xml_path))
    root = tree.getroot()
    
    # Find all paragraphs
    paragraphs = root.findall('.//w:p', NAMESPACES)
    
    result = {
        'work_experience': {},
        'technical_projects': {},
    }
    
    current_section = None
    current_subsection = None
    header_buffer = []  # Store potential header lines before bullets
    
    for para in paragraphs:
        text = get_paragraph_text(para)
        xpath = get_element_xpath(para, root)
        
        # Check for section headers
        section = is_section_header(text)
        if section:
            current_section = section
            current_subsection = None
            header_buffer = []
            continue
        
        # Skip if no section context yet
        if current_section is None:
            continue
        
        # Skip if not in a section we care about
        if current_section not in result:
            continue
        
        # Check for bullet line
        if is_bullet_paragraph(text, para):
            # If we have header buffer but no subsection, create one
            if current_subsection is None and header_buffer:
                # First header line is the subsection name
                subsection_name = header_buffer[0][0].strip()
                if subsection_name:
                    current_subsection = subsection_name
                    result[current_section][current_subsection] = {
                        'header_xpaths': [h[1] for h in header_buffer],
                        'bullet_xpaths': []
                    }
                header_buffer = []
            
            # Add bullet to current subsection
            if current_subsection and current_subsection in result[current_section]:
                result[current_section][current_subsection]['bullet_xpaths'].append(xpath)
        
        elif detect_subsection_title(text, []):
            # Potential new subsection header
            if text.strip():
                # If we already have a subsection with bullets, this starts a new one
                if current_subsection and result[current_section].get(current_subsection, {}).get('bullet_xpaths'):
                    # Commit current subsection, start new header buffer
                    current_subsection = None
                    header_buffer = [(text, xpath)]
                else:
                    # Still building header buffer
                    header_buffer.append((text, xpath))
    
    return result


def save_template_map(template_map: dict, output_path: Path) -> None:
    """Save template map to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(template_map, f, indent=2, ensure_ascii=False)


def load_template_map(map_path: Path) -> dict:
    """Load template map from JSON file."""
    with open(map_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def print_template_summary(template_map: dict) -> None:
    """Print a human-readable summary of the template map."""
    print("\n" + "=" * 60)
    print("TEMPLATE EXTRACTION SUMMARY")
    print("=" * 60)
    
    total_bullets = 0
    for section, subsections in template_map.items():
        section_bullets = sum(len(s.get('bullet_xpaths', [])) for s in subsections.values())
        total_bullets += section_bullets
        
        print(f"\n{section.upper().replace('_', ' ')} ({len(subsections)} subsections, {section_bullets} bullets)")
        print("-" * 40)
        
        for subsection, data in subsections.items():
            bullet_count = len(data.get('bullet_xpaths', []))
            header_count = len(data.get('header_xpaths', []))
            print(f"  • {subsection}: {bullet_count} bullets, {header_count} headers")
    
    print("\n" + "=" * 60)
    print(f"TOTAL: {total_bullets} bullet slots found")
    print("=" * 60 + "\n")


def main():
    """
    CLI: uv run python agent/template_extractor.py --user-id 1
    Reads profile/users/1/master_cv_template.docx
    Prints: sections found, subsections, bullet counts
    Asks: "Does this look right? (y/n)"
    On y: writes template_map.json
    """
    parser = argparse.ArgumentParser(description="Extract bullet zones from CV template")
    parser.add_argument("--user-id", type=int, default=1, help="User ID (default: 1)")
    parser.add_argument("--force", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()
    
    # Paths
    base_dir = Path(__file__).parent.parent
    user_dir = base_dir / "profile" / "users" / str(args.user_id)
    docx_path = user_dir / "master_cv_template.docx"
    output_dir = user_dir / ".template_unpacked"
    map_path = user_dir / "template_map.json"
    
    print(f"Extracting template for user {args.user_id}")
    print(f"Source: {docx_path}")
    
    if not docx_path.exists():
        print(f"ERROR: Template file not found: {docx_path}")
        print("Please place your master CV template at that location.")
        return 1
    
    # Unpack DOCX
    print("\nUnpacking DOCX...")
    doc_xml_path = unpack_docx(docx_path, output_dir)
    print(f"Unpacked to: {output_dir}")
    
    # Find bullet nodes
    print("\nScanning for bullet nodes...")
    template_map = find_bullet_nodes(doc_xml_path)
    
    # Print summary
    print_template_summary(template_map)
    
    # Confirm
    if not args.force:
        response = input("Does this look right? (y/n): ").strip().lower()
        if response != 'y':
            print("Aborted. No files written.")
            return 1
    
    # Save
    save_template_map(template_map, map_path)
    print(f"Template map saved to: {map_path}")
    
    # Clean up unpacked directory
    shutil.rmtree(output_dir)
    print("Cleaned up temporary files.")
    
    return 0


if __name__ == "__main__":
    exit(main())
