# Step 3.3.5 — Invalid Category Validation

## Purpose

Category validation detects values that do not belong to an explicitly
allowed set of categorical values.

This is different from type validation.

For example:

    Fire Sprinklers = "MAYBE"

is a valid string from a type perspective, but it is an invalid
categorical value.

---

## Design

The validator receives an explicit mapping of fields to their allowed
values.

Example:

```python
allowed_categories = {
    "Fire Sprinklers (Y/N)": {
        "Y",
        "N",
        "Y13",
        "Y(13R)",
    }
}