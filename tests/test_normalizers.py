from datetime import datetime

import pandas as pd
import pytest

from app.agents.data_quality import normalizers
from app.agents.data_quality.normalizers import Operation


@pytest.mark.parametrize(
    "value, expected",
    [
        ("$1,200,000", 1200000.0),
        ("1.2M", 1200000.0),
        ("750K", 750000.0),
        ("2.5B", 2500000000.0),
        ("-500", -500.0),
        (100, 100.0),
        ("abc", None),
        ("1,20,0", None),
    ],
)
def test_parse_monetary(value, expected):
    assert normalizers.parse_monetary(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [(3, 3), (3.0, 3), ("3", 3), ("3.0", 3), (2.5, None), ("2 + B", None), (True, None)],
)
def test_parse_whole_int(value, expected):
    assert normalizers.parse_whole_int(value) == expected


def test_extract_year_from_dates():
    assert normalizers.extract_year(pd.Timestamp("2008-05-20")) == 2008
    assert normalizers.extract_year(datetime(1999, 1, 1)) == 1999
    assert normalizers.extract_year("2008-05-20") == 2008
    assert normalizers.extract_year("05/20/2008") == 2008
    assert normalizers.extract_year("1920's") is None


@pytest.mark.parametrize(
    "value, expected",
    [(802.0, "00802"), ("2108", "02108"), (2108, "02108"), ("02108", None), ("12", None)],
)
def test_pad_zip(value, expected):
    assert normalizers.pad_zip(value) == expected


def test_zip_digits_never_loses_leading_zero():
    assert normalizers.zip_digits("02108") == "02108"
    assert normalizers.zip_digits(75219.0) == "75219"


@pytest.mark.parametrize(
    "value, expected",
    [
        ("TX", "TX"),
        ("tx", "TX"),
        ("Texas", "TX"),
        ("Calif.", "CA"),
        ("V.I.", "VI"),
        ("N.Y.", "NY"),
        ("CAL", None),
        ("Atlantis", None),
    ],
)
def test_standardise_state(value, expected):
    assert normalizers.standardise_state(value) == expected


def test_sprinkler_scale_and_canonical_values():
    assert normalizers.infer_sprinkler_scale([0.0, 1.0, 0.5]) == 1.0
    assert normalizers.infer_sprinkler_scale(["100", 1, 0]) == 100.0
    assert normalizers.infer_sprinkler_scale(["Yes"]) is None

    assert normalizers.canonical_sprinkler(0.0, 1.0) == "N"
    assert normalizers.canonical_sprinkler(1.0, 1.0) == "Y"
    assert normalizers.canonical_sprinkler(0.57, 1.0) is None
    assert normalizers.canonical_sprinkler(1, 100.0) is None
    assert normalizers.canonical_sprinkler("Yes") == "Y"
    assert normalizers.canonical_sprinkler("13R") == "Y(13R)"
    assert normalizers.canonical_sprinkler("MAYBE") is None


def test_unknown_sprinkler_is_never_guessed():
    assert normalizers.propose("Fire Sprinklers (Y/N)", "MAYBE") is None


def test_negative_value_has_no_proposal():
    assert normalizers.propose("Building Value", -500000) is None


def test_missing_value_has_no_proposal():
    assert normalizers.propose("Building Value", None) is None
    assert normalizers.propose("Address", float("nan")) is None


def test_year_placeholder_proposes_blank_not_a_guess():
    proposal = normalizers.propose("Year Built", 9999)

    assert proposal.operation == Operation.SET_BLANK
    assert proposal.after_value is None
    assert not proposal.lossless


def test_sprinkler_synonym_is_lossless_but_numeric_is_not():
    alias = normalizers.propose("Fire Sprinklers (Y/N)", "YES")
    numeric = normalizers.propose(
        "Fire Sprinklers (Y/N)", 0.0, {"sprinkler_scale": 1.0}
    )

    assert alias.lossless is True
    assert numeric.lossless is False
    assert numeric.params == {"scale": 1.0}


def test_foreign_rows_get_no_us_proposals():
    context = {"is_us": False}

    assert normalizers.propose("Zip", 4000.0, context) is None
    assert normalizers.propose("State", "Texas", context) is None


def test_apply_operation_matches_proposal():
    cases = [
        ("Building Value", "$1,200,000", {}),
        ("Zip", 802.0, {}),
        ("State", "Texas", {}),
        ("Year Built", pd.Timestamp("2001-02-03"), {}),
        ("Fire Sprinklers (Y/N)", 0.0, {"sprinkler_scale": 1.0}),
        ("Address", "  1 Main   St ", {}),
    ]

    for field_name, value, context in cases:
        proposal = normalizers.propose(field_name, value, context)
        applied = normalizers.apply_operation(
            proposal.operation, value, proposal.params
        )

        assert applied.ok
        assert applied.value == proposal.after_value


def test_apply_operation_refuses_unsafe_conversion():
    result = normalizers.apply_operation(Operation.PARSE_MONETARY, "TBD")

    assert not result.ok
    assert result.error


def test_apply_operation_keeps_missing_values_blank():
    result = normalizers.apply_operation(Operation.PARSE_MONETARY, None)

    assert result.ok and result.value is None
