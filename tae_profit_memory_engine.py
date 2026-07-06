#!/usr/bin/env python3
"""
TAE Profit Memory Engine v3 — SHADOW_ONLY / NO_BROKER.

Historical memory layer for profit episodes from shadow outputs.
Does NOT modify live_bot, portfolio, broker, or PIB execution logic.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

PIB_JSON = Path("tae_profit_intelligence_brain.json")
SHADOW_JSON = Path("tae_profit_protection_shadow.json")
VALIDATION_JSON = Path("tae_profit_protection_validation.json")
BOT_OUTPUT_LOG = Path("bot_output.log")

OUTPUT_JSON = Path("tae_profit_memory_engine.json")
OUTPUT_MD = Path("tae_profit_memory_engine.md")

MEMORY_LABELS = frozenset(
    {"PROFIT_SURVIVED", "PROFIT_DECAYED", "PROFIT_COLLAPSED", "UNKNOWN_OUTCOME"}
)
MEMORY_BIASES = frozenset(
    {"MEMORY_PROTECT_EARLY", "MEMORY_HOLD_WINNERS", "MEMORY_NEUTRAL"}
)


def load_json(path: Path) -> tuple[dict[str, Any] | None, bool]:
    if not path.is_file():
        return None, False
    try:
        return json.loads(path.read_text(encoding="utf-8")), True
    except (json.JSONDecodeError, OSError):
        return None, False


def classify_episode(
    *,
    current_pct: float,
    high_pct: float,
    drawdown: float,
) -> str:
    if high_pct >= 6.0 and current_pct <= 1.0:
        return "PROFIT_COLLAPSED"
    if high_pct >= 4.0 and drawdown <= -2.0:
        return "PROFIT_DECAYED"
    if current_pct > 0 and high_pct > 0 and current_pct >= high_pct * 0.75:
        return "PROFIT_SURVIVED"
    return "UNKNOWN_OUTCOME"


def build_episode_key(episode: dict[str, Any]) -> str:
    """Stable dedupe key — independent of captured_at timestamp."""
    ticker = str(episode.get("ticker", "")).upper()
    high_pct = round(float(episode.get("high_pct") or 0), 2)
    current_pct = round(float(episode.get("current_pct") or 0), 2)
    missed_usd = round(float(episode.get("missed_usd") or 0), 2)
    pib_rec = str(episode.get("pib_recommendation") or "")
    psp_urgency = str(episode.get("psp_urgency") or "")
    return f"{ticker}|{high_pct}|{current_pct}|{missed_usd}|{pib_rec}|{psp_urgency}"


def ensure_episode_key(episode: dict[str, Any]) -> dict[str, Any]:
    out = dict(episode)
    if not out.get("episode_key"):
        out["episode_key"] = build_episode_key(out)
    return out


def deduplicate_episodes(
    episodes: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Keep earliest captured_at per episode_key; return (unique, duplicates_removed)."""
    by_key: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for raw in episodes:
        ep = ensure_episode_key(raw)
        key = ep["episode_key"]
        if key not in by_key:
            by_key[key] = ep
            order.append(key)
            continue
        existing = by_key[key]
        if str(ep.get("captured_at", "")) < str(existing.get("captured_at", "")):
            by_key[key] = ep
    unique = [by_key[k] for k in order]
    return unique, len(episodes) - len(unique)


def merge_position_sources(
    pib_row: dict[str, Any] | None,
    shadow_row: dict[str, Any] | None,
    *,
    captured_at: str,
) -> dict[str, Any]:
    row = shadow_row or pib_row or {}
    pib = pib_row or {}

    current_pct = float(
        pib.get("current_pct") if pib.get("current_pct") is not None else row.get("current_pct") or 0
    )
    high_pct = float(
        pib.get("high_pct") if pib.get("high_pct") is not None else row.get("high_pct") or 0
    )
    drawdown = float(
        pib.get("drawdown")
        if pib.get("drawdown") is not None
        else row.get("drawdown_from_high_pct") or 0
    )
    missed_usd = float(
        pib.get("missed_usd")
        if pib.get("missed_usd") is not None
        else row.get("missed_opportunity_usd") or 0
    )

    pib_rec = (
        pib.get("psp_adjusted_recommendation")
        or pib.get("existing_pib_recommendation")
        or pib.get("final_recommendation")
    )
    psp_urgency = pib.get("psp_protection_urgency")

    episode = {
        "ticker": str(row.get("ticker") or pib.get("ticker", "")).upper(),
        "captured_at": captured_at,
        "current_pct": round(current_pct, 2),
        "high_pct": round(high_pct, 2),
        "drawdown": round(drawdown, 2),
        "missed_usd": round(missed_usd, 2),
        "pib_recommendation": pib_rec,
        "psp_survival_probability": pib.get("psp_survival_probability"),
        "psp_giveback_risk": pib.get("psp_giveback_risk"),
        "psp_urgency": psp_urgency,
        "memory_label": classify_episode(
            current_pct=current_pct,
            high_pct=high_pct,
            drawdown=drawdown,
        ),
        "source_run": {
            "pib_generated_at": pib.get("_run_generated_at"),
            "shadow_generated_at": shadow_row.get("_run_generated_at") if shadow_row else None,
        },
        "shadow_only": True,
    }
    episode["episode_key"] = build_episode_key(episode)
    return episode


def recommended_memory_bias(
    *,
    observations: int,
    collapsed_count: int,
    decayed_count: int,
    survived_count: int,
) -> str:
    if observations < 3:
        return "MEMORY_NEUTRAL"
    collapse_rate = collapsed_count / observations
    decay_rate = decayed_count / observations
    survival_rate = survived_count / observations
    if collapse_rate + decay_rate >= 0.60:
        return "MEMORY_PROTECT_EARLY"
    if survival_rate >= 0.60:
        return "MEMORY_HOLD_WINNERS"
    return "MEMORY_NEUTRAL"


def summarize_ticker(episodes: list[dict[str, Any]]) -> dict[str, Any]:
    observations = len(episodes)
    collapsed = sum(1 for e in episodes if e.get("memory_label") == "PROFIT_COLLAPSED")
    decayed = sum(1 for e in episodes if e.get("memory_label") == "PROFIT_DECAYED")
    survived = sum(1 for e in episodes if e.get("memory_label") == "PROFIT_SURVIVED")
    unknown = sum(1 for e in episodes if e.get("memory_label") == "UNKNOWN_OUTCOME")
    total_missed = round(sum(float(e.get("missed_usd") or 0) for e in episodes), 2)

    collapse_rate = round(collapsed / observations, 3) if observations else 0.0
    decay_rate = round(decayed / observations, 3) if observations else 0.0
    survival_rate = round(survived / observations, 3) if observations else 0.0

    bias = recommended_memory_bias(
        observations=observations,
        collapsed_count=collapsed,
        decayed_count=decayed,
        survived_count=survived,
    )

    return {
        "ticker": episodes[0]["ticker"] if episodes else "",
        "observations": observations,
        "collapsed_count": collapsed,
        "decayed_count": decayed,
        "survived_count": survived,
        "unknown_count": unknown,
        "collapse_rate": collapse_rate,
        "decay_rate": decay_rate,
        "survival_rate": survival_rate,
        "total_missed_usd": total_missed,
        "recommended_memory_bias": bias,
    }


def build_global_verdict(
    *,
    total_episodes: int,
    tickers_tracked: int,
    sources_loaded: dict[str, bool],
) -> str:
    if not any(sources_loaded.values()) or total_episodes == 0:
        return "MEMORY_NOT_READY"
    if total_episodes >= 10 and tickers_tracked >= 3:
        return "MEMORY_READY_FOR_OBSERVATION"
    if total_episodes >= 1:
        return "MEMORY_NEEDS_MORE_DATA"
    return "MEMORY_NOT_READY"


def capture_episodes_from_sources(
    *,
    pib: dict[str, Any] | None,
    shadow: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    captured_at = datetime.now().isoformat(timespec="seconds")
    pib_generated = (pib or {}).get("generated_at")
    shadow_generated = (shadow or {}).get("generated_at")

    pib_by_ticker = {
        str(r.get("ticker", "")).upper(): r for r in (pib or {}).get("positions") or [] if r.get("ticker")
    }
    shadow_by_ticker = {
        str(r.get("ticker", "")).upper(): r for r in (shadow or {}).get("positions") or [] if r.get("ticker")
    }

    all_tickers = sorted(set(pib_by_ticker) | set(shadow_by_ticker))
    episodes: list[dict[str, Any]] = []
    for ticker in all_tickers:
        pib_row = dict(pib_by_ticker.get(ticker) or {})
        shadow_row = dict(shadow_by_ticker.get(ticker) or {})
        if pib_row:
            pib_row["_run_generated_at"] = pib_generated
        if shadow_row:
            shadow_row["_run_generated_at"] = shadow_generated
        ep = merge_position_sources(pib_row or None, shadow_row or None, captured_at=captured_at)
        if ep["ticker"]:
            episodes.append(ep)
    return episodes


def append_episodes(
    existing_episodes: list[dict[str, Any]],
    new_episodes: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int, int]:
    seen = {ensure_episode_key(e)["episode_key"] for e in existing_episodes}
    merged = [ensure_episode_key(e) for e in existing_episodes]
    added = 0
    skipped = 0
    for raw in new_episodes:
        ep = ensure_episode_key(raw)
        if ep["episode_key"] in seen:
            skipped += 1
            continue
        merged.append(ep)
        seen.add(ep["episode_key"])
        added += 1
    return merged, added, skipped


def build_memory_report(
    *,
    memory_path: Path = OUTPUT_JSON,
    pib_path: Path = PIB_JSON,
    shadow_path: Path = SHADOW_JSON,
    validation_path: Path = VALIDATION_JSON,
) -> dict[str, Any]:
    prior, prior_loaded = load_json(memory_path)
    pib, pib_loaded = load_json(pib_path)
    shadow, shadow_loaded = load_json(shadow_path)
    validation, validation_loaded = load_json(validation_path)

    sources_loaded = {
        str(pib_path): pib_loaded,
        str(shadow_path): shadow_loaded,
        str(validation_path): validation_loaded,
        str(BOT_OUTPUT_LOG): BOT_OUTPUT_LOG.is_file(),
    }

    existing_episodes: list[dict[str, Any]] = list((prior or {}).get("episodes") or [])
    total_raw_before_cleanup = len(existing_episodes)
    existing_unique, legacy_collapsed = deduplicate_episodes(existing_episodes)

    new_episodes = capture_episodes_from_sources(pib=pib, shadow=shadow)
    merged_episodes, added_count, skipped_count = append_episodes(existing_unique, new_episodes)
    total_raw_after_append = len(merged_episodes)
    unique_episodes, post_append_collapsed = deduplicate_episodes(merged_episodes)
    duplicates_ignored_in_aggregation = legacy_collapsed + post_append_collapsed

    by_ticker: dict[str, list[dict[str, Any]]] = {}
    for ep in unique_episodes:
        by_ticker.setdefault(ep["ticker"], []).append(ep)

    ticker_memory = [summarize_ticker(eps) for eps in by_ticker.values()]
    ticker_memory.sort(key=lambda t: t.get("total_missed_usd", 0), reverse=True)

    collapse_ranked = sorted(
        ticker_memory,
        key=lambda t: (t.get("collapse_rate", 0) + t.get("decay_rate", 0), t.get("total_missed_usd", 0)),
        reverse=True,
    )
    survival_ranked = sorted(
        ticker_memory,
        key=lambda t: (t.get("survival_rate", 0), t.get("observations", 0)),
        reverse=True,
    )

    total_episodes = len(unique_episodes)
    tickers_tracked = len(ticker_memory)
    final_verdict = build_global_verdict(
        total_episodes=total_episodes,
        tickers_tracked=tickers_tracked,
        sources_loaded=sources_loaded,
    )

    first_run = not prior_loaded
    return {
        "schema": "tae_profit_memory_engine",
        "version": "v3",
        "dedupe_version": "episode_key_v1",
        "mode": "SHADOW_ONLY",
        "live_trading_impact": "NONE",
        "no_broker": True,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "initialized": first_run or (prior or {}).get("initialized", False) or first_run,
        "last_append": {
            "added_episodes": added_count,
            "skipped_duplicates": skipped_count,
            "legacy_duplicates_collapsed": legacy_collapsed,
            "source_pib_at": (pib or {}).get("generated_at"),
            "source_shadow_at": (shadow or {}).get("generated_at"),
        },
        "dedupe_policy": {
            "episode_key_fields": [
                "ticker",
                "high_pct",
                "current_pct",
                "missed_usd",
                "pib_recommendation",
                "psp_urgency",
            ],
            "timestamp_independent": True,
        },
        "sources_loaded": sources_loaded,
        "validation_verdict": (validation or {}).get("verdict"),
        "classification_rules": {
            "PROFIT_COLLAPSED": "high_pct >= 6 and current_pct <= 1",
            "PROFIT_DECAYED": "high_pct >= 4 and drawdown <= -2",
            "PROFIT_SURVIVED": "current_pct >= high_pct * 0.75 and current_pct > 0",
            "UNKNOWN_OUTCOME": "otherwise",
        },
        "bias_rules": {
            "MEMORY_PROTECT_EARLY": "collapse_rate + decay_rate >= 0.60 and observations >= 3",
            "MEMORY_HOLD_WINNERS": "survival_rate >= 0.60 and observations >= 3",
            "MEMORY_NEUTRAL": "else",
        },
        "episodes": unique_episodes,
        "ticker_memory": ticker_memory,
        "global_summary": {
            "total_raw_episodes": total_raw_after_append,
            "unique_episodes": total_episodes,
            "total_episodes": total_episodes,
            "tickers_tracked": tickers_tracked,
            "duplicates_skipped_this_run": skipped_count,
            "duplicates_ignored_in_aggregation": duplicates_ignored_in_aggregation,
            "legacy_duplicates_collapsed": legacy_collapsed,
            "top_collapse_tickers": [
                {
                    "ticker": t["ticker"],
                    "collapse_rate": t["collapse_rate"],
                    "decay_rate": t["decay_rate"],
                    "recommended_memory_bias": t["recommended_memory_bias"],
                    "observations": t["observations"],
                }
                for t in collapse_ranked[:5]
            ],
            "top_survival_tickers": [
                {
                    "ticker": t["ticker"],
                    "survival_rate": t["survival_rate"],
                    "recommended_memory_bias": t["recommended_memory_bias"],
                    "observations": t["observations"],
                }
                for t in survival_ranked[:5]
                if t.get("survival_rate", 0) > 0 or t.get("observations", 0) >= 1
            ],
            "final_verdict": final_verdict,
        },
    }


def write_outputs(report: dict[str, Any]) -> tuple[Path, Path]:
    OUTPUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    summary = report["global_summary"]
    append_info = report.get("last_append") or {}
    lines = [
        "# TAE Profit Memory Engine v3",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Mode:** {report['mode']} — {report['live_trading_impact']}",
        f"**Final verdict:** {summary['final_verdict']}",
        "",
        "> **NO BUY / NO SELL — SHADOW_ONLY research**",
        "",
        "## Global summary",
        f"- Total raw episodes: **{summary.get('total_raw_episodes', summary['total_episodes'])}**",
        f"- Unique episodes: **{summary.get('unique_episodes', summary['total_episodes'])}**",
        f"- Tickers tracked: **{summary['tickers_tracked']}**",
        f"- Episodes added this run: **{append_info.get('added_episodes', 0)}**",
        f"- Duplicates skipped this run: **{summary.get('duplicates_skipped_this_run', append_info.get('skipped_duplicates', 0))}**",
        f"- Duplicates ignored in aggregation: **{summary.get('duplicates_ignored_in_aggregation', 0)}**",
        f"- Legacy duplicates collapsed: **{summary.get('legacy_duplicates_collapsed', append_info.get('legacy_duplicates_collapsed', 0))}**",
        "",
        "## Top collapse tickers",
        "",
        "| ticker | collapse_rate | decay_rate | bias | observations |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in summary.get("top_collapse_tickers") or []:
        lines.append(
            f"| {row['ticker']} | {row['collapse_rate']} | {row['decay_rate']} | "
            f"{row['recommended_memory_bias']} | {row['observations']} |"
        )

    lines.extend(
        [
            "",
            "## Top survival tickers",
            "",
            "| ticker | survival_rate | bias | observations |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in summary.get("top_survival_tickers") or []:
        lines.append(
            f"| {row['ticker']} | {row['survival_rate']} | "
            f"{row['recommended_memory_bias']} | {row['observations']} |"
        )

    lines.extend(
        [
            "",
            "## Ticker memory",
            "",
            "| ticker | obs | collapsed | decayed | survived | collapse% | decay% | survival% | missed_usd | bias |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for t in report.get("ticker_memory") or []:
        lines.append(
            f"| {t['ticker']} | {t['observations']} | {t['collapsed_count']} | {t['decayed_count']} | "
            f"{t['survived_count']} | {t['collapse_rate']} | {t['decay_rate']} | {t['survival_rate']} | "
            f"{t['total_missed_usd']} | {t['recommended_memory_bias']} |"
        )

    lines.extend(["", "## Recent episodes", ""])
    recent = sorted(
        report.get("episodes") or [],
        key=lambda e: e.get("captured_at", ""),
        reverse=True,
    )[:20]
    for ep in recent:
        lines.append(
            f"- **{ep['ticker']}** @ {ep['captured_at']} [{ep.get('episode_key', '—')}]: "
            f"{ep['memory_label']} (high={ep['high_pct']}%, current={ep['current_pct']}%, "
            f"missed={ep['missed_usd']}) — PIB={ep.get('pib_recommendation') or '—'}"
        )

    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return OUTPUT_JSON, OUTPUT_MD


def print_summary(report: dict[str, Any]) -> None:
    summary = report["global_summary"]
    append_info = report.get("last_append") or {}
    print("===== TAE PROFIT MEMORY ENGINE v3 =====")
    print("Mode: SHADOW_ONLY — no live orders")
    print("Final verdict:", summary["final_verdict"])
    print("Total raw episodes:", summary.get("total_raw_episodes", summary["total_episodes"]))
    print("Unique episodes:", summary.get("unique_episodes", summary["total_episodes"]))
    print("Tickers tracked:", summary["tickers_tracked"])
    print("Added this run:", append_info.get("added_episodes", 0))
    print("Duplicates skipped:", summary.get("duplicates_skipped_this_run", append_info.get("skipped_duplicates", 0)))
    print("Duplicates ignored in aggregation:", summary.get("duplicates_ignored_in_aggregation", 0))
    if summary.get("top_collapse_tickers"):
        top = summary["top_collapse_tickers"][0]
        print("Top collapse ticker:", top["ticker"], f"(collapse+decay={top['collapse_rate']+top['decay_rate']:.2f})")


def main() -> int:
    report = build_memory_report()
    write_outputs(report)
    print_summary(report)
    print("Wrote:", OUTPUT_JSON, OUTPUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
