# TAE V1 vs V2 Audit (READ-ONLY)

**Date:** 2026-07-29  
**HEAD:** `11e4adb13ffe3aadb2f0214e86769c3284c893eb`  
**Mode:** READ_ONLY · NO_CODE_CHANGE · NO_COMMIT · NO_PAPER_MUTATION  
**Companion JSON:** `tae_v1_vs_v2_audit.json`

---

## 1. Executive verdict

**`V2_ACTIVE_BUT_NOT_ECONOMICALLY_CLOSED`**

- **LIVE** and **canonical PAPER** run **V1** (PDE / `live_bot` / `paper_execution`). Global `STRATEGY_V2_ENABLED=false`; env cannot enable.
- **V2 is active only in isolated Parallel PAPER** (`com.tradingai.parallel-paper`, `strategy_v2_enabled_override=True`).
- V2 is **not** economically closed: **0 `ADD_TRANCHE` fills**, **0 cycles with 2+ tranches**, closed-cycle sample below winner gates, comparison engine verdict **`DATASETS_NOT_COMPARABLE_BY_DESIGN`**.
- Observed V2 PnL looks less negative than parallel V1, but **must not** be read as “V2 wins”: different notional, exit policy, and capital utilization; official winner = **null / INSUFFICIENT_SAMPLE**.

---

## 2. Runtime truth

| Runtime | Strategy | Evidence |
|---------|----------|----------|
| **LIVE_RUNTIME** | V1 | LaunchAgent `com.tradingai.live-bot` → `live_bot.py`; `TAE_RUNTIME_ID=live`; `bot_status=RUNNING`; `portfolio.csv` |
| **PAPER_RUNTIME (canonical)** | V1 | PDE → `tae_paper_execution`; `runtime_outputs/paper_execution/paper_portfolio.json`; V2 hook dormant unless payload+flag |
| **PARALLEL_PAPER** | V1 arm + V2 arm | Daemon PID in `parallel_paper_status.json` (`RUNNING_HEALTHY`, interval 300s); isolated 30k books |
| **REPLAY_RUNTIME** | Research / tests | `tae_strategy_v2_*_replay.py` — offline |
| **SHADOW_RUNTIME** | Observability | Shadow sizing / CF — not a competing capital book |

```text
V1_ENABLED=true          (LIVE + canonical PAPER + parallel V1 arm)
V2_ENABLED=true          (parallel PAPER only; global flag false)
V2_FLAG_DEFAULT=false
V2_FLAG_EFFECTIVE=false  (is_strategy_v2_enabled())
V2_ENV_OVERRIDE_ALLOWED=false
CURRENT_LIVE_STRATEGY=V1
CURRENT_PAPER_STRATEGY=V1_CANONICAL + PARALLEL_V1_AND_V2_ISOLATED
CURRENT_REPLAY_STRATEGY=OFFLINE_V2_RESEARCH
```

Parallel status (read): `V2_ACTIVATION_SCOPE=PARALLEL_PAPER`, `V2_LIVE_ENABLED=false`, `V2_CANONICAL_PAPER_ENABLED=false`, `health_status=RUNNING_HEALTHY`.

---

## 3. V1 architecture

```text
market data → indicators/signals → scoring/PDE → hard-risk → BUY/SELL auth
  → paper_execution / live_bot fills → portfolio mutation → accounting → learning journals
```

| Stage | Owner (file / function) | LIVE | PAPER |
|-------|-------------------------|------|-------|
| Signals | `live_bot.generate_signals` / PDE inputs | yes | PDE |
| Decision | PDE `build_decision(s)` | n/a | yes |
| Risk | `hard_risk_guardian` (−3% / −5%); `core.trailing` | yes | yes |
| BUY | `live_bot.buy_position` / `execute_decision` BUY_PAPER | yes | yes |
| SELL | mechanical −3%/+5% (parallel) or trailing/hard-risk (LIVE/PAPER) | yes | yes |
| Portfolio | `portfolio.csv` / `paper_portfolio.json` | LIVE SSOT | PAPER SSOT |
| Accounting | `build_accounting_snapshot` / parallel `account.json` | yes | yes |

**Canonical for LIVE BUY/SELL/stop/TP/trailing/sizing/max positions/cash:** V1 (`live_bot` + settings + guardian/trailing).

**Parallel V1 exit:** `tae_strategy_v2_routing.v1_mechanical_exit_action` (−3% stop / +5% TP).

---

## 4. V2 architecture

```text
ticker selection → OPEN_CYCLE → (ADD_TRANCHE | HOLD | STOP_ACCUMULATION)
  → exit_policy CLOSE_CYCLE → cycle_state / tranche_events → accounting → attribution
```

| Param (effective config) | Value |
|--------------------------|-------|
| `STRATEGY_V2_ENABLED` | **false** |
| `add_tranche_drop_pct` | **0.03** (vs **last tranche price**) |
| `tranche_fraction` | **0.20** of company budget |
| `max_tranches` | **5** |
| company budget | **500–2500** USD |
| `MIN_CASH_RESERVE_USD` | **500** |
| profit close | **+10%** (`minimum_cycle_profit_pct`) |
| trailing | **+5% arm / −2% from peak** (`V2_PROFIT_TRAILING_5_2`) |
| hard-risk close | **−5% critical** (adapter); −3% = `STRATEGY_STOP_V1_ONLY` (does not close V2 / does not block ADD by design) |
| `profit_reference` | `aggregate_average_cost` |

**Modules:** `tae_strategy_v2_{config,foundation,buy_policy,exit_policy,hard_risk_adapter,routing,reentry_policy}` · wired by `tae_parallel_paper_runtime._run_v2_arm`.

**State files:** `runtime_outputs/parallel_paper/v2/cycle_state.json`, `tranche_events.jsonl` (canonical V2 runtime). Default `runtime_outputs/strategy_v2/` has tranche journal only; **no** `cycle_state.json` there.

---

## 5. Ownership matrix

| Concern | V1 | V2 |
|---------|----|----|
| DECISION_OWNER | PDE / `live_bot` / `_run_v1_arm` | buy_policy + exit_policy via `_run_v2_arm` |
| BUY_OWNER | `execute_decision` / `buy_position` | `apply_open_or_add_tranche` (+ override) |
| SELL_OWNER | mechanical / trailing / SELL_PAPER | `evaluate_exit_policy` → CLOSE_CYCLE |
| RISK_OWNER | `hard_risk_guardian` + trailing | adapter + exit_policy (−5% critical) |
| POSITION_STATE_OWNER | portfolio JSON/CSV | cycle_state + portfolio arm |
| ACCOUNTING_OWNER | accounting snapshot / account.json | same pattern, arm=V2 |
| EXECUTION_OWNER | `tae_paper_execution` / live fills | same `_buy_shares`/`_sell_shares` via foundation |
| CONFIG_OWNER | settings / live constants | `tae_strategy_v2_config.json` |
| RUNTIME_STATE_FILES | `portfolio.csv`, paper journals | `v2/cycle_state.json`, `tranche_events.jsonl` |

---

## 6. V1–V2 interference

**Same-book contamination (canonical/LIVE):** V2 not mutating LIVE or canonical PAPER → **no V1-SELL-on-V2-position** there.

**Parallel isolation:** separate 30k books. Routing intentionally skips V1 −3%/+5% and V1 trailing on V2-marked cycles.

| Check | Result |
|-------|--------|
| SELL V1 closes V2 position (same book) | **No** (isolated arms) |
| Observational `V1_SELL_V2_HOLD` | **5** divergence rows (different books) |
| Hard-risk −3% blocks ADD | **By design no**; **0 ADD** anyway |
| Hard-risk −5% closes V2 | **Yes** — 3× `CLOSE_HARD_RISK_CRITICAL` |
| Trailing V1 on V2 | **Skipped** for V2 markers; V2 uses own trailing |
| MAX_POSITIONS / cash V1 vs V2 | Per-arm reserves; not shared book |
| `portfolio.csv` vs `cycle_state` | Different runtimes; parallel V2 portfolio tickers align with non-CLOSED cycles |
| Dual ownership / double accounting across arms | **No cross-arm shared execution_ids**; dual-journal within arm expected |

**Attribution of V2 closes observed:** `CLOSE_HARD_RISK_CRITICAL` (3) + `V2_PROFIT_TRAILING_5_2` (2) → **`V2_BUY + V2_SELL`**, not `V2_BUY + V1_SELL`, on the V2 book.

---

## 7. ADD versus hard-risk funnel

Thresholds: **V2 ADD = −3% vs last tranche**; **V1 strategy stop / guardian STOP = −3%**; **critical = −5%**.

| Funnel step | Count |
|-------------|------:|
| V2_REEVALUATIONS (decisions) | 5605 |
| OPEN executed | 15 |
| HOLD_PRICE_STEP_NOT_REACHED | 1936 |
| V2_HOLD_OPEN | 1974 |
| STOP_ACCUMULATION (`STOP_INVALID_DATA`) | 12 |
| CLOSE (`CLOSE_HARD_RISK_CRITICAL`) | 3 |
| ADD_TRANCHE decisions / fills | **0** |
| Cycles with 2+ tranches | **0** |
| Reconstructed marks ≤ last×0.97 while “openish” | **9** (GE/PG/SIE.DE) — still **HOLD** (`V2_HOLD_OPEN`) because cycles already **`ACCUMULATION_STOPPED`** |

**Conclusion:** V2 tranche 2–5 is **not empirically exercised**. Dominant blockers: (1) price step not reached; (2) early **`STOP_INVALID_DATA`** freezing accumulation; (3) after stop, ADD path inactive even if later −3% is reached. Not primarily “−3% hard-risk blocks ADD” in this journal (adapter allows ADD at −3%).

```text
V2_REEVALUATIONS=5605
V2_PRICE_REACHED_ADD_THRESHOLD≈9 (reconstructed; post-STOP)
V2_VALID_FOR_ADD=0
V2_BLOCKED_BY_HARD_RISK=0 (explicit ADD block)
V2_ADD_EXECUTED=0
```

---

## 8. Economic comparison

**Comparison engine:** `get_v1_v2_economic_comparison(write_report=False)` → **`verdict=DATASETS_NOT_COMPARABLE_BY_DESIGN`**  
`IDENTITY_MATCHED_OPPORTUNITIES=15`, `ECONOMICALLY_COMPARABLE_OPPORTUNITIES=0`.

| Gate | Same? |
|------|-------|
| Initial capital | Yes (30k each parallel arm) |
| Market snapshot pairing | Yes (shared snapshots) |
| Exit policy | **No** (−3/+5 mechanical vs cycle exit) |
| Risk / sizing | **No** (V1 opens ~$2500 vs V2 tranche ~$500) |
| Accounting basis | Parallel snapshots comparable *observationally*; not matched closed trades |
| Sample for winner | **No** (`sample_sufficient_for_winner=false`) |

### Observed parallel results (attribution / accounts @ 2026-07-29T17:10:15Z)

| Metric | V1 | V2 |
|--------|-----|-----|
| Account value | 29533.38 | 29932.31 |
| Realized PnL | −532.24 | −47.68 |
| Unrealized PnL | +65.62 | −20.02 |
| Net (attrib.) | −532.24 (net realized) | −47.68 |
| Return (AV vs 30k) | ≈ −1.56% | ≈ −0.23% |
| Win rate (attrib closed) | 0.222 | 0.400 |
| Profit factor (attrib) | 0.219 | 0.555 |
| Closed / open cycles | 9 / 7 | 5 / 10 |
| Capital utilization % | 7.02 | 1.67 |
| Turnover | 31904 | 2970 |
| Avg tranches/cycle | n/a (flat trades) | **1.0** |
| Cycles 2+ tranches | n/a | **0** |
| Winner declared | **null** | **null** |

**OBSERVED_RESULT:** V2 book lost less dollars with far less capital deployed.  
**NORMALIZED_RESULT:** not declared — non-comparable exposure.  
**NON_COMPARABLE_FACTORS:** sizing, exit rules, ADD never fired, matched closed=0, insufficient sample.

---

## 9. Accounting integrity

| Check | V1 parallel | V2 parallel |
|-------|-------------|-------------|
| `reconciliation_pass` | **True** | **True** |
| EXECUTION_ID_INTEGRITY | **PASS** | **PASS** |
| Cross-arm shared execution ids | **0** | **0** |
| Dual-journal equivalents | expected / deduped | expected / deduped |

```text
V1_ACCOUNTING_INTEGRITY=PASS
V2_ACCOUNTING_INTEGRITY=PASS
CROSS_STRATEGY_ACCOUNTING_CONTAMINATION=NO
```

---

## 10. Test results (read-only unittest)

| SUITE | PASS | FAIL | ERROR |
|-------|-----:|-----:|------:|
| tae_strategy_v2_foundation_test | 27 | 0 | 0 |
| tae_strategy_v2_buy_policy_test | 38 | 0 | 0 |
| tae_strategy_v2_stateful_replay_test | 17 | 0 | 0 |
| tae_strategy_v2_exit_policy_test | 24 | 0 | 0 |
| tae_v1_v2_runtime_isolation_test | 21 | 0 | 0 |
| tae_v1_v2_economic_observability_test | 24 | 0 | 0 |
| tae_parallel_paper_test | 16 | 0 | 0 |
| tae_paper_execution_test | 84 | 0 | 0 |
| tae_decision_to_execution_test | 10 | 0 | 0 |
| tae_decision_state_test | 5 | 0 | 0 |
| tae_independent_position_risk_test | 3 | 0 | 0 |
| tae_chronological_portfolio_replay_test | 16 | 0 | 0 |
| tae_canonical_cash_ssot_regression_test | 6 | 0 | 0 |
| tae_economic_integrity_test | 8 | 0 | 0 |
| hard_risk_guardian_test | MISSING module | — | — |

**Total counted:** 299 tests OK (listed suites).

---

## 11. Blockers

1. Global V2 flag off — correct for LIVE/canonical safety; V2 only via parallel override.  
2. **ADD_TRANCHE never executed** — multi-tranche thesis unproven live.  
3. **`STOP_INVALID_DATA` → ACCUMULATION_STOPPED`** shortly after many opens; freezes ADD.  
4. Economic comparison **not valid by design** (sizing/exit/exposure).  
5. Winner gates unmet (min closed cycles / observation days).  
6. Worktree dirty with many unrelated generated reports (not touched by this audit).

---

## 12. Recommendation (do not implement)

Continue **ECONOMIC_PAPER_OBSERVATION** on parallel arms. Before any “V2 better” claim: restore a **real ADD path** (investigate `STOP_INVALID_DATA`), keep books isolated, and require **economically comparable** matched opportunities + sample gates. Do **not** enable `STRATEGY_V2_ENABLED` globally or LIVE.

**Recommended next action:** `INVESTIGATE_V2_STOP_INVALID_DATA_AND_ADD_PATH` (observation/design only — out of scope for this audit).

---

## Git / worktree

```text
HEAD=11e4adb13ffe3aadb2f0214e86769c3284c893eb
WORKTREE_STATUS=DIRTY (~61 paths; mostly generated TAE_*/tae_* reports — not modified by this audit)
```
