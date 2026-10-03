import pandas as pd

from app.agents.schema_mapping.field_evidence import (
    rank_field_evidence,
    score_field_evidence,
)
from app.agents.schema_mapping.value_profiler import profile_column


def _scores(profile):
    return {
        result.target_field: result
        for result in score_field_evidence(profile)
    }


def test_all_17_fields_receive_evidence():
    profile = profile_column(
        "Unknown",
        pd.Series(["A", "B", "C"]),
    )

    results = score_field_evidence(profile)

    assert len(results) == 17


def test_all_scores_are_between_zero_and_one():
    profile = profile_column(
        "Unknown",
        pd.Series([100, 200, 300]),
    )

    results = score_field_evidence(profile)

    for result in results:
        assert 0.0 <= result.score <= 1.0

        for value in result.components.values():
            assert 0.0 <= value <= 1.0


def test_monetary_column_has_strong_money_evidence():
    profile = profile_column(
        "Unknown",
        pd.Series(["$100,000", "$250,000", "$500,000"]),
    )

    scores = _scores(profile)

    assert scores["Building Value"].score >= 0.8
    assert scores["Contents"].score >= 0.8
    assert scores["BI"].score >= 0.8
    assert scores["Other"].score >= 0.8


def test_year_column_has_strong_year_evidence():
    profile = profile_column(
        "Unknown",
        pd.Series([1980, 1990, 2000, 2010]),
    )

    scores = _scores(profile)

    assert scores["Year Built"].score == 1.0


def test_sprinkler_column_has_strong_evidence():
    profile = profile_column(
        "Unknown",
        pd.Series(["Y", "N", "Y13", "Y(13R)"]),
    )

    scores = _scores(profile)

    assert scores["Fire Sprinklers (Y/N)"].score == 1.0


def test_zip_column_has_strong_zip_evidence():
    profile = profile_column(
        "Unknown",
        pd.Series(["12345", "54321", "10001"]),
    )

    scores = _scores(profile)

    assert scores["Zip"].score >= 0.75


def test_storeys_column_has_small_integer_evidence():
    profile = profile_column(
        "Unknown",
        pd.Series([1, 2, 3, 4, 5]),
    )

    scores = _scores(profile)

    assert scores["Storeys"].score == 1.0
    assert scores["Number of Buildings"].score == 1.0


def test_reference_column_has_uniqueness_evidence():
    profile = profile_column(
        "Unknown",
        pd.Series([
            "LOC-001",
            "LOC-002",
            "LOC-003",
            "LOC-004",
        ]),
    )

    scores = _scores(profile)

    assert scores["Reference"].score >= 0.65


def test_categorical_column_has_occupancy_evidence():
    profile = profile_column(
        "Unknown",
        pd.Series([
            "Office",
            "Office",
            "Office",
            "Retail",
            "Retail",
        ]),
    )

    scores = _scores(profile)

    assert scores["Occupancy"].score >= 0.5


def test_string_column_has_address_evidence():
    profile = profile_column(
        "Unknown",
        pd.Series([
            "12 Main Street",
            "45 Oak Road",
            "78 Park Avenue",
        ]),
    )

    scores = _scores(profile)

    assert scores["Address"].score >= 0.7


def test_ranking_is_sorted():
    profile = profile_column(
        "Unknown",
        pd.Series(["Y", "N", "Y13", "Y(13R)"]),
    )

    ranked = rank_field_evidence(profile)

    scores = [result.score for result in ranked]

    assert scores == sorted(
        scores,
        reverse=True,
    )


def test_evidence_contains_reasons():
    profile = profile_column(
        "Unknown",
        pd.Series(["Y", "N", "Y", "N"]),
    )

    results = score_field_evidence(profile)

    sprinkler = next(
        result
        for result in results
        if result.target_field == "Fire Sprinklers (Y/N)"
    )

    assert sprinkler.reasons