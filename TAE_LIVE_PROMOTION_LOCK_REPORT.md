# TAE Live Promotion Lock Report

**Generated:** 2026-07-07T15:26:26+00:00

## Policy

- Machine outputs MUST keep `live_promotion_allowed=false`
- Only `PROMOTE_TO_LIVE_CANDIDATE` is allowed (never bare `PROMOTE_TO_LIVE`)
- 30-day PAPER validation must complete before operator review
- Operator approval required outside automated cycle

## Promotion gate audit

- Gate present: **True**
- live_promotion_allowed: **False**
- Violations: **0**
- Candidate recommendations requiring approval: **2**

## Forbidden wording scan (tae_*.py)

- `tae_live_promotion_lock.py:14` — FORBIDDEN_PROMOTION = re.compile(r"PROMOTE_TO_LIVE(?!_CANDIDATE)")
- `tae_live_promotion_lock.py:58` — if rec == "PROMOTE_TO_LIVE":
- `tae_live_promotion_lock.py:59` — violations.append(f"{row.get('ticker')}/{row.get('action')}: forbidden PROMOTE_TO_LIVE")
- `tae_live_promotion_lock.py:84` — "forbidden_recommendations": ["PROMOTE_TO_LIVE"],
- `tae_live_promotion_lock.py:91` — if rec == "PROMOTE_TO_LIVE":
- `tae_live_promotion_lock.py:129` — "- Only `PROMOTE_TO_LIVE_CANDIDATE` is allowed (never bare `PROMOTE_TO_LIVE`)",
- `tae_live_promotion_lock.py:146` — lines.append("- No bare `PROMOTE_TO_LIVE` wording found in scanned TAE modules")
- `tae_adaptive_paper_weights_test.py:107` — {"promotion_recommendation": "PROMOTE_TO_LIVE", "ticker": "MRK", "action": "HOLD_PAPER"},

**Lock status:** PASS

