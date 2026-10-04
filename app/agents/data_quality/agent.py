"""
Agent 3: Data Quality and Reasoning Agent.

    canonical DataFrame (+ Agent 2 mappings)
        -> DeterministicValidator.validate_sov()   detect, every row
        -> QualityAggregator                        report + scores
        -> RecommendationEngine + DecisionPolicy    grouped review queue
        -> (optional) LLM business-impact notes
        -> ReviewLedger                             human review state
        -> ReviewSession                            approve / reject /
                                                    edit / escalate,
                                                    re-reasoning
        -> ApprovedChange[]                         handed to Agent 4

Agent 3 detects, explains and recommends. It never modifies the
DataFrame; analyse() verifies that with a fingerprint.
"""

import hashlib
from typing import Any, Iterable, Optional

import pandas as pd
from pydantic import BaseModel, Field

from app.agents.data_quality.canonical_frame import build_canonical_frame
from app.agents.data_quality.quality_aggregator import (
    QualityAggregator,
    QualityReport,
)
from app.agents.data_quality.reasoner import Reasoner, RuleBasedReasoner
from app.agents.data_quality.recommendation_engine import (
    CandidateChecker,
    RecommendationEngine,
)
from app.agents.data_quality.recommendation_schema import (
    Recommendation,
    ReviewPolicy,
)
from app.agents.data_quality.reflection import ReviewLedger, ReviewSession
from app.agents.data_quality.validator import DeterministicValidator


def dataframe_fingerprint(dataframe: pd.DataFrame) -> str:
    """Hash of values, dtypes, index and columns, to prove no mutation."""

    hasher = hashlib.sha256()
    hasher.update(repr(list(dataframe.columns)).encode())
    hasher.update(repr(list(dataframe.dtypes.astype(str))).encode())
    hasher.update(repr(list(dataframe.index)).encode())

    for column in dataframe.columns:
        hasher.update(repr(dataframe[column].tolist()).encode())

    return hasher.hexdigest()


class Agent3Result(BaseModel):
    quality_report: QualityReport

    ledger: ReviewLedger

    dataframe_fingerprint: str

    current_year: Optional[int] = None

    source_rows: dict[int, int] = Field(default_factory=dict)

    @property
    def recommendations(self) -> list[Recommendation]:
        return self.ledger.current_recommendations()

    def summary(self) -> dict[str, Any]:
        report = self.quality_report
        recommendations = self.recommendations

        return {
            "intake_quality_score": report.intake_quality_score,
            "total_issues": report.total_issues,
            "issues_by_severity": report.issues_by_severity,
            "issues_by_type": report.issues_by_type,
            "recommendations": len(recommendations),
            "bulk_approvable": sum(
                1
                for rec in recommendations
                if rec.policy == ReviewPolicy.BULK_APPROVABLE
            ),
            "review": self.ledger.summary(),
        }


class DataQualityAgent:
    def __init__(
        self,
        validator: DeterministicValidator | None = None,
        aggregator: QualityAggregator | None = None,
        engine: RecommendationEngine | None = None,
        reasoner: Reasoner | None = None,
        max_reasoning_attempts: int = 2,
        explain_with_llm: bool = False,
        max_llm_explanations: int = 15,
    ) -> None:
        self.validator = validator or DeterministicValidator()
        self.aggregator = aggregator or QualityAggregator()
        self.engine = engine or RecommendationEngine()
        self.reasoner = reasoner
        self.max_reasoning_attempts = max_reasoning_attempts
        self.explain_with_llm = explain_with_llm
        self.max_llm_explanations = max_llm_explanations

    def analyse(
        self,
        dataframe: pd.DataFrame,
        mappings: Iterable[Any] | None = None,
        source_rows: dict[int, int] | None = None,
        source_columns: dict[str, str] | None = None,
        current_year: int | None = None,
        previous: Agent3Result | None = None,
        previous_ledger: ReviewLedger | None = None,
    ) -> Agent3Result:
        """
        Detect issues and build the review queue.

        previous: an earlier result for the same file; decisions on
        unchanged recommendations are carried over (e.g. after a
        column-mapping edit triggers re-analysis).
        """

        if not isinstance(dataframe, pd.DataFrame):
            raise TypeError("dataframe must be a pandas DataFrame")

        fingerprint = dataframe_fingerprint(dataframe)

        issues = self.validator.validate_sov(
            dataframe,
            current_year=current_year,
        )

        report = self.aggregator.aggregate(issues, dataframe=dataframe)

        recommendations = self.engine.build(
            issues=issues,
            dataframe=dataframe,
            mappings=mappings,
            source_rows=source_rows,
            source_columns=source_columns,
            current_year=current_year,
        )

        if self.explain_with_llm and self.reasoner is not None:
            recommendations = self._explain(recommendations)

        ledger = ReviewLedger.from_recommendations(
            recommendations,
            max_reasoning_attempts=self.max_reasoning_attempts,
        )

        if previous is not None:
            previous_ledger = previous.ledger

        if previous_ledger is not None:
            ledger = ledger.carry_over(previous_ledger)

        if dataframe_fingerprint(dataframe) != fingerprint:
            raise RuntimeError("Agent 3 must not modify the input DataFrame")

        return Agent3Result(
            quality_report=report,
            ledger=ledger,
            dataframe_fingerprint=fingerprint,
            current_year=current_year,
            source_rows=dict(source_rows or {}),
        )

    def review_session(
        self,
        result: Agent3Result,
        dataframe: pd.DataFrame,
    ) -> ReviewSession:
        """Open the human review gate for a result."""

        if dataframe_fingerprint(dataframe) != result.dataframe_fingerprint:
            raise ValueError(
                "The DataFrame differs from the one that was analysed; "
                "re-run analyse() first."
            )

        return ReviewSession(
            ledger=result.ledger,
            dataframe=dataframe,
            reasoner=self.reasoner,
            fallback_reasoner=RuleBasedReasoner(),
            checker=CandidateChecker(result.current_year),
            source_rows=result.source_rows,
            current_year=result.current_year,
        )

    def session_from_state(
        self,
        state: Any,
        current_year: int | None = None,
    ) -> ReviewSession:
        """Open the review gate on the ledger stored in SOVState."""

        if state.review_ledger is None or state.canonical_data is None:
            raise ValueError("Agent 3 has not run on this state.")

        if (
            state.agent3_fingerprint
            and dataframe_fingerprint(state.canonical_data)
            != state.agent3_fingerprint
        ):
            raise ValueError(
                "The analysed data changed; re-run Agent 3 first."
            )

        return ReviewSession(
            ledger=state.review_ledger,
            dataframe=state.canonical_data,
            reasoner=self.reasoner,
            fallback_reasoner=RuleBasedReasoner(),
            checker=CandidateChecker(current_year),
            source_rows=state.metadata.get("agent3_source_rows", {}),
            current_year=current_year,
        )

    def run(
        self,
        state: Any,
        current_year: int | None = None,
        previous_ledger: ReviewLedger | None = None,
    ) -> Any:
        """
        LangGraph-style node: read Agent 2 output from SOVState and
        write Agent 3 output back.

        Requires Agent 1's state.data_table (index = Excel row numbers)
        and Agent 2's state.schema_mappings. Errors are recorded on the
        state instead of raised (NFR-4).
        """

        try:
            source = state.data_table

            if source is None:
                raise ValueError(
                    "No data table: Agent 1 must run before Agent 3."
                )

            canonical = build_canonical_frame(
                source,
                state.schema_mappings,
                row_numbers=list(source.index),
            )

            result = self.analyse(
                canonical.dataframe,
                mappings=state.schema_mappings,
                source_rows=canonical.source_rows,
                source_columns=canonical.source_columns,
                current_year=current_year,
                previous_ledger=previous_ledger,
            )

        except Exception as error:
            state.errors.append(f"Agent 3 failed: {error}")
            return state

        state.canonical_data = canonical.dataframe
        state.source_columns = canonical.source_columns
        state.quality_report = result.quality_report
        state.review_ledger = result.ledger
        state.agent3_fingerprint = result.dataframe_fingerprint
        state.metadata["agent3_source_rows"] = canonical.source_rows
        state.agent_trace.append(
            {
                "agent": "data_quality",
                "status": "awaiting_review",
                "summary": result.summary(),
            }
        )

        return state

    def _explain(
        self,
        recommendations: list[Recommendation],
    ) -> list[Recommendation]:
        explained: list[Recommendation] = []
        budget = self.max_llm_explanations

        for rec in recommendations:
            if budget > 0 and rec.policy == ReviewPolicy.HUMAN_REVIEW_REQUIRED:
                budget -= 1

                try:
                    note = self.reasoner.explain(rec)
                except Exception:
                    note = None

                if note:
                    rec = rec.model_copy(update={"llm_explanation": note})

            explained.append(rec)

        return explained
