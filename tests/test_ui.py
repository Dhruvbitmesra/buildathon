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


def _app(run, tab="Review", reviewer="tester"):
    streamlit_testing = pytest.importorskip("streamlit.testing.v1")

    app = streamlit_testing.AppTest.from_file(str(APP), default_timeout=120)
    app.session_state["run"] = run
    app.session_state["active_tab"] = tab

    if reviewer:
        app.session_state["reviewer"] = reviewer

    return app


def _analysed(tmp_path):
    from app.pipeline import PipelineRun

    run = PipelineRun(str(SAMPLE), output_dir=tmp_path, use_llm=False, use_memory=False)
    assert run.analyse()
    return run


@pytest.mark.skipif(not SAMPLE.exists(), reason="sample not present")
def test_review_actions_keep_the_review_tab(tmp_path):
    run = _analysed(tmp_path)
    app = _app(run)
    app.run()

    approve = next(b for b in app.button if (b.key or "").startswith("approve-"))
    pending = len(run.session.ledger.pending())
    approve.click().run()

    assert not app.exception
    assert app.session_state["active_tab"] == "Review"
    assert len(run.session.ledger.pending()) == pending - 1
    assert app.toast[0].value.startswith("Approved:")

    next(b for b in app.button if b.label.startswith("Approve All")).click().run()

    assert not app.exception
    assert app.session_state["active_tab"] == "Review"


@pytest.mark.skipif(not SAMPLE.exists(), reason="sample not present")
def test_decisions_need_a_reviewer_name(tmp_path):
    app = _app(_analysed(tmp_path), reviewer=None)
    app.run()

    approve = next(b for b in app.button if (b.key or "").startswith("approve-"))

    assert approve.disabled
    assert any("your name" in w.value for w in app.warning)


@pytest.mark.skipif(not SAMPLE.exists(), reason="sample not present")
def test_every_tab_renders(tmp_path):
    run = _analysed(tmp_path)

    assert "Agent 1" in workflow_dot(run) and "re-reason" in workflow_dot(run)

    for tab in ["Overview", "Sheets", "Mapping", "Data quality", "Review", "Export"]:
        app = _app(run, tab=tab)
        app.run()
        assert not app.exception, tab


@pytest.mark.skipif(not SAMPLE.exists(), reason="sample not present")
def test_export_from_the_ui(tmp_path):
    from app.agents.data_quality.recommendation_schema import ReviewAction

    run = _analysed(tmp_path)
    app = _app(run, tab="Export")
    app.run()

    export = next(b for b in app.button if b.label == "Export Cleaned_SOV.xlsx")
    assert export.disabled  # FR-5: blocked while items are pending

    for rec in list(run.session.ledger.pending()):
        run.submit(ReviewAction(recommendation_id=rec.recommendation_id, decision="approve", reviewer="tester"))

    app.run()
    next(b for b in app.button if b.label == "Export Cleaned_SOV.xlsx").click().run()

    assert not app.exception
    assert app.session_state["active_tab"] == "Export"
    assert run.export_result is not None and run.export_result.schema_valid
    assert {b.label for b in app.get("download_button")} == {
        "Download Cleaned_SOV.xlsx",
        "Download Audit_Log.xlsx",
        "Download Audit_Log.json",
        "Download processing summary",
    }
