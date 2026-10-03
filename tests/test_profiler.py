from app.ingestion.loader import load_sov_file
from app.agents.sheet_discovery.profiler import (
    profile_all_sheets,
    profile_sheet,
)


def test_profile_single_sheet():
    state = load_sov_file(
        "data/input/SOV_B4ID.xlsx"
    )

    sheet_name = state.sheets[0].name

    profile = profile_sheet(
        sheet_name,
        state.sheet_data[sheet_name],
    )

    assert profile["sheet_name"] == sheet_name
    assert profile["rows"] > 0
    assert profile["columns"] > 0
    assert profile["non_empty_cells"] > 0
    assert 0 <= profile["data_density"] <= 1
    assert 0 <= profile["blank_row_ratio"] <= 1
    assert 0 <= profile["blank_column_ratio"] <= 1


def test_profile_all_real_workbooks():
    files = [
        "data/input/SOV_B4ID.xlsx",
        "data/input/SOV_H6D2.xlsx",
        "data/input/SOV_K4T9.xlsx",
        "data/input/SOV_Q8B3.xlsx",
    ]

    for file_path in files:
        state = load_sov_file(file_path)

        profiles = profile_all_sheets(
            state.sheet_data
        )

        assert len(profiles) == len(state.sheets)

        for profile in profiles:
            assert profile["rows"] >= 0
            assert profile["columns"] >= 0
            assert 0 <= profile["data_density"] <= 1
            assert 0 <= profile["blank_row_ratio"] <= 1
            assert 0 <= profile["blank_column_ratio"] <= 1