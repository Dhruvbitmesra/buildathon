# Demo Script (10 minutes, 7 required stages)

Start: `uv run streamlit run app/ui/streamlit_app.py`. Warm the models
once before the demo (analyse any file) so the first analysis is fast.

Recommended file: **SOV_K4T9.xlsx** — 7 sheets (sheet detection), header
on row 6, a semantic/value-based mapping, non-US data, `9999` year
placeholders. Alternative: **SOV_H6D2.xlsx** for a clean US example.

| # | Stage | Where | What to show / say |
|---|---|---|---|
| 1 | Upload and sheet detection | Sidebar → *Analyse file*; **1 · Sheets** | 7 sheets ranked Primary/Secondary/Reject with confidence and reasons; two look primary, `Locations` wins on rank score; header found on row 6; title/blank rows excluded. |
| 2 | Schema detection | **2 · Mapping** | Mapping JSON with confidence and method. Highlight `Buildings` → **Building Value**: the header alone says "Number of Buildings", but the values are EUR 22M, so the agent resolves it by values. `Location Name` → City is a semantic match at 0.59, so it goes to review. |
| 3 | Data quality report | **3 · Data quality** | Intake score, per-field completeness/validity, issues by type. Point at ≥3 issues: `9999` year placeholders, missing values, statistical outliers; US state/ZIP rules skipped for European rows. |
| 4 | Recommendations | **4 · Review** | Open one *column_mapping*, one *data_correction* (`9999` → blank), one *standardisation* (e.g. trailing spaces / state codes): each shows rationale, uncertainty, confidence and a before → after table. |
| 5 | Approval workflow | **4 · Review** | Click **Approve All** (only lossless ≥ 0.90 items). Approve one item. **Reject** one with a note (e.g. on a sprinkler/placeholder item: "client confirmed these are N") → the agent re-reasons (attempt 2, title "revised after rejection"). Reject again → **Escalated**. Show *Decision history*. Edit a mapping → Agent 3 re-validates. |
| 6 | Transformation and audit | **5 · Preview & export** | Before/after side by side. Export is blocked until nothing is pending — finish the queue, click **Export**; show the audit log (source/target column, before/after, confidence, approved_by, timestamp). |
| 7 | Download | **5 · Preview & export** | Download `Cleaned_SOV.xlsx`: one sheet `Cleaned_SOV`, 17 headers in row 1, data from row 2, no merged cells, blanks not zeros; `Audit_Log` sheet and `Audit_Log.json`. |

Close on the **Workflow** tab: the live agent diagram (green done,
amber waiting for review, dashed re-reasoning loop) — bonus
"workflow visualisation". Mention mapping memory: approved mappings are
remembered (headers only) and reused for the next file.

Fallback if the network is down: untick *Use LLM reasoning*; everything
except LLM explanations works deterministically.
