from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from research.signals import generate_signals
from live_bot_v5_1 import manage_portfolio
from core.portfolio_prices import update_portfolio_prices

generate_signals(
    manage_portfolio,
    update_portfolio_prices
)

print("===== V35.5 LIVE SIGNAL REFRESH + VIRTUAL PORTFOLIO COMPLETE =====")
