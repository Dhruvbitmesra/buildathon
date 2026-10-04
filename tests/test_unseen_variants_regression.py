"""
Regression on generated, unseen SOV variants (held-out TEST split).

Thresholds are the problem-statement targets, not the current scores:
mapping accuracy >= 74% (NFR-1), anomaly recall >= 90% (NFR-2), and
sheet/header detection on every file.
"""

import pytest

from tests.evaluate_unseen_variants import _source_tables, evaluate


@pytest.mark.skipif(not _source_tables(), reason="SOV samples not present")
def test_unseen_variants_meet_targets():
    result = evaluate(variants=2, split="test")
    totals = result["totals"]

    assert totals["sheet_wrong"] == 0
    assert totals["header_wrong"] == 0
    assert totals["real_ok"] / totals["real_fields"] >= 0.74
    assert totals["detected"] / totals["planted"] >= 0.90
