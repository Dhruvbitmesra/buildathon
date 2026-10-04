# Step 3.3.3 — Type Validation

## Purpose

Type validation checks whether individual SOV values are compatible with
the expected type of their mapped target field.

The validation is performed at the value level rather than relying only
on the pandas column dtype because Excel data can contain mixed types.

---

## Supported Types

The initial validator supports:

- `string`
- `integer`
- `float`

The expected type is supplied explicitly for each target field.

Example:

```python
field_types = {
    "Building Value": "float",
    "Contents": "float",
    "BI": "float",
    "Storeys": "integer",
    "Number of Buildings": "integer",
    "Year Built": "integer",
}