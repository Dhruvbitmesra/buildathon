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


st.set_page_config(
    page_title="SOVereign AI",
    page_icon=":material/fact_check:",
    layout="wide",
)

# Fixed labels: a label that changes (e.g. with a live count) resets the
# selected tab, which sent reviewers back to the first tab after every
# decision.
TABS = ["Overview", "Sheets", "Mapping", "Data quality", "Review", "Export"]
PAGE_SIZE = 10

SEVERITY = {
    "critical": ("Critical", "red"),
    "high": ("High", "orange"),
    "medium": ("Medium", "yellow"),
    "low": ("Low", "gray"),
}
STATUS = {
    "recommended": ("Pending", "blue"),
    "approved": ("Approved", "green"),
    "escalated": ("Escalated", "red"),
    "resolved": ("Resolved", "green"),
    "rejected": ("Rejected", "gray"),
}
ACTION_LABEL = {
    "column_mapping": "Column mapping",
    "data_correction": "Data correction",
    "standardisation": "Standardisation",
    "flag_for_review": "Flag for review",
}
LEAVE_UNMAPPED = "— leave unmapped —"

st.markdown(
    """
    <style>
      .block-container {padding-top: 1.6rem; padding-bottom: 3rem;}
      div[data-testid="stMetric"] {padding: 0.6rem 0.9rem;}
      .sov-title {font-size: 1.05rem; font-weight: 600; margin: 0.15rem 0 0.35rem;}
      .sov-muted {opacity: 0.75; font-size: 0.9rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------


def current_run() -> PipelineRun | None:
    return st.session_state.get("run")


def reviewer_name() -> str:
    return (st.session_state.get("reviewer") or "").strip()


def notify(message: str, icon: str = ":material/check_circle:") -> None:
    """Show a message after the next rerun (banner + toast)."""

    st.session_state.flash = (message, icon)


def badges(*items: tuple[str, str]) -> None:
    row = st.container(horizontal=True, gap="small")

    for label, color in items:
        row.badge(label, color=color)


# ---------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------


def sidebar() -> None:
    with st.sidebar:
        st.title("SOVereign AI")
        st.caption("Agentic SOV cleansing — nothing changes without your approval.")

        st.text_input(
            "1 · Your name",
            key="reviewer",
            placeholder="Required to make review decisions",
            help="Recorded as approved_by in the audit log.",
        )

        uploaded = st.file_uploader(
            "2 · SOV file", type=["xlsx", "xls", "csv"]
        )

        has_key = llm_available()

        with st.expander("Options", icon=":material/tune:"):
            use_llm = st.toggle(
                "LLM reasoning (Groq)",
                value=has_key,
                disabled=not has_key,
                help=(
                    "Ambiguous columns and rejected recommendations are "
                    "re-assessed by the LLM; identifying values are masked."
                    if has_key
                    else "Set GROQ_API_KEY in .env to enable."
                ),
            )
            explain = st.toggle(
                "LLM business-impact notes",
                value=use_llm,
                disabled=not use_llm,
            )
            use_memory = st.toggle(
                "Learn from reviewed mappings",
                value=True,
                help="Remembers approved column mappings (headers only).",
            )

        if st.button(
            "3 · Analyse file",
            type="primary",
            icon=":material/play_arrow:",
            disabled=uploaded is None,
            width="stretch",
        ):
            analyse(uploaded, use_llm, explain, use_memory)

        run = current_run()

        if run is not None and run.state is not None:
            st.divider()
            st.caption("Current file")
            st.write(f"**{Path(run.file_path).name}**")
            st.caption(
                f"LLM {'on' if run.use_llm else 'off'} · memory "
                f"{len(run.memory.entries) if run.memory else 'off'}"
            )

            with st.expander("Timings", icon=":material/timer:"):
                for stage, seconds in run.timings.items():
                    st.caption(f"{stage}: {seconds:.1f}s")

            if st.button("Start over", icon=":material/restart_alt:", width="stretch"):
                for key in ("run", "review_page", "flash"):
                    st.session_state.pop(key, None)
                st.rerun()


def analyse(uploaded, use_llm: bool, explain: bool, use_memory: bool) -> None:
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
    run.quality_agent.explain_with_llm = explain and use_llm

    with st.spinner("Running Agents 1–3 (the first run loads the models)…"):
        run.analyse()

    st.session_state.run = run
    st.session_state.review_page = 0
    st.session_state.active_tab = "Overview"
    st.rerun()


# ---------------------------------------------------------------------
# Header: always-visible progress
# ---------------------------------------------------------------------


def header(run: PipelineRun) -> None:
    state = run.state
    summary = run.session.ledger.summary()
    decided = summary["total"] - summary["pending"]

    left, right = st.columns([3, 2], vertical_alignment="bottom")

    with left:
        st.subheader(Path(run.file_path).name, anchor=False)
        st.caption(
            f"Sheet **{state.selected_sheet}** · header row {state.header_row + 1} · "
            f"{len(state.data_table)} rows · intake score "
            f"**{state.quality_report.intake_quality_score:.0f}/100**"
        )

    with right:
        if run.export_result is not None:
            st.success("Exported — download in the Export tab.", icon=":material/task_alt:")
        elif summary["pending"] == 0:
            st.success("All items decided — ready to export.", icon=":material/task_alt:")
        else:
            st.progress(
                decided / summary["total"] if summary["total"] else 1.0,
                text=f"Review: {decided} of {summary['total']} decided · "
                f"{summary['pending']} pending",
            )


# ---------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------


def tab_overview(run: PipelineRun) -> None:
    summary = run.session.ledger.summary()
    report = run.state.quality_report
    mapping = run.state.metadata.get("schema_mapping_json", {})

    cols = st.columns(4)
    cols[0].metric("Intake quality", f"{report.intake_quality_score:.0f}/100", border=True)
    cols[1].metric(
        "Columns mapped",
        sum(1 for m in mapping.get("mappings", {}).values() if m["target"]),
        border=True,
    )
    cols[2].metric("Issues found", report.total_issues, border=True)
    cols[3].metric("Pending decisions", summary["pending"], border=True)

    st.markdown("##### Agent workflow")
    st.graphviz_chart(workflow_dot(run), width="stretch")
    st.caption(
        "Green: done · Amber: waiting for you · Grey: not started · Red: failed. "
        "The dashed edge is the re-reasoning loop after a rejection."
    )

    st.markdown("##### Next steps")
    steps = [
        (bool(reviewer_name()), "Enter your name in the sidebar"),
        (summary["bulk_approvable_pending"] == 0, "Approve the safe, high-confidence items (Review → Approve All)"),
        (summary["pending"] == 0, f"Decide the remaining items ({summary['pending']} pending)"),
        (run.export_result is not None, "Export Cleaned_SOV.xlsx (Export tab)"),
    ]

    for done, text in steps:
        st.markdown(f"{':material/check_circle:' if done else ':material/radio_button_unchecked:'} {text}")

    with st.expander("Shared state hand-offs (agent trace)"):
        st.json(run.state.agent_trace)


def tab_sheets(run: PipelineRun) -> None:
    state = run.state
    st.markdown(
        f"Selected **{state.selected_sheet}** — header on row "
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
            column_config={
                "sheet_name": "Sheet",
                "classification": "Role",
                "confidence": st.column_config.ProgressColumn(
                    "Confidence", min_value=0.0, max_value=1.0, format="%.2f"
                ),
                "rank_score": st.column_config.NumberColumn("Rank score", format="%.2f"),
                "header_row": "Header row",
                "data_rows": "Data rows",
                "reasoning": st.column_config.TextColumn("Reasoning", width="large"),
            },
        )

    excluded = state.metadata.get("excluded_rows", [])

    if excluded:
        with st.expander(f"{len(excluded)} row(s) left out of the data table (not locations)"):
            st.dataframe(pd.DataFrame(excluded), hide_index=True, width="stretch")

    for warning in state.warnings:
        st.warning(warning, icon=":material/info:")


def tab_mapping(run: PipelineRun) -> None:
    mapping_json = run.state.metadata.get("schema_mapping_json", {})
    rows = [
        {
            "Source column": source,
            "Target field": entry["target"] or LEAVE_UNMAPPED,
            "Confidence": entry["confidence"],
            "Method": entry["method"],
            "Needs review": "yes" if entry.get("flag") else "",
        }
        for source, entry in mapping_json.get("mappings", {}).items()
    ]
    mapped = sum(1 for r in rows if r["Target field"] != LEAVE_UNMAPPED)

    cols = st.columns(3)
    cols[0].metric("Mapped", mapped, border=True)
    cols[1].metric("Unresolved", mapping_json.get("unresolved_count", 0), border=True)
    cols[2].metric("Overall confidence", f"{mapping_json.get('overall_confidence', 0):.2f}", border=True)

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
        st.info(
            "Target fields with no source column (exported blank): " + ", ".join(missing),
            icon=":material/info:",
        )

    st.caption("Change a mapping from the Review tab (Edit on a column-mapping item).")

    with st.expander("Mapping JSON (Section 09 format)"):
        st.json(mapping_json)


def tab_quality(run: PipelineRun) -> None:
    report = run.state.quality_report

    cols = st.columns(4)
    cols[0].metric("Intake quality score", f"{report.intake_quality_score:.1f}/100", border=True)
    cols[1].metric("Issues", report.total_issues, border=True)
    cols[2].metric("High / critical", report.high_issue_count + report.critical_issue_count, border=True)
    cols[3].metric("Rows with issues", len(report.row_flags), border=True)

    left, right = st.columns(2)

    with left, st.container(border=True):
        st.markdown("**Issues by type**")
        st.bar_chart(pd.Series(report.issues_by_type, name="issues"), horizontal=True, height=260)

    with right, st.container(border=True):
        st.markdown("**Issues by severity**")
        order = ["critical", "high", "medium", "low"]
        st.bar_chart(
            pd.Series({k: report.issues_by_severity.get(k, 0) for k in order}, name="issues"),
            horizontal=True,
            height=260,
        )

    st.markdown("**Per-field completeness and validity**")
    st.dataframe(
        pd.DataFrame(
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
        ),
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
                        "Fields with issues": ", ".join(map(str, fields)),
                    }
                    for row, fields in report.row_flags.items()
                ]
            ),
            hide_index=True,
            width="stretch",
        )


def tab_review(run: PipelineRun) -> None:
    ledger = run.session.ledger
    summary = ledger.summary()
    reviewer = reviewer_name()

    if not reviewer:
        st.warning(
            "Enter **your name** in the sidebar to make decisions — it is "
            "recorded in the audit log.",
            icon=":material/person:",
        )

    top = st.columns([2, 2, 2, 3], vertical_alignment="bottom")
    top[0].metric("Pending", summary["pending"], border=True)
    top[1].metric("Escalated", summary["escalated"], border=True)
    top[2].metric("Decided", summary["total"] - summary["pending"], border=True)

    with top[3]:
        if st.button(
            f"Approve All safe items ({summary['bulk_approvable_pending']})",
            type="primary",
            icon=":material/done_all:",
            disabled=not reviewer or summary["bulk_approvable_pending"] == 0,
            help="Lossless standardisations and column mappings with confidence ≥ 0.90.",
            width="stretch",
        ):
            approved = run.session.approve_all_bulk(reviewer)
            run.state.review_ledger = run.session.ledger
            run.save_review_queue()
            notify(f"Approved {len(approved)} high-confidence item(s).")
            st.rerun()

    filters = st.columns([3, 4, 4])
    view = filters[0].segmented_control(
        "Show", ["Pending", "Escalated", "Decided", "All"],
        default="Pending", key="review_view", required=True,
    )
    severities = filters[1].pills(
        "Severity", [v[0] for v in SEVERITY.values()], selection_mode="multi",
        key="review_severity",
    )
    actions = filters[2].pills(
        "Action", list(ACTION_LABEL.values()), selection_mode="multi",
        key="review_actions",
    )

    def visible(item) -> bool:
        rec = item.current
        status = rec.status

        if view == "Pending" and status not in {IssueStatus.RECOMMENDED, IssueStatus.ESCALATED}:
            return False
        if view == "Escalated" and status != IssueStatus.ESCALATED:
            return False
        if view == "Decided" and item.is_open:
            return False
        if severities and SEVERITY[rec.severity.value][0] not in severities:
            return False
        if actions and ACTION_LABEL[rec.action_type.value] not in actions:
            return False
        return True

    items = [item for item in ledger.items.values() if visible(item)]

    if not items:
        st.success(
            "Nothing here. " + ("All items are decided — go to **Export**." if summary["pending"] == 0 else ""),
            icon=":material/inbox:",
        )
        return

    pages = max(1, -(-len(items) // PAGE_SIZE))
    page = min(st.session_state.get("review_page", 0), pages - 1)
    st.session_state.review_page = page

    for item in items[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]:
        review_card(run, item, reviewer)

    if pages > 1:
        nav = st.columns([1, 2, 1], vertical_alignment="center")

        if nav[0].button("Previous", icon=":material/chevron_left:", disabled=page == 0, width="stretch"):
            st.session_state.review_page = page - 1
            st.rerun()

        nav[1].caption(f"Page {page + 1} of {pages} · {len(items)} item(s)")

        if nav[2].button("Next", icon=":material/chevron_right:", disabled=page >= pages - 1, width="stretch"):
            st.session_state.review_page = page + 1
            st.rerun()


def review_card(run: PipelineRun, item, reviewer: str) -> None:
    rec = item.current
    rec_id = rec.recommendation_id

    with st.container(border=True, key=f"card-{rec_id}"):
        severity, severity_color = SEVERITY[rec.severity.value]
        status, status_color = STATUS.get(rec.status.value, (rec.status.value, "gray"))
        tags = [
            (severity, severity_color),
            (ACTION_LABEL[rec.action_type.value], "blue"),
            (status, status_color),
            (f"confidence {rec.fix_confidence:.2f}", "gray"),
        ]

        if rec.policy == ReviewPolicy.BULK_APPROVABLE and item.is_open:
            tags.append(("Approve-All eligible", "green"))
        if rec.attempt > 1:
            tags.append((f"attempt {rec.attempt} · {rec.reasoning_source.value}", "violet"))

        badges(*tags)
        st.markdown(f'<div class="sov-title">{rec.title}</div>', unsafe_allow_html=True)

        body, side = st.columns([3, 2])

        with body:
            st.markdown(rec.rationale)
            st.caption(f"Uncertainty: {rec.uncertainty}")

            if rec.llm_explanation:
                st.info(rec.llm_explanation, icon=":material/lightbulb:")

        with side:
            if rec.samples:
                source_rows = run.state.metadata.get("agent3_source_rows", {})
                st.dataframe(
                    display_frame(
                        pd.DataFrame(
                            [
                                {
                                    "Row": s.source_row or source_rows.get(s.row_index, ""),
                                    "Before": s.before,
                                    "After": s.after,
                                }
                                for s in rec.samples
                            ]
                        )
                    ),
                    hide_index=True,
                    width="stretch",
                    height=min(38 + 35 * len(rec.samples), 220),
                )
            elif rec.action_type == ActionType.COLUMN_MAPPING:
                st.markdown(f"`{rec.source_column}` → **{rec.target_field}**")

        with st.expander("Evidence and history", icon=":material/history:"):
            if rec.policy_reasons:
                st.caption("Review policy: " + " ".join(rec.policy_reasons))

            st.json(rec.evidence.model_dump(mode="json"), expanded=False)

            for position, action in enumerate(item.actions):
                version = item.history[position] if position < len(item.history) else rec
                st.markdown(
                    f"- **{action.decision.value}** by {action.reviewer} "
                    f"({action.timestamp:%Y-%m-%d %H:%M}) on attempt {version.attempt}: "
                    f"“{version.title}”" + (f" — {action.reason}" if action.reason else "")
                )

        if not item.is_open:
            return

        buttons = st.container(horizontal=True, gap="small")
        disabled = not reviewer

        if buttons.button("Approve", key=f"approve-{rec_id}", type="primary",
                          icon=":material/check:", disabled=disabled):
            submit(run, rec, ReviewDecision.APPROVE, reviewer)

        if buttons.button("Reject", key=f"reject-{rec_id}", icon=":material/close:", disabled=disabled):
            decision_dialog(rec_id, "reject")

        if buttons.button("Edit", key=f"edit-{rec_id}", icon=":material/edit:", disabled=disabled):
            decision_dialog(rec_id, "edit")

        if buttons.button("Escalate", key=f"escalate-{rec_id}", icon=":material/flag:", disabled=disabled):
            decision_dialog(rec_id, "escalate")


@st.dialog("Review decision", width="large")
def decision_dialog(rec_id: str, mode: str) -> None:
    run = current_run()
    reviewer = reviewer_name()
    item = run.session.ledger.get(rec_id)
    rec = item.current
    is_mapping = rec.rule_id in {"schema_mapping", "column_unmapped"}

    st.markdown(f"**{rec.title}**")
    st.caption(rec.rationale)

    edited = None
    per_row = None

    if mode == "reject":
        st.info(
            "The agent re-assesses this item using your note (maximum two "
            "attempts, then it is escalated).",
            icon=":material/psychology:",
        )
        note = st.text_area("Why is this wrong? (required)", key=f"note-{rec_id}")

    elif mode == "escalate":
        note = st.text_area("Note for the escalation (optional)", key=f"note-{rec_id}")

    else:
        if is_mapping:
            options = [LEAVE_UNMAPPED] + list(SOV_REQUIRED_FIELDS)
            current = rec.target_field if rec.target_field in options else options[0]
            edited = st.selectbox(
                f"Map column '{rec.source_column}' to",
                options,
                index=options.index(current),
            )
        elif rec.affected_rows:
            canonical = run.state.canonical_data
            source_rows = run.state.metadata.get("agent3_source_rows", {})
            befores = {
                row: canonical.at[row, rec.target_field]
                for row in rec.affected_rows
                if rec.target_field in canonical.columns
            }

            if len({repr(v) for v in befores.values()}) <= 1:
                edited = st.text_input(
                    f"New value for {rec.target_field} "
                    f"({rec.affected_row_count} row(s); leave blank for an empty cell)"
                )
            else:
                st.caption("Rows have different values — set each row (blank keeps the source value).")
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
                    column_config={"row": None},
                    key=f"editor-{rec_id}",
                )
        else:
            st.warning("This item is not tied to specific cells; edit the column mapping instead.")
            return

        note = st.text_input("Note (optional)", key=f"note-{rec_id}")

    labels = {"reject": "Reject and re-reason", "edit": "Save edit", "escalate": "Escalate"}

    if st.button(labels[mode], type="primary", width="stretch"):
        try:
            submit(
                run,
                rec,
                ReviewDecision(mode),
                reviewer,
                note=note,
                edited=edited,
                per_row=per_row,
                is_mapping=is_mapping,
            )
        except (ReviewError, ValidationError, ValueError) as error:
            st.error(str(error))


def submit(
    run: PipelineRun,
    rec,
    decision: ReviewDecision,
    reviewer: str,
    note: str | None = None,
    edited=None,
    per_row=None,
    is_mapping: bool = False,
) -> None:
    """Apply one decision, re-validate if a mapping changed, stay on Review."""

    kwargs = {
        "recommendation_id": rec.recommendation_id,
        "decision": decision,
        "reviewer": reviewer,
        "reason": (note or "").strip() or None,
    }

    if decision == ReviewDecision.EDIT:
        if is_mapping:
            kwargs["edited_value"] = None if edited == LEAVE_UNMAPPED else edited
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

    if decision == ReviewDecision.APPROVE:
        try:
            result = run.submit(ReviewAction(**kwargs))
        except (ReviewError, ValidationError, ValueError) as error:
            st.error(str(error))
            return
    else:
        result = run.submit(ReviewAction(**kwargs))

    if decision == ReviewDecision.REJECT:
        message = (
            f"Re-reasoned (attempt {result.attempt}): {result.title}"
            if result.status == IssueStatus.RECOMMENDED
            else f"Escalated: {result.policy_reasons[-1]}"
        )
        icon = ":material/psychology:"
    else:
        past = {"approve": "Approved", "edit": "Edited", "escalate": "Escalated"}
        message = f"{past[decision.value]}: {result.title}"
        icon = ":material/check_circle:"

    if run.revalidate_if_needed():
        message += " — mapping changed, Agent 3 re-validated the data."

    run.save_review_queue()
    notify(message, icon)
    st.rerun()


def tab_export(run: PipelineRun) -> None:
    pending = len(run.session.ledger.pending())

    with st.container(border=True):
        st.markdown("**Before / after preview**")
        rows = st.slider(
            "Rows to preview", 5, max(5, min(200, len(run.state.data_table))), 10,
            key="preview_rows",
        )
        only_changed = st.toggle("Only columns with approved changes", key="preview_changed")

        before = run.state.canonical_data.head(rows)
        after = run.preview().head(rows)

        if only_changed:
            columns = [
                c for c in after.columns
                if c in before.columns
                and not display_frame(before[[c]]).equals(display_frame(after[[c]]))
            ]
            before, after = before[columns], after[columns]

        left, right = st.columns(2)
        left.caption("Before — source values under target names")
        left.dataframe(display_frame(before), width="stretch")
        right.caption("After — approved changes + data-dictionary types")
        right.dataframe(display_frame(after), width="stretch")

    with st.container(border=True):
        st.markdown("**Export**")

        if pending:
            st.warning(
                f"Export is blocked: {pending} item(s) still need a decision "
                "(Review tab).",
                icon=":material/lock:",
            )

        if st.button(
            "Export Cleaned_SOV.xlsx",
            type="primary",
            icon=":material/download:",
            disabled=pending > 0,
        ):
            with st.spinner("Applying approved transformations…"):
                result = run.export()

            if result is None:
                st.error(run.errors[-1])
            else:
                notify(
                    f"Exported {result.rows} rows, {result.applied_changes} approved "
                    f"changes, {result.audit_entries} audit entries."
                )
                st.rerun()

        result = run.export_result

        if result is None:
            return

        if result.schema_valid:
            st.success(
                "Schema validation passed: single sheet 'Cleaned_SOV', 17 columns "
                "in order, correct types, no merged cells.",
                icon=":material/verified:",
            )
        else:
            st.error("Schema problems: " + "; ".join(result.schema_problems))

        downloads = [
            ("Download Cleaned_SOV.xlsx", result.output_path, "Cleaned_SOV.xlsx"),
            ("Download Audit_Log.xlsx", result.audit_xlsx_path, "Audit_Log.xlsx"),
            ("Download Audit_Log.json", result.audit_json_path, "Audit_Log.json"),
            ("Download processing summary", result.summary_path, "Processing_Summary.md"),
        ]

        for column, (label, path, name) in zip(st.columns(len(downloads)), downloads):
            column.download_button(
                label, Path(path).read_bytes(), file_name=name,
                icon=":material/file_download:", width="stretch",
            )

        with st.expander("Processing summary"):
            st.markdown(Path(result.summary_path).read_text(encoding="utf-8"))

        audit = json.loads(Path(result.audit_json_path).read_text(encoding="utf-8"))

        with st.expander(f"Audit log ({len(audit)} entries)"):
            st.dataframe(display_frame(pd.DataFrame(audit)), hide_index=True, width="stretch")


# ---------------------------------------------------------------------


def main() -> None:
    sidebar()
    run = current_run()

    if run is None:
        st.title("SOVereign AI")
        st.markdown(
            "Upload a Statement of Values (.xlsx or .csv) in the sidebar and "
            "click **Analyse file**. Four agents find the data sheet, map the "
            "columns to the 17-field schema, check every row and recommend "
            "fixes. **Nothing changes until you approve it.**"
        )
        cols = st.columns(4)
        for col, (title, text) in zip(cols, [
            ("1 · Sheet discovery", "Finds the data sheet and header row."),
            ("2 · Schema mapping", "Maps columns to the 17 target fields."),
            ("3 · Quality & reasoning", "Checks every row, explains each fix."),
            ("4 · Transformation", "Applies only what you approve, with an audit log."),
        ]):
            with col.container(border=True):
                st.markdown(f"**{title}**")
                st.caption(text)
        return

    if run.state is None or (run.errors and run.session is None):
        st.error("The file could not be processed:", icon=":material/error:")
        for error in run.errors:
            st.write(f"- {error}")
        return

    flash = st.session_state.pop("flash", None)

    if flash:
        message, icon = flash if isinstance(flash, tuple) else (flash, None)
        st.toast(message, icon=icon)

    header(run)

    # Stateful tabs with fixed labels: the selected tab survives every
    # rerun (review decisions, exports) and is kept in the URL.
    tabs = st.tabs(TABS, key="active_tab", on_change="rerun", bind="query-params")
    renderers = [tab_overview, tab_sheets, tab_mapping, tab_quality, tab_review, tab_export]

    for tab, render in zip(tabs, renderers):
        # Only the open tab is computed (open is None if state tracking
        # is unavailable; then everything renders).
        if tab.open is False:
            continue

        with tab:
            render(run)


main()
