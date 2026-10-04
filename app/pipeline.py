"""
End-to-end SOV pipeline: ingestion -> Agent 1 -> Agent 2 -> Agent 3
-> human review -> Agent 4.

All agents share one SOVState (NFR-7). Every stage records failures on
the state instead of raising, and the pipeline stops at the first stage
that fails (NFR-4). Agent 4 runs only when every recommendation has a
human decision (C-01, FR-5).
"""

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional

import pandas as pd

from app.agents.data_quality.agent import DataQualityAgent
from app.agents.data_quality.recommendation_schema import (
    ReviewAction,
    ReviewDecision,
)
from app.agents.data_quality.reflection import ReviewError
from app.agents.schema_mapping.agent import SchemaMappingAgent
from app.agents.schema_mapping.mapping_memory import MappingMemory
from app.agents.sheet_discovery.agent import SheetDiscoveryAgent
from app.agents.transformation.agent import (
    ExportBlockedError,
    TransformationAgent,
)
from app.ingestion.file_validator import FileValidationError
from app.ingestion.loader import load_sov_file
from app.state.sov_state import SOVState


ApproveMode = Literal["none", "bulk", "all"]


@dataclass
class PipelineResult:
    state: Optional[SOVState]
    ok: bool
    stage_reached: str
    timings: dict[str, float] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)
    export: Optional[dict[str, Any]] = None
    errors: list[str] = field(default_factory=list)


def readable_read_error(error: Exception) -> str:
    """Translate library errors into a message a reviewer can act on."""

    text = str(error)
    lowered = text.lower()

    if "format cannot be determined" in lowered or "not a zip file" in lowered or "bad zip" in lowered:
        return (
            "The file is not a valid Excel workbook. It may be corrupt, "
            "password-protected or saved in another format; re-save it as "
            ".xlsx and upload again."
        )

    if "no columns to parse" in lowered:
        return "The CSV file is empty."

    if "xlrd" in lowered:
        return "Reading .xls files needs the 'xlrd' package; save the file as .xlsx."

    if "codec" in lowered or "decode" in lowered:
        return "The CSV file's text encoding could not be read; save it as UTF-8."

    return f"The file could not be read: {text}"


def llm_available() -> bool:
    from app.llm_pool import configured_keys

    return bool(configured_keys())


def prefer_offline_models() -> None:
    """
    Use cached Hugging Face models without contacting the Hub on every
    load. Falls back to online mode when a model is not cached.
    """

    if os.getenv("HF_HUB_OFFLINE") is not None:
        return

    try:
        from huggingface_hub import try_to_load_from_cache

        from app.agents.schema_mapping.cross_encoder_reranker import (
            DEFAULT_CROSS_ENCODER_MODEL,
        )
        from app.agents.schema_mapping.embedding_retriever import (
            DEFAULT_MODEL_NAME,
        )

        cached = all(
            isinstance(
                try_to_load_from_cache(model, "config.json"),
                str,
            )
            for model in (DEFAULT_MODEL_NAME, DEFAULT_CROSS_ENCODER_MODEL)
        )
    except Exception:
        cached = False

    if cached:
        os.environ["HF_HUB_OFFLINE"] = "1"


def build_agents(
    use_llm: bool,
    memory=None,
) -> tuple[SchemaMappingAgent, DataQualityAgent]:
    mapping_client = None
    reasoner = None

    if use_llm:
        from app.agents.data_quality.reasoner import GroqReasoner
        from app.agents.schema_mapping.groq_client import GroqLLMClient

        mapping_client = GroqLLMClient()
        reasoner = GroqReasoner()

    # With the LLM on, Agent 3 also adds batched business-impact notes
    # (FR-4: LLM-powered reasoning); values are always deterministic.
    return SchemaMappingAgent(
        llm_client=mapping_client, memory=memory
    ), DataQualityAgent(reasoner=reasoner, explain_with_llm=use_llm)


class PipelineRun:
    """
    One SOV file moving through the agents. The CLI and the web UI both
    drive this object, so they share exactly the same behaviour.

        run = PipelineRun(path, output_dir)
        run.analyse()                 # ingestion -> Agents 1, 2, 3
        run.submit(ReviewAction(...)) # human review (repeat)
        run.revalidate_if_needed()    # after mapping edits (NFR-7)
        run.preview()                 # cleaned data so far (no file)
        run.export()                  # Agent 4, only when nothing pending
    """

    def __init__(
        self,
        file_path: str,
        output_dir: str | Path = "output",
        use_llm: Optional[bool] = None,
        current_year: Optional[int] = None,
        memory_path: Optional[str | Path] = None,
        use_memory: bool = True,
    ) -> None:
        self.file_path = file_path
        self.output_dir = Path(output_dir)
        self.use_llm = llm_available() if use_llm is None else use_llm
        self.current_year = current_year
        self.state: Optional[SOVState] = None
        self.session = None
        self.timings: dict[str, float] = {}
        self.artifacts: dict[str, str] = {}
        self.errors: list[str] = []
        self.stage_reached = "not_started"
        self.export_result = None
        self.memory = MappingMemory(memory_path) if use_memory else None
        self.mapping_agent, self.quality_agent = build_agents(
            self.use_llm, self.memory
        )

    # -----------------------------------------------------------------

    def analyse(self) -> bool:
        """Ingestion and Agents 1-3. Returns False on a stage error."""

        prefer_offline_models()
        started = time.perf_counter()

        try:
            state = load_sov_file(self.file_path)
        except FileValidationError as error:
            return self._fail("ingestion", str(error))
        except Exception as error:
            return self._fail("ingestion", readable_read_error(error))

        self.timings["ingestion"] = time.perf_counter() - started
        state.metadata["llm_enabled"] = self.use_llm

        stages = [
            ("sheet_discovery", lambda s: SheetDiscoveryAgent().run(s)),
            ("schema_mapping", lambda s: self.mapping_agent.run(s)),
            (
                "data_quality",
                lambda s: self.quality_agent.run(s, self.current_year),
            ),
        ]

        for name, stage in stages:
            started = time.perf_counter()
            errors_before = len(state.errors)
            state = stage(state)
            self.timings[name] = time.perf_counter() - started
            self.state = state

            if len(state.errors) > errors_before:
                return self._fail(name, *state.errors[errors_before:])

        self.session = self.quality_agent.session_from_state(
            state, self.current_year
        )
        self.stage_reached = "human_review"
        self.artifacts.update(
            _write_intermediate_artifacts(state, self.output_dir)
        )
        self.save_review_queue()
        return True

    # -----------------------------------------------------------------
    # Review
    # -----------------------------------------------------------------

    def submit(self, action: ReviewAction):
        rec = self.session.submit(action)
        self.state.review_ledger = self.session.ledger
        return rec

    def approve_mode(self, approve: ApproveMode, reviewer: str) -> None:
        _apply_approve_mode(self.session, approve, reviewer)
        self.state.review_ledger = self.session.ledger

    def apply_decisions_file(self, path: str, reviewer: str) -> list[str]:
        errors = _apply_decisions_file(self.session, path, reviewer)
        self.state.review_ledger = self.session.ledger
        self.state.warnings.extend(errors)
        return errors

    def mappings_changed(self) -> bool:
        effective = effective_mappings(
            self.state.schema_mappings, self.session.ledger
        )
        return _mapping_targets(effective) != _mapping_targets(
            self.state.schema_mappings
        )

    def revalidate_if_needed(self) -> bool:
        """
        A reviewer who changed a column mapping changed Agent 3's
        input. Re-validate (NFR-7), carrying over decisions on unchanged
        items. Returns True when a re-run happened.
        """

        if not self.mappings_changed():
            return False

        self.state.schema_mappings = effective_mappings(
            self.state.schema_mappings, self.session.ledger
        )
        errors_before = len(self.state.errors)
        self.state = self.quality_agent.run(
            self.state,
            self.current_year,
            previous_ledger=self.session.ledger,
        )

        if len(self.state.errors) > errors_before:
            self._fail("data_quality", *self.state.errors[errors_before:])
            return True

        self.session = self.quality_agent.session_from_state(
            self.state, self.current_year
        )
        self.artifacts.update(
            _write_intermediate_artifacts(self.state, self.output_dir)
        )
        self.save_review_queue()
        return True

    def save_review_queue(self) -> None:
        self.artifacts["review_queue"] = _write_json(
            self.output_dir / "review_queue.json",
            _review_queue(self.state),
        )

    @property
    def export_ready(self) -> bool:
        return self.session is not None and self.session.ledger.export_ready

    # -----------------------------------------------------------------
    # Agent 4
    # -----------------------------------------------------------------

    def preview(self) -> pd.DataFrame:
        """Cleaned data with the decisions made so far (nothing written)."""

        output, _, _ = TransformationAgent().transform(
            self.state.data_table,
            self.state.schema_mappings,
            self.session.approved_changes(),
            self.session.ledger,
            require_complete=False,
        )
        return output

    def export(self):
        started = time.perf_counter()

        try:
            result = TransformationAgent().export(
                data_table=self.state.data_table,
                mappings=self.state.schema_mappings,
                changes=self.session.approved_changes(),
                ledger=self.session.ledger,
                output_dir=self.output_dir,
                context=self.summary_context(),
            )
        except (ExportBlockedError, ReviewError, ValueError) as error:
            self._fail("transformation", f"Agent 4 failed: {error}")
            return None

        self.timings["transformation"] = time.perf_counter() - started
        self.export_result = result
        self.remember_mappings()
        self.stage_reached = "transformation"
        self.artifacts["cleaned_sov"] = result.output_path
        self.artifacts["audit_log"] = result.audit_json_path
        self.artifacts["audit_log_xlsx"] = result.audit_xlsx_path
        self.artifacts["processing_summary"] = result.summary_path
        self.state.agent_trace.append(
            {
                "agent": "transformation",
                "status": "completed",
                "summary": result.model_dump(),
            }
        )
        self.artifacts["agent_trace"] = _write_json(
            self.output_dir / "agent_trace.json", self.state.agent_trace
        )
        self.save_review_queue()
        self.errors.extend(
            f"Schema problem: {problem}" for problem in result.schema_problems
        )
        return result

    def summary_context(self) -> dict[str, Any]:
        state = self.state
        mapping = state.metadata.get("schema_mapping_json", {})
        report = state.quality_report

        return {
            "source_file": Path(self.file_path).name,
            "selected_sheet": state.selected_sheet,
            "header_row": state.header_row + 1 if state.header_row is not None else None,
            "llm_enabled": self.use_llm,
            "mapping": {
                "mapped": sum(1 for m in mapping.get("mappings", {}).values() if m["target"]),
                "unresolved": mapping.get("unresolved_count"),
                "overall_confidence": mapping.get("overall_confidence"),
            },
            "quality": {
                "intake_quality_score": report.intake_quality_score,
                "total_issues": report.total_issues,
                "issues_by_severity": report.issues_by_severity,
            },
            "excluded_rows": len(state.metadata.get("excluded_rows", [])),
            "timings": dict(self.timings),
        }

    def remember_mappings(self) -> int:
        """
        Store the reviewed column mappings in vector memory (headers
        only, never row values). Returns the number of decisions saved.
        """

        if self.memory is None:
            return 0

        from app.agents.data_quality.recommendation_schema import (
            ReasoningSource,
        )
        from app.agents.data_quality.reflection import DONE_STATUSES

        saved = 0

        for item in self.session.ledger.items.values():
            rec = item.current

            if rec.rule_id not in {"schema_mapping", "column_unmapped"}:
                continue

            if rec.status not in DONE_STATUSES or not item.actions:
                continue

            final = rec.target_field if rec.operation.value == "rename_column" else None

            # Proposals the reviewer rejected or replaced are negative
            # evidence for that header.
            for version in item.history:
                if version.target_field and version.target_field != final:
                    self.memory.remember(rec.source_column, version.target_field, approved=False)
                    saved += 1

            if final:
                self.memory.remember(rec.source_column, final, approved=True)
                saved += 1

        self.memory.save()
        return saved

    def _fail(self, stage: str, *messages: str) -> bool:
        self.stage_reached = stage
        self.errors.extend(messages)

        if self.state is not None:
            for message in messages:
                if message not in self.state.errors:
                    self.state.errors.append(message)

        return False


def run_pipeline(
    file_path: str,
    output_dir: str | Path = "output",
    use_llm: Optional[bool] = None,
    approve: ApproveMode = "none",
    reviewer: str = "cli-reviewer",
    decisions_file: Optional[str] = None,
    current_year: Optional[int] = None,
    use_memory: bool = True,
) -> PipelineResult:
    run = PipelineRun(
        file_path, output_dir, use_llm, current_year, use_memory=use_memory
    )

    if not run.analyse():
        return run_result(run, ok=False)

    started = time.perf_counter()

    if decisions_file:
        run.apply_decisions_file(decisions_file, reviewer)

    run.approve_mode(approve, reviewer)

    if run.revalidate_if_needed():
        if run.errors:
            return run_result(run, ok=False)

        run.approve_mode(approve, reviewer)

    run.timings["review"] = time.perf_counter() - started
    run.save_review_queue()

    if not run.export_ready:
        pending = len(run.session.ledger.pending())
        run.state.agent_trace.append(
            {
                "agent": "human_review",
                "status": "awaiting_review",
                "summary": {"pending": pending},
            }
        )
        run.errors.append(
            f"Export blocked: {pending} recommendation(s) await a "
            "review decision (see review_queue.json)."
        )
        return run_result(run, ok=True)

    result = run.export()

    if result is None:
        return run_result(run, ok=False)

    return run_result(run, ok=result.schema_valid)


def run_result(run: PipelineRun, ok: bool) -> PipelineResult:
    return PipelineResult(
        state=run.state,
        ok=ok,
        stage_reached=run.stage_reached,
        timings=run.timings,
        artifacts=run.artifacts,
        export=run.export_result.model_dump() if run.export_result else None,
        errors=list(run.errors),
    )


def _apply_approve_mode(session, approve: str, reviewer: str) -> None:
    if approve in {"bulk", "all"}:
        session.approve_all_bulk(reviewer)

    if approve == "all":
        for rec in list(session.ledger.pending()):
            session.submit(
                ReviewAction(
                    recommendation_id=rec.recommendation_id,
                    decision=ReviewDecision.APPROVE,
                    reviewer=reviewer,
                    reason="Approved via --approve all.",
                )
            )


def effective_mappings(mappings: list[dict], ledger) -> list[dict]:
    """
    Agent 2 mappings with the reviewer's mapping edits applied.
    Undecided mappings keep Agent 2's proposal.
    """

    from app.agents.data_quality.normalizers import Operation
    from app.agents.data_quality.recommendation_schema import ReasoningSource

    decided: dict[str, Any] = {}

    for item in ledger.items.values():
        rec = item.current

        if rec.rule_id not in {"schema_mapping", "column_unmapped"}:
            continue

        if rec.reasoning_source == ReasoningSource.DETERMINISTIC and rec.attempt == 1:
            continue

        decided[rec.source_column] = (
            rec.target_field if rec.operation == Operation.RENAME_COLUMN else None
        )

    result = []

    for mapping in mappings:
        source = mapping["source_header"]

        if source in decided and decided[source] != mapping["target_field"]:
            mapping = {
                **mapping,
                "target_field": decided[source],
                "score": 1.0 if decided[source] else 0.0,
                "method": "human",
                "reason": "Set during human review.",
            }

        result.append(mapping)

    return result


def _mapping_targets(mappings: list[dict]) -> dict[str, Any]:
    return {m["source_header"]: m["target_field"] for m in mappings}


def _apply_decisions_file(session, path: str, reviewer: str) -> list[str]:
    """
    Apply decisions from JSON: a list of
    {"recommendation_id", "decision", "reason"?, "edited_value"?, "reviewer"?}
    """

    errors: list[str] = []

    try:
        decisions = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as error:
        return [f"Could not read decisions file: {error}"]

    for decision in decisions:
        try:
            payload = {"reviewer": reviewer, **decision}
            session.submit(ReviewAction(**payload))
        except Exception as error:
            errors.append(
                f"Decision for {decision.get('recommendation_id')} not "
                f"applied: {error}"
            )

    return errors


def _review_queue(state: SOVState) -> list[dict[str, Any]]:
    queue = []

    for item in state.review_ledger.items.values():
        rec = item.current
        queue.append(
            {
                "recommendation_id": rec.recommendation_id,
                "status": rec.status.value,
                "policy": rec.policy.value,
                "severity": rec.severity.value,
                "action_type": rec.action_type.value,
                "title": rec.title,
                "rationale": rec.rationale,
                "uncertainty": rec.uncertainty,
                "llm_explanation": rec.llm_explanation,
                "fix_confidence": rec.fix_confidence,
                "source_column": rec.source_column,
                "target_field": rec.target_field,
                "affected_row_count": rec.affected_row_count,
                "samples": [
                    sample.model_dump() for sample in rec.samples
                ],
                "attempt": rec.attempt,
            }
        )

    return queue


def _write_intermediate_artifacts(state: SOVState, output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)

    return {
        "sheet_manifest": _write_json(
            output_dir / "sheet_manifest.json", state.sheet_manifest
        ),
        "schema_mapping": _write_json(
            output_dir / "schema_mapping.json",
            state.metadata.get("schema_mapping_json", {}),
        ),
        "quality_report": _write_json(
            output_dir / "quality_report.json",
            state.quality_report.model_dump(
                mode="json", exclude={"issues"}
            ),
        ),
    }


def _write_json(path: Path, data: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return str(path)
