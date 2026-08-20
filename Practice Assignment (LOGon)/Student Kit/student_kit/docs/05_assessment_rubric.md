# Suggested Assessment Rubric

Total: 100 points.

## Problem Understanding: 15

- 5: describes the business bottleneck clearly;
- 5: identifies input channels and noise sources;
- 5: explains why human review remains necessary.

## Gemini Integration: 20

- 5: uses the current Google Gen AI SDK, not deprecated libraries;
- 5: handles at least one multimodal input type;
- 5: uses structured output or equivalent schema validation;
- 5: handles errors, missing API keys, and invalid model responses.

## Matching and Validation: 25

- 5: implements customer-template first-pass matching;
- 5: computes interpretable match scores;
- 5: searches the full catalog as fallback;
- 5: returns alternatives for uncertain matches;
- 5: includes tests for matching behavior.

## Frontend and Workflow: 15

- 5: supports upload or text input;
- 5: lets the user review and correct proposed order lines;
- 5: does not expose secrets in browser code.

## Feedback Loop: 10

- 5: captures final corrected order data;
- 5: explains how feedback would improve customer-specific recognition.

## Engineering Quality: 15

- 5: clear repository structure and setup instructions;
- 5: meaningful tests and reproducible examples;
- 5: clear discussion of limitations, privacy, and failure modes.

## Optional Bonus

- embeddings for semantic product matching;
- dialect or multilingual synonym handling;
- benchmark dataset with before/after matching quality;
- SQLite or DuckDB feedback store;
- deployment on Cloud Run, a university server, or another protected backend environment.
