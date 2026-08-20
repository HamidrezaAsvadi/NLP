# Order-Capture Architecture Rule

This workspace is for the LOGon/Foppa/UniBZ NLP practice project.

The desired system converts messy restaurant/food-wholesale orders into ERP-ready JSON.

## Expected Pipeline

1. Accept PDF or scanned order-document input as the baseline.
2. Treat text, image, or audio channels as optional extensions only after the PDF flow works.
3. Use Gemini for multimodal extraction into a validated extraction object.
4. Validate the extraction schema with Pydantic, JSON Schema, Zod, or an equivalent.
5. Match extracted item phrases against customer history first.
6. Score candidates with fuzzy or semantic matching.
7. Fall back to the full article catalog below the confidence threshold.
8. Show results to a human reviewer.
9. Store final corrections as feedback in local storage.

## Frontend Behavior

The frontend should focus on the reviewer workflow:

- input upload;
- extracted raw text;
- matched article code and description;
- confidence;
- alternatives;
- editable quantity;
- final confirmation;
- feedback.

Avoid marketing pages or decorative layouts. This is an operational review tool.
