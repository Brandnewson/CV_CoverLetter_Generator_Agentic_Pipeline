# Job Pipeline — CV Generation Skill

## Commands

- "show queued jobs" → `uv run python dashboard/review.py`
- "start the builder UI" → `uv run python dashboard/cv_builder_ui.py` then open http://localhost:5051
- "run tests" → `uv run pytest tests/ -v`
- "how much have I spent?" → `uv run python agent/cost_report.py`
- "add bullets from job <id>" → use /api/bullets/add-to-bank in the UI
- "run diagnostics" → `uv run python scripts/debug_bullet_mapping.py --job-id <id>`

## Generation sequence

1. Ensure job is in 'queued' status (use `dashboard/review.py` or set directly in DB).

2. Start the builder: `uv run python dashboard/cv_builder_ui.py`
   Open http://localhost:5051/build/<id>

3. Review each slot. Accept or rephrase bullets until all slots are approved.

4. Click "Generate CV" — the DOCX is saved to `output/`.

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
