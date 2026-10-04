"""
Post-processing of raw validator output.

Several validators can fire on the same cell: Year Built 2099 is both a
future year and a statistical outlier. Reporting both double-counts the
cell in the score and in the review queue. These helpers keep one
primary issue per cell and attach the rest as supporting evidence.

Neither function mutates the issues passed in.
"""

from copy import deepcopy

import pandas as pd

from app.agents.data_quality.field_rules import FIELD_RULES
from app.agents.data_quality.issue_schema import (
    SEVERITY_RANK,
    IssueSeverity,
    IssueType,
    QualityIssue,
)


# Higher wins when two issues on a cell share a severity.
_TYPE_PRIORITY = {
    IssueType.NEGATIVE_VALUE: 9,
    IssueType.FUTURE_YEAR: 8,
    IssueType.INVALID_RANGE: 7,
    IssueType.INVALID_TYPE: 6,
    IssueType.INVALID_CATEGORY: 5,
    IssueType.DUPLICATE: 4,
    IssueType.MISSING_VALUE: 3,
    IssueType.FORMAT_INCONSISTENCY: 2,
    IssueType.STATISTICAL_ANOMALY: 1,
}

# Relationship issues are reviewed separately from single-cell issues.
_SEPARATE_FAMILY = {IssueType.CROSS_FIELD_CONFLICT}


def consolidate_cell_issues(issues: list[QualityIssue]) -> list[QualityIssue]:
    """Keep one primary issue per (row, field); attach others as evidence."""

    groups: dict[tuple, list[QualityIssue]] = {}
    order: list[tuple] = []

    for position, issue in enumerate(issues):
        if issue.row_index is None:
            key = ("dataset", position)
        else:
            family = (
                "relation"
                if issue.issue_type in _SEPARATE_FAMILY
                else "cell"
            )
            key = (issue.row_index, issue.source_field, family)

        if key not in groups:
            groups[key] = []
            order.append(key)

        groups[key].append(issue)

    consolidated: list[QualityIssue] = []

    for key in order:
        group = groups[key]

        if len(group) == 1:
            consolidated.append(group[0])
            continue

        primary = max(
            group,
            key=lambda issue: (
                SEVERITY_RANK[issue.severity],
                _TYPE_PRIORITY.get(issue.issue_type, 0),
            ),
        )

        evidence = deepcopy(primary.evidence)
        evidence["related_issues"] = [
            {
                "issue_id": other.issue_id,
                "rule_id": other.rule_id,
                "issue_type": other.issue_type.value,
                "severity": other.severity.value,
            }
            for other in group
            if other is not primary
        ]

        for other in group:
            if (
                other is not primary
                and other.issue_type == IssueType.STATISTICAL_ANOMALY
            ):
                evidence["statistical_context"] = deepcopy(other.evidence)

        consolidated.append(
            primary.model_copy(update={"evidence": evidence})
        )

    return consolidated


def collapse_empty_columns(
    issues: list[QualityIssue],
    dataframe: pd.DataFrame,
) -> list[QualityIssue]:
    """
    Replace per-row missing-value issues of a fully empty column with a
    single column-level issue.
    """

    if len(dataframe) == 0:
        return list(issues)

    empty_columns = {
        column
        for column in dataframe.columns
        if dataframe[column].isna().all()
    }

    if not empty_columns:
        return list(issues)

    kept = [
        issue
        for issue in issues
        if not (
            issue.issue_type == IssueType.MISSING_VALUE
            and issue.row_index is not None
            and issue.source_field in empty_columns
        )
    ]

    for column in sorted(empty_columns, key=str):
        required = FIELD_RULES.get(column, {}).get("required", True)

        kept.append(
            QualityIssue(
                issue_id=f"DQ-COLUMN-EMPTY-{column}",
                row_index=None,
                source_field=str(column),
                target_field=str(column),
                issue_type=IssueType.MISSING_VALUE,
                severity=(
                    IssueSeverity.MEDIUM if required else IssueSeverity.LOW
                ),
                observed_value=None,
                expected_condition=f"{column} should contain values.",
                evidence={
                    "rule": "column_empty",
                    "row_count": int(len(dataframe)),
                },
                recommendation=(
                    "Confirm the column is genuinely empty in the source; "
                    "it will be exported blank."
                ),
                confidence=1.0,
                uncertainty=(
                    "The mapped source column has no values, or the wrong "
                    "source column was mapped."
                ),
                rule_id="column_empty",
            )
        )

    return kept
