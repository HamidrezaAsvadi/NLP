# Gemini Course Guardrails

Apply these rules to all agent work in this student kit.

## SDK and API

- Use the current Google Gen AI SDK:
  - Python: `from google import genai`
  - JavaScript/TypeScript: `@google/genai`
- Do not use the deprecated `google-generativeai` Python package.
- Keep model names configurable with an environment variable such as `GEMINI_MODEL`.

## Secrets

- Never write `GEMINI_API_KEY` into source files.
- Never expose Gemini API keys in frontend/browser code.
- Use `.env.example` for documentation only.
- Prefer server-side or local Python Gemini calls for this course project.

## Output Discipline

- Gemini extraction must produce structured JSON.
- Validate all model output with Pydantic, Zod, JSON Schema, or equivalent schema validation.
- Do not send an order to ERP-style output unless every item has a product code, quantity, unit, confidence, and explanation.

## Matching

- First search the customer template.
- Then compute an interpretable score.
- If the score is below the threshold, search the full catalog.
- Return alternatives for low-confidence matches.

## Verification

- Run relevant tests after code changes.
- Add or update tests when changing matching logic.
- Report changed files and verification results.
