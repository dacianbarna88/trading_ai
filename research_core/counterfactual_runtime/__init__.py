"""Counterfactual runtime — connects entry/exit analysis and shadow validation."""

from research_core.counterfactual_runtime.counterfactual_context import CounterfactualContext
from research_core.counterfactual_runtime.counterfactual_runner import run_counterfactual_modules

__all__ = ["CounterfactualContext", "run_counterfactual_modules"]
