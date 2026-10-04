from typing import Optional

from app.agents.schema_mapping.batch_mapper import (
    BatchMappingResult,
    SourceColumnEvidence,
    assign_one_to_one,
)
from app.agents.schema_mapping.domain_aliases import (
    DOMAIN_ALIAS_LOOKUP,
)
from app.agents.schema_mapping.exact_matcher import (
    exact_match_header,
)
from app.agents.schema_mapping.field_evidence import (
    score_field_evidence,
)
from app.agents.schema_mapping.fuzzy_matcher import (
    fuzzy_match_header,
)
from app.agents.schema_mapping.llm_decision import (
    LLMMappingDecision,
)
from app.agents.schema_mapping.llm_prompt import (
    build_llm_decision_context,
)
from app.agents.schema_mapping.semantic_pipeline import (
    run_semantic_pipeline,
)
from app.agents.schema_mapping.decision_engine import (
    resolve_mapping,
)
from app.agents.schema_mapping.value_profiler import (
    profile_column,
)
from app.agents.schema_mapping.groq_client import (
    GroqLLMClient,
)
from app.agents.schema_mapping.target_schema import (
    TARGET_FIELDS,
)


class SchemaMappingInput:
    """
    Input contract for Agent 2.

    sample_values is optional so the Agent 2 API remains
    backward compatible with callers that only provide headers.
    """

    def __init__(
        self,
        source_headers: list[str],
        sample_values: Optional[dict[str, list[str]]] = None,
    ):
        self.source_headers = source_headers
        self.sample_values = sample_values or {}

class SchemaMappingAgentResult:
    """
    Final result returned by Agent 2.
    """

    def __init__(
        self,
        mappings,
        unresolved_columns,
        assigned_targets,
        warnings,
    ):
        self.mappings = mappings
        self.unresolved_columns = unresolved_columns
        self.assigned_targets = assigned_targets
        self.warnings = warnings


class SchemaMappingAgent:
    """
    Agent 2: Schema Intelligence.

    Coordinates:

    1. Exact deterministic matching
    2. Domain alias matching
    3. Fuzzy matching
    4. Statistical/value evidence
    5. Embedding retrieval
    6. Cross-encoder semantic reasoning
    7. LLM fallback
    8. Global one-to-one assignment
    """

    # ------------------------------------------------------------------
    # Score weights
    # ------------------------------------------------------------------

    EXACT_SCORE = 1.00

    DOMAIN_ALIAS_SCORE = 0.97

    FUZZY_SCORE_WEIGHT = 0.90

    VALUE_EVIDENCE_WEIGHT = 0.85

    SEMANTIC_WEIGHT = 0.75

    LLM_WEIGHT = 0.90
    VALUE_ONLY_MAX_SCORE = 0.49

    FUZZY_HEADER_WEIGHT = 0.80
    FUZZY_VALUE_WEIGHT = 0.20

    SEMANTIC_HEADER_WEIGHT = 0.80
    SEMANTIC_VALUE_WEIGHT = 0.20

    LLM_HEADER_WEIGHT = 0.80
    LLM_VALUE_WEIGHT = 0.20
    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def __init__(
        self,
        llm_client: Optional[GroqLLMClient] = None,
    ):
        self.llm_client = llm_client

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _target_names() -> list[str]:
        return [
            field.name
            for field in TARGET_FIELDS
        ]

    # ------------------------------------------------------------------
    # Value evidence
    # ------------------------------------------------------------------

    def _build_value_evidence(
        self,
        source_header: str,
        samples: list[str],
    ) -> list[dict]:

        if not samples:
            return []

        try:

            profile = profile_column(
                column_name=source_header,
                values=samples,
            )

            evidence_results = score_field_evidence(
                profile
            )

        except Exception:
            return []

        candidates = []

        for evidence in evidence_results:

            candidates.append(
                {
                    "target_field": evidence.target_field,
                    "score": float(evidence.score),
                    "value_evidence_score": float(
                        evidence.score
                    ),
                    "embedding_similarity": 0.0,
                    "fuzzy_score": 0.0,
                    "deterministic_score": 0.0,
                    "evidence_reasons": list(
                        evidence.reasons
                    ),
                }
            )

        return candidates

    # ------------------------------------------------------------------
    # Deterministic evidence
    # ------------------------------------------------------------------

    def _build_deterministic_evidence(
        self,
        source_header: str,
        assigned_fields: set[str],
    ) -> list[dict]:

        candidates = []

        # --------------------------------------------------------------
        # Exact canonical/approved alias matching
        # --------------------------------------------------------------

        exact_result = exact_match_header(
            source_header,
            assigned_fields=assigned_fields,
        )

        if exact_result.matched_field is not None:

            candidates.append(
                {
                    "target_field": (
                        exact_result.matched_field
                    ),
                    "score": self.EXACT_SCORE,
                    "value_evidence_score": 0.0,
                    "embedding_similarity": 0.0,
                    "fuzzy_score": 1.0,
                    "deterministic_score": 1.0,
                    "evidence_reasons": [
                        "Exact normalized header or approved alias match."
                    ],
                    "method": "exact",
                }
            )

        # --------------------------------------------------------------
        # Domain alias
        # --------------------------------------------------------------

        normalized = exact_result.normalized_header

        domain_target = DOMAIN_ALIAS_LOOKUP.get(
            normalized
        )

        if (
            domain_target is not None
            and domain_target not in assigned_fields
        ):

            candidates.append(
                {
                    "target_field": domain_target,
                    "score": self.DOMAIN_ALIAS_SCORE,
                    "value_evidence_score": 0.0,
                    "embedding_similarity": 0.0,
                    "fuzzy_score": 1.0,
                    "deterministic_score": 0.97,
                    "evidence_reasons": [
                        "Approved insurance-domain alias match."
                    ],
                    "method": "domain_alias",
                }
            )

        # --------------------------------------------------------------
        # Fuzzy matching
        # --------------------------------------------------------------

        fuzzy_result = fuzzy_match_header(
            source_header,
            assigned_fields=assigned_fields,
        )

        if fuzzy_result.matched_field is not None:

            fuzzy_score = float(
                fuzzy_result.confidence
            )

            candidates.append(
                {
                    "target_field": (
                        fuzzy_result.matched_field
                    ),
                    "score": (
                        fuzzy_score
                        * self.FUZZY_SCORE_WEIGHT
                    ),
                    "value_evidence_score": 0.0,
                    "embedding_similarity": 0.0,
                    "fuzzy_score": fuzzy_score,
                    "deterministic_score": fuzzy_score,
                    "evidence_reasons": [
                        (
                            "Fuzzy header match: "
                            f"{fuzzy_result.matched_text}"
                        )
                    ],
                    "method": "fuzzy",
                }
            )

        return candidates

    # ------------------------------------------------------------------
    # Merge candidates
    # ------------------------------------------------------------------

    @classmethod
    def _merge_candidates(
        cls,
        candidates: list[dict],
    ) -> list[dict]:
        """
        Merge evidence for the same target field.

        Evidence sources:
        - deterministic/exact/domain alias
        - fuzzy header similarity
        - semantic similarity
        - value-profile evidence
        - LLM reasoning

        Important:
        Value evidence alone must never create a strong automatic mapping.
        Header/semantic evidence must support the mapping.
        """

        merged: dict[str, dict] = {}

        # ================================================================
        # 1. MERGE CANDIDATES BY TARGET FIELD
        # ================================================================

        for candidate in candidates:

            target = candidate.get("target_field")

            if not target:
                continue

            if target not in merged:

                merged[target] = {
                    "target_field": target,

                    "score": 0.0,

                    "embedding_similarity": float(
                        candidate.get(
                            "embedding_similarity",
                            0.0,
                        )
                        or 0.0
                    ),

                    "value_evidence_score": float(
                        candidate.get(
                            "value_evidence_score",
                            0.0,
                        )
                        or 0.0
                    ),

                    "fuzzy_score": float(
                        candidate.get(
                            "fuzzy_score",
                            0.0,
                        )
                        or 0.0
                    ),

                    "deterministic_score": float(
                        candidate.get(
                            "deterministic_score",
                            0.0,
                        )
                        or 0.0
                    ),

                    "semantic_score": float(
                        candidate.get(
                            "semantic_score",
                            0.0,
                        )
                        or 0.0
                    ),

                    "llm_score": float(
                        candidate.get(
                            "llm_score",
                            0.0,
                        )
                        or 0.0
                    ),

                    "evidence_reasons": list(
                        candidate.get(
                            "evidence_reasons",
                            [],
                        )
                    ),

                    "method": candidate.get(
                        "method"
                    ),
                }

            else:

                existing = merged[target]

                # --------------------------------------------------------
                # Keep strongest evidence from each evidence family.
                # --------------------------------------------------------

                existing[
                    "embedding_similarity"
                ] = max(
                    existing[
                        "embedding_similarity"
                    ],
                    float(
                        candidate.get(
                            "embedding_similarity",
                            0.0,
                        )
                        or 0.0
                    ),
                )

                existing[
                    "value_evidence_score"
                ] = max(
                    existing[
                        "value_evidence_score"
                    ],
                    float(
                        candidate.get(
                            "value_evidence_score",
                            0.0,
                        )
                        or 0.0
                    ),
                )

                existing[
                    "fuzzy_score"
                ] = max(
                    existing[
                        "fuzzy_score"
                    ],
                    float(
                        candidate.get(
                            "fuzzy_score",
                            0.0,
                        )
                        or 0.0
                    ),
                )

                existing[
                    "deterministic_score"
                ] = max(
                    existing[
                        "deterministic_score"
                    ],
                    float(
                        candidate.get(
                            "deterministic_score",
                            0.0,
                        )
                        or 0.0
                    ),
                )

                existing[
                    "semantic_score"
                ] = max(
                    existing[
                        "semantic_score"
                    ],
                    float(
                        candidate.get(
                            "semantic_score",
                            0.0,
                        )
                        or 0.0
                    ),
                )

                existing[
                    "llm_score"
                ] = max(
                    existing[
                        "llm_score"
                    ],
                    float(
                        candidate.get(
                            "llm_score",
                            0.0,
                        )
                        or 0.0
                    ),
                )

                # --------------------------------------------------------
                # Merge explanations without duplicates.
                # --------------------------------------------------------

                for reason in candidate.get(
                    "evidence_reasons",
                    [],
                ):

                    if reason not in existing[
                        "evidence_reasons"
                    ]:

                        existing[
                            "evidence_reasons"
                        ].append(reason)

                # --------------------------------------------------------
                # Preserve strongest method.
                # --------------------------------------------------------

                method_priority = {
                    "exact": 6,
                    "domain_alias": 6,
                    "fuzzy": 5,
                    "llm": 4,
                    "semantic": 3,
                    "value_evidence": 1,
                    None: 0,
                }

                current_method = existing.get(
                    "method"
                )

                candidate_method = candidate.get(
                    "method"
                )

                if (
                    method_priority.get(
                        candidate_method,
                        0,
                    )
                    >
                    method_priority.get(
                        current_method,
                        0,
                    )
                ):
                    existing[
                        "method"
                    ] = candidate_method

        # ================================================================
        # 2. CALCULATE FINAL EVIDENCE-AWARE SCORE
        # ================================================================

        for candidate in merged.values():

            deterministic_score = max(
                0.0,
                min(
                    float(
                        candidate.get(
                            "deterministic_score",
                            0.0,
                        )
                    ),
                    1.0,
                ),
            )

            fuzzy_score = max(
                0.0,
                min(
                    float(
                        candidate.get(
                            "fuzzy_score",
                            0.0,
                        )
                    ),
                    1.0,
                ),
            )

            semantic_score = max(
                0.0,
                min(
                    float(
                        candidate.get(
                            "semantic_score",
                            0.0,
                        )
                    ),
                    1.0,
                ),
            )

            llm_score = max(
                0.0,
                min(
                    float(
                        candidate.get(
                            "llm_score",
                            0.0,
                        )
                    ),
                    1.0,
                ),
            )

            value_score = max(
                0.0,
                min(
                    float(
                        candidate.get(
                            "value_evidence_score",
                            0.0,
                        )
                    ),
                    1.0,
                ),
            )

            # ============================================================
            # CASE 1 — Exact / domain alias
            # ============================================================

            if deterministic_score >= 0.97:

                candidate["score"] = (
                    deterministic_score
                )

                continue

            # ============================================================
            # CASE 2 — Fuzzy header + value evidence
            # ============================================================

            if fuzzy_score >= 0.75:

                candidate["score"] = (
                    0.80 * fuzzy_score
                    +
                    0.20 * value_score
                )

                continue

            # ============================================================
            # CASE 3 — Semantic header + value evidence
            # ============================================================

            if semantic_score > 0.0:

                candidate["score"] = (
                    0.80 * semantic_score
                    +
                    0.20 * value_score
                )

                continue

            # ============================================================
            # CASE 4 — LLM + value evidence
            # ============================================================

            if llm_score > 0.0:

                candidate["score"] = (
                    0.80 * llm_score
                    +
                    0.20 * value_score
                )

                continue

            # ============================================================
            # CASE 5 — Value evidence only
            #
            # Never allow value evidence alone to produce an automatic
            # mapping. Cap it below the global assignment threshold.
            # ============================================================

            candidate["score"] = min(
                value_score * 0.45,
                0.49,
            )

            if candidate.get("method") is None:

                candidate["method"] = (
                    "value_evidence"
                )

        return list(
            merged.values()
        )
    def _build_column_evidence(
        self,
        source_header: str,
        samples: list[str],
    ) -> SourceColumnEvidence:

        candidates: list[dict] = []

        # --------------------------------------------------------------
        # 1. Deterministic evidence
        # --------------------------------------------------------------

        deterministic_candidates = (
            self._build_deterministic_evidence(
                source_header=source_header,
                assigned_fields=set(),
            )
        )

        candidates.extend(
            deterministic_candidates
        )

        # --------------------------------------------------------------
        # 2. Statistical/value evidence
        # --------------------------------------------------------------

        value_candidates = (
            self._build_value_evidence(
                source_header=source_header,
                samples=samples,
            )
        )

        for candidate in value_candidates:

            candidate["score"] = (
                float(
                    candidate[
                        "value_evidence_score"
                    ]
                )
                * self.VALUE_EVIDENCE_WEIGHT
            )

            candidates.append(candidate)

        # --------------------------------------------------------------
        # 3. Semantic pipeline
        # --------------------------------------------------------------

        pipeline = run_semantic_pipeline(
            source_header=source_header,
        )

        if pipeline.evaluation:

            for candidate in (
                pipeline.evaluation.candidates
            ):

                candidates.append(
                    {
                        "target_field": (
                            candidate.target_field
                        ),
                        "score": float(
                            candidate.combined_score
                        )
                        * self.SEMANTIC_WEIGHT,
                        "embedding_similarity": float(
                            candidate.embedding_similarity
                        ),
                        "value_evidence_score": float(
                            candidate.value_evidence_score
                        ),
                        "fuzzy_score": 0.0,
                        "deterministic_score": 0.0,
                        "evidence_reasons": list(
                            candidate.evidence_reasons
                        ),
                        "method": "semantic",
                    }
                )

        # --------------------------------------------------------------
        # 4. Merge duplicate target candidates
        # --------------------------------------------------------------

        candidates = self._merge_candidates(
            candidates
        )

        # --------------------------------------------------------------
        # 5. LLM fallback only when semantic pipeline requests it
        # --------------------------------------------------------------

        decision = resolve_mapping(
            pipeline,
            sample_values=samples,
            llm_client=self.llm_client,
        )

        if (
            decision.method == "llm"
            and decision.target_field is not None
            and decision.confidence is not None
        ):

            candidates.append(
                {
                    "target_field": (
                        decision.target_field
                    ),
                    "score": (
                        float(
                            decision.confidence
                        )
                        * self.LLM_WEIGHT
                    ),
                    "embedding_similarity": 0.0,
                    "value_evidence_score": 0.0,
                    "fuzzy_score": 0.0,
                    "deterministic_score": 0.0,
                    "evidence_reasons": [
                        decision.reason
                    ],
                    "method": "llm",
                }
            )

        candidates = self._merge_candidates(
            candidates
        )

        # --------------------------------------------------------------
        # 6. Keep only canonical targets
        # --------------------------------------------------------------

        valid_targets = set(
            self._target_names()
        )

        candidates = [
            candidate
            for candidate in candidates
            if candidate[
                "target_field"
            ] in valid_targets
        ]

        return SourceColumnEvidence(
            source_header=source_header,
            candidates=candidates,
        )

    # ------------------------------------------------------------------
    # Public Agent 2 API
    # ------------------------------------------------------------------

    def map(
        self,
        mapping_input: SchemaMappingInput,
    ) -> SchemaMappingAgentResult:
        """
        Run Agent 2 over all source columns.
        """

        column_evidence = []

        warnings = []

        for source_header in (
            mapping_input.source_headers
        ):

            samples = (
                mapping_input.sample_values.get(
                    source_header,
                    [],
                )
            )

            try:

                evidence = (
                    self._build_column_evidence(
                        source_header,
                        samples,
                    )
                )

                column_evidence.append(
                    evidence
                )

            except Exception as exc:

                warnings.append(
                    f"Failed to process "
                    f"'{source_header}': {exc}"
                )

                column_evidence.append(
                    SourceColumnEvidence(
                        source_header=source_header,
                        candidates=[],
                    )
                )

        assignment = assign_one_to_one(
            column_evidence
        )

        return SchemaMappingAgentResult(
            mappings=assignment.mappings,
            unresolved_columns=(
                assignment.unresolved_columns
            ),
            assigned_targets=(
                assignment.assigned_targets
            ),
            warnings=warnings,
        )