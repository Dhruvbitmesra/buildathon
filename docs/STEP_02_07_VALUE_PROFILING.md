# Step 2.7 — Column Value Profiling

## 1. Purpose

Header text alone may not provide enough evidence to determine which
target SOV field a source column represents.

Column Value Profiling generates statistical and structural evidence
from the values in a source column.

This evidence is later used by the semantic schema-mapping layer.

---

## 2. Input

The profiler receives:

- Source column name
- Column values

The values are analyzed locally.

Raw row values are not stored as semantic memory and are not sent to
the LLM as a complete dataset.

---

## 3. Profile Information

The profile contains:

- Total count
- Missing count
- Missing ratio
- Unique count
- Unique ratio
- Numeric ratio
- String ratio
- Minimum
- Maximum
- Mean
- Median
- Standard deviation
- First quartile
- Third quartile
- Top values
- Detected value patterns

---

## 4. Numeric Evidence

The profiler attempts to identify numeric values even when the source
column is represented as strings.

Examples:

    "100000"
    "250000.50"
    "1,250,000"

can provide evidence that the column is numeric.

---

## 5. Pattern Detection

The profiler identifies useful structural patterns.

Examples:

### Year-like

Values such as:

    1985
    2001
    2020

may produce year-like evidence.

### Boolean-like

Values such as:

    Y
    N

may produce boolean-like evidence.

### Fire sprinkler values

Values such as:

    Y
    N
    Y13
    Y(13R)

may produce sprinkler-like evidence.

### ZIP-like

Values with a consistent postal-code structure may produce ZIP-like
evidence.

### Currency-like

Values containing currency symbols, commas, or common monetary
suffixes may produce currency-like evidence.

---

## 6. Missing Values

The following are treated as missing:

- None
- NaN
- Empty strings
- Whitespace-only strings

Missing values are not converted to zero.

---

## 7. Statistical Evidence

For numeric columns, the profiler calculates:

- Minimum
- Maximum
- Mean
- Median
- Standard deviation
- Q1
- Q3

These statistics are descriptive evidence only.

They do not directly determine the target field.

---

## 8. Top Values

For categorical/string-like columns, the profiler records the most
frequent values and their counts.

Only a limited number of top values are retained.

This prevents the profile from becoming a copy of the source dataset.

---

## 9. Privacy

The profiler operates locally.

The complete source dataset is not sent to an external LLM.

Later semantic reasoning will use:

- Header
- Column profile
- Limited masked samples where required

rather than the complete raw column.

---

## 10. Relationship With Existing SOVState

The existing `ColumnProfile` model in:

    app/state/sov_state.py

already contains most of the fields required by this profiler.

The profiler should return a `ColumnProfile` object so that the
information can be stored in the shared typed state.

---

## 11. Definition of Done

Step 2.7 is complete when:

- A reusable column profiler exists.
- Missing values are handled correctly.
- Numeric values are identified.
- Statistical summaries are generated.
- Top values are generated.
- Useful value patterns are detected.
- Profiles are represented using `ColumnProfile`.
- Unit tests pass.