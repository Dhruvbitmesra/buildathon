"""UI helpers and a headless run of the Streamlit review interface."""

from pathlib import Path

import pytest

from app.ui.helpers import coerce_edit_value, workflow_dot


SAMPLE = Path("data/sample/sample_sov.xlsx")
APP = Path(__file__).resolve().parents[1] / "app" / "ui" / "streamlit_app.py"


@pytest.mark.parametrize(
    "field, text, expected",
    [
        ("Building Value", "$1.2M", 1200000.0),
        ("Building Value", "  ", None),
        ("Storeys", "3", 3),
        ("Year Built", "1985", 1985),
        ("Fire Sprinklers (Y/N)", " y13 ", "Y13"),
        ("State", "Texas", "TX"),
        ("City", " Boston ", "Boston"),
    ],
)
def test_coerce_edit_value(field, text, expected):
    assert coerce_edit_value(field, text) == expected


def test_coerce_edit_value_rejects_bad_numbers():
    with pytest.raises(ValueError):
        coerce_edit_value("Storeys", "two")


@pytest.mark.skipif(not SAMPLE.exists(), reason="sample not present")
def test_streamlit_review_flow(tmp_path):
    streamlit_testing = pytest.importorskip("streamlit.testing.v1")
    from app.pipeline import PipelineRun

    run = PipelineRun(str(SAMPLE), output_dir=tmp_path, use_llm=False)
    assert run.analyse()

    dot = workflow_dot(run)
    assert "Agent 1" in dot and "re-reason" in dot

    app = streamlit_testing.AppTest.from_file(str(APP), default_timeout=120)
    app.session_state["run"] = run
    app.session_state["reviewer"] = "tester"
    app.run()

    assert not app.exception
    assert any("Review" in tab.label for tab in app.tabs)

    export = next(b for b in app.button if b.label == "Export Cleaned_SOV.xlsx")
    assert export.disabled  # FR-5: blocked while items are pending

    next(b for b in app.button if b.label.startswith("Approve All")).click().run()
    assert not app.exception

    from app.agents.data_quality.recommendation_schema import ReviewAction

    for rec in list(run.session.ledger.pending()):
        run.submit(ReviewAction(recommendation_id=rec.recommendation_id, decision="approve", reviewer="tester"))

    app.run()
    next(b for b in app.button if b.label == "Export Cleaned_SOV.xlsx").click().run()

    assert not app.exception
    assert run.export_result is not None and run.export_result.schema_valid
    assert {b.label for b in app.get("download_button")} == {
        "Download Cleaned_SOV.xlsx",
        "Download Audit_Log.xlsx",
        "Download Audit_Log.json",
        "Download processing summary",
    }
