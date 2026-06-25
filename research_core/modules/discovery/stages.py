"""Pipeline stages for edge discovery module."""

from __future__ import annotations

from typing import Any

from research_core.config.discovery import DiscoveryConfig
from research_core.discovery.evaluator import RuleEvaluator
from research_core.features.registry import FeatureBinRegistry
from research_core.framework.context import ResearchContext, ResearchStageError
from research_core.modules.discovery.progress import DiscoveryProgressTracker
from research_core.reporting.writer import DiscoveryReportWriter
from research_core.rules.cap import cap_rules_deterministic
from research_core.rules.generator import BinRuleGenerator
from research_core.services.dataset_builder import SignalDatasetBuilder
from research_core.types import SignalDataset
from research_core.validation.walk_forward import WalkForwardValidator


def _get_progress(context: ResearchContext) -> DiscoveryProgressTracker | None:
    progress = context.artifact("progress")
    return progress if isinstance(progress, DiscoveryProgressTracker) else None


class InitProgressStage:
    name = "init_progress"

    def run(self, context: ResearchContext) -> dict[str, Any]:
        config = _as_discovery_config(context.config)
        progress = DiscoveryProgressTracker(context.output_dir, config)
        context.artifacts["progress"] = progress
        progress.set_stage(self.name)
        progress.log(
            "Safe first-run limits: "
            f"max_candidates={config.max_candidates_first_run}, "
            f"max_feature_combinations={config.max_feature_combinations}, "
            f"three_feature_rules={config.enable_three_feature_rules}"
        )
        return {"progress_initialized": True}


class LoadDatasetStage:
    name = "load_dataset"

    def __init__(self, dataset_builder: SignalDatasetBuilder | None = None) -> None:
        self._builder = dataset_builder

    def run(self, context: ResearchContext) -> dict[str, Any]:
        config = context.config
        progress = _get_progress(context)
        if progress:
            progress.set_stage(self.name)

        builder = self._builder or SignalDatasetBuilder(config)
        on_ticker = progress.ticker_loaded if progress else None
        dataset = builder.build(on_ticker_loaded=on_ticker)

        if dataset is None:
            config_d = _as_discovery_config(config)
            reporter = DiscoveryReportWriter(config_d)
            reporter.write_failure(context.output_dir, "SPY_DOWNLOAD_FAILED_OR_NO_DATA", progress)
            if progress:
                progress.finalize("failed", "SPY_DOWNLOAD_FAILED_OR_NO_DATA")
            raise ResearchStageError(self.name, "SPY_DOWNLOAD_FAILED_OR_NO_DATA")

        bin_cols = [c for c in dataset.signals.columns if c.startswith("BIN_")]
        if progress:
            progress.feature_bins_generated(len(bin_cols), len(dataset.signals))

        context.artifacts["dataset"] = dataset
        context.artifacts["feature_bin_count"] = len(bin_cols)
        return {
            "signals": len(dataset.signals),
            "tickers_loaded": dataset.tickers_loaded,
            "universe_size": dataset.universe_size,
            "feature_bins": len(bin_cols),
        }


class GenerateRulesStage:
    name = "generate_rules"

    def __init__(self, feature_registry: FeatureBinRegistry | None = None) -> None:
        self._registry = feature_registry or FeatureBinRegistry()

    def run(self, context: ResearchContext) -> dict[str, Any]:
        dataset = _require_dataset(context)
        config = _as_discovery_config(context.config)
        progress = _get_progress(context)
        if progress:
            progress.set_stage(self.name)

        self._registry.register_defaults()
        groups = self._registry.bin_column_groups(dataset.signals)
        generator = BinRuleGenerator(config, groups)
        rules = generator.generate(dataset.signals)
        original_count = len(rules)

        capped_rules, was_capped, _ = cap_rules_deterministic(
            rules, config.max_candidates_first_run
        )
        context.artifacts["rules"] = capped_rules
        context.artifacts["rules_capped"] = was_capped
        context.artifacts["rules_before_cap"] = original_count

        if progress:
            progress.candidates_generated(
                len(capped_rules), capped=was_capped, original_count=original_count
            )

        return {
            "rules_generated": len(capped_rules),
            "rules_before_cap": original_count,
            "rules_capped": was_capped,
        }


class EvaluateCandidatesStage:
    name = "evaluate_candidates"

    def __init__(self, evaluator: RuleEvaluator | None = None) -> None:
        self._evaluator = evaluator

    def run(self, context: ResearchContext) -> dict[str, Any]:
        dataset = _require_dataset(context)
        config = _as_discovery_config(context.config)
        progress = _get_progress(context)
        if progress:
            progress.set_stage(self.name)

        rules = context.artifact("rules", [])
        evaluator = self._evaluator or RuleEvaluator(config)
        wf = WalkForwardValidator(config)
        windows = wf.build_test_windows(dataset.min_date, dataset.max_date)
        context.artifacts["test_windows"] = windows

        candidates: list[dict] = []
        rejected: list[dict] = []
        survivors: list[dict] = []
        reject_counts: dict[str, int] = {}
        total = len(rules)
        interval = config.evaluation_progress_interval

        for index, rule in enumerate(rules, start=1):
            result = evaluator.evaluate(dataset, rule, windows)
            row = result.to_row()
            candidates.append(row)
            if result.rejection_reason:
                rej = dict(row)
                rej["Rejection_Reason"] = result.rejection_reason
                rej["Robustness_Issues"] = "; ".join(result.robustness_issues)
                rejected.append(rej)
                reject_counts[result.rejection_reason] = (
                    reject_counts.get(result.rejection_reason, 0) + 1
                )
            else:
                survivors.append(row)

            if progress and (index % interval == 0 or index == total):
                progress.evaluation_progress(index, total, len(rejected), len(survivors))
                progress.write_candidates_preview(candidates)

        context.artifacts["candidates"] = candidates
        context.artifacts["rejected"] = rejected
        context.artifacts["survivors"] = survivors
        context.artifacts["reject_counts"] = reject_counts

        if progress:
            progress.write_candidates_preview(candidates)

        return {
            "candidates": len(candidates),
            "survivors": len(survivors),
            "rejected": len(rejected),
        }


class WriteReportsStage:
    name = "write_reports"

    def __init__(self, reporter: DiscoveryReportWriter | None = None) -> None:
        self._reporter = reporter

    def run(self, context: ResearchContext) -> dict[str, Any]:
        dataset = _require_dataset(context)
        config = _as_discovery_config(context.config)
        progress = _get_progress(context)
        if progress:
            progress.set_stage(self.name)

        reporter = self._reporter or DiscoveryReportWriter(config)
        summary = reporter.write(
            context.output_dir,
            dataset=dataset,
            candidates=context.artifact("candidates", []),
            rejected=context.artifact("rejected", []),
            survivors=context.artifact("survivors", []),
            reject_counts=context.artifact("reject_counts", {}),
            rules_capped=context.artifact("rules_capped", False),
            rules_before_cap=context.artifact("rules_before_cap", 0),
            feature_bin_count=context.artifact("feature_bin_count", 0),
        )
        paths = config.output_paths(context.output_dir)
        context.artifacts["summary"] = summary
        context.artifacts["output_paths"] = paths
        context.artifacts["run_metrics"] = {
            "signals": len(dataset.signals),
            "candidates": len(context.artifact("candidates", [])),
            "survivors": len(context.artifact("survivors", [])),
            "rejected": len(context.artifact("rejected", [])),
        }
        if progress:
            progress.finalize("ok")
        print(summary.split("\n")[0])
        return context.artifacts["run_metrics"]


def _require_dataset(context: ResearchContext) -> SignalDataset:
    dataset = context.artifact("dataset")
    if dataset is None:
        raise ResearchStageError("pipeline", "dataset not loaded")
    return dataset


def _as_discovery_config(config) -> DiscoveryConfig:
    if isinstance(config, DiscoveryConfig):
        return config
    return DiscoveryConfig(
        **{k: getattr(config, k) for k in vars(config) if not k.startswith("_")}
    )
