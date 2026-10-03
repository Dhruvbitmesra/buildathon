from pathlib import Path

import pandas as pd

from app.state.sov_state import SheetInfo


def read_excel_file(
    file_path: str | Path,
) -> tuple[dict[str, pd.DataFrame], list[SheetInfo]]:
    """
    Read every worksheet from an Excel workbook.

    Returns:
        sheet_data:
            Dictionary containing each worksheet as a DataFrame.

        sheet_info:
            Basic metadata about each worksheet.
    """

    # Open the workbook
    workbook = pd.ExcelFile(file_path)

    sheet_data = {}
    sheet_info = []

    # Process every worksheet
    for sheet_name in workbook.sheet_names:

        # Read without assuming where the header is
        df = pd.read_excel(
            workbook,
            sheet_name=sheet_name,
            header=None,
        )

        # Store raw DataFrame
        sheet_data[sheet_name] = df

        # Store basic sheet metadata
        sheet_info.append(
            SheetInfo(
                name=sheet_name,
                rows=len(df),
                columns=len(df.columns),
                is_empty=df.empty,
            )
        )

    return sheet_data, sheet_info