from __future__ import annotations

import re
from typing import Any

import pandas as pd


# Domain vocabulary used as supporting evidence for a possible SOV header.
SOV_HEADER_TERMS = {
    "location",
    "loc",
    "address",
    "street",
    "city",
    "state",
    "state code",
    "zip",
    "zip code",
    "postal",
    "building",
    "bldg",
    "property",
    "facility",
    "construction",
    "construction type",
    "occupancy",
    "year built",
    "year",
    "value",
    "building value",
    "replacement value",
    "replacement cost",
    "repl cost",
    "sprinkler",
    "fire protection",
    "fire prot",
    "county",
    "country",
    "latitude",
    "longitude",
}


DEFAULT_SEARCH_ROWS = 30


def _normalize_text(value: Any) -> str:
    """Normalize a cell value for textual analysis."""
    if pd.isna(value):
        return ""

    text = str(value).strip().lower()
    text = re.sub(r"\s+", " ", text)

    return text


def _is_empty(value: Any) -> bool:
    """Return True when a cell should be considered empty."""
    if pd.isna(value):
        return True

    return str(value).strip() == ""


def _is_numeric(value: Any) -> bool:
    """Check whether a value is numeric."""
    if _is_empty(value):
        return False

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return True

    text = str(value).strip()

    try:
        float(text.replace(",", "").replace("$", ""))
        return True
    except ValueError:
        return False


def calculate_non_empty_ratio(row: pd.Series) -> float:
    """Calculate the proportion of populated cells in a row."""
    if len(row) == 0:
        return 0.0

    non_empty = sum(not _is_empty(value) for value in row)

    return non_empty / len(row)


def calculate_text_ratio(row: pd.Series) -> float:
    """
    Calculate the proportion of non-empty cells that are textual.

    Empty cells are excluded from the denominator.
    """
    non_empty_values = [
        value for value in row
        if not _is_empty(value)
    ]

    if not non_empty_values:
        return 0.0

    text_values = [
        value
        for value in non_empty_values
        if not _is_numeric(value)
    ]

    return len(text_values) / len(non_empty_values)


def calculate_numeric_ratio(row: pd.Series) -> float:
    """Calculate the proportion of non-empty cells that are numeric."""
    non_empty_values = [
        value for value in row
        if not _is_empty(value)
    ]

    if not non_empty_values:
        return 0.0

    numeric_values = [
        value
        for value in non_empty_values
        if _is_numeric(value)
    ]

    return len(numeric_values) / len(non_empty_values)


def calculate_unique_ratio(row: pd.Series) -> float:
    """Calculate uniqueness among non-empty row values."""
    values = [
        _normalize_text(value)
        for value in row
        if not _is_empty(value)
    ]

    if not values:
        return 0.0

    return len(set(values)) / len(values)


def calculate_duplicate_ratio(row: pd.Series) -> float:
    """Calculate the proportion of duplicate non-empty values."""
    return 1.0 - calculate_unique_ratio(row)


def calculate_sov_term_ratio(row: pd.Series) -> float:
    """
    Calculate how strongly a row resembles SOV terminology.

    A match is counted when a normalized cell contains one of the
    known SOV/property terms.
    """
    values = [
        _normalize_text(value)
        for value in row
        if not _is_empty(value)
    ]

    if not values:
        return 0.0

    matches = 0

    for value in values:
        if any(term in value for term in SOV_HEADER_TERMS):
            matches += 1

    return matches / len(values)


def calculate_data_below_score(
    df: pd.DataFrame,
    row_index: int,
    lookahead: int = 5,
) -> float:
    """
    Estimate whether meaningful tabular data exists below a candidate row.

    We inspect up to `lookahead` rows after the candidate and measure
    how populated they are relative to the candidate width.
    """
    if df.empty or row_index >= len(df) - 1:
        return 0.0

    start = row_index + 1
    end = min(row_index + 1 + lookahead, len(df))

    rows_below = df.iloc[start:end]

    if rows_below.empty:
        return 0.0

    densities = []

    for _, row in rows_below.iterrows():
        densities.append(calculate_non_empty_ratio(row))

    if not densities:
        return 0.0

    return float(sum(densities) / len(densities))


def calculate_header_score(
    *,
    non_empty_ratio: float,
    text_ratio: float,
    unique_ratio: float,
    sov_term_ratio: float,
    numeric_ratio: float,
    duplicate_ratio: float,
    data_below_score: float,
) -> float:
    """
    Calculate deterministic header-likeness score.

    The score is bounded between 0 and 1.
    """

    score = (
        0.20 * non_empty_ratio
        + 0.20 * text_ratio
        + 0.15 * unique_ratio
        + 0.20 * sov_term_ratio
        + 0.25 * data_below_score
        - 0.15 * numeric_ratio
        - 0.10 * duplicate_ratio
    )

    return max(0.0, min(1.0, score))


def determine_confidence(
    best_score: float,
    second_score: float | None,
) -> str:
    """
    Determine qualitative confidence from score and separation
    from the second-best candidate.
    """
    if second_score is None:
        if best_score >= 0.60:
            return "high"
        if best_score >= 0.35:
            return "medium"
        return "low"

    gap = best_score - second_score

    if best_score >= 0.65 and gap >= 0.10:
        return "high"

    if best_score >= 0.45 and gap >= 0.05:
        return "medium"

    return "low"


def detect_possible_multirow_header(
    df: pd.DataFrame,
    header_row: int,
) -> bool:
    """
    Detect a possible two-row/grouped header.

    This is only a flag. It does not modify or merge the rows.
    """
    if header_row <= 0:
        return False

    current_row = df.iloc[header_row]

    previous_row = df.iloc[header_row - 1]

    current_non_empty = calculate_non_empty_ratio(current_row)
    previous_non_empty = calculate_non_empty_ratio(previous_row)

    current_text = calculate_text_ratio(current_row)
    previous_text = calculate_text_ratio(previous_row)

    # A previous row with meaningful text and a partially populated
    # current header row may indicate grouped/two-level headers.
    if (
        previous_non_empty >= 0.20
        and previous_text >= 0.50
        and current_non_empty >= 0.40
        and current_text >= 0.50
    ):
        return True

    return False


def generate_header_candidates(
    df: pd.DataFrame,
    max_rows: int = DEFAULT_SEARCH_ROWS,
) -> list[dict[str, Any]]:
    """
    Generate and score possible header rows from the first `max_rows`.
    """
    if df.empty:
        return []

    search_limit = min(max_rows, len(df))
    candidates: list[dict[str, Any]] = []

    for row_index in range(search_limit):
        row = df.iloc[row_index]

        # Completely blank rows are not header candidates.
        if calculate_non_empty_ratio(row) == 0.0:
            continue

        non_empty_ratio = calculate_non_empty_ratio(row)
        text_ratio = calculate_text_ratio(row)
        numeric_ratio = calculate_numeric_ratio(row)
        unique_ratio = calculate_unique_ratio(row)
        duplicate_ratio = calculate_duplicate_ratio(row)
        sov_term_ratio = calculate_sov_term_ratio(row)
        data_below_score = calculate_data_below_score(
            df,
            row_index,
        )

        score = calculate_header_score(
            non_empty_ratio=non_empty_ratio,
            text_ratio=text_ratio,
            unique_ratio=unique_ratio,
            sov_term_ratio=sov_term_ratio,
            numeric_ratio=numeric_ratio,
            duplicate_ratio=duplicate_ratio,
            data_below_score=data_below_score,
        )

        candidates.append(
            {
                "row": row_index,
                "score": round(score, 4),
                "non_empty_ratio": round(non_empty_ratio, 4),
                "text_ratio": round(text_ratio, 4),
                "numeric_ratio": round(numeric_ratio, 4),
                "unique_ratio": round(unique_ratio, 4),
                "duplicate_ratio": round(duplicate_ratio, 4),
                "sov_term_ratio": round(sov_term_ratio, 4),
                "data_below_score": round(data_below_score, 4),
            }
        )

    candidates.sort(
        key=lambda candidate: candidate["score"],
        reverse=True,
    )

    return candidates


def detect_header(
    df: pd.DataFrame,
    max_rows: int = DEFAULT_SEARCH_ROWS,
) -> dict[str, Any]:
    """
    Detect the most likely header row in a raw SOV sheet.
    """
    candidates = generate_header_candidates(
        df,
        max_rows=max_rows,
    )

    if not candidates:
        return {
            "header_row": None,
            "header_score": 0.0,
            "header_confidence": "low",
            "candidate_rows": [],
            "possible_multirow_header": False,
        }

    best_candidate = candidates[0]

    second_score = (
        candidates[1]["score"]
        if len(candidates) > 1
        else None
    )

    confidence = determine_confidence(
        best_score=best_candidate["score"],
        second_score=second_score,
    )

    header_row = best_candidate["row"]

    possible_multirow = detect_possible_multirow_header(
        df,
        header_row,
    )

    return {
        "header_row": header_row,
        "header_score": best_candidate["score"],
        "header_confidence": confidence,
        "candidate_rows": candidates,
        "possible_multirow_header": possible_multirow,
    }