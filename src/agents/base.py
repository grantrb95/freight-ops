"""
Base agent class for freight operations agents.

All agents inherit from :class:`BaseAgent`, which provides structured decision
logging so that agent reasoning can be audited and improved over time.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class AgentDecision(BaseModel):
    """Structured record of an agent decision for audit and oversight."""

    agent: str = Field(..., description="Name of the agent that made the decision")
    timestamp: datetime = Field(default_factory=datetime.now)
    summary: str = Field(..., description="Short description of the decision")
    data_considered: dict[str, Any] = Field(
        default_factory=dict, description="Inputs the decision was based on"
    )
    rules_applied: list[str] = Field(
        default_factory=list, description="Thresholds/rules that were applied"
    )
    rationale: str = Field("", description="Why this decision was made")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Confidence in the decision")

    class Config:
        """Pydantic configuration."""

        json_encoders = {datetime: lambda v: v.isoformat()}


class BaseAgent(ABC):
    """Abstract base class for all freight operations agents."""

    def __init__(self, name: str, config: Optional[dict[str, Any]] = None) -> None:
        self.name = name
        self.config: dict[str, Any] = config or {}
        self.logger = logging.getLogger(f"freight_ops.agents.{name}")
        self.decisions: list[AgentDecision] = []

    def log_decision(
        self,
        summary: str,
        *,
        data_considered: Optional[dict[str, Any]] = None,
        rules_applied: Optional[list[str]] = None,
        rationale: str = "",
        confidence: float = 1.0,
    ) -> AgentDecision:
        """Record a structured decision and emit it to the logger."""
        decision = AgentDecision(
            agent=self.name,
            summary=summary,
            data_considered=data_considered or {},
            rules_applied=rules_applied or [],
            rationale=rationale,
            confidence=confidence,
        )
        self.decisions.append(decision)
        self.logger.info("decision: %s", summary, extra={"agent_decision": decision.model_dump(mode="json")})
        return decision

    @abstractmethod
    def run(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the agent's primary task."""
        raise NotImplementedError
