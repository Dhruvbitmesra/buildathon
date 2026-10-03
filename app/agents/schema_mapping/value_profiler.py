import math
import re
from collections import Counter
from typing import Any

import numpy as np
import pandas as pd

from app.state.sov_state import ColumnProfile


MISSING_STRINGS = {
    "",
    "na",
    "n/a",
    "nan",
    "none",
    "null",
    "-",
    "--",
}


def _is_missing(value: Any) -> bool:
    if value is None:
        return True

    if isinstance(value, str):
        return value.strip().lower() in MISSING_STRINGS

    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _clean_string(value: Any) -> str:
    return str(value).strip()


def _parse_numeric(value: Any) -> float | None:
    if _is_missing(value):
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float, np.integer, np.floating)):
        numeric = float(value)
        return numeric if math.isfinite(numeric) else None

    text = _clean_string(value)

    text = re.sub(r"[$€£₹]", "", text)
    text = text.replace(",", "")

    multiplier = 1.0

    if text.lower().endswith("k"):
        multiplier = 1_000.0
        text = text[:-1]

    elif text.lower().endswith("m"):
        multiplier = 1_000_000.0
        text = text[:-1]

    elif text.lower().endswith("b"):
        multiplier = 1_000_000_000.0
        text = text[:-1]

    try:
        numeric = float(text.strip()) * multiplier
    except ValueError:
        return None

    return numeric if math.isfinite(numeric) else None


def _is_year_like(value: Any) -> bool:
    numeric = _parse_numeric(value)

    if numeric is None:
        return False

    return numeric.is_integer() and 1700 <= numeric <= 2100


def _is_boolean_like(value: Any) -> bool:
    if _is_missing(value):
        return False

    normalized = _clean_string(value).upper()

    return normalized in {
        "Y",
        "N",
        "YES",
        "NO",
        "TRUE",
        "FALSE",
        "T",
        "F",
    }


def _is_sprinkler_like(value: Any) -> bool:
    if _is_missing(value):
        return False

    normalized = _clean_string(value).upper()

    return normalized in {
        "Y",
        "N",
        "Y13",
        "Y(13R)",
    }


def _is_zip_like(value: Any) -> bool:
    if _is_missing(value):
        return False

    text = _clean_string(value)

    return bool(re.fullmatch(r"\d{5}(?:-\d{4})?", text))


def _is_currency_like(value: Any) -> bool:
    if _is_missing(value):
        return False

    text = _clean_string(value)

    if re.search(r"[$€£₹]", text):
        return True

    if re.search(r"\d[\d,]*\.\d+", text):
        return True

    if re.fullmatch(r"\d[\d,]*", text):
        return True

    if re.search(r"\d+(?:\.\d+)?\s*[KMBkmb]$", text):
        return True

    return False


def _calculate_pattern_ratio(
    values: list[Any],
    detector,
) -> float:
    non_missing = [
        value
        for value in values
        if not _is_missing(value)
    ]

    if not non_missing:
        return 0.0

    matches = sum(
        detector(value)
        for value in non_missing
    )

    return matches / len(non_missing)


def profile_column(
    column_name: str,
    values: pd.Series | list[Any],
    top_n: int = 10,
) -> ColumnProfile:
    """
    Build a local statistical and structural profile for one column.
    """

    series = (
        values
        if isinstance(values, pd.Series)
        else pd.Series(values)
    )

    raw_values = series.tolist()

    total_count = len(raw_values)

    missing_count = sum(
        _is_missing(value)
        for value in raw_values
    )

    non_missing_values = [
        value
        for value in raw_values
        if not _is_missing(value)
    ]

    non_missing_count = len(non_missing_values)

    missing_ratio = (
        missing_count / total_count
        if total_count
        else 0.0
    )

    cleaned_strings = [
        _clean_string(value)
        for value in non_missing_values
    ]

    unique_count = len(set(cleaned_strings))

    unique_ratio = (
        unique_count / non_missing_count
        if non_missing_count
        else 0.0
    )

    numeric_values = [
        numeric
        for value in non_missing_values
        if (numeric := _parse_numeric(value)) is not None
    ]

    numeric_ratio = (
        len(numeric_values) / non_missing_count
        if non_missing_count
        else 0.0
    )

    string_ratio = (
        1.0 - numeric_ratio
        if non_missing_count
        else 0.0
    )

    min_value = None
    max_value = None
    mean = None
    median = None
    std = None
    q1 = None
    q3 = None

    if numeric_values:
        numeric_array = np.array(
            numeric_values,
            dtype=float,
        )

        min_value = float(np.min(numeric_array))
        max_value = float(np.max(numeric_array))
        mean = float(np.mean(numeric_array))
        median = float(np.median(numeric_array))

        if len(numeric_array) > 1:
            std = float(np.std(numeric_array, ddof=1))
        else:
            std = 0.0

        q1 = float(np.percentile(numeric_array, 25))
        q3 = float(np.percentile(numeric_array, 75))

    value_counts = Counter(cleaned_strings)

    top_values = dict(
        value_counts.most_common(top_n)
    )

    patterns = {
        "year_like_ratio": _calculate_pattern_ratio(
            non_missing_values,
            _is_year_like,
        ),
        "boolean_like_ratio": _calculate_pattern_ratio(
            non_missing_values,
            _is_boolean_like,
        ),
        "sprinkler_like_ratio": _calculate_pattern_ratio(
            non_missing_values,
            _is_sprinkler_like,
        ),
        "zip_like_ratio": _calculate_pattern_ratio(
            non_missing_values,
            _is_zip_like,
        ),
        "currency_like_ratio": _calculate_pattern_ratio(
            non_missing_values,
            _is_currency_like,
        ),
    }

    data_type = str(series.dtype)

    return ColumnProfile(
        column_name=column_name,
        data_type=data_type,
        total_count=total_count,
        missing_count=missing_count,
        missing_ratio=missing_ratio,
        unique_count=unique_count,
        unique_ratio=unique_ratio,
        numeric_ratio=numeric_ratio,
        string_ratio=string_ratio,
        min_value=min_value,
        max_value=max_value,
        mean=mean,
        median=median,
        std=std,
        q1=q1,
        q3=q3,
        top_values=top_values,
        patterns=patterns,
    )


def profile_dataframe(
    dataframe: pd.DataFrame,
    top_n: int = 10,
) -> dict[str, ColumnProfile]:
    """
    Profile every column in a dataframe.
    """

    return {
        column_name: profile_column(
            column_name=column_name,
            values=dataframe[column_name],
            top_n=top_n,
        )
        for column_name in dataframe.columns
    }