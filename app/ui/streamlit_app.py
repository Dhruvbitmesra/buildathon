"""
SOVereign AI - human approval interface (FR-1, FR-5).

    streamlit run app/ui/streamlit_app.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from app.agents.data_quality.config import SOV_REQUIRED_FIELDS  # noqa: E402
from app.agents.data_quality.issue_schema import IssueStatus  # noqa: E402
from app.agents.data_quality.recommendation_schema import (  # noqa: E402
    ActionType,
    ReviewAction,
    ReviewDecision,
    ReviewPolicy,
)
from app.agents.data_quality.reflection import ReviewError  # noqa: E402
from app.pipeline import PipelineRun, llm_available  # noqa: E402
from app.ui.helpers import (  # noqa: E402
    coerce_edit_value,
    display_frame,
    workflow_dot,
)


st.set_page_config(page_title="SOVereign AI", layout="wide")

SEVERITY_BADGE = {
    "critical": "🟥 CRITICAL",
    "high": "🟧 HIGH",
    "medium": "🟨 MEDIUM",
    "low": "⬜ LOW",
}
STATUS_LABEL = {
    "recommended": "Pending",
    "approved": "Approved",
    "escalated": "Escalated",
    "resolved": "Resolved",
    "rejected": "Rejected",
}


# ---------------------------------------------------------------------
# Sidebar: upload and run
# ---------------------------------------------------------------------


def sidebar() -> None:
    st.sidebar.title("SOVereign AI")
    st.sidebar.caption("Agentic SOV cleansing with human approval")

    uploaded = st.sidebar.file_uploader(
        "SOV file", type=["xlsx", "xls", "csv"]
    )

    st.session_state.reviewer = st.sidebar.text_input(
        "Reviewer name", value=st.session_state.get("reviewer", "")
    )

    has_key = llm_available()
    use_llm = st.sidebar.toggle(
        "Use LLM reasoning (Groq)",
        value=has_key,
        disabled=not has_key,
        help=(
            "Headers and up to 20 sample values per ambiguous column are "
            "sent to the LLM; names and addresses are masked in Agent 3."
            if has_key
            else "Set GROQ_API_KEY in .env to enable."
        ),
    )
    explain = st.sidebar.toggle(
        "LLM business-impact notes",
        value=False,
        disabled=not use_llm,
    )
    use_memory = st.sidebar.toggle(
        "Learn from reviewed mappings",
        value=True,
        help=(
            "Approved and corrected column mappings are remembered "
            "(headers only, never row values) and used as evidence for "
            "future files."
        ),
    )

    if st.sidebar.button(
        "Analyse file", type="primary", disabled=uploaded is None, width="stretch"
    ):
        upload_dir = ROOT / "output" / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        path = upload_dir / uploaded.name
        path.write_bytes(uploaded.getvalue())

        source = Path(uploaded.name)
        run = PipelineRun(
            str(path),
            output_dir=ROOT / "output" / f"{source.stem}_{source.suffix.lstrip('.')}",
            use_llm=use_llm,
            use_memory=use_memory,
        )
        run.quality_agent.explain_with_llm = explain

        with st.spinner(
            "Running Agents 1-3 (the first run loads the language models)..."
        ):
            run.analyse()

        st.session_state.run = run
        st.session_state.flash = None
        st.rerun()

    run = st.session_state.get("run")

    if run is not None and run.state is not None:
        st.sidebar.divider()
        st.sidebar.write(f"**File:** {Path(run.file_path).name}")
        st.sidebar.write(
            f"**LLM:** {'on' if run.use_llm else 'off (deterministic)'}"
        )
        if run.memory is not None:
            st.sidebar.write(
                f"**Mapping memory:** {len(run.memory.entries)} reviewed header(s)"
            )

        for stage, seconds in run.timings.items():
            st.sidebar.caption(f"{stage}: {seconds:.1f}s")


# ---------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------


def tab_workflow(run: PipelineRun) -> None:
    st.subheader("Agent workflow")
    st.graphviz_chart(workflow_dot(run), width="stretch")
    st.caption(
        "Green: done · Amber: waiting for you · Grey: not started · Red: failed. "
        "The dashed edge is the re-reasoning loop after a rejection."
    )

    with st.expander("Shared state hand-offs (agent trace)"):
        st.json(run.state.agent_trace)


def tab_sheets(run: PipelineRun) -> None:
    state = run.state
    st.subheader("Sheet discovery (Agent 1)")
    st.write(
        f"Selected **{state.selected_sheet}**, header detected on row "
        f"**{state.header_row + 1}**, {len(state.data_table)} data rows "
        f"(confidence {state.metadata.get('sheet_selection_confidence', 0):.2f})."
    )

    manifest = pd.DataFrame(state.sheet_manifest)

    if not manifest.empty:
        manifest["header_row"] = manifest["header_row"].map(
            lambda r: "" if pd.isna(r) else int(r) + 1
        )
        manifest["reasoning"] = manifest["reasoning"].map("; ".join)
        st.dataframe(
            manifest[
                ["sheet_name", "classification", "confidence", "rank_score",
                 "header_row", "data_rows", "reasoning"]
            ],
            hide_index=True,
            width="stretch",
        )

    excluded = state.metadata.get("excluded_rows", [])

    if excluded:
        st.write("**Rows left out of the data table** (not locations):")
        st.dataframe(pd.DataFrame(excluded), hide_index=True, width="stretch")

    for warning in state.warnings:
        st.warning(warning)


def tab_mapping(run: PipelineRun) -> None:
    state = run.state
    st.subheader("Schema mapping (Agent 2)")
    mapping_json = state.metadata.get("schema_mapping_json", {})

    rows = [
        {
            "Source column": source,
            "Target field": entry["target"] or "— unmapped —",
            "Confidence": entry["confidence"],
            "Method": entry["method"],
            "Flag": entry.get("flag", ""),
        }
        for source, entry in mapping_json.get("mappings", {}).items()
    ]

    col1, col2, col3 = st.columns(3)
    col1.metric("Mapped", sum(1 for r in rows if r["Target field"] != "— unmapped —"))
    col2.metric("Unresolved", mapping_json.get("unresolved_count", 0))
    col3.metric("Overall confidence", mapping_json.get("overall_confidence", 0))

    st.dataframe(
        pd.DataFrame(rows),
        hide_index=True,
        width="stretch",
        column_config={
            "Confidence": st.column_config.ProgressColumn(
                "Confidence", min_value=0.0, max_value=1.0, format="%.2f"
            )
        },
    )

    missing = [
        field for field in SOV_REQUIRED_FIELDS
        if field not in {r["Target field"] for r in rows}
    ]

    if missing:
        st.info("Target fields with no source column: " + ", ".join(missing))

    with st.expander("Mapping JSON"):
        st.json(mapping_json)


def tab_quality(run: PipelineRun) -> None:
    report = run.state.quality_report
    st.subheader("Data quality report (Agent 3)")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Intake quality score", f"{report.intake_quality_score:.1f} / 100")
    col2.metric("Issues", report.total_issues)
    col3.metric("High / critical", report.high_issue_count + report.critical_issue_count)
    col4.metric("Rows with issues", len(report.row_flags))

    left, right = st.columns(2)

    with left:
        st.write("**Issues by type**")
        st.bar_chart(pd.Series(report.issues_by_type, name="issues"), horizontal=True)

    with right:
        st.write("**Issues by severity**")
        order = ["critical", "high", "medium", "low"]
        st.bar_chart(
            pd.Series(
                {k: report.issues_by_severity.get(k, 0) for k in order},
                name="issues",
            ),
            horizontal=True,
        )

    st.write("**Per-field completeness and validity**")
    fields = pd.DataFrame(
        [
            {
                "Field": q.field,
                "Mapped": "yes" if q.present else "no",
                "Completeness": q.completeness_rate,
                "Validity": q.validity_rate,
                "Cells with issues": q.issue_cell_count,
            }
            for q in report.field_quality.values()
        ]
    )
    st.dataframe(
        fields,
        hide_index=True,
        width="stretch",
        column_config={
            "Completeness": st.column_config.ProgressColumn(
                "Completeness", min_value=0.0, max_value=1.0, format="%.2f"
            ),
            "Validity": st.column_config.ProgressColumn(
                "Validity", min_value=0.0, max_value=1.0, format="%.2f"
            ),
        },
    )

    with st.expander("Per-row anomaly flags"):
        source_rows = run.state.metadata.get("agent3_source_rows", {})
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Excel row": source_rows.get(row, ""),
                        "Fields with issues": ", ".join(map(str, fields_)),
                    }
                    for row, fields_ in report.row_flags.items()
                ]
            ),
            hide_index=True,
            width="stretch",
        )


def tab_review(run: PipelineRun) -> None:
    ledger = run.session.ledger
    summary = ledger.summary()
    st.subheader("Recommendation queue — nothing is applied without your approval")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Pending", summary["pending"])
    col2.metric("Approve-All eligible", summary["bulk_approvable_pending"])
    col3.metric("Escalated", summary["escalated"])
    col4.metric("Total", summary["total"])

    reviewer = st.session_state.get("reviewer", "").strip()

    if not reviewer:
        st.warning("Enter your name in the sidebar to review recommendations.")

    if st.button(
        f"Approve All high-confidence items (≥ 0.90, lossless) — "
        f"{summary['bulk_approvable_pending']}",
        disabled=not reviewer or summary["bulk_approvable_pending"] == 0,
    ):
        approved = run.session.approve_all_bulk(reviewer)
        run.state.review_ledger = run.session.ledger
        run.save_review_queue()
        st.session_state.flash = f"Approved {len(approved)} item(s)."
        st.rerun()

    view = st.radio(
        "Show", ["Pending", "Escalated", "Decided", "All"], horizontal=True
    )
    kinds = st.multiselect(
        "Action types",
        [a.value for a in ActionType],
        default=[a.value for a in ActionType],
    )

    items = list(ledger.items.values())

    def visible(item) -> bool:
        status = item.current.status
        if view == "Pending" and status not in {IssueStatus.RECOMMENDED, IssueStatus.ESCALATED}:
            return False
        if view == "Escalated" and status != IssueStatus.ESCALATED:
            return False
        if view == "Decided" and item.is_open:
            return False
        return item.current.action_type.value in kinds

    shown = [item for item in items if visible(item)]
    st.caption(f"{len(shown)} item(s)")

    for item in shown:
        render_item(run, item, reviewer)


def render_item(run: PipelineRun, item, reviewer: str) -> None:
    rec = item.current
    label = (
        f"{SEVERITY_BADGE[rec.severity.value]} · "
        f"{STATUS_LABEL.get(rec.status.value, rec.status.value)} · {rec.title}"
    )

    with st.expander(label, expanded=False):
        meta = st.columns(5)
        meta[0].write(f"**Action**\n\n{rec.action_type.value}")
        meta[1].write(f"**Operation**\n\n{rec.operation.value}")
        meta[2].write(f"**Fix confidence**\n\n{rec.fix_confidence:.2f}")
        meta[3].write(f"**Rows**\n\n{rec.affected_row_count}")
        meta[4].write(
            f"**Attempt**\n\n{rec.attempt} ({rec.reasoning_source.value})"
        )

        if rec.source_column:
            st.write(f"**Source column:** {rec.source_column} → **{rec.target_field}**"
                     if rec.action_type == ActionType.COLUMN_MAPPING
                     else f"**Source column:** {rec.source_column}")

        st.write(f"**Why:** {rec.rationale}")
        st.write(f"**Uncertainty:** {rec.uncertainty}")

        if rec.llm_explanation:
            st.info(f"Business impact: {rec.llm_explanation}")

        if rec.policy_reasons:
            st.caption(
                ("Approve-All eligible. " if rec.policy == ReviewPolicy.BULK_APPROVABLE else "")
                + " ".join(rec.policy_reasons)
            )

        if rec.samples:
            source_rows = run.state.metadata.get("agent3_source_rows", {})
            st.write("**Before → after (sample)**")
            st.dataframe(
                display_frame(
                    pd.DataFrame(
                        [
                            {
                                "Excel row": s.source_row or source_rows.get(s.row_index, ""),
                                "Before": s.before,
                                "After": s.after,
                            }
                            for s in rec.samples
                        ]
                    )
                ),
                hide_index=True,
            )

        if item.history or item.actions:
            with st.popover("Decision history"):
                for position, action in enumerate(item.actions):
                    version = item.history[position] if position < len(item.history) else rec
                    st.write(
                        f"**{action.decision.value}** by {action.reviewer} "
                        f"({action.timestamp:%Y-%m-%d %H:%M}) on attempt "
                        f"{version.attempt}: “{version.title}”"
                        + (f" — {action.reason}" if action.reason else "")
                    )

        if item.is_open:
            review_form(run, item, reviewer)


def review_form(run: PipelineRun, item, reviewer: str) -> None:
    rec = item.current
    is_mapping = rec.rule_id in {"schema_mapping", "column_unmapped"}

    with st.form(key=f"form-{rec.recommendation_id}-{len(item.actions)}"):
        decision = st.radio(
            "Decision",
            ["Approve", "Reject", "Edit", "Escalate"],
            horizontal=True,
        )
        reason = st.text_input("Note (required to reject — the agent re-reasons with it)")

        edited = None
        per_row = None

        if is_mapping:
            options = ["— leave unmapped —"] + list(SOV_REQUIRED_FIELDS)
            current = rec.target_field if rec.target_field in options else options[0]
            edited = st.selectbox(
                "Edit: map this column to", options, index=options.index(current)
            )
        elif rec.affected_rows:
            source_rows = run.state.metadata.get("agent3_source_rows", {})
            canonical = run.state.canonical_data
            befores = {
                row: canonical.at[row, rec.target_field]
                for row in rec.affected_rows
                if rec.target_field in canonical.columns
            }

            if len({repr(v) for v in befores.values()}) <= 1:
                edited = st.text_input(
                    f"Edit: new value for all {rec.affected_row_count} row(s) "
                    "(leave blank for an empty cell)"
                )
            else:
                st.caption("Edit: rows have different values — set each row (blank = keep source value).")
                per_row = st.data_editor(
                    display_frame(
                        pd.DataFrame(
                            {
                                "row": list(befores),
                                "Excel row": [source_rows.get(r, "") for r in befores],
                                "Before": list(befores.values()),
                                "New value": [""] * len(befores),
                            }
                        )
                    ),
                    disabled=["row", "Excel row", "Before"],
                    hide_index=True,
                    key=f"editor-{rec.recommendation_id}",
                )

        submitted = st.form_submit_button("Submit decision", disabled=not reviewer)

    if not submitted:
        return

    try:
        action = build_action(rec, decision, reason, edited, per_row, reviewer, is_mapping)
        result = run.submit(action)
        message = f"{decision}d: {result.title}" if decision != "Edit" else f"Edited: {result.title}"

        if decision == "Reject":
            message = (
                f"Re-reasoned (attempt {result.attempt}): {result.title}"
                if result.status == IssueStatus.RECOMMENDED
                else f"Escalated: {result.policy_reasons[-1]}"
            )

        if run.revalidate_if_needed():
            message += " — mapping changed, Agent 3 re-validated the data."

        run.save_review_queue()
        st.session_state.flash = message
        st.rerun()

    except (ReviewError, ValidationError, ValueError) as error:
        st.error(str(error))


def build_action(rec, decision, reason, edited, per_row, reviewer, is_mapping) -> ReviewAction:
    kwargs = {
        "recommendation_id": rec.recommendation_id,
        "decision": ReviewDecision(decision.lower()),
        "reviewer": reviewer,
        "reason": reason or None,
    }

    if decision != "Edit":
        return ReviewAction(**kwargs)

    if is_mapping:
        kwargs["edited_value"] = None if edited == "— leave unmapped —" else edited
    elif per_row is not None:
        values = {
            int(row["row"]): coerce_edit_value(rec.target_field, row["New value"])
            for _, row in per_row.iterrows()
            if str(row["New value"]).strip()
        }

        if not values:
            raise ValueError("Enter a new value for at least one row.")

        kwargs["edited_value"] = values
    else:
        kwargs["edited_value"] = coerce_edit_value(rec.target_field, edited)

    return ReviewAction(**kwargs)


def tab_export(run: PipelineRun) -> None:
    st.subheader("Before / after preview and export (Agent 4)")

    rows = st.slider("Rows to preview", 5, max(5, min(200, len(run.state.data_table))), 10)
    before = run.state.canonical_data.head(rows)
    after = run.preview().head(rows)
    changed = st.toggle("Show only columns with approved changes", value=False)

    if changed:
        columns = [
            c for c in after.columns
            if c in before.columns
            and not display_frame(before[[c]]).equals(display_frame(after[[c]]))
        ]
        before, after = before[columns], after[columns]

    left, right = st.columns(2)
    left.write("**Before** (source values under target names)")
    left.dataframe(display_frame(before), width="stretch")
    right.write("**After** (approved changes + data-dictionary types)")
    right.dataframe(display_frame(after), width="stretch")

    st.divider()
    pending = len(run.session.ledger.pending())

    if pending:
        st.warning(
            f"Export is blocked: {pending} recommendation(s) still need a "
            "decision (FR-5). Finish them in the Review tab."
        )

    if st.button("Export Cleaned_SOV.xlsx", type="primary", disabled=pending > 0):
        with st.spinner("Applying approved transformations..."):
            result = run.export()

        if result is None:
            st.error(run.errors[-1])
        else:
            st.session_state.flash = (
                f"Exported {result.rows} rows, {result.applied_changes} approved "
                f"changes, {result.audit_entries} audit entries."
            )
            st.rerun()

    result = run.export_result

    if result is not None:
        if result.schema_valid:
            st.success("Schema validation passed: 17 columns in order, correct types, no merged cells.")
        else:
            st.error("Schema problems: " + "; ".join(result.schema_problems))

        col1, col2 = st.columns(2)
        col1.download_button(
            "Download Cleaned_SOV.xlsx",
            Path(result.output_path).read_bytes(),
            file_name="Cleaned_SOV.xlsx",
        )
        col2.download_button(
            "Download Audit_Log.json",
            Path(result.audit_json_path).read_bytes(),
            file_name="Audit_Log.json",
        )

        audit = json.loads(Path(result.audit_json_path).read_text(encoding="utf-8"))
        st.write("**Audit log**")
        st.dataframe(display_frame(pd.DataFrame(audit)), hide_index=True, width="stretch")


# ---------------------------------------------------------------------


def main() -> None:
    sidebar()
    run = st.session_state.get("run")

    if run is None:
        st.title("SOVereign AI")
        st.write(
            "Upload a Statement of Values (.xlsx or .csv) in the sidebar and "
            "click **Analyse file**. Four agents find the data sheet, map the "
            "columns to the 17-field schema, check every row and recommend "
            "fixes. Nothing changes until you approve it."
        )
        return

    if run.state is None or (run.errors and run.session is None):
        st.error("The file could not be processed:")
        for error in run.errors:
            st.write(f"- {error}")
        return

    flash = st.session_state.pop("flash", None)

    if flash:
        st.success(flash)

    tabs = st.tabs(
        ["Workflow", "1 · Sheets", "2 · Mapping", "3 · Data quality",
         f"4 · Review ({len(run.session.ledger.pending())})", "5 · Preview & export"]
    )

    with tabs[0]:
        tab_workflow(run)
    with tabs[1]:
        tab_sheets(run)
    with tabs[2]:
        tab_mapping(run)
    with tabs[3]:
        tab_quality(run)
    with tabs[4]:
        tab_review(run)
    with tabs[5]:
        tab_export(run)


main()
