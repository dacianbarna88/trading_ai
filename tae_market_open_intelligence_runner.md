# TAE Market Open Intelligence Runner

**Generated:** 2026-07-05T20:44:06
**Mode:** SHADOW_ONLY | **Live impact:** NONE

> PAPER_ONLY / NO_BROKER — analysis orchestration only. No orders placed.

## Executive summary

- **Overall status:** PASS
- **Modules:** 11 PASS / 0 WARN / 0 FAIL
- **Protected files unchanged:** True
- **Live trading recommendations detected:** None

## Module results

| # | Module | Script | Status | Duration | Detail |
|---|--------|--------|--------|----------|--------|
| 1 | infrastructure_health | `tae_infrastructure_health.py` | **PASS** | 0.57s | Completed successfully |
| 2 | intraday_fade_intelligence | `tae_intraday_fade_intelligence.py` | **PASS** | 4.4s | Completed successfully |
| 3 | fade_history | `tae_intraday_fade_history.py` | **PASS** | 1.49s | Completed successfully |
| 4 | intraday_discovery | `tae_intraday_discovery_engine.py` | **PASS** | 1.41s | Completed successfully |
| 5 | profit_protection_shadow | `tae_profit_protection_shadow.py` | **PASS** | 2.26s | Completed successfully |
| 6 | profit_protection_validation | `tae_profit_protection_validation.py` | **PASS** | 2.1s | Completed successfully |
| 7 | cooldown_audit | `tae_stop_reentry_cooldown_audit.py` | **PASS** | 1.66s | Completed successfully |
| 8 | decision_replay | `tae_decision_replay_composer.py` | **PASS** | 1.41s | Completed successfully |
| 9 | confidence_evolution | `tae_confidence_evolution.py` | **PASS** | 0.12s | Completed successfully |
| 10 | knowledge_base | `tae_knowledge_base.py` | **PASS** | 1.32s | Completed successfully |
| 11 | decision_governor | `tae_decision_governor.py` | **PASS** | 2.16s | Completed successfully |

## Pipeline order

1. infrastructure_health
2. intraday_fade_intelligence
3. fade_history
4. intraday_discovery
5. profit_protection_shadow
6. profit_protection_validation
7. cooldown_audit
8. decision_replay
9. confidence_evolution
10. knowledge_base
11. decision_governor

*Runner VIEW only. live_bot.py and trading logic untouched.*
