# Student Kit

This kit is designed to get students productive quickly while keeping the architecture close to the LOGon/Foppa assignment.

## Quick Start

Run the starter app locally:

```bash
cd starter_app
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest  # verify setup
python app.py  # start the server
```

Then open `http://127.0.0.1:8000`.

## Default Path vs Advanced Path

**Default path:** If unsure, use the starter app as-is and extend it.

**Advanced path:** Only swap the stack or architecture if your team has a clear justification. Document your reasoning.

## Learning Path

1. Use `decks/pdf-gemini-order-capture-student-kit.pptx` as the classroom walkthrough after the LOGon presentation.
2. Read `docs/project_brief.md` to understand the problem.
3. Read `docs/01_gemini_sdk_intro.md` and run the first SDK examples.
4. Study `docs/02_architecture_for_order_capture.md` before designing a solution.
5. Open the folder in Google Antigravity and use the workflows in `.agents/workflows/`.
6. Run and extend `starter_app/`.
7. Review `docs/06_ci_cd_flow.md` later, when the team is ready to push and deploy.
8. Use `docs/05_assessment_rubric.md` as a checklist before submission.

## Recommended Student Deliverable

Each student team should deliver:

- a working extraction API for PDFs or scanned order documents;
- a structured JSON schema for ERP order handoff;
- a matching module with customer-template matching, probabilistic scoring, and fallback search;
- a small frontend for upload, review, correction, and feedback submission;
- tests for matching and schema validation;
- a short report explaining tradeoffs, failure cases, and feedback-loop design.

## Tooling Choice

Use Google products for the AI workflow:

- Google Gen AI SDK for Python or JavaScript/TypeScript;
- Gemini API for PDF, image, and document understanding;
- Google Antigravity as the agentic development environment.

## Architecture Choice

The starter app is a reference implementation, not a requirement. It uses a Python backend and schema validation because that is a small, inspectable way to demonstrate the pipeline.

Teams should discuss architecture tradeoffs with Gemini and Antigravity before committing to a stack. They may choose FastAPI, Flask, Node/TypeScript, a notebook, a CLI, or another reasonable structure. What matters is that the solution keeps API keys safe, validates model output, supports matching and review, stores feedback locally, and produces ERP-ready JSON.

For local storage, start with one of these:

- JSONL for the simplest feedback log;
- SQLite for a small catalog, customer templates, and feedback tables;
- DuckDB for local analytics over larger tabular files;
- Chroma or FAISS only if the team adds embedding-based matching.

## Known Limitations of the Starter App

- Demo extraction uses hardcoded/mock data. Replace it with live Gemini calls once credentials are configured.
- PDF parsing quality varies by document type, scan quality, layout, and handwriting.
- Matching logic is deliberately simplistic. Extend synonyms, fuzzy matching, customer-history boosts, or semantic matching.
- There is no real persistence beyond JSONL append.
- No evaluation dataset is provided yet.
- `feedback.jsonl` has no deduplication or file locking.

## Submission Checklist

- [ ] Repository URL
- [ ] Setup instructions: how to install and run
- [ ] Required environment variables listed
- [ ] At least one sample input PDF included
- [ ] `pytest` passes
- [ ] Short report section in README: approach, decisions, limitations
- [ ] Screenshots or demo link, optional but recommended
