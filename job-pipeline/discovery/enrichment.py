"""Discovery-time enrichment for job/company text and keywords."""

import json
import re
from datetime import datetime, timezone

import anthropic

from agent.config import get_claude_model


ENRICHMENT_VERSION = "v1"


TECH_PATTERNS = {
    "python": [r"\bpython\b"],
    "javascript": [r"\bjavascript\b", r"\bjs\b"],
    "typescript": [r"\btypescript\b", r"\bts\b"],
    "java": [r"\bjava\b"],
    "c++": [r"\bc\+\+\b"],
    "c#": [r"\bc#\b", r"\bcsharp\b"],
    "go": [r"\bgolang\b", r"\bgo\b"],
    "rust": [r"\brust\b"],
    "sql": [r"\bsql\b", r"\bpostgres\b", r"\bpostgresql\b"],
    "react": [r"\breact\b"],
    "node.js": [r"\bnode\b", r"\bnode\.js\b"],
    "docker": [r"\bdocker\b"],
    "kubernetes": [r"\bkubernetes\b", r"\bk8s\b"],
    "aws": [r"\baws\b"],
    "azure": [r"\bazure\b"],
    "gcp": [r"\bgcp\b", r"\bgoogle cloud\b"],
    "terraform": [r"\bterraform\b"],
    "ci/cd": [r"\bci/cd\b", r"\bcontinuous integration\b", r"\bcontinuous delivery\b"],
    "llms": [r"\bllm\b", r"\blarge language model\b", r"\bgenerative ai\b"],
    "pytorch": [r"\bpytorch\b"],
    "tensorflow": [r"\btensorflow\b"],
}


SKILL_ABILITY_PROMPT = """You are extracting concise hiring signals from a job description.

Return valid JSON ONLY with this exact schema:
{{
  "skills": ["..."],
  "abilities": ["..."]
}}

Rules:
- lowercase all entries
- each item is 1-4 words
- max 12 skills and max 12 abilities
- no duplicates
- no generic filler words
- skills = soft skills + architecture/problem-solving skills
- abilities = operational expectations and responsibilities the company asks for

Job description:
{job_description}
"""


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned


def extract_technologies_deterministic(job_description: str) -> list[str]:
    """Deterministically extract technology keywords from text."""
    text = job_description.lower()
    technologies: list[str] = []

    for tech, patterns in TECH_PATTERNS.items():
        if any(re.search(pattern, text) for pattern in patterns):
            technologies.append(tech)

    return technologies


def extract_skills_and_abilities_with_claude(job_description: str) -> dict:
    """Use Claude once to extract skills and abilities."""
    if not job_description or len(job_description.strip()) < 50:
        return {"skills": [], "abilities": []}
    
    client = anthropic.Anthropic()
    prompt = SKILL_ABILITY_PROMPT.format(job_description=job_description[:9000])

    try:
        response = client.messages.create(
            model=get_claude_model(),
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )

        content = response.content[0].text.strip()
        
        # Remove markdown code blocks if present
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\n?", "", content)
            content = re.sub(r"\n?```$", "", content)
        
        # Find JSON object in response (Claude sometimes adds explanation text)
        json_match = re.search(r'\{[^{}]*"skills"[^{}]*"abilities"[^{}]*\}', content, re.DOTALL)
        if not json_match:
            # Try to find any JSON object
            json_match = re.search(r'\{[\s\S]*\}', content)
        
        if json_match:
            content = json_match.group(0)
        
        data = json.loads(content)
        
        if not isinstance(data, dict):
            return {"skills": [], "abilities": []}
        
        skills = [str(item).strip().lower() for item in data.get("skills", []) if str(item).strip()]
        abilities = [str(item).strip().lower() for item in data.get("abilities", []) if str(item).strip()]

        return {
            "skills": list(dict.fromkeys(skills))[:12],
            "abilities": list(dict.fromkeys(abilities))[:12],
        }
    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as e:
        print(f"Enrichment LLM parsing error: {e}")
        return {"skills": [], "abilities": []}
    except Exception as e:
        print(f"Enrichment LLM call failed: {e}")
        return {"skills": [], "abilities": []}


def build_enrichment(job_description_raw: str) -> dict:
    """Build enrichment payload for a job description."""
    normalized_description = _normalize_text(job_description_raw)
    technologies = extract_technologies_deterministic(normalized_description)
    llm_enrichment = extract_skills_and_abilities_with_claude(normalized_description)

    return {
        "technologies": technologies,
        "skills": llm_enrichment.get("skills", []),
        "abilities": llm_enrichment.get("abilities", []),
        "version": ENRICHMENT_VERSION,
        "enriched_at": datetime.now(timezone.utc).isoformat(),
    }
