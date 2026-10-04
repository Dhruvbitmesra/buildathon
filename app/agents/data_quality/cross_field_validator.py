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
    states_for_zip_prefix,
)


ROW_FIELD = "(row)"
TIV_FIELD = "TIV"


class CrossFieldValidator:
    """
    Detect combinations of values that are individually valid but
    suspicious together.

    Checks:
    - ZIP prefix does not belong to the State
    - every insured value (Building, Contents, BI, Other) is zero
    - a US state code on a row whose Country is not the US
    - whole rows duplicated

    All checks are advisory: they flag for review and never propose a
    replacement value.
    """

    def validate(self, dataframe: pd.DataFrame) -> list[QualityIssue]:
        if not isinstance(dataframe, pd.DataFrame):
            raise TypeError("dataframe must be a pandas DataFrame")

        issues: list[QualityIssue] = []
        issues.extend(self._check_zip_state(dataframe))
        issues.extend(self._check_zero_tiv(dataframe))
        issues.extend(self._check_us_state_foreign_country(dataframe))
        issues.extend(self._check_duplicate_rows(dataframe))
        return issues

    # -----------------------------------------------------------------

    def _check_zip_state(self, dataframe: pd.DataFrame) -> list[QualityIssue]:
        if not {"Zip", "State"} <= set(dataframe.columns):
            return []

        issues: list[QualityIssue] = []

        for row_index in dataframe.index:
            row = dataframe.loc[row_index]

            if not normalizers.is_us_country(row.get("Country")):
                continue

            state = normalizers.standardise_state(row["State"])
            zip_value = row["Zip"]

            if state is None or normalizers.is_missing(zip_value):
                continue

            digits = normalizers.pad_zip(zip_value) or normalizers.zip_digits(
                zip_value
            )

            if digits is None or len(digits.replace("-", "")) not in {5, 9}:
                continue

            expected_states = states_for_zip_prefix(digits)

            if expected_states is None or state in expected_states:
                continue

            issues.append(
                QualityIssue(
                    issue_id=f"DQ-CROSS-ZIP-STATE-{row_index}",
                    row_index=int(row_index),
                    source_field="Zip",
                    target_field="Zip",
                    issue_type=IssueType.CROSS_FIELD_CONFLICT,
                    severity=IssueSeverity.MEDIUM,
                    observed_value=zip_value,
                    expected_condition=(
                        "The ZIP code should belong to the row's State."
                    ),
                    evidence={
                        "rule": "zip_state_mismatch",
                        "zip": digits,
                        "state": state,
                        "states_for_zip_prefix": sorted(expected_states),
                        "related_fields": ["Zip", "State"],
                    },
                    recommendation="Review whether the ZIP or the State is wrong.",
                    confidence=0.85,
                    uncertainty=(
                        "A few ZIP prefixes cross state lines, and the "
                        "validator cannot tell which of the two fields "
                        "is wrong."
                    ),
                    status=IssueStatus.DETECTED,
                    rule_id="zip_state_mismatch",
                )
            )

        return issues

    def _check_zero_tiv(self, dataframe: pd.DataFrame) -> list[QualityIssue]:
        tiv_fields = [
            field
            for field in ("Building Value", "Contents", "BI", "Other")
            if field in dataframe.columns
        ]

        if not tiv_fields:
            return []

        issues: list[QualityIssue] = []

        for row_index in dataframe.index:
            values = {
                field: normalizers.parse_monetary(dataframe.at[row_index, field])
                if not normalizers.is_missing(dataframe.at[row_index, field])
                else None
                for field in tiv_fields
            }

            present = [v for v in values.values() if v is not None]

            # All-missing rows are covered by missing-value checks.
            if not present or any(v != 0 for v in present):
                continue

            issues.append(
                QualityIssue(
                    issue_id=f"DQ-CROSS-ZERO-TIV-{row_index}",
                    row_index=int(row_index),
                    source_field=TIV_FIELD,
                    target_field=None,
                    issue_type=IssueType.CROSS_FIELD_CONFLICT,
                    severity=IssueSeverity.MEDIUM,
                    observed_value=values,
                    expected_condition=(
                        "An insured location should carry some insured value."
                    ),
                    evidence={
                        "rule": "zero_total_insured_value",
                        "values": values,
                        "related_fields": tiv_fields,
                    },
                    recommendation=(
                        "Confirm whether this location is insured "
                        "elsewhere or its values are missing."
                    ),
                    confidence=0.9,
                    uncertainty=(
                        "A zero-value row can be legitimate, for example a "
                        "location insured under another schedule."
                    ),
                    status=IssueStatus.DETECTED,
                    rule_id="zero_total_insured_value",
                )
            )

        return issues

    def _check_us_state_foreign_country(
        self,
        dataframe: pd.DataFrame,
    ) -> list[QualityIssue]:
        if not {"State", "Country"} <= set(dataframe.columns):
            return []

        issues: list[QualityIssue] = []

        for row_index in dataframe.index:
            country = dataframe.at[row_index, "Country"]
            state = dataframe.at[row_index, "State"]

            if normalizers.is_us_country(country):
                continue

            if not isinstance(state, str):
                continue

            text = state.strip()

            if not (
                text.upper() in STATE_CODES and len(text) == 2
            ) and text.lower() not in STATE_NAME_TO_CODE:
                continue

            issues.append(
                QualityIssue(
                    issue_id=f"DQ-CROSS-COUNTRY-STATE-{row_index}",
                    row_index=int(row_index),
                    source_field="Country",
                    target_field="Country",
                    issue_type=IssueType.CROSS_FIELD_CONFLICT,
                    severity=IssueSeverity.MEDIUM,
                    observed_value=country,
                    expected_condition=(
                        "A US state should appear only on US rows."
                    ),
                    evidence={
                        "rule": "us_state_foreign_country",
                        "country": country,
                        "state": state,
                        "related_fields": ["Country", "State"],
                    },
                    recommendation="Review the Country and State together.",
                    confidence=0.75,
                    uncertainty=(
                        "Some non-US regions share 2-letter codes with "
                        "US states."
                    ),
                    status=IssueStatus.DETECTED,
                    rule_id="us_state_foreign_country",
                )
            )

        return issues

    def _check_duplicate_rows(self, dataframe: pd.DataFrame) -> list[QualityIssue]:
        if dataframe.shape[1] < 2 or len(dataframe) < 2:
            return []

        non_empty = dataframe[dataframe.notna().any(axis=1)]
        as_text = non_empty.astype(str)
        mask = as_text.duplicated(keep=False)

        if not mask.any():
            return []

        groups = as_text[mask].groupby(
            list(as_text.columns),
            dropna=False,
        ).groups

        issues: list[QualityIssue] = []

        for rows in groups.values():
            rows = [int(r) for r in rows]

            for row_index in rows:
                issues.append(
                    QualityIssue(
                        issue_id=f"DQ-DUPLICATE-ROW-{row_index}",
                        row_index=row_index,
                        source_field=ROW_FIELD,
                        target_field=None,
                        issue_type=IssueType.DUPLICATE,
                        severity=IssueSeverity.MEDIUM,
                        observed_value=None,
                        expected_condition=(
                            "Each location row should appear once."
                        ),
                        evidence={
                            "rule": "duplicate_row",
                            "duplicate_rows": rows,
                        },
                        recommendation=(
                            "Review whether the repeated rows double-count "
                            "exposure."
                        ),
                        confidence=1.0,
                        uncertainty=(
                            "Identical rows may be separate buildings that "
                            "were entered without distinguishing details."
                        ),
                        status=IssueStatus.DETECTED,
                        rule_id="duplicate_row",
                    )
                )

        return issues
