# Step 2.18 — Batch Schema Mapping & One-to-One Assignment

## Objective

Extend single-column schema reasoning to the complete source
workbook.

The system must assign source columns to the canonical SOV
schema while preventing multiple source columns from claiming
the same target field.

---

## Target Schema

The canonical schema contains 17 fields.

Each target field may be assigned at most once during the
global assignment stage.

---

## Candidate Matrix

For N source columns and 17 canonical fields:

```text
                 Target Fields
             ┌───────────────────┐
             │ 17 canonical      │
             │ SOV fields        │
             └───────────────────┘
                      ↑
                      │
              candidate scores
                      │
             Source Columns