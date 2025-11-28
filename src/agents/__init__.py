"""
AI Agents for freight operations.

This module contains specialized agents for:
- Dispatch: Load matching and booking
- Rate Analysis: Market rate analysis and pricing
- Compliance: IFTA, HOS, and DOT compliance
- Route Optimization: Efficient routing and deadhead reduction
- Settlement: Driver pay calculations
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import BaseAgent

__all__ = ["BaseAgent"]
