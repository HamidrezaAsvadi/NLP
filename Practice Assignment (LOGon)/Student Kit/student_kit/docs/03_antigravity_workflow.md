# Google Antigravity Workflow for Students

Google Antigravity is an agentic development environment. It is not the runtime SDK for the project. Students should use it to plan, implement, test, and verify their code, while the application itself uses the Google Gen AI SDK, Gemini API, and local storage such as JSONL, SQLite, or DuckDB.

## First Setup

1. Install Antigravity from the official site: https://antigravity.google/
2. Open this project folder.
3. Let Antigravity index the workspace.
4. Review the `.agents/rules/` and `.agents/workflows/` files.
5. Use "Request Review" for terminal permissions at first.
6. Keep terminal sandboxing enabled when available.

## Recommended Agent Prompts

Use small, verifiable tasks:

```text
Read student_kit/docs/project_brief.md and student_kit/starter_app/README.md.
Implement support for PDF uploads in the extraction endpoint.
Show me the plan before editing files.
After implementation, run the relevant tests and summarize the exact files changed.
```

```text
Improve the matching score for German/Italian food-product abbreviations.
Do not change the API schema.
Add tests that demonstrate the improvement.
```

```text
Review the frontend for the order-review workflow.
Make the UI show alternatives and confidence clearly.
Do not expose GEMINI_API_KEY in browser code.
```

## Suggested Student Routine

For each feature:

1. Ask Antigravity for a plan.
2. Approve only the parts that match the assignment.
3. Let the agent edit a small file set.
4. Run tests.
5. Inspect diffs.
6. Try the frontend manually.
7. Commit with a meaningful message.

## Safety Rules

Students should configure Antigravity conservatively:

- use review prompts for terminal commands;
- do not allow destructive commands such as `rm -rf`;
- keep the agent inside the workspace;
- never store API keys in committed files;
- treat uploaded customer data as sensitive;
- ask the agent to create artifacts: plan, changed files, test output, and screenshots.

## Why This Matters

The assignment itself is about turning unstructured real-world data into reliable business data. Students should apply the same discipline to AI-assisted development: agents can speed up work, but the human team remains responsible for correctness, privacy, and downstream ERP behavior.

## Sources

- Google Developers Blog introduction to Antigravity: https://developers.googleblog.com/en/build-with-google-antigravity-our-new-agentic-development-platform/
- Google Codelab, Getting Started with Google Antigravity: https://codelabs.developers.google.com/getting-started-google-antigravity
