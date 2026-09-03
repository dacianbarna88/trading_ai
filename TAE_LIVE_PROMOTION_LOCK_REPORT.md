# TAE Live Promotion Lock Report

**Generated:** 2026-09-03T13:15:21+00:00

## Policy

- Machine outputs MUST keep `live_promotion_allowed=false`
- Only `PROMOTE_TO_LIVE_CANDIDATE` is allowed (never bare `PROMOTE_TO_LIVE`)
- 30-day PAPER validation must complete before operator review
- Operator approval required outside automated cycle

## Promotion gate audit

- Gate present: **True**
- live_promotion_allowed: **False**
- Violations: **0**
- Candidate recommendations requiring approval: **34**

## Forbidden wording scan (tae_*.py)

- `tae_live_promotion_lock.py:14` — FORBIDDEN_PROMOTION = re.compile(r"PROMOTE_TO_LIVE(?!_CANDIDATE)")
- `tae_live_promotion_lock.py:58` — if rec == "PROMOTE_TO_LIVE":
- `tae_live_promotion_lock.py:59` — violations.append(f"{row.get('ticker')}/{row.get('action')}: forbidden PROMOTE_TO_LIVE")
- `tae_live_promotion_lock.py:84` — "forbidden_recommendations": ["PROMOTE_TO_LIVE"],
- `tae_live_promotion_lock.py:91` — if rec == "PROMOTE_TO_LIVE":
- `tae_live_promotion_lock.py:129` — "- Only `PROMOTE_TO_LIVE_CANDIDATE` is allowed (never bare `PROMOTE_TO_LIVE`)",
- `tae_live_promotion_lock.py:146` — lines.append("- No bare `PROMOTE_TO_LIVE` wording found in scanned TAE modules")
- `tae_paper_decision_engine.py:144` — FORBIDDEN_KB_RECOMMENDATIONS = frozenset({"BUY", "SELL", "STOP", "TAKE_PROFIT", "PROMOTE_TO_LIVE"})
- `tae_paper_decision_engine.py:1099` — if "PROMOTE_TO_LIVE" in rec and "DO_NOT" not in rec:

**Lock status:** PASS

