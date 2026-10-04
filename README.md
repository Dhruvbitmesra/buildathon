# SOVereign AI — Agentic SOV Cleansing & Intelligence System

Four collaborating agents turn a client's Statement of Values (any layout)
into a schema-conformant `Cleaned_SOV.xlsx`, with a human approving every
change.

```text
Upload ─► Agent 1 Sheet Discovery ─► Agent 2 Schema Mapping ─► Agent 3 Data Quality & Reasoning
                                                                      │   ▲ reject + note
                                                                      ▼   │ (re-reason, max 2)
                                                               Human Review (UI)
                                                                      │ all items decided
                                                                      ▼
                                                  Agent 4 Controlled Transformation
                                                                      ▼
                                                  Cleaned_SOV.xlsx + Audit_Log
```

All agents share one typed state object (`app/state/sov_state.py`).

## Setup

```bash
uv sync                      # Python 3.13
cp .env.example .env         # optional: GROQ_API_KEY=... enables LLM reasoning
```

The first run downloads two small Hugging Face models (embeddings and a
cross-encoder); later runs use the local cache.

## Run the web app (recommended)

```bash
uv run streamlit run app/ui/streamlit_app.py
```

Upload an `.xlsx`/`.csv`, enter your name, click **Analyse file**, then
work through the tabs: Workflow · Sheets · Mapping · Data quality ·
Review · Preview & export. Export is enabled only when every
recommendation has a decision.

## Run from the command line

```bash
uv run python -m app.main data/input/SOV_H6D2.xlsx                 # stops at review
uv run python -m app.main data/input/SOV_H6D2.xlsx --approve bulk  # Approve All (>= 0.90, lossless)
uv run python -m app.main FILE --decisions decisions.json --reviewer alice
uv run python -m app.main FILE --no-llm --no-memory                # deterministic, no learning
```

Outputs go to `output/<file>_<ext>/`: `sheet_manifest.json`,
`schema_mapping.json`, `quality_report.json`, `review_queue.json`, and
after export `Cleaned_SOV.xlsx`, `Audit_Log.json`, `agent_trace.json`.

## Evaluate

```bash
uv run pytest                                          # full suite
uv run python -m tests.evaluate_mapping_accuracy       # mapping accuracy on the samples
uv run python -m tests.evaluate_unseen_variants        # held-out: unseen headers/layouts
uv run python -m tests.evaluate_agent3_real            # anomaly recall on the samples
```

The sample files were used during development, so their scores are
optimistic; `evaluate_unseen_variants` reports a held-out split that was
never used for tuning. Real unseen files from the team are the best
test: label them in `tests/evaluate_mapping_accuracy.py` and run it.

## Guarantees

- No change is applied without an explicit human decision (C-01).
- Missing values stay blank; nothing is invented (C-02).
- Every recommendation carries a rationale, uncertainty and before/after
  values (NFR-6); every applied change is in the audit log (NFR-3).
- Only headers (never row values) are stored in mapping memory; names
  and addresses are masked before any LLM call in Agent 3.

## Documentation

`docs/STEP_*.md` record each step; `docs/DEMO_SCRIPT.md` walks through
the 7 demo stages.

---

Statistical + Bayesian Column Mapping — Short Documentation
1. Purpose
The SOV files can have different column names for the same insurance field.
For example:
Source Column	Actual Meaning
Bldg Repl Cost New	Building Value
Construction Yr	Year Built
No. Floors	Storeys
Postal Code	Zip
Sprk	Fire Sprinklers


A simple string-matching approach can fail because column names may be abbreviated, misspelled, or completely different.
Our module adds statistical evidence to the mapping process.
Instead of asking the LLM:
"What does this column mean?"

we first ask:
"What does the data inside this column statistically look like?"

2. What the Code Does
The module has four main stages:
Stage 1 — Column Profiling
For every source column, we calculate a statistical fingerprint.
Examples:
- Missing percentage
- Unique values
- Numeric percentage
- Mean / median
- Min / max
- Standard deviation
- Q1 / Q3
- Negative values
- Zero values
- String length
- Year pattern
- ZIP pattern
- State-code pattern
- Yes/No pattern
- Currency pattern
Example:
Construction Yr

numeric_ratio = 1.00
min = 1998
max = 2018
year_4_digit = 1.00
missing_ratio = 0.00

This gives the system evidence that the column probably represents a year.
3. Statistical Evidence
We then compare the observed column profile with the expected profile of each target field.
For example:
Observed:

Construction Yr
    numeric = 100%
    4-digit values = 100%
    range = 1998–2018

Target: Year Built

Expected:
    numeric = TRUE
    4-digit year = TRUE
    reasonable historical range

Therefore:
Statistical compatibility = HIGH

But:
Target: Storeys

Expected:
    numeric = TRUE
    positive integer
    usually small values

The values 1998–2018 are statistically inconsistent with Storeys.
Therefore:
Statistical compatibility = LOW

4. Bayesian Mapping
We combine multiple sources of evidence:
                Column
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
     Header     Statistics   Values
     Evidence    Evidence    Patterns
        │          │          │
        └──────────┼──────────┘
                   ▼
             Bayesian Score
                   │
                   ▼
       P(Target Field | Evidence)

Conceptually:
\[
P(Field|Evidence)
\propto
P(Evidence|Field)P(Field)
\]
The system therefore doesn't rely only on the column name.
For example:
"Construction Yr"

Header evidence       → Year Built
Statistical evidence  → Year Built
Value pattern         → Year Built

Final probability:
Year Built → 0.91
Storeys    → 0.03
Zip        → 0.02
...

The output becomes:
{
    "source_column": "Construction Yr",
    "predicted_field": "Year Built",
    "probability": 0.91,
    "decision": "auto_map"
}

5. Where It Plugs Into Your Project
This should primarily be plugged into Agent 2 — Schema Mapping.
Your existing architecture is:
                SOV FILE
                   │
                   ▼
          Agent 1: Sheet Discovery
                   │
                   ▼
          ┌────────────────────┐
          │ Agent 2             │
          │ Schema Mapping      │
          └─────────┬──────────┘
                    │
          ┌─────────▼──────────┐
          │ Statistical Layer  │
          │                    │
          │ 1. Column Profile  │
          │ 2. Field Rules     │
          │ 3. Bayesian Score  │
          └─────────┬──────────┘
                    │
                    ▼
             Mapping Candidates
                    │
             ┌──────┴──────┐
             ▼             ▼
        High confidence   Ambiguous
             │             │
             ▼             ▼
          Auto-map    Embedding / GPT
                           │
                           ▼
                      Human Review
                           │
                           ▼
               Agent 3: Data Quality
                           │
                           ▼
               Agent 4: Transformation

The project specification already places schema mapping in Agent 2, including exact matching, abbreviation matching, RapidFuzz, embeddings/value profiles, GPT for unresolved cases, and human review for low-confidence mappings. Your statistical layer fits naturally between the deterministic matching and the embedding/LLM fallback.     404_Agent_Not_Found_PS3
6. Recommended Agent 2 Pipeline
I would implement Agent 2 like this:
Source Column
     │
     ▼
Exact Match?
     │
   Yes ──────────────► Map
     │
    No
     ▼
Abbreviation Dictionary
     │
     ▼
RapidFuzz
     │
     ▼
Statistical Column Profiling
     │
     ▼
Bayesian Evidence Scoring
     │
     ├── High confidence ──► Map
     │
     └── Low/Ambiguous
             │
             ▼
       Top-3 Candidates
             │
             ▼
      Embedding + GPT
             │
             ▼
       Human Review

This is particularly useful because the project explicitly follows the principle "deterministic first, LLM last."     404_Agent_Not_Found_PS3
7. Why This Is Useful
Without statistical profiling
"Bldg Repl Cost New"
          ↓
LLM
          ↓
Building Value

The model is making the decision primarily from semantics.
With your approach
"Bldg Repl Cost New"
          │
          ├── Header similarity
          ├── Numeric ratio
          ├── Range
          ├── Distribution
          ├── Value patterns
          └── Domain expectations
                    │
                    ▼
             Bayesian evidence
                    │
                    ▼
             Building Value

This makes the mapping:
more explainable + more evidence-driven + less dependent on the LLM.
8. Where Agent 3 Can Reuse It
The same statistical profile should not be thrown away after Agent 2.
Pass it through your shared SOVState:
state["column_profiles"]


Then Agent 3 can use it for data-quality analysis.
For example:
Year Built
    min = 1890
    max = 2037

Agent 3 can detect:
2037 > current year
        ↓
Potential invalid Year Built
        ↓
Flag for review

Similarly:
Building Value
    negative_ratio = 0.03
        ↓
Negative values detected
        ↓
Data quality issue

So your statistical layer contributes to both Agent 2 and Agent 3.
The project specification already calls for deterministic checks over completeness, types, negative values, future years, storeys, currency formats, state formats, sprinkler codes, duplicates, etc.     404_Agent_Not_Found_PS3
9. One-line explanation for judges
If they ask "What did you contribute?", say:
"We built a statistical intelligence layer that creates a statistical fingerprint for every SOV column and combines header, distribution, and value-pattern evidence using probabilistic scoring to improve schema mapping and provide evidence for downstream data-quality decisions."

And if they ask "Why Bayes?":
"Because column names alone are unreliable in heterogeneous SOV files. Bayesian-style evidence scoring lets us combine semantic information from headers with statistical evidence from the actual data and quantify mapping confidence."

One important implementation point: once you receive the official 17 target fields, create a statistical expectation profile for each of those 17 fields. That's where this will become a strong, project-specific component rather than a generic column profiler.


             Statistical Data Intelligence
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
   Column Profiling  Bayesian Mapping  Anomaly Detection
          │              │              │
          └──────────────┼──────────────┘
                         ▼
                  Agentic SOV Pipeline



