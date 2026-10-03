from __future__ import annotations

from typing import Any

import pandas as pd

from app.agents.sheet_discovery.header_detector import detect_header
from app.agents.sheet_discovery.profiler import profile_sheet


NON_SOV_SHEET_NAME_TERMS = {
    "glossary",
    "confidentiality",
    "disclaimer",
    "disclaimers",
    "questions",
    "yoy",
    "comparison",
    "summary",
    "autos",
    "trailer",
    "equipment",
}


SECONDARY_SOV_SHEET_NAME_TERMS = {
    "deleted",
    "elsewhere",
    "business interruption",
    "bi values",
}


PRIMARY_SOV_HEADER_TERMS = {
    "loc",
    "loc #",
    "location",
    "location id",
    "location name",
    "building",
    "bldg",
    "bldg #",
    "facility",
    "facility name",
    "companies and locations",
    "address",
    "city",
    "city / town",
    "state",
    "zip",
    "country",
    "latitude",
    "longitude",
    "construction",
    "construction type",
    "year built",
    "occupancy",
    "insured occupancy",
    "protection class",
    "sprinkler",
    "sprinkler %",
    "square footage",
    "sq. ft.",
    "buildings",
    "buildings and installations",
    "contents",
    "contents, machinery, equipment",
    "machinery & equipment values",
    "business personal property",
    "stock",
    "total pd",
    "tiv",
    "bi",
    "bi value",
    "business interruption",
    "total bi",
    "total overall",
    "total",
}

def _normalize_text(value: Any) -> str:
    return " ".join(
        str(value)
        .strip()
        .lower()
        .replace("\n", " ")
        .split()
    )


def _header_role_score(header: list[str]) -> float:
    if not header:
        return 0.0

    normalized = [_normalize_text(value) for value in header]
    header_text = " | ".join(normalized)

    matched = 0

    for term in PRIMARY_SOV_HEADER_TERMS:
        if term in header_text:
            matched += 1

    return matched / max(len(normalized), 1)


def _has_location_identity(header: list[str]) -> bool:
    normalized = [_normalize_text(value) for value in header]
    header_text = " | ".join(normalized)

    identity_terms = {
        "loc",
        "loc #",
        "location",
        "location id",
        "location name",
        "bldg",
        "bldg #",
        "building",
        "facility",
        "facility name",
        "complex/facility",
        "companies and locations",
        "address",
        "street",
        "street address",
        "city",
        "city / town",
        "latitude",
        "longitude",
    }

    return any(
        term in header_text
        for term in identity_terms
    )
def _has_property_attributes(header: list[str]) -> bool:
    normalized = [_normalize_text(value) for value in header]
    header_text = " | ".join(normalized)

    property_terms = {
        "construction",
        "construction type",
        "year built",
        "occupancy",
        "insured occupancy",
        "protection class",
        "sprinkler",
        "sprinkler %",
        "square footage",
        "sq. ft.",
        "sq. ft",
        "#floor",
        "no. of stories",
        "no. of bldgs",
        "buildings",
        "buildings and installations",
        "contents",
        "contents, machinery, equipment",
        "machinery & equipment values",
        "business personal property",
        "stock",
        "building values",
        "building value",
        "total pd",
        "tiv",
        "bi",
        "bi value",
        "business interruption",
        "total bi",
        "total overall",
        "total",
    }

    matches = sum(
        1
        for term in property_terms
        if term in header_text
    )

    return matches >= 3

def _is_secondary_sheet(
    sheet_name: str,
    header: list[str],
) -> bool:
    normalized_name = _normalize_text(sheet_name)

    header_text = " | ".join(
        _normalize_text(value) for value in header
    )

    if any(
        term in normalized_name
        for term in SECONDARY_SOV_SHEET_NAME_TERMS
    ):
        return True

    if "business interruption" in header_text:
        return True

    if (
        "bi value" in header_text
        and "building value" not in header_text
    ):
        return True

    if "notes" in header_text and "deleted" in normalized_name:
        return True

    return False


def classify_sheet_role(
    sheet_name: str,
    df: pd.DataFrame,
) -> dict[str, Any]:

    profile = profile_sheet(sheet_name, df)
    header = detect_header(df)

    normalized_name = _normalize_text(sheet_name)

    if any(
        term in normalized_name
        for term in NON_SOV_SHEET_NAME_TERMS
    ):
        return {
            "sheet_name": sheet_name,
            "role": "reject",
            "reason": "sheet_name_indicates_non_sov_content",
            "header": header,
            "profile": profile,
        }

    if header["header_row"] is None:
        return {
            "sheet_name": sheet_name,
            "role": "reject",
            "reason": "no_plausible_header_detected",
            "header": header,
            "profile": profile,
        }

    if header["header_rejected_as_data"]:
        return {
            "sheet_name": sheet_name,
            "role": "reject",
            "reason": "candidate_rows_look_like_repeated_data_records",
            "header": header,
            "profile": profile,
        }

    header_candidate = header["candidate_rows"][0]

    header_values = header_candidate.get(
        "header_values",
        [],
    )

    if not header_values:
        header_row = header["header_row"]

        if header_row is not None:
            header_values = (
                df.iloc[header_row]
                .dropna()
                .astype(str)
                .tolist()
            )

    header_score = _header_role_score(header_values)

    has_location_identity = _has_location_identity(
        header_values
    )

    has_property_attributes = _has_property_attributes(
        header_values
    )

    data_density = float(profile["data_density"])

    if _is_secondary_sheet(
        sheet_name,
        header_values,
    ):
        role = "secondary"
        reason = "specialized_or_excluded_exposure_sheet"

    elif (
        has_location_identity
        and has_property_attributes
        and data_density >= 0.15
    ):
        role = "primary"
        reason = "location_identity_and_property_attributes"

    elif (
        header_score >= 0.10
        and data_density >= 0.20
    ):
        role = "secondary"
        reason = "partial_sov_structure"

    else:
        role = "reject"
        reason = "insufficient_sov_structure"

    return {
        "sheet_name": sheet_name,
        "role": role,
        "reason": reason,
        "header": header,
        "profile": profile,
        "classification_features": {
            "header_role_score": round(
                header_score,
                4,
            ),
            "has_location_identity": has_location_identity,
            "has_property_attributes": has_property_attributes,
            "data_density": round(
                data_density,
                4,
            ),
        },
    }