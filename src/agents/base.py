"""
Base agent class for all freight operations agents.

Provides common functionality:
- LLM client initialization
- MCP tool integration
- Logging and decision tracking
- Error handling and retries
"""

import json
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional

import structlog
from anthropic import Anthropic
from openai import OpenAI
from pydantic import BaseModel

from src.core.config import AgentLLMConfig, ConfigManager, get_config


class AgentDecision(BaseModel):
    """
    Structured format for agent decisions.

    Used to track reasoning and provide transparency.
    """

    timestamp: datetime
    agent_name: str
    decision_type: str
    input_data: dict[str, Any]
    reasoning: str
    confidence: float  # 0.0 to 1.0
    output_data: dict[str, Any]
    tools_used: list[str]
    execution_time_seconds: float


class BaseAgent(ABC):
    """
    Base class for all freight operations agents.

    Provides:
    - LLM client management (Anthropic/OpenAI)
    - Configuration loading
    - Decision logging
    - Error handling
    - MCP tool integration points
    """

    def __init__(
        self,
        agent_name: str,
        config_manager: Optional[ConfigManager] = None,
        logger: Optional[structlog.BoundLogger] = None,
    ) -> None:
        """
        Initialize the base agent.

        Args:
            agent_name: Name of the agent (e.g., "dispatch", "rate_analysis")
            config_manager: Optional config manager (defaults to global instance)
            logger: Optional structured logger
        """
        self.agent_name = agent_name
        self.config_manager = config_manager or get_config()
        self.logger = logger or structlog.get_logger(agent_name=agent_name)

        # Load agent-specific LLM configuration
        self.llm_config = self.config_manager.get_agent_llm_config(agent_name)

        # Initialize LLM clients
        self._anthropic_client: Optional[Anthropic] = None
        self._openai_client: Optional[OpenAI] = None

        # Decision history (for debugging and improvement)
        self.decision_history: list[AgentDecision] = []

        self.logger.info("agent_initialized", agent_name=agent_name)

    @property
    def anthropic_client(self) -> Anthropic:
        """Get or create Anthropic client."""
        if self._anthropic_client is None:
            api_key = self.config_manager.get_api_key("anthropic")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not set in environment")
            self._anthropic_client = Anthropic(api_key=api_key)
        return self._anthropic_client

    @property
    def openai_client(self) -> OpenAI:
        """Get or create OpenAI client."""
        if self._openai_client is None:
            api_key = self.config_manager.get_api_key("openai")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not set in environment")
            self._openai_client = OpenAI(api_key=api_key)
        return self._openai_client

    def get_llm_client(self, use_fallback: bool = False) -> Anthropic | OpenAI:
        """
        Get the appropriate LLM client based on configuration.

        Args:
            use_fallback: If True, use fallback model instead of primary

        Returns:
            Configured LLM client (Anthropic or OpenAI)
        """
        model_config = self.llm_config.fallback_model if use_fallback else self.llm_config.primary_model

        if model_config is None:
            model_config = self.llm_config.primary_model

        if model_config.provider == "anthropic":
            return self.anthropic_client
        elif model_config.provider == "openai":
            return self.openai_client
        else:
            raise ValueError(f"Unsupported provider: {model_config.provider}")

    def call_llm(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        use_fallback: bool = False,
        **kwargs: Any,
    ) -> str:
        """
        Call the LLM with the given prompt.

        Args:
            prompt: User prompt/query
            system_prompt: Optional system prompt (defaults to agent's template)
            use_fallback: Whether to use fallback model
            **kwargs: Additional arguments to pass to the LLM

        Returns:
            LLM response text
        """
        model_config = self.llm_config.fallback_model if use_fallback else self.llm_config.primary_model

        if model_config is None:
            model_config = self.llm_config.primary_model

        system_prompt = system_prompt or self.llm_config.system_prompt_template

        # Merge kwargs with model config defaults
        call_kwargs = {
            "temperature": model_config.temperature,
            "max_tokens": model_config.max_tokens,
            **kwargs,
        }

        self.logger.info(
            "calling_llm",
            provider=model_config.provider,
            model=model_config.model,
            prompt_length=len(prompt),
        )

        try:
            if model_config.provider == "anthropic":
                response = self.anthropic_client.messages.create(
                    model=model_config.model,
                    system=system_prompt,
                    messages=[{"role": "user", "content": prompt}],
                    **call_kwargs,
                )
                return response.content[0].text

            elif model_config.provider == "openai":
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ]
                response = self.openai_client.chat.completions.create(
                    model=model_config.model, messages=messages, **call_kwargs
                )
                return response.choices[0].message.content or ""

            else:
                raise ValueError(f"Unsupported provider: {model_config.provider}")

        except Exception as e:
            self.logger.error("llm_call_failed", error=str(e), provider=model_config.provider)
            raise

    def log_decision(self, decision: AgentDecision) -> None:
        """
        Log an agent decision for transparency and debugging.

        Args:
            decision: AgentDecision instance with decision details
        """
        self.decision_history.append(decision)
        self.logger.info(
            "agent_decision",
            decision_type=decision.decision_type,
            confidence=decision.confidence,
            reasoning=decision.reasoning,
            execution_time=decision.execution_time_seconds,
        )

    def export_decisions(self, filepath: str) -> None:
        """
        Export decision history to JSON file.

        Args:
            filepath: Path to output JSON file
        """
        with open(filepath, "w") as f:
            decisions_dict = [d.model_dump(mode="json") for d in self.decision_history]
            json.dump(decisions_dict, f, indent=2, default=str)

        self.logger.info("decisions_exported", filepath=filepath, count=len(self.decision_history))

    @abstractmethod
    def execute(self, *args: Any, **kwargs: Any) -> Any:
        """
        Execute the agent's primary function.

        Each agent must implement this method with their specific logic.

        Returns:
            Agent-specific output (varies by agent type)
        """
        pass

    def __repr__(self) -> str:
        """String representation of the agent."""
        return f"{self.__class__.__name__}(agent_name='{self.agent_name}')"
