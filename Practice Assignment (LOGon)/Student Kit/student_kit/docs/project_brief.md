# Project Brief: AI-Supported Order Capture

## One-Sentence Goal

Build a service that converts PDF-based or scanned food-wholesale order inputs into validated ERP-ready JSON.

## Partners and Context

The PDF describes an innovation project between LOGon, Foppa, and UniBZ:

- LOGon contributes ERP, app, and webshop technology experience.
- Foppa contributes the real business process from food wholesale logistics.
- UniBZ contributes applied informatics, machine learning, NLP, and computer vision expertise.

## Starting Problem

For the course project, the primary starting point is a PDF or scanned order document. In realistic deployments, similar order information may also arrive through other informal channels, but the student prototype should optimize for document extraction first.

- ambiguous product descriptions, abbreviations, dialect, or spelling variants.
- handwriting, scan quality, layout variation, or cropped/rotated pages;
- product names that do not exactly match the catalog.

The current bottleneck is manual transfer into structured systems. This consumes sales and back-office time, introduces transcription errors, and blocks automation.

## Target Output

The AI service should produce a standardized JSON order containing:

- article code;
- article description;
- unit of measure;
- requested quantity or package amount;
- original recognized text;
- confidence/probability;
- explanation for why an item was selected;
- fallback alternative if the main match is below threshold;
- delivery notes such as "deliver tomorrow".

## Required Matching Logic

The PDF frames a three-stage matching logic:

1. Customer template: first compare against what this customer usually orders.
2. Probabilistic scoring: compute match probability using fuzzy matching or a similar method.
3. Fallback search: if confidence is below a threshold such as 85 percent, search the full Foppa article catalog.

## Feedback Loop

After the human operator finalizes the ERP order, the final order plus the original input should be sent back to the service. The service should update customer-specific examples and improve recognition of spelling variants, short names, and dialect over time.

## Suggested Student Scope

A realistic course project can implement a prototype:

- PDF upload or scanned-document upload;
- a small sample catalog and customer history;
- JSON schema validation;
- matching with alternatives;
- a review UI;
- feedback storage as a simple JSONL file or database table;
- tests for the matching module and output schema.
