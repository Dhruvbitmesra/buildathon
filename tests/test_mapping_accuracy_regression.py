"""Regression: Agent 2 header-mapping accuracy on the samples (NFR-1)."""

from pathlib import Path

import pytest

from app.agents.schema_mapping.agent import SchemaMappingAgent
from tests.evaluate_mapping_accuracy import GROUND_TRUTH, TARGET_ACCURACY, evaluate


AVAILABLE = [path for path in GROUND_TRUTH if Path(path).exists()]


@pytest.mark.skipif(not AVAILABLE, reason="SOV samples not present")
def test_mapping_accuracy_meets_target():
    agent = SchemaMappingAgent()
    correct = total = 0

    for path in AVAILABLE:
        result = evaluate(path, agent)
        correct += result["correct"]
        total += result["headers"]

    assert correct / total >= max(TARGET_ACCURACY, 0.95)


@pytest.mark.skipif(not AVAILABLE, reason="SOV samples not present")
@pytest.mark.parametrize(
    "path, header, target",
    [
        ("data/input/SOV_B4ID.xlsx", "Building", "Building Value"),
        ("data/input/SOV_B4ID.xlsx", "Loc #", "Reference"),
        ("data/input/SOV_K4T9.xlsx", "Buildings", "Building Value"),
        ("data/input/SOV_K4T9.xlsx", "Year Built", "Year Built"),
        ("data/input/SOV_K4T9.xlsx", "Account Name", None),
        ("data/input/SOV_H6D2.xlsx", "Insured Occupancy", "Occupancy"),
        ("data/input/SOV_H6D2.xlsx", "Primary Occupancy & %", None),
        ("data/input/SOV_Q8B3.xlsx", "Building", None),
    ],
)
def test_known_hard_headers(path, header, target):
    if not Path(path).exists():
        pytest.skip("sample not present")

    from app.agents.sheet_discovery.agent import SheetDiscoveryAgent
    from app.ingestion.loader import load_sov_file

    state = SchemaMappingAgent().run(
        SheetDiscoveryAgent().run(load_sov_file(path))
    )
    mapped = {m["source_header"]: m["target_field"] for m in state.schema_mappings}

    assert mapped[header] == target
