"""Report generation for discovery runs."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from research_core.config.discovery import DiscoveryConfig
from research_core.modules.discovery.progress import DiscoveryProgressTracker
from research_core.types import SignalDataset


class DiscoveryReportWriter:
    def __init__(self, config: DiscoveryConfig) -> None:
        self._config = config

    def write_failure(
        self,
        base_dir: Path,
        message: str,
        progress: DiscoveryProgressTracker | None = None,
    ) -> None:
        paths = self._config.output_paths(base_dir)
        summary_lines = [
            f"===== EDGE DISCOVERY ENGINE V{self._config.version} =====",
            "",
            "RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION",
            "",
            f"STATUS: FAILED — {message}",
            "",
            "No full candidate evaluation completed.",
            "Check edge_discovery_progress.txt and edge_discovery_runtime_log.txt.",
            "",
        ]
        paths["summary"].write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
        if progress:
            progress.finalize("failed", message)

    def write(
        self,
        base_dir: Path,
        dataset: SignalDataset,
        candidates: list[dict],
        rejected: list[dict],
        survivors: list[dict],
        reject_counts: dict[str, int],
        rules_capped: bool = False,
        rules_before_cap: int = 0,
        feature_bin_count: int = 0,
    ) -> str:
        paths = self._config.output_paths(base_dir)
        pd.DataFrame(candidates).to_csv(paths["candidates"], index=False)
        pd.DataFrame(rejected).to_csv(paths["rejected"], index=False)

        survivors_df = pd.DataFrame(survivors)
        if not survivors_df.empty:
            survivors_df = survivors_df.sort_values(
                ["Edge_Confidence_Score", "Robustness_Score", "Walk_Forward_Score"],
                ascending=False,
            )
        survivors_df.to_csv(paths["survivors"], index=False)

        baseline = dataset.baseline_metrics
        top = survivors_df.head(20) if not survivors_df.empty else pd.DataFrame()

        lines = [
            f"===== EDGE DISCOVERY ENGINE V{self._config.version} =====",
            "",
            "RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION",
            "Research Core framework — no automatic production promotion.",
            "",
            f"Universe size: {dataset.universe_size}",
            f"Tickers loaded: {dataset.tickers_loaded}",
            f"Signals analyzed: {len(dataset.signals)}",
            f"Feature bins generated: {feature_bin_count}",
            f"Total candidates generated: {len(candidates)}",
            f"Candidates capped: {rules_capped}"
            + (f" (from {rules_before_cap})" if rules_capped and rules_before_cap else ""),
            f"Rejected: {len(rejected)}",
            f"Survivors (all validations passed): {len(survivors)}",
            "",
            "--- First-run limits ---",
            f"  max_candidates_first_run: {self._config.max_candidates_first_run}",
            f"  max_feature_combinations: {self._config.max_feature_combinations}",
            f"  enable_three_feature_rules: {self._config.enable_three_feature_rules}",
            "",
            "--- Checkpoint files ---",
            f"  {paths['progress']}",
            f"  {paths['runtime_log']}",
            f"  {paths['candidates_preview']}",
            "",
            "--- Rejection breakdown ---",
            f"  Low_Sample: {reject_counts.get('Low_Sample', 0)}",
            f"  Overfitting: {reject_counts.get('Overfitting', 0)}",
            f"  Walk_Forward_Failure: {reject_counts.get('Walk_Forward_Failure', 0)}",
            f"  Ticker_Concentration: {reject_counts.get('Ticker_Concentration', 0)}",
            f"  Sector_Concentration: {reject_counts.get('Sector_Concentration', 0)}",
            f"  Poor_Robustness: {reject_counts.get('Poor_Robustness', 0)}",
            "",
            "--- Baseline (all signals) ---",
            f"  Trades: {baseline['Trades']} Win: {baseline['Win_Rate']}% "
            f"Avg: {baseline['Avg_Return']}% PF: {baseline['Profit_Factor']}",
            "",
            "--- Top surviving edges ---",
        ]
        if top.empty:
            lines.append("  No edges survived full validation pipeline.")
        else:
            for _, r in top.iterrows():
                lines.append(
                    f"  [{r['Edge_Confidence_Score']}] {r['Rule_Description']} | "
                    f"trades={int(r['Trades'])} avg={r['Avg_Return']}% "
                    f"robust={r['Robustness_Score']} wf={r['Walk_Forward_Score']} | "
                    f"{r['Recommendation']}"
                )
                lines.append(f"    {r['Explanation']}")
        lines.extend(
            [
                "",
                "Architecture: research_core package (modular, extensible).",
                "All outputs remain DISCOVERY_ONLY until explicit human approval.",
                "",
            ]
        )
        summary = "\n".join(lines)
        paths["summary"].write_text(summary, encoding="utf-8")
        print(f"Saved: {paths['candidates']}")
        print(f"Saved: {paths['rejected']}")
        print(f"Saved: {paths['survivors']}")
        print(f"Saved: {paths['summary']}")
        print(f"Saved: {paths['progress']}")
        print(f"Saved: {paths['runtime_log']}")
        print(f"Saved: {paths['candidates_preview']}")
        return summary
