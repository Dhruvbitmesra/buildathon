from typing import Any

import numpy as np
import pandas as pd

from app.agents.data_quality.issue_schema import (
    IssueSeverity,
    IssueStatus,
    IssueType,
    QualityIssue,
)


STATISTICAL_FIELDS = {
    "Building Value",
    "Contents",
    "BI",
    "Storeys",
    "Number of Buildings",
    "Year Built",
    "Other",
}


# Insured values are heavily right-skewed (many small sites, a few very
# large ones). On a linear scale IQR flags a large share of normal
# rows, so these fields are analysed as log10 of their positive values.
LOG_SCALE_FIELDS = {
    "Building Value",
    "Contents",
    "BI",
    "Other",
}


class StatisticalAnomalyValidator:
    """
    Detect statistically unusual values without modifying the DataFrame.

    Statistical anomalies are advisory: severity is LOW (one method) or
    MEDIUM (IQR and MAD agree), never a hard validation failure.
    A method is skipped when the field has no spread (IQR or MAD of 0),
    e.g. a Storeys column where almost every building has 1 floor.
    """

    def __init__(
        self,
        minimum_sample_size: int = 5,
        iqr_multiplier: float = 1.5,
        mad_threshold: float = 3.5,
    ) -> None:
        if minimum_sample_size < 2:
            raise ValueError("minimum_sample_size must be at least 2")

        if iqr_multiplier <= 0:
            raise ValueError("iqr_multiplier must be greater than 0")

        if mad_threshold <= 0:
            raise ValueError("mad_threshold must be greater than 0")

        self.minimum_sample_size = minimum_sample_size
        self.iqr_multiplier = iqr_multiplier
        self.mad_threshold = mad_threshold

    def validate(self, dataframe: pd.DataFrame) -> list[QualityIssue]:
        if not isinstance(dataframe, pd.DataFrame):
            raise TypeError("dataframe must be a pandas DataFrame")

        issues: list[QualityIssue] = []

        for field in STATISTICAL_FIELDS:
            if field not in dataframe.columns:
                continue

            raw = pd.to_numeric(dataframe[field], errors="coerce")
            log_scale = field in LOG_SCALE_FIELDS

            if log_scale:
                # Zero and negative values are excluded: zero is a
                # legitimate value and negatives have their own rule.
                series = np.log10(raw.where(raw > 0))
            else:
                series = raw

            valid_values = series.dropna()

            if len(valid_values) < self.minimum_sample_size:
                continue

            iqr_bounds = self._calculate_iqr_bounds(valid_values)
            mad_values = self._calculate_modified_z_scores(valid_values)

            for row_index, value in series.items():
                if pd.isna(value):
                    continue

                iqr_outlier = iqr_bounds["iqr"] > 0 and (
                    value < iqr_bounds["lower"]
                    or value > iqr_bounds["upper"]
                )

                mad_score = mad_values.get(row_index, 0.0)
                mad_outlier = abs(mad_score) > self.mad_threshold

                if not iqr_outlier and not mad_outlier:
                    continue

                methods: list[str] = []

                if iqr_outlier:
                    methods.append("IQR")

                if mad_outlier:
                    methods.append("MAD")

                severity = self._determine_severity(
                    iqr_outlier=iqr_outlier,
                    mad_outlier=mad_outlier,
                )

                issues.append(
                    QualityIssue(
                        issue_id=f"statistical_anomaly_{field}_{row_index}",
                        row_index=int(row_index),
                        source_field=field,
                        target_field=field,
                        issue_type=IssueType.STATISTICAL_ANOMALY,
                        severity=severity,
                        observed_value=self._plain(raw.loc[row_index]),
                        expected_condition=(
                            "Value should be reasonably consistent with "
                            "the observed distribution of the field."
                        ),
                        evidence={
                            "validation": "statistical_anomaly",
                            "methods": methods,
                            "sample_size": int(len(valid_values)),
                            "q1": float(iqr_bounds["q1"]),
                            "q3": float(iqr_bounds["q3"]),
                            "iqr": float(iqr_bounds["iqr"]),
                            "lower_iqr_bound": float(iqr_bounds["lower"]),
                            "upper_iqr_bound": float(iqr_bounds["upper"]),
                            "modified_z_score": float(mad_score),
                            "scale": "log10" if log_scale else "linear",
                            "typical_range": [
                                self._to_original(iqr_bounds["q1"], log_scale),
                                self._to_original(iqr_bounds["q3"], log_scale),
                            ],
                        },
                        recommendation=(
                            f"Review the {field} value because it is "
                            "statistically unusual compared with the "
                            "observed field distribution."
                        ),
                        confidence=self._calculate_confidence(
                            iqr_outlier=iqr_outlier,
                            mad_outlier=mad_outlier,
                        ),
                        uncertainty=(
                            "Statistical unusualness does not necessarily "
                            "indicate an invalid business value."
                        ),
                        status=IssueStatus.DETECTED,
                    )
                )

        return issues

    def _calculate_iqr_bounds(
        self,
        values: pd.Series,
    ) -> dict[str, float]:
        q1 = float(values.quantile(0.25))
        q3 = float(values.quantile(0.75))
        iqr = q3 - q1

        lower = q1 - self.iqr_multiplier * iqr
        upper = q3 + self.iqr_multiplier * iqr

        return {
            "q1": q1,
            "q3": q3,
            "iqr": float(iqr),
            "lower": float(lower),
            "upper": float(upper),
        }

    def _calculate_modified_z_scores(
        self,
        values: pd.Series,
    ) -> dict[Any, float]:
        median = float(values.median())

        absolute_deviation = (values - median).abs()
        mad = float(absolute_deviation.median())

        if mad == 0:
            return {index: 0.0 for index in values.index}

        modified_z_scores = (
            0.6745 * (values - median) / mad
        )

        return {
            index: float(score)
            for index, score in modified_z_scores.items()
        }

    @staticmethod
    def _plain(value: Any) -> Any:
        return value.item() if hasattr(value, "item") else value

    @staticmethod
    def _to_original(value: float, log_scale: bool) -> float:
        return round(float(10 ** value), 2) if log_scale else float(value)

    @staticmethod
    def _determine_severity(
        iqr_outlier: bool,
        mad_outlier: bool,
    ) -> IssueSeverity:
        if iqr_outlier and mad_outlier:
            return IssueSeverity.MEDIUM

        return IssueSeverity.LOW

    @staticmethod
    def _calculate_confidence(
        iqr_outlier: bool,
        mad_outlier: bool,
    ) -> float:
        if iqr_outlier and mad_outlier:
            return 0.95

        return 0.80