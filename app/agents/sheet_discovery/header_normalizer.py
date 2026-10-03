from __future__ import annotations

import re
from typing import Any

import pandas as pd


def normalize_header(value: Any) -> str:
    """
    Normalize a single raw header value.

    This function performs only syntactic normalization.
    It does NOT perform semantic schema mapping.
    """

    # Handle empty / missing values.
    if value is None or pd.isna(value):
        return ""

    text = str(value).strip().lower()

    # Normalize common separators to spaces.
    text = re.sub(r"[-_/]", " ", text)

    # Remove punctuation while preserving letters, numbers and spaces.
    text = re.sub(r"[^\w\s]", " ", text)

    # Collapse repeated whitespace.
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalize_headers(
    headers: list[Any],
) -> list[dict[str, Any]]:
    """
    Normalize a list of headers while preserving the originals.

    Empty headers receive a positional placeholder so that
    column positions are never lost.
    """

    normalized_headers = []

    for index, header in enumerate(headers):
        original = None if pd.isna(header) else str(header)

        normalized = normalize_header(header)

        # Preserve column position for empty headers.
        if not normalized:
            normalized = f"unnamed_{index}"

        normalized_headers.append(
            {
                "column_index": index,
                "original": original,
                "normalized": normalized,
            }
        )

    return normalized_headers


def normalize_header_row(
    df: pd.DataFrame,
    header_row: int,
) -> list[dict[str, Any]]:
    """
    Extract and normalize a detected header row.

    The original DataFrame is not modified.
    """

    if df.empty:
        return []

    if header_row < 0 or header_row >= len(df):
        raise IndexError(
            f"Header row {header_row} is outside "
            f"the DataFrame range 0-{len(df) - 1}."
        )

    raw_headers = df.iloc[header_row].tolist()

    return normalize_headers(raw_headers)


def find_duplicate_normalized_headers(
    normalized_headers: list[dict[str, Any]],
) -> dict[str, list[int]]:
    """
    Find normalized headers that occur more than once.

    Returns:
        {
            "building value": [2, 7],
            "state": [4, 8]
        }
    """

    positions: dict[str, list[int]] = {}

    for item in normalized_headers:
        normalized = item["normalized"]

        positions.setdefault(normalized, []).append(
            item["column_index"]
        )

    return {
        header: indices
        for header, indices in positions.items()
        if len(indices) > 1
    }


def get_normalization_summary(
    normalized_headers: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Generate summary information about normalized headers.
    """

    duplicates = find_duplicate_normalized_headers(
        normalized_headers
    )

    return {
        "total_headers": len(normalized_headers),
        "empty_headers": sum(
            item["original"] is None
            for item in normalized_headers
        ),
        "unique_normalized_headers": len(
            {
                item["normalized"]
                for item in normalized_headers
            }
        ),
        "duplicate_headers": duplicates,
    }