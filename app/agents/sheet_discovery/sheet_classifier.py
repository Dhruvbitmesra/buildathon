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
}


def classify_sheet_role(
    sheet_name: str,
    df: pd.DataFrame,
) -> dict[str, Any]:

    profile = profile_sheet(sheet_name, df)
    header = detect_header(df)

    normalized_name = sheet_name.strip().lower()

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

    sov_signal = header_candidate["sov_term_ratio"]
    data_density = profile["data_density"]

    if sov_signal >= 0.15 and data_density >= 0.20:
        role = "primary"

    elif sov_signal >= 0.05 and data_density >= 0.15:
        role = "secondary"

    else:
        role = "reject"

    return {
        "sheet_name": sheet_name,
        "role": role,
        "reason": "combined_header_and_sheet_evidence",
        "header": header,
        "profile": profile,
    }