# Step 3.3.7 — Future-Year Validation

## Purpose

Future-year validation detects Year Built values that are greater than
the current calendar year.

Example:

    Current year = 2026
    Year Built = 2035

The value is invalid because a building cannot have a construction year
in the future.

---

## Target Field

The initial implementation validates:

    Year Built

---

## Detection Rule

For every non-missing, integer-compatible Year Built value:

    Year Built > current_year

produces:

    issue_type = future_year

---

## Current Year

The validator should obtain the current year dynamically rather than
hardcoding a year.

Example:

```python
datetime.now().year