# TAE Conversion Breakthrough Audit

**Generated:** 2026-07-21T23:10:51
**Verdict:** `BLOCKER_REJECTED`
**Mode:** PAPER_ONLY · AUDIT_FIRST

## Phase 3 — Dominant blocker

- **same_action** — 100% actionable→order failure (8/8 actionable blocked); policy_skip prevents 11 earlier but execution idempotency is acute failure
- Harmful same_action cases: 0

## Phase 1 — Complete opportunity chains (25)

### AAPL (`PDEC-AAPL-0001`)

1. **Opportunity** — missed $9.72 | signal=TAKE PROFIT (40.0)
2. **Signal** — TAKE PROFIT score=40.0
3. **PDE score** — action=PROTECT_PAPER conf=0.725 expected_delta=2.43
4. **Filters** — hard_risk:PASS (no_override); PPG:PASS (SKIP=24.3); APPE:PASS (adaptive policy applied); knowledge_rules:PASS (KB rules in evidence); confidence:PASS (confidence=0.725); conflict_resolution:PASS (winner=none); decision_state:PASS (switch_authorized=True previous=REDUCE_PAPER); cooldown:PASS (churn=HIGH cooldown_active=False); hypothesis_rules:PASS (hypothesis gate)
5. **Final action** — `PROTECT_PAPER`
6. **Order or no order** — ORDER (last=NO_CHANGE @ 2026-07-21T22:35:32+00:00)
7. **Exact blocking reason** — PROTECT_PAPER protect-only — monitor strategy=HOLD_AND_MONITOR_SHADOW; knowledge base rules: MISSED_PROFIT_PROTECTION, SCORE_DECAY_SHADOW, STOP_REENTRY_CHURN, TRAILING_1_PROTECTION_HYPOTHESIS; named c

### ABBV (`PDEC-ABBV-0002`)

1. **Opportunity** — missed $0.00 | signal=STRONG BUY (100.0)
2. **Signal** — STRONG BUY score=100.0
3. **PDE score** — action=PROTECT_PAPER conf=0.554 expected_delta=0.00
4. **Filters** — hard_risk:PASS (no_override); PPG:PASS (SKIP=24.3); APPE:PASS (adaptive policy applied); knowledge_rules:PASS (KB rules in evidence); confidence:PASS (confidence=0.554); conflict_resolution:PASS (winner=none); decision_state:PASS (switch_authorized=True previous=BUY_PAPER); cooldown:PASS (churn=HIGH cooldown_active=False); hypothesis_rules:PASS (hypothesis gate)
5. **Final action** — `PROTECT_PAPER`
6. **Order or no order** — NO_ORDER (last=NO_CHANGE @ 2026-07-21T22:35:23+00:00)
7. **Exact blocking reason** — already_processed_same_action

### AIR.PA (`PDEC-AIR.PA-0003`)

1. **Opportunity** — missed $0.00 | signal=WAIT (0.0)
2. **Signal** — WAIT score=0.0
3. **PDE score** — action=HOLD_PAPER conf=0.676 expected_delta=0.00
4. **Filters** — hard_risk:PASS (no_override); PPG:PASS (SKIP=42.3); APPE:PASS (adaptive policy applied); knowledge_rules:PASS (KB rules in evidence); confidence:PASS (confidence=0.676); conflict_resolution:PASS (winner=none); decision_state:PASS (switch_authorized=True previous=BUY_PAPER); cooldown:PASS (churn=HIGH cooldown_active=False); hypothesis_rules:PASS (hypothesis gate)
5. **Final action** — `HOLD_PAPER`
6. **Order or no order** — NO_ORDER (last=NO_CHANGE @ 2026-07-21T22:35:23+00:00)
7. **Exact blocking reason** — HOLD_PAPER — no trade order required

### ALV.DE (`PDEC-ALV.DE-0004`)

1. **Opportunity** — missed $0.00 | signal=WAIT (40.0)
2. **Signal** — WAIT score=40.0
3. **PDE score** — action=SKIP_PAPER conf=0.346 expected_delta=0.00
4. **Filters** — hard_risk:PASS (no_override); PPG:BLOCK (SKIP=37.1); APPE:PASS (adaptive policy applied); knowledge_rules:PASS (KB rules in evidence); confidence:PASS (confidence=0.346); conflict_resolution:PASS (winner=none); decision_state:PASS (switch_authorized=True previous=SKIP_PAPER); hypothesis_rules:BLOCK (hypothesis gate)
5. **Final action** — `SKIP_PAPER`
6. **Order or no order** — NO_ORDER (last=NO_CHANGE @ 2026-07-21T22:35:23+00:00)
7. **Exact blocking reason** — PDE action SKIP_PAPER — execution not attempted for trade

### AMAT (`PDEC-AMAT-0005`)

1. **Opportunity** — missed $222.51 | signal=WAIT (40.0)
2. **Signal** — WAIT score=40.0
3. **PDE score** — action=SKIP_PAPER conf=0.796 expected_delta=35.25
4. **Filters** — hard_risk:PASS (no_override); PPG:BLOCK (SKIP=82.1); APPE:PASS (adaptive policy applied); knowledge_rules:PASS (KB rules in evidence); confidence:PASS (confidence=0.796); conflict_resolution:PASS (winner=none); decision_state:PASS (switch_authorized=True previous=SELL_PAPER); cooldown:PASS (churn=HIGH cooldown_active=False); hypothesis_rules:BLOCK (hypothesis gate)
5. **Final action** — `SKIP_PAPER`
6. **Order or no order** — NO_ORDER (last=NO_CHANGE @ 2026-07-21T22:35:23+00:00)
7. **Exact blocking reason** — PDE action SKIP_PAPER — execution not attempted for trade

### AZN.L (`PDEC-AZN.L-0006`)

1. **Opportunity** — missed $0.00 | signal=WAIT (0.0)
2. **Signal** — WAIT score=0.0
3. **PDE score** — action=SKIP_PAPER conf=0.346 expected_delta=0.00
4. **Filters** — hard_risk:PASS (no_override); PPG:BLOCK (SKIP=37.1); APPE:PASS (adaptive policy applied); knowledge_rules:PASS (KB rules in evidence); confidence:PASS (confidence=0.346); conflict_resolution:PASS (winner=none); decision_state:PASS (switch_authorized=True previous=SKIP_PAPER); hypothesis_rules:BLOCK (hypothesis gate)
5. **Final action** — `SKIP_PAPER`
6. **Order or no order** — NO_ORDER (last=NO_CHANGE @ 2026-07-21T22:35:23+00:00)
7. **Exact blocking reason** — PDE action SKIP_PAPER — execution not attempted for trade

### BP.L (`PDEC-BP.L-0007`)

1. **Opportunity** — missed $0.00 | signal=TAKE PROFIT (0.0)
2. **Signal** — TAKE PROFIT score=0.0
3. **PDE score** — action=SKIP_PAPER conf=0.346 expected_delta=0.00
4. **Filters** — hard_risk:PASS (no_override); PPG:BLOCK (SKIP=37.1); APPE:PASS (adaptive policy applied); knowledge_rules:PASS (KB rules in evidence); confidence:PASS (confidence=0.346); conflict_resolution:PASS (winner=none); decision_state:PASS (switch_authorized=True previous=SKIP_PAPER); hypothesis_rules:BLOCK (hypothesis gate)
5. **Final action** — `SKIP_PAPER`
6. **Order or no order** — NO_ORDER (last=NO_CHANGE @ 2026-07-21T22:35:23+00:00)
7. **Exact blocking reason** — PDE action SKIP_PAPER — execution not attempted for trade

### DIA (`PDEC-DIA-0008`)

1. **Opportunity** — missed $0.00 | signal=STRONG BUY (80.0)
2. **Signal** — STRONG BUY score=80.0
3. **PDE score** — action=PROTECT_PAPER conf=0.635 expected_delta=0.00
4. **Filters** — hard_risk:PASS (no_override); PPG:PASS (SKIP=24.3); APPE:PASS (adaptive policy applied); knowledge_rules:PASS (KB rules in evidence); confidence:PASS (confidence=0.635); conflict_resolution:PASS (winner=none); decision_state:PASS (switch_authorized=True previous=BUY_PAPER); cooldown:PASS (churn=HIGH cooldown_active=False); hypothesis_rules:PASS (hypothesis gate)
5. **Final action** — `PROTECT_PAPER`
6. **Order or no order** — NO_ORDER (last=NO_CHANGE @ 2026-07-21T22:35:23+00:00)
7. **Exact blocking reason** — already_processed_same_action

### GE (`PDEC-GE-0009`)

1. **Opportunity** — missed $0.00 | signal=WAIT (40.0)
2. **Signal** — WAIT score=40.0
3. **PDE score** — action=SKIP_PAPER conf=0.346 expected_delta=0.00
4. **Filters** — hard_risk:PASS (no_override); PPG:BLOCK (SKIP=37.1); APPE:PASS (adaptive policy applied); knowledge_rules:PASS (KB rules in evidence); confidence:PASS (confidence=0.346); conflict_resolution:PASS (winner=none); decision_state:PASS (switch_authorized=True previous=SELL_PAPER); cooldown:PASS (churn=HIGH cooldown_active=False); hypothesis_rules:BLOCK (hypothesis gate)
5. **Final action** — `SKIP_PAPER`
6. **Order or no order** — NO_ORDER (last=NO_CHANGE @ 2026-07-21T22:35:23+00:00)
7. **Exact blocking reason** — PDE action SKIP_PAPER — execution not attempted for trade

### HD (`PDEC-HD-0010`)

1. **Opportunity** — missed $0.00 | signal=WAIT (40.0)
2. **Signal** — WAIT score=40.0
3. **PDE score** — action=PROTECT_PAPER conf=0.634 expected_delta=0.00
4. **Filters** — hard_risk:PASS (no_override); PPG:PASS (SKIP=24.3); APPE:PASS (adaptive policy applied); knowledge_rules:PASS (KB rules in evidence); confidence:PASS (confidence=0.634); conflict_resolution:PASS (winner=none); decision_state:PASS (switch_authorized=True previous=BUY_PAPER); cooldown:PASS (churn=HIGH cooldown_active=False); hypothesis_rules:PASS (hypothesis gate)
5. **Final action** — `PROTECT_PAPER`
6. **Order or no order** — NO_ORDER (last=NO_CHANGE @ 2026-07-21T22:35:23+00:00)
7. **Exact blocking reason** — already_processed_same_action

### HSBA.L (`PDEC-HSBA.L-0011`)

1. **Opportunity** — missed $235.96 | signal=WAIT (0.0)
2. **Signal** — WAIT score=0.0
3. **PDE score** — action=REDUCE_PAPER conf=0.950 expected_delta=37.38
4. **Filters** — hard_risk:PASS (no_override); PPG:PASS (SKIP=87.3); APPE:PASS (adaptive policy applied); knowledge_rules:PASS (KB rules in evidence); confidence:PASS (confidence=0.950); conflict_resolution:PASS (winner=none); decision_state:PASS (switch_authorized=True previous=REDUCE_PAPER); hypothesis_rules:PASS (hypothesis gate)
5. **Final action** — `REDUCE_PAPER`
6. **Order or no order** — NO_ORDER (last=NO_CHANGE @ 2026-07-21T22:35:23+00:00)
7. **Exact blocking reason** — already_processed_same_action

### LLY (`PDEC-LLY-0012`)

1. **Opportunity** — missed $45.64 | signal=STRONG BUY (80.0)
2. **Signal** — STRONG BUY score=80.0
3. **PDE score** — action=PROTECT_PAPER conf=0.727 expected_delta=4.96
4. **Filters** — hard_risk:PASS (no_override); PPG:PASS (SKIP=24.3); APPE:PASS (adaptive policy applied); knowledge_rules:PASS (KB rules in evidence); confidence:PASS (confidence=0.727); conflict_resolution:PASS (winner=none); decision_state:PASS (switch_authorized=True previous=BUY_PAPER); cooldown:PASS (churn=HIGH cooldown_active=False); hypothesis_rules:PASS (hypothesis gate)
5. **Final action** — `PROTECT_PAPER`
6. **Order or no order** — NO_ORDER (last=NO_CHANGE @ 2026-07-21T22:35:23+00:00)
7. **Exact blocking reason** — already_processed_same_action

### MC.PA (`PDEC-MC.PA-0013`)

1. **Opportunity** — missed $10.50 | signal=WAIT (60.0)
2. **Signal** — WAIT score=60.0
3. **PDE score** — action=PROTECT_PAPER conf=0.874 expected_delta=1.05
4. **Filters** — hard_risk:PASS (no_override); PPG:PASS (SKIP=69.3); APPE:PASS (adaptive policy applied); knowledge_rules:PASS (KB rules in evidence); confidence:PASS (confidence=0.874); conflict_resolution:PASS (winner=none); decision_state:PASS (switch_authorized=True previous=PROTECT_PAPER); cooldown:PASS (churn=HIGH cooldown_active=False); hypothesis_rules:PASS (hypothesis gate)
5. **Final action** — `PROTECT_PAPER`
6. **Order or no order** — NO_ORDER (last=NO_CHANGE @ 2026-07-21T22:35:23+00:00)
7. **Exact blocking reason** — already_processed_same_action

### MRK (`PDEC-MRK-0014`)

1. **Opportunity** — missed $1.76 | signal=STRONG BUY (80.0)
2. **Signal** — STRONG BUY score=80.0
3. **PDE score** — action=HOLD_PAPER conf=0.811 expected_delta=0.32
4. **Filters** — hard_risk:PASS (no_override); PPG:PASS (SKIP=24.3); APPE:PASS (adaptive policy applied); knowledge_rules:PASS (KB rules in evidence); confidence:PASS (confidence=0.811); conflict_resolution:PASS (winner=none); decision_state:PASS (switch_authorized=True previous=BUY_PAPER); cooldown:PASS (churn=MEDIUM cooldown_active=False); hypothesis_rules:PASS (hypothesis gate)
5. **Final action** — `HOLD_PAPER`
6. **Order or no order** — NO_ORDER (last=NO_CHANGE @ 2026-07-21T22:35:23+00:00)
7. **Exact blocking reason** — already_processed_same_action

### MSFT (`PDEC-MSFT-0015`)

1. **Opportunity** — missed $0.00 | signal=WAIT (0.0)
2. **Signal** — WAIT score=0.0
3. **PDE score** — action=SKIP_PAPER conf=0.346 expected_delta=0.00
4. **Filters** — hard_risk:PASS (no_override); PPG:BLOCK (SKIP=37.1); APPE:PASS (adaptive policy applied); knowledge_rules:PASS (KB rules in evidence); confidence:PASS (confidence=0.346); conflict_resolution:PASS (winner=none); decision_state:PASS (switch_authorized=True previous=SKIP_PAPER); hypothesis_rules:BLOCK (hypothesis gate)
5. **Final action** — `SKIP_PAPER`
6. **Order or no order** — NO_ORDER (last=NO_CHANGE @ 2026-07-21T22:35:23+00:00)
7. **Exact blocking reason** — PDE action SKIP_PAPER — execution not attempted for trade

### MU (`PDEC-MU-0016`)

1. **Opportunity** — missed $226.61 | signal=WAIT (40.0)
2. **Signal** — WAIT score=40.0
3. **PDE score** — action=SKIP_PAPER conf=0.796 expected_delta=35.90
4. **Filters** — hard_risk:PASS (no_override); PPG:BLOCK (SKIP=82.1); APPE:PASS (adaptive policy applied); knowledge_rules:PASS (KB rules in evidence); confidence:PASS (confidence=0.796); conflict_resolution:PASS (winner=none); decision_state:PASS (switch_authorized=True previous=SELL_PAPER); cooldown:PASS (churn=MEDIUM cooldown_active=False); hypothesis_rules:BLOCK (hypothesis gate)
5. **Final action** — `SKIP_PAPER`
6. **Order or no order** — NO_ORDER (last=NO_CHANGE @ 2026-07-21T22:35:23+00:00)
7. **Exact blocking reason** — PDE action SKIP_PAPER — execution not attempted for trade

### NVDA (`PDEC-NVDA-0017`)

1. **Opportunity** — missed $0.00 | signal=WAIT (60.0)
2. **Signal** — WAIT score=60.0
3. **PDE score** — action=SKIP_PAPER conf=0.346 expected_delta=0.00
4. **Filters** — hard_risk:PASS (no_override); PPG:BLOCK (SKIP=37.1); APPE:PASS (adaptive policy applied); knowledge_rules:PASS (KB rules in evidence); confidence:PASS (confidence=0.346); conflict_resolution:PASS (winner=none); decision_state:PASS (switch_authorized=True previous=SELL_PAPER); cooldown:PASS (churn=HIGH cooldown_active=False); hypothesis_rules:BLOCK (hypothesis gate)
5. **Final action** — `SKIP_PAPER`
6. **Order or no order** — NO_ORDER (last=NO_CHANGE @ 2026-07-21T22:35:23+00:00)
7. **Exact blocking reason** — PDE action SKIP_PAPER — execution not attempted for trade

### PG (`PDEC-PG-0018`)

1. **Opportunity** — missed $4.47 | signal=STRONG BUY (100.0)
2. **Signal** — STRONG BUY score=100.0
3. **PDE score** — action=HOLD_PAPER conf=0.816 expected_delta=0.83
4. **Filters** — hard_risk:PASS (no_override); PPG:PASS (SKIP=24.3); APPE:PASS (adaptive policy applied); knowledge_rules:PASS (KB rules in evidence); confidence:PASS (confidence=0.816); conflict_resolution:PASS (winner=none); decision_state:PASS (switch_authorized=True previous=REDUCE_PAPER); hypothesis_rules:PASS (hypothesis gate)
5. **Final action** — `HOLD_PAPER`
6. **Order or no order** — NO_ORDER (last=NO_CHANGE @ 2026-07-21T22:35:23+00:00)
7. **Exact blocking reason** — HOLD_PAPER — no trade order required

### PM (`PDEC-PM-0019`)

1. **Opportunity** — missed $22.25 | signal=STRONG BUY (100.0)
2. **Signal** — STRONG BUY score=100.0
3. **PDE score** — action=HOLD_PAPER conf=0.869 expected_delta=4.27
4. **Filters** — hard_risk:PASS (no_override); PPG:PASS (SKIP=24.3); APPE:PASS (adaptive policy applied); knowledge_rules:PASS (KB rules in evidence); confidence:PASS (confidence=0.869); conflict_resolution:PASS (winner=none); decision_state:PASS (switch_authorized=True previous=BUY_PAPER); cooldown:PASS (churn=MEDIUM cooldown_active=False); hypothesis_rules:PASS (hypothesis gate)
5. **Final action** — `HOLD_PAPER`
6. **Order or no order** — NO_ORDER (last=NO_CHANGE @ 2026-07-21T22:35:23+00:00)
7. **Exact blocking reason** — already_processed_same_action

### QQQ (`PDEC-QQQ-0020`)

1. **Opportunity** — missed $7.86 | signal=WAIT (0.0)
2. **Signal** — WAIT score=0.0
3. **PDE score** — action=SKIP_PAPER conf=0.541 expected_delta=0.00
4. **Filters** — hard_risk:PASS (no_override); PPG:BLOCK (SKIP=56.6); APPE:PASS (adaptive policy applied); knowledge_rules:PASS (KB rules in evidence); confidence:PASS (confidence=0.541); conflict_resolution:PASS (winner=none); decision_state:PASS (switch_authorized=True previous=SELL_PAPER); cooldown:PASS (churn=MEDIUM cooldown_active=False); hypothesis_rules:BLOCK (hypothesis gate)
5. **Final action** — `SKIP_PAPER`
6. **Order or no order** — NO_ORDER (last=NO_CHANGE @ 2026-07-21T22:35:23+00:00)
7. **Exact blocking reason** — PDE action SKIP_PAPER — execution not attempted for trade

### SAP.DE (`PDEC-SAP.DE-0021`)

1. **Opportunity** — missed $0.00 | signal=WAIT (40.0)
2. **Signal** — WAIT score=40.0
3. **PDE score** — action=SKIP_PAPER conf=0.796 expected_delta=0.00
4. **Filters** — hard_risk:PASS (no_override); PPG:BLOCK (SKIP=82.1); APPE:PASS (adaptive policy applied); knowledge_rules:PASS (KB rules in evidence); confidence:PASS (confidence=0.796); conflict_resolution:PASS (winner=none); decision_state:PASS (switch_authorized=True previous=SKIP_PAPER); hypothesis_rules:BLOCK (hypothesis gate)
5. **Final action** — `SKIP_PAPER`
6. **Order or no order** — NO_ORDER (last=NO_CHANGE @ 2026-07-21T22:35:23+00:00)
7. **Exact blocking reason** — PDE action SKIP_PAPER — execution not attempted for trade

### SHEL.L (`PDEC-SHEL.L-0022`)

1. **Opportunity** — missed $0.00 | signal=TAKE PROFIT (0.0)
2. **Signal** — TAKE PROFIT score=0.0
3. **PDE score** — action=PROTECT_PAPER conf=0.554 expected_delta=0.00
4. **Filters** — hard_risk:PASS (no_override); PPG:PASS (SKIP=24.3); APPE:PASS (adaptive policy applied); knowledge_rules:PASS (KB rules in evidence); confidence:PASS (confidence=0.554); conflict_resolution:PASS (winner=none); decision_state:PASS (switch_authorized=True previous=BUY_PAPER); cooldown:PASS (churn=MEDIUM cooldown_active=False); hypothesis_rules:PASS (hypothesis gate)
5. **Final action** — `PROTECT_PAPER`
6. **Order or no order** — NO_ORDER (last=NO_CHANGE @ 2026-07-21T22:35:23+00:00)
7. **Exact blocking reason** — already_processed_same_action

### SIE.DE (`PDEC-SIE.DE-0023`)

1. **Opportunity** — missed $20.42 | signal=WAIT (40.0)
2. **Signal** — WAIT score=40.0
3. **PDE score** — action=SKIP_PAPER conf=0.346 expected_delta=0.00
4. **Filters** — hard_risk:PASS (no_override); PPG:BLOCK (SKIP=37.1); APPE:PASS (adaptive policy applied); knowledge_rules:PASS (KB rules in evidence); confidence:PASS (confidence=0.346); conflict_resolution:PASS (winner=none); decision_state:PASS (switch_authorized=True previous=SELL_PAPER); cooldown:PASS (churn=HIGH cooldown_active=False); hypothesis_rules:BLOCK (hypothesis gate)
5. **Final action** — `SKIP_PAPER`
6. **Order or no order** — NO_ORDER (last=NO_CHANGE @ 2026-07-21T22:35:23+00:00)
7. **Exact blocking reason** — PDE action SKIP_PAPER — execution not attempted for trade

### SPY (`PDEC-SPY-0024`)

1. **Opportunity** — missed $22.02 | signal=STRONG BUY (100.0)
2. **Signal** — STRONG BUY score=100.0
3. **PDE score** — action=HOLD_PAPER conf=0.933 expected_delta=4.37
4. **Filters** — hard_risk:PASS (no_override); PPG:PASS (SKIP=24.3); APPE:PASS (adaptive policy applied); knowledge_rules:PASS (KB rules in evidence); confidence:PASS (confidence=0.933); conflict_resolution:PASS (winner=none); decision_state:PASS (switch_authorized=True previous=HOLD_PAPER); hypothesis_rules:PASS (hypothesis gate)
5. **Final action** — `HOLD_PAPER`
6. **Order or no order** — NO_ORDER (last=NO_CHANGE @ 2026-07-21T22:35:23+00:00)
7. **Exact blocking reason** — already_processed_same_action

### ULVR.L (`PDEC-ULVR.L-0025`)

1. **Opportunity** — missed $0.00 | signal=WAIT (60.0)
2. **Signal** — WAIT score=60.0
3. **PDE score** — action=PROTECT_PAPER conf=0.715 expected_delta=0.00
4. **Filters** — hard_risk:PASS (no_override); PPG:PASS (SKIP=24.3); APPE:PASS (adaptive policy applied); knowledge_rules:PASS (KB rules in evidence); confidence:PASS (confidence=0.715); conflict_resolution:PASS (winner=none); decision_state:PASS (switch_authorized=True previous=BUY_PAPER); cooldown:PASS (churn=MEDIUM cooldown_active=False); hypothesis_rules:PASS (hypothesis gate)
5. **Final action** — `PROTECT_PAPER`
6. **Order or no order** — NO_ORDER (last=NO_CHANGE @ 2026-07-21T22:35:23+00:00)
7. **Exact blocking reason** — already_processed_same_action

## Phase 5 — Promotion

- Verdict: **BLOCKER_REJECTED**
- Reason: Promotion criteria failed: higher_profit, conversion_improved. Challenger improves conversion plumbing but lacks closed-trade profit uplift in replay.

### Checks

- higher_profit: **False**
- equal_or_lower_drawdown: **True**
- profit_integrity_pass: **True**
- reconciliation_pass: **True**
- no_hard_risk_regression: **True**
- no_decision_state_regression: **True**
- no_churn_regression: **True**
- conversion_improved: **False**
