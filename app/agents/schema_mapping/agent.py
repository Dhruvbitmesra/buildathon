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
from app.agents.schema_mapping.header_normalizer import (
    normalize_header,
)
from app.agents.schema_mapping.keyword_evidence import (
    keyword_match,
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

    KEYWORD_SCORE = 0.85

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
        memory=None,
    ):
        self.llm_client = llm_client
        # Optional MappingMemory of reviewer-confirmed mappings.
        self.memory = memory
        self._llm_warnings: list[str] = []
        self._pipelines: dict = {}
        self._prefetched_decisions: dict = {}
        self._batch_prefetched = False
        self._llm_failures: list = []

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
    # Value plausibility veto
    # ------------------------------------------------------------------

    MONETARY_TARGETS = {"Building Value", "Contents", "BI", "Other"}
    COUNT_TARGETS = {"Storeys", "Number of Buildings"}
    TEXT_TARGETS = {
        "Address",
        "City",
        "State",
        "County",
        "Country",
        "Occupancy",
        "Construction",
    }

    @classmethod
    def _values_contradict(
        cls,
        target_field: str,
        samples: list[str],
    ) -> bool:
        """
        True when the column's values rule out the target, whatever
        the header says. Examples:

            "Buildings" = 22,756,726 -> not Number of Buildings
            "Primary Occupancy & %" = 1.0 -> not Occupancy (text)
            "Building" = "Animal Control Center" -> not Building Value

        Needs at least 3 sample values; otherwise no veto.
        """

        values = [str(v).strip() for v in samples if str(v).strip()]

        if len(values) < 3:
            return False

        numbers: list[float] = []

        for value in values:
            text = value.replace(",", "").replace("$", "").rstrip("%")

            try:
                numbers.append(float(text))
            except ValueError:
                continue

        numeric_share = len(numbers) / len(values)

        if target_field in cls.MONETARY_TARGETS:
            if numeric_share < 0.5:
                return True
            # Small sequence numbers (1, 2, 3 ...) are identifiers or
            # counts, not insured values.
            return bool(numbers) and max(numbers) < 100

        if target_field in cls.TEXT_TARGETS:
            return numeric_share >= 0.8

        if target_field in cls.COUNT_TARGETS:
            # Text identifiers ("hou-1") can never be a count.
            if numeric_share < 0.5:
                return True
            ordered = sorted(numbers)
            return ordered[len(ordered) // 2] > 500

        if target_field == "Year Built":
            if numeric_share < 0.8:
                return False
            # 0 / 9999 mean "unknown year": a data-quality issue for
            # Agent 3, not evidence against the mapping.
            real = [n for n in numbers if n not in {0, 9998, 9999, 99999}]

            if not real:
                return False

            plausible = sum(1 for n in real if 1600 <= n <= 2100)
            return plausible / len(real) < 0.5

        return False

    # Headers whose meaning depends on the values they hold.
    AMBIGUOUS_HEADERS = {
        "building": {"monetary": "Building Value", "count": "Number of Buildings"},
        "buildings": {"monetary": "Building Value", "count": "Number of Buildings"},
    }

    @classmethod
    def _disambiguate_by_values(
        cls,
        normalized_header: str,
        samples: list[str],
    ) -> Optional[dict]:
        options = cls.AMBIGUOUS_HEADERS.get(normalized_header)
        values = [str(v).strip() for v in samples if str(v).strip()]

        if not options or len(values) < 3:
            return None

        numbers: list[float] = []

        for value in values:
            try:
                numbers.append(float(value.replace(",", "").replace("$", "")))
            except ValueError:
                continue

        # Text values (e.g. building names) resolve to nothing.
        if len(numbers) / len(values) < 0.8:
            return None

        if max(numbers) >= 1000:
            kind = "monetary"
        elif max(numbers) < 100 and all(n.is_integer() for n in numbers):
            kind = "count"
        else:
            return None

        target = options[kind]

        return {
            "target_field": target,
            "score": 0.97,
            "value_evidence_score": 1.0,
            "embedding_similarity": 0.0,
            "fuzzy_score": 0.0,
            # Header and values agree; treated like an approved alias.
            "deterministic_score": 0.97,
            "evidence_reasons": [
                f"Ambiguous header '{normalized_header}' resolved "
                f"to {target} because its values are {kind}."
            ],
            "method": "value_disambiguation",
        }

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

        # --------------------------------------------------------------
        # Memory of reviewer-confirmed mappings from earlier files
        # --------------------------------------------------------------

        remembered = self.memory.recall(source_header) if self.memory else None

        if (
            remembered is not None
            and remembered["target"] not in assigned_fields
        ):
            exact = remembered["exact"]
            strength = (
                self.DOMAIN_ALIAS_SCORE
                if exact
                else round(0.9 * remembered["similarity"], 4)
            )
            candidates.append(
                {
                    "target_field": remembered["target"],
                    "score": strength,
                    "value_evidence_score": 0.0,
                    "embedding_similarity": remembered["similarity"],
                    "fuzzy_score": strength,
                    "deterministic_score": strength,
                    "evidence_reasons": [
                        "A reviewer confirmed "
                        f"'{remembered['matched_header']}' -> "
                        f"{remembered['target']} in an earlier file"
                        + ("" if exact else f" (similarity {remembered['similarity']:.2f})")
                        + "."
                    ],
                    "method": "memory",
                }
            )

        # --------------------------------------------------------------
        # Concept keywords ("Bldg TIV", "Yr Blt", "Premises Address")
        # --------------------------------------------------------------

        keyword = keyword_match(source_header)

        if keyword is not None and keyword[0] not in assigned_fields:
            target, reason = keyword
            candidates.append(
                {
                    "target_field": target,
                    "score": self.KEYWORD_SCORE,
                    "value_evidence_score": 0.0,
                    "embedding_similarity": 0.0,
                    # Scored like a fuzzy lexical match (0.8 header +
                    # 0.2 value evidence), below exact/alias matches.
                    "fuzzy_score": self.KEYWORD_SCORE,
                    "deterministic_score": self.KEYWORD_SCORE,
                    "evidence_reasons": [
                        f"Header contains the concept words for {target} "
                        f"({reason})."
                    ],
                    "method": "keyword",
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
                    "keyword": 5,
                    "memory": 5,
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
            # CASE 3 — Semantic or LLM header evidence + value evidence
            #
            # Use the stronger of the two. Checking semantic first meant
            # a weak semantic score (e.g. 0.19) silently overrode a
            # confident LLM decision (e.g. 0.72).
            # ============================================================

            header_score = max(semantic_score, llm_score)

            if header_score > 0.0:

                candidate["score"] = (
                    0.80 * header_score
                    +
                    0.20 * value_score
                )

                if llm_score > semantic_score:
                    candidate["method"] = "llm"

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

        pipeline = self._pipelines.get(source_header) or run_semantic_pipeline(
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
                        # Without this key the merge step scored every
                        # semantic match as value-only evidence (capped
                        # at 0.45), so semantic matches could never win.
                        "semantic_score": float(
                            candidate.combined_score
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

        # An LLM failure (network, malformed output) must not discard
        # the deterministic and semantic evidence gathered above.
        try:
            if source_header in self._prefetched_decisions:
                prefetched = self._prefetched_decisions[source_header]

                if isinstance(prefetched, Exception):
                    raise prefetched

                decision = prefetched
            elif self._batch_prefetched:
                # The batch already covered every column that needed
                # the LLM; never fall back to one call per column.
                decision = None
            else:
                decision = resolve_mapping(
                    pipeline,
                    sample_values=samples,
                    llm_client=(
                        None
                        if self._has_strong_header_match(source_header)
                        else self.llm_client
                    ),
                )
        except Exception as exc:
            self._llm_failures.append((source_header, exc))
            decision = None

        if (
            decision is not None
            and decision.method == "llm"
            and decision.target_field is not None
            and decision.confidence is not None
        ):

            candidates.append(
                {
                    "target_field": (
                        decision.target_field
                    ),
                    "llm_score": (
                        float(
                            decision.confidence
                        )
                        * self.LLM_WEIGHT
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

        # Targets a reviewer rejected for this header in earlier files.
        blocked = (
            self.memory.blocked_targets(source_header)
            if self.memory
            else set()
        )

        candidates = [
            candidate
            for candidate in candidates
            if candidate[
                "target_field"
            ] in valid_targets
            and not self._values_contradict(
                candidate["target_field"],
                samples,
            )
            and candidate["target_field"] not in blocked
        ]

        disambiguated = self._disambiguate_by_values(
            normalize_header(source_header),
            samples,
        )

        if disambiguated is not None:
            candidates = [
                candidate
                for candidate in candidates
                if candidate["target_field"] != disambiguated["target_field"]
            ] + [disambiguated]

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

        self._llm_warnings = warnings
        self._llm_failures = []
        self._prefetch_llm_decisions(mapping_input)

        try:
            result = self._map_columns(mapping_input, column_evidence, warnings)
        finally:
            self._pipelines = {}
            self._prefetched_decisions = {}
            self._batch_prefetched = False

        if self._llm_failures:
            warnings.append(summarise_llm_failures(self._llm_failures))

        return result

    def _has_strong_header_match(self, source_header: str) -> bool:
        """Exact, alias or fuzzy evidence already decides the column."""

        return any(
            candidate.get("deterministic_score", 0.0) >= 0.75
            for candidate in self._build_deterministic_evidence(
                source_header=source_header,
                assigned_fields=set(),
            )
        )

    def _prefetch_llm_decisions(
        self,
        mapping_input: SchemaMappingInput,
        max_workers: int = 3,
    ) -> None:
        """
        Run the semantic pipeline for every column, then send the
        columns that need the LLM to it concurrently. LLM calls are
        network-bound; issuing them one by one dominated Agent 2's
        run time.
        """

        self._pipelines = {}
        self._prefetched_decisions = {}

        for source_header in mapping_input.source_headers:
            try:
                self._pipelines[source_header] = run_semantic_pipeline(
                    source_header=source_header,
                )
            except Exception:
                continue

        if self.llm_client is None:
            return

        from concurrent.futures import ThreadPoolExecutor

        from app.agents.schema_mapping.decision_engine import (
            _semantic_decision,
        )

        needs_llm = [
            header
            for header, pipeline in self._pipelines.items()
            if _semantic_decision(pipeline) is None
            and not self._has_strong_header_match(header)
        ]

        if not needs_llm:
            return

        if hasattr(self.llm_client, "decide_batch"):
            self._prefetch_in_batches(needs_llm, mapping_input, max_workers)
            return

        executor = ThreadPoolExecutor(max_workers=max_workers)
        futures = {
            header: executor.submit(
                resolve_mapping,
                self._pipelines[header],
                mapping_input.sample_values.get(header, []),
                self.llm_client,
            )
            for header in needs_llm
        }
        executor.shutdown(wait=True)

        for header, future in futures.items():
            try:
                self._prefetched_decisions[header] = future.result()
            except Exception as error:
                self._prefetched_decisions[header] = error

    def _prefetch_in_batches(
        self,
        headers: list[str],
        mapping_input: SchemaMappingInput,
        max_workers: int,
    ) -> None:
        """
        One LLM request per batch of columns (see
        GroqLLMClient.decide_batch); the shared token limiter paces
        the requests so the free-tier budget is not exceeded.
        """

        from concurrent.futures import ThreadPoolExecutor

        from app.agents.schema_mapping.decision_engine import (
            decision_from_llm,
        )
        from app.agents.schema_mapping.llm_prompt import (
            build_llm_decision_context,
        )

        size = getattr(self.llm_client, "BATCH_SIZE", 8)
        batches = [headers[i:i + size] for i in range(0, len(headers), size)]
        contexts = {
            header: build_llm_decision_context(
                self._pipelines[header],
                sample_values=mapping_input.sample_values.get(header, []),
            )
            for header in headers
        }

        def run_batch(batch: list[str]) -> dict:
            return self.llm_client.decide_batch([contexts[h] for h in batch])

        with ThreadPoolExecutor(max_workers=max(1, min(max_workers, 2))) as executor:
            results = list(zip(batches, executor.map(_safe(run_batch), batches)))

        for batch, outcome in results:
            for header in batch:
                if isinstance(outcome, Exception):
                    self._prefetched_decisions[header] = outcome
                elif header in outcome:
                    self._prefetched_decisions[header] = decision_from_llm(
                        self._pipelines[header], outcome[header]
                    )

        self._batch_prefetched = True

    def _map_columns(
        self,
        mapping_input: SchemaMappingInput,
        column_evidence: list,
        warnings: list[str],
    ) -> SchemaMappingAgentResult:

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
    # ------------------------------------------------------------------
    # Pipeline integration
    # ------------------------------------------------------------------

    def run(self, state, sample_size: int = 20):
        """
        LangGraph-style node: map Agent 1's data table headers and
        write the mappings to state.schema_mappings. Errors are
        recorded on the state (NFR-4).
        """

        try:
            table = state.data_table

            if table is None:
                raise ValueError(
                    "No data table: Agent 1 must run before Agent 2."
                )

            headers = [str(column) for column in table.columns]
            samples = {
                header: (
                    table[column]
                    .dropna()
                    .astype(str)
                    .head(sample_size)
                    .tolist()
                )
                for header, column in zip(headers, table.columns)
            }

            result = self.map(
                SchemaMappingInput(
                    source_headers=headers,
                    sample_values=samples,
                )
            )

        except Exception as exc:
            state.errors.append(f"Agent 2 failed: {exc}")
            return state

        state.schema_mappings = [
            {
                "source_header": mapping.source_header,
                "target_field": mapping.target_field,
                "score": round(float(mapping.score), 4),
                "method": mapping.method,
                "reason": mapping.reason,
                "human_review_required": bool(
                    mapping.human_review_required
                    or mapping.target_field is None
                    or mapping.score < 0.50
                ),
            }
            for mapping in result.mappings
        ]
        state.warnings.extend(result.warnings)
        state.metadata["schema_mapping_json"] = build_mapping_json(
            state.schema_mappings,
            sheet=state.selected_sheet,
            header_row=state.header_row,
        )
        state.agent_trace.append(
            {
                "agent": "schema_mapping",
                "status": "completed",
                "summary": {
                    "mapped": len(result.assigned_targets),
                    "unresolved": len(result.unresolved_columns),
                    "overall_confidence": state.metadata[
                        "schema_mapping_json"
                    ]["overall_confidence"],
                },
            }
        )

        return state


def build_mapping_json(
    mappings: list[dict],
    sheet: Optional[str],
    header_row: Optional[int],
) -> dict:
    """
    Agent 2 output in the problem statement's mapping format
    (Section 09).
    """

    entries = {}

    for mapping in mappings:
        entry = {
            "target": mapping["target_field"],
            "confidence": mapping["score"],
            "method": (
                mapping["method"]
                if mapping["target_field"] is not None
                else "none"
            ),
        }

        if mapping["target_field"] is None or mapping["score"] < 0.50:
            entry["flag"] = "human_review_required"

        entries[mapping["source_header"]] = entry

    mapped_scores = [
        mapping["score"]
        for mapping in mappings
        if mapping["target_field"] is not None
    ]

    return {
        "sheet_identified": sheet,
        # 1-based, as a spreadsheet user sees it.
        "header_row": header_row + 1 if header_row is not None else None,
        "mappings": entries,
        "unresolved_count": sum(
            1 for mapping in mappings if mapping["target_field"] is None
        ),
        "overall_confidence": (
            round(sum(mapped_scores) / len(mapped_scores), 4)
            if mapped_scores
            else 0.0
        ),
    }


def _safe(function):
    """Return exceptions instead of raising (for executor.map)."""

    def wrapper(*args):
        try:
            return function(*args)
        except Exception as error:
            return error

    return wrapper


def summarise_llm_failures(failures: list) -> str:
    """One readable warning instead of one per column."""

    from app.llm_rate_limiter import LLMUnavailableError

    headers = [header for header, _ in failures]
    unavailable = next(
        (error for _, error in failures if isinstance(error, LLMUnavailableError)),
        None,
    )
    rate_limited = any(
        "429" in str(error) or "rate limit" in str(error).lower()
        for _, error in failures
    )

    if unavailable is not None:
        reason = str(unavailable).rstrip(".").replace("; continuing without the LLM", "")
        reason = reason[0].lower() + reason[1:]
    elif rate_limited:
        reason = "the LLM provider's rate limit was reached"
    else:
        reason = f"the LLM call failed ({str(failures[0][1]).splitlines()[0][:100]})"
    shown = ", ".join(f"'{h}'" for h in headers[:5])
    more = f" and {len(headers) - 5} more" if len(headers) > 5 else ""

    return (
        f"LLM fallback skipped for {len(headers)} column(s) because {reason}: "
        f"{shown}{more}. Their deterministic and semantic evidence was kept; "
        "anything uncertain is in the review queue."
    )
