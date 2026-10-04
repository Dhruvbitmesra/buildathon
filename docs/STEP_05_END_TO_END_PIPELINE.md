# Step 5 — End-to-End Pipeline Run and Fixes

## Objective

Run the whole system (ingestion -> Agent 1 -> Agent 2 -> Agent 3 ->
human review -> Agent 4) on every sample file, find where it fails and
fix the causes.

## How to run

```bash
# Stops at the human review gate; writes output/<file>_<ext>/review_queue.json
python -m app.main data/input/SOV_H6D2.xlsx

# Approve only "Approve All"-eligible items
python -m app.main data/input/SOV_H6D2.xlsx --approve bulk

# Apply reviewer decisions from a file, then export when nothing is pending
python -m app.main data/input/SOV_H6D2.xlsx --decisions decisions.json --reviewer alice

# Deterministic only (no Groq calls)
python -m app.main data/input/SOV_H6D2.xlsx --no-llm
```

`decisions.json` is a list of
`{"recommendation_id", "decision": "approve|reject|edit|escalate", "reason", "edited_value"}`,
applied in order (a reject followed by an approve approves the re-reasoned attempt).

Outputs per file: `sheet_manifest.json`, `schema_mapping.json` (problem
statement section 09 format), `quality_report.json`, `review_queue.json`,
and once every item is decided `Cleaned_SOV.xlsx` (single sheet `Cleaned_SOV`; see Step 7
for the separate audit files), `Audit_Log.json`, `agent_trace.json`.

## Errors found and fixed

| # | Where | Error | Fix |
|---|---|---|---|
| 1 | `app/main.py` | Hard-coded `data/input/sample_sov.csv` (does not exist); crashed with a traceback | CLI over `app/pipeline.py`; readable errors, exit codes |
| 2 | Orchestration | No code connected the agents | `app/pipeline.py`, state nodes `run(state)` for every agent |
| 3 | Agent 1 | Only per-sheet classification; K4T9 has two Primary sheets and nothing chose between them; the sample files have no Primary | `SheetDiscoveryAgent`: ranked manifest with confidence and reasoning, best Primary, fallback to best Secondary with a warning |
| 4 | Agent 1 -> 2 | Duplicate headers (`2024 - Increase 10%` x3) and blank headers crashed column selection | `clean_header_names`: unique, whitespace-normalised names, `Unnamed_<n>` |
| 5 | Agent 1 -> 3 | Blank rows, `Total` rows and single-cell footnotes entered the data as fake locations | `extract_table` excludes and reports them; table index keeps Excel row numbers |
| 6 | Agent 2 | `resolve_mapping` created a Groq client when none was given; without a key (or on any LLM error) the column lost *all* evidence and became unmapped | No implicit client; LLM failures keep deterministic/semantic evidence and add a warning |
| 7 | Agent 2 | LLM answered `"confidence": "high"` -> validation error -> column dropped | Verbal confidences coerced (high/medium/low) |
| 8 | Agent 2 | Semantic candidates never set `semantic_score`, so every semantic match was capped at 0.45 and could never be assigned | Score passed through |
| 9 | Agent 2 | Exact alias `Buildings` -> Number of Buildings although values were EUR 22M; `Primary Occupancy & %` (1.0) -> Occupancy | Value-plausibility veto; value-based disambiguation for `building(s)` |
| 10 | Agent 2 | `#` stripped: `Loc #` -> `loc`, `# Of Stories` -> `of stories` | `#` normalised to "number" |
| 11 | Agent 2 | Fuzzy `Account Name` -> County (0.87, character similarity) | Fuzzy match requires the vocabulary entry's key words to be present |
| 12 | Agent 2 | Every mapping reported method `global_assignment` | Real method reported (exact / domain_alias / fuzzy / semantic / llm) |
| 13 | Agent 2 | Target-schema embeddings recomputed for every column (~80% of run time) | Cached per model |
| 14 | Agent 2 | LLM calls sequential (93 s on H6D2) and hit Groq's 8k tokens/min limit (HTTP 429) | Concurrent prefetch (3 workers), retry honouring "try again in Xs", no LLM call when exact/alias/fuzzy evidence is already strong |
| 15 | Ingestion | CSV read as all-text, so numbers became "format issues" (CSV gave 2x the issues of the identical xlsx) | Plain numeric tokens typed; leading-zero tokens (`02108`) stay text |
| 16 | Agent 3 | `run(state)` read the raw sheet without its header | Reads Agent 1's table |
| 17 | Review | A reviewer's mapping edit was never validated by Agent 3 (NFR-7) | Pipeline re-runs Agent 3 after mapping edits, carrying over decisions |
| 18 | Review | Re-reasoned / edited items kept their old title | Titles rebuilt |
| 19 | Agent 4 | Did not exist; nothing produced `Cleaned_SOV.xlsx` | `app/agents/transformation/agent.py` |
| 20 | Output | `sample_sov.csv` and `.xlsx` wrote to the same folder | Output folder includes the extension |

## Agent 4 (new)

- Refuses to export while any recommendation is pending or escalated.
- Applies only approved column mappings and cell changes, re-checking
  each change's before-value against the data.
- Casts to the data dictionary types; values that cannot be cast (e.g.
  "TBD" in Building Value, a kept "MAYBE" sprinkler) are left blank,
  never zero, and the original value is recorded in the audit log.
- Zip is written as an integer (data dictionary) with display format
  `00000`, so `00802` stays visible.
- Validates the written file: sheet name, exact 17 headers in order, no
  merged cells, cell types, sprinkler values.

## Results

| File | Sheet chosen | Mapping accuracy | Run time (no LLM) | Output schema |
|---|---|---|---|---|
| SOV_B4ID | SOV | 27/27 | 15 s | valid |
| SOV_H6D2 | SOV | 25/25 | 15 s | valid |
| SOV_K4T9 | Locations | 16/17 | 15 s | valid |
| SOV_Q8B3 | 23-24 Values | 29/29 | 25 s | valid |
| sample_sov.xlsx/.csv | Property Data / CSV_Data | 6/6 | 15 s | valid |

Mapping accuracy is measured by `python -m tests.evaluate_mapping_accuracy`
against hand-labelled ground truth (`tests/evaluate_mapping_accuracy.py`):
99.0% overall (was 92.3%), target 74%. Most of each run is the one-time
model load (~13 s).

With the LLM on the Groq free tier, mapping a large file can take up to
~60 s because of rate-limit waits.

## Tests

`tests/test_pipeline_end_to_end.py`, `tests/test_mapping_accuracy_regression.py`.
