from __future__ import annotations

import re

import pandas as pd

from app.state.sov_state import SheetInfo


SOV_KEYWORDS = {
    "location",
    "loc",
    "building",
    "bldg",
    "facility",
    "address",
    "street",
    "city",
    "state",
    "zip",
    "postal",
    "construction",
    "year built",
    "value",
    "replacement",
    "sprinkler",
    "occupancy",
    "property",
}


def _normalize_text(value: object) -> str:
    """Convert a cell value into normalized searchable text."""
    if pd.isna(value):
        return ""

    text = str(value).strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def calculate_data_density(df: pd.DataFrame) -> float:
    """Calculate the proportion of non-empty cells."""
    if df.empty or df.size == 0:
        return 0.0

    return float(df.notna().sum().sum() / df.size)


def calculate_blank_row_ratio(df: pd.DataFrame) -> float:
    """Calculate the proportion of completely blank rows."""
    if df.empty:
        return 1.0

    blank_rows = df.isna().all(axis=1).sum()
    return float(blank_rows / len(df))


def calculate_blank_column_ratio(df: pd.DataFrame) -> float:
    """Calculate the proportion of completely blank columns."""
    if df.empty:
        return 1.0

    blank_columns = df.isna().all(axis=0).sum()
    return float(blank_columns / len(df.columns))


def calculate_non_empty_row_count(df: pd.DataFrame) -> int:
    """Count rows containing at least one non-empty value."""
    if df.empty:
        return 0

    return int((~df.isna().all(axis=1)).sum())


def calculate_sov_keyword_score(df: pd.DataFrame) -> float:
    """
    Calculate the proportion of SOV-related keywords found
    in the worksheet's non-empty cell values.
    """
    if df.empty:
        return 0.0

    values = [
        _normalize_text(value)
        for value in df.to_numpy().flatten()
        if not pd.isna(value)
    ]

    if not values:
        return 0.0

    matches = 0

    for value in values:
        if any(keyword in value for keyword in SOV_KEYWORDS):
            matches += 1

    return float(matches / len(values))


def profile_sheet(
    sheet_name: str,
    df: pd.DataFrame,
) -> dict:
    """Generate structural evidence for one worksheet."""

    total_cells = int(df.size)

    non_empty_cells = (
        int(df.notna().sum().sum())
        if not df.empty
        else 0
    )

    return {
        "sheet_name": sheet_name,
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "total_cells": total_cells,
        "non_empty_cells": non_empty_cells,
        "data_density": calculate_data_density(df),
        "blank_row_ratio": calculate_blank_row_ratio(df),
        "blank_column_ratio": calculate_blank_column_ratio(df),
        "non_empty_row_count": calculate_non_empty_row_count(df),
        "sov_keyword_score": calculate_sov_keyword_score(df),
        "is_empty": bool(df.empty),
    }


def profile_all_sheets(
    sheet_data: dict[str, pd.DataFrame],
) -> list[dict]:
    """Profile every worksheet in an SOV workbook."""

    profiles = []

    for sheet_name, df in sheet_data.items():
        profiles.append(
            profile_sheet(
                sheet_name=sheet_name,
                df=df,
            )
        )

    return profiles