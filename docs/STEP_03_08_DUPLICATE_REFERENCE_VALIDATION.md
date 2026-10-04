# Step 3.3.8 — Duplicate Reference Validation

## Purpose

Duplicate validation detects repeated values in fields that are expected
to uniquely identify SOV records.

The initial implementation focuses on:

    Reference

A duplicate Reference can indicate:

- duplicated location records
- repeated exposure records
- accidental row duplication
- source-data inconsistencies

---

## Design

The validator receives a set of fields whose values should be unique.

Example:

```python
unique_fields = {
    "Reference",
}