"""
Agent 3 evaluation harness on the real SOV samples (NFR-2, NFR-6).

For each sample workbook:
1. Build the canonical frame with a fixed reference mapping (so the
   measurement isolates Agent 3 from Agent 2's mapping accuracy).
2. Plant known anomalies into cells that currently have no issue.
3. Run Agent 3 and measure recall: planted cells that received an issue.
4. Check every recommendation has a rationale and that the DataFrame
   was not modified.

Run:  python -m tests.evaluate_agent3_real
"""

import random
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from app.agents.data_quality.agent import DataQualityAgent, dataframe_fingerprint
from app.agents.data_quality.canonical_frame import build_canonical_frame


DATA_DIR = Path("data/input")
CURRENT_YEAR = 2026
RECALL_TARGET = 0.90


# Reference mappings: source header -> target field.
SAMPLES = {
    "SOV_B4ID.xlsx": (
        "SOV",
        11,
        {
            "Loc # ": "Reference",
            "Street": "Address",
            "City": "City",
            "State": "State",
            "Zip": "Zip",
            "Building": "Building Value",
            "BPP": "Contents",
            "Extra Expense": "BI",
            "Other": "Other",
            "Occupancy": "Occupancy",
            "Construction Type": "Construction",
            "# Of Buildings": "Number of Buildings",
            "# Of Stories": "Storeys",
            "Year Built": "Year Built",
            "% Sprinklered": "Fire Sprinklers (Y/N)",
        },
    ),
    "SOV_H6D2.xlsx": (
        "SOV",
        6,
        {
            "Item\n#": "Reference",
            "Street\n Address": "Address",
            "City": "City",
            "County": "County",
            "State": "State",
            "Zip": "Zip",
            "Country": "Country",
            "Insured \nOccupancy": "Occupancy",
            "\n*Building Values": "Building Value",
            "Business Personal Property": "Contents",
            "Year Built": "Year Built",
            "No. of Bldgs": "Number of Buildings",
            "No. of Stories": "Storeys",
            "Construction Type": "Construction",
            "Sprinkler %": "Fire Sprinklers (Y/N)",
        },
    ),
    "SOV_K4T9.xlsx": (
        "Locations",
        5,
        {
            "Location ID": "Reference",
            "Address": "Address",
            "Country Name": "Country",
            "Buildings": "Building Value",
            "Contents": "Contents",
            "BI": "BI",
            "RMS Construction": "Construction",
            "RMS Occupancy": "Occupancy",
            "Year Built": "Year Built",
        },
    ),
    "SOV_Q8B3.xlsx": (
        "23-24 Values",
        0,
        {
            "Bldg #": "Reference",
            "Address": "Address",
            "Zip": "Zip",
            "County": "County",
            "Yr. Built": "Year Built",
            "#Floor": "Storeys",
            "Construction": "Construction",
            "%Sprink": "Fire Sprinklers (Y/N)",
            "2023 Building Value": "Building Value",
            "2023 Contents Value": "Contents",
            "BI Value": "BI",
        },
    ),
}


# anomaly name -> (fields it can be planted in, planted value factory)
ANOMALIES = {
    "missing_value": (
        ["Address", "Building Value", "Year Built", "Reference"],
        lambda value, rng: None,
    ),
    "negative_tiv": (
        ["Building Value", "Contents", "BI"],
        lambda value, rng: -abs(float(value or 0)) - rng.randint(1, 9) * 1000,
    ),
    "future_year": (
        ["Year Built"],
        lambda value, rng: CURRENT_YEAR + rng.randint(1, 30),
    ),
    "storeys_below_one": (
        ["Storeys"],
        lambda value, rng: 0,
    ),
    "invalid_sprinkler": (
        ["Fire Sprinklers (Y/N)"],
        lambda value, rng: rng.choice(["MAYBE", "UNKNOWN", "Partial"]),
    ),
    "type_error": (
        ["Building Value", "Contents", "Storeys"],
        lambda value, rng: rng.choice(["TBD", "n/a", "see note"]),
    ),
    "currency_format": (
        ["Building Value", "Contents"],
        lambda value, rng: f"${rng.randint(100, 9999):,},000",
    ),
    "invalid_state": (
        ["State"],
        lambda value, rng: rng.choice(["XX", "Atlantis", "ZZ"]),
    ),
    "malformed_zip": (
        ["Zip"],
        lambda value, rng: rng.choice(["ABCDE", "123456", "1234-5"]),
    ),
}

PLANTS_PER_ANOMALY = 3


@dataclass
class SampleResult:
    name: str
    rows: int
    planted: dict[str, int] = field(default_factory=dict)
    detected: dict[str, int] = field(default_factory=dict)
    missed: list[str] = field(default_factory=list)
    recommendations: int = 0
    rationale_coverage: float = 0.0
    intake_score: float | None = None
    unchanged: bool = True
    seconds: float = 0.0


def load_canonical(name: str) -> tuple[pd.DataFrame, dict, dict, list]:
    sheet, header_row, mapping = SAMPLES[name]
    source = pd.read_excel(DATA_DIR / name, sheet_name=sheet, header=header_row)

    mappings = [
        {
            "source_header": source_header,
            "target_field": target,
            "score": 1.0,
            "method": "reference",
        }
        for source_header, target in mapping.items()
    ]

    canonical = build_canonical_frame(source, mappings, header_row=header_row)
    frame = canonical.dataframe

    # Drop rows with no mapped data at all (blank separator rows).
    keep = frame.notna().any(axis=1)
    frame = frame[keep].reset_index(drop=True)
    source_rows = {
        new: canonical.source_rows[old]
        for new, old in enumerate(keep[keep].index)
    }

    return frame, source_rows, canonical.source_columns, mappings


def issue_cells(result) -> set[tuple[int, str]]:
    return {
        (issue.row_index, issue.source_field)
        for issue in result.quality_report.issues
        if issue.row_index is not None
    }


def plant(
    frame: pd.DataFrame,
    clean_cells: set[tuple[int, str]],
    rng: random.Random,
) -> tuple[pd.DataFrame, dict[tuple[int, str], str]]:
    planted_frame = frame.copy(deep=True)
    planted: dict[tuple[int, str], str] = {}

    for anomaly, (fields, factory) in ANOMALIES.items():
        candidates = [
            (row, field_name)
            for field_name in fields
            if field_name in frame.columns
            for row in frame.index
            if (row, field_name) in clean_cells
            and pd.notna(frame.at[row, field_name])
            and all((row, f) not in planted for f in frame.columns)
        ]

        if anomaly == "invalid_state" and "Country" in frame.columns:
            from app.agents.data_quality.normalizers import is_us_country

            candidates = [
                (row, f)
                for row, f in candidates
                if is_us_country(frame.at[row, "Country"])
            ]

        rng.shuffle(candidates)

        for row, field_name in candidates[:PLANTS_PER_ANOMALY]:
            planted_frame.at[row, field_name] = factory(
                frame.at[row, field_name], rng
            )
            planted[(row, field_name)] = anomaly

    # Duplicate reference: copy one clean reference onto another row.
    if "Reference" in frame.columns:
        refs = [
            row
            for row in frame.index
            if (row, "Reference") in clean_cells
            and pd.notna(frame.at[row, "Reference"])
            and (row, "Reference") not in planted
        ]
        rng.shuffle(refs)

        if len(refs) >= 2:
            source_row, target_row = refs[0], refs[1]
            planted_frame.at[target_row, "Reference"] = frame.at[
                source_row, "Reference"
            ]
            planted[(target_row, "Reference")] = "duplicate_reference"

    return planted_frame, planted


def evaluate_sample(name: str, seed: int = 7) -> SampleResult:
    frame, source_rows, source_columns, mappings = load_canonical(name)
    agent = DataQualityAgent()

    baseline = agent.analyse(frame, current_year=CURRENT_YEAR)
    flagged = issue_cells(baseline)
    clean = {
        (row, field_name)
        for row in frame.index
        for field_name in frame.columns
        if (row, field_name) not in flagged
    }

    planted_frame, planted = plant(frame, clean, random.Random(seed))
    before = dataframe_fingerprint(planted_frame)

    started = time.perf_counter()
    result = agent.analyse(
        planted_frame,
        mappings=mappings,
        source_rows=source_rows,
        source_columns=source_columns,
        current_year=CURRENT_YEAR,
    )
    seconds = time.perf_counter() - started

    detected_cells = issue_cells(result)

    outcome = SampleResult(name=name, rows=len(frame), seconds=seconds)

    for cell, anomaly in planted.items():
        outcome.planted[anomaly] = outcome.planted.get(anomaly, 0) + 1

        if cell in detected_cells:
            outcome.detected[anomaly] = outcome.detected.get(anomaly, 0) + 1
        else:
            outcome.missed.append(
                f"{anomaly} at row {cell[0]} {cell[1]}="
                f"{planted_frame.at[cell[0], cell[1]]!r}"
            )

    recommendations = result.recommendations
    outcome.recommendations = len(recommendations)
    outcome.rationale_coverage = (
        sum(1 for rec in recommendations if rec.rationale.strip())
        / len(recommendations)
        if recommendations
        else 1.0
    )
    outcome.intake_score = result.quality_report.intake_quality_score
    outcome.unchanged = dataframe_fingerprint(planted_frame) == before

    return outcome


def main() -> int:
    results = [
        evaluate_sample(name)
        for name in SAMPLES
        if (DATA_DIR / name).exists()
    ]

    if not results:
        print("No sample files found in data/input.")
        return 1

    total_planted = total_detected = 0

    for outcome in results:
        planted = sum(outcome.planted.values())
        detected = sum(outcome.detected.values())
        total_planted += planted
        total_detected += detected

        print(f"\n=== {outcome.name}  ({outcome.rows} rows, "
              f"{outcome.seconds:.2f}s)")
        print(f"recall: {detected}/{planted} = "
              f"{detected / planted if planted else 1:.1%}")

        for anomaly in sorted(outcome.planted):
            print(f"  {anomaly:22} {outcome.detected.get(anomaly, 0)}/"
                  f"{outcome.planted[anomaly]}")

        for miss in outcome.missed:
            print(f"  MISSED {miss}")

        print(f"recommendations: {outcome.recommendations}  "
              f"rationale coverage: {outcome.rationale_coverage:.0%}  "
              f"intake score: {outcome.intake_score}  "
              f"dataframe unchanged: {outcome.unchanged}")

    recall = total_detected / total_planted if total_planted else 1.0
    print(f"\nOVERALL RECALL: {total_detected}/{total_planted} = {recall:.1%} "
          f"(target {RECALL_TARGET:.0%})")

    ok = (
        recall >= RECALL_TARGET
        and all(o.rationale_coverage == 1.0 for o in results)
        and all(o.unchanged for o in results)
    )

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
