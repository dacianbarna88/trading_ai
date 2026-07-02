# TAE Decision Replay (X.REPLAY-1 Composer)

**Generated:** 2026-07-02T17:34:26
**Mode:** SHADOW_ONLY | **Live impact:** NONE

> SHADOW_ONLY — This report composes existing validation outputs. It does not execute trades or modify live_bot.

## Executive summary

- **Primary cause:** MISSED_PROFIT_PROTECTION
- **Secondary cause:** STOP_REENTRY_CHURN
- **Best shadow hypothesis:** shadow_trailing_1
- **Promotion readiness:** NOT_READY

Intraday gains evaporate (exit/protection gap) while rapid STOP→reentry churn compounds losses on high-score names.

## Sources loaded

- ✅ portfolio.csv
- ✅ tae_accounting_snapshot.json
- ✅ tae_profit_protection_validation.json
- ✅ tae_stop_reentry_cooldown_audit.json
- ✅ tae_knowledge_base.json
- ✅ tae_profit_attribution.json
- ✅ tae_performance_pipeline_report.json
- ✅ decision_registry.csv
- ✅ decision_replay_summary.txt

## PnL summary (accounting SSOT)
- Total trading PnL: **-22.4926 USD**
- Realized: 36.6544 USD
- Unrealized: -59.147 USD

## Failure mode attribution

- **MISSED_PROFIT_PROTECTION** (HIGH) — Shadow trailing delta vs HOLD +616.18 USD [tae_profit_protection_validation.json]
- **STOP_REENTRY_CHURN** (HIGH) — 5 immediate reentries after STOP [tae_stop_reentry_cooldown_audit.json]
- **SCORE_PERSISTENCE_AFTER_STOP** (MEDIUM) — 8 reentries with score≥80 + STRONG BUY after STOP [tae_stop_reentry_cooldown_audit.json]
- **LEGACY_CLOSED_FREEZE_DRAG** (MEDIUM) — CLOSED_FREEZE rows cumulative drag -786.26 USD [portfolio.csv]

## Counterfactual comparison

| Metric | Value |
|--------|-------|
| HOLD baseline (shadow book) | -37.13 USD |
| Best protection (shadow_trailing_1) | 579.05 USD |
| Protection Δ vs HOLD | **616.18 USD** |
| Best cooldown (cooldown_15m) net | **23.98 USD** |
| Combined (ESTIMATED) | 640.16 USD |

⚠️ Protection and cooldown effects may overlap on same tickers (e.g. MU, PM, LLY). Combined total is indicative only — not additive proof.

## Top costly decisions

1. **MU** — INTRADAY_FADE: Missed opportunity 269.72 USD; fade observations=2 | Δ est. **269.72 USD** | counterfactual: shadow_trailing_1 | MISSED_PROFIT_PROTECTION
2. **PM** — INTRADAY_FADE: Missed opportunity 184.2 USD; fade observations=3 | Δ est. **184.2 USD** | counterfactual: shadow_trailing_1 | MISSED_PROFIT_PROTECTION
3. **LLY** — INTRADAY_FADE: Missed opportunity 175.14 USD; fade observations=3 | Δ est. **175.14 USD** | counterfactual: shadow_trailing_1 | MISSED_PROFIT_PROTECTION
4. **AZN.L** — INTRADAY_FADE: Missed opportunity 123.48 USD; fade observations=2 | Δ est. **123.48 USD** | counterfactual: shadow_trailing_1 | MISSED_PROFIT_PROTECTION
5. **MRK** — INTRADAY_FADE: Missed opportunity 118.04 USD; fade observations=2 | Δ est. **118.04 USD** | counterfactual: shadow_trailing_1 | MISSED_PROFIT_PROTECTION
6. **SIE.DE** — INTRADAY_FADE: Missed opportunity 112.6 USD; fade observations=2 | Δ est. **112.6 USD** | counterfactual: shadow_trailing_1 | MISSED_PROFIT_PROTECTION
7. **MU** — STOP_REENTRY: STOP→BUY after 1.33m; outcome=REENTRY_SECOND_STOP | Δ est. **75.71 USD** | counterfactual: Apply cooldown_15m | STOP_REENTRY_CHURN
8. **AAPL** — STOP_REENTRY: STOP→BUY after 21589.08m; outcome=REENTRY_SECOND_STOP | Δ est. **40.3 USD** | counterfactual: Apply cooldown_15m | STOP_REENTRY_CHURN

## Promotion readiness
- PROTECT-2: NOT_READY (gates passed: False)
- COOLDOWN-1: NOT_READY (gates passed: False)
- **Final:** NOT_READY

## Final recommendation
- Next module: **Continue observation until >=30 PROTECT-2 samples; then X.KNOWLEDGE-1B**
- Needs more data: >=30 fade history observations (PROTECT-2 G1), >=10 stop-reentry cases (COOLDOWN-1 G1)
- Do NOT promote yet: Shadow advisory — gates not passed, DO_NOT_PROMOTE_TO_ADVISORY_YET, DO_NOT_PROMOTE_TO_LIVE

## Recommendations (SHADOW_ONLY)

- INSUFFICIENT_DATA
- DO_NOT_PROMOTE_TO_ADVISORY_YET
- CONTINUE_OBSERVATION
- TEST_TRAILING_SHADOW
- DO_NOT_PROMOTE_TO_LIVE
- TEST_15M_COOLDOWN_SHADOW

*Composer VIEW only. Upstream SSOT files remain authoritative.*
