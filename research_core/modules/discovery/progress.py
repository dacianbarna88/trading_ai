"""Progress logging and checkpoint files for edge discovery runs."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from research_core.config.discovery import DiscoveryConfig


class DiscoveryProgressTracker:
    """
    Terminal progress, runtime log, progress snapshot, and candidate preview CSV.
    """

    def __init__(self, output_dir: Path, config: DiscoveryConfig) -> None:
        self._output_dir = output_dir
        self._config = config
        self._progress_path = output_dir / config.progress_txt
        self._runtime_log_path = output_dir / config.runtime_log_txt
        self._preview_path = output_dir / config.candidates_preview_csv
        self._state: dict[str, Any] = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "tickers_loaded": 0,
            "signals_collected": 0,
            "feature_bins_generated": 0,
            "candidates_generated": 0,
            "candidates_evaluated": 0,
            "candidates_capped": False,
            "candidates_cap_limit": config.max_candidates_first_run,
            "rejected": 0,
            "survivors": 0,
            "stage": "init",
        }
        output_dir.mkdir(parents=True, exist_ok=True)
        self._runtime_log_path.write_text(
            f"===== EDGE DISCOVERY RUNTIME LOG V{config.version} =====\n",
            encoding="utf-8",
        )
        self._write_progress()

    def log(self, message: str) -> None:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        line = f"[{stamp}] {message}"
        print(line)
        with self._runtime_log_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def set_stage(self, stage: str) -> None:
        self._state["stage"] = stage
        self._write_progress()

    def ticker_loaded(self, ticker: str, tickers_loaded: int, signals_collected: int) -> None:
        self._state["tickers_loaded"] = tickers_loaded
        self._state["signals_collected"] = signals_collected
        self._state["last_ticker"] = ticker
        self.log(f"Tickers loaded: {tickers_loaded} | Signals collected: {signals_collected} ({ticker})")
        self._write_progress()

    def feature_bins_generated(self, bin_count: int, signal_count: int) -> None:
        self._state["feature_bins_generated"] = bin_count
        self._state["signals_collected"] = signal_count
        self.log(f"Feature bins generated: {bin_count} | Signals: {signal_count}")
        self._write_progress()

    def candidates_generated(
        self,
        count: int,
        capped: bool = False,
        original_count: int | None = None,
    ) -> None:
        self._state["candidates_generated"] = count
        self._state["candidates_capped"] = capped
        if original_count is not None:
            self._state["candidates_before_cap"] = original_count
        msg = f"Candidate rules generated: {count}"
        if capped and original_count is not None:
            msg += f" (capped from {original_count})"
        self.log(msg)
        self._write_progress()

    def evaluation_progress(
        self,
        evaluated: int,
        total: int,
        rejected: int,
        survivors: int,
    ) -> None:
        self._state["candidates_evaluated"] = evaluated
        self._state["rejected"] = rejected
        self._state["survivors"] = survivors
        self.log(
            f"Evaluation progress: {evaluated}/{total} | "
            f"Rejected: {rejected} | Survivors: {survivors}"
        )
        self._write_progress()

    def write_candidates_preview(self, candidates: list[dict]) -> None:
        if not candidates:
            pd.DataFrame().to_csv(self._preview_path, index=False)
            return
        preview = pd.DataFrame(candidates)
        if "Edge_Confidence_Score" in preview.columns:
            preview = preview.sort_values("Edge_Confidence_Score", ascending=False)
        preview.head(self._config.preview_row_limit).to_csv(self._preview_path, index=False)
        self.log(f"Checkpoint: {self._preview_path} ({len(candidates)} rows, preview saved)")

    def finalize(self, status: str, detail: str = "") -> None:
        self._state["status"] = status
        self._state["finished_at"] = datetime.now(timezone.utc).isoformat()
        if detail:
            self._state["detail"] = detail
        self.log(f"Run finished: {status}" + (f" — {detail}" if detail else ""))
        self._write_progress()

    def _write_progress(self) -> None:
        lines = [
            f"===== EDGE DISCOVERY PROGRESS V{self._config.version} =====",
            f"Stage: {self._state.get('stage', 'unknown')}",
            f"Tickers loaded: {self._state.get('tickers_loaded', 0)}",
            f"Signals collected: {self._state.get('signals_collected', 0)}",
            f"Feature bins generated: {self._state.get('feature_bins_generated', 0)}",
            f"Candidates generated: {self._state.get('candidates_generated', 0)}",
            f"Candidates evaluated: {self._state.get('candidates_evaluated', 0)}",
            f"Candidates capped: {self._state.get('candidates_capped', False)}",
            f"Rejected: {self._state.get('rejected', 0)}",
            f"Survivors: {self._state.get('survivors', 0)}",
        ]
        if self._state.get("candidates_before_cap"):
            lines.append(
                f"Candidates before cap: {self._state['candidates_before_cap']}"
            )
        if self._state.get("last_ticker"):
            lines.append(f"Last ticker: {self._state['last_ticker']}")
        if self._state.get("status"):
            lines.append(f"Status: {self._state['status']}")
        lines.append("")
        self._progress_path.write_text("\n".join(lines), encoding="utf-8")
