# TAE Knowledge Base

**Generated:** 2026-07-01T23:15:06
**Mode:** SHADOW_ONLY — NONE
**View type:** MATERIALIZED_VIEW

Upstream source files remain authoritative; this file is a read-only consolidation.

## Active Knowledge (CONFIRMED)
| id | subject | pattern_type | status | confidence | trend | recommendation |
| --- | --- | --- | --- | --- | --- | --- |
| kb_evidence_accounting_verified | accounting_verified | EVIDENCE_CONFIRMED | CONFIRMED | HIGH | NEW | CONTINUE_OBSERVATION |
| kb_evidence_exit_approximately_optimal | exit_approximately_optimal | EVIDENCE_CONFIRMED | CONFIRMED | HIGH | NEW | CONTINUE_OBSERVATION |
| kb_evidence_legacy_closed_freeze_distortion | legacy_closed_freeze_distortion | EVIDENCE_CONFIRMED | CONFIRMED | HIGH | NEW | CONTINUE_OBSERVATION |
| kb_evidence_profit_attribution_loss_consumption | profit_attribution_loss_consumption | EVIDENCE_CONFIRMED | CONFIRMED | HIGH | NEW | CONTINUE_OBSERVATION |
| kb_evidence_score_100_anomaly_initial | score_100_anomaly_initial | EVIDENCE_CONFIRMED | CONFIRMED | HIGH | NEW | CONTINUE_OBSERVATION |
| kb_evidence_score_100_current_not_defective | score_100_current_not_defective | EVIDENCE_CONFIRMED | CONFIRMED | HIGH | NEW | CONTINUE_OBSERVATION |
| kb_evidence_simulation_best_score_90_plus_no_closed_freeze | simulation_best_score_90_plus_no_closed_freeze | EVIDENCE_CONFIRMED | CONFIRMED | HIGH | NEW | CONTINUE_OBSERVATION |
| kb_candidate_kn_s53_00001 | kn_s53_00001 | KNOWLEDGE_CANDIDATE | CONFIRMED | HIGH | NEW | CONTINUE_OBSERVATION |
| kb_candidate_kn_d5_00002 | kn_d5_00002 | KNOWLEDGE_CANDIDATE | CONFIRMED | HIGH | NEW | CONTINUE_OBSERVATION |
| kb_candidate_kn_d5_00003 | kn_d5_00003 | KNOWLEDGE_CANDIDATE | CONFIRMED | HIGH | NEW | CONTINUE_OBSERVATION |
| kb_discovery_hyp_d2_00007 | hyp_d2_00007 | DISCOVERY_HYPOTHESIS | CONFIRMED | HIGH | NEW | CONTINUE_OBSERVATION |
| kb_discovery_hyp_d2_00005 | hyp_d2_00005 | DISCOVERY_HYPOTHESIS | CONFIRMED | HIGH | NEW | CONTINUE_OBSERVATION |
| kb_discovery_hyp_d2_00006 | hyp_d2_00006 | DISCOVERY_HYPOTHESIS | CONFIRMED | HIGH | NEW | CONTINUE_OBSERVATION |

## Experimental Knowledge
| id | subject | pattern_type | status | confidence | trend | recommendation |
| --- | --- | --- | --- | --- | --- | --- |
| kb_intraday_P001 | all | LOW_CONFIDENCE_INSUFFICIENT_SAMPLE | EXPERIMENTAL | LOW | NEW | INSUFFICIENT_DATA |
| kb_intraday_P002 | shadow_trailing_1 | BEST_SHADOW_TRAILING | EXPERIMENTAL | LOW | NEW | TEST_TRAILING_SHADOW |
| kb_intraday_P003 | PM | HIGH_FADE_TICKER | EXPERIMENTAL | LOW | NEW | PRIORITIZE_TRACKING |
| kb_intraday_P004 | LLY | HIGH_FADE_TICKER | EXPERIMENTAL | LOW | NEW | PRIORITIZE_TRACKING |
| kb_intraday_ticker_pm | PM | TICKER_FADE_LEARNING | EXPERIMENTAL | LOW | NEW | PRIORITIZE_TRACKING |
| kb_intraday_ticker_lly | LLY | TICKER_FADE_LEARNING | EXPERIMENTAL | LOW | NEW | PRIORITIZE_TRACKING |
| kb_intraday_ticker_mu | MU | TICKER_FADE_LEARNING | EXPERIMENTAL | LOW | NEW | PRIORITIZE_TRACKING |
| kb_intraday_ticker_azn_l | AZN.L | TICKER_FADE_LEARNING | EXPERIMENTAL | LOW | NEW | PRIORITIZE_TRACKING |
| kb_intraday_ticker_mrk | MRK | TICKER_FADE_LEARNING | EXPERIMENTAL | LOW | NEW | PRIORITIZE_TRACKING |
| kb_intraday_ticker_sie_de | SIE.DE | TICKER_FADE_LEARNING | EXPERIMENTAL | LOW | NEW | PRIORITIZE_TRACKING |
| kb_intraday_ticker_aapl | AAPL | TICKER_FADE_LEARNING | EXPERIMENTAL | LOW | NEW | CONTINUE_OBSERVATION |
| kb_intraday_ticker_spy | SPY | TICKER_FADE_LEARNING | EXPERIMENTAL | LOW | NEW | CONTINUE_OBSERVATION |
| kb_intraday_ticker_ulvr_l | ULVR.L | TICKER_FADE_LEARNING | EXPERIMENTAL | LOW | NEW | CONTINUE_OBSERVATION |
| kb_intraday_ticker_pg | PG | TICKER_FADE_LEARNING | EXPERIMENTAL | LOW | NEW | CONTINUE_OBSERVATION |
| kb_intraday_ticker_qqq | QQQ | TICKER_FADE_LEARNING | EXPERIMENTAL | LOW | NEW | CONTINUE_OBSERVATION |
| kb_intraday_ticker_mc_pa | MC.PA | TICKER_FADE_LEARNING | EXPERIMENTAL | LOW | NEW | CONTINUE_OBSERVATION |
| kb_learning_track_score_90_plus_no_closed_freeze | SCORE_90_PLUS_NO_CLOSED_FREEZE | PAPER_TRACKING | EXPERIMENTAL | LOW | NEW | CONTINUE_OBSERVATION |
| kb_learning_track_score_100_current_only | SCORE_100_CURRENT_ONLY | PAPER_TRACKING | EXPERIMENTAL | LOW | NEW | INSUFFICIENT_DATA |
| kb_intraday_history_dataset | portfolio | FADE_HISTORY_DATASET | EXPERIMENTAL | LOW | NEW | INSUFFICIENT_DATA |

## Growing Patterns (LEARNING)
| id | subject | pattern_type | status | confidence | trend | recommendation |
| --- | --- | --- | --- | --- | --- | --- |
| kb_learning_top_score_90_plus_no_closed_freeze | SCORE_90_PLUS_NO_CLOSED_FREEZE | TOP_RANKED_STRATEGY | LEARNING | MEDIUM | NEW | CONTINUE_OBSERVATION |
| kb_learning_conflict_evidence_engine_vs_isolated_reports | evidence_engine_vs_isolated_reports | LEARNING_CONFLICT | LEARNING | LOW | NEW | CONTINUE_OBSERVATION |
| kb_learning_conflict_daily_runner_vs_individual_steps | daily_runner_vs_individual_steps | LEARNING_CONFLICT | LEARNING | LOW | NEW | CONTINUE_OBSERVATION |
| kb_learning_conflict_orchestrator_vs_manual_demos | orchestrator_vs_manual_demos | LEARNING_CONFLICT | LEARNING | LOW | NEW | CONTINUE_OBSERVATION |
| kb_learning_conflict_phase_v_vs_phase_viii_evolution | phase_v_vs_phase_viii_evolution | LEARNING_CONFLICT | LEARNING | LOW | NEW | CONTINUE_OBSERVATION |
| kb_learning_conflict_accounting_views_vs_canonical | accounting_views_vs_canonical | LEARNING_CONFLICT | LEARNING | LOW | NEW | CONTINUE_OBSERVATION |

## Needs More Data
| id | subject | pattern_type | status | confidence | trend | recommendation |
| --- | --- | --- | --- | --- | --- | --- |
| kb_intraday_P001 | all | LOW_CONFIDENCE_INSUFFICIENT_SAMPLE | EXPERIMENTAL | LOW | NEW | INSUFFICIENT_DATA |
| kb_learning_track_score_100_current_only | SCORE_100_CURRENT_ONLY | PAPER_TRACKING | EXPERIMENTAL | LOW | NEW | INSUFFICIENT_DATA |
| kb_intraday_history_dataset | portfolio | FADE_HISTORY_DATASET | EXPERIMENTAL | LOW | NEW | INSUFFICIENT_DATA |

## Retired / Declining
_No entries._


## Summary counts
{
  "entries_total": 38,
  "by_status": {
    "EXPERIMENTAL": 19,
    "CONFIRMED": 13,
    "LEARNING": 6
  },
  "by_confidence": {
    "LOW": 24,
    "HIGH": 13,
    "MEDIUM": 1
  },
  "by_source": {
    "intraday_discovery": 16,
    "evidence_engine": 7,
    "learning_memory": 8,
    "intraday_fade_history": 1,
    "knowledge_candidates": 3,
    "discovery_hypothesis": 3
  },
  "by_trend": {
    "NEW": 38
  }
}
