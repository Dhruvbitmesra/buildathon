import pandas as pd
import pytest

from app.agents.sheet_discovery.header_normalizer import (
    find_duplicate_normalized_headers,
    get_normalization_summary,
    normalize_header,
    normalize_header_row,
    normalize_headers,
)


def test_normalize_header_whitespace():
    result = normalize_header(
        "  Building    Replacement    Cost  "
    )

    assert result == "building replacement cost"


def test_normalize_header_case():
    result = normalize_header("BUILDING VALUE")

    assert result == "building value"


def test_normalize_header_punctuation():
    result = normalize_header("Bldg. Repl. Cost-New")

    assert result == "bldg repl cost new"


def test_normalize_header_separators():
    result = normalize_header("State-Code/Zip_Code")

    assert result == "state code zip code"

def test_abbreviations_are_preserved():
    result = normalize_header(
        "Bldg Repl Cost New"
    )

    assert result == "bldg repl cost new"


def test_empty_header():
    assert normalize_header(None) == ""
    assert normalize_header("") == ""


def test_normalize_headers_preserves_original():
    headers = [
        "Bldg. Value",
        "State",
        "Address",
    ]

    result = normalize_headers(headers)

    assert result[0]["original"] == "Bldg. Value"
    assert result[0]["normalized"] == "bldg value"
    assert result[1]["original"] == "State"
    assert result[1]["normalized"] == "state"


def test_empty_headers_keep_position():
    headers = [
        "Location",
        None,
        "State",
    ]

    result = normalize_headers(headers)

    assert result[0]["normalized"] == "location"
    assert result[1]["normalized"] == "unnamed_1"
    assert result[2]["normalized"] == "state"


def test_duplicate_headers_are_preserved():
    headers = [
        "Building Value",
        "building value",
        "State",
        "STATE",
    ]

    result = normalize_headers(headers)

    duplicates = find_duplicate_normalized_headers(result)

    assert duplicates["building value"] == [0, 1]
    assert duplicates["state"] == [2, 3]


def test_normalize_header_row():
    df = pd.DataFrame(
        [
            ["Report", None, None],
            ["Bldg. Value", "State-Code", "Year-Built"],
            [500000, "NJ", 2020],
        ]
    )

    result = normalize_header_row(
        df,
        header_row=1,
    )

    assert result[0]["original"] == "Bldg. Value"
    assert result[0]["normalized"] == "bldg value"

    assert result[1]["normalized"] == "state code"

    assert result[2]["normalized"] == "year built"


def test_invalid_header_row():
    df = pd.DataFrame(
        [
            ["A", "B"],
            ["C", "D"],
        ]
    )

    with pytest.raises(IndexError):
        normalize_header_row(
            df,
            header_row=10,
        )


def test_dataframe_is_not_modified():
    df = pd.DataFrame(
        [
            ["Report", None],
            ["Bldg. Value", "State"],
            [500000, "NJ"],
        ]
    )

    original = df.copy(deep=True)

    normalize_header_row(
        df,
        header_row=1,
    )

    pd.testing.assert_frame_equal(
        df,
        original,
    )


def test_normalization_summary():
    headers = [
        "Building Value",
        "building value",
        "State",
        None,
    ]

    normalized = normalize_headers(headers)

    summary = get_normalization_summary(
        normalized
    )

    assert summary["total_headers"] == 4
    assert summary["empty_headers"] == 1
    assert "building value" in summary["duplicate_headers"]