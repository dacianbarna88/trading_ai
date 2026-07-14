# TAE Forensic Losses — Before / After Synchronization

**Generated:** 2026-07-14  
**Verdict:** `MAIN_BRAIN_RISK_SYNCHRONIZED`

---

## Comparison table

| Case | Original action | Synchronized action | Original PnL | Counterfactual PnL | Drawdown impact |
| ---- | --------------- | ------------------- | -----------: | -----------------: | --------------: |
| LOSS-001 AMAT Jul 8 add-on | BUY → Hard Risk SELL | **SKIP_PAPER** | -$122.41 | $0.00 | avoided entry |
| LOSS-002 MU Jul 8 add-on | BUY → Hard Risk SELL | **SKIP_PAPER** | -$163.10 | $0.00 | avoided entry |
| LOSS-003 SIE.DE inherited | Hard Risk SELL | **N/A** (no PDE BUY) | -$142.49 | -$142.49 | unchanged |
| LOSS-004 QQQ protect trim | PROTECT trim | **N/A** (no PDE BUY) | -$0.61 | -$0.61 | unchanged |
| LOSS-005 AMAT Jul 9 reentry | BUY → Hard Risk SELL | **SKIP_PAPER** | -$22.99 | $0.00 | avoided entry |

**Clean replay prevented loss:** **$308.50** (entry avoidance only — no claim on SIE/QQQ inherited exposure)

---

## Per-case notes

### AMAT (LOSS-001, LOSS-005)

- **Before:** STRONG BUY +40 overwhelmed HIGH_RISK -8; GII `PROFIT_DECAY` + `collapse_probability=1.0` ignored for BUY path.
- **After:** `critical_collapse_profit_decay_high_risk` + `tighten_trail_critical_collapse` + `existing_exposure_structural_decay` → hard block.
- **Jul 9 reentry:** `persistent_critical_risk_after_hard_stop` blocks even after 30m cooldown expired.

### MU (LOSS-002)

- Same structural pattern as AMAT Jul 8 — synchronized to **SKIP_PAPER**.

### SIE.DE (LOSS-003)

- Inherited baseline exposure; no PDE BUY to synchronize. Hard Risk SELL when breach occurred remains mandatory.

### QQQ (LOSS-004)

- Immaterial PROTECT trim; no BUY contradiction. Soft penalty applied for elevated collapse under HIGH_RISK when BUY scored.

### HD (control)

- Flat-position replay: **BUY_PAPER** · `decision_coherence_status=COHERENT` · `pre_entry_hard_risk_compatible=true`

---

## STOP_REENTRY_CHURN

| Field | Jul 9 AMAT |
| --- | --- |
| Previous hard-risk SELL | 2026-07-08T21:15:45+00:00 |
| Cooldown | expired (30m) |
| Current risk | collapse=1.0, PROFIT_DECAY, HIGH_RISK |
| Reentry authorized | **false** (persistent critical risk) |
| Authorization reason | `persistent_critical_risk_after_hard_stop` |
