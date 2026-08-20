# def3_new_schablone_upgrade.md

Because the complete project rewrite requires extensive modifications across
load_schablone(), best_fuzzy_match(), enrich_with_schablone(), Gemini prompting,
and confidence scoring, this document summarizes the exact changes to implement.

Key changes:
1. Load new columns:
   - DescriptionItalian
   - SumQty
   - SumQtyBox
   - LastDocDatum
   - LastorderedQty

2. Create:
   - SearchText = DescriptionGerman + DescriptionItalian
   - DaysSinceLastOrder

3. Use combined ranking:
   score =
     0.50 * fuzzy +
     0.10 * trigram +
     0.25 * history +
     0.15 * recency

4. Use local matching instead of sending large catalogs to Gemini.

5. Keep RLMatcher unchanged.

The uploaded def3.py is large (~900 lines). A full production rewrite should be
performed directly against the source repository to avoid truncation or accidental
regressions.
