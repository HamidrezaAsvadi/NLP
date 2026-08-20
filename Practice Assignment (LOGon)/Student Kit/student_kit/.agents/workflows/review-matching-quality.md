# Workflow: Review Matching Quality

Use this workflow when improving article matching.

## Steps

1. Inspect `starter_app/app/matching.py`.
2. Inspect `starter_app/app/sample_data.py`.
3. Identify one weakness in the current scoring.
4. Add or adjust tests in `starter_app/tests/test_matching.py`.
5. Improve the scoring function.
6. Run tests.
7. Explain the behavior before and after the change.

## Acceptance Criteria

- Customer-history products receive a reasonable boost.
- Fallback search can still find products outside the customer template.
- Low-confidence results include alternatives.
- The score remains explainable to a business user.
