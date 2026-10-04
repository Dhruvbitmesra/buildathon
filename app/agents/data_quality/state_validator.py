from typing import Any

import pandas as pd

from app.agents.data_quality import normalizers
from app.agents.data_quality.issue_schema import (
    IssueSeverity,
    IssueStatus,
    IssueType,
    QualityIssue,
)
from app.agents.data_quality.us_reference import (
    STATE_CODES,
    STATE_NAME_TO_CODE,
)


# Kept for backward compatibility with callers importing these names.
STATE_NAMES = set(STATE_NAME_TO_CODE)


class StateSemanticValidator:
    """
    Validate semantic representations of SOV State values.

    Recognised values: 2-letter codes (any case), full names, US
    territories and AP-style abbreviations such as "Calif." or "V.I.".
    Recognised but non-canonical values are reported by the format
    validator as standardisations; this validator only reports values
    that cannot be resolved to a state.

    Rows whose Country is not the US are skipped.
    """

    def validate(self, dataframe: pd.DataFrame) -> list[QualityIssue]:
        if not isinstance(dataframe, pd.DataFrame):
            raise TypeError("dataframe must be a pandas DataFrame")

        if "State" not in dataframe.columns:
            return []

        has_country = "Country" in dataframe.columns
        issues: list[QualityIssue] = []

        for row_index, value in dataframe["State"].items():
            if pd.isna(value):
                continue

            if has_country and not normalizers.is_us_country(
                dataframe.at[row_index, "Country"]
            ):
                continue

            if self._is_valid_state(value):
                continue

            issues.append(
                QualityIssue(
                    issue_id=f"state_semantic_{row_index}",
                    row_index=int(row_index),
                    source_field="State",
                    target_field="State",
                    issue_type=IssueType.INVALID_CATEGORY,
                    severity=IssueSeverity.MEDIUM,
                    observed_value=value,
                    expected_condition=(
                        "State must be a recognized two-letter state code "
                        "or full state name."
                    ),
                    evidence={
                        "normalized_value": str(value).strip().upper(),
                        "validation": "state_vocabulary",
                    },
                    recommendation=(
                        "Review the State value and map it to a valid "
                        "state code or state name."
                    ),
                    confidence=0.95,
                    uncertainty=(
                        "The value does not match the configured state "
                        "vocabulary."
                    ),
                    status=IssueStatus.DETECTED,
                )
            )

        return issues

    @staticmethod
    def _is_valid_state(value: Any) -> bool:
        normalized = " ".join(str(value).strip().split())

        if not normalized:
            return True

        if normalized.upper() in STATE_CODES:
            return True

        return normalizers.standardise_state(normalized) is not None
