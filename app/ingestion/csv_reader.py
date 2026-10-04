import re
from pathlib import Path
from typing import Any

import pandas as pd

from app.state.sov_state import SheetInfo


# Plain numbers only. Tokens with a leading zero ("02108") stay text so
# identifiers such as ZIP codes keep their form.
_NUMBER_RE = re.compile(r"^-?(0|[1-9]\d*)(\.\d+)?$")


def _type_cell(value: Any) -> Any:
    """
    Give a CSV cell the type a spreadsheet would: plain integers and
    decimals become numbers, everything else stays as written.
    """

    if not isinstance(value, str):
        return value

    text = value.strip()

    if not _NUMBER_RE.match(text):
        return value

    number = float(text)

    return int(number) if "." not in text else number


def read_csv_file(
    file_path: str | Path,
) -> tuple[dict[str, pd.DataFrame], list[SheetInfo]]:
    """
    Read a CSV file and represent it as one logical sheet.

    The file is read as text without assuming a header row (Agent 1
    detects it), then plain numeric cells are typed individually so a
    header row inside the data does not force whole columns to text.

    Returns:
        sheet_data:
            Dictionary containing the CSV DataFrame.

        sheet_info:
            Basic metadata about the CSV.
    """

    df = pd.read_csv(
        file_path,
        header=None,
        dtype=str,
        keep_default_na=True,
    )

    df = df.astype(object).map(_type_cell)

    # CSV has no worksheets, so create one logical sheet
    sheet_name = "CSV_Data"

    sheet_data = {
        sheet_name: df
    }

    sheet_info = [
        SheetInfo(
            name=sheet_name,
            rows=len(df),
            columns=len(df.columns),
            is_empty=df.empty,
        )
    ]

    return sheet_data, sheet_info
