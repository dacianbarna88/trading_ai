# TAE Live Trailing Protection — Pre-Change Audit

**Date:** 2026-07-22  
**Canonical owner:** `live_bot.py` → `manage_portfolio` / `manage_position_risk_independent`

## SELL paths before change

| Location | Trigger | Action |
|----------|---------|--------|
| `live_bot.manage_portfolio` L690-692 | `signal == "TAKE PROFIT"` | Full SELL |
| `live_bot.manage_portfolio` L694-696 | `pnl_pct >= TAKE_PROFIT_PCT (+5%)` | Full SELL `PROFIT +x%` |
| `live_bot.manage_portfolio` L698-700 | `pnl_pct <= STOP_LOSS_PCT (-3%)` | Full SELL stop-loss |
| `live_bot.manage_position_risk_independent` L520-523 | `pnl_pct >= TAKE_PROFIT_PCT` | Full SELL independent TP |
| `live_bot.manage_position_risk_independent` L520-521 | `pnl_pct <= STOP_LOSS_PCT` | Full SELL independent SL |

## Parallel / unused logic

| Module | Status |
|--------|--------|
| `core/trailing.py` | Existed but **not imported** by `live_bot`; used `config.settings` (4%/5%) |
| `config/settings.py` | Legacy V5.1 constants — not live_bot owner |
| Paper / shadow modules | Separate books — out of scope |

## Decision

- **Owner:** `core/trailing.py` rewritten as canonical pure trailing engine
- **Wiring:** `live_bot._evaluate_open_position_exit()` single path for held positions + independent risk
- **Removed:** Hard full exit at `+5%`; `TAKE_PROFIT_PCT` now **activates** trailing only

## AIR.PA numeric simulation (avg buy 207.90)

| Step | Price | Result |
|------|-------|--------|
| +5% activation | 218.30 | Trailing ON, stop ≥ 211.75 (97% of high) and ≥ 212.06 (+2% lock) → **211.75** |
| Peak +10% | 228.69 | High=228.69, stop ≈ 221.83 |
| Pullback −2% from peak | 224.12 | **HOLD** (above stop) |
| Pullback −3% from peak | 221.83 | **SELL trailing** |
| Rally to +30% | 270.27 | **HOLD**; stop ratchets up, no profit cap |
