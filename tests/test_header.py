import pandas as pd

from app.agents.sheet_discovery.header_detector import (
    calculate_data_below_score,
    calculate_non_empty_ratio,
    calculate_text_ratio,
    detect_header,
    generate_header_candidates,
)
from app.ingestion.loader import load_sov_file


REAL_SOV_FILES = [
    "data/input/SOV_B4ID.xlsx",
    "data/input/SOV_H6D2.xlsx",
    "data/input/SOV_K4T9.xlsx",
    "data/input/SOV_Q8B3.xlsx",
]


def test_non_empty_ratio():
    row = pd.Series(["Location", "Address", None, "State"])

    result = calculate_non_empty_ratio(row)

    assert result == 0.75


def test_text_ratio():
    row = pd.Series(["Location", "Address", None, "State"])

    result = calculate_text_ratio(row)

    assert result == 1.0


def test_data_below_score():
    df = pd.DataFrame(
        [
            ["Title", None, None],
            ["Location", "Address", "State"],
            ["001", "Main Street", "NJ"],
            ["002", "Second Street", "NY"],
        ]
    )

    result = calculate_data_below_score(
        df,
        row_index=1,
    )

    assert result > 0


def test_header_detection_on_simple_data():
    df = pd.DataFrame(
        [
            ["Statement of Values", None, None],
            ["Client", "ABC Insurance", None],
            [None, None, None],
            ["Location", "Address", "State"],
            ["001", "Main Street", "NJ"],
            ["002", "Second Street", "NY"],
        ]
    )

    result = detect_header(df)

    assert result["header_row"] == 3
    assert result["header_score"] > 0
    assert result["header_confidence"] in {
        "high",
        "medium",
        "low",
    }


def test_blank_rows_are_not_candidates():
    df = pd.DataFrame(
        [
            [None, None, None],
            ["Location", "Address", "State"],
            ["001", "Main Street", "NJ"],
        ]
    )

    candidates = generate_header_candidates(df)

    candidate_rows = [
        candidate["row"]
        for candidate in candidates
    ]

    assert 0 not in candidate_rows


def test_header_detection_does_not_modify_dataframe():
    df = pd.DataFrame(
        [
            ["Report", None, None],
            ["Location", "Address", "State"],
            ["001", "Main Street", "NJ"],
        ]
    )

    original = df.copy(deep=True)

    detect_header(df)

    pd.testing.assert_frame_equal(
        df,
        original,
    )


def test_all_real_sov_workbooks():
    for file_path in REAL_SOV_FILES:
        state = load_sov_file(file_path)

        for sheet_name, df in state.sheet_data.items():
            result = detect_header(df)

            assert "header_row" in result
            assert "header_score" in result
            assert "header_confidence" in result
            assert "candidate_rows" in result
            assert "possible_multirow_header" in result

            assert 0 <= result["header_score"] <= 1

            for candidate in result["candidate_rows"]:
                assert 0 <= candidate["score"] <= 1