# TAE Decision State & Decision Ownership Audit

**Generated:** 2026-07-08T19:15:00+00:00  
**Mode:** READ_ONLY — no code changes, no commit  
**Branch context:** post conflict-resolution wiring (`d55a456`)

---

## 1. Executive Verdict

### **DECISION_STATE_EXISTS_BUT_NOT_CONNECTED**

TAE has **partial decision-related state** (PAPER portfolio, execution journals, `processed_decision_ids`, longitudinal memory, DPE events) — but **no connected per-ticker active decision owner**. Each cycle, PDE recomputes actions from current intelligence + positions. Execution **intentionally re-runs** when the same `decision_id` changes action (`action_changed:BUY→SELL`), with **no hysteresis, no hold period, and no cooldown** preventing BUY→SELL→BUY churn.

**Oscillation risk: HIGH**

**Master Decision Authority needed?** **No** — not yet. Safest path is to **connect existing execution logs and portfolio state** into PDE/conflict resolution with hold-period rules. A new top-level authority would duplicate PDE + governance.

---

## 2. Core Answer

| Question | Answer |
|----------|--------|
| When TAE makes a PAPER decision, who owns it? | **Nobody persistently.** PDE owns the *current cycle snapshot*; execution owns *fills*; hard risk owns *stop-loss overrides*. |
| Where is it stored? | `paper_decisions.json` (overwritten each run) + `paper_orders.jsonl` (append) + `paper_portfolio.json` (positions). |
| What rules allow it to change? | Any new PDE score pass; hard risk override; execution `action_changed` path on same `decision_id`. |

---

## 3. Answers to All 18 Questions

| # | Question | Answer |
|---|----------|--------|
| 1 | Persistent decision state? | **Partial** — positions + journals + dedup set; no active decision registry |
| 2 | Active decision per ticker? | **`paper_decisions.json`** (current cycle only); positions in **`paper_portfolio.json`** |
| 3 | Registry or append-only logs? | **Both, disconnected.** Orders/trades append; PDE jsonl **overwritten**; legacy `decision_registry.csv` separate |
| 4 | PDE reads previous action? | **No** — only `paper_positions`, signals, GII, etc. |
| 5 | Conflict resolution reads previous action? | **No** — fresh EV table each run |
| 6 | Execution knows action changed? | **Yes** — `should_execute_decision()` + `action_changed` flag |
| 7 | Who can change a decision? | PDE (soft), hard_risk (hard SELL), execution (re-apply on change) |
| 8 | Hysteresis / switch threshold? | **No** |
| 9 | Cooldown preventing BUY→SELL→BUY? | **No** |
| 10 | `STOP_REENTRY_CHURN` enforced? | **No** — PDE score delta only (`BUY_PAPER -6`, `SKIP_PAPER +4`) |
| 11 | `processed_decision_ids` as state? | **Execution idempotency**, not ownership — allows re-exec when action flips |
| 12 | DPE event bus state? | **Events only** — immutable snapshots, not active decision |
| 13 | Longitudinal memory ownership? | **Future weights only** — ingest skips same `decision_id` on action change |
| 14 | Investment Council owns decisions? | **No** — synthesis only (`synthesis_only: true`) |
| 15 | Structural governance owns decisions? | **No** — orchestrates PDE/execution; no decision store |
| 16 | AMAT/AIR.PA/DIA/GE/HD BUY then SELL? | See §5 — hard risk (AMAT) vs held-position SELL scoring (others) |
| 17 | Oscillation cause? | **Missing ownership + no cooldown + layer conflict** (conflict says BUY, PDE says SELL); AMAT also **hard stop** |
| 18 | Minimal safe fix? | See §7 — wire existing logs, no new engine |

---

## 4. Active-State Map

| Artifact | Producer | Consumer | State type | → PDE | → Execution | → Governance |
|----------|----------|----------|------------|-------|-------------|--------------|
| `paper_decisions.json` | PDE | execution, council, memory | cycle snapshot | — | ✅ | ✅ |
| `paper_decisions.jsonl` | PDE | *(none durable)* | **overwritten** each run | — | — | — |
| `paper_portfolio.json` | execution | PDE, conflict, MTM | **position state** | ✅ | ✅ | ✅ |
| `paper_orders.jsonl` | execution | execution dedup, memory | append journal | — | ✅ | — |
| `paper_trades.jsonl` | execution | memory, reconciliation | append journal | — | ✅ | — |
| `processed_decision_ids` | execution | execution | dedup set | — | ✅ | — |
| `longitudinal_memory/decisions.jsonl` | outcome memory | hints → PDE | learning record | ✅ | — | ✅ |
| `dpe/decision_events.jsonl` | event bus | DPE splitter | event log | — | — | ✅ |
| `conflict_resolution/conflicts.json` | conflict layer | PDE bias | EV snapshot | ✅ | — | ✅ |
| `decision_registry.csv` | legacy | replay engine | live registry | — | — | — |
| `tae_decision_replay.json` | replay composer | PDE named rules | advisory | ✅ | — | — |
| `tae_stop_reentry_cooldown_audit.json` | cooldown audit | governor, PDE bias | audit | ✅* | — | — |

\*Evidence bias only — not enforced block.

---

## 5. Decision-Change Chain (AMAT / AIR.PA / DIA / GE / HD)

Evidence from `paper_orders.jsonl` and latest `paper_decisions.json` (2026-07-08).

### AMAT — hard risk driven

| Time | Previous | New | Who changed | Allowed by |
|------|----------|-----|-------------|------------|
| 18:51:45 | SKIP_PAPER | **BUY_PAPER** | PDE + conflict resolution | Soft — HIGH_RISK BUY EV mitigation |
| 18:56:49 | BUY_PAPER | **SELL_PAPER** | `hard_risk_discipline` | **Hard — `HARD_STOP_LOSS_-3` at -3.80%** |

- PDE evidence: `HARD RISK override … SELL_PAPER (before soft logic)`
- Conflict EV winner: N/A (hard path short-circuits)
- **Root cause:** Legitimate hard rule after conflict-enabled BUY; not a bug, but shows **no hold period** between soft BUY and hard SELL.

### AIR.PA / DIA / GE / HD — layer conflict + missing ownership

| Time | Previous | New | Who changed | Allowed by |
|------|----------|-----|-------------|------------|
| 18:51:45 | SKIP_PAPER | **BUY_PAPER** | PDE + conflict (`EV_OPTIMIZER`, `high_risk_buy_allowed`) | Soft — conflict bias |
| 18:56:49 | BUY_PAPER | **SELL_PAPER** | PDE `score_actions_for_ticker` (held branch) | Soft — **not** hard rule |

**PDE evidence (all four):**
- `low capital_efficiency=0.0`
- Knowledge rules: `MISSED_PROFIT_PROTECTION`, `SCORE_DECAY_SHADOW`, **`STOP_REENTRY_CHURN`**, `TRAILING_1_PROTECTION_HYPOTHESIS`
- `loss_discipline.preferred: SELL_PAPER` (sell_score > protect_score)
- **`winning_scenario: BUY_PAPER`** / `final_authority: EV_OPTIMIZER` — conflict **disagrees** with final action

**Root cause stack:**
1. Cycle 1: flat → BUY (conflict + PDE bias).
2. Cycle 2: position now held → GII `cap_eff=0` adds **+35 SELL** (`tae_paper_decision_engine.py` held branch).
3. Conflict EV bias **not binding** — PDE max-score still wins with SELL.
4. **No read of prior cycle action** — system treats as fresh optimization.
5. Execution **allows flip** via `action_changed:BUY_PAPER->SELL_PAPER`.
6. **`STOP_REENTRY_CHURN` in evidence but only -6 BUY score** — did not block re-BUY or subsequent SELL.

---

## 6. Key Mechanism: `decision_id` + `processed_decision_ids`

```1013:1027:tae_paper_execution.py
def should_execute_decision(
    decision_id: str,
    action: str,
    *,
    processed: set[str],
    last_orders: dict[str, dict[str, Any]],
) -> tuple[bool, str]:
    if not decision_id:
        return False, "missing decision_id"
    if decision_id not in processed:
        return True, "new_decision"
    prior_action = _s((last_orders.get(decision_id) or {}).get("action")).upper()
    if prior_action and prior_action != action:
        return True, f"action_changed:{prior_action}->{action}"
    return False, "already_processed_same_action"
```

- `decision_id` = `PDEC-{TICKER}-{seq:04d}` — **stable per ticker** when universe order stable (e.g. `PDEC-AMAT-0005`).
- `processed_decision_ids` = "have we ever executed this id" — **not** "what is the active action".
- **Design intent:** skip duplicate same-action runs; **re-execute on action change**.
- **Side effect:** BUY→SELL→BUY churn is **explicitly permitted** every cycle.

PDE does **not** read `processed_decision_ids` or last order when scoring.

---

## 7. `STOP_REENTRY_CHURN` — Evidence, Not Enforcement

```106:113:tae_paper_decision_engine.py
NAMED_RULE_SCORE_DELTAS: dict[str, dict[str, float]] = {
    "SCORE_DECAY_SHADOW": {"BUY_PAPER": -8.0, "SKIP_PAPER": 5.0},
    "STOP_REENTRY_CHURN": {"BUY_PAPER": -6.0, "SKIP_PAPER": 4.0},
    ...
}
```

- Sourced from `tae_decision_replay.json` / confidence evolution / cooldown audit.
- `tae_decision_governor.py` uses churn for **advisory posture** — not PDE hard block.
- `tae_stop_reentry_cooldown_audit.json` exists but **does not gate PDE or execution**.

---

## 8. Longitudinal Memory Gap

- Ingest keyed by `decision_id` — **skips if id already in records**.
- Same `PDEC-AIR.PA-0003` stays at first ingested action (`SKIP_PAPER`) even after BUY/SELL flips.
- `adaptation_hints.json` applies aggregate biases (e.g. `SELL_PAPER: -0.5`) — **not per-ticker last action**.
- Affects **future weight tuning**, not **current decision ownership**.

---

## 9. Layer Ownership Summary

| Layer | Owns decisions? | Role |
|-------|-----------------|------|
| **PDE** | De facto per-cycle | Computes action; overwrites snapshot |
| **Hard risk** | Override only | -3% stop → SELL |
| **Conflict resolution** | None | EV evidence bias only |
| **Paper execution** | Fills + journals | Applies PDE; tracks `action_changed` |
| **Investment Council** | None | Synthesis report |
| **Structural governance** | None | Step orchestration |
| **DPE event bus** | None | Immutable events for shadow arms |
| **Longitudinal memory** | None | Learning / hints |

---

## 10. Oscillation Risk Assessment

### **HIGH**

| Factor | Severity |
|--------|----------|
| Full recompute each cycle | High |
| No min-hold / hysteresis | High |
| Conflict EV non-binding vs PDE | High |
| `action_changed` re-exec enabled | Medium (by design) |
| `paper_decisions.jsonl` overwritten | Medium (no audit trail in PDE) |
| Stale longitudinal ingest | Medium |
| Hard stop after conflict BUY (AMAT) | Expected but churny |

---

## 11. Minimal Wiring Plan (Reuse — No New Module)

**Do not create Master Decision Authority yet.**

1. **Ticker last action** — Derive from `paper_orders.jsonl` (last executed order per ticker). Optional: add `last_pde_action` / `last_action_at` to `paper_portfolio.json` in execution (extend existing schema).

2. **PDE + conflict read last action** — Before opposite action (BUY after SELL, SELL after BUY within N cycles), require EV margin or block soft flip. Reuse score-bias pattern from conflict resolution.

3. **Enforce cooldown** — Wire `tae_stop_reentry_cooldown_audit.json` / replay churn tickers as **hard BUY block** after recent SELL (reuse `tae_decision_governor.extract_churn_tickers` logic).

4. **Append decision history** — Change PDE `paper_decisions.jsonl` to append (or write `decision_state.json` per ticker) so prior actions are auditable.

5. **Longitudinal re-ingest on action change** — Emit new memory event when `action_changed` fires for same `decision_id`.

6. **Bind conflict when non-hard** — If `winning_scenario != final PDE action` and no hard override, require explicit `ev_override_reason` in decision record (reporting only first).

All steps extend **`tae_paper_execution.py`**, **`tae_paper_decision_engine.py`**, **`tae_conflict_resolution.py`**, **`tae_longitudinal_outcome_memory.py`** — no new brain.

---

## 12. Final Recommendation

| Option | Verdict |
|--------|---------|
| Build Master Decision Authority now | **Not needed** — would duplicate PDE + governance |
| Connect existing PDE/execution state | **Yes — safest next step** |
| Immediate priority | Ticker-level **last-action + min-hold hysteresis** from `paper_orders.jsonl` |

**Safest next step:** Implement a **Decision State View** (read-only aggregate over `paper_orders.jsonl` + `paper_portfolio.json`) consumed by PDE and conflict resolution for churn prevention — **not** a new decision engine.

---

## 13. Safety Confirmation

| Rule | Status |
|------|--------|
| READ_ONLY audit | ✅ |
| No code changes | ✅ |
| No commit | ✅ |
| No broker / live money | ✅ |
| `live_promotion_allowed` | **false** |
| Forbidden paths modified | **0** |

---

*Machine-readable companion: `tae_decision_state_ownership_audit.json`*
