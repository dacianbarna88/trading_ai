# TAE — FULL TRANSACTION AUDIT — 2026-07-24
## LIVE / Parallel V1 / Parallel V2

**Mode:** STRICT READ-ONLY audit (no repairs, no process changes, no commits)  
**Project root:** `/Users/book/Desktop/trading_ai`  
**Generated from host evidence at audit time:** 2026-07-24 ~17:22 EEST  
**Naming:** LIVE = paper `live_bot.py` capital book. Parallel V1 / V2 = `tae_parallel_paper_daemon.py` arms. There is no `live_bot_v1.py` / `live_bot_v2.py`.

---

## Verdicts (mandatory)

| Key | Verdict |
|---|---|
| **LIVE_TRANSACTION_HISTORY** | `PARTIALLY_CORRUPTED` |
| **V1_TRANSACTION_HISTORY** | `VALID` |
| **V2_TRANSACTION_HISTORY** | `VALID` |
| **LEARNING_DATA_2026_07_24** | `VALID` |
| **ROOT_CAUSE** | `PARTIALLY_PROVEN` |

---

## 1. Canonical sources (absolute paths)

| Runtime | Path | Size | mtime | Owner |
|---|---|---|---|---|
| LIVE | `/Users/book/Desktop/trading_ai/portfolio.csv` | 2096 | 2026-07-24T17:20:46 | LIVE |
| LIVE | `/Users/book/Desktop/trading_ai/live_signals.csv` | 1441 | 2026-07-24T17:20:33 | LIVE |
| LIVE | `/Users/book/Desktop/trading_ai/alerts_log.csv` | ~1.96MB | 2026-07-24T17:21:55 | LIVE |
| LIVE | `/Users/book/Desktop/trading_ai/bot_output.log` | ~18.2MB | 2026-07-24T17:21:48 | LIVE |
| LIVE | `/Users/book/Desktop/trading_ai/bot_status.txt` | 7 | 2026-07-24T17:19:14 | LIVE |
| LIVE | `/Users/book/Desktop/trading_ai/bot_pid.txt` | 5 (contents `23438`) | 2026-07-24T17:19:14 | LIVE |
| LIVE | `/Users/book/Desktop/trading_ai/tae_live_advisory.json` | 21799 | 2026-07-24T17:21:48 | LIVE |
| LIVE | `/Users/book/Desktop/trading_ai/tae_accounting_snapshot.json` | 13130 | **2026-07-23T14:21:18** | STALE projection (not live SSOT) |
| LIVE | `/Users/book/Desktop/trading_ai/portfolio.csv.lock` | 0 | **2026-07-24T13:25:56** | LIVE |
| LIVE | `/Users/book/Desktop/trading_ai/portfolio.csv.runtime.json` | 277 | 2026-07-24T14:46:05 | LIVE sidecar |
| LIVE | `/Users/book/Desktop/trading_ai/portfolio.csv.wiped_20260724_1327` | 143 | **2026-07-24T13:29:06** | wipe artifact (header-only) |
| LIVE | `/Users/book/Desktop/trading_ai/runtime_outputs/live/` | empty dir | — | no execution journal written |
| V1 | `/Users/book/Desktop/trading_ai/runtime_outputs/parallel_paper/v1/canonical_mirror_snapshot.json` | 4591 | 2026-07-24T17:21:18 | parallel_v1 |
| V1 | `…/v1/accounting_snapshot.json` / `account.json` / `health.json` | 465/465/470 | 2026-07-24T17:21:18 | parallel_v1 |
| V1 | `…/v1/journals/decisions.jsonl` | ~113KB | 2026-07-24T17:21:18 | parallel_v1 |
| V1 | `…/v1/journals/executions.jsonl` | 3687 | **2026-07-23T23:48:31** | no Jul-24 executions |
| V1 | `…/v1/journals/trades.jsonl` | 307 | 2026-07-23T19:53:04 | Jul-23 only |
| V2 | `…/v2/portfolio.json` | 800 | 2026-07-24T17:21:18 | parallel_v2 |
| V2 | `…/v2/accounting_snapshot.json` / `account.json` / `health.json` | 243/243/385 | 2026-07-24T17:21:18 | parallel_v2 |
| V2 | `…/v2/journals/decisions.jsonl` + `executions.jsonl` | ~101–108KB | 2026-07-24T17:21:18 | parallel_v2 (HOLD cycles) |
| SHARED daemon | `…/parallel_paper.pid` / `.lock` / `daemon.log` | — | — | one daemon for both arms |
| LEARN | `…/canonical_learning/applied_events.jsonl` | 2793 | 2026-07-24T01:19:44 | last apply content dated **2026-07-23** |
| LEARN | `…/canonical_learning/cycle_ledger.jsonl` | 6539 | 2026-07-24T17:15:17 | Jul-24 cycles = `DUPLICATE_SKIPPED` |

**Mixing check:** Parallel journals and LIVE `portfolio.csv` are different absolute paths. No evidence that V1/V2 wrote LIVE portfolio on 2026-07-24. `runtime_outputs/live/` has no journal file.

---

## 2. Chronology (unique LIVE executions + critical state events)

Log contains duplicated blocks (same timestamps reappear at later file offsets). Tables below use **deduplicated** `(timestamp, ticker, action, qty, price)` keys from `/Users/book/Desktop/trading_ai/bot_output.log`.

### A. Evaluated / rejected BUY (aggregate)

| Class | Evidence | Count / note |
|---|---|---|
| BUY skipped — market closed | `bot_output.log` many lines e.g. `00:00:29 BUY skipped for ALV.DE: ticker market closed` | Dominant overnight |
| BUY blocked — RISK_ADVISORY | e.g. `10:20:17` / `10:21:43` `BUY blocat pentru ALV.DE: TAE RISK_ADVISORY…` | Pre-open ALV |
| BUY blocked — ECONOMIC_SSOT_INVALID | `13:25:00`–`13:35:44` and `13:27:29` | During empty/corrupt portfolio window |
| Parallel V1/V2 today | decisions = **HOLD only** (316 each arm) | No Jul-24 BUY/SELL executions |

### B–D. LIVE executions (unique)

| ts | runtime | ticker | action | price | qty | value | score/reason | source line theme | portfolio basis | classification |
|---|---|---|---|---|---|---|---|---|---|---|
| 10:23:10 | LIVE | ALV.DE | BUY | 426.80 | 5.6343 | 2404.72 | score=80 STRONG BUY; `BUY permis…` then `BUY executat` | `bot_output.log` ~249652–249653 | Pre-wipe book (11→12 per behavior audit; lot **absent** from current CSV) | LEGITIMATE on then-current book; **LOST in wipe** |
| 13:08:53 | LIVE | — | MARK | — | — | — | `portfolio.csv actualizat cu prețuri live` | log ~253126 | Last mark update before discontinuity | State still had open BUY rows |
| 13:09:32 | LIVE | AIR.PA | SELL | 96.90 | 10.0 | — | STOP LOSS -3.10%; regime log says BEAR | log ~253151 | **No matching lot in current `portfolio.csv`**; price ≠ afternoon AIR ~204.5 | INCONSISTENT / PHANTOM relative to surviving CSV |
| 13:10:07 | LIVE | ALV.DE | BUY | 426.00 | 5.8685 | 2500.00 | score=100 | log ~253163–253164 | Requires high cash / empty-ish book | **POST-WIPE** (impossible with cash≈0 + 12 opens) |
| 13:10:07 | LIVE | ULVR.L | BUY | 4543.00 | 0.5503 | 2500.00 | AUTO STRONG BUY… | same | same | **POST-WIPE** |
| 13:10:07 | LIVE | AIR.PA | BUY | 204.50 | 12.2249 | 2500.00 | AUTO STRONG BUY… | same | same | **POST-WIPE** |
| 13:11:22 | LIVE | SIE.DE | BUY | 271.75 | 9.1996 | 2500.00 | AUTO STRONG BUY… | log ~253202 | same | **POST-WIPE** |
| 13:25:00+ | LIVE | SPY etc. | BLOCK | — | — | — | `ECONOMIC_SSOT_INVALID (cash unavailable)` | log ~254790+ | Empty/invalid portfolio | E. portfolio without legitimate full-book unwind |
| 13:27:29 | LIVE | — | INVALID | — | — | — | `portfolio.csv missing or empty` | log ~254807 | Empty book | E |
| 13:29:06 | LIVE | — | ARTIFACT | — | — | — | header-only file preserved | `portfolio.csv.wiped_20260724_1327` mtime | Header only | E |
| 13:34:24 | LIVE | — | MARK | — | — | — | portfolio update resumes | log ~254973 | Book restored enough to mark | After operator/manual restore window |
| 13:35:06 | LIVE | AIR.PA | SELL | 96.90 | 10.0 | — | STOP LOSS -3.10% | log ~254994 | No SELL row in current CSV for this | PHANTOM / INCONSISTENT |
| 13:35:44 | LIVE | AIR.PA | SELL | 96.90 | 10.0 | — | STOP LOSS -3.10% | log ~255035 | same | PHANTOM / DUPLICATE log of ghost stop |
| 16:30:53 | LIVE | PM | BUY | 193.52 | 12.9186 | 2500.00 | AUTO STRONG BUY… | log ~260597 | After 4-lot book + ~20k cash | LEGITIMATE on post-wipe book |
| 16:30:53 | LIVE | ABBV | BUY | 258.77 | 9.6611 | 2500.00 | | | | LEGITIMATE post-wipe |
| 16:30:53 | LIVE | MRK | BUY | 131.10 | 19.0694 | 2500.00 | | | | LEGITIMATE post-wipe |
| 16:30:53 | LIVE | AAPL | BUY | 323.08 | 7.738 | 2500.00 | | | | LEGITIMATE post-wipe |
| 16:30:53 | LIVE | LLY | BUY | 1194.93 | 2.0922 | 2500.00 | | | | LEGITIMATE post-wipe |
| 16:30:53 | LIVE | AMAT | BUY | 553.33 | 4.5181 | 2500.00 | | | | LEGITIMATE post-wipe |
| 16:34:24 | LIVE | MU | BUY | 963.59 | 2.5945 | 2500.00 | | log ~260665 | | LEGITIMATE post-wipe |
| 16:54:13 | LIVE | MU | SELL | 933.13 | 2.5945 | proceeds 2421.01 | STOP LOSS -3.16%; realized **-79.0285** | log ~261014 + CSV SELL row | Matches CSV | LEGITIMATE |
| 17:03:23 | LIVE | PG | BUY | 147.11 | 16.9941 | 2500.00 | | log ~261184 + CSV | | LEGITIMATE post-wipe |

**decision_id / execution_id:** LIVE `live_bot` path does **not** emit these IDs. Parallel IDs exist only under `runtime_outputs/parallel_paper/**/journals/`.

### E. Portfolio changes without legitimate full unwind of the 12-book

Proven: between last mark `13:08:53` and first post-gap BUY cluster `13:10:07`, LIVE behavior implies capital freed / book cleared enough to place **$10,000** of new buys while Jul-23 SSOT had **cash_available=0.0** with 12 opens.  
**No** set of `SELL executat` lines exists for SPY/DIA/MRK/PG/PM/MU/LLY/HD/ABBV (etc.) in that window.  
Therefore the 12→4 transition includes a **non-execution ledger break** (wipe/truncate/overwrite/restore), not a complete sell-down.

---

## 3. LIVE 12 → 4 forensic

### Last known 12-position set (file evidence)

| Item | Evidence |
|---|---|
| File with 12 opens | `/Users/book/Desktop/trading_ai/tae_accounting_snapshot.json` |
| Timestamp | `generated_at=2026-07-23T11:21:18.310895+00:00` (on-disk mtime 2026-07-23T14:21:18) |
| Tickers | SPY, DIA, MRK, SIE.DE, ULVR.L, PG, PM, MU, LLY, HD, AIR.PA, ABBV |
| Cash / AV | cash_available **0.0**, open_positions_value **29380.7617**, account_value_corrected **29380.76** |

**Gap:** No preserved `portfolio.csv` snapshot at `2026-07-24 13:08:53`. Morning ALV.DE BUY `10:23:10` proves the live book changed after the Jul-23 snapshot; exact morning-12 ticker list after ALV is **not on disk**. Behavior audit (operator) reported 11/12 before ALV and 12/12 after — that report is external to these files.

### Transition window (proven bounds)

| Bound | Timestamp | Evidence |
|---|---|---|
| Last mark on a non-empty open book | **2026-07-24 13:08:53** | `bot_output.log`: `portfolio.csv actualizat cu prețuri live (open BUY rows only).` |
| First cluster requiring ~$10k free cash on empty-ish book | **2026-07-24 13:10:07** | three `BUY executat` @ $2500 |
| Fourth BUY | **2026-07-24 13:11:22** | SIE.DE |
| Observed empty portfolio | **2026-07-24 13:27:29** | `ECONOMIC_SSOT_INVALID: portfolio.csv missing or empty` |
| Lock file touch | **2026-07-24 13:25:56** | `portfolio.csv.lock` mtime |
| Header-only wipe artifact | **2026-07-24 13:29:06** | `portfolio.csv.wiped_20260724_1327` contents = CSV header only |
| Marks resume | **2026-07-24 13:34:24** | `portfolio.csv actualizat…` |

**Exact transition timestamp for 12→0:** not captured as a single logged “wipe” event. Proven interval for capital discontinuity enabling the 13:10 buys: **(13:08:53, 13:10:07]**. A **second** empty episode is proven at **13:25–13:27**.

### Eight positions “gone” relative to Jul-23 SSOT 12 (no Jul-24 SELL for them)

From Jul-23 SSOT 12, tickers with **no** Jul-24 `SELL executat` in log:  
**SPY, DIA, MRK, PG, PM, MU, LLY, HD, ABBV** (and prior lots of SIE.DE / ULVR.L / AIR.PA were replaced by new 13:10–13:11 buys, not closed via logged sells at mark).

Morning ALV.DE lot (`5.6343 @ 426.80`) also has **no SELL** and is **absent** from current CSV.

### Who created wipe artifact / who wrote next portfolio?

| Question | Finding |
|---|---|
| Who created `portfolio.csv.wiped_20260724_1327`? | **EXACT_WRITER_PID_NOT_PROVEN.** File mtime 13:29:06; content header-only. No log line names the preserving process. Sidecar `portfolio.csv.runtime.json` was written later (`isolation_audit.bootstrap`, pid **32450**, `2026-07-24T11:46:05Z` UTC = 14:46 EEST) — **after** wipe, not the wipe itself. |
| Who wrote the surviving 4-row book? | Rows’ `Date` fields are `2026-07-24 13:10:07` / `13:11:22` matching `live_bot` `BUY executat` lines. Writer module for normal path: `live_bot.save_portfolio` ← `manage_portfolio` / `update_portfolio_prices`. **EXACT_WRITER_PID_NOT_PROVEN** for the wipe; current bot pid file reads **23438** (process started ~13:36 per host `ps` earlier in day, not proven as wipe actor). |
| Call path capable of wipe | Pre-atomic era: `DataFrame.to_csv(PORTFOLIO_FILE)` truncate-on-open; kill mid-write; empty overwrite. Current code (post-repair) uses tmp+`os.replace`, flock, refuse empty overwrite — but that does **not** retroactively identify the Jul-24 PID. |

**EXACT_WRITER_PID_NOT_PROVEN** for the 12→empty event.

---

## 4. All LIVE trades today (summary tables)

### BUY

| # | ticker | decision/exec ts | px | qty | value | before-state | classification |
|---|---|---|---|---|---|---|---|
| 1 | ALV.DE | 10:23:10 | 426.80 | 5.6343 | 2404.72 | Pre-wipe (audit 11→12) | LEGIT then; **missing from CSV** |
| 2 | ALV.DE | 13:10:07 | 426.00 | 5.8685 | 2500 | Post-wipe / high cash | POST-WIPE; in CSV |
| 3 | ULVR.L | 13:10:07 | 4543.00 | 0.5503 | 2500 | Post-wipe | POST-WIPE; in CSV |
| 4 | AIR.PA | 13:10:07 | 204.50 | 12.2249 | 2500 | Post-wipe | POST-WIPE; in CSV |
| 5 | SIE.DE | 13:11:22 | 271.75 | 9.1996 | 2500 | Post-wipe | POST-WIPE; in CSV |
| 6–11 | PM ABBV MRK AAPL LLY AMAT | 16:30:53 | … | … | 2500 each | 4 opens + ~20k cash | LEGIT on post-wipe book |
| 12 | MU | 16:34:24 | 963.59 | 2.5945 | 2500 | 10 opens + ~5k cash | LEGIT; later sold |
| 13 | PG | 17:03:23 | 147.11 | 16.9941 | 2500 | After MU sell | LEGIT; in CSV |

Trades **2–5 would not be jointly possible** on the Jul-23 SSOT state (cash 0, 12 opens) without an intervening ledger clear.

### SELL

| # | ticker | ts | px | qty | reason | CSV proof | classification |
|---|---|---|---|---|---|---|---|
| 1 | AIR.PA | 13:09:32 | 96.90 | 10.0 | STOP -3.10% | **No** matching SELL row | INCONSISTENT / PHANTOM |
| 2 | AIR.PA | 13:35:06 | 96.90 | 10.0 | STOP -3.10% | **No** | PHANTOM / DUPLICATE ghost |
| 3 | AIR.PA | 13:35:44 | 96.90 | 10.0 | STOP -3.10% | **No** | PHANTOM / DUPLICATE ghost |
| 4 | MU | 16:54:13 | 933.13 | 2.5945 | STOP -3.16% | **Yes** SELL row | LEGITIMATE; realized **-79.0285** |

---

## 5. Parallel V1 and V2 (2026-07-24)

### V1 (CANONICAL_PAPER_MIRROR)

| Field | Value | Source |
|---|---|---|
| Start-of-day posture | Mirror of canonical paper; not LIVE CSV | `mirror_meta` / daily report |
| Jul-24 decisions | **316 HOLD** (0 BUY/SELL) | `v1/journals/decisions.jsonl` |
| Jul-24 executions | **0** (executions.jsonl mtime Jul-23) | `v1/journals/executions.jsonl` |
| Final positions (13) | AAPL, ABBV, AIR.PA, DIA, HD, LLY, MC.PA, MRK, PG, PM, SHEL.L, SPY, ULVR.L | `canonical_mirror_snapshot.json` |
| Cash / AV | 17088.5442 / 29792.0451 | account.json |
| Realized / unrealized | -696.4528 / 147.5771 | same |
| Learning from V1 today | No new applied learning events | cycle_ledger `DUPLICATE_SKIPPED` |

### V2 (ISOLATED_PARALLEL_PAPER)

| Field | Value | Source |
|---|---|---|
| Open positions | MSFT (1.174812), NVDA (2.352277) | `v2/portfolio.json` |
| Opened | **2026-07-23T16:53:04Z** OPEN executions | `v2/journals/executions.jsonl` |
| Jul-24 decisions/executions | **316 HOLD** (executed flag on HOLD rows; value 0) | journals |
| Cash / AV | 29000.0 / 29999.999986 | account.json |
| Realized / unrealized | 0.0 / 0.0 | same |
| Jul-24 BUY/SELL | **none** | journals |

### V1 vs V2 same-ticker windows (today)

Both arms evaluated overlapping watch names as **HOLD** every cycle.  
**Not a DRAW from equal AV:** V1 AV≈29792 with 13 mirrored positions; V2 AV≈30000 with 2 small tranches and cash 29000. Modes differ (`CANONICAL_PAPER_MIRROR` vs `ISOLATED_PARALLEL_PAPER`). Daily report `v2_counts`: OPEN 2 (historical), HOLD 13 (sample window in report), ADD/CLOSE 0 today.

---

## 6. Learning data 2026-07-24

| Event | Runtime | Result | Classification |
|---|---|---|---|
| `applied_events.jsonl` entries | canonical_learning | Last content timestamps **2026-07-23T22:19:44Z**; outcomes_evaluated=46 on last_applied | **VALID** historical; **no new Jul-24 apply** |
| `cycle_ledger.jsonl` Jul-24 cycles | canonical_learning | `result=DUPLICATE_SKIPPED` every 15m from 07:15Z onward | **DUPLICATE** (skip), not corrupted LIVE wipe outcomes |
| LIVE wipe window trades | — | No learning apply lines reference LIVE portfolio wipe | No `INVALID_DUE_TO_PORTFOLIO_WIPE` apply found |
| Cross-runtime same destination | LIVE vs parallel vs learning paths | Distinct directories | **No CROSS_RUNTIME_CONTAMINATION** found for Jul-24 applies |

**LEARNING_DATA_2026_07_24: VALID** (idle/duplicate skips; no proven ingestion of wipe-era LIVE fills into applied learning).

---

## 7. Accounting reconciliation

### Parallel V1 (from arm files)

`cash 17088.5442 + open_positions_value 12703.5009 = 29792.0451` (= account_value).  
`starting/peak context in mirror`; cumulative realized -696.4528 + unreal 147.5771 consistent with daily report cumulative_pnl -548.8757.  
**Delta formulas:** reconciliation_pass true in daily report.

### Parallel V2

`cash 29000 + invested ≈1000 = 30000` (AV 29999.999986). Realized 0, unreal 0.  
**Delta:** ~1e-5 float noise only.

### LIVE phases

| Phase | Evidence | Opens | Cash (known) | AV (known) |
|---|---|---|---|---|
| Pre-day SSOT (Jul 23) | `tae_accounting_snapshot.json` | 12 | 0.0 | 29380.76 |
| Pre-wipe Jul 24 13:08 | **NOT PRESERVED** as portfolio dump | UNKNOWN exact | UNKNOWN | UNKNOWN |
| Immediately after empty detect | log 13:27:29 | 0 / missing | unavailable (SSOT invalid) | invalid |
| After 4 BUYs (implied) | CSV dates 13:10–13:11 + earlier SSOT rebuild in day | 4 | ~20000.02 | ~29994 |
| End of day (audit rebuild) | `build_accounting_snapshot` | **11** | **2420.96** | **29962.58** |
| End realized / unreal | same | — | realized **-79.0285** (MU) | unreal ~41.60 |

**Cash path (post-wipe reconstruction, evidenced):**  
30000 − 10000 (4 buys) ≈ 20000 → −15000 (6 buys) ≈ 5000 → −2500 (MU) ≈ 2500 → +MU proceeds 2421.01 − residual ≈ then −2500 (PG) → **cash ≈ 2420.96** with 11 opens. Matches live SSOT.

**Formula deltas LIVE:** on-disk `tae_accounting_snapshot.json` is **stale** (12 opens) vs rebuilt SSOT (11). Do not use stale file as SSOT.

---

## 8. Code that can write LIVE portfolio

| File | Function | Caller | Write type | Atomic? | Lock | Empty overwrite guard | Active today? |
|---|---|---|---|---|---|---|---|
| `live_bot.py` | `save_portfolio` | `update_portfolio_prices`, `manage_portfolio` | CSV replace | Yes (tmp+`os.replace`) **now** | `portfolio.csv.lock` flock | Yes **now** | **Yes** (PID 23438) |
| `data/storage.py` | `save_portfolio` | `core/portfolio_prices.py` | CSV replace | Yes now | same lock | Yes now | Helper; LaunchAgents do not start it |
| `core/portfolio_prices.py` | `update_portfolio_prices` → storage | legacy | via storage | via storage | via storage | via storage | Not the live_bot loop |
| `tae_bootstrap_runtime.py` | seed header if absent | bootstrap only | create/seed | N/A | no | only absent/header | Not shown in Jul-24 bot log as wipe cause |
| `research/apply_rebalance_paper.py` | append SELL lines | manual | append | no | no | disabled unless env | Disabled without `TAE_ALLOW_LEGACY_PORTFOLIO_APPEND=1` |
| `tae_parallel_paper_runtime.save_portfolio` | JSON under v1/v2 | parallel daemon | JSON | arm paths | parallel lock | N/A | **Does not write LIVE CSV** |

### Root cause classification

| Tier | Statement |
|---|---|
| **Demonstrated** | LIVE ledger lost continuity on 2026-07-24 between 13:08:53 and 13:10:07 (and again empty at 13:25–13:27). Header-only artifact exists. Post-gap BUYs of $10k occurred. Jul-23 12-name SSOT and current CSV disagree without matching SELLs for vanished names. Mechanism class: **non-atomic / truncate / empty portfolio file event on LIVE path**, not V1/V2 cross-write. |
| **Contributive** | Historical `to_csv` truncate-on-open (pre-repair); process restart / log duplication; lock mtime 13:25; phantom AIR.PA stops @ 96.90; BEAR regime line at 13:09:32. |
| **Not demonstrated** | Exact PID of wipe; exact 12 ticker list at 13:08:53; whether kill-mid-write vs manual restore vs tool seed; authorship of `portfolio.csv.wiped_20260724_1327`. → **EXACT_WRITER_PID_NOT_PROVEN** |

**ROOT_CAUSE: PARTIALLY_PROVEN**

---

## 9. Final verdict block

1. **Chronology:** see §2–4.  
2. **LIVE trades:** 13 unique BUYs, 4 unique SELL log events (1 CSV-proven MU; 3 phantom AIR).  
3. **V1 trades Jul-24:** 0 fills; HOLD-only decisions.  
4. **V2 trades Jul-24:** 0 fills; HOLD-only; book still MSFT+NVDA from Jul-23.  
5. **Portfolios before/after:** pre-wipe 12-book not preserved; post-13:10 four CSV lots; EOD 11 opens.  
6. **12→4:** LIVE same-file wipe/clear + rebuild buys; **not** V1/V2 mix.  
7. **Enabling function class:** LIVE `save_portfolio` / CSV writer path (historical non-atomic).  
8. **Accounting impact:** lost continuity of pre-wipe positions/PnL; post-wipe day PnL dominated by MU stop **-79.03**; stale JSON still shows 12.  
9. **Learning impact:** no Jul-24 applied events from wipe fills; cycles duplicate-skipped.  
10. **Invalid/contaminated:** LIVE history partially corrupted; phantom AIR sells; morning ALV lot missing; stale accounting JSON.  
11. **Missing evidence:** pre-wipe portfolio dump; wipe PID; continuous FS history.  
12. **Verdicts:** table at top.

---

## Integrity of this audit run

### Files read (non-exhaustive but material)

`portfolio.csv`, `portfolio.csv.wiped_20260724_1327`, `portfolio.csv.lock`, `portfolio.csv.runtime.json`, `bot_output.log`, `live_signals.csv`, `alerts_log.csv`, `bot_pid.txt`, `bot_status.txt`, `tae_live_advisory.json`, `tae_accounting_snapshot.json`, parallel v1/v2 portfolios/accounts/journals/health, `parallel_paper.pid/lock/daemon.log`, canonical_learning `applied_events.jsonl` / `cycle_ledger.jsonl` / `last_applied.json`, daily parallel report JSON, `live_bot.py` / `data/storage.py` writers (read-only).

### Read-only commands run

`git status`; `ls -la`; `rg` on logs; `python3` parsers printing to stdout; `build_accounting_snapshot` **in-process read/rebuild** (does not modify portfolio); no `kill`, no bot restart, no portfolio write from this audit.

### Deliverable file

This report path: `/Users/book/Desktop/trading_ai/TAE_2026_07_24_V1_V2_LIVE_FULL_TRANSACTION_AUDIT.md` (audit artifact only).

### Process / runtime mutation

**Zero processes started/stopped by this audit.**  
**Zero LIVE/V1/V2 portfolio/journal/learning files rewritten by this audit.**

### Git status

- **Before:** dirty tree of pre-existing report/json artifacts (unchanged by this work).  
- **After:** same dirty set **plus** this new untracked audit markdown (deliverable). No commit created.
