from pathlib import Path
from core.historical_risk import (
    get_historical_risk_mode,
    get_risk_multiplier,
)
from core.forecast_risk import (
    get_forecast_multiplier,
)

historical_mode = get_historical_risk_mode()
historical_mult = get_risk_multiplier()
forecast_mult = get_forecast_multiplier()

effective_risk = round(
    historical_mult * forecast_mult,
    3
)

summary = f"""
===== STRATEGIC RISK DASHBOARD =====

Historical Risk:
{historical_mode}

Historical Multiplier:
{historical_mult}

Forecast Multiplier:
{forecast_mult}

Effective Risk:
{effective_risk}

Status:
PAPER_ONLY
NO_BROKER
NO_AUTO_EXECUTION
"""

Path("strategic_risk_summary.txt").write_text(
    summary.strip()
)

print(summary)
