# Workflow: Implement Gemini Feature

Use this workflow when adding an extraction, matching, or Gemini API feature.

## Steps

1. Read `docs/project_brief.md`.
2. Read the relevant starter app files in `starter_app/app/`.
3. Produce a short plan with:
   - files to change;
   - expected API behavior;
   - tests to add or run.
4. Implement the smallest useful change.
5. Run relevant tests.
6. Summarize:
   - changed files;
   - how to run it;
   - remaining limitations.

## Constraints

- Keep `GEMINI_API_KEY` server-side.
- Use `google-genai`.
- Validate Gemini output before matching.
- Preserve the existing endpoint shape unless the task requires a change.
