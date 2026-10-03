from app.ingestion.loader import load_sov_file


def test_excel_ingestion():
    state = load_sov_file(
        "data/input/SOV_B4ID.xlsx"
    )

    assert state.file_name == "SOV_B4ID.xlsx"
    assert state.file_type == "xlsx"
    assert len(state.sheets) >= 1
    assert len(state.sheet_data) >= 1
    assert state.selected_sheet is None
    assert state.errors == []


def test_all_real_workbooks_can_be_loaded():
    files = [
        "data/input/SOV_B4ID.xlsx",
        "data/input/SOV_H6D2.xlsx",
        "data/input/SOV_K4T9.xlsx",
        "data/input/SOV_Q8B3.xlsx",
    ]

    for file_path in files:
        state = load_sov_file(file_path)

        assert state.file_type == "xlsx"
        assert len(state.sheets) >= 1
        assert len(state.sheet_data) >= 1
        assert state.selected_sheet is None
        assert state.errors == []