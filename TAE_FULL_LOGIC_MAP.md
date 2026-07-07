# TAE Full Logic Map

**Generated:** 2026-07-07T14:31:44+00:00

## Closed loop

Market Data → Multi-Horizon → GII → LTP → PER → PDE → Validation → Promotion Gate → Learning → DPE Adaptive → (NO LIVE PROMOTION default)

## Stages

1. market_data
2. multi_horizon_context
3. growth_intelligence
4. opportunity_cost
5. winner_lifecycle
6. profit_protection
7. ppg_appe
8. dpe
9. learning_to_profit
10. paper_experiments
11. paper_decisions
12. paper_decision_validation
13. outcome_tracking
14. learning_update
15. adaptive_recommendation
16. promotion_rejection_gate

## Edges

| id | source → target | active | impact |
| --- | --- | --- | --- |
| E01 | market_data → intraday_fade | True | 7D horizon, PROTECT |
| E02 | historical_intelligence.csv → paper_decisions | True | 2Y-20Y trends |
| E03 | profit_stack → gii | True | all PAPER actions |
| E04 | gii → ltp_bridge | True | experiments |
| E05 | ltp_bridge → paper_experiments | True | verdicts |
| E06 | paper_experiments → paper_decisions | True | PDE scoring |
| E07 | paper_decisions → decision_validation | True | PROMISING/CONTINUE/REJECT |
| E08 | decision_validation → promotion_gate | True | CONTINUE_PAPER/REJECT |
| E09 | dpe_event_bus → dpe_splitter | True | DPE philosophy jobs |
| E10 | dpe_splitter → dpe_executors | True | paper A/B |
| E11 | dpe_executors → dpe_evaluator | True | philosophy winner |
| E12 | dpe_evaluator → dpe_learning | True | learning update |
| E13 | dpe_learning → dpe_adaptive | True | PDE philosophy bias |
| E14 | confidence_evolution → paper_decisions | True | BUY/SKIP bias |
| E15 | decision_replay → paper_decisions | True | promotion caution |
| E16 | live_advisory → live_bot | True | live BUY only |
| E17 | strategic_allocation_runtime → live_advisory | False | stale allocation |
| E18 | outcome_tracking → learning_update | PARTIAL | learning |
