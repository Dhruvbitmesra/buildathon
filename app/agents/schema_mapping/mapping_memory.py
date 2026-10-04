"""
Vector memory of reviewer-confirmed column mappings (cross-submission
learning).

When a reviewer approves or corrects a column mapping and the file is
exported, the source header and its final target are stored with the
header's embedding. Later files use the memory as evidence:

- the same normalised header -> strong evidence for the confirmed target;
- a semantically close header (cosine >= SIMILARITY_THRESHOLD) ->
  moderate evidence;
- a target the reviewer rejected for that header is blocked.

Only headers are stored, never row values. The store is a JSON file
(default memory/mapping_memory.json, override with SOV_MEMORY_PATH),
so it needs no database server.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np

from app.agents.schema_mapping.header_normalizer import normalize_header


SIMILARITY_THRESHOLD = 0.90
DEFAULT_PATH = Path("memory") / "mapping_memory.json"


class MappingMemory:
    def __init__(
        self,
        path: str | Path | None = None,
        embed=None,
    ) -> None:
        self.path = Path(path or os.getenv("SOV_MEMORY_PATH") or DEFAULT_PATH)
        self._embed = embed
        self.entries: dict[str, dict] = {}

        if self.path.exists():
            try:
                self.entries = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self.entries = {}

    # -----------------------------------------------------------------

    def remember(self, source_header: str, target: Optional[str], approved: bool) -> None:
        """
        Record a reviewer decision. approved=False records that `target`
        is wrong for this header.
        """

        normalized = normalize_header(source_header)

        if not normalized or target is None:
            return

        entry = self.entries.setdefault(
            normalized,
            {
                "header": source_header,
                "embedding": self._embedding(normalized),
                "approved": {},
                "rejected": {},
            },
        )
        bucket = entry["approved" if approved else "rejected"]
        bucket[target] = bucket.get(target, 0) + 1
        entry["updated"] = datetime.now(timezone.utc).isoformat()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.entries, indent=1), encoding="utf-8")

    # -----------------------------------------------------------------

    def recall(self, source_header: str) -> Optional[dict]:
        """
        Best confirmed target for a header:
        {"target", "similarity", "matched_header", "exact"} or None.
        """

        normalized = normalize_header(source_header)

        if not normalized or not self.entries:
            return None

        exact = self.entries.get(normalized)

        if exact is not None:
            target = self._confirmed_target(exact)

            if target:
                return {
                    "target": target,
                    "similarity": 1.0,
                    "matched_header": exact["header"],
                    "exact": True,
                }

        query = self._embedding(normalized)

        if query is None:
            return None

        best = None

        for entry in self.entries.values():
            vector = entry.get("embedding")
            target = self._confirmed_target(entry)

            if vector is None or not target:
                continue

            similarity = float(np.dot(query, vector))

            if similarity >= SIMILARITY_THRESHOLD and (
                best is None or similarity > best["similarity"]
            ):
                best = {
                    "target": target,
                    "similarity": round(similarity, 4),
                    "matched_header": entry["header"],
                    "exact": False,
                }

        return best

    def blocked_targets(self, source_header: str) -> set[str]:
        """Targets reviewers rejected for this exact header more than approved."""

        entry = self.entries.get(normalize_header(source_header))

        if entry is None:
            return set()

        return {
            target
            for target, count in entry["rejected"].items()
            if count > entry["approved"].get(target, 0)
        }

    # -----------------------------------------------------------------

    @staticmethod
    def _confirmed_target(entry: dict) -> Optional[str]:
        scores = {
            target: count - entry["rejected"].get(target, 0)
            for target, count in entry["approved"].items()
        }
        scores = {t: s for t, s in scores.items() if s > 0}

        return max(scores, key=scores.get) if scores else None

    def _embedding(self, text: str):
        try:
            if self._embed is None:
                from app.agents.schema_mapping.embedding_retriever import (
                    load_embedding_model,
                )

                model = load_embedding_model()
                self._embed = lambda t: model.encode(
                    [t], normalize_embeddings=True, show_progress_bar=False
                )[0]

            return [float(x) for x in self._embed(text)]
        except Exception:
            return None
