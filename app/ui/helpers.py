"""
UI-independent helpers for the review interface (kept out of the
Streamlit script so they can be unit-tested).
"""

from typing import Any, Optional

import pandas as pd

from app.agents.data_quality import normalizers
from app.agents.data_quality.issue_schema import IssueStatus


def coerce_edit_value(field: Optional[str], text: Any) -> Any:
    """
    Turn what a reviewer typed into a value of the field's type.

    Blank means "leave the cell blank" (never 0 or a placeholder).
    Raises ValueError with a readable message when the text cannot be
    a value of that field; the deterministic validator still checks the
    result when the edit is submitted.
    """

    if text is None:
        return None

    if not isinstance(text, str):
        return text

    value = text.strip()

    if not value:
        return None

    if field in normalizers.MONETARY_FIELDS:
        number = normalizers.parse_monetary(value)

        if number is None:
            raise ValueError(f"'{value}' is not an amount (e.g. 1200000 or $1.2M).")

        return number

    if field in normalizers.INTEGER_FIELDS or field == "Year Built":
        number = normalizers.parse_whole_int(value)

        if number is None:
            raise ValueError(f"'{value}' is not a whole number.")

        return number

    if field == "Fire Sprinklers (Y/N)":
        return " ".join(value.upper().split())

    if field == "State":
        return normalizers.standardise_state(value) or value

    return value


def display_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Text-only copy for display; blanks stay visibly blank."""

    return frame.astype(object).map(
        lambda value: "" if normalizers.is_missing(value) else str(value)
    )


_NODE_STYLE = {
    "done": ('"#d1fae5"', '"#047857"'),
    "active": ('"#fef3c7"', '"#b45309"'),
    "waiting": ('"#f3f4f6"', '"#6b7280"'),
    "error": ('"#fee2e2"', '"#b91c1c"'),
}


def workflow_dot(run: Any) -> str:
    """
    Graphviz DOT of the agent workflow and its current state, including
    the reject -> re-reason loop between review and Agent 3.
    """

    state = run.state
    trace = {entry["agent"]: entry for entry in (state.agent_trace if state else [])}
    failed = run.stage_reached if run.errors and not run.export_result else None

    def status(agent: str, done: bool, active: bool = False) -> str:
        if failed == agent:
            return "error"
        if done:
            return "done"
        return "active" if active else "waiting"

    ledger = state.review_ledger if state else None
    pending = len(ledger.pending()) if ledger else 0
    escalated = (
        sum(1 for r in ledger.pending() if r.status == IssueStatus.ESCALATED)
        if ledger
        else 0
    )
    exported = run.export_result is not None

    def summary(agent: str) -> str:
        data = trace.get(agent, {}).get("summary", {})

        if agent == "sheet_discovery" and data:
            return f"{data['selected_sheet']}\\n{data['data_rows']} rows"
        if agent == "schema_mapping" and data:
            return f"{data['mapped']} mapped / {data['unresolved']} unresolved"
        if agent == "data_quality" and state and state.quality_report:
            report = state.quality_report
            return f"{report.total_issues} issues\\nscore {report.intake_quality_score}"
        if agent == "transformation" and exported:
            return f"{run.export_result.applied_changes} changes applied"
        return ""

    nodes = [
        ("ingestion", "Ingestion", status("ingestion", state is not None), ""),
        ("sheet_discovery", "Agent 1\\nSheet Discovery",
         status("sheet_discovery", "sheet_discovery" in trace), summary("sheet_discovery")),
        ("schema_mapping", "Agent 2\\nSchema Mapping",
         status("schema_mapping", "schema_mapping" in trace), summary("schema_mapping")),
        ("data_quality", "Agent 3\\nData Quality & Reasoning",
         status("data_quality", "data_quality" in trace), summary("data_quality")),
        ("human_review", "Human Review",
         status("human_review", ledger is not None and pending == 0,
                active=ledger is not None and pending > 0),
         f"{pending} pending" + (f", {escalated} escalated" if escalated else "")
         if ledger else ""),
        ("transformation", "Agent 4\\nControlled Transformation",
         status("transformation", exported, active=run.export_ready and not exported),
         summary("transformation")),
        ("output", "Cleaned_SOV.xlsx\\n+ Audit_Log", "done" if exported else "waiting", ""),
    ]

    lines = [
        "digraph G {",
        "rankdir=LR;",
        'node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11];',
        'edge [color="#6b7280"];',
    ]

    for key, label, node_status, detail in nodes:
        fill, line = _NODE_STYLE[node_status]
        text = f"{label}\\n{detail}" if detail else label
        lines.append(f'{key} [label="{text}", fillcolor={fill}, color={line}];')

    order = [key for key, *_ in nodes]

    for left, right in zip(order, order[1:]):
        lines.append(f"{left} -> {right};")

    lines.append(
        'human_review -> data_quality [label="reject + note\\n(re-reason, max 2)", '
        'style=dashed, constraint=false];'
    )
    lines.append("}")
    return "\n".join(lines)
