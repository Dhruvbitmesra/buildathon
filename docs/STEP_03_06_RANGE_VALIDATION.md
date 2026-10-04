# Step 3.3.6 — Range Validation

## Purpose

Range validation detects numeric values that are outside an explicitly
defined valid range for their SOV field.

This is separate from negative-value validation.

For example:

    Storeys = 0

is not a negative value, but it is still invalid because Storeys must
be at least 1.

---

## Design

The validator receives explicit minimum and/or maximum constraints.

Example:

```python
field_ranges = {
    "Storeys": {
        "min": 1,
    },
    "Number of Buildings": {
        "min": 1,
    },
}