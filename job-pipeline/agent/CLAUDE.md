# Job Pipeline — CV Generation Skill

## Commands

- "generate cv for job <id>" → run sequence below
- "check job <id>" → uv run python agent/generate_cv.py --job-id <id> --check
- "show queued jobs" → uv run python dashboard/review.py
- "run tests" → uv run pytest tests/ -v
- "how much have I spent?" → uv run python agent/cost_report.py
- "add bullets from job <id>" → use /api/bullets/add-to-bank in the UI

## Generation sequence

1. `uv run python agent/generate_cv.py --job-id <id> --check`
   Fix any errors before proceeding.

2. `uv run python agent/generate_cv.py --job-id <id>`
   Tell user to open http://localhost:5051/build/<id>

3. Wait for user to confirm all slots accepted and CV downloaded.

4. style_updater.py runs automatically after approve. Confirm CLAUDE.md was updated.

5. Tell user the DOCX path and remind them to review in Word before applying.

## Rules
- Never modify profile/users/1/master_cv_template.docx
- Never write to master_bullets.md without explicit user confirmation
- Always print token cost after generation
- Fix failing tests before proceeding with any task

## Approved Examples (motorsport)
<!-- AUTO-UPDATED after each session. Do not edit manually. -->

## Approved Examples (ai-startup)
<!-- AUTO-UPDATED after each session. Do not edit manually. -->

## Approved Examples (forward-deployed-swe)
<!-- AUTO-UPDATED after each session. Do not edit manually. -->

## Approved Examples (general-swe)
<!-- AUTO-UPDATED after each session. Do not edit manually. -->

## Distilled Style Rules
<!-- AUTO-UPDATED after each session. Do not edit manually. -->
