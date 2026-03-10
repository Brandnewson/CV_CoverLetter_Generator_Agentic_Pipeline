# CV Hard Rules

## Fixed sections (never modify)
- Section order: Work Experience → Education → Technical Projects →
  Additional Experience → Technical Skills/Soft Skills → Hobbies
- Company names, job titles, dates, locations: never modify
- Tech stack line in Technical Projects (e.g. "| Python, Vehicle Dynamics"): never modify
- Education section: verbatim copy
- Technical Skills section: verbatim copy
- Hobbies section: verbatim copy

## Bullet constraints
- Maximum 120 characters per bullet including spaces (hard reject above 120, retry)
- Soft warning in UI if over 110 characters
- Start with action verb — past tense for past roles, present tense for current role
- Never start with "I"
- British English spelling throughout
- No invented metrics — only numbers already in master_bullets.md or stories.md
- Work Experience: 8–12 bullets per role
- Technical Projects: 2–3 bullets per project

## Keyword deduplication
- Each keyword or technology should appear in at most 2 bullets across the whole CV
- The rephraser must check already_used_keywords before generating

## Banned phrases
- "fast-paced environment", "passion for", "I am excited", "team player",
  "results-driven", "leveraged synergies", "spearheaded", "utilised",
  "passionate about", "dynamic team"
