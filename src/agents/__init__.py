"""
AI Agents for freight operations.

This module contains specialized agents for:
- Dispatch: Load matching and booking
- Rate Analysis: Market rate analysis and pricing
- Compliance: IFTA, HOS, and DOT compliance
- Route Optimization: Efficient routing and deadhead reduction
- Settlement: Driver pay calculations
"""

from .base import AgentDecision, BaseAgent
from .compliance import ComplianceAgent
from .dispatch import DispatchAgent
from .rate_analysis import RateAnalysisAgent
from .route_optimizer import RouteOptimizerAgent
from .settlement import SettlementAgent

__all__ = [
    "BaseAgent",
    "AgentDecision",
    "DispatchAgent",
    "RateAnalysisAgent",
    "ComplianceAgent",
    "RouteOptimizerAgent",
    "SettlementAgent",
]
