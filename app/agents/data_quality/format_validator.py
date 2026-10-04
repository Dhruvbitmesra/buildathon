from datetime import datetime
from typing import Any

import pandas as pd

from app.agents.data_quality import normalizers
from app.agents.data_quality.issue_schema import (
    IssueSeverity,
    IssueStatus,
    IssueType,
    QualityIssue,
)
from app.agents.data_quality.normalizers import Operation


# Proposal operation -> (rule_id, expected condition)
_FORMAT_RULES: dict[Operation, tuple[str, str]] = {
    Operation.PARSE_MONETARY: (
        "monetary_text_format",
        "Monetary values should be plain numbers without currency "
        "symbols, separators or K/M/B suffixes.",
    ),
    Operation.PARSE_INTEGER: (
        "integer_text_format",
        "Whole-number fields should be stored as numbers, not text.",
    ),
    Operation.EXTRACT_YEAR: (
        "year_date_format",
        "Year Built should be a 4-digit year, not a full date.",
    ),
    Operation.STANDARDISE_STATE: (
        "state_non_canonical",
        "State should use the 2-letter abbreviation.",
    ),
    Operation.TRIM_WHITESPACE: (
        "text_whitespace",
        "Text should not contain leading, trailing or repeated spaces.",
    ),
}


class FormatConsistencyValidator:
    """
    Detect values that are right in meaning but wrong in form.

    Examples:
        Building Value "$1,200,000"   -> 1200000.0
        State "Texas"                 -> "TX"
        Year Built 2008-05-20         -> 2008
        Year Built 9999               -> placeholder for "unknown"

    The candidate value comes from the shared normalizers so the
    recommendation preview matches what Agent 4 will apply.

    ZIP and sprinkler representations are owned by their dedicated
    semantic validators and are not reported here.
    """

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

        country = (
            dataframe["Country"]
            if "Country" in dataframe.columns
            else None
        )

        for field_name in dataframe.columns:

            if field_name in {"Zip", normalizers.SPRINKLER_FIELD}:
                continue

            for row_index, value in dataframe[field_name].items():

                if normalizers.is_missing(value):
                    continue

                context = {
                    "is_us": normalizers.is_us_country(
                        country.loc[row_index]
                        if country is not None
                        else None
                    ),
                }

                proposal = normalizers.propose(
                    field_name,
                    value,
                    context,
                )

                if proposal is None:
                    continue

                if proposal.operation == Operation.SET_BLANK:
                    issues.append(
                        self._placeholder_issue(
                            field_name,
                            row_index,
                            value,
                            proposal,
                        )
                    )
                    continue

                if proposal.operation not in _FORMAT_RULES:
                    continue

                # Text can hide a real error: "(500)" is a negative
                # amount, "2099" a future year. Report the real problem.
                hidden = self._hidden_violation(
                    field_name,
                    row_index,
                    value,
                    proposal.after_value,
                    current_year,
                )

                if hidden is not None:
                    issues.append(hidden)
                    continue

                rule_id, expected = _FORMAT_RULES[proposal.operation]

                issues.append(
                    QualityIssue(
                        issue_id=f"DQ-FORMAT-{field_name}-{row_index}",
                        row_index=int(row_index),
                        source_field=field_name,
                        target_field=field_name,
                        issue_type=IssueType.FORMAT_INCONSISTENCY,
                        severity=IssueSeverity.LOW,
                        observed_value=value,
                        expected_condition=expected,
                        evidence={
                            "rule": rule_id,
                            "candidate_value": proposal.after_value,
                            "operation": proposal.operation.value,
                        },
                        recommendation=(
                            f"Standardise to {proposal.after_value!r} "
                            "after approval."
                        ),
                        confidence=1.0,
                        uncertainty=(
                            "The value's meaning is clear; only its "
                            "representation differs from the schema."
                        ),
                        status=IssueStatus.DETECTED,
                        rule_id=rule_id,
                    )
                )

        return issues

    @staticmethod
    def _hidden_violation(
        field_name: str,
        row_index: Any,
        value: Any,
        candidate: Any,
        current_year: int,
    ) -> QualityIssue | None:
        if not normalizers.is_number(candidate):
            return None

        if (
            field_name in normalizers.MONETARY_FIELDS
            or field_name in normalizers.INTEGER_FIELDS
        ) and candidate < 0:
            issue_type = IssueType.NEGATIVE_VALUE
            severity = (
                IssueSeverity.HIGH
                if field_name in normalizers.MONETARY_FIELDS
                else IssueSeverity.MEDIUM
            )
            rule_id = "negative_value_in_text"
            expected = f"{field_name} must be greater than or equal to zero."

        elif field_name in normalizers.INTEGER_FIELDS and candidate < 1:
            issue_type = IssueType.INVALID_RANGE
            severity = IssueSeverity.MEDIUM
            rule_id = "minimum_range_in_text"
            expected = f"{field_name} must be at least 1."

        elif field_name == "Year Built" and candidate > current_year:
            issue_type = IssueType.FUTURE_YEAR
            severity = IssueSeverity.HIGH
            rule_id = "future_year_in_text"
            expected = "Year Built must not exceed the current year."

        else:
            return None

        return QualityIssue(
            issue_id=f"DQ-{rule_id.upper()}-{field_name}-{row_index}",
            row_index=int(row_index),
            source_field=field_name,
            target_field=field_name,
            issue_type=issue_type,
            severity=severity,
            observed_value=value,
            expected_condition=expected,
            evidence={
                "rule": rule_id,
                "interpreted_value": candidate,
            },
            recommendation="Review source value.",
            confidence=1.0,
            uncertainty=(
                "The text was read as a number that breaks a business "
                "rule; the correct value cannot be inferred."
            ),
            status=IssueStatus.DETECTED,
            rule_id=rule_id,
        )

    @staticmethod
    def _placeholder_issue(
        field_name: str,
        row_index: Any,
        value: Any,
        proposal: normalizers.Proposal,
    ) -> QualityIssue:
        return QualityIssue(
            issue_id=f"DQ-PLACEHOLDER-{field_name}-{row_index}",
            row_index=int(row_index),
            source_field=field_name,
            target_field=field_name,
            issue_type=IssueType.INVALID_RANGE,
            severity=IssueSeverity.MEDIUM,
            observed_value=value,
            expected_condition=(
                f"{field_name} should be a real year, not a placeholder."
            ),
            evidence={
                "rule": "year_placeholder",
                "placeholder_values": sorted(normalizers.YEAR_PLACEHOLDERS),
            },
            recommendation="Leave blank after approval; do not guess a year.",
            confidence=0.9,
            uncertainty=(
                "The value is a common 'unknown' placeholder, but the "
                "client may have used it differently."
            ),
            status=IssueStatus.DETECTED,
            rule_id="year_placeholder",
        )
