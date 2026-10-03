from pathlib import Path

import pandas as pd

from app.agents.sheet_discovery.header_detector import detect_header
from app.agents.sheet_discovery.sheet_classifier import classify_sheet_role


DATA_DIR = Path("data/input")


def load_q8b3_sheet(name: str) -> pd.DataFrame:
    return pd.read_excel(
        DATA_DIR / "SOV_Q8B3.xlsx",
        sheet_name=name,
        header=None,
    )


def test_trailer_does_not_invent_header_from_data_row():
    """
    Trailer contains actual data records that can look structurally
    similar to a header. The detector must reject them.
    """

    df = load_q8b3_sheet("Trailer")

    result = detect_header(df)

    assert result["header_row"] is None
    assert result["header_rejected_as_data"] is True


def test_equipment_does_not_invent_header_from_data_row():
    """
    Equipment contains actual data records that can look like headers.
    The detector must reject them.
    """

    df = load_q8b3_sheet("Equipment")

    result = detect_header(df)

    assert result["header_row"] is None
    assert result["header_rejected_as_data"] is True


def test_glossary_is_rejected_as_non_sov():
    """
    Glossary is reference/documentation content rather than the
    primary SOV data table.
    """

    df = pd.DataFrame(
        [
            [None, None, None],
            [None, None, None],
            ["RMS Construction", "Definition", None],
            [
                "Year Built",
                "year in which the structure was constructed.",
                None,
            ],
            [
                "Sprinkler",
                "fire protection system description.",
                None,
            ],
        ]
    )

    result = classify_sheet_role(
        "Glossary",
        df,
    )

    assert result["role"] == "reject"
    assert result["reason"] == "sheet_name_indicates_non_sov_content"


def test_confidentiality_is_rejected():
    """
    Confidentiality text is not an SOV data table.
    """

    df = pd.DataFrame(
        [
            [None, None],
            ["Confidentiality", None],
            [
                "Acceptance of this document shall be deemed agreement.",
                None,
            ],
        ]
    )

    result = classify_sheet_role(
        "Confidentiality",
        df,
    )

    assert result["role"] == "reject"


def test_vendor_disclaimer_is_rejected():
    """
    Vendor disclaimer text is not an SOV data table.
    """

    df = pd.DataFrame(
        [
            [None, None],
            ["FEMA Disclaimer", None],
            ["Long disclaimer text.", None],
        ]
    )

    result = classify_sheet_role(
        "Vendor Disclaimers",
        df,
    )

    assert result["role"] == "reject"


def test_all_autos_can_have_a_header_but_is_not_primary_property_sov():
    """
    All Autos may contain a legitimate-looking header, but it should
    not be classified as the primary property SOV sheet.
    """

    df = load_q8b3_sheet("All Autos")

    result = classify_sheet_role(
        "All Autos",
        df,
    )

    assert result["header"]["header_row"] == 1
    assert result["role"] != "primary"