"""Strategy simulation runtime — connects existing simulation modules."""

from research_core.strategy_simulation_runtime.simulation_runner import run_simulation_modules
from research_core.strategy_simulation_runtime.strategy_context import StrategyContext

__all__ = ["StrategyContext", "run_simulation_modules"]
