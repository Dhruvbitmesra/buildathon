from typing import Any

import pandas as pd

from app.agents.data_quality import normalizers

from app.agents.data_quality.issue_schema import (
    IssueSeverity,
    IssueStatus,
    IssueType,
    QualityIssue,
)


CANONICAL_SPRINKLER_VALUES = {
    "Y",
    "N",
    "Y13",
    "Y(13R)",
}


ALTERNATE_SPRINKLER_VALUES = {
    "YES": "Y",
    "NO": "N",
    "SPRINKLERED": "Y",
    "NOT SPRINKLERED": "N",
    "13R": "Y(13R)",
    "Y 13": "Y13",
    "Y (13R)": "Y(13R)",
}


class SprinklerSemanticValidator:
    """
    Validate semantic representations of Fire Sprinklers (Y/N).

    Canonical values:
        Y
        N
        Y13
        Y(13R)

    Recognized alternate representations are reported as semantic
    normalization recommendations.

    Unknown values are intentionally NOT reported here. They are
    handled by the generic categorical validator so that there is
    exactly one issue for truly invalid values.
    """

    def validate(
        self,
        dataframe: pd.DataFrame,
    ) -> list[QualityIssue]:

        if not isinstance(dataframe, pd.DataFrame):
            raise TypeError("dataframe must be a pandas DataFrame")

        field = "Fire Sprinklers (Y/N)"

        if field not in dataframe.columns:
            return []

        issues: list[QualityIssue] = []

        # Columns such as "% Sprinklered" store coverage as a number.
        # The scale (0-1 or 0-100) is decided once for the column.
        scale = normalizers.infer_sprinkler_scale(
            dataframe[field].dropna().tolist()
        )

        for row_index, value in dataframe[field].items():

            if pd.isna(value):
                continue

            if normalizers.sprinkler_number(value) is not None:
                issues.append(
                    self._numeric_issue(row_index, value, scale)
                )
                continue

            normalized = self._normalize(value)

            # ---------------------------------------------------------
            # Canonical values are already valid.
            # ---------------------------------------------------------
            if normalized in CANONICAL_SPRINKLER_VALUES:
                continue

            # ---------------------------------------------------------
            # Recognized alternate representation.
            #
            # Example:
            #     YES -> Y
            #     NO -> N
            #     13R -> Y(13R)
            # ---------------------------------------------------------
            canonical_candidate = ALTERNATE_SPRINKLER_VALUES.get(
                normalized
            )

            if canonical_candidate is not None:

                issues.append(
                    QualityIssue(
                        issue_id=f"DQ-SPRINKLER-{row_index}",
                        row_index=int(row_index),
                        source_field=field,
                        target_field=field,
                        issue_type=IssueType.INVALID_CATEGORY,
                        severity=IssueSeverity.MEDIUM,
                        observed_value=value,
                        expected_condition=(
                            "Value should use one of canonical sprinkler "
                            "representations: Y, N, Y13, Y(13R)."
                        ),
                        evidence={
                            "normalized_value": normalized,
                            "candidate_canonical_value": (
                                canonical_candidate
                            ),
                            "validation": "sprinkler_semantics",
                        },
                        recommendation=(
                            f"Consider mapping this value to "
                            f"'{canonical_candidate}' after approval."
                        ),
                        confidence=0.95,
                        uncertainty=(
                            "The source value is a recognized alternate "
                            "representation, but normalization requires "
                            "approval before transformation."
                        ),
                        status=IssueStatus.DETECTED,
                    )
                )

                continue

            # ---------------------------------------------------------
            # Unknown values such as:
            #     MAYBE
            #     UNKNOWN
            #
            # These require human review because the correct canonical
            # sprinkler value cannot be inferred safely.
            # ---------------------------------------------------------
            issues.append(
                QualityIssue(
                    issue_id=f"DQ-SPRINKLER-{row_index}",
                    row_index=int(row_index),
                    source_field=field,
                    target_field=field,
                    issue_type=IssueType.INVALID_CATEGORY,
                    severity=IssueSeverity.HIGH,
                    observed_value=value,
                    expected_condition=(
                        "Value must be one of the canonical sprinkler "
                        "representations: Y, N, Y13, Y(13R)."
                    ),
                    evidence={
                        "normalized_value": normalized,
                        "validation": "sprinkler_semantics",
                        "reason": "unknown_sprinkler_value",
                    },
                    recommendation=(
                        "Send this value for human review. Do not automatically "
                        "transform an unknown sprinkler representation."
                    ),
                    confidence=0.95,
                    uncertainty=(
                        "The source value does not match a known sprinkler "
                        "representation, so the correct canonical value "
                        "cannot be determined safely."
                    ),
                    status=IssueStatus.DETECTED,
                )
            )

        return issues

    @staticmethod
    def _numeric_issue(
        row_index: Any,
        value: Any,
        scale: float | None,
    ) -> QualityIssue:
        """
        Report a numeric sprinkler-coverage value.

        0 -> N and full coverage -> Y are proposed (MEDIUM). Partial
        coverage has no safe canonical value and needs review (HIGH).
        """

        field = "Fire Sprinklers (Y/N)"
        candidate = normalizers.canonical_sprinkler(value, scale)

        if candidate is not None:
            return QualityIssue(
                issue_id=f"DQ-SPRINKLER-{row_index}",
                row_index=int(row_index),
                source_field=field,
                target_field=field,
                issue_type=IssueType.INVALID_CATEGORY,
                severity=IssueSeverity.MEDIUM,
                observed_value=value,
                expected_condition=(
                    "Value should use one of canonical sprinkler "
                    "representations: Y, N, Y13, Y(13R)."
                ),
                evidence={
                    "validation": "sprinkler_semantics",
                    "candidate_canonical_value": candidate,
                    "coverage_scale": scale,
                },
                recommendation=(
                    f"Consider mapping this value to '{candidate}' "
                    "after approval."
                ),
                confidence=0.9,
                uncertainty=(
                    "The column stores sprinklered coverage as a number; "
                    "the system type (Y vs Y13 / Y(13R)) is not known."
                ),
                status=IssueStatus.DETECTED,
                rule_id="sprinkler_numeric_coverage",
            )

        partial = scale is not None and 0 < float(
            normalizers.sprinkler_number(value)
        ) < scale

        return QualityIssue(
            issue_id=f"DQ-SPRINKLER-{row_index}",
            row_index=int(row_index),
            source_field=field,
            target_field=field,
            issue_type=IssueType.INVALID_CATEGORY,
            severity=IssueSeverity.HIGH,
            observed_value=value,
            expected_condition=(
                "Value must be one of the canonical sprinkler "
                "representations: Y, N, Y13, Y(13R)."
            ),
            evidence={
                "validation": "sprinkler_semantics",
                "coverage_scale": scale,
                "reason": (
                    "partial_sprinkler_coverage"
                    if partial
                    else "unknown_sprinkler_value"
                ),
            },
            recommendation=(
                "Send this value for human review. Partial coverage cannot "
                "be expressed as Y or N without an underwriting decision."
                if partial
                else "Send this value for human review."
            ),
            confidence=0.9,
            uncertainty=(
                "The location is partially sprinklered; whether that "
                "counts as Y or N is a business decision."
                if partial
                else "The numeric value cannot be interpreted as coverage."
            ),
            status=IssueStatus.DETECTED,
            rule_id=(
                "sprinkler_partial_coverage"
                if partial
                else "sprinkler_unknown"
            ),
        )

    @staticmethod
    def _normalize(value: Any) -> str:
        """
        Normalize whitespace and casing for semantic comparison.
        """
        return " ".join(
            str(value).strip().upper().split()
        )