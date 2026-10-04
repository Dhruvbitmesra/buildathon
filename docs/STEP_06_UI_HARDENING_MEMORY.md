# Step 6 — Review UI, Held-out Evaluation, Hardening, Mapping Memory

## 1. Human approval interface (FR-1, FR-5)

`app/ui/streamlit_app.py` (run: `uv run streamlit run app/ui/streamlit_app.py`).

| Tab | Content |
|---|---|
| Workflow | Live Graphviz diagram of the agents and their state, incl. the re-reasoning loop; agent trace |
| 1 · Sheets | Ranked sheet manifest, header row, rows excluded from the table |
| 2 · Mapping | Source -> target, confidence bar, method, flags; mapping JSON |
| 3 · Data quality | Intake score, issues by type/severity, per-field completeness and validity, per-row flags |
| 4 · Review | Queue with filters; per item: rationale, uncertainty, confidence, before/after sample, decision history; Approve / Reject (note required) / Edit (typed value, per-row editor, or target field) / Escalate; **Approve All** for lossless items >= 0.90 |
| 5 · Preview & export | Before/after side by side; export disabled until nothing is pending; downloads for `Cleaned_SOV.xlsx`, `Audit_Log.xlsx`, `Audit_Log.json` and the processing summary; audit table |

The UI and CLI share `PipelineRun` (`app/pipeline.py`): `analyse()`,
`submit()`, `revalidate_if_needed()`, `preview()`, `export()`.

## 2. Held-out evaluation

`tests/evaluate_unseen_variants.py` builds workbooks from the sample data
with headers renamed from an independent synonym bank (phrasings already
in the alias vocabulary are excluded), random title rows, blank/Total
rows, distractor columns, extra sheets and planted anomalies. The bank is
split by hash into DEV (used to diagnose) and TEST (reported only).

| | Before | After |
|---|---|---|
| Sheet / header detection (30 files) | 30 / 30 | 30 / 30 |
| Mapping accuracy, real fields, TEST split | 56.7% | 98.3% |
| Anomaly recall incl. European numbers, bracket negatives | 100% | 100% |
| Mapping accuracy on the 4 known samples | 99.0% | 99.0% |

Caveat: the synonym bank and the concept lexicon were written by the
same author, so the TEST score is still optimistic. Real unseen team
files are the definitive check.

Fixes driven by the DEV split (all general):
- `keyword_evidence.py`: SOV abbreviation expansion (bldg, yr, blt,
  const, occ, cnty, ...) and concept rules per target field (e.g.
  building/structure + value word -> Building Value; year + built ->
  Year Built), still subject to the value veto and 1:1 assignment;
- fuzzy matching treats 2-letter words (`bi`, `id`) as key words;
- a count field rejects text values; "building number" is an ID, not a count;
- `excel_reader` now closes the workbook (Windows file lock on uploads).

## 3. Detection gaps closed

`normalizers.parse_monetary` (shared by validator, engine and Agent 4)
now reads `EUR 1.200.000,50`, `1 200 000`, `(500)`, `USD 1.2 million`,
`£2.5m`, `12bn`; ambiguous forms (`1.2MM`, `1.234`) are unchanged.
Text that hides a rule violation is reported as that violation:
`(500)` -> negative value (HIGH), `"2099"` -> future year, `"0"`
storeys -> range. Mixed date forms (`c. 1985`, `1985-1990`) are flagged
for review, never guessed.

## 4. Mapping memory (bonus: cross-submission learning)

`app/agents/schema_mapping/mapping_memory.py`: on export, reviewed
column mappings are stored (header + embedding, never row values) in
`memory/mapping_memory.json`. Agent 2 uses them as evidence (same header
~ alias strength, similar header >= 0.90 cosine ~ fuzzy strength) and
blocks targets a reviewer rejected for that header. Disable with
`--no-memory` or the sidebar toggle.

## Tests

`tests/test_ui.py`, `tests/test_unseen_variants_regression.py`, new
cases in `tests/test_pipeline_end_to_end.py` and
`tests/test_recommendation_layer.py`. `tests/conftest.py` isolates the
mapping memory per test.
