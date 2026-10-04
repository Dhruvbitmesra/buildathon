import re
from typing import Any

import pandas as pd

from app.agents.data_quality.issue_schema import (
    IssueSeverity,
    IssueStatus,
    IssueType,
    QualityIssue,
)


MONETARY_FIELDS = {
    "Building Value",
    "Contents",
    "BI",
    "Other",
}


# Examples:
# 1,200,000
# $1,200,000
# 1200000
# 1.2M
# $1.2M
# 750K
# 2.5B
MONETARY_PATTERN = re.compile(
    r"""
    ^\s*
    \$?
    (?:
        \d+(?:,\d{3})*(?:\.\d+)?
        |
        \d+(?:\.\d+)?[KMB]
    )
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)


class MonetarySemanticValidator:
    """Validate semantic representations of SOV monetary values."""

    def validate(self, dataframe: pd.DataFrame) -> list[QualityIssue]:
        if not isinstance(dataframe, pd.DataFrame):
            raise TypeError("dataframe must be a pandas DataFrame")

        issues: list[QualityIssue] = []

        for field_name in MONETARY_FIELDS:
            if field_name not in dataframe.columns:
                continue

            for row_index, value in dataframe[field_name].items():
                if pd.isna(value):
                    continue

                # Already numeric: generic type validation handles
                # whether the value is numerically valid.
                if self._is_numeric(value):
                    continue

                if not isinstance(value, str):
                    continue

                normalized = value.strip()

# Plain alphabetic/text values are handled by the
# generic type validator, not the monetary validator.
                if normalized.isalpha():
                    continue

                if self._is_valid_monetary_representation(value):
                    continue

                issues.append(
                    QualityIssue(
                        issue_id=f"monetary_semantic_{field_name}_{row_index}",
                        row_index=int(row_index),
                        source_field=field_name,
                        target_field=field_name,
                        issue_type=IssueType.INVALID_TYPE,
                        severity=IssueSeverity.MEDIUM,
                        observed_value=value,
                        expected_condition=(
                            "Monetary value must be numeric or use a recognized "
                            "monetary representation such as "
                            "$1,200,000, 1.2M, 750K, or 2.5B."
                        ),
                        evidence={
                            "normalized_value": normalized,
                            "validation": "monetary_representation",
                        },
                        recommendation=(
                            "Review the monetary representation and convert it "
                            "to a supported numeric format."
                        ),
                        confidence=0.95,
                        uncertainty=(
                            "The value does not match a recognized monetary "
                            "representation."
                        ),
                        status=IssueStatus.DETECTED,
                    )
                )
        return issues

    @staticmethod
    def _is_numeric(value: Any) -> bool:
        if isinstance(value, bool):
            return False

        try:
            numeric = pd.to_numeric(value)
        except (TypeError, ValueError):
            return False

        return not pd.isna(numeric)

    @staticmethod
    def _is_valid_monetary_representation(value: Any) -> bool:
        if not isinstance(value, str):
            return False

        # Same parser the recommendation engine and Agent 4 use.
        from app.agents.data_quality.normalizers import parse_monetary

        return parse_monetary(value) is not None