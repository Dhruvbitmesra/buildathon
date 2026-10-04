"""
Agent 2 header-mapping accuracy on the SOV samples (NFR-1, target 74%).

Headers come from Agent 1 (real sheet selection and header detection).
Ground truth below was labelled by reading each header together with its
values. A header may accept several targets where the business meaning
is genuinely ambiguous; None means "should stay unmapped".

Accuracy = headers whose predicted target is acceptable / all headers.
Precision and recall on the mapped subset are reported too.

Run:  python -m tests.evaluate_mapping_accuracy [--llm]
"""

import sys
import time
from pathlib import Path

from app.agents.schema_mapping.agent import SchemaMappingAgent
from app.agents.sheet_discovery.agent import SheetDiscoveryAgent
from app.ingestion.loader import load_sov_file
from app.state.sov_state import SOVState


TARGET_ACCURACY = 0.74
N = None

GROUND_TRUTH: dict[str, dict[str, set]] = {
    "data/input/SOV_B4ID.xlsx": {
        "Loc #": {"Reference"},
        "Bldg.": {N},
        "Street": {"Address"},
        "City": {"City"},
        "State": {"State"},
        "Zip": {"Zip"},
        "Outside City Limits": {N},
        "Owned/ Leased": {N},
        "Building": {"Building Value"},
        "2024 - Increase 10%": {N},
        "BPP": {"Contents"},
        "Improvements & Betterments": {N, "Other"},
        "Extra Expense": {N, "BI"},
        "Other": {"Other"},
        "2024 - Increase 10% (2)": {N},
        "EDP": {N, "Other"},
        "2024 - Increase 10% (3)": {N},
        "Valuation": {N},
        "Occupancy": {"Occupancy"},
        "Construction Type": {"Construction"},
        "Protection Class": {N},
        "# Of Buildings": {"Number of Buildings"},
        "# Of Stories": {"Storeys"},
        "Year Built": {"Year Built"},
        "Square Footage": {N},
        "% Sprinklered": {"Fire Sprinklers (Y/N)"},
        "Alarm": {N},
    },
    "data/input/SOV_H6D2.xlsx": {
        "Item #": {"Reference"},
        "Facility Name": {N},
        "Street Address": {"Address"},
        "City": {"City"},
        "County": {"County"},
        "State": {"State"},
        "Zip": {"Zip"},
        "Country": {"Country"},
        "Insured Occupancy": {"Occupancy"},
        "*Building Values": {"Building Value"},
        "Machinery & Equipment Values": {N, "Other"},
        "Business Personal Property": {"Contents"},
        "Computer/ Fixture/ Office Equipment": {N, "Other"},
        "Total": {N},
        "Primary Occupancy & %": {N},
        "Protection Class": {N},
        "Owned or Leased": {N},
        "Year Built": {"Year Built"},
        "No. of Bldgs": {"Number of Buildings"},
        "No. of Stories": {"Storeys"},
        "Basement Yes/No": {N},
        "Construction Type": {"Construction"},
        "Sprinkler %": {"Fire Sprinklers (Y/N)"},
        "Square Footage": {N},
        "Comments": {N},
    },
    "data/input/SOV_K4T9.xlsx": {
        "Account Name": {N},
        "Business Entity": {N},
        "Location ID": {"Reference"},
        "Location Name": {N},
        "Latitude": {N},
        "Longitude": {N},
        "Address": {"Address"},
        "Country Name": {"Country"},
        "Buildings": {"Building Value"},
        "Contents": {"Contents"},
        "PD": {N},
        "BI": {"BI"},
        "TIV": {N},
        "RMS Construction": {"Construction"},
        "RMS Occupancy": {"Occupancy"},
        "Year Built": {"Year Built"},
        "Survey Report": {N},
    },
    "data/input/SOV_Q8B3.xlsx": {
        "SW": {N, "Reference"},
        "Loc #": {N, "Reference"},
        "Bldg #": {N, "Reference"},
        "Complex/Facility": {N},
        "Building": {N},
        "Address": {"Address"},
        "Zip": {"Zip"},
        "County": {"County"},
        "Dept": {N},
        "Sq. Ft.": {N},
        "Yr. Built": {"Year Built"},
        "Reconstruction Date": {N},
        "#Floor": {"Storeys"},
        "2015 Flood Zone Determination": {N},
        "Year of Property Risk Assement": {N},
        "Year of Marshall Swift Valution": {N},
        "Owned / Leased": {N},
        "Construction": {"Construction"},
        "%Sprink": {"Fire Sprinklers (Y/N)"},
        "Wiring Updates": {N},
        "Roof Construction": {N},
        "Roof Updates": {N},
        "HVAC Updates": {N},
        "INSPECTION Completion / Property Risk Assements Change Date": {N},
        "Marshall Swift Valution Summary Change Date": {N},
        "2023 Building Value": {"Building Value"},
        "2023 Contents Value": {"Contents"},
        "BI Value": {"BI"},
        "2023 TOTAL": {N},
    },
    "data/sample/sample_sov.xlsx": {
        "Location ID": {"Reference"},
        "Bldg Repl Cost New": {"Building Value"},
        "Construction Yr": {"Year Built"},
        "No. Floors": {"Storeys"},
        "Sprk": {"Fire Sprinklers (Y/N)"},
        "Zip": {"Zip"},
    },
}


def evaluate(path: str, agent: SchemaMappingAgent) -> dict:
    state: SOVState = load_sov_file(path)
    state = SheetDiscoveryAgent().run(state)
    state = agent.run(state)

    if state.errors:
        raise RuntimeError(state.errors)

    truth = GROUND_TRUTH[path]
    predicted = {m["source_header"]: m["target_field"] for m in state.schema_mappings}

    correct = 0
    wrong: list[str] = []
    true_positive = predicted_positive = actual_positive = 0

    for header, target in predicted.items():
        acceptable = truth.get(header, {N})

        if target in acceptable:
            correct += 1
        else:
            wrong.append(f"{header!r}: got {target}, expected {sorted(acceptable, key=str)}")

        if target is not None:
            predicted_positive += 1
            true_positive += target in acceptable

        if acceptable != {N}:
            actual_positive += 1

    unknown = sorted(set(truth) - set(predicted))

    return {
        "headers": len(predicted),
        "correct": correct,
        "accuracy": correct / len(predicted) if predicted else 1.0,
        "precision": true_positive / predicted_positive if predicted_positive else 1.0,
        "recall": true_positive / actual_positive if actual_positive else 1.0,
        "wrong": wrong,
        "labels_not_seen": unknown,
    }


def main(argv: list[str]) -> int:
    client = None

    if "--llm" in argv:
        from app.agents.schema_mapping.groq_client import GroqLLMClient

        client = GroqLLMClient()

    agent = SchemaMappingAgent(llm_client=client)
    total = correct = 0

    for path in GROUND_TRUTH:
        if not Path(path).exists():
            continue

        started = time.perf_counter()
        result = evaluate(path, agent)
        total += result["headers"]
        correct += result["correct"]

        print(f"\n=== {path}  accuracy {result['accuracy']:.1%} "
              f"({result['correct']}/{result['headers']})  precision "
              f"{result['precision']:.1%}  recall {result['recall']:.1%}  "
              f"[{time.perf_counter() - started:.1f}s]")

        for line in result["wrong"]:
            print(f"   WRONG {line}")

        if result["labels_not_seen"]:
            print(f"   (labelled headers not produced: {result['labels_not_seen']})")

    accuracy = correct / total if total else 0.0
    print(f"\nOVERALL ACCURACY {correct}/{total} = {accuracy:.1%} "
          f"(target {TARGET_ACCURACY:.0%})")

    return 0 if accuracy >= TARGET_ACCURACY else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
