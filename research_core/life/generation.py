"""TAE generation tracking — evolution phases of the ecosystem."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class GenerationRecord:
    number: int
    name: str
    theme: str
    started_at: datetime
    description: str


GENERATION_DEFINITIONS: dict[int, tuple[str, str]] = {
    1: ("Foundation", "Philosophy, architecture, research core"),
    2: ("Communication", "Organisms, evidence packets, collective intelligence"),
    3: ("Cognition", "Memory, feedback, curiosity, knowledge graph"),
    4: ("Real Organisms", "Live research modules wired to ecosystem"),
    5: ("Collective Learning", "Cross-organism learning and trust evolution"),
    6: ("Autonomous Discovery", "Self-directed research and edge discovery"),
    7: ("Production Intelligence", "Human-gated production candidates"),
}


class GenerationTracker:
    """Tracks TAE generational evolution."""

    def __init__(self, start_generation: int = 3) -> None:
        self._current = start_generation
        self._history: list[GenerationRecord] = []
        for num in range(1, start_generation + 1):
            if num in GENERATION_DEFINITIONS:
                theme, desc = GENERATION_DEFINITIONS[num]
                self._history.append(
                    GenerationRecord(
                        number=num,
                        name=f"Generation {num}",
                        theme=theme,
                        started_at=datetime(2026, 6, 25, tzinfo=timezone.utc),
                        description=desc,
                    )
                )

    def current_generation(self) -> int:
        return self._current

    def current_generation_info(self) -> GenerationRecord | None:
        for record in reversed(self._history):
            if record.number == self._current:
                return record
        if self._current in GENERATION_DEFINITIONS:
            theme, desc = GENERATION_DEFINITIONS[self._current]
            return GenerationRecord(
                number=self._current,
                name=f"Generation {self._current}",
                theme=theme,
                started_at=datetime.now(timezone.utc),
                description=desc,
            )
        return None

    def promote_generation(self, reason: str = "") -> GenerationRecord:
        if self._current >= 7:
            return self._history[-1]
        self._current += 1
        theme, desc = GENERATION_DEFINITIONS.get(
            self._current,
            ("Unknown", "Future generation"),
        )
        record = GenerationRecord(
            number=self._current,
            name=f"Generation {self._current}",
            theme=theme,
            started_at=datetime.now(timezone.utc),
            description=f"{desc}. {reason}".strip(),
        )
        self._history.append(record)
        return record

    def history(self) -> list[GenerationRecord]:
        return list(self._history)

    def generation_name(self, number: int | None = None) -> str:
        num = number if number is not None else self._current
        if num in GENERATION_DEFINITIONS:
            return GENERATION_DEFINITIONS[num][0]
        return f"Generation {num}"

    def to_dict(self) -> dict[str, Any]:
        info = self.current_generation_info()
        return {
            "current": self._current,
            "theme": info.theme if info else "",
            "description": info.description if info else "",
            "history_count": len(self._history),
        }
