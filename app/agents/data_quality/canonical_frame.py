"""
Adapter between Agent 2 and Agent 3.

Agent 2 produces column mappings (source header -> target field).
Agent 3 validates data under the 17 target field names. This module
builds that canonical view as a copy, keeping what Agent 4's audit log
needs: the source column for every target field and the original
workbook row number for every row.
"""

from dataclasses import dataclass, field
from typing import Any, Iterable

import pandas as pd

from app.agents.data_quality.config import SOV_REQUIRED_FIELDS


@dataclass
class CanonicalFrame:
    dataframe: pd.DataFrame

    # target field -> source header
    source_columns: dict[str, str] = field(default_factory=dict)

    # row index -> 1-based workbook row number (None when unknown)
    source_rows: dict[int, int] = field(default_factory=dict)

    unmapped_source_columns: list[str] = field(default_factory=list)


def _get(mapping: Any, *names: str) -> Any:
    for name in names:
        if isinstance(mapping, dict) and name in mapping:
            return mapping[name]

        if hasattr(mapping, name):
            return getattr(mapping, name)

    return None


def build_canonical_frame(
    source: pd.DataFrame,
    mappings: Iterable[Any],
    header_row: int | None = None,
    row_numbers: list[int] | None = None,
) -> CanonicalFrame:
    """
    Select and rename mapped source columns to target field names.

    Parameters
    ----------
    source:
        Data rows of the primary sheet, with source headers as columns.
    mappings:
        Agent 2 mappings (BatchMapping objects or dicts with
        source_header and target_field).
    header_row:
        0-based position of the header row in the worksheet. When
        given, source_rows holds the 1-based Excel row of each data row
        (header_row + 2 + position).
    row_numbers:
        Explicit 1-based Excel row of each data row (e.g. Agent 1's
        table index after blank/total rows were excluded). Takes
        precedence over header_row.

    The source DataFrame is not modified. Values are copied with
    object dtype so identifiers such as ZIP "02108" keep their form.
    """

    columns: dict[str, str] = {}
    unmapped: list[str] = []

    for mapping in mappings:
        source_header = _get(mapping, "source_header", "source_column")
        target = _get(mapping, "target_field", "target")

        if source_header is None:
            continue

        if target is None:
            unmapped.append(str(source_header))
            continue

        if target not in SOV_REQUIRED_FIELDS:
            raise ValueError(f"{target!r} is not a target field")

        if target in columns:
            raise ValueError(
                f"{target} is mapped from both '{columns[target]}' and "
                f"'{source_header}'"
            )

        if source_header not in source.columns:
            raise KeyError(f"Source column '{source_header}' not found")

        columns[target] = source_header

    ordered_targets = [
        target for target in SOV_REQUIRED_FIELDS if target in columns
    ]

    canonical = pd.DataFrame(
        {
            target: source[columns[target]].astype(object).to_numpy()
            for target in ordered_targets
        },
        index=pd.RangeIndex(len(source)),
        dtype=object,
    )

    if row_numbers is not None:
        if len(row_numbers) != len(source):
            raise ValueError("row_numbers must have one entry per row")

        source_rows = {
            position: int(number) for position, number in enumerate(row_numbers)
        }
    elif header_row is not None:
        source_rows = {
            position: header_row + 2 + position
            for position in range(len(source))
        }
    else:
        source_rows = {}

    return CanonicalFrame(
        dataframe=canonical,
        source_columns={target: str(columns[target]) for target in ordered_targets},
        source_rows=source_rows,
        unmapped_source_columns=unmapped,
    )
