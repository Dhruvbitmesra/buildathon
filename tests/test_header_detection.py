from app.ingestion.loader import load_sov_file
from app.agents.sheet_discovery.header_detector import detect_header


FILES = [
    "data/input/SOV_B4ID.xlsx",
    "data/input/SOV_H6D2.xlsx",
    "data/input/SOV_K4T9.xlsx",
    "data/input/SOV_Q8B3.xlsx",
]


def test_header_detection_on_real_sov_workbooks():
    """
    Run header detection across all real SOV workbooks.

    This is primarily a regression/integration test to make sure
    header detection runs successfully on the real datasets.
    """

    for file_path in FILES:
        state = load_sov_file(file_path)

        assert state.sheet_data, (
            f"No sheets were loaded from {file_path}"
        )

        for sheet_name, df in state.sheet_data.items():
            result = detect_header(df)

            assert isinstance(result, dict), (
                f"Invalid detector result for "
                f"{file_path} -> {sheet_name}"
            )

            assert "header_row" in result
            assert "header_score" in result
            assert "header_confidence" in result
            assert "candidate_rows" in result
            assert "possible_multirow_header" in result
            assert "header_rejected_as_data" in result


def test_header_candidates_have_compatible_keys():
    """
    Ensure every generated candidate contains both row identifiers.

    'row' is retained for compatibility with existing debugging/tests,
    while 'row_index' is the canonical internal field.
    """

    for file_path in FILES:
        state = load_sov_file(file_path)

        for sheet_name, df in state.sheet_data.items():
            result = detect_header(df)

            for candidate in result["candidate_rows"]:
                assert "row" in candidate
                assert "row_index" in candidate
                assert candidate["row"] == candidate["row_index"]