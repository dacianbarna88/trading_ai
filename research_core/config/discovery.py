"""Edge discovery module configuration (V3.x)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from research_core.config.base import BaseResearchConfig

DEFAULT_ROLLING_CONFIGS: list[tuple[str, float, float]] = [
    ("Rolling_3y_Train_6m_Test", 3.0, 0.5),
    ("Rolling_3y_Train_1y_Test", 3.0, 1.0),
    ("Rolling_4y_Train_1y_Test", 4.0, 1.0),
    ("Rolling_5y_Train_1y_Test", 5.0, 1.0),
    ("Rolling_5y_Train_2y_Test", 5.0, 2.0),
]


@dataclass
class DiscoveryConfig(BaseResearchConfig):
    """V3.0 edge discovery thresholds and output filenames."""

    module_id: str = "edge_discovery"
    version: str = "3.0"

    min_trades: int = 100
    min_single_bin_trades: int = 40
    min_lift_pct: float = 2.0
    unstable_gap: float = 4.0
    max_top_ticker_share: float = 0.35
    max_top_sector_share: float = 0.55
    min_sector_trades: int = 10
    min_sectors_with_edge: int = 2

    min_wf_valid_trades: int = 10
    min_wf_win_pct: float = 60.0
    min_wf_pass_rate: float = 0.5
    roll_step_months: int = 6
    rolling_configs: list[tuple[str, float, float]] = field(
        default_factory=lambda: list(DEFAULT_ROLLING_CONFIGS)
    )

    max_rules_per_group_pair: int = 12
    max_pair_rules_for_triples: int = 200
    max_triples_per_group: int = 5
    production_review_confidence: float = 70.0

    # Safe first-run limits (V3.0 defaults)
    max_candidates_first_run: int = 5000
    max_feature_combinations: int = 2
    enable_three_feature_rules: bool = False
    evaluation_progress_interval: int = 500
    preview_row_limit: int = 200

    confidence_weights: dict[str, float] = field(
        default_factory=lambda: {
            "robustness": 0.30,
            "walk_forward": 0.25,
            "trade_count": 0.20,
            "sector_diversity": 0.15,
            "performance": 0.10,
        }
    )

    candidates_csv: str = "edge_discovery_candidates.csv"
    rejected_csv: str = "edge_discovery_rejected.csv"
    survivors_csv: str = "edge_discovery_survivors.csv"
    summary_txt: str = "edge_discovery_summary.txt"
    progress_txt: str = "edge_discovery_progress.txt"
    runtime_log_txt: str = "edge_discovery_runtime_log.txt"
    candidates_preview_csv: str = "edge_discovery_candidates_preview.csv"

    @classmethod
    def v30_default(cls) -> DiscoveryConfig:
        return cls(version="3.0")

    def output_paths(self, base_dir: Path | None = None) -> dict[str, Path]:
        root = base_dir or Path(self.output_dir)
        return {
            "candidates": root / self.candidates_csv,
            "rejected": root / self.rejected_csv,
            "survivors": root / self.survivors_csv,
            "summary": root / self.summary_txt,
            "progress": root / self.progress_txt,
            "runtime_log": root / self.runtime_log_txt,
            "candidates_preview": root / self.candidates_preview_csv,
        }
