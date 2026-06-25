"""
TAE Hypothesis registry — JSON persistence for research hypotheses.

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_core.hypothesis.hypothesis_model import Hypothesis, HypothesisStatus

logger = logging.getLogger(__name__)

DEFAULT_REGISTRY_PATH = Path("tae_hypothesis_registry.json")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_hypothesis_registry"


class HypothesisRegistry:
    """Persistent store of research hypotheses — stdlib json only."""

    def __init__(self, path: Path | None = None, auto_load: bool = True) -> None:
        self._path = path or DEFAULT_REGISTRY_PATH
        self._hypotheses: dict[str, Hypothesis] = {}
        self._sequence: int = 0
        self._loaded_at_startup = False
        if auto_load:
            self._loaded_at_startup = self.load()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def loaded_at_startup(self) -> bool:
        return self._loaded_at_startup

    def count(self) -> int:
        return len(self._hypotheses)

    def list_all(self) -> list[Hypothesis]:
        return sorted(self._hypotheses.values(), key=lambda h: h.created_at)

    def list_by_status(self, status: HypothesisStatus) -> list[Hypothesis]:
        return [h for h in self._hypotheses.values() if h.status == status]

    def list_untested(self) -> list[Hypothesis]:
        """Candidates for Sprint 5.1 Experiment Runner."""
        return self.list_by_status(HypothesisStatus.UNTESTED)

    def update_status(self, hypothesis_id: str, status: HypothesisStatus) -> Hypothesis | None:
        hypothesis = self._hypotheses.get(hypothesis_id)
        if hypothesis is None:
            return None
        hypothesis.status = status
        return hypothesis

    def get(self, hypothesis_id: str) -> Hypothesis | None:
        return self._hypotheses.get(hypothesis_id)

    def next_id(self, prefix: str = "hyp_s5") -> str:
        self._sequence += 1
        return f"{prefix}_{self._sequence:05d}"

    def register(self, hypothesis: Hypothesis) -> Hypothesis:
        if hypothesis.hypothesis_id in self._hypotheses:
            raise ValueError(f"Duplicate hypothesis_id: {hypothesis.hypothesis_id}")
        self._hypotheses[hypothesis.hypothesis_id] = hypothesis
        return hypothesis

    def add_generated(self, hypothesis: Hypothesis) -> Hypothesis:
        """Register a new hypothesis, assigning id if missing."""
        if not hypothesis.hypothesis_id:
            hypothesis.hypothesis_id = self.next_id()
        if hypothesis.hypothesis_id in self._hypotheses:
            hypothesis.hypothesis_id = self.next_id()
        return self.register(hypothesis)

    def load(self) -> bool:
        if not self._path.is_file():
            return False
        try:
            raw = self._path.read_text(encoding="utf-8")
            payload = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Hypothesis registry unreadable (%s): %s", self._path, exc)
            return False

        if not isinstance(payload, dict) or payload.get("schema") != SCHEMA_NAME:
            logger.warning("Hypothesis registry schema mismatch in %s", self._path)
            return False

        self._sequence = int(payload.get("sequence", 0))
        items = payload.get("hypotheses", [])
        if not isinstance(items, list):
            return False

        restored: dict[str, Hypothesis] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            hypothesis = Hypothesis.from_dict(item)
            if hypothesis is not None:
                restored[hypothesis.hypothesis_id] = hypothesis

        self._hypotheses = restored
        if self._sequence < len(restored):
            self._sequence = len(restored)
        return True

    def persist(self) -> Path:
        payload = {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "sequence": self._sequence,
            "hypothesis_count": len(self._hypotheses),
            "hypotheses": [h.to_dict() for h in self.list_all()],
        }
        self._path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return self._path

    def format_summary(self) -> str:
        if not self._hypotheses:
            return "Hypothesis registry empty."
        lines = ["===== HYPOTHESIS REGISTRY =====", ""]
        for hypothesis in self.list_all():
            lines.append(f"  {hypothesis.summary_line()}")
        lines.append("")
        return "\n".join(lines)
