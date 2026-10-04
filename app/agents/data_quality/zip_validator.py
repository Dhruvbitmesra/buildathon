import re
from typing import Any

import pandas as pd

from app.agents.data_quality import normalizers
from app.agents.data_quality.issue_schema import (
    IssueSeverity,
    IssueStatus,
    IssueType,
    QualityIssue,
)


class ZipSemanticValidator:
    """
    Validate structural representations of SOV ZIP values.

    ZIP is an identifier and is handled as text so leading zeros
    survive ("02108" must never become 2108).

    - Excel numbers such as 75219.0 are accepted: they are a lossless
      type cast handled by Agent 4.
    - ZIPs with 3-4 digits most likely lost their leading zeros and
      are reported with the padded candidate.
    - Rows whose Country is not the US are skipped; foreign postal
      codes follow other formats.
    """

    ZIP_PATTERN = re.compile(
        r"^\d{5}$|^\d{9}$|^\d{5}-\d{4}$"
    )

    def validate(self, dataframe: pd.DataFrame) -> list[QualityIssue]:
        if not isinstance(dataframe, pd.DataFrame):
            raise TypeError("dataframe must be a pandas DataFrame")

        if "Zip" not in dataframe.columns:
            return []

        has_country = "Country" in dataframe.columns
        issues: list[QualityIssue] = []

        for row_index, value in dataframe["Zip"].items():
            if pd.isna(value):
                continue

            if has_country and not normalizers.is_us_country(
                dataframe.at[row_index, "Country"]
            ):
                continue

            if self._is_valid_zip(value):
                continue

            padded = normalizers.pad_zip(value)

            if padded is not None:
                issues.append(
                    QualityIssue(
                        issue_id=f"zip_semantic_{row_index}",
                        row_index=int(row_index),
                        source_field="Zip",
                        target_field="Zip",
                        issue_type=IssueType.INVALID_TYPE,
                        severity=IssueSeverity.MEDIUM,
                        observed_value=value,
                        expected_condition=(
                            "ZIP must contain 5 digits, 9 digits, "
                            "or use the ZIP+4 format XXXXX-XXXX."
                        ),
                        evidence={
                            "normalized_value": normalizers.zip_digits(value),
                            "validation": "zip_structure",
                            "candidate_value": padded,
                        },
                        recommendation=(
                            f"Restore leading zeros: {padded}."
                        ),
                        confidence=0.95,
                        uncertainty=(
                            "Leading zeros were most likely dropped by a "
                            "spreadsheet, but a truncated ZIP is possible."
                        ),
                        status=IssueStatus.DETECTED,
                        rule_id="zip_leading_zeros_lost",
                    )
                )
                continue

            issues.append(
                QualityIssue(
                    issue_id=f"zip_semantic_{row_index}",
                    row_index=int(row_index),
                    source_field="Zip",
                    target_field="Zip",
                    issue_type=IssueType.INVALID_TYPE,
                    severity=IssueSeverity.MEDIUM,
                    observed_value=value,
                    expected_condition=(
                        "ZIP must contain 5 digits, 9 digits, "
                        "or use the ZIP+4 format XXXXX-XXXX."
                    ),
                    evidence={
                        "normalized_value": str(value).strip(),
                        "validation": "zip_structure",
                    },
                    recommendation=(
                        "Review the ZIP value and correct its "
                        "structural representation."
                    ),
                    confidence=0.95,
                    uncertainty=(
                        "The value does not match a recognized "
                        "ZIP structural pattern."
                    ),
                    status=IssueStatus.DETECTED,
                    rule_id="zip_structure",
                )
            )

        return issues

    @classmethod
    def _is_valid_zip(cls, value: Any) -> bool:
        digits = normalizers.zip_digits(value)

        if digits is None:
            return False

        return bool(cls.ZIP_PATTERN.fullmatch(digits))
