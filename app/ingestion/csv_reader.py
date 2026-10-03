from pathlib import Path

import pandas as pd

from app.state.sov_state import SheetInfo


def read_csv_file(
    file_path: str | Path,
) -> tuple[dict[str, pd.DataFrame], list[SheetInfo]]:
    """
    Read a CSV file and represent it as one logical sheet.

    Returns:
        sheet_data:
            Dictionary containing the CSV DataFrame.

        sheet_info:
            Basic metadata about the CSV.
    """

    # Read CSV without assuming the first row is the header
    df = pd.read_csv(
        file_path,
        header=None,
    )

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