# Step 3.4.5 — Statistical Anomaly Detection

## Purpose

This step adds statistical anomaly detection to Agent 3.

The objective is to identify numerical values that are unusually far
from the distribution of the corresponding SOV field.

A statistical anomaly is not automatically an invalid value.

For example, a very large Building Value may be legitimate for a large
commercial property. Therefore, statistical detection produces an
evidence-backed review issue rather than modifying or rejecting the value.

## Position in Agent 3

The validation pipeline is:

1. Generic deterministic validation
2. Field-specific validation
3. State semantic validation
4. ZIP semantic validation
5. Monetary semantic validation
6. Sprinkler semantic validation
7. Statistical anomaly detection
8. Future reasoning/recommendation layer

## Statistical Methods

### IQR

The Interquartile Range is:

IQR = Q3 - Q1

Values below:

Q1 - 1.5 × IQR

or above:

Q3 + 1.5 × IQR

are considered potential outliers.

### MAD

Median Absolute Deviation is calculated as:

MAD = median(|x - median(x)|)

MAD provides a robust measure of dispersion and is less sensitive to
extreme observations than standard deviation.

## Design Principles

### Deterministic first

Statistical detection is applied only after deterministic validation.

### No automatic modification

This step never changes the source DataFrame.

### Anomaly does not mean invalid

A statistical anomaly should be presented as a review signal.

### Minimum sample size

Very small columns should not be treated as statistically reliable
distributions.

### Field-aware behavior

Statistical detection should primarily target continuous or count-like
numeric SOV fields.

## Output

Each detected anomaly is represented using `QualityIssue`.

The issue contains:

- row index
- source field
- observed value
- statistical evidence
- anomaly method
- severity
- confidence
- recommendation
- uncertainty

## Example

If most Building Values are between $100,000 and $200,000 and one
record contains $8,500,000, the validator may generate:

- issue_type: statistical_anomaly
- severity: medium
- observed_value: 8500000
- method: IQR
- recommendation: Review unusually high Building Value

The value is not automatically changed.

## Why this step matters

This adds statistical intelligence to Agent 3 without allowing the
statistical layer to overwrite valid business data.