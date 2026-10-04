"""
Agent 1: Sheet Intelligence and Discovery.

Scans every worksheet, classifies it (Primary / Secondary / Reject),
ranks the candidates, selects the authoritative data sheet and extracts
its data table below the detected header row.

Table extraction is structural only - no cell value is changed:
- header cells become unique, whitespace-normalised column names;
- fully blank columns without a header are dropped;
- blank rows, "Total" rows and single-cell note/footer rows are
  excluded and listed in excluded_rows so the reviewer can see them;
- the table index holds the 1-based Excel row number of each row.
"""

import math
import re
from typing import Any, Optional

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from app.agents.sheet_discovery.sheet_classifier import classify_sheet_role


_ROLE_LABELS = {
    "primary": "Primary",
    "secondary": "Secondary",
    "reject": "Reject",
}

_REASON_TEXT = {
    "sheet_name_indicates_non_sov_content": (
        "Sheet name indicates non-SOV content"
    ),
    "no_plausible_header_detected": "No plausible header row detected",
    "candidate_rows_look_like_repeated_data_records": (
        "Candidate header rows look like data records"
    ),
    "specialized_or_excluded_exposure_sheet": (
        "Specialised or excluded exposure sheet"
    ),
    "location_identity_and_property_attributes": (
        "Has location identity and property attribute columns"
    ),
    "partial_sov_structure": "Partial SOV structure",
    "insufficient_sov_structure": "Insufficient SOV structure",
}

_TOTAL_RE = re.compile(r"^\s*(grand\s+)?(sub\s*)?totals?\s*:?\s*$", re.IGNORECASE)


class SheetManifestEntry(BaseModel):
    sheet_name: str

    classification: str

    confidence: float = Field(ge=0.0, le=1.0)

    rank_score: float = Field(ge=0.0)

    header_row: Optional[int] = None

    data_rows: int = 0

    reasoning: list[str] = Field(default_factory=list)


class SheetDiscoveryResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    manifest: list[SheetManifestEntry]

    selected_sheet: Optional[str] = None

    selection_confidence: float = 0.0

    # 0-based worksheet row of the header.
    header_row: Optional[int] = None

    # Data table; index = 1-based Excel row number.
    table: Any = None

    # Rows below the header left out of the table, with the reason.
    excluded_rows: list[dict[str, Any]] = Field(default_factory=list)

    warnings: list[str] = Field(default_factory=list)


class SheetDiscoveryAgent:
    def discover(
        self,
        sheet_data: dict[str, pd.DataFrame],
    ) -> SheetDiscoveryResult:
        entries: list[tuple[SheetManifestEntry, dict]] = []

        for sheet_name, raw in sheet_data.items():
            classification = classify_sheet_role(sheet_name, raw)
            entries.append(
                (self._manifest_entry(sheet_name, raw, classification), classification)
            )

        entries.sort(
            key=lambda pair: (
                {"Primary": 0, "Secondary": 1, "Reject": 2}[
                    pair[0].classification
                ],
                -pair[0].rank_score,
            )
        )

        manifest = [entry for entry, _ in entries]
        warnings: list[str] = []

        candidates = [
            entry for entry in manifest if entry.classification != "Reject"
        ]

        if not candidates:
            return SheetDiscoveryResult(
                manifest=manifest,
                warnings=["No worksheet looks like SOV data."],
            )

        selected = candidates[0]

        if selected.classification != "Primary":
            warnings.append(
                f"No sheet was classified Primary; using the best "
                f"Secondary sheet '{selected.sheet_name}'."
            )

        primaries = [e for e in manifest if e.classification == "Primary"]

        if len(primaries) > 1:
            warnings.append(
                "Several sheets look like primary SOV data: "
                + ", ".join(f"'{e.sheet_name}'" for e in primaries)
                + f". Selected '{selected.sheet_name}' (highest rank score)."
            )

        table, excluded = extract_table(
            sheet_data[selected.sheet_name],
            selected.header_row,
        )

        selection_confidence = selected.confidence

        if len(candidates) > 1:
            margin = selected.rank_score - candidates[1].rank_score
            selection_confidence = round(
                min(selected.confidence, 0.5 + max(margin, 0.0)), 4
            )

        return SheetDiscoveryResult(
            manifest=manifest,
            selected_sheet=selected.sheet_name,
            selection_confidence=selection_confidence,
            header_row=selected.header_row,
            table=table,
            excluded_rows=excluded,
            warnings=warnings,
        )

    def run(self, state: Any) -> Any:
        """Read state.sheet_data, write the manifest and data table."""

        try:
            result = self.discover(state.sheet_data)
        except Exception as error:
            state.errors.append(f"Agent 1 failed: {error}")
            return state

        state.sheet_manifest = [entry.model_dump() for entry in result.manifest]
        state.warnings.extend(result.warnings)

        if result.selected_sheet is None:
            state.errors.append(
                "No worksheet containing SOV data was found."
            )
            return state

        state.selected_sheet = result.selected_sheet
        state.header_row = result.header_row
        state.data_table = result.table
        state.columns = [str(column) for column in result.table.columns]
        state.metadata["excluded_rows"] = result.excluded_rows
        state.metadata["sheet_selection_confidence"] = (
            result.selection_confidence
        )
        state.agent_trace.append(
            {
                "agent": "sheet_discovery",
                "status": "completed",
                "summary": {
                    "selected_sheet": result.selected_sheet,
                    "header_row": result.header_row,
                    "data_rows": int(len(result.table)),
                    "excluded_rows": len(result.excluded_rows),
                    "confidence": result.selection_confidence,
                },
            }
        )

        return state

    @staticmethod
    def _manifest_entry(
        sheet_name: str,
        raw: pd.DataFrame,
        classification: dict,
    ) -> SheetManifestEntry:
        role = _ROLE_LABELS[classification["role"]]
        header = classification["header"]
        profile = classification["profile"]
        features = classification.get("classification_features", {})

        header_score = float(header.get("header_score") or 0.0)
        density = float(profile.get("data_density") or 0.0)
        role_score = min(float(features.get("header_role_score", 0.0)), 1.0)

        rank_score = round(
            0.4 * header_score + 0.4 * density + 0.2 * role_score,
            4,
        )

        if role == "Reject":
            confidence = 0.9 if classification["reason"].startswith(
                "sheet_name"
            ) else 0.75
        else:
            confidence = min(0.99, 0.5 + rank_score / 2)

        reasoning = [_REASON_TEXT.get(classification["reason"], classification["reason"])]

        if header.get("header_row") is not None:
            reasoning.append(
                f"Header detected at row {header['header_row'] + 1} "
                f"({header.get('header_confidence')} confidence)"
            )

        if role != "Reject":
            reasoning.append(f"Data density {density:.0%}")

        header_row = header.get("header_row")

        data_rows = (
            int(raw.iloc[header_row + 1:].notna().any(axis=1).sum())
            if header_row is not None
            else 0
        )

        return SheetManifestEntry(
            sheet_name=sheet_name,
            classification=role,
            confidence=round(confidence, 4),
            rank_score=rank_score,
            header_row=header_row,
            data_rows=data_rows,
            reasoning=reasoning,
        )


def clean_header_names(values: list[Any]) -> list[str]:
    """Unique, whitespace-normalised names; blanks become Unnamed_<n>."""

    names: list[str] = []
    seen: dict[str, int] = {}

    for position, value in enumerate(values):
        if value is None or (isinstance(value, float) and math.isnan(value)):
            name = f"Unnamed_{position + 1}"
        else:
            name = " ".join(str(value).split()) or f"Unnamed_{position + 1}"

        if name in seen:
            seen[name] += 1
            name = f"{name} ({seen[name]})"
        else:
            seen[name] = 1

        names.append(name)

    return names


def extract_table(
    raw: pd.DataFrame,
    header_row: int,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """
    Build the data table below header_row.

    Returns the table (index = 1-based Excel row) and the excluded rows.
    """

    header_values = raw.iloc[header_row].tolist()
    body = raw.iloc[header_row + 1:].copy()
    body.columns = clean_header_names(header_values)
    body.index = [int(position) + 1 for position in body.index]

    # Drop columns that have neither a header nor any value.
    blank_header = [
        name
        for name, value in zip(body.columns, header_values)
        if value is None or (isinstance(value, float) and math.isnan(value))
    ]
    body = body.drop(
        columns=[name for name in blank_header if body[name].isna().all()]
    )

    column_count = body.shape[1]
    excluded: list[dict[str, Any]] = []
    keep: list[int] = []

    for excel_row, row in body.iterrows():
        values = [value for value in row.tolist() if pd.notna(value)]

        if not values:
            continue

        text_values = [str(value).strip() for value in values]

        if any(_TOTAL_RE.match(text) for text in text_values):
            excluded.append(
                {"excel_row": int(excel_row), "reason": "total_row",
                 "preview": " | ".join(text_values[:4])}
            )
            continue

        if len(values) == 1 and column_count > 3:
            excluded.append(
                {"excel_row": int(excel_row), "reason": "note_or_footer",
                 "preview": text_values[0][:80]}
            )
            continue

        keep.append(excel_row)

    return body.loc[keep], excluded
