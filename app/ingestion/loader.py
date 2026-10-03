from pathlib import Path

from app.ingestion.csv_reader import read_csv_file
from app.ingestion.excel_reader import read_excel_file
from app.ingestion.file_validator import validate_file
from app.state.sov_state import SOVState


def load_sov_file(file_path: str) -> SOVState:
    """
    Validate and load an SOV file into SOVState.

    Supported formats:
        - .xlsx
        - .xls
        - .csv
    """

    # ---------------------------------------------------------
    # 1. Validate the input file
    # ---------------------------------------------------------

    path = validate_file(file_path)

    # ---------------------------------------------------------
    # 2. Determine file type
    # ---------------------------------------------------------

    extension = path.suffix.lower()

    # ---------------------------------------------------------
    # 3. Use the appropriate reader
    # ---------------------------------------------------------

    if extension in {".xlsx", ".xls"}:

        sheet_data, sheet_info = read_excel_file(
            path
        )

    elif extension == ".csv":

        sheet_data, sheet_info = read_csv_file(
            path
        )

    else:

        raise ValueError(
            f"Unsupported file extension: {extension}"
        )

    # ---------------------------------------------------------
    # 4. Create initial SOVState
    # ---------------------------------------------------------

    state = SOVState(
        file_name=path.name,
        file_type=extension.replace(".", ""),
        sheets=sheet_info,
        sheet_data=sheet_data,
    )

    return state