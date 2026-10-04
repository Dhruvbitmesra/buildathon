"""Regression: Agent 3 recall on the real SOV samples (NFR-2)."""

import pytest

from tests.evaluate_agent3_real import DATA_DIR, RECALL_TARGET, SAMPLES, evaluate_sample


AVAILABLE = [name for name in SAMPLES if (DATA_DIR / name).exists()]


@pytest.mark.skipif(not AVAILABLE, reason="real SOV samples not present")
@pytest.mark.parametrize("name", AVAILABLE)
def test_planted_anomaly_recall(name):
    outcome = evaluate_sample(name)

    planted = sum(outcome.planted.values())
    detected = sum(outcome.detected.values())

    assert planted > 0
    assert detected / planted >= RECALL_TARGET, outcome.missed
    assert outcome.rationale_coverage == 1.0
    assert outcome.unchanged
