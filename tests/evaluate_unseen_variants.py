"""
Held-out evaluation on generated, unseen SOV variants.

The 4 real samples were used while developing the agents, so scores on
them are optimistic. This harness builds new workbooks from their data:

- headers renamed to phrasings from an independent synonym bank; any
  phrasing already in the alias vocabulary is excluded, so mapping is
  measured on genuinely unseen wording;
- the bank is split deterministically into a DEV half (may be inspected
  when fixing bugs) and a TEST half (report only - never tuned on);
- random layout: title rows above the header, blank rows, a Total row,
  distractor columns, extra non-SOV sheets;
- planted anomalies, including formats the validators were not
  originally written for (European numbers, bracket negatives, "TBD").

Run:  python -m tests.evaluate_unseen_variants [--variants 6] [--split test]
"""

import argparse
import hashlib
import random
import sys
import tempfile
from collections import Counter
from pathlib import Path

import pandas as pd

from app.agents.data_quality.agent import DataQualityAgent
from app.agents.data_quality.canonical_frame import build_canonical_frame
from app.agents.schema_mapping.agent import SchemaMappingAgent
from app.agents.schema_mapping.domain_aliases import DOMAIN_ALIAS_LOOKUP
from app.agents.schema_mapping.header_normalizer import normalize_header
from app.agents.schema_mapping.target_schema import TARGET_FIELDS
from app.agents.sheet_discovery.agent import SheetDiscoveryAgent
from app.ingestion.loader import load_sov_file
from tests.evaluate_mapping_accuracy import GROUND_TRUTH


# Written independently of the alias lists (see module docstring).
SYNONYM_BANK: dict[str, list[str]] = {
    "Reference": [
        "Location #", "Loc No", "Site ID", "Property ID", "Location Number",
        "Loc Ref", "Site Number", "Property Number", "Risk ID", "Location Code",
    ],
    "Address": [
        "Street Address", "Location Address", "Address 1", "Site Address",
        "Address Line", "Street", "Premises Address", "Property Street",
    ],
    "City": [
        "Town", "City/Town", "Municipality", "City Name", "Location City",
        "Site City",
    ],
    "State": [
        "State Code", "ST", "Province/State", "State/Province", "Location State",
        "State Abbr",
    ],
    "Zip": [
        "Zip Code", "Postal Code", "ZIP/Postal", "Postcode", "Zip5",
        "Postal", "Location Zip",
    ],
    "County": ["County Name", "Parish/County", "Location County", "Cnty"],
    "Country": ["Country Code", "Nation", "Location Country", "Ctry"],
    "Building Value": [
        "Bldg Replacement Value", "Structure Value", "Building RCV",
        "Bldg Limit", "Building Insured Value", "Building Sum Insured",
        "Bldg Value ($)", "Building Replacement Cost", "Real Property Value",
        "Bldg TIV",
    ],
    "Contents": [
        "Contents Limit", "Personal Property", "BPP Limit",
        "Contents Sum Insured", "Stock & Contents", "Contents ($)",
        "Business Personal Property Value", "Contents RCV",
    ],
    "BI": [
        "Business Income Limit", "Loss of Income", "BI/EE",
        "Business Interruption Limit", "BI ($)", "Business Income & Extra Expense",
        "Annual BI",
    ],
    "Occupancy": [
        "Occupancy Description", "Building Use", "Primary Use", "Occ Type",
        "Occupancy Class", "Use of Building", "Occupancy Desc",
    ],
    "Construction": [
        "Construction Class", "Const Type", "ISO Construction",
        "Construction Description", "Bldg Construction", "Const. Class",
        "Construction Code",
    ],
    "Storeys": [
        "Number of Stories", "Stories", "Floors", "No. of Floors",
        "# Floors", "Num Stories", "Story Count", "Floor Count",
    ],
    "Number of Buildings": [
        "Bldg Count", "Building Count", "Total Buildings", "Num Bldgs",
        "# of Bldgs", "No of Buildings",
    ],
    "Year Built": [
        "Yr Built", "Construction Year", "Year of Construction", "Built Year",
        "Original Year Built", "Yr Blt", "Year Constructed",
    ],
    "Fire Sprinklers (Y/N)": [
        "Sprinklered (Y/N)", "Sprinklers?", "Fire Sprinkler System",
        "Auto Sprinklers", "Sprinkler Protection", "Sprinklered",
        "Sprinkler Y/N",
    ],
    "Other": ["Other Values", "Misc Property", "Other Insured Values"],
}

DISTRACTORS = [
    "Policy Number", "Broker", "Notes", "Inspection Date", "Square Feet",
    "Roof Type", "Latitude", "Longitude", "Flood Zone", "Alarm Type",
    "Valuation Date", "Owner", "Tenant Name", "Distance to Coast",
]

TITLES = [
    ["Statement of Values"],
    ["Client: Example Holdings", None, "Prepared 2026"],
    ["All values in USD"],
    [],
]

ANOMALIES = {
    "missing_value": ["Address", "Building Value", "Year Built"],
    "negative_tiv": ["Building Value", "Contents"],
    "future_year": ["Year Built"],
    "storeys_below_one": ["Storeys"],
    "type_error": ["Building Value", "Contents", "Storeys"],
    "bracket_negative": ["Building Value", "Contents"],
    "european_number": ["Building Value", "Contents"],
}


def _known_vocabulary() -> set[str]:
    known = set(DOMAIN_ALIAS_LOOKUP)

    for field in TARGET_FIELDS:
        known.add(normalize_header(field.name))
        known.update(normalize_header(alias) for alias in field.aliases)

    return known


def _split(phrase: str) -> str:
    digest = hashlib.sha1(phrase.encode()).hexdigest()
    return "dev" if int(digest, 16) % 2 == 0 else "test"


def unseen_bank(split: str) -> dict[str, list[str]]:
    known = _known_vocabulary()

    return {
        target: [
            phrase
            for phrase in phrases
            if normalize_header(phrase) not in known
            and (split == "all" or _split(phrase) == split)
        ]
        for target, phrases in SYNONYM_BANK.items()
    }


def _source_tables() -> list[tuple[str, pd.DataFrame, dict[str, str]]]:
    """Real data rows with their ground-truth target for each column."""

    tables = []

    for path, truth in GROUND_TRUTH.items():
        if not Path(path).exists():
            continue

        state = SheetDiscoveryAgent().run(load_sov_file(path))
        table = state.data_table.reset_index(drop=True)
        targets = {}

        for header, acceptable in truth.items():
            real = [t for t in acceptable if t is not None]

            if len(real) == 1 and len(acceptable) == 1 and header in table.columns:
                targets[header] = real[0]

        tables.append((path, table, targets))

    return tables


def make_variant(table, targets, bank, rng):
    """Return (workbook rows, header row index, truth, planted, columns)."""

    columns = {}
    truth = {}

    for source, target in targets.items():
        options = bank.get(target) or []

        if not options:
            continue

        header = rng.choice(options)
        columns[header] = table[source].tolist()
        truth[header] = target

    for name in rng.sample(DISTRACTORS, k=rng.randint(2, 4)):
        if name not in columns:
            columns[name] = [rng.choice(["x", "y", "", None]) for _ in range(len(table))]
            truth[name] = None

    headers = list(columns)
    rng.shuffle(headers)
    frame = pd.DataFrame({h: columns[h] for h in headers}, dtype=object)

    planted = {}

    for anomaly, fields in ANOMALIES.items():
        candidates = [
            (row, header)
            for header, target in truth.items()
            if target in fields
            for row in range(len(frame))
            if pd.notna(frame.at[row, header]) and (row, header) not in planted
        ]
        rng.shuffle(candidates)

        for row, header in candidates[:2]:
            original = frame.at[row, header]

            try:
                number = abs(float(str(original).replace(",", "")))
            except ValueError:
                number = 123456.0

            frame.at[row, header] = {
                "missing_value": None,
                "negative_tiv": -max(number, 1000.0),
                "future_year": 2050,
                "storeys_below_one": 0,
                "type_error": rng.choice(["TBD", "n/a", "see notes"]),
                "bracket_negative": f"({number:,.0f})",
                "european_number": f"EUR {number:,.2f}".replace(",", "_").replace(".", ",").replace("_", "."),
            }[anomaly]
            planted[(row, header)] = anomaly

    titles = rng.sample(TITLES, k=rng.randint(0, 3))
    rows = [list(t) for t in titles] + [headers] + frame.values.tolist()
    header_row = len(titles)

    # Blank row and a Total row at the end.
    rows.append([None] * len(headers))
    total = [None] * len(headers)
    total[0] = "Total"
    rows.append(total)

    return rows, header_row, truth, planted


def write_workbook(path: Path, rows, rng) -> str:
    sheet_name = rng.choice(["SOV", "Locations", "Schedule", "Property Schedule", "Sheet1"])

    with pd.ExcelWriter(path) as writer:
        if rng.random() < 0.6:
            pd.DataFrame([["Summary of values"], ["Total TIV", 1]]).to_excel(
                writer, sheet_name="Summary", header=False, index=False
            )

        pd.DataFrame(rows).to_excel(writer, sheet_name=sheet_name, header=False, index=False)

        if rng.random() < 0.6:
            pd.DataFrame([["Notes"], ["Values supplied by client"]]).to_excel(
                writer, sheet_name="Notes", header=False, index=False
            )

    return sheet_name


def evaluate(variants: int, split: str, seed: int = 11) -> dict:
    bank = unseen_bank(split)
    rng = random.Random(seed)
    agent2 = SchemaMappingAgent()
    agent3 = DataQualityAgent()

    totals = Counter()
    mapping_errors: Counter = Counter()
    missed_anomalies: Counter = Counter()

    with tempfile.TemporaryDirectory() as tmp:
        for source_path, table, targets in _source_tables():
            for index in range(variants):
                rows, header_row, truth, planted = make_variant(table, targets, bank, rng)
                path = Path(tmp) / f"{Path(source_path).stem}_v{index}.xlsx"
                sheet_name = write_workbook(path, rows, rng)

                state = SheetDiscoveryAgent().run(load_sov_file(str(path)))
                totals["files"] += 1

                if state.errors or state.selected_sheet != sheet_name:
                    totals["sheet_wrong"] += 1
                    continue

                if state.header_row != header_row:
                    totals["header_wrong"] += 1
                    continue

                state = agent2.run(state)
                predicted = {m["source_header"]: m["target_field"] for m in state.schema_mappings}

                for header, target in truth.items():
                    got = predicted.get(header)
                    totals["headers"] += 1
                    totals["mapped_ok"] += got == target

                    if target is not None:
                        totals["real_fields"] += 1
                        totals["real_ok"] += got == target

                    if got != target:
                        mapping_errors[f"{header!r} -> {got} (want {target})"] += 1

                # Anomaly recall, isolated from mapping errors: validate
                # with the true mapping.
                true_mappings = [
                    {"source_header": h, "target_field": t}
                    for h, t in truth.items() if t is not None
                ]
                canonical = build_canonical_frame(
                    state.data_table.reset_index(drop=True), true_mappings
                )
                result = agent3.analyse(canonical.dataframe, current_year=2026)
                flagged = {
                    (i.row_index, i.source_field)
                    for i in result.quality_report.issues
                    if i.row_index is not None
                }

                for (row, header), anomaly in planted.items():
                    totals["planted"] += 1

                    if (row, truth[header]) in flagged:
                        totals["detected"] += 1
                    else:
                        missed_anomalies[anomaly] += 1

    return {
        "split": split,
        "unseen_phrasings": sum(len(v) for v in bank.values()),
        "totals": totals,
        "mapping_errors": mapping_errors,
        "missed_anomalies": missed_anomalies,
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variants", type=int, default=6)
    parser.add_argument("--split", choices=["dev", "test", "all"], default="test")
    args = parser.parse_args(argv)

    result = evaluate(args.variants, args.split)
    t = result["totals"]

    print(f"split={result['split']}  unseen phrasings in bank: {result['unseen_phrasings']}")
    print(f"files: {t['files']}  wrong sheet: {t['sheet_wrong']}  wrong header row: {t['header_wrong']}")

    if t["headers"]:
        print(f"mapping accuracy (all headers incl. distractors): "
              f"{t['mapped_ok']}/{t['headers']} = {t['mapped_ok'] / t['headers']:.1%}")
        print(f"mapping accuracy (real SOV fields only):          "
              f"{t['real_ok']}/{t['real_fields']} = {t['real_ok'] / t['real_fields']:.1%}")

    if t["planted"]:
        print(f"anomaly recall: {t['detected']}/{t['planted']} = {t['detected'] / t['planted']:.1%}")

    if result["mapping_errors"]:
        print("\nmost common mapping errors:")
        for error, count in result["mapping_errors"].most_common(25):
            print(f"  {count:3}x {error}")

    if result["missed_anomalies"]:
        print("\nmissed anomalies:", dict(result["missed_anomalies"]))

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
