from datetime import datetime
from typing import Any

import pandas as pd

from app.agents.data_quality.issue_schema import (
    IssueSeverity,
    IssueStatus,
    IssueType,
    QualityIssue,
)

from app.agents.data_quality.sprinkler_validator import (
    SprinklerSemanticValidator,
)

from app.agents.data_quality.config import get_sov_validation_config

from app.agents.data_quality.field_validator import (
    FieldSpecificValidator,
)

from app.agents.data_quality.state_validator import (
    StateSemanticValidator,
)

from app.agents.data_quality.zip_validator import (
    ZipSemanticValidator,
)

from app.agents.data_quality.monetary_validator import (
    MonetarySemanticValidator,
)

from app.agents.data_quality.statistical_validator import (
    StatisticalAnomalyValidator,
)

from app.agents.data_quality.format_validator import (
    FormatConsistencyValidator,
)

from app.agents.data_quality.cross_field_validator import (
    CrossFieldValidator,
)

from app.agents.data_quality.issue_consolidator import (
    collapse_empty_columns,
    consolidate_cell_issues,
)

from app.agents.data_quality.field_rules import FIELD_RULES

from app.agents.data_quality import normalizers


# Type names accepted in field_types, in addition to str/int/float.
TYPE_ALIASES: dict[str, type] = {
    "string": str,
    "str": str,
    "text": str,
    "integer": int,
    "int": int,
    "float": float,
    "number": float,
    "numeric": float,
}


class DeterministicValidator:
    """
    Base deterministic validation engine for Agent 3.

    This class only detects data-quality issues.
    It does not modify the input DataFrame.
    """

    def __init__(self) -> None:
        self.field_specific_validator = FieldSpecificValidator()
        self.state_semantic_validator = StateSemanticValidator()
        self.zip_semantic_validator = ZipSemanticValidator()
        self.monetary_semantic_validator = MonetarySemanticValidator()
        self.sprinkler_semantic_validator = SprinklerSemanticValidator()
        self.statistical_validator = StatisticalAnomalyValidator()
        self.format_validator = FormatConsistencyValidator()
        self.cross_field_validator = CrossFieldValidator()

    def validate(
        self,
        dataframe: pd.DataFrame,
        required_fields: set[str] | list[str] | None = None,
        field_types: dict[str, type] | None = None,
        non_negative_fields: set[str] | None = None,
        allowed_categories: dict[str, set[str]] | None = None,
        field_ranges: dict[str, Any] | None = None,
        current_year: int | None = None,
        unique_fields: set[str] | None = None,
    ) -> list[QualityIssue]:
        """
        Validate the supplied SOV dataframe.

        Currently supports:
        - missing-value validation
        - type validation
        - negative-value validation
        - categorical validation
        - range validation
        - future-year validation
        - duplicate validation
        - field-specific validation
        - state semantic validation
        - ZIP semantic validation
        - monetary semantic validation
        - sprinkler semantic validation
        - statistical anomaly validation
        """

        if not isinstance(dataframe, pd.DataFrame):
            raise TypeError("dataframe must be a pandas DataFrame")

        issues: list[QualityIssue] = []

        required_fields = set(required_fields or [])
        field_types = field_types or {}
        non_negative_fields = non_negative_fields or set()
        allowed_categories = allowed_categories or {}
        field_ranges = field_ranges or {}
        unique_fields = unique_fields or set()

        # ---------------------------------------------------------
        # Missing-value validation
        # ---------------------------------------------------------

        issues.extend(
            self._check_missing_values(
                dataframe=dataframe,
                required_fields=required_fields,
            )
        )

        # ---------------------------------------------------------
        # Type validation
        # ---------------------------------------------------------

        issues.extend(
            self._check_types(
                dataframe=dataframe,
                field_types=field_types,
            )
        )

        # ---------------------------------------------------------
        # Negative-value validation
        # ---------------------------------------------------------

        issues.extend(
            self._check_negative_values(
                dataframe=dataframe,
                non_negative_fields=non_negative_fields,
            )
        )

        # ---------------------------------------------------------
        # Category validation
        #
        # The generic category validator remains active for
        # Fire Sprinklers because it must catch truly invalid
        # canonical-category values such as:
        #
        #     MAYBE
        #     UNKNOWN
        #     y
        #
        # Recognized alternate sprinkler representations are
        # skipped inside _check_categories() and handled by the
        # dedicated semantic validator.
        # ---------------------------------------------------------

        category_issues = self._check_categories(
            dataframe=dataframe,
            allowed_categories=allowed_categories,
        )

        issues.extend(category_issues)

        # ---------------------------------------------------------
        # Range validation
        # ---------------------------------------------------------

        issues.extend(
            self._check_ranges(
                dataframe=dataframe,
                field_ranges=field_ranges,
            )
        )

        # ---------------------------------------------------------
        # Future-year validation
        # ---------------------------------------------------------

        issues.extend(
            self._check_future_year(
                dataframe=dataframe,
                current_year=current_year,
            )
        )

        # ---------------------------------------------------------
        # Duplicate validation
        # ---------------------------------------------------------

        issues.extend(
            self._check_duplicates(
                dataframe=dataframe,
                unique_fields=unique_fields,
            )
        )

        # ---------------------------------------------------------
        # Field-specific semantic validation
        # ---------------------------------------------------------

        issues.extend(
            self.field_specific_validator.validate(
                dataframe=dataframe,
                current_year=current_year,
            )
        )

        # ---------------------------------------------------------
        # State semantic validation
        # ---------------------------------------------------------

        issues.extend(
            self.state_semantic_validator.validate(
                dataframe=dataframe,
            )
        )

        # ---------------------------------------------------------
        # ZIP semantic validation
        # ---------------------------------------------------------

        issues.extend(
            self.zip_semantic_validator.validate(
                dataframe=dataframe,
            )
        )

        # ---------------------------------------------------------
        # Monetary semantic validation
        # ---------------------------------------------------------

        issues.extend(
            self.monetary_semantic_validator.validate(
                dataframe=dataframe,
            )
        )

        # ---------------------------------------------------------
        # Sprinkler semantic validation
        #
        # The dedicated validator handles:
        #
        #     YES -> Y
        #     NO -> N
        #     SPRINKLERED -> Y
        #     NOT SPRINKLERED -> N
        #     13R -> Y(13R)
        #     Y 13 -> Y13
        #     Y (13R) -> Y(13R)
        #
        # Unknown values such as MAYBE/UNKNOWN are also detected
        # by the dedicated validator, but those are already
        # detected by _check_categories(). Therefore we deduplicate
        # only the overlapping HIGH invalid-category issues.
        # ---------------------------------------------------------

        sprinkler_issues = self.sprinkler_semantic_validator.validate(
            dataframe=dataframe,
        )

        category_issue_keys = {
            (
                issue.row_index,
                issue.source_field,
                issue.observed_value,
            )
            for issue in category_issues
        }

        for issue in sprinkler_issues:
            issue_key = (
                issue.row_index,
                issue.source_field,
                issue.observed_value,
            )

            # Prevent duplicate unknown-sprinkler issues.
            if (
                issue.issue_type == IssueType.INVALID_CATEGORY
                and issue.severity == IssueSeverity.HIGH
                and issue_key in category_issue_keys
            ):
                continue

            issues.append(issue)

        # ---------------------------------------------------------
        # Format consistency validation
        #
        # Values that are correct in meaning but not in form, such as
        # "$1,200,000", "Texas" or a full date in Year Built. The
        # type and category checks above defer these values here so
        # each cell receives one issue.
        # ---------------------------------------------------------

        issues.extend(
            self.format_validator.validate(dataframe, current_year)
        )

        # ---------------------------------------------------------
        # Statistical anomaly validation
        # ---------------------------------------------------------

        issues.extend(
            self.statistical_validator.validate(dataframe)
        )

        return issues

    def validate_sov(
        self,
        dataframe: pd.DataFrame,
        current_year: int | None = None,
    ) -> list[QualityIssue]:
        """
        Run the complete Agent 3 detection pipeline using the canonical
        SOV validation configuration.

        On top of validate(), this:
        - reports required columns that are absent (dataset-level);
        - runs cross-field checks;
        - collapses fully empty columns into one issue;
        - keeps one primary issue per cell, attaching the others as
          supporting evidence so nothing is double-counted.
        """

        config = get_sov_validation_config()

        issues = self.validate(
            dataframe=dataframe,
            required_fields=config["required_fields"],
            field_types=config["field_types"],
            non_negative_fields=config["non_negative_fields"],
            allowed_categories=config["allowed_categories"],
            field_ranges=config["field_ranges"],
            current_year=current_year,
            unique_fields=config["unique_fields"],
        )

        issues.extend(
            self._check_missing_columns(
                dataframe=dataframe,
                required_fields=config["required_fields"],
            )
        )

        issues.extend(
            self.cross_field_validator.validate(dataframe)
        )

        issues = collapse_empty_columns(issues, dataframe)

        return consolidate_cell_issues(issues)

    def _check_missing_columns(
        self,
        dataframe: pd.DataFrame,
        required_fields: list[str],
    ) -> list[QualityIssue]:
        """
        Report target fields that no source column was mapped to.

        The column will be exported blank; the reviewer must know.
        """

        issues: list[QualityIssue] = []

        for field in required_fields:

            if field in dataframe.columns:
                continue

            is_required = FIELD_RULES.get(field, {}).get(
                "required",
                True,
            )

            issues.append(
                QualityIssue(
                    issue_id=f"DQ-COLUMN-MISSING-{field}",
                    row_index=None,
                    source_field=field,
                    target_field=field,
                    issue_type=IssueType.MISSING_VALUE,
                    severity=(
                        IssueSeverity.HIGH
                        if is_required
                        else IssueSeverity.MEDIUM
                    ),
                    observed_value=None,
                    expected_condition=(
                        f"A source column should be mapped to {field}."
                    ),
                    evidence={
                        "rule": "column_not_mapped",
                        "field": field,
                        "row_count": int(len(dataframe)),
                    },
                    recommendation=(
                        "Map a source column to this field, or confirm "
                        "it should be exported blank."
                    ),
                    confidence=1.0,
                    uncertainty=(
                        "The source file may not contain this information, "
                        "or schema mapping may have missed the column."
                    ),
                    rule_id="column_not_mapped",
                )
            )

        return issues

    def _check_missing_values(
        self,
        dataframe: pd.DataFrame,
        required_fields: set[str],
    ) -> list[QualityIssue]:
        """
        Detect missing values in required fields.

        Missing values are reported but never modified.
        """

        issues: list[QualityIssue] = []

        for field in required_fields:

            if field not in dataframe.columns:
                continue

            missing_rows = dataframe.index[
                dataframe[field].isna()
            ]

            # Fields the data dictionary treats as optional are LOW.
            severity = (
                IssueSeverity.MEDIUM
                if FIELD_RULES.get(field, {}).get("required", True)
                else IssueSeverity.LOW
            )

            for row_index in missing_rows:

                issues.append(
                    QualityIssue(
                        issue_id=f"DQ-MISSING-{field}-{row_index}",
                        row_index=int(row_index),
                        source_field=field,
                        target_field=field,
                        issue_type=IssueType.MISSING_VALUE,
                        severity=severity,
                        observed_value=None,
                        expected_condition=(
                            f"{field} should contain a value."
                        ),
                        evidence={
                            "rule": "required_field_missing",
                            "field": field,
                        },
                        recommendation="Review source value.",
                        confidence=1.0,
                        uncertainty=(
                            "No reliable replacement value is available."
                        ),
                    )
                )

        return issues

    def _check_types(
        self,
        dataframe: pd.DataFrame,
        field_types: dict[str, type],
    ) -> list[QualityIssue]:
        """
        Detect values that are incompatible with their expected type.

        The canonical SOV configuration uses Python types:
            str
            int
            float

        The validator therefore uses those types directly.
        """

        issues: list[QualityIssue] = []

        supported_types = {
            str,
            int,
            float,
        }

        for field, declared_type in field_types.items():

            if field not in dataframe.columns:
                continue

            expected_type = (
                TYPE_ALIASES.get(declared_type.lower())
                if isinstance(declared_type, str)
                else declared_type
            )

            if expected_type not in supported_types:
                raise ValueError(
                    f"Unsupported field type: {declared_type}"
                )

            for row_index, value in dataframe[field].items():

                # Missing values are handled separately.
                if pd.isna(value):
                    continue

                if self._is_valid_type(
                    value=value,
                    expected_type=expected_type,
                ):
                    continue

                # Values with a recognised representation are owned by
                # a semantic or format validator, which reports them
                # with a precise rule and a safe candidate value.
                if self._has_semantic_owner(field, value):
                    continue

                severity = (
                    IssueSeverity.HIGH
                    if field in {
                        "Building Value",
                        "Contents",
                        "BI",
                    }
                    else IssueSeverity.MEDIUM
                )

                issues.append(
                    QualityIssue(
                        issue_id=f"DQ-TYPE-{field}-{row_index}",
                        row_index=int(row_index),
                        source_field=field,
                        target_field=field,
                        issue_type=IssueType.INVALID_TYPE,
                        severity=severity,
                        observed_value=value,
                        expected_condition=(
                            f"{field} should be compatible with "
                            f"type '{expected_type.__name__}'."
                        ),
                        evidence={
                            "rule": "field_type_validation",
                            "expected_type": expected_type.__name__,
                            "observed_python_type": type(value).__name__,
                        },
                        recommendation="Review source value.",
                        confidence=1.0,
                        uncertainty=(
                            "The value cannot be reliably interpreted "
                            f"as {expected_type.__name__}."
                        ),
                    )
                )

        return issues

    def _check_negative_values(
        self,
        dataframe: pd.DataFrame,
        non_negative_fields: set[str],
    ) -> list[QualityIssue]:
        """
        Detect negative values in fields that must be non-negative.
        """

        issues: list[QualityIssue] = []

        high_severity_fields = {
            "Building Value",
            "Contents",
            "BI",
            "Other",
        }

        for field in non_negative_fields:

            if field not in dataframe.columns:
                continue

            for row_index, value in dataframe[field].items():

                # Missing values are handled separately.
                if pd.isna(value):
                    continue

                # Type violations are handled by _check_types().
                if not isinstance(value, (int, float)) or isinstance(
                    value,
                    bool,
                ):
                    continue

                if value >= 0:
                    continue

                severity = (
                    IssueSeverity.HIGH
                    if field in high_severity_fields
                    else IssueSeverity.MEDIUM
                )

                issues.append(
                    QualityIssue(
                        issue_id=f"DQ-NEGATIVE-{field}-{row_index}",
                        row_index=int(row_index),
                        source_field=field,
                        target_field=field,
                        issue_type=IssueType.NEGATIVE_VALUE,
                        severity=severity,
                        observed_value=value,
                        expected_condition=(
                            f"{field} must be greater than or equal to zero."
                        ),
                        evidence={
                            "rule": "non_negative_value",
                            "observed_value": value,
                            "minimum_allowed": 0,
                        },
                        recommendation="Review source value.",
                        confidence=1.0,
                        uncertainty=(
                            "The correct replacement value cannot be "
                            "determined from the negative value alone."
                        ),
                    )
                )

        return issues

    def _check_categories(
        self,
        dataframe: pd.DataFrame,
        allowed_categories: dict[str, set[str]],
    ) -> list[QualityIssue]:
        """
        Validate categorical fields against their allowed values.

        For Fire Sprinklers (Y/N), recognized alternate representations
        are intentionally skipped here because they are handled by the
        dedicated SprinklerSemanticValidator.

        Truly invalid sprinkler values such as MAYBE or UNKNOWN are still
        detected here with high confidence.

        Category matching remains case-sensitive for canonical values.
        Therefore, lowercase 'y' is considered invalid.
        """

        issues: list[QualityIssue] = []

        high_severity_fields = {
            "Fire Sprinklers (Y/N)",
        }

        recognized_sprinkler_alternates = {
            "YES",
            "NO",
            "SPRINKLERED",
            "NOT SPRINKLERED",
            "13R",
            "Y 13",
            "Y (13R)",
        }

        for field, allowed_values in allowed_categories.items():

            if field not in dataframe.columns:
                continue

            for row_index, value in dataframe[field].items():

                if pd.isna(value):
                    continue

                # Recognized sprinkler aliases are handled by the
                # dedicated semantic validator.
                if field == "Fire Sprinklers (Y/N)":
                    normalized = str(value).strip().upper()

                    if normalized in recognized_sprinkler_alternates:
                        continue

                    # Numeric coverage values (0, 1, 0.57, 100) are
                    # interpreted by the sprinkler semantic validator.
                    if normalizers.sprinkler_number(value) is not None:
                        continue

                # Canonical category validation is intentionally
                # case-sensitive.
                if value in allowed_values:
                    continue

                # A value that only differs in letter case ("y") is a
                # standardisation, not an unknown category.
                case_only = (
                    isinstance(value, str)
                    and " ".join(value.strip().upper().split())
                    in allowed_values
                )

                if case_only:
                    severity = IssueSeverity.LOW

                elif field in high_severity_fields:
                    severity = IssueSeverity.HIGH

                else:
                    severity = IssueSeverity.MEDIUM

                issues.append(
                    QualityIssue(
                        issue_id=f"DQ-CATEGORY-{field}-{row_index}",
                        row_index=int(row_index),
                        source_field=field,
                        target_field=field,
                        issue_type=IssueType.INVALID_CATEGORY,
                        severity=severity,
                        observed_value=value,
                        expected_condition=(
                            f"{field} must contain one of the allowed values."
                        ),
                        evidence={
                            "rule": "allowed_category",
                            "observed_value": value,
                            "allowed_values": sorted(allowed_values),
                        },
                        recommendation="Review source value.",
                        confidence=1.0,
                        uncertainty=(
                            "The correct category cannot be determined "
                            "from the invalid value alone."
                        ),
                    )
                )

        return issues

    def _check_ranges(
        self,
        dataframe: pd.DataFrame,
        field_ranges: dict[str, Any],
    ) -> list[QualityIssue]:
        """
        Detect numeric values outside explicitly configured ranges.

        Supports both:
            {"min": 1, "max": 10}

        and:
            (1, 10)
        """

        issues: list[QualityIssue] = []

        for field, rules in field_ranges.items():

            if field not in dataframe.columns:
                continue

            if isinstance(rules, tuple):
                minimum, maximum = rules

            elif isinstance(rules, dict):
                minimum = rules.get("min")
                maximum = rules.get("max")

            else:
                raise TypeError(
                    f"Unsupported range configuration for {field}: {rules}"
                )

            for row_index, value in dataframe[field].items():

                # Missing values are handled separately.
                if pd.isna(value):
                    continue

                # Type validation handles non-numeric values.
                if not isinstance(value, (int, float)) or isinstance(
                    value,
                    bool,
                ):
                    continue

                violation = False
                rule_name = None

                if minimum is not None and value < minimum:
                    violation = True
                    rule_name = "minimum_range"

                elif maximum is not None and value > maximum:
                    violation = True
                    rule_name = "maximum_range"

                if not violation:
                    continue

                issues.append(
                    QualityIssue(
                        issue_id=f"DQ-RANGE-{field}-{row_index}",
                        row_index=int(row_index),
                        source_field=field,
                        target_field=field,
                        issue_type=IssueType.INVALID_RANGE,
                        severity=IssueSeverity.MEDIUM,
                        observed_value=value,
                        expected_condition=(
                            f"{field} must be within the configured "
                            f"valid range."
                        ),
                        evidence={
                            "rule": rule_name,
                            "observed_value": value,
                            "minimum_allowed": minimum,
                            "maximum_allowed": maximum,
                        },
                        recommendation="Review source value.",
                        confidence=1.0,
                        uncertainty=(
                            "The correct replacement value cannot be "
                            "determined from the range violation alone."
                        ),
                    )
                )

        return issues

    def _check_future_year(
        self,
        dataframe: pd.DataFrame,
        current_year: int | None = None,
    ) -> list[QualityIssue]:
        """
        Detect Year Built values greater than the current calendar year.
        """

        issues: list[QualityIssue] = []

        if "Year Built" not in dataframe.columns:
            return issues

        if current_year is None:
            current_year = datetime.now().year

        for row_index, value in dataframe["Year Built"].items():

            # Missing values are handled separately.
            if pd.isna(value):
                continue

            # Type validation handles invalid year values.
            if isinstance(value, bool):
                continue

            if not isinstance(value, (int, float)):
                continue

            # Whole-number floats are integer-compatible.
            if isinstance(value, float) and not value.is_integer():
                continue

            year = int(value)

            if year <= current_year:
                continue

            issues.append(
                QualityIssue(
                    issue_id=f"DQ-FUTURE-YEAR-Year Built-{row_index}",
                    row_index=int(row_index),
                    source_field="Year Built",
                    target_field="Year Built",
                    issue_type=IssueType.FUTURE_YEAR,
                    severity=IssueSeverity.HIGH,
                    observed_value=value,
                    expected_condition=(
                        "Year Built must not exceed the current year."
                    ),
                    evidence={
                        "rule": "year_built_not_future",
                        "observed_year": year,
                        "current_year": current_year,
                    },
                    recommendation="Review source value.",
                    confidence=1.0,
                    uncertainty=(
                        "No reliable replacement year can be inferred "
                        "from the future value alone."
                    ),
                )
            )

        return issues

    def _check_duplicates(
        self,
        dataframe: pd.DataFrame,
        unique_fields: set[str],
    ) -> list[QualityIssue]:
        """
        Detect duplicate non-missing values in fields that should be unique.
        """

        issues: list[QualityIssue] = []

        for field in unique_fields:

            if field not in dataframe.columns:
                continue

            series = dataframe[field]

            # Missing values are handled separately.
            non_missing = series.dropna()

            duplicate_mask = non_missing.duplicated(
                keep=False
            )

            duplicated_rows = non_missing[
                duplicate_mask
            ]

            if duplicated_rows.empty:
                continue

            duplicate_counts = duplicated_rows.value_counts()

            for row_index, value in duplicated_rows.items():

                duplicate_count = int(
                    duplicate_counts[value]
                )

                issues.append(
                    QualityIssue(
                        issue_id=f"DQ-DUPLICATE-{field}-{row_index}",
                        row_index=int(row_index),
                        source_field=field,
                        target_field=field,
                        issue_type=IssueType.DUPLICATE,
                        severity=IssueSeverity.MEDIUM,
                        observed_value=value,
                        expected_condition=(
                            f"{field} should contain unique "
                            "non-missing values."
                        ),
                        evidence={
                            "rule": "unique_field",
                            "field": field,
                            "duplicated_value": value,
                            "duplicate_count": duplicate_count,
                        },
                        recommendation=(
                            "Review duplicate records."
                        ),
                        confidence=1.0,
                        uncertainty=(
                            "The validator cannot determine whether "
                            "the duplicate represents a legitimate "
                            "record or a duplicated exposure."
                        ),
                    )
                )

        return issues

    @staticmethod
    def _has_semantic_owner(
        field: str,
        value: Any,
    ) -> bool:
        """
        Return True when a dedicated validator reports this value.

        Examples:
        - Zip 75219.0 (Excel number) -> ZIP semantic validator
        - Fire Sprinklers 0.57 -> sprinkler semantic validator
        - Building Value "$1,200,000" -> format validator
        - Storeys "3" / Year Built 2008-05-20 -> format validator
        """

        if field == "Zip":
            return normalizers.zip_digits(value) is not None

        # A numeric location number (1, 2.0) is a valid identifier;
        # Agent 4 casts it to text when writing the output.
        if field == "Reference":
            return (
                normalizers.is_number(value)
                and float(value).is_integer()
            )

        if field == "Fire Sprinklers (Y/N)":
            return normalizers.sprinkler_number(value) is not None

        if field in normalizers.MONETARY_FIELDS:
            return (
                isinstance(value, str)
                and normalizers.parse_monetary(value) is not None
            )

        if field in normalizers.INTEGER_FIELDS:
            return (
                isinstance(value, str)
                and normalizers.parse_whole_int(value) is not None
            )

        if field == "Year Built":
            return normalizers.propose(field, value) is not None

        return False

    @staticmethod
    def _is_valid_type(
        value: Any,
        expected_type: type,
    ) -> bool:
        """
        Check whether a single value is compatible with its expected
        Python type.

        Rules:
        - str requires a string.
        - int accepts integers and whole-number floats, but not bool.
        - float accepts integers and floats, but not bool.
        """

        if expected_type is str:
            return isinstance(value, str)

        if expected_type is int:

            if isinstance(value, bool):
                return False

            if isinstance(value, int):
                return True

            if isinstance(value, float):
                return value.is_integer()

            return False

        if expected_type is float:

            if isinstance(value, bool):
                return False

            if isinstance(value, (int, float)):
                return True

            return False

        return False