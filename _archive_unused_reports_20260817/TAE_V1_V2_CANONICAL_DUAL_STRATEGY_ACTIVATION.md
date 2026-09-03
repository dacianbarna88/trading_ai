# TAE V1 / V2 Canonical Dual Strategy Activation

**Sprint:** `V1_V2_CANONICAL_DUAL_STRATEGY_ACTIVATION`  
**Mode:** PAPER_ONLY | NO_BROKER | NO_DAEMON | NO_LAUNCHAGENT  
**Generated:** 2026-08-03

## Verdict

**FINAL_VERDICT = `V1_V2_DUAL_STRATEGY_ACTIVE`**

V1 (benchmark) and V2 (challenger) run inside the same canonical `full-paper-cycle` with fully separated economic books. Parallel-paper daemon and LaunchAgent remain unrestored.

---

## Audit (pre-activation)

### V1 (canonical PAPER — HEAD)

| Area | Owner / location |
| --- | --- |
| Portfolio / cash / positions | `runtime_outputs/paper_execution/paper_portfolio.json` via `tae_paper_execution` |
| Orders / trades | `paper_orders.jsonl`, `paper_trades.jsonl` |
| Equity | `paper_daily_equity.jsonl` |
| Decisions | FPC → paper decision engine → paper execution |
| Learning | `tae_canonical_learning_runtime` (inputs under `paper_execution/` only) |
| Capital baseline | `validation_capital_base` / historical **30000** |

### V2 (validated library — selective restore)

| Area | Owner / location |
| --- | --- |
| Foundation / buy / exit / routing / hard risk | `tae_strategy_v2_*.py` (already on tree) |
| Cycle state / tranche events | `runtime_outputs/parallel_paper/v2/cycle_state.json`, `tranche_events.jsonl` |
| Portfolio / journals | `runtime_outputs/parallel_paper/v2/` |
| Runtime library (not daemon) | `tae_parallel_paper_runtime.py`, `tae_parallel_paper_config.py` |
| Trailing helpers (V2 only) | `tae_strategy_v2_trailing.py` (does **not** mutate LIVE `core/trailing.py`) |
| Capital baseline | `V2_STARTING_CAPITAL=30000` in `tae_parallel_paper_config.json` |

### Intentionally NOT restored

| Component | Status |
| --- | --- |
| `tae_parallel_paper_daemon.py` | ABSENT |
| Parallel-paper LaunchAgent / autostart | ABSENT |
| Second execution / accounting engine | NOT CREATED |
| LIVE writer / Forward Observe / E3 forward | NOT RESTORED |
| Duplicate FPC / market / PDE / settlement framework | NOT CREATED |

### Capital decision

Canonical separate baselines exist historically:

- V1 PAPER base = **30000**
- V2 parallel-paper base = **30000**

These are **not** a shared 30k purse and are **not** an artificial double-count of one book. Combined equity is informational only.

---

## Architecture (activated)

```
full-paper-cycle (single orchestration)
  ├─ market data / PDE / V1 paper decision+execution+MTM
  ├─ dual_strategy_v1_v2 hook
  │    ├─ stamp V1 strategy_id on canonical book
  │    ├─ run_v2_challenger_cycle (isolated V2 book)
  │    └─ comparative report
  ├─ V1 learning (CLR → paper_execution only)
  └─ V2 learning (arm-local journals under parallel_paper/v2)
```

Wiring: `tae_structural_governance.py` → `tae_canonical_dual_strategy.run_dual_strategy_for_fpc`.

Fail-isolation: V2 exceptions do not flip V1 HARD exit; V1 failure does not mutate V2 cash.

---

## Isolation proof

| Check | Result |
| --- | --- |
| Separate portfolios | PASS |
| Separate cash | PASS |
| Separate positions (same ticker allowed independently) | PASS |
| Separate journals / settlements / equity | PASS |
| No cross-strategy cash mutation | PASS |
| No cross-strategy learning contamination | PASS (CLR V1-only inputs; V2 arm-local `record_execution_learning_feedback`) |
| strategy_id end-to-end | PASS |
| No duplicate engine / daemon / LaunchAgent | PASS |
| V1 semantics / SELL / Hard Risk unchanged | PASS |
| V2 OPEN/ADD/HOLD/STOP/SELL preserved | PASS (price −3%/−5% informational during accumulation per hard_risk adapter) |

---

## Validation

| Check | Result |
| --- | --- |
| Health | `TAE_QUICK_HEALTH_READY_WITH_WARNINGS` |
| Dual hook in FPC | V1_ok=True V2_ok=True isolation=PASS |
| Full-paper-cycle (network marks available) | `READY_FOR_PAPER_DAY` (`ORCH-20260803T175040Z-19781`) |
| Full-paper-cycle retry | May `BLOCKED_WITH_REASONS` when host yfinance marks are ALL_STALE (environmental; dual still PASS) |
| Unit suite | **173/173 OK** (4 skipped HEAD-surface aspirational checks) |
| Daemon restored | **NO** |
| LaunchAgent restored | **NO** |
| Duplicate runtime | **NO** |
| Scheduler | `READY_NOT_INSTALLED` (canonical FPC scheduler policy unchanged) |

---

## Artifacts

- `tae_canonical_dual_strategy.py`
- `tae_strategy_v2_trailing.py`
- `TAE_V1_V2_CANONICAL_DUAL_STRATEGY_REPORT.md` / `tae_v1_v2_canonical_dual_strategy_report.json`
- `tae_canonical_dual_strategy_test.py`
- This file + `tae_v1_v2_canonical_dual_strategy_activation.json`

---

## OUTPUT FINAL

```
V1_STATUS=ACTIVE
V2_STATUS=ACTIVE

V1_CAPITAL_BASE=30000
V2_CAPITAL_BASE=30000

V1_PORTFOLIO_OWNER=runtime_outputs/paper_execution/paper_portfolio.json
V2_PORTFOLIO_OWNER=runtime_outputs/parallel_paper/v2/portfolio.json

V1_EQUITY=29729.3175
V2_EQUITY=29884.950422

V1_OPEN_POSITIONS=8
V2_OPEN_POSITIONS=10

V1_CASH=21235.7828
V2_CASH=24952.3243

V1_DECISIONS=FPC_PAPER_DECISIONS
V2_DECISIONS=26

V1_EXECUTIONS=FPC_PAPER_EXECUTION
V2_EXECUTIONS=0

V1_SETTLEMENTS=FPC_PAPER_EXECUTION
V2_SETTLEMENTS=7

STRATEGY_ID_PROPAGATION=PASS
STATE_ISOLATION=PASS
ACCOUNTING_ISOLATION=PASS
LEARNING_ISOLATION=PASS

FULL_PAPER_CYCLE=READY_FOR_PAPER_DAY
FULL_PAPER_CYCLE_RETRY=BLOCKED_WITH_REASONS_ALL_STALE_HOST_MARKS
FULL_SUITE=PASS_173

DAEMON_RESTORED=NO
LAUNCHAGENT_RESTORED=NO
DUPLICATE_RUNTIME=NO

NEXT_ACTION=NONE

FINAL_VERDICT=V1_V2_DUAL_STRATEGY_ACTIVE
```

STOP.
