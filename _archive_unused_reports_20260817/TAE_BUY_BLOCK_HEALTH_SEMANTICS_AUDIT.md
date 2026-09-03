# TAE BUY Block / Health Semantics Audit

**Mode:** READ-ONLY · NO CODE CHANGES · NO COMMIT  
**Generated:** 2026-07-24T10:34:10.715154+03:00

## Executive correction

The operator-facing chain:

`READY_WITH_WARNINGS → block_new_buy=True`

is **not** what the current code does.

At `2026-07-24T10:22:10+03:00`, Quick Health was `READY_WITH_WARNINGS` / `generated_artifacts_only`.  
That verdict **allows** new BUY (`quick_health_allows_new_buy` → True). Health refresh rewrote advisory to `SELL_ADVISORY` / `block_new_buy=False`, and `ALV.DE` executed at `10:23:10`.

The ALV blocks at `10:15–10:21` came from a **stale** advisory (`age_h≈10.2`, still `<24h`) with:

`action=RISK_ADVISORY` · `Quick health not ready: WARNING`

## Owners

| Role | File | Function |
| --- | --- | --- |
| Quick Health owner | `tae_quick_health_check.py` | `run_health_check`, `_compute_verdict` |
| CLI entry | `tae_cli/commands/health.py` | `run` → `main()` |
| Verdict builder | `tae_quick_health_check.py` | `_compute_verdict` |
| Live Advisory owner | `research_core/governance/live_advisory_bridge.py` | `LiveAdvisoryBridge` |
| Advisory runtime | `research_core/governance/live_advisory_runtime.py` | `load_live_advisory`, `should_block_new_buy` |
| BUY gate owner | `live_bot.py` | `manage_portfolio` |
| block_new_buy consumer | `live_bot.py` L623/L658 | `if block_new_buy: log BUY blocat…` |

## Exact call chain (ALV block window)

1. Overnight/prior health emitted verdict `WARNING` → bridge mapped to `NOT_READY` → wrote `tae_live_advisory.json` with `RISK_ADVISORY` and blocker `Quick health not ready: WARNING`.
2. `live_bot.manage_portfolio` → `load_live_advisory()` (`load_status=ok` because age `<24h`) → `should_block_new_buy` True iff `action==RISK_ADVISORY`.
3. Eligibility gates for ALV passed: `STRONG BUY`, `score>=80`, `regime==BULL`, EU session open, `positions<MAX_POSITIONS(12)`.
4. Final gate: `block_new_buy` → BUY blocked.
5. Operator ran `tae.py health` at 10:22 → `_compute_verdict` with `GENERATED_ARTIFACTS_ONLY` → `READY_WITH_WARNINGS` → `refresh_live_advisory` → `SELL_ADVISORY` / `block_new_buy=False` → ALV BUY executed 10:23.

## Active boolean conditions

**Health at 10:22:10 (does NOT block):**
```
git_classification == "GENERATED_ARTIFACTS_ONLY"
→ verdict, reason = ("READY_WITH_WARNINGS", "generated_artifacts_only")
→ quick_health_allows_new_buy("READY_WITH_WARNINGS") is True
```

**BUY block at 10:15–10:21:**
```
advisory.load_status == "ok"
and advisory.action == "RISK_ADVISORY"
→ should_block_new_buy → True
# blocker text: Quick health not ready: WARNING
```

## Is `generated_artifacts_only` a trading risk?

| Question | Answer |
| --- | ---: |
| Economic decision? | No |
| Data? | No |
| Accounting? | No |
| Execution? | No |
| Safety? | No |
| Repository cleanliness only? | Yes |

`live_bot.py` BUY path literals: `watchlist.txt`, `live_signals.csv`, `portfolio.csv`, `alerts_log.csv`, `bot_status.txt`, plus `tae_live_advisory.json`. None of the 116 dirty paths are direct BUY inputs.

## Simulation excluding generated-artifact dirtiness

| Field | Value |
| --- | --- |
| Health | `HEALTHY` / `runtime_healthy_git_clean` |
| Advisory | non-RISK (observed post-refresh: `SELL_ADVISORY`) |
| block_new_buy | `False` |

## Fail-closed matrix

| Quick Health state | Advisory action | block_new_buy | Justification |
| --- | --- | ---: | --- |
| READY / HEALTHY | non-RISK possible | False | allowlist READY |
| READY_WITH_WARNINGS | non-RISK possible | False | allowlist READY_WITH_WARNINGS |
| WARNING | RISK_ADVISORY | True | mapped NOT_READY |
| FAILED / NOT_READY / DEGRADED | RISK_ADVISORY | True | mapped NOT_READY |
| GENERATED_ARTIFACTS_ONLY (reason) | does not force RISK | False | reason under READY_WITH_WARNINGS |
| missing health JSON | RISK likely | True | missing → blocker |

## Verdicts

- **TECHNICAL:** `BUY_BLOCK_SEMANTIC_COUPLING_BUG`
- **ECONOMIC:** opportunity delay then fill (ALV)
- **SAFETY:** fail-closed OK for FAILED; overly conservative for WARNING(autostart/git) + 24h stale RISK

**IS BUY BLOCK JUSTIFIED:** partially (policy), not for trading risk content  
**IS OPPORTUNITY LOSS POSSIBLE:** yes  
**IS SEMANTIC COUPLING ISSUE:** yes (WARNING≠trading critical; stale advisory not refreshed on market open)

## Minimal remediation (NOT implemented)

| Option | Benefit | Risk | Files | Dup risk | Rec |
| --- | --- | --- | --- | --- | --- |
| A severity classes | clearer tiers | mis-tier | health+bridge | med | no |
| B allowlist warnings | small | drift | bridge | low | no |
| C trading_readiness vs repository_readiness (+ market-open health refresh) | matches intent | needs contract | health+bridge+startup | low | **YES** |
| D unchanged | max conservatism | repeat blocks | — | none | no |

**Recommended:** Option C. **Implementation performed:** NO.
