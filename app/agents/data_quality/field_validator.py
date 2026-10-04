from datetime import datetime
from typing import Any

import pandas as pd

from app.agents.data_quality.field_rules import FIELD_RULES
from app.agents.data_quality.issue_schema import (
    IssueSeverity,
    IssueStatus,
    IssueType,
    QualityIssue,
)


class FieldSpecificValidator:
    """Deterministic validator for semantic SOV field rules."""

    def validate(
        self,
        dataframe: pd.DataFrame,
        current_year: int | None = None,
    ) -> list[QualityIssue]:
        if not isinstance(dataframe, pd.DataFrame):
            raise TypeError("dataframe must be a pandas DataFrame")

        if current_year is None:
            current_year = datetime.now().year

        issues: list[QualityIssue] = []

        for field_name, rules in FIELD_RULES.items():
            if field_name not in dataframe.columns:
                continue

            series = dataframe[field_name]

            for row_index, value in series.items():
                if pd.isna(value):
                    continue

                # Numeric, ZIP, year and category rules are enforced by
                # DeterministicValidator and the semantic validators.
                # This validator only owns the text-field rules.
                if rules.get("kind") in {"text", "state"}:
                    issue = self._validate_text(
                        field_name,
                        row_index,
                        value,
                        rules,
                    )
                else:
                    issue = None

                if issue is not None:
                    issues.append(issue)

        return issues

    def _base_issue(
        self,
        field_name: str,
        row_index: int,
        value: Any,
        issue_type: IssueType,
        expected_condition: str,
        evidence: dict[str, Any],
        severity: IssueSeverity = IssueSeverity.MEDIUM,
        confidence: float = 1.0,
        uncertainty: str = "Deterministic rule violation.",
    ) -> QualityIssue:
        return QualityIssue(
            issue_id=(
                f"field-rule-{field_name}-"
                f"{row_index}-{issue_type.value}"
            ),
            row_index=int(row_index),
            source_field=field_name,
            target_field=field_name,
            issue_type=issue_type,
            severity=severity,
            observed_value=value,
            expected_condition=expected_condition,
            evidence=evidence,
            recommendation=None,
            confidence=confidence,
            uncertainty=uncertainty,
            status=IssueStatus.DETECTED,
        )

    def _validate_text(
        self,
        field_name: str,
        row_index: int,
        value: Any,
        rules: dict[str, Any],
    ) -> QualityIssue | None:
        if not rules.get("reject_numeric_only"):
            return None

        text = str(value).strip()

        if text and text.isdigit():
            return self._base_issue(
                field_name=field_name,
                row_index=row_index,
                value=value,
                issue_type=IssueType.INVALID_TYPE,
                expected_condition="Value must not be numeric-only text.",
                evidence={
                    "rule": "text",
                    "numeric_only": True,
                },
                severity=IssueSeverity.LOW,
                confidence=0.95,
                uncertainty=(
                    "Numeric-only text may be suspicious rather than "
                    "strictly invalid."
                ),
            )

        return None

    @staticmethod
    def _to_numeric(value: Any) -> float | None:
        try:
            numeric = pd.to_numeric(value)

            if pd.isna(numeric):
                return None

            return float(numeric)

        except (TypeError, ValueError):
            return None