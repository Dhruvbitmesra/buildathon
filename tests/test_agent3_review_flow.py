"""
Levels 3 and 4: Agent 3 integration and the review / re-reasoning loop.
"""

import pandas as pd
import pytest

from app.agents.data_quality.agent import DataQualityAgent, dataframe_fingerprint
from app.agents.data_quality.canonical_frame import build_canonical_frame
from app.agents.data_quality.issue_schema import IssueStatus, IssueType
from app.agents.data_quality.normalizers import Operation
from app.agents.data_quality.reasoner import (
    GroqReasoner,
    ReasoningProposal,
    RuleBasedReasoner,
    find_value_in_note,
    masked_summary,
)
from app.agents.data_quality.recommendation_schema import (
    ActionType,
    ReasoningSource,
    ReviewAction,
    ReviewDecision,
)
from app.agents.data_quality.reflection import ReviewError
from app.state.sov_state import SOVState


YEAR = 2026


def frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Reference": ["L1", "L2", "L3", "L4"],
            "Country": ["USA"] * 4,
            "State": ["MA", "Texas", "TX", "TX"],
            "Zip": ["02108", "75219", "2108", "9410"],
            "Building Value": [100000.0, "$1,200,000", -500000.0, 250000.0],
            "Year Built": [1990, 2099, 1985, 2000],
            "Fire Sprinklers (Y/N)": ["Y", "YES", "MAYBE", "MAYBE"],
        },
        dtype=object,
    )


def session_for(df=None, reasoner=None, attempts=2):
    df = frame() if df is None else df
    agent = DataQualityAgent(reasoner=reasoner, max_reasoning_attempts=attempts)
    result = agent.analyse(df, current_year=YEAR)
    return result, agent.review_session(result, df), df


def rec_where(result, **criteria):
    for rec in result.recommendations:
        if all(getattr(rec, key) == value for key, value in criteria.items()):
            return rec
    raise AssertionError(f"no recommendation matching {criteria}")


def act(session, rec_id, decision, reason=None, **extra):
    return session.submit(
        ReviewAction(
            recommendation_id=rec_id,
            decision=decision,
            reviewer="tester",
            reason=reason,
            **extra,
        )
    )


# ---------------------------------------------------------------------
# Level 3: integration
# ---------------------------------------------------------------------


def test_analyse_does_not_modify_dataframe():
    df = frame()
    original = df.copy(deep=True)

    result = DataQualityAgent().analyse(df, current_year=YEAR)

    pd.testing.assert_frame_equal(df, original)
    assert result.dataframe_fingerprint == dataframe_fingerprint(original)


def test_analyse_produces_report_and_queue():
    result, _, _ = session_for()
    summary = result.summary()

    assert result.quality_report.total_issues > 0
    assert result.quality_report.intake_quality_score is not None
    assert summary["recommendations"] == len(result.recommendations)
    assert summary["review"]["export_ready"] is False


def test_review_requires_the_analysed_dataframe():
    df = frame()
    agent = DataQualityAgent()
    result = agent.analyse(df, current_year=YEAR)
    changed = df.copy()
    changed.at[0, "State"] = "NY"

    with pytest.raises(ValueError):
        agent.review_session(result, changed)


def test_canonical_frame_from_agent2_mappings():
    source = pd.DataFrame(
        {"Loc #": ["1", "2"], "Bldg Repl Cost": [1e6, 2e6], "Notes": ["a", "b"]}
    )
    mappings = [
        {"source_header": "Loc #", "target_field": "Reference"},
        {"source_header": "Bldg Repl Cost", "target_field": "Building Value"},
        {"source_header": "Notes", "target_field": None},
    ]

    canonical = build_canonical_frame(source, mappings, header_row=3)

    assert list(canonical.dataframe.columns) == ["Reference", "Building Value"]
    assert canonical.source_columns == {
        "Reference": "Loc #",
        "Building Value": "Bldg Repl Cost",
    }
    assert canonical.source_rows == {0: 5, 1: 6}
    assert canonical.unmapped_source_columns == ["Notes"]
    assert list(source.columns) == ["Loc #", "Bldg Repl Cost", "Notes"]


def test_canonical_frame_rejects_two_columns_for_one_target():
    source = pd.DataFrame({"a": [1], "b": [2]})

    with pytest.raises(ValueError):
        build_canonical_frame(
            source,
            [
                {"source_header": "a", "target_field": "BI"},
                {"source_header": "b", "target_field": "BI"},
            ],
        )


def test_sov_state_integration():
    source = pd.DataFrame(
        {"Loc": ["1", "1"], "TIV": ["$1,000", -5], "Sprk": ["YES", "MAYBE"]}
    )
    source.index = [2, 3]  # Agent 1 table index = Excel row numbers
    state = SOVState(
        selected_sheet="SOV",
        data_table=source,
        header_row=0,
        schema_mappings=[
            {"source_header": "Loc", "target_field": "Reference", "score": 0.95, "method": "exact"},
            {"source_header": "TIV", "target_field": "Building Value", "score": 0.7, "method": "semantic"},
            {"source_header": "Sprk", "target_field": "Fire Sprinklers (Y/N)", "score": 0.9, "method": "fuzzy"},
        ],
    )

    state = DataQualityAgent().run(state, current_year=YEAR)

    assert state.errors == []
    assert state.quality_report.total_issues > 0
    assert state.review_ledger.pending()
    assert state.source_columns["Building Value"] == "TIV"
    assert state.metadata["agent3_source_rows"] == {0: 2, 1: 3}
    assert state.agent_trace[-1]["agent"] == "data_quality"
    # The source sheet is untouched.
    assert source["TIV"].tolist() == ["$1,000", -5]


def test_sov_state_errors_are_recorded_not_raised():
    state = SOVState(selected_sheet="missing", sheet_data={})

    state = DataQualityAgent().run(state)

    assert state.errors and "Agent 1 must run before Agent 3" in state.errors[0]


# ---------------------------------------------------------------------
# Level 4: review and re-reasoning
# ---------------------------------------------------------------------


def test_approval_on_first_attempt_has_no_re_reasoning():
    result, session, _ = session_for()
    rec = rec_where(result, operation=Operation.PARSE_MONETARY)

    approved = act(session, rec.recommendation_id, ReviewDecision.APPROVE)

    assert approved.status == IssueStatus.APPROVED
    assert approved.attempt == 1


def test_reject_then_approve_second_recommendation():
    result, session, _ = session_for()
    rec = rec_where(result, operation=Operation.PARSE_MONETARY)

    second = act(session, rec.recommendation_id, ReviewDecision.REJECT,
                 "Client says these figures are in thousands")

    assert second.status == IssueStatus.RECOMMENDED
    assert second.attempt == 2
    assert second.operation == Operation.KEEP
    assert "Re-assessed after rejection" in second.rationale

    final = act(session, rec.recommendation_id, ReviewDecision.APPROVE)
    item = session.ledger.get(rec.recommendation_id)

    assert final.status == IssueStatus.APPROVED
    assert item.history[0].status == IssueStatus.REJECTED
    assert item.rejection_reasons == ["Client says these figures are in thousands"]


def test_two_rejections_escalate():
    result, session, _ = session_for()
    rec = rec_where(result, operation=Operation.PARSE_MONETARY)

    act(session, rec.recommendation_id, ReviewDecision.REJECT, "no")
    escalated = act(session, rec.recommendation_id, ReviewDecision.REJECT, "still no")

    assert escalated.status == IssueStatus.ESCALATED
    assert session.ledger.export_ready is False


def test_loop_is_bounded_by_max_attempts():
    result, session, _ = session_for(attempts=1)
    rec = rec_where(result, operation=Operation.PARSE_MONETARY)

    escalated = act(session, rec.recommendation_id, ReviewDecision.REJECT, "no")

    assert escalated.status == IssueStatus.ESCALATED


def test_rejecting_an_escalated_item_keeps_source_values():
    result, session, _ = session_for()
    rec = rec_where(result, operation=Operation.PARSE_MONETARY)

    act(session, rec.recommendation_id, ReviewDecision.REJECT, "no")
    act(session, rec.recommendation_id, ReviewDecision.REJECT, "no")
    final = act(session, rec.recommendation_id, ReviewDecision.REJECT, "leave it")

    assert final.status == IssueStatus.RESOLVED
    assert final.operation == Operation.KEEP
    assert not [c for c in session.approved_changes() if c.recommendation_id == rec.recommendation_id]


def test_rejection_note_naming_a_valid_value_is_used():
    result, session, _ = session_for()
    rec = rec_where(result, before_value="MAYBE")

    second = act(session, rec.recommendation_id, ReviewDecision.REJECT,
                 "Broker confirmed both sites have Y(13R) systems")

    assert second.operation == Operation.SET_VALUE
    assert second.after_value == "Y(13R)"
    assert second.reasoning_source == ReasoningSource.DETERMINISTIC


def test_flag_with_no_alternative_escalates_immediately():
    result, session, _ = session_for()
    rec = rec_where(result, issue_type=IssueType.NEGATIVE_VALUE)

    escalated = act(session, rec.recommendation_id, ReviewDecision.REJECT, "this is wrong")

    assert escalated.status == IssueStatus.ESCALATED


def test_decided_items_cannot_be_reviewed_again():
    result, session, _ = session_for()
    rec = rec_where(result, operation=Operation.PARSE_MONETARY)
    act(session, rec.recommendation_id, ReviewDecision.APPROVE)

    with pytest.raises(ReviewError):
        act(session, rec.recommendation_id, ReviewDecision.APPROVE)


def test_edit_is_validated():
    result, session, _ = session_for()
    rec = rec_where(result, before_value="MAYBE")

    with pytest.raises(ReviewError):
        act(session, rec.recommendation_id, ReviewDecision.EDIT, edited_value="PERHAPS")

    edited = act(session, rec.recommendation_id, ReviewDecision.EDIT, edited_value="N")

    assert edited.operation == Operation.SET_VALUE
    assert edited.reasoning_source == ReasoningSource.HUMAN


def test_single_edit_value_refused_for_rows_with_different_values():
    result, session, _ = session_for()
    rec = rec_where(result, operation=Operation.PAD_ZIP)

    with pytest.raises(ReviewError):
        act(session, rec.recommendation_id, ReviewDecision.EDIT, edited_value="02108")

    edited = act(session, rec.recommendation_id, ReviewDecision.EDIT,
                 edited_value={2: "02108"})
    changes = [c for c in session.approved_changes() if c.recommendation_id == rec.recommendation_id]

    assert edited.affected_rows == [2]
    assert [(c.row_index, c.after_value) for c in changes] == [(2, "02108")]


def test_approve_all_only_touches_bulk_items():
    result, session, _ = session_for()

    approved = session.approve_all_bulk("lead")

    assert approved
    assert all(rec.action_type in {ActionType.STANDARDISATION, ActionType.COLUMN_MAPPING}
               for rec in approved)
    assert all(rec.status == IssueStatus.RECOMMENDED for rec in session.ledger.pending())
    assert not session.ledger.export_ready


def test_export_ready_after_every_item_is_decided():
    result, session, _ = session_for()
    session.approve_all_bulk("lead")

    for rec in list(session.ledger.pending()):
        act(session, rec.recommendation_id, ReviewDecision.APPROVE)

    assert session.ledger.export_ready


def test_approved_changes_carry_audit_fields_and_match_preview():
    result, session, df = session_for()
    rec = rec_where(result, operation=Operation.PARSE_MONETARY)
    act(session, rec.recommendation_id, ReviewDecision.APPROVE)

    changes = session.approved_changes()

    assert len(changes) == 1
    change = changes[0]
    assert change.before_value == "$1,200,000"
    assert change.after_value == rec.samples[0].after == 1200000.0
    assert change.approved_by == "tester"
    assert change.timestamp is not None
    assert change.transformation_applied == Operation.PARSE_MONETARY
    assert df.at[1, "Building Value"] == "$1,200,000"


def test_audit_trail_records_every_action():
    result, session, _ = session_for()
    rec = rec_where(result, operation=Operation.PARSE_MONETARY)
    act(session, rec.recommendation_id, ReviewDecision.REJECT, "no")
    act(session, rec.recommendation_id, ReviewDecision.APPROVE)

    trail = session.ledger.audit_trail()

    assert [row["decision"] for row in trail] == ["reject", "approve"]
    assert [row["reasoning_attempt"] for row in trail] == [1, 2]


def test_ledger_round_trips_through_json():
    result, session, _ = session_for()
    rec = rec_where(result, operation=Operation.PARSE_MONETARY)
    act(session, rec.recommendation_id, ReviewDecision.REJECT, "no")

    restored = type(session.ledger).model_validate_json(session.ledger.model_dump_json())

    assert restored.get(rec.recommendation_id).current.attempt == 2


def test_carry_over_keeps_decisions_for_unchanged_items():
    df = frame()
    agent = DataQualityAgent()
    first = agent.analyse(df, current_year=YEAR)
    session = agent.review_session(first, df)
    rec = rec_where(first, operation=Operation.PARSE_MONETARY)
    act(session, rec.recommendation_id, ReviewDecision.APPROVE)

    second = agent.analyse(df, current_year=YEAR, previous=first)

    assert second.ledger.get(rec.recommendation_id).current.status == IssueStatus.APPROVED


# ---------------------------------------------------------------------
# Reasoner guardrails
# ---------------------------------------------------------------------


class ScriptedReasoner:
    name = "scripted"

    def __init__(self, proposal):
        self.proposal = proposal

    def reconsider(self, context):
        return self.proposal

    def explain(self, recommendation):
        return None


def test_llm_proposal_is_used_when_valid():
    proposal = ReasoningProposal(
        operation=Operation.SET_VALUE, value="Y13", rationale="Reviewer said Y13.",
        uncertainty="u", confidence=0.7,
    )
    result, session, _ = session_for(reasoner=ScriptedReasoner(proposal))
    rec = rec_where(result, before_value="MAYBE")

    second = act(session, rec.recommendation_id, ReviewDecision.REJECT, "use Y13")

    assert second.after_value == "Y13"
    assert second.reasoning_source == ReasoningSource.LLM


def test_llm_cannot_invent_values():
    proposal = ReasoningProposal(
        operation=Operation.SET_VALUE, value="Y", rationale="Guess.", uncertainty="u",
        confidence=0.99,
    )
    result, session, _ = session_for(reasoner=ScriptedReasoner(proposal))
    rec = rec_where(result, issue_type=IssueType.NEGATIVE_VALUE)

    # "Y" is not an allowed Building Value and is not in the note:
    # the proposal is discarded and the item escalates.
    outcome = act(session, rec.recommendation_id, ReviewDecision.REJECT, "this is wrong")

    assert outcome.status == IssueStatus.ESCALATED


def test_llm_cannot_use_operations_outside_the_field():
    proposal = ReasoningProposal(
        operation=Operation.PAD_ZIP, rationale="x", uncertainty="u", confidence=0.9,
    )
    result, session, _ = session_for(reasoner=ScriptedReasoner(proposal))
    rec = rec_where(result, operation=Operation.PARSE_MONETARY)

    second = act(session, rec.recommendation_id, ReviewDecision.REJECT, "no")

    # Falls back to the rule-based reasoner.
    assert second.operation == Operation.KEEP
    assert second.reasoning_source == ReasoningSource.DETERMINISTIC


def test_llm_cannot_repeat_the_rejected_proposal():
    proposal = ReasoningProposal(
        operation=Operation.PARSE_MONETARY, rationale="x", uncertainty="u", confidence=0.9,
    )
    result, session, _ = session_for(reasoner=ScriptedReasoner(proposal))
    rec = rec_where(result, operation=Operation.PARSE_MONETARY)

    second = act(session, rec.recommendation_id, ReviewDecision.REJECT, "no")

    assert second.reasoning_source == ReasoningSource.DETERMINISTIC


def test_find_value_in_note():
    values = ["N", "Y", "Y(13R)", "Y13"]

    assert find_value_in_note("they are Y(13R) systems", values) == "Y(13R)"
    assert find_value_in_note("set to N please", values) == "N"
    assert find_value_in_note("Not sure", values) is None
    assert find_value_in_note("either Y or N", values) is None


def test_masked_summary_hides_identifying_values():
    result, _, _ = session_for(df=pd.DataFrame({"Address": ["1 Main St", None]}))
    rec = rec_where(result, target_field="Address")

    summary = masked_summary(rec)

    assert "1 Main St" not in str(summary)


class FakeGroqClient:
    def __init__(self, content):
        self.content = content
        self.calls = []
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        self.calls.append(kwargs)

        class Message:
            content = self.content

        class Choice:
            message = Message()

        class Response:
            choices = [Choice()]

        return Response()


def test_groq_reasoner_uses_temperature_zero_and_validates_output():
    client = FakeGroqClient(
        '{"operation": "keep", "value": null, "rationale": "Keep it.", '
        '"uncertainty": "u", "confidence": 0.8}'
    )
    reasoner = GroqReasoner(client=client)
    result, session, _ = session_for(reasoner=reasoner)
    rec = rec_where(result, operation=Operation.PARSE_MONETARY)

    second = act(session, rec.recommendation_id, ReviewDecision.REJECT, "no")

    assert client.calls[0]["temperature"] == 0
    assert second.operation == Operation.KEEP
    assert second.reasoning_source == ReasoningSource.LLM


def test_groq_reasoner_falls_back_on_bad_output():
    reasoner = GroqReasoner(client=FakeGroqClient("not json"))
    result, session, _ = session_for(reasoner=reasoner)
    rec = rec_where(result, operation=Operation.PARSE_MONETARY)

    second = act(session, rec.recommendation_id, ReviewDecision.REJECT, "no")

    assert second.reasoning_source == ReasoningSource.DETERMINISTIC


class BatchExplainClient(FakeGroqClient):
    """Answers a batched explain request for every item it receives."""

    def create(self, **kwargs):
        import json as _json

        self.calls.append(kwargs)
        items = _json.loads(kwargs["messages"][1]["content"])["items"]
        self.content = _json.dumps(
            {"explanations": {i["id"]: f"Impact of {i['rule_id']}." for i in items}}
        )
        return self._response()

    def _response(self):
        content = self.content

        class Message:
            pass

        Message.content = content

        class Choice:
            message = Message()

        class Response:
            choices = [Choice()]

        return Response()


def test_llm_explanations_are_optional_and_do_not_change_values():
    client = BatchExplainClient("")
    agent = DataQualityAgent(reasoner=GroqReasoner(client=client), explain_with_llm=True)
    result = agent.analyse(frame(), current_year=YEAR)

    rec = rec_where(result, issue_type=IssueType.NEGATIVE_VALUE)

    assert len(client.calls) == 1  # one batched call
    assert rec.llm_explanation == "Impact of non_negative_value."
    assert rec.operation == Operation.KEEP
    payload = client.calls[0]["messages"][1]["content"]
    assert "1 Main St" not in payload  # identifying values masked


def test_rule_based_reasoner_is_default_fallback():
    assert RuleBasedReasoner().name == "rule_based"
