# Step 7 — Problem Statement Compliance Audit

Checked against *Agentic SOV Cleansing & Intelligence System* (the
problem statement PDF). "Verified" means exercised by a run or test, not
only implemented.

## Gaps found by this audit and fixed

| Requirement | Gap | Fix |
|---|---|---|
| FR-6 single-sheet output; C-07 audit file naming | `Cleaned_SOV.xlsx` contained a second `Audit_Log` sheet | Single sheet; separate `Audit_Log.xlsx` + `Audit_Log.json` |
| NFR-3 100% of applied transformations audited | Type casts logged once per column | One audit entry per changed cell |
| Agent 4 output: processing summary report | Missing | `Processing_Summary.md` / `.json` |
| FR-1 5,000 rows without timeout | Worked but took ~98 s | Candidate-check cache, write-only/read-only workbook IO: 15.5 s end to end |
| NFR-4 user-readable errors | Raw library messages for corrupt/empty files | Plain-language messages |
| Supported formats | `.xls` advertised but `xlrd` missing | `xlrd` added |
| Data privacy | Agent 2 sent raw sample values (addresses, company names) to the LLM | Identifying values sent as shapes only (`999 Aaaaaa ...`) |
| FR-4 LLM-powered reasoning | LLM explanations off by default, one call per item | One batched, masked call; on by default when the LLM is enabled |
| NFR-5 validation speed / rigour | Full workbook load | Read-only check incl. single sheet and merged cells |

## Requirement matrix

### Primary objectives

| # | Objective | Status | Where |
|---|---|---|---|
| 1 | Ingest .xlsx/.csv, find data sheet and header row anywhere | Verified | `ingestion/`, `sheet_discovery/agent.py` |
| 2 | Map to 17 fields (exact, fuzzy, semantic), confidence JSON | Verified | `schema_mapping/`, `schema_mapping.json` |
| 3 | Detect missing, type, logical, format issues | Verified | `data_quality/validator.py` and validators |
| 4 | Explainable recommendations with uncertainty | Verified | `recommendation_engine.py` |
| 5 | Human approval UI; transform only after approval; export xlsx | Verified | `ui/streamlit_app.py`, `transformation/agent.py` |

### Functional requirements

| ID | Requirement | Status | Evidence |
|---|---|---|---|
| FR-1 | Upload .xlsx/.csv via UI | Verified | Streamlit uploader; `test_ui.py` |
| FR-1 | Multi-sheet, automatic tab and header detection | Verified | 30/30 generated variants, 4/4 samples |
| FR-1 | Header at any row | Verified | Samples have headers on rows 1, 6, 7, 12 |
| FR-1 | 5,000 rows without timeout/memory failure | Verified | 5,000-row file: 15.5 s end to end |
| FR-1 | Structured internal representation | Verified | `SOVState`, pandas DataFrames |
| FR-2 | Rank candidate sheets | Verified | Sheet manifest with rank score and confidence |
| FR-2 | Pass 1 exact then RapidFuzz fuzzy, threshold 0.75 | Verified | `exact_matcher.py`, `fuzzy_matcher.py` (`FUZZY_THRESHOLD = 0.75`) |
| FR-2 | Pass 2 sentence embeddings for unresolved | Verified | `embedding_retriever.py` (bge-small) + cross-encoder |
| FR-2 | Confidence 0-1 and method per mapping | Verified | `schema_mapping.json` |
| FR-2 | Flag confidence < 0.50 for review | Verified | `"flag": "human_review_required"` |
| FR-2 | JSON mapping in the Section 09 format | Verified | `build_mapping_json` |
| FR-3 | Per-field completeness rate | Verified | `QualityReport.field_quality` |
| FR-3 | Type validation per row | Verified | Monetary numeric, integers, sprinkler values; Zip validated as digits (kept as text internally to preserve leading zeros, written as integer) |
| FR-3 | Negative values, future Year Built, Storeys < 1 | Verified | Incl. when hidden in text (`(500)`, `"2099"`) |
| FR-3 | Currency symbols, date formats, state abbreviations | Verified | Format validator; mixed/uncertain dates flagged |
| FR-3 | Per-row and per-field flags | Verified | `row_flags`, `field_quality` |
| FR-4 | Consumes FR-2 and FR-3 | Verified | Column-mapping and data recommendations in one queue |
| FR-4 | Action types column_mapping / data_correction / standardisation / flag_for_review | Verified | `ActionType` |
| FR-4 | Before/after, rationale, confidence, uncertainty | Verified | Mandatory fields in `Recommendation` |
| FR-4 | Powered by an LLM | Verified (by design: values deterministic) | LLM explains impact (batched), re-reasons after rejection; Agent 2 LLM fallback |
| FR-4 | No auto-apply | Verified | Export gate; `test_export_is_blocked_until_everything_is_reviewed` |
| FR-4 | Re-reasoning on rejection with a note | Verified | Max 2 attempts, then escalation |
| FR-5 | Show raw column, mapping, confidence, rationale | Verified | Review tab |
| FR-5 | Accept / reject / edit individually | Verified | Plus escalate |
| FR-5 | Before/after preview side by side | Verified | Preview & export tab |
| FR-5 | Approve All for >= 0.90 | Verified (stricter) | Only lossless standardisations/mappings >= 0.90 with LOW/MEDIUM severity; data corrections always individual |
| FR-5 | Block export until flagged/low-confidence items reviewed | Verified (stricter) | Every item must have a decision |
| FR-6 | Only approved transformations | Verified | `ApprovedChange` only; before-value re-checked |
| FR-6 | Exact target names, cast types | Verified | `validate_output` |
| FR-6 | Nulls as empty cells, no zeros/placeholders | Verified | Uncastable values left blank and recorded in the audit |
| FR-6 | `Cleaned_SOV.xlsx`, sheet `Cleaned_SOV`, single sheet, headers row 1, no merged cells | Verified | All 6 sample outputs validated |
| FR-6 | Audit log with source/target column, transformation, before/after, confidence, approved_by, timestamp | Verified | `Audit_Log.xlsx` / `.json` |

### Non-functional requirements

| ID | Requirement | Status | Evidence |
|---|---|---|---|
| NFR-1 | Mapping accuracy >= 74% | Verified* | 99.0% on samples; 98.3% on held-out generated variants (*optimistic: see Step 6; confirm on unseen team files) |
| NFR-2 | Anomaly recall >= 90% | Verified* | 100% on planted anomalies (samples and variants) |
| NFR-3 | 100% of applied transformations audited | Verified | Per-cell audit; `test_every_changed_cell_is_in_the_audit_log` |
| NFR-4 | No crash on malformed input, readable error | Verified | Corrupt/empty/unsupported/missing files tested |
| NFR-5 | 17 columns, types, no merged cells | Verified | `validate_output` on every export |
| NFR-6 | Rationale for every decision | Verified | 100% rationale coverage; sheet reasoning; audit rationale |
| NFR-7 | Shared structured state; no unvalidated inputs | Verified | `SOVState`; re-validation after mapping edits |

### Constraints

| ID | Constraint | Status |
|---|---|---|
| C-01 | No auto-transformation | Verified (CLI `--approve all` is an explicit human instruction) |
| C-02 | No hallucinated data | Verified (placeholders -> blank only with approval; no fills) |
| C-03 | Exactly 17 fields, no extra/renamed/reordered | Verified |
| C-04 | 4 distinct agents sharing state | Verified (Agents 1-4 + human review gate) |
| C-05 | Rationale for every mapping and transformation | Verified |
| C-06 | Process the 3 samples without crashing | Verified (4 samples + 2 extra files) |
| C-07 | `Cleaned_SOV.xlsx`; `Audit_Log.xlsx` / `Audit_Log.json` | Verified |
| Privacy | No hard-coded keys; careful data handling | Verified (`.env`; masked LLM inputs; memory stores headers only) |

### Bonus objectives

| Bonus | Status |
|---|---|
| Vector memory of past mappings | Done: embedding-based JSON vector store (`mapping_memory.py`); no external DB server (ChromaDB from the original plan not used) |
| Agent workflow visualisation | Done: live diagram in the Workflow tab |
| Iterative refinement on rejection | Done |
| Data quality score at intake | Done: `intake_quality_score` |

### Demo stages

All 7 stages are covered by the UI; see `docs/DEMO_SCRIPT.md`.

## Remaining caveats

- Accuracy figures come from the provided samples and generated
  variants; unseen client files may score lower (low-confidence columns
  then go to review rather than being guessed).
- The output Zip column is an integer (data dictionary) with display
  format `00000`; a checker that reads raw values sees `802` for `00802`.
