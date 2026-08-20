# Gemini Order Capture Student Kit

This folder now contains teaching material and a runnable starter app for the NLP practice project described in `UniBzLOGonFoppa.pdf`.

The project goal: build an AI-assisted order-capture workflow for food wholesale orders. Students should start from PDFs or scanned order documents and turn them into validated JSON records that can be consumed by an ERP, app, or web workflow. Other input channels such as images or audio can be treated as optional extensions.

Start here:

- `student_kit/docs/project_brief.md` - concise project summary extracted from the PDF.
- `student_kit/docs/01_gemini_sdk_intro.md` - introduction to the Google Gen AI SDK and core Gemini API concepts.
- `student_kit/docs/02_architecture_for_order_capture.md` - target pipeline architecture.
- `student_kit/docs/03_antigravity_workflow.md` - how students should use Google Antigravity.
- `student_kit/docs/04_frontend_options.md` - frontend patterns, including API-key safety.
- `student_kit/docs/05_assessment_rubric.md` - suggested milestones and grading rubric.
- `student_kit/decks/pdf-gemini-order-capture-student-kit.pptx` - classroom presentation that explains the kit and the project path.
- `student_kit/starter_app/` - runnable reference implementation.
- `.agents/` - Google Antigravity rules and workflows for this project workspace.

The starter app runs without a Gemini API key in demo mode, and switches to live Gemini extraction when `GEMINI_API_KEY` is set.

The starter app is intentionally a scaffold, not a mandated architecture. Teams may use FastAPI, Flask, Node, a notebook, or another stack if they keep the same core responsibilities: PDF-first extraction, schema validation, matching, human review, local storage, and feedback capture.
