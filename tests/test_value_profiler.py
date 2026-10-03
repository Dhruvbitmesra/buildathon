import pandas as pd

from app.agents.schema_mapping.value_profiler import (
    profile_column,
    profile_dataframe,
)


def test_numeric_profile():
    values = pd.Series([100, 200, 300, 400])

    profile = profile_column("Building Value", values)

    assert profile.total_count == 4
    assert profile.missing_count == 0
    assert profile.numeric_ratio == 1.0
    assert profile.min_value == 100.0
    assert profile.max_value == 400.0
    assert profile.median == 250.0


def test_missing_values():
    values = pd.Series(
        [100, None, "", "N/A", 200]
    )

    profile = profile_column("Value", values)

    assert profile.total_count == 5
    assert profile.missing_count == 3
    assert profile.missing_ratio == 0.6


def test_unique_ratio():
    values = pd.Series(
        ["A", "A", "B", "B"]
    )

    profile = profile_column("Occupancy", values)

    assert profile.unique_count == 2
    assert profile.unique_ratio == 0.5


def test_top_values():
    values = pd.Series(
        ["Office", "Office", "Retail", "Office", "Retail"]
    )

    profile = profile_column("Occupancy", values)

    assert profile.top_values["Office"] == 3
    assert profile.top_values["Retail"] == 2


def test_year_pattern():
    values = pd.Series(
        [1980, 1995, 2001, 2020]
    )

    profile = profile_column("Year Built", values)

    assert profile.patterns["year_like_ratio"] == 1.0


def test_boolean_pattern():
    values = pd.Series(
        ["Y", "N", "Y", "N"]
    )

    profile = profile_column(
        "Fire Sprinklers (Y/N)",
        values,
    )

    assert profile.patterns["boolean_like_ratio"] == 1.0
    assert profile.patterns["sprinkler_like_ratio"] == 1.0


def test_sprinkler_pattern():
    values = pd.Series(
        ["Y", "N", "Y13", "Y(13R)"]
    )

    profile = profile_column(
        "Sprinklers",
        values,
    )

    assert profile.patterns["sprinkler_like_ratio"] == 1.0


def test_zip_pattern():
    values = pd.Series(
        ["12345", "54321", "10001"]
    )

    profile = profile_column(
        "Zip",
        values,
    )

    assert profile.patterns["zip_like_ratio"] == 1.0


def test_currency_pattern():
    values = pd.Series(
        ["$100,000", "$250,000", "1.2M"]
    )

    profile = profile_column(
        "Building Value",
        values,
    )

    assert profile.patterns["currency_like_ratio"] == 1.0
    assert profile.numeric_ratio == 1.0


def test_numeric_statistics():
    values = pd.Series(
        [10, 20, 30, 40, 50]
    )

    profile = profile_column("Value", values)

    assert profile.mean == 30.0
    assert profile.median == 30.0
    assert profile.q1 == 20.0
    assert profile.q3 == 40.0


def test_dataframe_profile():
    dataframe = pd.DataFrame(
        {
            "Building Value": [100, 200, 300],
            "Occupancy": ["Office", "Retail", "Office"],
        }
    )

    profiles = profile_dataframe(dataframe)

    assert len(profiles) == 2
    assert "Building Value" in profiles
    assert "Occupancy" in profiles


def test_empty_column():
    values = pd.Series([], dtype="object")

    profile = profile_column("Empty", values)

    assert profile.total_count == 0
    assert profile.missing_count == 0
    assert profile.numeric_ratio == 0.0
    assert profile.missing_ratio == 0.0